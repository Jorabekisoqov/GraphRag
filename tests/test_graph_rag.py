"""Tests for graph_rag module."""
import pytest
from unittest.mock import Mock, patch, MagicMock
from src.data.graph_rag import (
    get_graph_rag_chain,
    query_graph,
    fallback_text_search,
    _is_weak_result,
    _extract_bilingual_keywords,
    _extract_domain_terms,
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


class TestExtractDomainTerms:
    """Tests for _extract_domain_terms."""

    def test_extracts_bhms_number(self):
        """Test extraction of BHMS numbers like 1-son, 21-sonli."""
        result = _extract_domain_terms("1-сон БҲМС нима ҳақида?")
        assert "1-сон" in result or "БҲМС" in result

    def test_extracts_account_codes(self):
        """Test extraction of 4-digit account codes."""
        result = _extract_domain_terms("0110 ва 4610 счётлар")
        assert "0110" in result
        assert "4610" in result

    def test_extracts_moliya(self):
        """Test extraction of Moliya/Moliyа."""
        result = _extract_domain_terms("Молия вазирлиги")
        assert "Молия" in result


class TestExtractBilingualKeywords:
    """Tests for _extract_bilingual_keywords."""

    def test_prioritizes_original_uzbek_terms(self):
        """Test that Uzbek terms from original query are included."""
        original = "1-сон БҲМС нима ҳақида?"
        refined = "Find information about BHMS 1"
        result = _extract_bilingual_keywords(refined, original, max_keywords=5)
        # Should include domain terms (1-son, BHMS) and/or Uzbek keywords
        assert len(result) >= 1
        # At least one term should be from original (BHMS, 1-son, or Uzbek word)
        has_domain = any(
            "1" in t or "son" in t.lower() or "bhms" in t.lower() or "бҲмс" in t
            for t in result
        )
        assert has_domain, f"Expected domain terms in {result}"

    def test_merges_refined_and_original(self):
        """Test that both refined and original keywords are merged."""
        original = "Бухгалтерия ҳисобварақлар"
        refined = "chart of accounts buxgalteriya"
        result = _extract_bilingual_keywords(refined, original, max_keywords=6)
        assert len(result) >= 2

    def test_fallback_when_empty(self):
        """Test fallback to simple extraction when no domain terms."""
        result = _extract_bilingual_keywords("hello world", "привет мир", max_keywords=3)
        assert isinstance(result, list)
        assert len(result) >= 1


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

    @patch('src.data.graph_rag.get_neo4j_graph')
    def test_fallback_with_original_query_uses_bilingual_keywords(self, mock_get_graph):
        """Test fallback with original_query uses bilingual keyword extraction."""
        mock_graph = Mock()
        mock_graph.query.return_value = [{"text": "1-sonli BHMS content"}]
        mock_get_graph.return_value = mock_graph

        result = fallback_text_search(
            "Find info about BHMS 1",
            original_query="1-сон БҲМС нима ҳақида?",
        )
        assert "1-sonli BHMS content" in result
        # Should have been called with keywords derived from both queries
        mock_graph.query.assert_called()
