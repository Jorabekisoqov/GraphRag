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


def _extract_tokens(line_clean: str) -> list[str]:
    """Compact tokens for % rates and modda references (same shapes as before)."""
    toks: list[str] = []
    for m in re.finditer(r"\d+(?:[.,]\d+)?\s*%", line_clean):
        toks.append(_norm_compact(m.group(0)))
    for m in re.finditer(
        r"\d{1,3}\s*[-]?\s*(?:modda|модда|moddasi|moddasining)", line_clean, re.I
    ):
        toks.append(_norm_compact(m.group(0)))
    return toks


def _token_supported_by_body(tok: str, body: str) -> bool:
    """
    True if tok (from the answer line) is evidenced in body.

    Treats N% in the answer as matching N foiz / N% in the source (Uzbek legal text).
    """
    b = _norm_compact(body)
    if tok in b:
        return True
    if re.search(r"modda|модда", tok):
        return tok in b
    m = re.fullmatch(r"(\d+(?:[.,]\d+)?)%", tok)
    if not m:
        return False
    num = m.group(1)
    # N% <-> Nfoiz / N% in body (already handled tok in b)
    foiz_compact = f"{num}foiz"
    if foiz_compact in b:
        return True
    # Some texts use comma as decimal: already in num
    if "," in num or "." in num:
        alt = num.replace(",", ".")
        if f"{alt}foiz".replace(".", "") in b.replace(".", ""):
            return True
    return False


def _line_tokens_supported(line: str, bodies: list[str]) -> bool:
    """Every extracted token must appear in at least one cited chunk body."""
    line_clean = CHUNK_TAG.sub("", _strip_html(line))
    toks = _extract_tokens(line_clean)
    if not toks:
        return True
    for tok in toks:
        if not any(_token_supported_by_body(tok, body) for body in bodies):
            return False
    return True


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
    Multiple [CHUNK id] on one line: each rate/modda token must match at least one cited body.
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
        matches = list(CHUNK_TAG.finditer(line))
        if not matches:
            uncited.append(line[:240])
            continue
        ids: list[str] = []
        seen: set[str] = set()
        for m in matches:
            cid = m.group(1).strip()
            if cid not in seen:
                seen.add(cid)
                ids.append(cid)
        bad = [cid for cid in ids if cid not in id_to_text]
        if bad:
            for cid in bad:
                unknown_ids.append(cid)
            failed.append(line[:240])
            continue
        bodies = [id_to_text[cid] for cid in ids]
        if not _line_tokens_supported(line, bodies):
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
