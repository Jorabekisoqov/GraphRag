"""Tests for graph_rag module."""
import pytest
from unittest.mock import Mock, patch, MagicMock
from src.data.graph_rag import get_graph_rag_chain, query_graph


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
