"""
Shared utilities for document text extraction and chunking.
Used by add_doc_to_source script and Telegram bot file upload.
"""
import os
import re


def strip_html(html: str) -> str:
    """Remove HTML tags and normalize whitespace."""
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
    from pypdf import PdfReader
    reader = PdfReader(path)
    parts = []
    for page in reader.pages:
        t = page.extract_text()
        if t:
            parts.append(t)
    return "\n\n".join(parts)


def read_docx(path: str) -> str:
    """Extract text from a DOCX file."""
    from docx import Document
    doc = Document(path)
    return "\n".join(p.text for p in doc.paragraphs)


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
    """Read file based on extension; return plain text. Supports PDF, TXT, DOC, DOCX."""
    ext = os.path.splitext(path)[1].lower()
    if ext == ".pdf":
        return read_pdf(path)
    if ext == ".docx":
        return read_docx(path)
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
        start = end - chunk_overlap if end < len(text) else end
        if start >= len(text):
            break
    return chunks
