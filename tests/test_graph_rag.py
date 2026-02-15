"""Tests for graph_rag module."""
import pytest
from unittest.mock import Mock, patch, MagicMock
from src.data.graph_rag import (
    get_graph_rag_chain,
    query_graph,
    fallback_text_search,
    _is_weak_result,
)


class TestGetGraphRagChain:
    """Tests for graph RAG chain creation."""
    
    @patch('src.data.graph_rag.get_neo4j_graph')
    @patch('src.data.graph_rag.ChatOpenAI')
    def test_get_graph_rag_chain_success(self, mock_chat_openai, mock_get_graph):
        """Test successful chain creation."""
        mock_graph = Mock()
        mock_get_graph.return_value = mock_graph
        mock_llm = Mock()
        mock_chat_openai.return_value = mock_llm
        
        chain = get_graph_rag_chain()
        assert chain is not None
        mock_get_graph.assert_called_once()
        mock_chat_openai.assert_called_once()


class TestQueryGraph:
    """Tests for graph querying."""
    
    @patch('src.data.graph_rag.get_graph_rag_chain')
    def test_query_graph_success(self, mock_get_chain):
        """Test successful graph query."""
        mock_chain = Mock()
        mock_chain.invoke.return_value = {"result": "Query result"}
        mock_get_chain.return_value = mock_chain
        
        result = query_graph("test query")
        assert result == "Query result"
        mock_chain.invoke.assert_called_once_with({"query": "test query"})
    
    @patch('src.data.graph_rag.get_graph_rag_chain')
    def test_query_graph_error(self, mock_get_chain):
        """Test error handling in graph query."""
        mock_chain = Mock()
        mock_chain.invoke.side_effect = Exception("Test error")
        mock_get_chain.return_value = mock_chain

        result = query_graph("test query")
        assert "error" in result.lower()


class TestIsWeakResult:
    """Tests for _is_weak_result helper."""

    def test_empty_string(self):
        assert _is_weak_result("") is True
        assert _is_weak_result("   ") is True

    def test_short_string(self):
        assert _is_weak_result("Hi") is True
        assert _is_weak_result("x" * 40) is True

    def test_weak_patterns(self):
        assert _is_weak_result("I don't know the answer") is True
        assert _is_weak_result("No results found") is True
        assert _is_weak_result("Error querying graph: timeout") is True

    def test_strong_result(self):
        assert _is_weak_result("21-son BҲMS is the main normative document.") is False
        assert _is_weak_result("A" * 60) is False


class TestFallbackTextSearch:
    """Tests for fallback_text_search."""

    @patch('src.data.graph_rag.get_neo4j_graph')
    def test_fallback_returns_concatenated_text(self, mock_get_graph):
        """Test fallback returns concatenated chunk texts."""
        mock_graph = Mock()
        mock_graph.query.return_value = [
            {"text": "Chunk 1 content"},
            {"text": "Chunk 2 content"},
        ]
        mock_get_graph.return_value = mock_graph

        result = fallback_text_search("BҲMS", keywords=["BҲMS"])
        assert "Chunk 1 content" in result
        assert "Chunk 2 content" in result
        mock_graph.query.assert_called()

    @patch('src.data.graph_rag.get_neo4j_graph')
    def test_fallback_empty_result(self, mock_get_graph):
        """Test fallback handles empty result."""
        mock_graph = Mock()
        mock_graph.query.return_value = []
        mock_get_graph.return_value = mock_graph

        result = fallback_text_search("nonexistent")
        assert result == ""
