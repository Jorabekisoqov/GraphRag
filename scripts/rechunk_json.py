#!/usr/bin/env python3
"""
Re-chunk an existing JSON file into smaller chunks.

Reads graph_data from JSON, concatenates original_text, re-chunks with configurable
size/overlap, and writes back. Preserves metadata. Use before extract_entities and ingestion.

Usage:
  python scripts/rechunk_json.py src/data/source/Json/soliq_kodeksi.json --chunk-size 800 --chunk-overlap 150
"""
import argparse
import json
import os
import re
import sys

# Uzbek document header patterns (chapter, section) - Cyrillic and Latin
CHAPTER_PATTERN = re.compile(
    r"^(\d+|[I]{1,3}|IV|V|VI|VII|VIII|IX|X+)\s*[-]?\s*[бБbB]ob\.?\s*(.*)$",
    re.MULTILINE | re.IGNORECASE,
)
SECTION_PATTERN = re.compile(
    r"^(\d+|[I]{1,3}|IV|V|VI|VII|VIII|IX|X+)\s*[-]?\s*[қКqQ]ism\.?\s*(.*)$",
    re.MULTILINE | re.IGNORECASE,
)
INTRO_PATTERN = re.compile(r"^(Муқаддима|Muqaddima)\s*$", re.MULTILINE | re.IGNORECASE)


def _detect_section_chapter(text_slice: str) -> tuple[str, str]:
    """Detect section and chapter from text. Returns (section, chapter). Fast path: scan first 300 chars only."""
    section, chapter = "Unknown", "Unknown"
    head = text_slice[:300]
    for line in head.split("\n"):
        line = line.strip()
        if not line:
            continue
        m = CHAPTER_PATTERN.match(line)
        if m:
            chapter = f"{m.group(1)}-bob"
            if m.group(2).strip():
                section = m.group(2).strip()[:50]
            return (section, chapter)
        m = SECTION_PATTERN.match(line)
        if m:
            section = f"{m.group(1)}-qism"
            if m.group(2).strip():
                section = m.group(2).strip()[:50]
            return (section, chapter)
        if INTRO_PATTERN.match(line):
            return ("Муқаддима", "")
    return (section, chapter)


def chunk_text(
    text: str,
    max_chunk_size: int = 800,
    chunk_overlap: int = 150,
) -> list[dict]:
    """Split text into chunks with overlap; each chunk has chunk_id, original_text, section, chapter, nodes, relationships."""
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
            section, chapter = _detect_section_chapter(part)
            chunks.append({
                "chunk_id": str(i),
                "original_text": part,
                "section": section,
                "chapter": chapter,
                "nodes": [],
                "relationships": [],
            })
            i += 1
        # Overlap: next chunk starts before the end of current chunk
        start = end - chunk_overlap if end < len(text) else end
        if start >= len(text):
            break
    return chunks


def main() -> None:
    parser = argparse.ArgumentParser(description="Re-chunk JSON file for ingestion.")
    parser.add_argument("input", help="Path to JSON file (e.g. src/data/source/Json/soliq_kodeksi.json)")
    parser.add_argument("--output", default=None, help="Output path (default: overwrite input)")
    parser.add_argument("--chunk-size", type=int, default=800, help="Max characters per chunk")
    parser.add_argument("--chunk-overlap", type=int, default=150, help="Overlap between chunks (chars)")
    args = parser.parse_args()

    if not os.path.isfile(args.input):
        print(f"Error: file not found: {args.input}", file=sys.stderr)
        sys.exit(1)

    with open(args.input, "r", encoding="utf-8") as f:
        data = json.load(f)

    graph_data = data.get("graph_data", [])
    if not graph_data:
        print("Error: no graph_data in file", file=sys.stderr)
        sys.exit(1)

    # Concatenate all original_text
    text_parts = []
    for chunk in graph_data:
        t = chunk.get("original_text", "")
        if t:
            text_parts.append(t)
    full_text = "\n\n".join(text_parts)

    print(f"Concatenated {len(full_text)} characters from {len(graph_data)} chunks.")

    new_chunks = chunk_text(
        full_text,
        max_chunk_size=args.chunk_size,
        chunk_overlap=args.chunk_overlap,
    )

    data["graph_data"] = new_chunks
    out_path = args.output or args.input

    # Omit indent for large outputs to speed up I/O
    with open(out_path, "w", encoding="utf-8") as f:
        if len(new_chunks) > 500:
            json.dump(data, f, ensure_ascii=False)
        else:
            json.dump(data, f, ensure_ascii=False, indent=2)

    print(f"Wrote {out_path} ({len(new_chunks)} chunks).")


if __name__ == "__main__":
    main()
