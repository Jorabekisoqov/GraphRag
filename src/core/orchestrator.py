from src.data.graph_rag import query_graph
from langchain_openai import ChatOpenAI
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.output_parsers import StrOutputParser
import logging
import os

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

llm = ChatOpenAI(temperature=0, model="gpt-4o")

def refine_query(user_query: str) -> str:
    """
    Refines the user's query to be more suitable for graph database retrieval.
    """
    prompt = ChatPromptTemplate.from_messages([
        ("system", "You are an expert at translating user questions into specific Cypher-ready search intents for a knowledge graph about legal regulations and accounting standards. \n"
                   "The graph contains Documents, Chunks, and Entities. \n"
                   "If the user asks broadly like 'Tell me about X', convert it to 'Find all information relative to X'. \n"
                   "Do NOT ask the user for clarification. Make your best guess for a search query."),
        ("human", "{question}")
    ])
    chain = prompt | llm | StrOutputParser()
    return chain.invoke({"question": user_query})

def synthesize_response(user_query: str, graph_result: str) -> str:
    """
    Synthesizes a final response based on the user's original query and the graph's output.
    """
    prompt = ChatPromptTemplate.from_messages([
        ("system", "You are a helpful assistant. detailed answer based on the provided context.\n"
                   "Context from Knowledge Graph: {context}\n"
                   "If the context says 'I don't know' or is empty, politeliy inform the user you couldn't find relevant information in the specific documents."),
        ("human", "{question}")
    ])
    chain = prompt | llm | StrOutputParser()
    return chain.invoke({"question": user_query, "context": graph_result})

def process_query(user_query: str) -> str:
    """
    Orchestrates the flow from user query to GraphRAG retrieval.
    """
    logger.info(f"Received query: {user_query}")
    
    if not user_query:
        return "Please provide a valid query."

    try:
        # 1. Refine Query
        refined_query = refine_query(user_query)
        logger.info(f"Refined Query: {refined_query}")

        # 2. Retrieve from Graph
        # Check if the refined query suggests it's just a greeting (heuristic or LLM based)
        # For simplicity, we send everything to the graph unless it's obviously non-query.
        # But GraphCypherQAChain can be expensive/slow for "Hi". 
        # For this iteration, we accept the cost for robustness.
        graph_result = query_graph(refined_query)
        logger.info(f"Graph Result: {graph_result}")

        # 3. Synthesize Answer
        final_answer = synthesize_response(user_query, graph_result)
        logger.info(f"Final Answer: {final_answer}")
        
        return final_answer

    except Exception as e:
        logger.error(f"Error processing query: {e}")
        return "Sorry, I encountered an error while processing your request."

if __name__ == "__main__":
    # Test
    print(process_query("Tell me about the accounting standards"))
