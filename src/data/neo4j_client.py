import os
from typing import Optional
from dotenv import load_dotenv
from langchain_community.graphs import Neo4jGraph
from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception_type
from neo4j.exceptions import ServiceUnavailable, TransientError
from src.core.logging_config import get_logger

load_dotenv()

logger = get_logger(__name__)

# Global graph instance for connection pooling
_graph_instance: Optional[Neo4jGraph] = None

@retry(
    stop=stop_after_attempt(3),
    wait=wait_exponential(multiplier=1, min=2, max=10),
    retry=retry_if_exception_type((ServiceUnavailable, TransientError)),
    reraise=True
)
def get_neo4j_graph() -> Neo4jGraph:
    """
    Establishes a connection to the Neo4j database using environment variables.
    Uses a singleton pattern to maintain connection pooling.
    
    Returns:
        Neo4jGraph: A LangChain Neo4j graph object.
        
    Raises:
        ValueError: If Neo4j configuration is missing.
        ServiceUnavailable: If Neo4j service is unavailable after retries.
        TransientError: If a transient Neo4j error occurs after retries.
    """
    global _graph_instance
    
    # Return cached instance if available
    if _graph_instance is not None:
        return _graph_instance
    
    url = os.getenv("NEO4J_URI")
    username = os.getenv("NEO4J_USERNAME")
    password = os.getenv("NEO4J_PASSWORD")
    
    if not all([url, username, password]):
        raise ValueError("Neo4j configuration not found in environment variables.")
    
    # Relax SSL verification if needed (e.g. self-signed or missing root CAs)
    if url and url.startswith("neo4j+s://"):
        logger.warning("ssl_downgrade", original_url=url)
        url = url.replace("neo4j+s://", "neo4j+ssc://")

    try:
        _graph_instance = Neo4jGraph(
            url=url,
            username=username,
            password=password
        )
        # Test connection
        _graph_instance.refresh_schema()
        logger.info("neo4j_connected", url=url)
        return _graph_instance
    except (ServiceUnavailable, TransientError) as e:
        logger.error("neo4j_connection_error", error=str(e), exc_info=True)
        raise
    except Exception as e:
        logger.error("neo4j_unexpected_error", error=str(e), exc_info=True)
        raise

if __name__ == "__main__":
    try:
        g = get_neo4j_graph()
        g.refresh_schema()
        print(f"Connected to Neo4j! Schema: {g.schema[:100]}...")
    except Exception as e:
        print(f"Failed to connect: {e}")
