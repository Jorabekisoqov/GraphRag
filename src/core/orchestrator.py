from src.data.retrieval_types import RetrievalResult
from src.data.graph_rag import fallback_text_search, hybrid_retrieve, _is_weak_result
from src.core.prompts import REFINE_QUERY_SYSTEM, SYNTHESIZE_SYSTEM
from src.core.citation_verify import apply_citation_result, verify_citations
from src.core.embedding_verify import (
    format_answer_with_optional_warning,
    verify_answer_grounding,
)
from src.core.llm_config import get_llm
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.output_parsers import StrOutputParser
from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception_type
from openai import APIError, RateLimitError, APIConnectionError
from src.core.logging_config import get_logger
from src.core.metrics import (
    QueryTimer,
    citation_verify_outcomes,
    embedding_verify_outcomes,
    openai_api_calls,
)

logger = get_logger(__name__)

llm = get_llm(temperature=0)

@retry(
    stop=stop_after_attempt(3),
    wait=wait_exponential(multiplier=1, min=2, max=10),
    retry=retry_if_exception_type((APIError, RateLimitError, APIConnectionError)),
    reraise=True
)
def refine_query(user_query: str) -> str:
    """
    Refines the user's query to be more suitable for graph database retrieval.
    
    Args:
        user_query: The original user query string.
        
    Returns:
        A refined query string optimized for graph database retrieval.
        
    Raises:
        APIError: If OpenAI API call fails after retries.
        RateLimitError: If rate limit is exceeded.
        APIConnectionError: If connection to OpenAI fails.
    """
    openai_api_calls.labels(operation='refine_query').inc()
    prompt = ChatPromptTemplate.from_messages([
        ("system", REFINE_QUERY_SYSTEM),
        ("human", "{question}")
    ])
    chain = prompt | llm | StrOutputParser()
    return chain.invoke({"question": user_query})

@retry(
    stop=stop_after_attempt(3),
    wait=wait_exponential(multiplier=1, min=2, max=10),
    retry=retry_if_exception_type((APIError, RateLimitError, APIConnectionError)),
    reraise=True
)
def synthesize_response(user_query: str, graph_result: str) -> str:
    """
    Synthesizes a final response based on the user's original query and the graph's output.
    
    Args:
        user_query: The original user query string.
        graph_result: The result from the graph database query.
        
    Returns:
        A synthesized natural language response.
        
    Raises:
        APIError: If OpenAI API call fails after retries.
        RateLimitError: If rate limit is exceeded.
        APIConnectionError: If connection to OpenAI fails.
    """
    openai_api_calls.labels(operation='synthesize_response').inc()
    prompt = ChatPromptTemplate.from_messages([
        ("system", SYNTHESIZE_SYSTEM),
        ("human", "{question}")
    ])
    chain = prompt | llm | StrOutputParser()
    return chain.invoke({"question": user_query, "context": graph_result})

def validate_query(user_query: str) -> tuple[bool, str]:
    """
    Validates user query input.
    
    Args:
        user_query: The user query string to validate.
        
    Returns:
        Tuple of (is_valid, error_message). If valid, error_message is empty.
    """
    if not user_query:
        return False, "Please provide a valid query."
    
    if not isinstance(user_query, str):
        return False, "Query must be a string."
    
    # Check length limit
    MAX_QUERY_LENGTH = 2000
    if len(user_query) > MAX_QUERY_LENGTH:
        return False, f"Query is too long. Maximum length is {MAX_QUERY_LENGTH} characters."
    
    # Check for potentially dangerous characters (basic sanitization)
    # Allow most characters but block control characters
    if any(ord(c) < 32 and c not in '\n\r\t' for c in user_query):
        return False, "Query contains invalid characters."
    
    return True, ""

def process_query(user_query: str) -> str:
    """
    Orchestrates the flow from user query to GraphRAG retrieval.
    
    Args:
        user_query: The user's query string.
        
    Returns:
        A natural language response to the user's query.
    """
    logger.info("query_received", query=user_query)
    
    # Validate input
    is_valid, error_message = validate_query(user_query)
    if not is_valid:
        logger.warning("invalid_query_rejected", reason=error_message)
        return error_message

    # Track metrics
    with QueryTimer():
        try:
            # 1. Refine Query
            refined_query = refine_query(user_query)
            logger.info("query_refined", original=user_query, refined=refined_query)

            # 2. Retrieve: hybrid (vector + CONTAINS) or Cypher chain
            rr: RetrievalResult = hybrid_retrieve(
                refined_query, original_query=user_query
            )
            logger.info(
                "retrieve_completed",
                result_length=len(rr.context_for_llm),
                chunk_count=len(rr.chunks),
            )

            # 2b. Fallback: if result still weak, try CONTAINS with original query (raw Uzbek terms)
            if _is_weak_result(rr.context_for_llm):
                rr = fallback_text_search(user_query, original_query=user_query)
                logger.info("fallback_used", original_query=user_query)

            graph_context = rr.context_for_llm
            retrieved_chunks = rr.chunks

            # 3. Synthesize Answer
            final_answer = synthesize_response(user_query, graph_context)
            logger.info("response_synthesized", answer_length=len(final_answer))

            # 3b. Citation verification (non-LLM; stavka/modda vs chunk text)
            try:
                cv = verify_citations(final_answer, retrieved_chunks)
                if cv.mode in ("warn", "strict"):
                    if cv.passed:
                        citation_verify_outcomes.labels(outcome="passed").inc()
                    else:
                        citation_verify_outcomes.labels(outcome="failed").inc()
                    logger.info(
                        "citation_verify",
                        passed=cv.passed,
                        uncited=len(cv.uncited_risky_lines),
                        failed_match=len(cv.failed_chunk_match_lines),
                        unknown_ids=len(cv.unknown_chunk_ids),
                    )
                final_answer = apply_citation_result(final_answer, cv)
            except Exception as cv_err:
                logger.warning("citation_verify_failed", error=str(cv_err))

            # 4. Optional: embedding-based grounding check (non-LLM)
            try:
                weak_ctx = _is_weak_result(graph_context)
                gr = verify_answer_grounding(
                    final_answer, graph_context, is_weak_context=weak_ctx
                )
                if gr.skipped:
                    reason = gr.skipped_reason or ""
                    if reason.startswith("embed_error") or reason == "embed_length_mismatch":
                        embedding_verify_outcomes.labels(outcome="error").inc()
                    else:
                        embedding_verify_outcomes.labels(outcome="skipped").inc()
                    logger.info(
                        "embedding_verify_skipped",
                        reason=gr.skipped_reason,
                        low_sentence_count=gr.low_sentence_count,
                    )
                else:
                    logger.info(
                        "embedding_verify_result",
                        min_score=gr.min_score,
                        mean_score=gr.mean_score,
                        threshold=gr.threshold,
                        low_sentence_count=gr.low_sentence_count,
                    )
                    if gr.min_score is not None and gr.min_score < gr.threshold:
                        embedding_verify_outcomes.labels(outcome="low_score").inc()
                    else:
                        embedding_verify_outcomes.labels(outcome="passed").inc()
                    final_answer = format_answer_with_optional_warning(
                        final_answer, gr
                    )
            except Exception as ev_err:
                embedding_verify_outcomes.labels(outcome="error").inc()
                logger.warning("embedding_verify_failed", error=str(ev_err))

            return final_answer

        except (APIError, RateLimitError, APIConnectionError) as e:
            logger.error("openai_api_error", error=str(e), exc_info=True)
            return "Sorry, I'm experiencing issues connecting to the AI service. Please try again in a moment."
        except Exception as e:
            logger.error("query_processing_error", error=str(e), exc_info=True)
            return "Sorry, I encountered an error while processing your request. Please try again."

if __name__ == "__main__":
    # Test
    print(process_query("Tell me about the accounting standards"))
