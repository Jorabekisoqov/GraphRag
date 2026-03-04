#!/usr/bin/env python3
"""
Populate embeddings on existing Chunk nodes and create Neo4j vector index.

Run after ingestion: python -m src.data.ingestion
Then: python scripts/add_embeddings.py

Requires: OPENAI_API_KEY, NEO4J_URI, NEO4J_USERNAME, NEO4J_PASSWORD
"""
import os
import sys

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from dotenv import load_dotenv

load_dotenv()


def main() -> None:
    try:
        from langchain_neo4j import Neo4jVector
        from langchain_openai import OpenAIEmbeddings
    except ImportError:
        try:
            from langchain_community.vectorstores.neo4j_vector import Neo4jVector
            from langchain_openai import OpenAIEmbeddings
        except ImportError:
            print("Error: Install langchain-neo4j: pip install langchain-neo4j")
            sys.exit(1)

    url = os.getenv("NEO4J_URI")
    username = os.getenv("NEO4J_USERNAME")
    password = os.getenv("NEO4J_PASSWORD")
    if not all([url, username, password]):
        print("Error: Set NEO4J_URI, NEO4J_USERNAME, NEO4J_PASSWORD")
        sys.exit(1)

    if not os.getenv("OPENAI_API_KEY"):
        print("Error: Set OPENAI_API_KEY")
        sys.exit(1)

    if url and url.startswith("neo4j+s://"):
        url = url.replace("neo4j+s://", "neo4j+ssc://")

    index_name = "chunk_vector_index"
    embeddings = OpenAIEmbeddings()

    print("Creating vector index and populating embeddings on Chunk nodes...")
    kwargs = dict(
        embedding=embeddings,
        url=url,
        username=username,
        password=password,
        index_name=index_name,
        node_label="Chunk",
        embedding_node_property="embedding",
    )
    try:
        # langchain-neo4j uses text_node_properties (plural, list)
        store = Neo4jVector.from_existing_graph(**kwargs, text_node_properties=["text"])
    except TypeError:
        # langchain-community uses text_node_property (singular)
        store = Neo4jVector.from_existing_graph(**kwargs, text_node_property="text")
    print(f"Done. Vector index '{index_name}' is ready.")


if __name__ == "__main__":
    main()
