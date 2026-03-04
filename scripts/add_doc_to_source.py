#!/usr/bin/env python3
"""
Add a document to src/data/source (Raw + Json) in the format expected by ingestion.

Usage:
  python scripts/add_doc_to_source.py path/to/file.doc --basename soliq_kodeksi --title "Soliq kodeksi"
  python scripts/add_doc_to_source.py path/to/file.pdf --basename buxgalteriya_utkazmasi --title "3000 ta buxgalteriya utkazmasi"

Supports:
  - .doc files that are actually HTML (Word "Save as .doc" often stores HTML).
  - .txt files (copied as-is).
  - .pdf files (text extraction via pypdf).
  - .docx files (python-docx).
"""
import argparse
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.data.document_utils import read_file, chunk_text


def main() -> None:
    parser = argparse.ArgumentParser(description="Add document to Raw + Json for ingestion.")
    parser.add_argument("input", help="Path to .doc, .txt, or .pdf file")
    parser.add_argument("--basename", default="soliq_kodeksi", help="Base name for output files (no extension)")
    parser.add_argument("--title", default="Soliq kodeksi", help="Document title for metadata")
    parser.add_argument("--chunk-size", type=int, default=800, help="Max characters per chunk")
    parser.add_argument("--chunk-overlap", type=int, default=150, help="Overlap between chunks (chars)")
    args = parser.parse_args()

    repo_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    raw_dir = os.path.join(repo_root, "src", "data", "source", "Raw")
    json_dir = os.path.join(repo_root, "src", "data", "source", "Json")
    os.makedirs(raw_dir, exist_ok=True)
    os.makedirs(json_dir, exist_ok=True)

    if not os.path.isfile(args.input):
        print(f"Error: file not found: {args.input}", file=sys.stderr)
        sys.exit(1)

    print(f"Reading {args.input}...")
    text = read_file(args.input)
    print(f"Extracted {len(text)} characters.")

    raw_path = os.path.join(raw_dir, f"{args.basename}.txt")
    with open(raw_path, "w", encoding="utf-8") as f:
        f.write(text)
    print(f"Wrote {raw_path}")

    graph_data = chunk_text(
        text,
        max_chunk_size=args.chunk_size,
        chunk_overlap=args.chunk_overlap,
    )
    payload = {
        "metadata": {
            "file_name": f"{args.basename}.json",
            "document_title": args.title,
            "authority": "O'zbekiston Respublikasi",
        },
        "graph_data": graph_data,
    }
    json_path = os.path.join(json_dir, f"{args.basename}.json")
    with open(json_path, "w", encoding="utf-8") as f:
        json.dump(payload, f, ensure_ascii=False, indent=4)
    print(f"Wrote {json_path} ({len(graph_data)} chunks).")
    print("Run ingestion: python -m src.data.ingestion")


if __name__ == "__main__":
    main()
