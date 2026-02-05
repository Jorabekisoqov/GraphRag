from langchain_community.chains.graph_qa.cypher import GraphCypherQAChain
from langchain_openai import ChatOpenAI
from src.data.neo4j_client import get_neo4j_graph
from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception_type
from typing import Any
from neo4j.exceptions import ServiceUnavailable, TransientError
from src.core.logging_config import get_logger
from src.core.metrics import neo4j_queries

logger = get_logger(__name__)

def get_graph_rag_chain(model_name: str = "gpt-4o") -> GraphCypherQAChain:
    """
    Creates a GraphCypherQAChain for querying the GraphRAG.
    
    Args:
        model_name: The OpenAI model name to use.
        
    Returns:
        A configured GraphCypherQAChain instance.
    """
    graph = get_neo4j_graph()
    
    llm = ChatOpenAI(temperature=0, model=model_name)
    
    from langchain_core.prompts import PromptTemplate

    CYPHER_GENERATION_TEMPLATE = """Task: Generate Cypher statement to query a graph database about accounting standards.

Instructions:
- Use only the provided relationship types and property keys in the schema
- Do not use any other relationship types or property keys that are not provided
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
        logger.info("graph_query_success", query=query)
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

if __name__ == "__main__":
    # Test the chain
    print(query_graph("What rules are in the database?"))
