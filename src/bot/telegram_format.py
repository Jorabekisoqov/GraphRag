"""Telegram HTML formatting: markdown bold + safe tag whitelist."""

import re


def format_telegram_html(text: str) -> str:
    """Convert **bold** to HTML, escape everything, then restore Telegram-safe tags."""
    text = re.sub(r"\*\*(.+?)\*\*", r"<b>\1</b>", text)
    text = text.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
    text = text.replace("&lt;b&gt;", "<b>").replace("&lt;/b&gt;", "</b>")
    text = text.replace("&lt;i&gt;", "<i>").replace("&lt;/i&gt;", "</i>")
    # Blockquote (expandable first so the longer opening tag is not split)
    text = text.replace("&lt;blockquote expandable&gt;", "<blockquote expandable>")
    text = text.replace("&lt;blockquote&gt;", "<blockquote>")
    text = text.replace("&lt;/blockquote&gt;", "</blockquote>")
    return text
