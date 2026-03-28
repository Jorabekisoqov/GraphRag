"""Optional Graphiti (temporal memory graph) on Neo4j — semantic recall alongside chat history.

Neo4j Community has a single user database; Graphiti's ``group_id`` cannot isolate tenants via separate DBs.
Episodes are tagged with a stable per-chat token and search results are filtered to facts containing it.

Requires OPENAI_API_KEY (Graphiti uses OpenAI for extraction/embeddings by default)."""

from __future__ import annotations

import asyncio
import os
import threading
import uuid
from collections.abc import Awaitable
from datetime import datetime, timezone
from typing import Any

from src.core.logging_config import get_logger

logger = get_logger(__name__)

_client: Any = None
_init_lock = threading.Lock()
_op_lock = threading.Lock()
_schema_ready = False  # set True after build_indices succeeds (serialized via _op_lock)


def is_graphiti_memory_enabled() -> bool:
    v = (os.getenv("GRAPHITI_MEMORY_ENABLED") or "").strip().lower()
    return v in ("1", "true", "yes", "on")


def graphiti_search_limit() -> int:
    try:
        n = int(os.getenv("GRAPHITI_SEARCH_LIMIT", "8"))
        return max(1, min(n, 20))
    except ValueError:
        return 8


def _scope_token(telegram_chat_id: int) -> str:
    return f"<<<TGCHAT_{int(telegram_chat_id)}>>>"


def _run_graphiti(coro: Awaitable[Any]) -> Any:
    """Serialize Graphiti async ops — library expects episodes added sequentially."""
    with _op_lock:
        return asyncio.run(coro)


def _get_client() -> Any:
    global _client
    with _init_lock:
        if _client is not None:
            return _client
        from graphiti_core import Graphiti
        from graphiti_core.driver.neo4j_driver import Neo4jDriver

        uri = (os.getenv("NEO4J_URI") or "").strip()
        user = (os.getenv("NEO4J_USERNAME") or "").strip()
        password = (os.getenv("NEO4J_PASSWORD") or "").strip()
        if not uri or not user or not password:
            raise ValueError("NEO4J_URI, NEO4J_USERNAME, and NEO4J_PASSWORD are required for Graphiti")

        db = (os.getenv("GRAPHITI_NEO4J_DATABASE") or "neo4j").strip() or "neo4j"
        driver = Neo4jDriver(uri, user, password, database=db)
        _client = Graphiti(graph_driver=driver)
        return _client


async def _ensure_schema(client: Any) -> None:
    global _schema_ready
    if _schema_ready:
        return
    await client.build_indices_and_constraints()
    _schema_ready = True


def format_episode_body(
    telegram_chat_id: int,
    telegram_user_id: int,
    user_text: str,
    assistant_text: str,
) -> str:
    tok = _scope_token(telegram_chat_id)
    return (
        f"{tok}\n"
        f"telegram_user_id={int(telegram_user_id)} telegram_chat_id={int(telegram_chat_id)}\n\n"
        f"User: {user_text.strip()}\n\n"
        f"Assistant: {assistant_text.strip()}"
    )


def format_memory_for_prompt(facts: list[str]) -> str:
    if not facts:
        return "(none)"
    lines = [f"- {f.strip()}" for f in facts if f and str(f).strip()]
    if not lines:
        return "(none)"
    return "\n".join(lines)


def search_memory_facts(
    telegram_chat_id: int,
    telegram_user_id: int,
    user_query: str,
) -> list[str]:
    """
    Hybrid search over Graphiti facts, restricted to this chat via scope token filtering.
    """
    if not is_graphiti_memory_enabled():
        return []

    tok = _scope_token(telegram_chat_id)

    async def _search() -> list[str]:
        client = _get_client()
        await _ensure_schema(client)
        q = f"{tok} {user_query.strip()}"
        edges = await client.search(q, num_results=graphiti_search_limit() * 3)
        facts: list[str] = []
        for e in edges:
            fact = getattr(e, "fact", None)
            if not fact:
                continue
            fs = str(fact).strip()
            if tok not in fs and str(telegram_chat_id) not in fs:
                continue
            facts.append(fs)
            if len(facts) >= graphiti_search_limit():
                break
        return facts

    try:
        return _run_graphiti(_search())
    except Exception as e:
        logger.warning("graphiti_search_failed", error=str(e))
        return []


def append_episode(
    telegram_chat_id: int,
    telegram_user_id: int,
    user_text: str,
    assistant_text: str,
) -> None:
    if not is_graphiti_memory_enabled():
        return
    try:
        from graphiti_core.nodes import EpisodeType
    except ImportError:
        logger.warning("graphiti_memory_import_failed", package="graphiti_core")
        return

    body = format_episode_body(
        telegram_chat_id, telegram_user_id, user_text, assistant_text
    )
    name = f"tg-{telegram_chat_id}-{uuid.uuid4().hex[:12]}"
    desc = f"telegram chat_id={telegram_chat_id} user_id={telegram_user_id}"

    async def _add() -> None:
        client = _get_client()
        await _ensure_schema(client)
        await client.add_episode(
            name=name,
            episode_body=body,
            source=EpisodeType.text,
            source_description=desc,
            reference_time=datetime.now(timezone.utc),
        )

    try:
        _run_graphiti(_add())
    except Exception as e:
        logger.warning("graphiti_append_episode_failed", error=str(e))
