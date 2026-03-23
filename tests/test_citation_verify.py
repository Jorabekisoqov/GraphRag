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


def test_foiz_in_chunk_percent_in_line(monkeypatch):
    """Chunk uses Uzbek 'foiz', answer uses % — should pass."""
    monkeypatch.setenv("CITATION_VERIFY_MODE", "warn")
    chunks = [
        RetrievedChunk(
            id="doc_a",
            text="Rezident uchun stavka 12 foiz miqdorida belgilanadi.",
        )
    ]
    r = verify_citations("12% stavka qo‘llaniladi [CHUNK doc_a]", chunks)
    assert r.passed


def test_two_chunks_tokens_split_across_bodies(monkeypatch):
    """Each token must match at least one cited chunk (union)."""
    monkeypatch.setenv("CITATION_VERIFY_MODE", "warn")
    chunks = [
        RetrievedChunk(id="c1", text="Birinchi holat: 5% soliq."),
        RetrievedChunk(id="c2", text="Ikkinchi holat: 12% stavka."),
    ]
    line = "5% va 12% [CHUNK c1] [CHUNK c2]"
    r = verify_citations(line, chunks)
    assert r.passed
