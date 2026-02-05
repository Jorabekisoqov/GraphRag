from src.data.graph_rag import query_graph
from langchain_openai import ChatOpenAI
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.output_parsers import StrOutputParser
from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception_type
import os
from openai import APIError, RateLimitError, APIConnectionError
from src.core.logging_config import get_logger
from src.core.metrics import QueryTimer, openai_api_calls

logger = get_logger(__name__)

llm = ChatOpenAI(temperature=0, model="gpt-4o")

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
        ("system", """You are an expert at translating user questions into specific Cypher-ready search intents for a knowledge graph about legal regulations and accounting standards (BHMS).

The graph contains Documents, Chunks, and Entities with properties like:
- Account codes (account, hisob, kod)
- Accounting entries (debit, credit)
- Exchange rate information (valyuta, kurs, exchange)
- Accounting methods (hisob usuli)

When the user asks about accounting topics, prioritize finding:
1. Specific account codes and their usage
2. Debit/credit entry structures
3. Exchange rate profit/loss treatment
4. Accounting methods and procedures

Translate accounting terms:
- "account" -> "hisob" or search for "account" property
- "debit" -> "debit" or "DT"
- "credit" -> "credit" or "KT"
- "exchange rate" -> "valyuta kursi" or "kurs"
- "profit/loss" -> "foyda/zarar"

If the user asks broadly like 'Tell me about X', convert it to 'Find all information relative to X including account codes, debit/credit entries, and exchange rate treatment'.
Do NOT ask the user for clarification. Make your best guess for a search query."""),
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
        ("system", """You are an expert accounting assistant specializing in Uzbek accounting standards (BHMS).

Your responses MUST include:
1. SPECIFIC ACCOUNT CODES: When account codes are mentioned in the context, always state them explicitly (e.g., "Account 9300", "Hisob 1230")
2. DEBIT/CREDIT ENTRIES: For any accounting transaction, clearly specify:
   - Which accounts are debited and credited
   - The amounts (if available)
   - The accounting treatment
3. EXCHANGE RATE TREATMENT: For currency/exchange rate questions, explain:
   - How exchange rate differences are treated
   - Which accounts record exchange rate profit/loss
   - When exchange rate differences are recognized
4. DATA STRUCTURE REVIEW: Always reference specific sections, paragraphs, or tables from the provided context
5. STRUCTURED FORMAT: Use clear formatting:
   - Account codes: Bold or clearly marked
   - Debit entries: Clearly labeled "Debit:"
   - Credit entries: Clearly labeled "Credit:"
   - Exchange rate treatment: Separate section

If the context contains tables, account codes, or specific accounting entries, you MUST reference them explicitly.
Do not provide vague answers. If specific details are in the context, include them.

Context from Knowledge Graph: {context}

If the context says 'I don't know' or is empty, politely inform the user you couldn't find relevant information in the specific documents."""),
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

            # 2. Retrieve from Graph
            # Check if the refined query suggests it's just a greeting (heuristic or LLM based)
            # For simplicity, we send everything to the graph unless it's obviously non-query.
            # But GraphCypherQAChain can be expensive/slow for "Hi". 
            # For this iteration, we accept the cost for robustness.
            graph_result = query_graph(refined_query)
            logger.info("graph_query_completed", result_length=len(graph_result))

            # 3. Synthesize Answer
            final_answer = synthesize_response(user_query, graph_result)
            logger.info("response_synthesized", answer_length=len(final_answer))
            
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
