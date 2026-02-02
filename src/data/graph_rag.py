from langchain_community.chains.graph_qa.cypher import GraphCypherQAChain
from langchain_openai import ChatOpenAI
from src.data.neo4j_client import get_neo4j_graph
import os

def get_graph_rag_chain(model_name="gpt-4o"):
    """
    Creates a GraphCypherQAChain for querying the GraphRAG.
    """
    graph = get_neo4j_graph()
    
    llm = ChatOpenAI(temperature=0, model=model_name)
    
    from langchain_core.prompts import PromptTemplate

    CYPHER_GENERATION_TEMPLATE = """Task:Generate Cypher statement to query a graph database.
Instructions:
Use only the provided relationship types and property keys in the schema.
Do not use any other relationship types or property keys that are not provided.
Schema:
{schema}
Note: Do not include any explanations or apologies in your responses.
Do not respond to any questions that might ask anything else than for you to construct a Cypher statement.
The database content is primarily in Uzbek language (e.g. 'Buxgalteriya', 'Asosiy vositalar').
When searching for string values, always try to translate the user's English keywords into Uzbek or use broad CONTAINS queries if unsure.
Example: 'accounting' -> 'buxgalteriya'
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
