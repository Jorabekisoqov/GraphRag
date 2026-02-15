#!/usr/bin/env python3
"""
Extract entities (NormativeDocument, AccountCode, BHMS, etc.) from chunks using LLM.

Outputs nodes and relationships to update JSON for re-ingestion.
Optional: run after add_doc_to_source, then merge into JSON and re-run ingestion.

Usage:
  python scripts/extract_entities.py [--input path/to/file.json] [--output path/to/output.json]
"""
import argparse
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from dotenv import load_dotenv

load_dotenv()

# Entity types to extract (Uzbek accounting domain)
ENTITY_TYPES = ["NormativeDocument", "AccountCode", "BHMS", "MinistryOfFinance", "Regulation"]


def extract_entities_from_chunk(chunk_text: str, chunk_id: str) -> tuple[list, list]:
    """
    Use LLM to extract entities and relationships from a chunk.

    Returns (nodes, relationships).
    """
    try:
        from langchain_openai import ChatOpenAI
        from langchain_core.output_parsers import JsonOutputParser
        from langchain_core.prompts import PromptTemplate
    except ImportError:
        return [], []

    llm = ChatOpenAI(temperature=0, model="gpt-4o")
    parser = JsonOutputParser()

    prompt = PromptTemplate.from_template("""
Extract accounting-related entities from this Uzbek text. Return JSON with "nodes" and "relationships".

Entity types: NormativeDocument, AccountCode, BHMS, MinistryOfFinance, Regulation.

Nodes: list of {{"id": "unique_id", "type": "EntityType", "properties": {{"name": "...", ...}}}}
Relationships: list of {{"source": "node_id", "target": "node_id", "type": "REFERENCES"}}

Text:
{text}

Return only valid JSON, no markdown.
""")
    chain = prompt | llm | parser
    try:
        result = chain.invoke({"text": chunk_text[:3000]})
        nodes = result.get("nodes", []) if isinstance(result, dict) else []
        rels = result.get("relationships", []) if isinstance(result, dict) else []
        return nodes, rels
    except Exception:
        return [], []


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", default=None, help="Input JSON file (default: all in Json/)")
    parser.add_argument("--output", default=None, help="Output JSON file")
    parser.add_argument("--limit", type=int, default=5, help="Max chunks to process (for testing)")
    args = parser.parse_args()

    repo_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    json_dir = os.path.join(repo_root, "src", "data", "source", "Json")

    if args.input:
        files = [args.input]
    else:
        files = [os.path.join(json_dir, f) for f in os.listdir(json_dir) if f.endswith(".json")]

    for fp in files:
        if not os.path.isfile(fp):
            continue
        with open(fp, "r", encoding="utf-8") as f:
            data = json.load(f)
        graph_data = data.get("graph_data", [])
        for i, chunk in enumerate(graph_data[: args.limit]):
            text = chunk.get("original_text", "")
            nodes, rels = extract_entities_from_chunk(text, chunk.get("chunk_id", str(i)))
            chunk["nodes"] = nodes
            chunk["relationships"] = rels

        out = args.output or fp
        with open(out, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=4)
        print(f"Wrote {out}")


if __name__ == "__main__":
    main()
