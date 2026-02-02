import os
from dotenv import load_dotenv
from langchain_community.graphs import Neo4jGraph

load_dotenv()

def get_neo4j_graph():
    """
    Establishes a connection to the Neo4j database using environment variables.
    Returns:
        Neo4jGraph: A LangChain Neo4j graph object.
    """
    url = os.getenv("NEO4J_URI")
    username = os.getenv("NEO4J_USERNAME")
    password = os.getenv("NEO4J_PASSWORD")
    
    # Relax SSL verification if needed (e.g. self-signed or missing root CAs)
    if url and url.startswith("neo4j+s://"):
        print("Warning: Downgrading to neo4j+ssc:// to bypass SSL verification errors.")
        url = url.replace("neo4j+s://", "neo4j+ssc://")

    if not all([url, username, password]):
        raise ValueError("Neo4j configuration not found in environment variables.")

    graph = Neo4jGraph(
        url=url,
        username=username,
        password=password
    )
    return graph

if __name__ == "__main__":
    try:
        g = get_neo4j_graph()
        g.refresh_schema()
        print(f"Connected to Neo4j! Schema: {g.schema[:100]}...")
    except Exception as e:
        print(f"Failed to connect: {e}")
