"""Tests for telegram_format (no heavy bot/orchestrator imports)."""

from src.bot.telegram_format import format_telegram_html


def test_format_telegram_html_blockquote():
    """Blockquote tags survive escaping; other HTML stays escaped."""
    raw = '<blockquote>Matn</blockquote> va <script>x</script>'
    out = format_telegram_html(raw)
    assert "<blockquote>Matn</blockquote>" in out
    assert "<script>" not in out
    assert "&lt;script&gt;" in out


def test_format_telegram_html_blockquote_expandable():
    out = format_telegram_html("<blockquote expandable>Uzun matn</blockquote>")
    assert "<blockquote expandable>" in out
    assert "</blockquote>" in out
