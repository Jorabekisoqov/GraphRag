"""Tests for citation verification."""

import pytest

from src.data.retrieval_types import RetrievedChunk
from src.core.citation_verify import (
    apply_citation_result,
    verify_citations,
)


@pytest.fixture
def sample_chunks():
    return [
        RetrievedChunk(
            id="soliq_kodeksi_1",
            text="Jismoniy shaxslardan olinadigan daromad solig‘i 12% (381-modda).",
        )
    ]


def test_verify_off_by_default(monkeypatch, sample_chunks):
    monkeypatch.delenv("CITATION_VERIFY_MODE", raising=False)
    r = verify_citations("12% stavka [CHUNK soliq_kodeksi_1]", sample_chunks)
    assert r.passed
    assert r.mode == "off"


def test_verify_warn_uncited(monkeypatch, sample_chunks):
    monkeypatch.setenv("CITATION_VERIFY_MODE", "warn")
    r = verify_citations("Daromad solig‘i stavkasi 12% bo‘ladi.", sample_chunks)
    assert not r.passed
    assert r.uncited_risky_lines


def test_verify_pass_with_chunk_tag(monkeypatch, sample_chunks):
    monkeypatch.setenv("CITATION_VERIFY_MODE", "warn")
    line = "12% stavka [CHUNK soliq_kodeksi_1]"
    r = verify_citations(line, sample_chunks)
    assert r.passed
    assert not r.failed_chunk_match_lines


def test_apply_warn_appends(monkeypatch, sample_chunks):
    monkeypatch.setenv("CITATION_VERIFY_MODE", "warn")
    r = verify_citations("12% [CHUNK wrong_id]", sample_chunks)
    assert not r.passed
    out = apply_citation_result("12% [CHUNK wrong_id]", r)
    assert "Eslatma" in out or "eslatma" in out.lower()


def test_apply_strict_redacts(monkeypatch, sample_chunks):
    monkeypatch.setenv("CITATION_VERIFY_MODE", "strict")
    r = verify_citations("12% hech qayerda", sample_chunks)
    out = apply_citation_result("12% hech qayerda", r)
    assert "tasdiqlanmagan" in out or "12%" not in out
