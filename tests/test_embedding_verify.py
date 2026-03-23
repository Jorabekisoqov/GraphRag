"""Tests for embedding-based answer grounding (mocked embeddings)."""

import os
from unittest.mock import MagicMock, patch

import pytest

from src.core.embedding_verify import (
    CONTEXT_DELIMITER,
    GroundingResult,
    format_answer_with_optional_warning,
    split_answer_sentences,
    split_context_segments,
    strip_html_for_embedding,
    verify_answer_grounding,
)


def test_strip_html_for_embedding():
    assert strip_html_for_embedding("<b>Hello</b> world.") == "Hello world."
    assert strip_html_for_embedding("") == ""


def test_split_context_segments():
    assert split_context_segments("a" + CONTEXT_DELIMITER + "b") == ["a", "b"]
    assert split_context_segments("single block") == ["single block"]
    assert split_context_segments("") == []


def test_split_answer_sentences():
    sents = split_answer_sentences(
        "This is the first full sentence. Here is another longer one!"
    )
    assert len(sents) >= 2
    assert any("first" in s.lower() for s in sents)


def test_verify_disabled(monkeypatch):
    monkeypatch.delenv("ENABLE_EMBEDDING_VERIFY", raising=False)
    monkeypatch.setenv("ENABLE_EMBEDDING_VERIFY", "0")
    gr = verify_answer_grounding("Answer text here.", "context block", is_weak_context=False)
    assert gr.skipped
    assert gr.skipped_reason == "disabled"


def test_verify_skips_weak_context(monkeypatch):
    monkeypatch.setenv("ENABLE_EMBEDDING_VERIFY", "1")
    gr = verify_answer_grounding("x" * 100, "ctx", is_weak_context=True)
    assert gr.skipped
    assert gr.skipped_reason == "weak_context"


def test_verify_skips_no_openai_key(monkeypatch):
    monkeypatch.setenv("ENABLE_EMBEDDING_VERIFY", "1")
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    gr = verify_answer_grounding(
        "This is a full sentence for testing.",
        "Some context segment with enough text.",
        is_weak_context=False,
    )
    assert gr.skipped
    assert gr.skipped_reason == "no_openai_key"


@patch("src.core.embedding_verify._get_embeddings_client")
def test_verify_high_similarity(mock_get_client, monkeypatch):
    monkeypatch.setenv("ENABLE_EMBEDDING_VERIFY", "1")
    monkeypatch.setenv("OPENAI_API_KEY", "sk-test")
    monkeypatch.setenv("EMBEDDING_VERIFY_MIN_COSINE", "0.5")

    # Same embedding for segment and sentence -> cosine 1.0
    vec = [1.0, 0.0, 0.0]
    mock_emb = MagicMock()
    mock_emb.embed_documents.return_value = [vec, vec]
    mock_get_client.return_value = mock_emb

    ctx = "segment one"
    ans = "Sentence one matches."
    gr = verify_answer_grounding(ans, ctx, is_weak_context=False)
    assert not gr.skipped
    assert gr.min_score is not None
    assert gr.min_score >= 0.99
    assert gr.low_sentence_count == 0


@patch("src.core.embedding_verify._get_embeddings_client")
def test_verify_low_similarity(mock_get_client, monkeypatch):
    monkeypatch.setenv("ENABLE_EMBEDDING_VERIFY", "1")
    monkeypatch.setenv("OPENAI_API_KEY", "sk-test")
    monkeypatch.setenv("EMBEDDING_VERIFY_MIN_COSINE", "0.99")

    a = [1.0, 0.0, 0.0]
    b = [0.0, 1.0, 0.0]
    mock_emb = MagicMock()
    mock_emb.embed_documents.return_value = [a, b]
    mock_get_client.return_value = mock_emb

    gr = verify_answer_grounding(
        "This is a long enough sentence.",
        "context block",
        is_weak_context=False,
    )
    assert not gr.skipped
    assert gr.min_score is not None
    assert gr.min_score < 0.99
    assert gr.low_sentence_count >= 1


def test_format_answer_warning(monkeypatch):
    monkeypatch.setenv("EMBEDDING_VERIFY_WARN_USER", "1")
    gr = GroundingResult(
        skipped=False,
        skipped_reason=None,
        min_score=0.1,
        mean_score=0.2,
        per_sentence_scores=[0.1],
        below_threshold_indices=[0],
        threshold=0.72,
        low_sentence_count=1,
    )
    out = format_answer_with_optional_warning("Hello.", gr)
    assert "Avtomatik tekshiruv" in out
    assert out.startswith("Hello.")


def test_format_answer_no_warning_when_score_ok(monkeypatch):
    monkeypatch.setenv("EMBEDDING_VERIFY_WARN_USER", "1")
    gr = GroundingResult(
        skipped=False,
        skipped_reason=None,
        min_score=0.95,
        mean_score=0.95,
        per_sentence_scores=[0.95],
        below_threshold_indices=[],
        threshold=0.72,
        low_sentence_count=0,
    )
    assert format_answer_with_optional_warning("Hello.", gr) == "Hello."
