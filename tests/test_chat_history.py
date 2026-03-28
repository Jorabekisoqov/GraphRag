"""Tests for chat_history helpers."""

import os

import pytest

from src.data import chat_history as ch


def test_format_conversation_history_empty():
    assert ch.format_conversation_history([]) == ""


def test_format_conversation_history_lines():
    rows = [
        {"role": "user", "text": "Salom"},
        {"role": "assistant", "text": "Yordam bera olaman."},
    ]
    out = ch.format_conversation_history(rows)
    assert "User: Salom" in out
    assert "Assistant: Yordam bera olaman." in out


def test_is_chat_history_enabled_default(monkeypatch):
    monkeypatch.delenv("CHAT_HISTORY_ENABLED", raising=False)
    assert ch.is_chat_history_enabled() is False


@pytest.mark.parametrize("raw", ("true", "TRUE", "1", "yes", "on"))
def test_is_chat_history_enabled_on(monkeypatch, raw):
    monkeypatch.setenv("CHAT_HISTORY_ENABLED", raw)
    assert ch.is_chat_history_enabled() is True


def test_chat_history_limit_default(monkeypatch):
    monkeypatch.delenv("CHAT_HISTORY_LIMIT", raising=False)
    assert ch.chat_history_limit() == 10


def test_chat_history_limit_clamped(monkeypatch):
    monkeypatch.setenv("CHAT_HISTORY_LIMIT", "999")
    assert ch.chat_history_limit() == 50
