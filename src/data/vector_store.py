"""
Neo4j vector store for semantic search on Chunk nodes.

Used by hybrid retrieval to complement Cypher-based graph queries.
Requires embeddings to be populated via scripts/add_embeddings.py after ingestion.
"""
import os
from typing import Optional

from src.core.logging_config import get_logger

logger = get_logger(__name__)

_vector_store_instance: Optional[object] = None


def get_neo4j_vector_store():
    """
    Get or create Neo4jVector store for similarity search on Chunk nodes.

    Uses from_existing_index when vector index exists, or from_existing_graph
    to create index and populate embeddings on first run.

    Returns:
        Neo4jVector instance, or None if not available (e.g. missing langchain-neo4j).
    """
    global _vector_store_instance
    if _vector_store_instance is not None:
        return _vector_store_instance

    try:
        from langchain_neo4j import Neo4jVector
        from langchain_openai import OpenAIEmbeddings
    except ImportError:
        try:
            from langchain_community.vectorstores.neo4j_vector import Neo4jVector
            from langchain_openai import OpenAIEmbeddings
        except ImportError:
            logger.warning("vector_store_unavailable", reason="langchain-neo4j or langchain_community not installed")
            return None

    url = os.getenv("NEO4J_URI")
    username = os.getenv("NEO4J_USERNAME")
    password = os.getenv("NEO4J_PASSWORD")
    if not all([url, username, password]):
        logger.warning("vector_store_unavailable", reason="Neo4j env vars not set")
        return None

    if url and url.startswith("neo4j+s://"):
        url = url.replace("neo4j+s://", "neo4j+ssc://")

    embeddings = OpenAIEmbeddings()
    index_name = "chunk_vector_index"

    try:
        # Try existing index first (after add_embeddings has been run)
        store = Neo4jVector.from_existing_index(
            embedding=embeddings,
            url=url,
            username=username,
            password=password,
            index_name=index_name,
            node_label="Chunk",
            text_node_property="text",
        )
        logger.info("vector_store_loaded", index=index_name)
    except Exception:
        # Index may not exist; from_existing_graph would create it, but we need Chunks first
        store = None
        logger.info("vector_store_not_ready", hint="Run scripts/add_embeddings.py after ingestion")

    _vector_store_instance = store
    return store
