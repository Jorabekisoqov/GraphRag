"""Tests for orchestrator module."""
import pytest
from unittest.mock import Mock, patch, MagicMock
from src.data.retrieval_types import RetrievalResult
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
        mock_hybrid.return_value = RetrievalResult(
            context_for_llm="Detailed graph result with accounting standards and regulations.",
            chunks=[],
        )
        mock_synthesize.return_value = "final answer"

        result = process_query("test query")
        assert result == "final answer"
        mock_refine.assert_called_once_with("test query")
        mock_hybrid.assert_called_once_with("refined query", original_query="test query")
        mock_synthesize.assert_called_once_with(
            "test query",
            "Detailed graph result with accounting standards and regulations.",
            conversation_history="(none)",
            agent_memory="(none)",
        )
        mock_fallback.assert_not_called()

    @patch('src.core.orchestrator.fallback_text_search')
    @patch('src.core.orchestrator.hybrid_retrieve')
    @patch('src.core.orchestrator.refine_query')
    @patch('src.core.orchestrator.synthesize_response')
    def test_process_query_fallback_used(self, mock_synthesize, mock_refine, mock_hybrid, mock_fallback):
        """Test that fallback text search is used when hybrid returns weak result."""
        mock_refine.return_value = "refined query"
        mock_hybrid.return_value = RetrievalResult(
            context_for_llm="I don't know", chunks=[]
        )  # weak result
        mock_fallback.return_value = RetrievalResult(
            context_for_llm="Fallback chunk text with relevant content.",
            chunks=[],
        )
        mock_synthesize.return_value = "final answer from fallback"

        result = process_query("test query")
        assert result == "final answer from fallback"
        mock_fallback.assert_called_once_with(
            "test query", original_query="test query"
        )
        mock_synthesize.assert_called_once_with(
            "test query",
            "Fallback chunk text with relevant content.",
            conversation_history="(none)",
            agent_memory="(none)",
        )

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

    @patch("src.core.orchestrator.append_exchange")
    @patch("src.core.orchestrator.fetch_recent_messages")
    @patch("src.core.orchestrator.is_chat_history_enabled", return_value=True)
    @patch("src.core.orchestrator.fallback_text_search")
    @patch("src.core.orchestrator.hybrid_retrieve")
    @patch("src.core.orchestrator.refine_query")
    @patch("src.core.orchestrator.synthesize_response")
    def test_process_query_passes_conversation_history_and_appends(
        self,
        mock_synthesize,
        mock_refine,
        mock_hybrid,
        mock_fallback,
        _mock_enabled,
        mock_fetch,
        mock_append,
    ):
        mock_refine.return_value = "refined"
        mock_hybrid.return_value = RetrievalResult(
            context_for_llm="Detailed graph result with accounting standards and regulations.",
            chunks=[],
        )
        mock_fetch.return_value = [{"role": "user", "text": "Old question"}]
        mock_synthesize.return_value = "final answer"

        result = process_query(
            "new question",
            telegram_user_id=111,
            telegram_chat_id=222,
        )
        assert result == "final answer"
        mock_fetch.assert_called_once()
        mock_synthesize.assert_called_once_with(
            "new question",
            "Detailed graph result with accounting standards and regulations.",
            conversation_history="User: Old question",
            agent_memory="(none)",
        )
        mock_append.assert_called_once_with(111, 222, "new question", "final answer")
