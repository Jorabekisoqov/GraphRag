"""Tests for ingestion module."""
import pytest
import json
import tempfile
import os
from unittest.mock import Mock, patch, MagicMock
from src.data.ingestion import ingest_json_data


class TestIngestJsonData:
    """Tests for JSON data ingestion."""
    
    def test_ingest_json_data_success(self, mock_neo4j_graph, sample_json_data):
        """Test successful JSON ingestion."""
        with tempfile.TemporaryDirectory() as tmpdir:
            json_file = os.path.join(tmpdir, "test.json")
            with open(json_file, 'w', encoding='utf-8') as f:
                json.dump(sample_json_data, f)
            
            with patch('src.data.ingestion.get_neo4j_graph', return_value=mock_neo4j_graph):
                ingest_json_data(tmpdir)
            
            # Verify that graph.query was called
            assert mock_neo4j_graph.query.called
            assert mock_neo4j_graph.refresh_schema.called
    
    def test_ingest_json_data_invalid_file(self, mock_neo4j_graph):
        """Test handling of invalid JSON files."""
        with tempfile.TemporaryDirectory() as tmpdir:
            json_file = os.path.join(tmpdir, "invalid.json")
            with open(json_file, 'w', encoding='utf-8') as f:
                f.write("invalid json content")
            
            with patch('src.data.ingestion.get_neo4j_graph', return_value=mock_neo4j_graph):
                # Should not raise exception, but handle error gracefully
                ingest_json_data(tmpdir)
    
    def test_ingest_json_data_missing_fields(self, mock_neo4j_graph):
        """Test handling of JSON with missing required fields."""
        incomplete_data = {
            "metadata": {
                "file_name": "test.json"
            },
            "graph_data": []
        }
        
        with tempfile.TemporaryDirectory() as tmpdir:
            json_file = os.path.join(tmpdir, "incomplete.json")
            with open(json_file, 'w', encoding='utf-8') as f:
                json.dump(incomplete_data, f)
            
            with patch('src.data.ingestion.get_neo4j_graph', return_value=mock_neo4j_graph):
                ingest_json_data(tmpdir)
                # Should handle gracefully without crashing
