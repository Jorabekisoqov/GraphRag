"""
Non-LLM grounding check: cosine similarity between answer sentences and context segments.

Uses OpenAIEmbeddings (same stack as chunk indexing). See env vars in verify_answer_grounding.
"""
from __future__ import annotations

import os
import re
from dataclasses import dataclass
from typing import Any

from src.core.logging_config import get_logger

logger = get_logger(__name__)

CONTEXT_DELIMITER = "\n\n---\n\n"
WARN_MESSAGE_UZ = (
    "⚠️ Avtomatik tekshiruv: javobning ayrim qismlari manba matnlari bilan zaif mos keldi. "
    "Muhim hollarda asl hujjatni tekshiring."
)


def _env_bool(name: str, default: bool = False) -> bool:
    raw = os.getenv(name)
    if raw is None or raw.strip() == "":
        return default
    return raw.strip().lower() in ("1", "true", "yes", "on")


def _env_float(name: str, default: float) -> float:
    raw = os.getenv(name)
    if raw is None or raw.strip() == "":
        return default
    try:
        return float(raw)
    except ValueError:
        return default


def _env_int(name: str, default: int) -> int:
    raw = os.getenv(name)
    if raw is None or raw.strip() == "":
        return default
    try:
        return max(1, int(raw))
    except ValueError:
        return default


def strip_html_for_embedding(text: str) -> str:
    """Remove simple Telegram/HTML tags so embeddings match natural language."""
    if not text:
        return ""
    s = re.sub(r"<[^>]+>", " ", text)
    return re.sub(r"\s+", " ", s).strip()


def split_context_segments(context: str) -> list[str]:
    """Split merged retrieval text on the same delimiter as hybrid_retrieve / fallback."""
    if not context or not context.strip():
        return []
    parts = context.split(CONTEXT_DELIMITER)
    out = [p.strip() for p in parts if p.strip()]
    return out if out else [context.strip()]


def split_answer_sentences(text: str, min_len: int = 12) -> list[str]:
    """Split answer into sentences for per-sentence similarity; drop very short noise."""
    plain = strip_html_for_embedding(text)
    if not plain:
        return []
    # Sentence boundaries + line breaks (Telegram)
    raw_parts = re.split(r"(?<=[.!?…])\s+|\n+", plain)
    sentences = [p.strip() for p in raw_parts if len(p.strip()) >= min_len]
    return sentences


def _cosine_similarity(a: list[float], b: list[float]) -> float:
    dot = sum(x * y for x, y in zip(a, b, strict=True))
    na = sum(x * x for x in a) ** 0.5
    nb = sum(x * x for x in b) ** 0.5
    if na == 0.0 or nb == 0.0:
        return 0.0
    return dot / (na * nb)


def _max_cosine_to_segments(
    sentence_emb: list[float], segment_embs: list[list[float]]
) -> float:
    if not segment_embs:
        return 0.0
    return max(_cosine_similarity(sentence_emb, seg) for seg in segment_embs)


@dataclass
class GroundingResult:
    skipped: bool
    skipped_reason: str | None
    min_score: float | None
    mean_score: float | None
    per_sentence_scores: list[float]
    below_threshold_indices: list[int]
    threshold: float
    low_sentence_count: int


def _get_embeddings_client() -> Any:
    from langchain_openai import OpenAIEmbeddings

    return OpenAIEmbeddings()


def verify_answer_grounding(
    answer: str,
    context: str,
    *,
    is_weak_context: bool = False,
) -> GroundingResult:
    """
    Embed context segments and answer sentences; score each sentence by max cosine to any segment.

    Args:
        answer: Model output (may include HTML).
        context: Merged retrieval string.
        is_weak_context: If True, skip (caller already determined weak retrieval).

    Returns:
        GroundingResult with scores; skipped if disabled, weak context, or missing API key.
    """
    threshold = _env_float("EMBEDDING_VERIFY_MIN_COSINE", 0.72)
    max_sentences = _env_int("EMBEDDING_VERIFY_MAX_SENTENCES", 40)

    if not _env_bool("ENABLE_EMBEDDING_VERIFY", False):
        return GroundingResult(
            skipped=True,
            skipped_reason="disabled",
            min_score=None,
            mean_score=None,
            per_sentence_scores=[],
            below_threshold_indices=[],
            threshold=threshold,
            low_sentence_count=0,
        )

    if is_weak_context:
        return GroundingResult(
            skipped=True,
            skipped_reason="weak_context",
            min_score=None,
            mean_score=None,
            per_sentence_scores=[],
            below_threshold_indices=[],
            threshold=threshold,
            low_sentence_count=0,
        )

    segments = split_context_segments(context)
    if not segments:
        return GroundingResult(
            skipped=True,
            skipped_reason="no_segments",
            min_score=None,
            mean_score=None,
            per_sentence_scores=[],
            below_threshold_indices=[],
            threshold=threshold,
            low_sentence_count=0,
        )

    sentences = split_answer_sentences(answer)
    if not sentences:
        return GroundingResult(
            skipped=True,
            skipped_reason="no_sentences",
            min_score=None,
            mean_score=None,
            per_sentence_scores=[],
            below_threshold_indices=[],
            threshold=threshold,
            low_sentence_count=0,
        )

    sentences = sentences[:max_sentences]

    if not os.getenv("OPENAI_API_KEY"):
        logger.warning("embedding_verify_skipped", reason="OPENAI_API_KEY unset")
        return GroundingResult(
            skipped=True,
            skipped_reason="no_openai_key",
            min_score=None,
            mean_score=None,
            per_sentence_scores=[],
            below_threshold_indices=[],
            threshold=threshold,
            low_sentence_count=0,
        )

    try:
        emb = _get_embeddings_client()
        # Single batch: segments first, then sentences (one round-trip)
        all_texts = [strip_html_for_embedding(s) for s in segments] + [
            strip_html_for_embedding(s) for s in sentences
        ]
        vectors = emb.embed_documents(all_texts)
    except Exception as e:
        logger.error("embedding_verify_error", error=str(e), exc_info=True)
        return GroundingResult(
            skipped=True,
            skipped_reason=f"embed_error:{e!s}",
            min_score=None,
            mean_score=None,
            per_sentence_scores=[],
            below_threshold_indices=[],
            threshold=threshold,
            low_sentence_count=0,
        )

    n_seg = len(segments)
    if len(vectors) != len(all_texts):
        return GroundingResult(
            skipped=True,
            skipped_reason="embed_length_mismatch",
            min_score=None,
            mean_score=None,
            per_sentence_scores=[],
            below_threshold_indices=[],
            threshold=threshold,
            low_sentence_count=0,
        )

    segment_embs = vectors[:n_seg]
    sentence_embs = vectors[n_seg:]

    per_sentence_scores: list[float] = []
    below_threshold_indices: list[int] = []
    for i, s_emb in enumerate(sentence_embs):
        score = _max_cosine_to_segments(s_emb, segment_embs)
        per_sentence_scores.append(score)
        if score < threshold:
            below_threshold_indices.append(i)

    min_score = min(per_sentence_scores) if per_sentence_scores else None
    mean_score = (
        sum(per_sentence_scores) / len(per_sentence_scores) if per_sentence_scores else None
    )

    return GroundingResult(
        skipped=False,
        skipped_reason=None,
        min_score=min_score,
        mean_score=mean_score,
        per_sentence_scores=per_sentence_scores,
        below_threshold_indices=below_threshold_indices,
        threshold=threshold,
        low_sentence_count=len(below_threshold_indices),
    )


def format_answer_with_optional_warning(answer: str, result: GroundingResult) -> str:
    """Append Uzbek disclaimer when WARN_USER is on and any sentence is below threshold."""
    if result.skipped or result.min_score is None:
        return answer
    if not _env_bool("EMBEDDING_VERIFY_WARN_USER", False):
        return answer
    if result.min_score >= result.threshold:
        return answer
    if WARN_MESSAGE_UZ in answer:
        return answer
    return answer.rstrip() + "\n\n" + WARN_MESSAGE_UZ
