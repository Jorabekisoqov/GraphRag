#!/usr/bin/env python3
"""
Add a document to src/data/source (Raw + Json) in the format expected by ingestion.

Usage:
  python scripts/add_doc_to_source.py path/to/file.doc --basename soliq_kodeksi --title "Soliq kodeksi"

Supports:
  - .doc files that are actually HTML (Word "Save as .doc" often stores HTML).
  - .txt files (copied as-is).
"""
import argparse
import json
import os
import re
import sys


def strip_html(html: str) -> str:
    """Remove HTML tags and normalize whitespace."""
    # Drop style and script blocks so their content is not in the output
    html = re.sub(r"<style[^>]*>[\s\S]*?</style>", " ", html, flags=re.IGNORECASE)
    html = re.sub(r"<script[^>]*>[\s\S]*?</script>", " ", html, flags=re.IGNORECASE)
    text = re.sub(r"<br\s*/?>", "\n", html, flags=re.IGNORECASE)
    text = re.sub(r"</(?:p|div|tr|li)>", "\n", text, flags=re.IGNORECASE)
    text = re.sub(r"<[^>]+>", " ", text)
    text = re.sub(r"&nbsp;", " ", text, flags=re.IGNORECASE)
    text = re.sub(r"&amp;", "&", text, flags=re.IGNORECASE)
    text = re.sub(r"&lt;", "<", text, flags=re.IGNORECASE)
    text = re.sub(r"&gt;", ">", text, flags=re.IGNORECASE)
    text = re.sub(r"\s+", " ", text)
    text = re.sub(r"\n\s*\n", "\n\n", text)
    return text.strip()


def read_doc_or_txt(path: str) -> str:
    """Read file; if it looks like HTML, strip tags and return plain text."""
    with open(path, "rb") as f:
        raw = f.read()
    for enc in ("utf-8", "utf-8-sig", "cp1251", "latin-1"):
        try:
            text = raw.decode(enc)
            break
        except UnicodeDecodeError:
            continue
    else:
        raise ValueError(f"Cannot decode {path}")
    if "<html" in text.lower() or "<body" in text.lower() or "<div" in text.lower():
        return strip_html(text)
    return text


def chunk_text(text: str, max_chunk_size: int = 4000) -> list[dict]:
    """Split text into chunks; each chunk has chunk_id, original_text, nodes, relationships."""
    chunks = []
    start = 0
    i = 0
    while start < len(text):
        end = min(start + max_chunk_size, len(text))
        if end < len(text):
            # Try to break at paragraph or sentence
            break_at = text.rfind("\n\n", start, end + 1)
            if break_at > start:
                end = break_at + 2
            else:
                break_at = text.rfind(". ", start, end + 1)
                if break_at > start:
                    end = break_at + 2
        part = text[start:end].strip()
        if part:
            chunks.append({
                "chunk_id": str(i),
                "original_text": part,
                "nodes": [],
                "relationships": [],
            })
            i += 1
        start = end
    return chunks


def main() -> None:
    parser = argparse.ArgumentParser(description="Add document to Raw + Json for ingestion.")
    parser.add_argument("input", help="Path to .doc or .txt file")
    parser.add_argument("--basename", default="soliq_kodeksi", help="Base name for output files (no extension)")
    parser.add_argument("--title", default="Soliq kodeksi", help="Document title for metadata")
    parser.add_argument("--chunk-size", type=int, default=4000, help="Max characters per chunk")
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
    text = read_doc_or_txt(args.input)
    print(f"Extracted {len(text)} characters.")

    raw_path = os.path.join(raw_dir, f"{args.basename}.txt")
    with open(raw_path, "w", encoding="utf-8") as f:
        f.write(text)
    print(f"Wrote {raw_path}")

    graph_data = chunk_text(text, max_chunk_size=args.chunk_size)
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
