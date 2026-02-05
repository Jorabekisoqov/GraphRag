"""Health check functionality."""
from typing import Dict, Any
from src.data.neo4j_client import get_neo4j_graph
from src.core.logging_config import get_logger
from src.core.metrics import neo4j_connection_status, openai_api_status

logger = get_logger(__name__)


def check_neo4j_health() -> tuple[bool, str]:
    """
    Check Neo4j database connection health.
    
    Returns:
        Tuple of (is_healthy, message).
    """
    try:
        graph = get_neo4j_graph()
        graph.refresh_schema()
        neo4j_connection_status.set(1)
        return True, "Neo4j connection healthy"
    except Exception as e:
        logger.error("neo4j_health_check_failed", error=str(e), exc_info=True)
        neo4j_connection_status.set(0)
        return False, f"Neo4j connection failed: {str(e)}"


def check_openai_health() -> tuple[bool, str]:
    """
    Check OpenAI API health (basic connectivity test).
    
    Returns:
        Tuple of (is_healthy, message).
    """
    try:
        from langchain_openai import ChatOpenAI
        from langchain_core.prompts import ChatPromptTemplate
        from langchain_core.output_parsers import StrOutputParser
        
        llm = ChatOpenAI(temperature=0, model="gpt-4o", max_tokens=10)
        prompt = ChatPromptTemplate.from_messages([("human", "Say 'ok'")])
        chain = prompt | llm | StrOutputParser()
        response = chain.invoke({})
        
        if response:
            openai_api_status.set(1)
            return True, "OpenAI API connection healthy"
        else:
            openai_api_status.set(0)
            return False, "OpenAI API returned empty response"
    except Exception as e:
        logger.error("openai_health_check_failed", error=str(e), exc_info=True)
        openai_api_status.set(0)
        return False, f"OpenAI API connection failed: {str(e)}"


def get_health_status() -> Dict[str, Any]:
    """
    Get overall health status of the system.
    
    Returns:
        Dictionary with health status information.
    """
    neo4j_healthy, neo4j_message = check_neo4j_health()
    openai_healthy, openai_message = check_openai_health()
    
    overall_healthy = neo4j_healthy and openai_healthy
    
    return {
        "status": "healthy" if overall_healthy else "unhealthy",
        "neo4j": {
            "healthy": neo4j_healthy,
            "message": neo4j_message
        },
        "openai": {
            "healthy": openai_healthy,
            "message": openai_message
        }
    }
