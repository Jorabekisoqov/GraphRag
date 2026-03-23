#!/usr/bin/env python3
"""
Offline spot-check: extract % and modda-like tokens from an answer and search source JSON.

Usage:
  python scripts/spot_check_answer_against_json.py answer.txt path/to/soliq_kodeksi.json
  echo "Your answer text" | python scripts/spot_check_answer_against_json.py - path/to/file.json
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path


def _read_answer(path: str) -> str:
    if path == "-":
        return sys.stdin.read()
    return Path(path).read_text(encoding="utf-8")


def _concat_json_texts(data: object) -> str:
    """Concatenate original_text from graph_data entries if present."""
    if isinstance(data, dict) and "graph_data" in data:
        parts = []
        for ch in data.get("graph_data") or []:
            if isinstance(ch, dict) and ch.get("original_text"):
                parts.append(str(ch["original_text"]))
        return "\n".join(parts)
    return ""


def _tokens(answer: str) -> list[tuple[str, str]]:
    """Return (kind, token) for percentages and modda refs."""
    out: list[tuple[str, str]] = []
    for m in re.finditer(r"\d+(?:[.,]\d+)?\s*%", answer):
        out.append(("pct", m.group(0).replace(" ", "")))
    for m in re.finditer(r"\d{1,3}\s*[-]?\s*(?:modda|модда|moddasi)", answer, re.I):
        out.append(("modda", re.sub(r"\s+", "", m.group(0).lower())))
    return out


def main() -> None:
    p = argparse.ArgumentParser(description="Spot-check answer tokens against JSON corpus.")
    p.add_argument("answer_file", help="Path to answer text or - for stdin")
    p.add_argument("json_file", help="Path to soliq_kodeksi.json (or similar)")
    args = p.parse_args()

    answer = _read_answer(args.answer_file)
    raw = json.loads(Path(args.json_file).read_text(encoding="utf-8"))
    corpus = _concat_json_texts(raw)
    norm = re.sub(r"\s+", " ", corpus.lower())

    print("Token check (substring in concatenated original_text):")
    for kind, tok in _tokens(answer):
        needle = tok.lower().replace("%", " %").strip()
        ok = needle in norm or tok.lower() in norm
        status = "PASS" if ok else "FAIL"
        print(f"  [{status}] {kind}: {tok!r}")
    if not _tokens(answer):
        print("  (no % or modda-like tokens found in answer)")


if __name__ == "__main__":
    main()
