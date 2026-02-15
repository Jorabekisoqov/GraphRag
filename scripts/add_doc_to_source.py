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


def read_pdf(path: str) -> str:
    """Extract text from a PDF file."""
    try:
        from pypdf import PdfReader
    except ImportError:
        raise ImportError("pypdf is required for PDF files. Install with: pip install pypdf")
    reader = PdfReader(path)
    parts = []
    for page in reader.pages:
        t = page.extract_text()
        if t:
            parts.append(t)
    return "\n\n".join(parts)


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


def read_file(path: str) -> str:
    """Read file based on extension; return plain text."""
    ext = os.path.splitext(path)[1].lower()
    if ext == ".pdf":
        return read_pdf(path)
    return read_doc_or_txt(path)


# Uzbek document header patterns (chapter, section)
CHAPTER_PATTERN = re.compile(
    r"^(I{1,3}|IV|V|VI|VII|VIII|IX|X+)\s+[бБ]об\.?\s*(.*)$",
    re.MULTILINE,
)
SECTION_PATTERN = re.compile(
    r"^(I{1,3}|IV|V|VI|VII|VIII|IX|X+)\s+[қК]исм\.?\s*(.*)$",
    re.MULTILINE,
)
INTRO_PATTERN = re.compile(r"^Муқаддима\s*$", re.MULTILINE)


def _detect_section_chapter(text_slice: str) -> tuple[str, str]:
    """Detect section and chapter from text. Returns (section, chapter)."""
    section = ""
    chapter = ""
    for line in text_slice.split("\n")[:50]:
        line = line.strip()
        if not line:
            continue
        m = CHAPTER_PATTERN.match(line)
        if m:
            chapter = f"{m.group(1)} боб"
            if m.group(2).strip():
                section = m.group(2).strip()[:50]
            continue
        m = SECTION_PATTERN.match(line)
        if m:
            section = f"{m.group(1)} қисм"
            if m.group(2).strip():
                section = m.group(2).strip()[:50]
            continue
        if INTRO_PATTERN.match(line):
            section = "Муқаддима"
            chapter = ""
    return (section or "Unknown", chapter or "Unknown")


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
