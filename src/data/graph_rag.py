from langchain_community.chains.graph_qa.cypher import GraphCypherQAChain
from src.core.llm_config import get_llm
from src.data.neo4j_client import get_neo4j_graph
from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception_type
from typing import Any
from neo4j.exceptions import ServiceUnavailable, TransientError
from src.core.logging_config import get_logger
from src.core.metrics import neo4j_queries
import re

logger = get_logger(__name__)

# Minimum result length to consider retrieval successful
WEAK_RESULT_MIN_LENGTH = 50
WEAK_RESULT_PATTERNS = (
    "don't know",
    "don't have",
    "no result",
    "no information",
    "could not find",
    "couldn't find",
    "i don't",
    "i cannot",
    "не знаю",
    "топа олмадим",
    "маълумот топа олмадим",
    "error querying",
)


def _is_weak_result(s: str) -> bool:
    """Check if the graph/retrieval result is weak (empty, generic, or too short)."""
    if not s or not s.strip():
        return True
    if len(s.strip()) < WEAK_RESULT_MIN_LENGTH:
        return True
    lower = s.lower().strip()
    return any(p in lower for p in WEAK_RESULT_PATTERNS)


def _extract_simple_keywords(query: str, max_keywords: int = 3) -> list[str]:
    """Extract simple keywords from query for fallback search (e.g. first significant words)."""
    # Remove punctuation, split, filter short/common words
    words = re.findall(r"[\w\u0400-\u04FF]+", query)
    stop = {"the", "a", "an", "is", "are", "what", "which", "how", "when", "where", "and", "or", "for", "to", "of", "in", "on", "va", "ва", "қандай", "қайси", "нима"}
    keywords = [w for w in words if len(w) > 2 and w.lower() not in stop][:max_keywords]
    return keywords if keywords else [query.strip()[:50]]  # fallback to first 50 chars


# Domain term patterns for bilingual keyword extraction (Uzbek accounting/BHMS)
_DOMAIN_PATTERNS = [
    r"\d+-?son\s*(?:li\s*)?(?:BHMS|БҲМС)?",  # 1-son, 21-sonli BHMS (Latin)
    r"\d+-?сон\s*(?:ли\s*)?(?:BHMS|БҲМС)?",  # 1-сон (Cyrillic)
    r"\d+-?son\b",  # 21-son alone (Latin)
    r"\d+-?сон\b",  # 21-сон alone (Cyrillic)
    r"БҲМС|BHMS",
    r"\b(?:0\d{3})\b",  # 4-digit account codes: 0110, 4610
    r"hisobvarak|ҳисобварақ|hisobvaraklar",
    r"Moliya|Молия",
]

# Cyrillic to Latin mapping for BHMS terms (сон <-> son, ли <-> li)
_CYRILLIC_TO_LATIN = str.maketrans("сонли", "sonli")
_LATIN_TO_CYRILLIC = str.maketrans("sonli", "сонли")


def _normalize_bhms_for_search(term: str) -> list[str]:
    """
    Return both Cyrillic and Latin variants of a BHMS term for CONTAINS search.
    E.g. '21-сон' -> ['21-сон', '21-son'], '21-son' -> ['21-son', '21-сон']
    """
    variants = [term]
    if "сон" in term or "ли" in term:
        latin = term.translate(_CYRILLIC_TO_LATIN)
        if latin != term and latin not in variants:
            variants.append(latin)
    if "son" in term or "li" in term:
        cyrillic = term.translate(_LATIN_TO_CYRILLIC)
        if cyrillic != term and cyrillic not in variants:
            variants.append(cyrillic)
    return variants


def _extract_domain_terms(text: str) -> list[str]:
    """Extract domain-specific terms (BHMS numbers, account codes, etc.) from text."""
    found: list[str] = []
    for pattern in _DOMAIN_PATTERNS:
        for m in re.finditer(pattern, text, re.IGNORECASE):
            term = m.group(0).strip()
            if term and term not in found:
                found.append(term)
    return found


def _extract_bilingual_keywords(
    refined_query: str, original_query: str, max_keywords: int = 8
) -> list[str]:
    """
    Extract keywords from both refined and original queries, prioritizing original (Uzbek) terms.

    Merges keywords from both sources and adds domain-term extraction (BHMS numbers,
    account codes, etc.). BHMS terms get both Cyrillic and Latin variants for search.
    Domain terms are always included (not capped by max_keywords).
    """
    # Domain terms first (from both queries) - always include, with search variants
    domain_terms = _extract_domain_terms(original_query) + _extract_domain_terms(
        refined_query
    )
    seen: set[str] = set()
    result: list[str] = []
    for t in domain_terms:
        t_lower = t.lower()
        if t_lower not in seen:
            seen.add(t_lower)
            result.append(t)
        # Add Cyrillic/Latin variants for BHMS-like terms
        if re.search(r"\d+.*(?:son|сон)", t, re.IGNORECASE):
            for v in _normalize_bhms_for_search(t):
                v_lower = v.lower()
                if v_lower not in seen:
                    seen.add(v_lower)
                    result.append(v)

    # Original query keywords (prioritize Uzbek terms)
    original_kw = _extract_simple_keywords(original_query, max_keywords=4)
    for w in original_kw:
        if w.lower() not in seen and len(w) >= 2:
            seen.add(w.lower())
            result.append(w)

    # Refined query keywords (fill remaining slots)
    refined_kw = _extract_simple_keywords(refined_query, max_keywords=3)
    for w in refined_kw:
        if w.lower() not in seen and len(w) >= 2:
            seen.add(w.lower())
            result.append(w)

    return result[:max_keywords] if result else _extract_simple_keywords(
        refined_query, max_keywords
    )


def fallback_text_search(
    query: str,
    keywords: list[str] | None = None,
    original_query: str | None = None,
    limit_per_keyword: int = 5,
) -> str:
    """
    Fallback text search using Cypher CONTAINS on Chunk.text when primary retrieval fails.

    Args:
        query: The search query string (typically refined query).
        keywords: Optional list of keywords to search for. If None, extracted from query.
        original_query: Optional original user query for bilingual keyword extraction.
        limit_per_keyword: Max chunks to return per keyword.

    Returns:
        Concatenated chunk texts that match the search.
    """
    graph = get_neo4j_graph()
    if keywords is not None:
        search_terms = keywords
    elif original_query is not None:
        search_terms = _extract_bilingual_keywords(query, original_query, max_keywords=8)
    else:
        search_terms = _extract_simple_keywords(query)
    seen_texts: set[str] = set()
    results: list[str] = []

    for term in search_terms:
        if not term or len(term) < 2:
            continue
        try:
            # Use parameterized query; CONTAINS is case-sensitive, use toLower for both
            # Note: LIMIT must be literal in some Neo4j versions; use fixed cap
            cypher = """
            MATCH (c:Chunk)
            WHERE c.text IS NOT NULL AND toLower(c.text) CONTAINS toLower($keyword)
            RETURN c.text AS text
            LIMIT 5
            """
            raw = graph.query(cypher, {"keyword": term})
            # Neo4jGraph.query may return list of dicts or list of lists
            for row in raw if isinstance(raw, list) else []:
                text = row.get("text") if isinstance(row, dict) else (row[0] if row else None)
                if text and text not in seen_texts:
                    seen_texts.add(text)
                    results.append(text)
        except Exception as e:
            logger.warning("fallback_text_search_error", keyword=term, error=str(e))

    if not results:
        # Last resort: try full query as single keyword (truncated)
        try:
            keyword = query.strip()[:100]
            cypher = """
            MATCH (c:Chunk)
            WHERE c.text IS NOT NULL AND toLower(c.text) CONTAINS toLower($keyword)
            RETURN c.text AS text
            LIMIT 5
            """
            raw = graph.query(cypher, {"keyword": keyword})
            for row in raw if isinstance(raw, list) else []:
                text = row.get("text") if isinstance(row, dict) else (row[0] if row else None)
                if text and text not in seen_texts:
                    seen_texts.add(text)
                    results.append(text)
        except Exception as e:
            logger.warning("fallback_text_search_final_error", error=str(e))

    combined = "\n\n---\n\n".join(results[:10])  # cap total chunks
    logger.info("fallback_text_search_used", query=query, results_count=len(results))
    return combined

def get_graph_rag_chain(model_name: str | None = None) -> GraphCypherQAChain:
    """
    Creates a GraphCypherQAChain for querying the GraphRAG.
    
    Args:
        model_name: The DeepSeek model name (default: deepseek-chat).
        
    Returns:
        A configured GraphCypherQAChain instance.
    """
    graph = get_neo4j_graph()
    
    llm = get_llm(temperature=0, model=model_name)
    
    from langchain_core.prompts import PromptTemplate

    CYPHER_GENERATION_TEMPLATE = """Task: Generate Cypher statement to query a graph database about accounting standards.

Instructions:
- Use only the provided relationship types and property keys in the schema
- Do not use any other relationship types or property keys that are not provided
- The graph has Document and Chunk nodes. Chunk has a "text" property with full content.
- For content questions (regulations, standards, documents): MATCH (d:Document)-[:CONTAINS]->(c:Chunk) WHERE c.text CONTAINS $keyword RETURN c.text
- If full-text index "chunk_text_index" exists: CALL db.index.fulltext.queryNodes("chunk_text_index", $query) YIELD node, score RETURN node.text AS text
- Always return Chunk.text when answering content questions. Use CONTAINS on c.text or fulltext query.
- For accounting queries, prioritize retrieving:
  1. Nodes with "account", "hisob", "kod" properties (account codes)
  2. Relationships showing debit/credit flows
  3. Nodes related to "valyuta", "kurs", "exchange" (currency/exchange rate)
  4. Properties containing accounting methods ("hisob usuli")
- When searching for account codes, use CONTAINS or exact match on "account" property
- For debit/credit entries, look for relationships or properties indicating transaction flows
- The database content is primarily in Uzbek language (e.g. 'Buxgalteriya', 'Asosiy vositalar')
- When searching for string values, always try to translate the user's English keywords into Uzbek or use broad CONTAINS queries if unsure
- Example: 'accounting' -> 'buxgalteriya', 'account code' -> search for 'account' or 'hisob' property

Note: Do not include any explanations or apologies in your responses.
Do not respond to any questions that might ask anything else than for you to construct a Cypher statement.

Schema:
{schema}

The question is:
{question}"""

    CYPHER_GENERATION_PROMPT = PromptTemplate(
        input_variables=["schema", "question"], template=CYPHER_GENERATION_TEMPLATE
    )

    chain = GraphCypherQAChain.from_llm(
        llm=llm,
        graph=graph,
        cypher_prompt=CYPHER_GENERATION_PROMPT,
        verbose=True,
        allow_dangerous_requests=True
    )
    return chain

@retry(
    stop=stop_after_attempt(3),
    wait=wait_exponential(multiplier=1, min=2, max=10),
    retry=retry_if_exception_type((ServiceUnavailable, TransientError)),
    reraise=True
)
def query_graph(query: str) -> str:
    """
    Executes a query against the GraphRAG system.
    
    Args:
        query: The query string to execute against the graph.
        
    Returns:
        The result string from the graph query.
        
    Raises:
        ServiceUnavailable: If Neo4j service is unavailable after retries.
        TransientError: If a transient Neo4j error occurs after retries.
        Exception: For other errors, returns error message string.
    """
    chain = get_graph_rag_chain()
    try:
        response = chain.invoke({"query": query})
        logger.info(
            "graph_query_success",
            query=query,
            result_length=len(response.get("result", "")),
        )
        neo4j_queries.labels(status='success').inc()
        return response["result"]
    except (ServiceUnavailable, TransientError) as e:
        logger.error("neo4j_connection_error", error=str(e), exc_info=True)
        neo4j_queries.labels(status='error').inc()
        raise
    except Exception as e:
        logger.error("graph_query_error", query=query, error=str(e), exc_info=True)
        neo4j_queries.labels(status='error').inc()
        return f"Error querying graph: {e}"

def hybrid_retrieve(
    query: str,
    original_query: str | None = None,
    k_vector: int = 3,
) -> str:
    """
    Hybrid retrieval: combine vector search (if available) with CONTAINS text search.

    Vector search provides semantic similarity; CONTAINS provides keyword match.
    Both return raw chunk text for synthesis.

    Args:
        query: The search query (typically refined query).
        original_query: Optional original user query for bilingual keyword extraction.
        k_vector: Number of chunks to retrieve via vector search.

    Returns:
        Merged context string from both retrieval sources.
    """
    seen_texts: set[str] = set()
    results: list[str] = []

    # 1. Vector search (optional - skip if not available)
    try:
        from src.data.vector_store import get_neo4j_vector_store

        store = get_neo4j_vector_store()
        if store is not None:
            docs_with_score = store.similarity_search_with_score(query, k=k_vector)
            for doc, _ in docs_with_score:
                text = doc.page_content if hasattr(doc, "page_content") else str(doc)
                if text and text not in seen_texts:
                    seen_texts.add(text)
                    results.append(text)
            logger.info("hybrid_vector_results", count=len(results))
    except Exception as e:
        logger.warning("hybrid_vector_skip", error=str(e))

    # 2. CONTAINS text search (Cypher on Chunk.text) - always run for keyword coverage
    fallback_result = fallback_text_search(query, original_query=original_query)
    if fallback_result:
        for part in fallback_result.split("\n\n---\n\n"):
            if part.strip() and part.strip() not in seen_texts:
                seen_texts.add(part.strip())
                results.append(part.strip())

    # 3. If we have vector store, use hybrid result; else run full Cypher chain
    if results:
        combined = "\n\n---\n\n".join(results[:10])
        return combined

    # No vector + empty fallback: run GraphCypherQAChain (may return LLM answer)
    return query_graph(query)


if __name__ == "__main__":
    # Test the chain
    print(query_graph("What rules are in the database?"))
