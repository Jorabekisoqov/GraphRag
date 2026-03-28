"""Unit tests for Graphiti memory helpers (no live Neo4j / Graphiti)."""

from src.data import graphiti_memory as gm


def test_scope_token_stable():
    assert "<<<TGCHAT_99>>>" in gm.format_episode_body(99, 1, "hi", "yo")


def test_format_episode_body_contains_ids():
    body = gm.format_episode_body(42, 7, "Q", "A")
    assert "telegram_chat_id=42" in body
    assert "telegram_user_id=7" in body
    assert "User: Q" in body
    assert "Assistant: A" in body


def test_format_memory_for_prompt():
    assert gm.format_memory_for_prompt([]) == "(none)"
    assert gm.format_memory_for_prompt(["a", "b"]) == "- a\n- b"


def test_is_graphiti_memory_enabled_env(monkeypatch):
    monkeypatch.delenv("GRAPHITI_MEMORY_ENABLED", raising=False)
    assert gm.is_graphiti_memory_enabled() is False
    monkeypatch.setenv("GRAPHITI_MEMORY_ENABLED", "true")
    assert gm.is_graphiti_memory_enabled() is True


def test_graphiti_search_limit(monkeypatch):
    monkeypatch.delenv("GRAPHITI_SEARCH_LIMIT", raising=False)
    assert gm.graphiti_search_limit() == 8
    monkeypatch.setenv("GRAPHITI_SEARCH_LIMIT", "3")
    assert gm.graphiti_search_limit() == 3
    monkeypatch.setenv("GRAPHITI_SEARCH_LIMIT", "999")
    assert gm.graphiti_search_limit() == 20
