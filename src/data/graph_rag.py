from __future__ import annotations

import hashlib

from langchain_community.chains.graph_qa.cypher import GraphCypherQAChain
from src.core.llm_config import get_llm
from src.data.neo4j_client import get_neo4j_graph
from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception_type
from typing import Any
from neo4j.exceptions import ServiceUnavailable, TransientError
from src.core.logging_config import get_logger
from src.core.metrics import neo4j_queries
import os
import re

from src.data.retrieval_types import RetrievedChunk, RetrievalResult

logger = get_logger(__name__)

# Retrieval tuning (env overrides)
def _env_int(name: str, default: int) -> int:
    raw = os.getenv(name)
    if raw is None or raw.strip() == "":
        return default
    try:
        return max(1, int(raw))
    except ValueError:
        return default


FALLBACK_CHUNK_LIMIT = _env_int("FALLBACK_CHUNK_LIMIT", 8)
HYBRID_VECTOR_K = _env_int("HYBRID_VECTOR_K", 8)
FALLBACK_MERGE_CAP = _env_int("FALLBACK_MERGE_CAP", 12)
FULLTEXT_INDEX_NAME = os.getenv("CHUNK_FULLTEXT_INDEX", "chunk_text_index")


def _synthetic_chunk_id(text: str) -> str:
    """Stable id when Neo4j id is missing (dedupe/debug only)."""
    h = hashlib.sha256(text.encode("utf-8")).hexdigest()[:16]
    return f"hash_{h}"


def _chunk_from_row(row: dict[str, Any] | Any, text_key: str = "text") -> RetrievedChunk | None:
    """Build RetrievedChunk from a Cypher row dict."""
    if not isinstance(row, dict):
        return None
    text = row.get(text_key)
    if not text:
        return None
    cid = row.get("id")
    if cid is None or str(cid).strip() == "":
        cid = _synthetic_chunk_id(str(text))
    return RetrievedChunk(id=str(cid), text=str(text))


def _lookup_chunk_id_by_text(graph: Any, text: str) -> str | None:
    """Resolve Chunk.id from exact text match (vector path fallback)."""
    try:
        raw = graph.query(
            "MATCH (c:Chunk) WHERE c.text = $t RETURN c.id AS id LIMIT 1",
            {"t": text},
        )
        if not raw or not isinstance(raw, list):
            return None
        row = raw[0]
        if isinstance(row, dict):
            cid = row.get("id")
            return str(cid) if cid is not None else None
        return str(row[0]) if row else None
    except Exception as e:
        logger.debug("lookup_chunk_id_by_text_failed", error=str(e))
        return None


def format_chunks_for_llm(chunks: list[RetrievedChunk]) -> str:
    """Format labeled chunks for the synthesizer (matches citation prompt)."""
    if not chunks:
        return ""
    parts = [f"[CHUNK {c.id}]\n{c.text}" for c in chunks]
    return "\n\n---\n\n".join(parts)


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


# Domain term patterns for bilingual keyword extraction (Uzbek accounting/BHMS/Soliq Kodeksi)
_DOMAIN_PATTERNS = [
    r"\d+-?son\s*(?:li\s*)?(?:BHMS|БҲМС)?",  # 1-son, 21-sonli BHMS (Latin)
    r"\d+-?сон\s*(?:ли\s*)?(?:BHMS|БҲМС)?",  # 1-сон (Cyrillic)
    r"\d+-?son\b",  # 21-son alone (Latin)
    r"\d+-?сон\b",  # 21-сон alone (Cyrillic)
    r"БҲМС|BHMS",
    r"\b(?:0\d{3})\b",  # 4-digit account codes: 0110, 4610
    r"hisobvarak|ҳисобварақ|hisobvaraklar",
    r"Moliya|Молия",
    # Soliq Kodeksi / tax articles (Latin)
    r"\d{1,3}-moddasi",
    r"\d{1,3}-moddasining",
    r"\d{1,3}-modda",
    r"\d{1,3}\s+modda\b",
    # Cyrillic variants (модда)
    r"\d{1,3}-модда",
    r"\d{1,3}\s+модда\b",
]

# Cyrillic to Latin mapping for BHMS terms (сон <-> son, ли <-> li)
_CYRILLIC_TO_LATIN = str.maketrans("сонли", "sonli")
_LATIN_TO_CYRILLIC = str.maketrans("sonli", "сонли")


def _normalize_modda_for_search(term: str) -> list[str]:
    """Latin/Cyrillic variants for tax article references (CONTAINS search)."""
    variants = [term]
    if re.search(r"модда", term, re.IGNORECASE):
        latin = re.sub(r"модда", "modda", term, flags=re.IGNORECASE)
        if latin != term and latin not in variants:
            variants.append(latin)
    if re.search(r"modda", term, re.IGNORECASE) and not re.search(r"модда", term, re.IGNORECASE):
        cyr = re.sub(r"modda", "модда", term, flags=re.IGNORECASE)
        if cyr != term and cyr not in variants:
            variants.append(cyr)
    return variants


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
    account codes, Soliq Kodeksi modda references, etc.). BHMS/modda terms get
    Cyrillic/Latin variants for search. Domain terms are never truncated; filler
    keywords from the queries are capped by max_keywords.
    """
    # Domain terms first (from both queries) - always include, with search variants
    domain_terms = _extract_domain_terms(original_query) + _extract_domain_terms(
        refined_query
    )
    seen: set[str] = set()
    domain_result: list[str] = []
    for t in domain_terms:
        t_lower = t.lower()
        if t_lower not in seen:
            seen.add(t_lower)
            domain_result.append(t)
        # Add Cyrillic/Latin variants for BHMS-like terms
        if re.search(r"\d+.*(?:son|сон)", t, re.IGNORECASE):
            for v in _normalize_bhms_for_search(t):
                v_lower = v.lower()
                if v_lower not in seen:
                    seen.add(v_lower)
                    domain_result.append(v)
        # Modda (tax article) variants
        if re.search(r"\d+.*(?:modda|модда)", t, re.IGNORECASE):
            for v in _normalize_modda_for_search(t):
                v_lower = v.lower()
                if v_lower not in seen:
                    seen.add(v_lower)
                    domain_result.append(v)

    filler: list[str] = []
    # Original query keywords (prioritize Uzbek terms)
    original_kw = _extract_simple_keywords(original_query, max_keywords=4)
    for w in original_kw:
        if w.lower() not in seen and len(w) >= 2:
            seen.add(w.lower())
            filler.append(w)

    # Refined query keywords (fill remaining slots)
    refined_kw = _extract_simple_keywords(refined_query, max_keywords=3)
    for w in refined_kw:
        if w.lower() not in seen and len(w) >= 2:
            seen.add(w.lower())
            filler.append(w)

    if not domain_result and not filler:
        return _extract_simple_keywords(refined_query, max_keywords)

    # Domain terms always kept; filler capped so total keyword queries stay bounded
    return domain_result + filler[:max_keywords]


def _parse_modda_raqam_from_queries(*texts: str) -> str | None:
    """Extract first tax-article number (N-modda) from user/refined queries."""
    for t in texts:
        if not t:
            continue
        m = re.search(r"(\d{1,3})-moddasi", t, re.IGNORECASE)
        if m:
            return m.group(1)
        m = re.search(r"(\d{1,3})-moddasining", t, re.IGNORECASE)
        if m:
            return m.group(1)
        m = re.search(r"(\d{1,3})-modda", t, re.IGNORECASE)
        if m:
            return m.group(1)
        m = re.search(r"(\d{1,3})\s+modda\b", t, re.IGNORECASE)
        if m:
            return m.group(1)
        m = re.search(r"(\d{1,3})-модда", t, re.IGNORECASE)
        if m:
            return m.group(1)
    return None


def _modda_fast_path_chunks(
    graph: Any, modda: str, limit: int
) -> list[RetrievedChunk]:
    """Return chunks where modda_numbers (from ingest) contains this article number."""
    out: list[RetrievedChunk] = []
    try:
        cypher = """
        MATCH (c:Chunk)
        WHERE c.modda_numbers IS NOT NULL AND $modda IN c.modda_numbers AND c.text IS NOT NULL
        RETURN c.id AS id, c.text AS text
        LIMIT $lim
        """
        raw = graph.query(cypher, {"modda": str(modda), "lim": limit})
        for row in raw if isinstance(raw, list) else []:
            ch = _chunk_from_row(row) if isinstance(row, dict) else None
            if ch:
                out.append(ch)
    except Exception as e:
        logger.warning("modda_fast_path_error", modda=modda, error=str(e))
    return out


def _fulltext_search_chunks(
    graph: Any, query: str, limit: int
) -> list[RetrievedChunk]:
    """Full-text search on Chunk.text using Neo4j full-text index (if present)."""
    if not query or len(query.strip()) < 2:
        return []
    out: list[RetrievedChunk] = []
    try:
        cypher = """
        CALL db.index.fulltext.queryNodes($index_name, $q) YIELD node, score
        RETURN node.id AS id, node.text AS text
        LIMIT $lim
        """
        raw = graph.query(
            cypher,
            {"index_name": FULLTEXT_INDEX_NAME, "q": query.strip()[:500], "lim": limit},
        )
        for row in raw if isinstance(raw, list) else []:
            ch = _chunk_from_row(row) if isinstance(row, dict) else None
            if ch:
                out.append(ch)
    except Exception as e:
        logger.debug("fulltext_search_skipped", error=str(e))
    return out


def _merge_chunks(
    seen_texts: set[str],
    bucket: list[RetrievedChunk],
    new_chunks: list[RetrievedChunk],
) -> None:
    for ch in new_chunks:
        if ch.text and ch.text not in seen_texts:
            seen_texts.add(ch.text)
            bucket.append(ch)


def fallback_text_search(
    query: str,
    keywords: list[str] | None = None,
    original_query: str | None = None,
    limit_per_keyword: int | None = None,
) -> RetrievalResult:
    """
    Fallback text search: optional modda fast path, full-text index, then CONTAINS on Chunk.text.

    Args:
        query: The search query string (typically refined query).
        keywords: Optional list of keywords to search for. If None, extracted from query.
        original_query: Optional original user query for bilingual keyword extraction.
        limit_per_keyword: Max chunks per keyword (default: FALLBACK_CHUNK_LIMIT env).

    Returns:
        RetrievalResult with labeled context_for_llm and RetrievedChunk list.
    """
    graph = get_neo4j_graph()
    lim = limit_per_keyword if limit_per_keyword is not None else FALLBACK_CHUNK_LIMIT
    merge_cap = FALLBACK_MERGE_CAP

    if keywords is not None:
        search_terms = keywords
    elif original_query is not None:
        search_terms = _extract_bilingual_keywords(query, original_query, max_keywords=8)
    else:
        search_terms = _extract_simple_keywords(query)

    seen_texts: set[str] = set()
    results: list[RetrievedChunk] = []

    # 1) Fast path: chunk.modda_numbers from ingest (Soliq Kodeksi Modda entities)
    modda_n = _parse_modda_raqam_from_queries(
        query, original_query or "", *(search_terms[:3] if search_terms else [])
    )
    if modda_n:
        _merge_chunks(seen_texts, results, _modda_fast_path_chunks(graph, modda_n, lim))

    # 2) Full-text index (best-effort; 1–2 query strings)
    if original_query:
        ft_queries: list[str] = []
        strong = next(
            (t for t in search_terms if re.search(r"modda|модда", t, re.IGNORECASE)),
            None,
        )
        if strong:
            ft_queries.append(strong)
        qstrip = query.strip()[:200]
        if qstrip and qstrip not in ft_queries:
            ft_queries.append(qstrip)
        for ftq in ft_queries[:2]:
            _merge_chunks(seen_texts, results, _fulltext_search_chunks(graph, ftq, lim))
    else:
        _merge_chunks(
            seen_texts, results, _fulltext_search_chunks(graph, query.strip()[:200], lim)
        )

    # 3) CONTAINS per keyword (parameterized LIMIT)
    cypher_contains = """
    MATCH (c:Chunk)
    WHERE c.text IS NOT NULL AND toLower(c.text) CONTAINS toLower($keyword)
    RETURN c.id AS id, c.text AS text
    LIMIT $lim
    """
    for term in search_terms:
        if not term or len(term) < 2:
            continue
        try:
            raw = graph.query(cypher_contains, {"keyword": term, "lim": lim})
            for row in raw if isinstance(raw, list) else []:
                ch = _chunk_from_row(row) if isinstance(row, dict) else None
                if ch:
                    _merge_chunks(seen_texts, results, [ch])
        except Exception as e:
            logger.warning("fallback_text_search_error", keyword=term, error=str(e))

    if not results:
        # Last resort: try full query as single keyword (truncated)
        try:
            keyword = query.strip()[:100]
            raw = graph.query(cypher_contains, {"keyword": keyword, "lim": lim})
            for row in raw if isinstance(raw, list) else []:
                ch = _chunk_from_row(row) if isinstance(row, dict) else None
                if ch:
                    _merge_chunks(seen_texts, results, [ch])
        except Exception as e:
            logger.warning("fallback_text_search_final_error", error=str(e))

    capped = results[:merge_cap]
    combined = format_chunks_for_llm(capped)
    logger.info("fallback_text_search_used", query=query, results_count=len(results))
    return RetrievalResult(context_for_llm=combined, chunks=capped)

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

    CYPHER_GENERATION_TEMPLATE = """Task: Generate Cypher to query a graph database of Uzbek legal and accounting texts (Soliq kodeksi, BHMS, regulations).

Instructions:
- Use only the provided relationship types and property keys in the schema
- Do not use any other relationship types or property keys that are not provided
- The graph has Document and Chunk nodes. Chunk has a "text" property with full content.
- For content questions (laws, standards, documents): MATCH (d:Document)-[:CONTAINS]->(c:Chunk) WHERE c.text CONTAINS $keyword RETURN c.text
- If full-text index "chunk_text_index" exists: CALL db.index.fulltext.queryNodes("chunk_text_index", $query) YIELD node, score RETURN node.text AS text
- Always return Chunk.text for content questions. Use CONTAINS on c.text or fulltext query.
- If the question mentions modda, Soliq kodeksi, soliq, band, or tax articles: prioritize Chunk text search with those Uzbek/legal keywords (and digits from article numbers). Do not assume accounting-only content.
- If the question is about accounting, hisob, debit/credit, BHMS, valyuta, or kurs: also retrieve nodes/properties related to account codes ("account", "hisob", "kod"), debit/credit flows, valyuta/kurs/exchange, or "hisob usuli" when present in the schema.
- The database content is primarily in Uzbek (e.g. 'Buxgalteriya', 'Soliq kodeksi', 'modda')
- Translate English keywords into Uzbek when helpful, or use broad CONTAINS if unsure

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
    k_vector: int | None = None,
) -> RetrievalResult:
    """
    Hybrid retrieval: combine vector search (if available) with CONTAINS text search.

    Vector search provides semantic similarity; CONTAINS provides keyword match.
    Returns labeled context and chunk ids for citation verification.

    Args:
        query: The search query (typically refined query).
        original_query: Optional original user query for bilingual keyword extraction.
        k_vector: Number of chunks to retrieve via vector search (default: HYBRID_VECTOR_K env).

    Returns:
        RetrievalResult with context_for_llm and chunks list.
    """
    kv = k_vector if k_vector is not None else HYBRID_VECTOR_K
    seen_texts: set[str] = set()
    merged: list[RetrievedChunk] = []
    graph = get_neo4j_graph()

    # 1. Vector search (optional - skip if not available)
    try:
        from src.data.vector_store import get_neo4j_vector_store

        store = get_neo4j_vector_store()
        if store is not None:
            docs_with_score = store.similarity_search_with_score(query, k=kv)
            for doc, _ in docs_with_score:
                text = doc.page_content if hasattr(doc, "page_content") else str(doc)
                if not text or not str(text).strip():
                    continue
                text = str(text).strip()
                if text in seen_texts:
                    continue
                meta = getattr(doc, "metadata", None) or {}
                cid = meta.get("id") or meta.get("chunk_id")
                if not cid:
                    cid = _lookup_chunk_id_by_text(graph, text) or _synthetic_chunk_id(text)
                seen_texts.add(text)
                merged.append(RetrievedChunk(id=str(cid), text=text))
            logger.info("hybrid_vector_results", count=len(merged))
    except Exception as e:
        logger.warning("hybrid_vector_skip", error=str(e))

    # 2. Fallback: modda fast path + full-text + CONTAINS on Chunk.text
    fb = fallback_text_search(query, original_query=original_query)
    for ch in fb.chunks:
        if ch.text and ch.text not in seen_texts:
            seen_texts.add(ch.text)
            merged.append(ch)

    # 3. If we have any chunks, return merged labeled context
    if merged:
        capped = merged[:FALLBACK_MERGE_CAP]
        return RetrievalResult(
            context_for_llm=format_chunks_for_llm(capped),
            chunks=capped,
        )

    # No vector + empty fallback: run GraphCypherQAChain (may return LLM answer)
    qg = query_graph(query)
    return RetrievalResult(context_for_llm=qg, chunks=[])


if __name__ == "__main__":
    # Test the chain
    print(query_graph("What rules are in the database?"))
