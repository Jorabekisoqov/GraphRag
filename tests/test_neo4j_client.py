"""Tests for neo4j_client module."""
import pytest
from unittest.mock import Mock, patch
import os
from src.data.neo4j_client import get_neo4j_graph


class TestGetNeo4jGraph:
    """Tests for Neo4j graph connection."""
    
    @patch.dict(os.environ, {
        'NEO4J_URI': 'neo4j://localhost:7687',
        'NEO4J_USERNAME': 'neo4j',
        'NEO4J_PASSWORD': 'password'
    })
    @patch('src.data.neo4j_client.Neo4jGraph')
    def test_get_neo4j_graph_success(self, mock_neo4j_graph):
        """Test successful Neo4j connection."""
        mock_graph = Mock()
        mock_neo4j_graph.return_value = mock_graph
        
        result = get_neo4j_graph()
        assert result == mock_graph
        mock_neo4j_graph.assert_called_once()
    
    @patch.dict(os.environ, {}, clear=True)
    def test_get_neo4j_graph_missing_env(self):
        """Test error when environment variables are missing."""
        with pytest.raises(ValueError, match="Neo4j configuration"):
            get_neo4j_graph()
    
    @patch.dict(os.environ, {
        'NEO4J_URI': 'neo4j+s://localhost:7687',
        'NEO4J_USERNAME': 'neo4j',
        'NEO4J_PASSWORD': 'password'
    })
    @patch('src.data.neo4j_client.Neo4jGraph')
    def test_get_neo4j_graph_ssl_downgrade(self, mock_neo4j_graph):
        """Test SSL downgrade for neo4j+s:// URLs."""
        mock_graph = Mock()
        mock_neo4j_graph.return_value = mock_graph
        
        result = get_neo4j_graph()
        # Verify that the URI was downgraded
        call_args = mock_neo4j_graph.call_args
        assert 'neo4j+ssc://' in call_args[1]['url'] or 'neo4j+ssc://' in call_args[0][0]
