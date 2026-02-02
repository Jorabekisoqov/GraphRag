from src.data.graph_rag import query_graph
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def process_query(user_query: str) -> str:
    """
    Orchestrates the flow from user query to GraphRAG retrieval.
    """
    logger.info(f"Received query: {user_query}")
    
    if not user_query:
        return "Please provide a valid query."

    # In the future, we can add intent classification or other steps here.
    
    try:
        result = query_graph(user_query)
        logger.info(f"Result: {result}")
        return result
    except Exception as e:
        logger.error(f"Error processing query: {e}")
        return "Sorry, I encountered an error while processing your request."

if __name__ == "__main__":
    print(process_query("Test query"))
