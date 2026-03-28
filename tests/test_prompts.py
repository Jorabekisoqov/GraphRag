"""Smoke tests for prompt templates (no LangChain / Neo4j imports)."""

from src.core.prompts import REFINE_QUERY_SYSTEM, SYNTHESIZE_SYSTEM


def test_refine_query_prompt_has_domain_rules():
    assert "BHMS" in REFINE_QUERY_SYSTEM
    assert "modda" in REFINE_QUERY_SYSTEM.lower()
    assert "Soliq" in REFINE_QUERY_SYSTEM or "soliq" in REFINE_QUERY_SYSTEM.lower()


def test_synthesize_prompt_has_context_placeholder():
    assert "{context}" in SYNTHESIZE_SYSTEM
    assert "{agent_memory}" in SYNTHESIZE_SYSTEM
    assert "Telegram" in SYNTHESIZE_SYSTEM or "<b>" in SYNTHESIZE_SYSTEM


def test_synthesize_prompt_grounding():
    assert "only" in SYNTHESIZE_SYSTEM.lower() or "ONLY" in SYNTHESIZE_SYSTEM
    assert "invent" in SYNTHESIZE_SYSTEM.lower()
