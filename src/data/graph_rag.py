from langchain.chains import GraphCypherQAChain
from langchain_openai import ChatOpenAI
from src.data.neo4j_client import get_neo4j_graph
import os

def get_graph_rag_chain(model_name="gpt-4o"):
    """
    Creates a GraphCypherQAChain for querying the GraphRAG.
    """
    graph = get_neo4j_graph()
    
    llm = ChatOpenAI(temperature=0, model=model_name)
    
    chain = GraphCypherQAChain.from_llm(
        llm=llm,
        graph=graph,
        verbose=True,
        allow_dangerous_requests=True
    )
    return chain

def query_graph(query: str):
    """
    Executes a query against the GraphRAG system.
    """
    chain = get_graph_rag_chain()
    try:
        response = chain.invoke({"query": query})
        return response["result"]
    except Exception as e:
        return f"Error querying graph: {e}"

if __name__ == "__main__":
    # Test the chain
    print(query_graph("What rules are in the database?"))
