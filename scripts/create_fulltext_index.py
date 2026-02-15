#!/usr/bin/env python3
"""
Create Neo4j full-text index on Chunk.text for keyword search.

Run after ingestion. Enables Cypher queries like:
  CALL db.index.fulltext.queryNodes("chunk_text_index", $query) YIELD node, score RETURN node.text
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from dotenv import load_dotenv

load_dotenv()


def main() -> None:
    from src.data.neo4j_client import get_neo4j_graph

    graph = get_neo4j_graph()
    index_name = "chunk_text_index"

    cypher = f"""
    CREATE FULLTEXT INDEX {index_name} IF NOT EXISTS
    FOR (c:Chunk) ON EACH [c.text]
    """
    try:
        graph.query(cypher)
        print(f"Full-text index '{index_name}' created or already exists.")
    except Exception as e:
        print(f"Error: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
