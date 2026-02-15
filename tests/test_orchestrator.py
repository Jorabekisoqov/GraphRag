"""Tests for orchestrator module."""
import pytest
from unittest.mock import Mock, patch, MagicMock
from src.core.orchestrator import refine_query, synthesize_response, process_query


class TestRefineQuery:
    """Tests for query refinement."""
    
    @patch('src.core.orchestrator.llm')
    def test_refine_query_success(self, mock_llm):
        """Test successful query refinement."""
        mock_llm.invoke.return_value = Mock(content="Find information about accounting standards")
        result = refine_query("Tell me about accounting")
        assert isinstance(result, str)
        assert len(result) > 0
    
    @patch('src.core.orchestrator.llm')
    def test_refine_query_empty_input(self, mock_llm):
        """Test refinement with empty input."""
        mock_llm.invoke.return_value = Mock(content="")
        result = refine_query("")
        assert isinstance(result, str)


class TestSynthesizeResponse:
    """Tests for response synthesis."""
    
    @patch('src.core.orchestrator.llm')
    def test_synthesize_response_success(self, mock_llm):
        """Test successful response synthesis."""
        mock_llm.invoke.return_value = Mock(content="Based on the context, here is the answer...")
        result = synthesize_response("What is accounting?", "Context: Accounting standards...")
        assert isinstance(result, str)
        assert len(result) > 0


class TestProcessQuery:
    """Tests for main query processing."""
    
    @patch('src.core.orchestrator.fallback_text_search')
    @patch('src.core.orchestrator.hybrid_retrieve')
    @patch('src.core.orchestrator.refine_query')
    @patch('src.core.orchestrator.synthesize_response')
    def test_process_query_success(self, mock_synthesize, mock_refine, mock_hybrid, mock_fallback):
        """Test successful query processing."""
        mock_refine.return_value = "refined query"
        # Return non-weak result (>=50 chars, no weak patterns) so fallback is not triggered
        mock_hybrid.return_value = "Detailed graph result with accounting standards and regulations."
        mock_synthesize.return_value = "final answer"

        result = process_query("test query")
        assert result == "final answer"
        mock_refine.assert_called_once_with("test query")
        mock_hybrid.assert_called_once_with("refined query", original_query="test query")
        mock_synthesize.assert_called_once_with("test query", "Detailed graph result with accounting standards and regulations.")
        mock_fallback.assert_not_called()

    @patch('src.core.orchestrator.fallback_text_search')
    @patch('src.core.orchestrator.hybrid_retrieve')
    @patch('src.core.orchestrator.refine_query')
    @patch('src.core.orchestrator.synthesize_response')
    def test_process_query_fallback_used(self, mock_synthesize, mock_refine, mock_hybrid, mock_fallback):
        """Test that fallback text search is used when hybrid returns weak result."""
        mock_refine.return_value = "refined query"
        mock_hybrid.return_value = "I don't know"  # weak result
        mock_fallback.return_value = "Fallback chunk text with relevant content."
        mock_synthesize.return_value = "final answer from fallback"

        result = process_query("test query")
        assert result == "final answer from fallback"
        mock_fallback.assert_called_once_with(
            "refined query", original_query="test query"
        )
        mock_synthesize.assert_called_once_with("test query", "Fallback chunk text with relevant content.")

    def test_process_query_empty(self):
        """Test processing empty query."""
        result = process_query("")
        assert "valid query" in result.lower()
    
    @patch('src.core.orchestrator.hybrid_retrieve')
    @patch('src.core.orchestrator.refine_query')
    def test_process_query_error_handling(self, mock_refine, mock_hybrid):
        """Test error handling in query processing."""
        mock_refine.side_effect = Exception("Test error")
        result = process_query("test query")
        assert "error" in result.lower() or "sorry" in result.lower()
