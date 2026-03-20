#!/usr/bin/env python3
"""
Rule-based entity extraction for Soliq kodeksi and Buxgalteriya (Accounting) JSON.
Populates nodes and relationships by parsing original_text - no LLM required.

Soliq kodeksi extracts: Modda, Bob, SoliqTuri, Tashkilot, Sana, REFERENCES.
Buxgalteriya extracts: HisobKodi (account codes), BHMS, Bob, Qism, DEBIT_CREDIT.

Usage:
  python scripts/populate_soliq_entities.py [--input path/to/file.json]
"""
import argparse
import json
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Uzbek Cyrillic to Latin (official 1995 script)
_CYRILLIC_TO_LATIN = {
    "А": "A", "а": "a", "Б": "B", "б": "b", "В": "V", "в": "v", "Г": "G", "г": "g",
    "Д": "D", "д": "d", "Е": "E", "е": "e", "Ё": "Yo", "ё": "yo", "Ж": "J", "ж": "j",
    "З": "Z", "з": "z", "И": "I", "и": "i", "Й": "Y", "й": "y", "К": "K", "к": "k",
    "Қ": "Q", "қ": "q", "Л": "L", "л": "l", "М": "M", "м": "m", "Н": "N", "н": "n",
    "О": "O", "о": "o", "П": "P", "п": "p", "Р": "R", "р": "r", "С": "S", "с": "s",
    "Т": "T", "т": "t", "У": "U", "у": "u", "Ҳ": "H", "ҳ": "h", "Ф": "F", "ф": "f",
    "Х": "X", "х": "x", "Ц": "Ts", "ц": "ts", "Ч": "Ch", "ч": "ch", "Ш": "Sh", "ш": "sh",
    "Щ": "Sh", "щ": "sh", "Ъ": "'", "ъ": "'", "Ь": "", "ь": "", "Э": "E", "э": "e",
    "Ю": "Yu", "ю": "yu", "Я": "Ya", "я": "ya", "Ў": "O'", "ў": "o'", "Ғ": "G'", "ғ": "g'",
    "Ҳ": "H", "ҳ": "h",
}


def _cyrillic_to_latin(text: str) -> str:
    """Convert Uzbek Cyrillic text to Latin script."""
    result = []
    i = 0
    while i < len(text):
        c = text[i]
        if c in _CYRILLIC_TO_LATIN:
            result.append(_CYRILLIC_TO_LATIN[c])
        else:
            result.append(c)
        i += 1
    return "".join(result)


# Tax types from 17-modda (Soliqlarning va yig'imlarning turlari)
SOLIQ_TURLARI = [
    "qo'shilgan qiymat solig'i",
    "qqs",
    "aksiz solig'i",
    "foyda solig'i",
    "jismoniy shaxslardan olinadigan daromad solig'i",
    "yer qa'ridan foydalanganlik uchun soliq",
    "maxsus renta solig'i",
    "suv resurslaridan foydalanganlik uchun soliq",
    "mol-mulk solig'i",
    "yer solig'i",
    "ijtimoiy soliq",
    "aylanmadan olinadigan soliq",
    "yuridik shaxslarning mol-mulkiga solinadigan soliq",
    "yuridik shaxslardan olinadigan yer solig'i",
]

# Regex patterns - Soliq (Latin)
MODDA_PATTERN = re.compile(r"(\d{1,3})-modda", re.IGNORECASE)
BOB_PATTERN = re.compile(r"(\d{1,2})-bob", re.IGNORECASE)
USHBU_MODDA_PATTERN = re.compile(
    r"ushbu\s+(?:Kodeksning\s+)?(\d{1,3})-moddas?(?:i|ida|ining|da)?",
    re.IGNORECASE
)
DATE_PATTERN = re.compile(
    r"(\d{4})-yil\s+(\d{1,2})-([a-z]+)",
    re.IGNORECASE
)

# Buxgalteriya (Cyrillic) patterns
BHMS_CYRILLIC_PATTERN = re.compile(r"(\d{1,2})-сон\s*БҲМС", re.IGNORECASE)
BOB_CYRILLIC_PATTERN = re.compile(r"(I{1,3}|IV|V|VI|VII|VIII|IX|X+)\s+[бБ][оО][бБ]")
QISM_CYRILLIC_PATTERN = re.compile(r"(I{1,3}|IV|V|VI)\s+[қК][иИ][сС][мМ]")
# Buxgalteriya (Latin) patterns
BHMS_LATIN_PATTERN = re.compile(r"(\d{1,2})-son\s*(?:li\s*)?BHMS", re.IGNORECASE)
BOB_LATIN_PATTERN = re.compile(r"(I{1,3}|IV|V|VI|VII|VIII|IX|X+)\s+bob\b", re.IGNORECASE)
QISM_LATIN_PATTERN = re.compile(r"(I{1,3}|IV|V|VI)\s+qism\b", re.IGNORECASE)
# Account codes: 3-digit (001-014) or 4-digit (0110, 6410) - exclude years 19xx, 20xx
HISOB_KODI_PATTERN = re.compile(r"\b(0\d{2,3}|[1-9]\d{3})\b")
ORG_PATTERNS = [
    (r"O['']zbekiston\s+Respublikasi\s+Davlat\s+soliq\s+qo['']mitasi", "Davlat_soliq_qomitasi"),
    (r"O['']zbekiston\s+Respublikasi\s+Vazirlar\s+Mahkamasi", "Vazirlar_Mahkamasi"),
    (r"Davlat\s+bojxona\s+qo['']mitasi", "Davlat_bojxona_qomitasi"),
    (r"soliq\s+organlari", "Soliq_organlari"),
    (r"soliq\s+to['']lovchilar", "Soliq_tolovchilar"),
    (r"soliq\s+agentlari", "Soliq_agentlari"),
    (r"vakolatli\s+organlar", "Vakolatli_organlar"),
]


def extract_moddalar(text: str) -> list[dict]:
    """Extract article (modda) references."""
    seen = set()
    nodes = []
    for m in MODDA_PATTERN.finditer(text):
        num = m.group(1)
        nid = f"Modda_{num}"
        if nid not in seen:
            seen.add(nid)
            nodes.append({
                "id": nid,
                "type": "Modda",
                "properties": {"raqam": num, "nomi": f"{num}-modda"}
            })
    return nodes


def extract_boblar(text: str) -> list[dict]:
    """Extract chapter (bob) references."""
    seen = set()
    nodes = []
    for m in BOB_PATTERN.finditer(text):
        num = m.group(1)
        nid = f"Bob_{num}"
        if nid not in seen:
            seen.add(nid)
            nodes.append({
                "id": nid,
                "type": "Bob",
                "properties": {"raqam": num, "nomi": f"{num}-bob"}
            })
    return nodes


def _normalize_uz(s: str) -> str:
    """Normalize Uzbek text for matching (apostrophes)."""
    return s.lower().replace("'", "'").replace("ʻ", "'")


def extract_soliq_turlari(text: str) -> list[dict]:
    """Extract tax types mentioned in text."""
    seen = set()
    nodes = []
    text_norm = _normalize_uz(text)
    for soliq in SOLIQ_TURLARI:
        if _normalize_uz(soliq) in text_norm:
            # Normalize ID: remove apostrophes, spaces
            nid = "Soliq_" + re.sub(r"[''\s\-]+", "_", soliq)[:40]
            if nid not in seen:
                seen.add(nid)
                nodes.append({
                    "id": nid,
                    "type": "SoliqTuri",
                    "properties": {"nomi": soliq}
                })
    return nodes


def extract_tashkilotlar(text: str) -> list[dict]:
    """Extract organization references."""
    seen = set()
    nodes = []
    for pattern, label in ORG_PATTERNS:
        if re.search(pattern, text, re.IGNORECASE):
            nid = f"Tashkilot_{label}"
            if nid not in seen:
                seen.add(nid)
                nodes.append({
                    "id": nid,
                    "type": "Tashkilot",
                    "properties": {"nomi": label.replace("_", " ")}
                })
    return nodes


def extract_sanalar(text: str) -> list[dict]:
    """Extract date references (e.g. 2025-yil 1-yanvar)."""
    seen = set()
    nodes = []
    for m in DATE_PATTERN.finditer(text):
        year, day, month = m.group(1), m.group(2), m.group(3)
        nid = f"Sana_{year}_{day}_{month}"
        if nid not in seen and len(seen) < 5:  # Limit dates per chunk
            seen.add(nid)
            nodes.append({
                "id": nid,
                "type": "Sana",
                "properties": {"yil": year, "oy": month, "kun": day}
            })
    return nodes


def _is_buxgalteriya(text: str) -> bool:
    """Detect if text is Cyrillic (buxgalteriya) content."""
    cyrillic = sum(1 for c in text if "\u0400" <= c <= "\u04FF")
    return cyrillic > len(text) * 0.1


def extract_hisob_kodlari(text: str, max_per_chunk: int = 50) -> list[dict]:
    """Extract account codes (3-4 digit) from buxgalteriya text. Exclude years."""
    seen = set()
    nodes = []
    for m in HISOB_KODI_PATTERN.finditer(text):
        code = m.group(1)
        # Exclude years: 19xx, 20xx (4-digit only)
        if len(code) == 4 and code.startswith(("19", "20")):
            continue
        nid = f"Hisob_{code}"
        if nid not in seen and len(seen) < max_per_chunk:
            seen.add(nid)
            nodes.append({
                "id": nid,
                "type": "HisobKodi",
                "properties": {"kod": code}
            })
    return nodes


def extract_bhms_cyrillic(text: str) -> list[dict]:
    """Extract BHMS references (Cyrillic): 21-сон БҲМС, 5-сон БҲМС."""
    seen = set()
    nodes = []
    for m in BHMS_CYRILLIC_PATTERN.finditer(text):
        num = m.group(1)
        nid = f"BHMS_{num}"
        if nid not in seen:
            seen.add(nid)
            nodes.append({
                "id": nid,
                "type": "BHMS",
                "properties": {"raqam": num, "nomi": f"{num}-son BHMS"}
            })
    return nodes


def extract_bob_cyrillic(text: str) -> list[dict]:
    """Extract Bob (Cyrillic): I боб, II боб."""
    seen = set()
    nodes = []
    for m in BOB_CYRILLIC_PATTERN.finditer(text):
        num = m.group(1)
        nid = f"Bob_{num}"
        if nid not in seen:
            seen.add(nid)
            nodes.append({
                "id": nid,
                "type": "Bob",
                "properties": {"raqam": num, "nomi": f"{num} bob"}
            })
    return nodes


def extract_qism_cyrillic(text: str) -> list[dict]:
    """Extract Qism (Cyrillic): I қисм, II қисм."""
    seen = set()
    nodes = []
    for m in QISM_CYRILLIC_PATTERN.finditer(text):
        num = m.group(1)
        nid = f"Qism_{num}"
        if nid not in seen:
            seen.add(nid)
            nodes.append({
                "id": nid,
                "type": "Qism",
                "properties": {"raqam": num, "nomi": f"{num} qism"}
            })
    return nodes


def extract_bhms_latin(text: str) -> list[dict]:
    """Extract BHMS references (Latin): 21-son BHMS, 5-sonli BHMS."""
    seen = set()
    nodes = []
    for m in BHMS_LATIN_PATTERN.finditer(text):
        num = m.group(1)
        nid = f"BHMS_{num}"
        if nid not in seen:
            seen.add(nid)
            nodes.append({
                "id": nid,
                "type": "BHMS",
                "properties": {"raqam": num, "nomi": f"{num}-son BHMS"}
            })
    return nodes


def extract_bob_latin(text: str) -> list[dict]:
    """Extract Bob (Latin): I bob, II bob."""
    seen = set()
    nodes = []
    for m in BOB_LATIN_PATTERN.finditer(text):
        num = m.group(1)
        nid = f"Bob_{num}"
        if nid not in seen:
            seen.add(nid)
            nodes.append({
                "id": nid,
                "type": "Bob",
                "properties": {"raqam": num, "nomi": f"{num} bob"}
            })
    return nodes


def extract_qism_latin(text: str) -> list[dict]:
    """Extract Qism (Latin): I qism, II qism."""
    seen = set()
    nodes = []
    for m in QISM_LATIN_PATTERN.finditer(text):
        num = m.group(1)
        nid = f"Qism_{num}"
        if nid not in seen:
            seen.add(nid)
            nodes.append({
                "id": nid,
                "type": "Qism",
                "properties": {"raqam": num, "nomi": f"{num} qism"}
            })
    return nodes


def _is_buxgalteriya_file(file_name: str, doc_title: str = "") -> bool:
    """Detect if file is buxgalteriya by name or document title."""
    combined = (file_name + " " + doc_title).lower()
    return "buxgalteriya" in combined or "hisobvar" in combined


def extract_entities_from_chunk(chunk: dict, file_name: str, doc_title: str = "", convert_to_latin: bool = False) -> tuple[list, list]:
    """Extract nodes and relationships from a chunk's original_text."""
    text = chunk.get("original_text", "")
    if convert_to_latin and any("\u0400" <= c <= "\u04FF" for c in text):
        text = _cyrillic_to_latin(text)
        chunk["original_text"] = text
    chunk_id = chunk.get("chunk_id", str(id(chunk)))
    file_chunk_id = f"{file_name}_{chunk_id}"

    nodes = []
    relationships = []
    is_cyrillic_bux = _is_buxgalteriya(text)
    is_latin_bux = _is_buxgalteriya_file(file_name, doc_title) and not is_cyrillic_bux

    if is_cyrillic_bux:
        # Buxgalteriya (Cyrillic) extraction
        hisob_nodes = extract_hisob_kodlari(text)
        bhms_nodes = extract_bhms_cyrillic(text)
        bob_nodes = extract_bob_cyrillic(text)
        qism_nodes = extract_qism_cyrillic(text)
        nodes.extend(hisob_nodes)
        nodes.extend(bhms_nodes)
        nodes.extend(bob_nodes)
        nodes.extend(qism_nodes)
        # REFERENCES between HisobKodi nodes mentioned together
        hisob_ids = [n["id"] for n in hisob_nodes]
        for i, a in enumerate(hisob_ids):
            for b in hisob_ids[i + 1 :]:
                relationships.append({"source": a, "target": b, "type": "REFERENCES"})
    elif is_latin_bux:
        # Buxgalteriya (Latin) extraction
        hisob_nodes = extract_hisob_kodlari(text)
        bhms_nodes = extract_bhms_latin(text)
        bob_nodes = extract_bob_latin(text)
        qism_nodes = extract_qism_latin(text)
        nodes.extend(hisob_nodes)
        nodes.extend(bhms_nodes)
        nodes.extend(bob_nodes)
        nodes.extend(qism_nodes)
        hisob_ids = [n["id"] for n in hisob_nodes]
        for i, a in enumerate(hisob_ids):
            for b in hisob_ids[i + 1 :]:
                relationships.append({"source": a, "target": b, "type": "REFERENCES"})
    else:
        # Soliq (Latin) extraction
        modda_nodes = extract_moddalar(text)
        bob_nodes = extract_boblar(text)
        soliq_nodes = extract_soliq_turlari(text)
        tashkilot_nodes = extract_tashkilotlar(text)
        sana_nodes = extract_sanalar(text)
        nodes.extend(modda_nodes)
        nodes.extend(bob_nodes)
        nodes.extend(soliq_nodes)
        nodes.extend(tashkilot_nodes)
        nodes.extend(sana_nodes)
        # Relationships: Modda REFERENCES other Modda (ushbu X-modda)
        modda_ids = {n["id"] for n in modda_nodes}
        for m in USHBU_MODDA_PATTERN.finditer(text):
            num = m.group(1)
            target_id = f"Modda_{num}"
            if modda_nodes and target_id in modda_ids:
                source_id = modda_nodes[0]["id"]
                if source_id != target_id:
                    relationships.append({
                        "source": source_id,
                        "target": target_id,
                        "type": "REFERENCES"
                    })

    # Deduplicate relationships
    seen_rels = set()
    unique_rels = []
    for r in relationships:
        key = (r["source"], r["target"], r["type"])
        if key not in seen_rels:
            seen_rels.add(key)
            unique_rels.append(r)

    return nodes, unique_rels


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--input",
        default=None,
        help="Input JSON file (default: src/data/source/Json/soliq_kodeksi.json)"
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Print stats without writing"
    )
    parser.add_argument(
        "--convert-to-latin",
        action="store_true",
        help="Convert Cyrillic original_text to Latin Uzbek before extraction (for buxgalteriya)"
    )
    args = parser.parse_args()

    repo_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    default_path = os.path.join(repo_root, "src", "data", "source", "Json", "soliq_kodeksi.json")
    input_path = args.input or default_path

    if not os.path.isfile(input_path):
        print(f"File not found: {input_path}")
        sys.exit(1)

    with open(input_path, "r", encoding="utf-8") as f:
        data = json.load(f)

    file_name = data.get("metadata", {}).get("file_name", "soliq_kodeksi.json")
    doc_title = data.get("metadata", {}).get("document_title", "")
    graph_data = data.get("graph_data", [])

    total_nodes = 0
    total_rels = 0
    chunks_with_entities = 0

    for chunk in graph_data:
        nodes, rels = extract_entities_from_chunk(
            chunk, file_name, doc_title=doc_title, convert_to_latin=args.convert_to_latin
        )
        chunk["nodes"] = nodes
        chunk["relationships"] = rels
        if nodes or rels:
            chunks_with_entities += 1
        total_nodes += len(nodes)
        total_rels += len(rels)

    if args.dry_run:
        print(f"Dry run: {len(graph_data)} chunks processed")
        print(f"Chunks with entities: {chunks_with_entities}")
        print(f"Total nodes: {total_nodes}")
        print(f"Total relationships: {total_rels}")
        return

    with open(input_path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=4)

    print(f"Updated {input_path}")
    print(f"Chunks with entities: {chunks_with_entities} / {len(graph_data)}")
    print(f"Total nodes: {total_nodes}")
    print(f"Total relationships: {total_rels}")


if __name__ == "__main__":
    main()
