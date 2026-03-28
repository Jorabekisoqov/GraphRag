"""Store and load Telegram chat turns in Neo4j for conversational context (not a legal source)."""

import os
import time
import uuid
from typing import Any

from src.core.logging_config import get_logger

logger = get_logger(__name__)

_MAX_MESSAGE_CHARS = 12000


def is_chat_history_enabled() -> bool:
    v = (os.getenv("CHAT_HISTORY_ENABLED") or "").strip().lower()
    return v in ("1", "true", "yes", "on")


def chat_history_limit() -> int:
    try:
        n = int(os.getenv("CHAT_HISTORY_LIMIT", "10"))
        return max(1, min(n, 50))
    except ValueError:
        return 10


def _user_node_id(telegram_user_id: int) -> str:
    return f"tg_user:{telegram_user_id}"


def _chat_node_id(telegram_chat_id: int) -> str:
    return f"tg_chat:{telegram_chat_id}"


def _truncate(text: str) -> str:
    if len(text) <= _MAX_MESSAGE_CHARS:
        return text
    return text[: _MAX_MESSAGE_CHARS - 3] + "..."


def format_conversation_history(messages: list[dict[str, str]]) -> str:
    """Turn role/text rows into a single block for the synthesizer."""
    if not messages:
        return ""
    lines: list[str] = []
    for m in messages:
        role = m.get("role", "")
        text = (m.get("text") or "").strip()
        if not text:
            continue
        label = "User" if role == "user" else "Assistant"
        lines.append(f"{label}: {text}")
    return "\n".join(lines)


def fetch_recent_messages(telegram_chat_id: int, limit: int | None = None) -> list[dict[str, str]]:
    """
    Return recent messages for this Telegram chat, oldest first (excluding the current turn).
    """
    if not is_chat_history_enabled():
        return []
    from src.data.neo4j_client import get_neo4j_graph

    lim = limit if limit is not None else chat_history_limit()
    graph = get_neo4j_graph()
    cid = _chat_node_id(telegram_chat_id)
    cypher = """
    MATCH (ch:TelegramChat {id: $chat_id})-[:HAS_MESSAGE]->(m:ChatMessage)
    RETURN m.role AS role, m.text AS text, m.created_at AS created_at
    ORDER BY m.created_at DESC, m.id DESC
    LIMIT $limit
    """
    try:
        raw: Any = graph.query(cypher, {"chat_id": cid, "limit": lim})
    except Exception as e:
        logger.warning("chat_history_fetch_failed", error=str(e))
        return []
    if not raw or not isinstance(raw, list):
        return []
    rows: list[dict[str, str]] = []
    for row in raw:
        if not isinstance(row, dict):
            continue
        r, t = row.get("role"), row.get("text")
        if r and t is not None:
            rows.append({"role": str(r), "text": str(t)})
    rows.reverse()
    return rows


def append_exchange(
    telegram_user_id: int,
    telegram_chat_id: int,
    user_text: str,
    assistant_text: str,
) -> None:
    """Persist one user message and one assistant reply linked to the Telegram chat."""
    if not is_chat_history_enabled():
        return
    from src.data.neo4j_client import get_neo4j_graph

    uid = _user_node_id(telegram_user_id)
    cid = _chat_node_id(telegram_chat_id)
    mid_u = f"chatmsg:{uuid.uuid4()}"
    mid_a = f"chatmsg:{uuid.uuid4()}"
    ts_u = int(time.time() * 1000)
    ts_a = ts_u + 1
    ut = _truncate(user_text.strip())
    at = _truncate(assistant_text.strip())
    graph = get_neo4j_graph()
    cypher = """
    MERGE (u:TelegramUser {id: $uid})
    SET u.telegram_user_id = $telegram_user_id
    MERGE (ch:TelegramChat {id: $cid})
    SET ch.telegram_chat_id = $telegram_chat_id
    MERGE (u)-[:IN_CHAT]->(ch)
    WITH ch
    CREATE (mu:ChatMessage {
      id: $mid_u,
      role: 'user',
      text: $user_text,
      created_at: $ts_u
    })
    CREATE (ma:ChatMessage {
      id: $mid_a,
      role: 'assistant',
      text: $assistant_text,
      created_at: $ts_a
    })
    MERGE (ch)-[:HAS_MESSAGE]->(mu)
    MERGE (ch)-[:HAS_MESSAGE]->(ma)
    MERGE (mu)-[:NEXT]->(ma)
    """
    try:
        graph.query(
            cypher,
            {
                "uid": uid,
                "telegram_user_id": int(telegram_user_id),
                "cid": cid,
                "telegram_chat_id": int(telegram_chat_id),
                "mid_u": mid_u,
                "mid_a": mid_a,
                "ts_u": ts_u,
                "ts_a": ts_a,
                "user_text": ut,
                "assistant_text": at,
            },
        )
    except Exception as e:
        logger.warning("chat_history_append_failed", error=str(e))
