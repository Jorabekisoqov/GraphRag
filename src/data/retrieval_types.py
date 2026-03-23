"""Lightweight types for hybrid retrieval (no Neo4j / LangChain imports)."""
from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class RetrievedChunk:
    """A single retrieved Chunk: Neo4j `Chunk.id` plus text body."""

    id: str
    text: str


@dataclass
class RetrievalResult:
    """Merged retrieval for the LLM and for citation verification."""

    context_for_llm: str
    chunks: list[RetrievedChunk]

    @property
    def text(self) -> str:
        """Alias for context_for_llm."""
        return self.context_for_llm
