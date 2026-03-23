"""
Deterministic citation checks for answers that cite [CHUNK id] against retrieved chunk text.

Does not use an LLM. Complements embedding_verify (which does not validate numbers).
"""
from __future__ import annotations

import os
import re
from dataclasses import dataclass, field

from src.core.logging_config import get_logger

logger = get_logger(__name__)

CHUNK_TAG = re.compile(r"\[CHUNK\s+([^\]]+?)\s*\]", re.IGNORECASE)

# Lines that look like factual tax/accounting claims needing a citation
_RISKY_LINE = re.compile(
    r"(?:\d+(?:[.,]\d+)?\s*%|\d{1,3}\s*[-]?\s*(?:modda|модда|moddasi|moddasining))",
    re.IGNORECASE,
)


def _env_str(name: str, default: str) -> str:
    raw = os.getenv(name)
    if raw is None or raw.strip() == "":
        return default
    return raw.strip().lower()


def _strip_html(s: str) -> str:
    return re.sub(r"<[^>]+>", " ", s)


def _norm_compact(s: str) -> str:
    return re.sub(r"\s+", "", s.lower())


def _line_has_chunk_tag(line: str) -> bool:
    return bool(CHUNK_TAG.search(line))


def _must_appear_in_chunk(line: str, body: str) -> bool:
    """Check that % and modda tokens in line appear in chunk body (normalized)."""
    line_clean = CHUNK_TAG.sub("", _strip_html(line))
    b = _norm_compact(body)
    toks: list[str] = []
    for m in re.finditer(r"\d+(?:[.,]\d+)?\s*%", line_clean):
        toks.append(_norm_compact(m.group(0)))
    for m in re.finditer(
        r"\d{1,3}\s*[-]?\s*(?:modda|модда|moddasi|moddasining)", line_clean, re.I
    ):
        toks.append(_norm_compact(m.group(0)))
    if not toks:
        return True
    return all(t in b for t in toks)


@dataclass
class CitationVerifyResult:
    passed: bool
    mode: str
    uncited_risky_lines: list[str] = field(default_factory=list)
    failed_chunk_match_lines: list[str] = field(default_factory=list)
    unknown_chunk_ids: list[str] = field(default_factory=list)


def verify_citations(answer: str, chunks: list) -> CitationVerifyResult:
    """
    Check risky lines for [CHUNK id] and token presence in cited chunk text.

    chunks: list of RetrievedChunk from graph_rag.
    """
    mode = _env_str("CITATION_VERIFY_MODE", "off")
    if mode not in ("warn", "strict"):
        return CitationVerifyResult(passed=True, mode=mode or "off")

    if not chunks:
        return CitationVerifyResult(passed=True, mode=mode)

    id_to_text = {c.id: c.text for c in chunks}
    lines = [ln.rstrip() for ln in answer.splitlines() if ln.strip()]

    uncited: list[str] = []
    failed: list[str] = []
    unknown_ids: list[str] = []

    for line in lines:
        if not _RISKY_LINE.search(line):
            continue
        m = CHUNK_TAG.search(line)
        if not m:
            uncited.append(line[:240])
            continue
        cid = m.group(1).strip()
        if cid not in id_to_text:
            unknown_ids.append(cid)
            failed.append(line[:240])
            continue
        body = id_to_text[cid]
        if not _must_appear_in_chunk(line, body):
            failed.append(line[:240])

    passed = not uncited and not failed and not unknown_ids
    return CitationVerifyResult(
        passed=passed,
        mode=mode,
        uncited_risky_lines=uncited,
        failed_chunk_match_lines=failed,
        unknown_chunk_ids=unknown_ids,
    )


WARN_CITATION_UZ = (
    "\n\n<i>Eslatma: avtomatik tekshiruv ba'zi foiz yoki modda qatorlarini manba bilan "
    "to'liq bog'lolmadi. Muhim stavkalarni asl hujjatdan tekshiring.</i>"
)

STRICT_PLACEHOLDER = (
    "<i>[Bu qator keltirilgan manba matnida tasdiqlanmagan]</i>"
)


def apply_citation_result(answer: str, result: CitationVerifyResult) -> str:
    """Append warning or redact risky lines in strict mode."""
    if result.mode == "off" or result.passed:
        return answer
    if result.mode == "warn":
        if "avtomatik tekshiruv ba'zi foiz" in answer:
            return answer
        return answer.rstrip() + WARN_CITATION_UZ
    # strict
    out_lines: list[str] = []
    for line in answer.splitlines():
        stripped = line.strip()
        if not stripped:
            out_lines.append(line)
            continue
        if _RISKY_LINE.search(stripped) and not _line_has_chunk_tag(stripped):
            out_lines.append(STRICT_PLACEHOLDER)
            continue
        out_lines.append(line)
    return "\n".join(out_lines)
