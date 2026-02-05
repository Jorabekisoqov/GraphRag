"""Pytest configuration and fixtures."""
import pytest
import os
from unittest.mock import Mock, MagicMock
from dotenv import load_dotenv

# Load test environment variables if available
load_dotenv()


@pytest.fixture
def mock_neo4j_graph():
    """Mock Neo4j graph object."""
    graph = Mock()
    graph.query = Mock(return_value=[])
    graph.refresh_schema = Mock()
    graph.schema = "Mock schema"
    return graph


@pytest.fixture
def mock_openai_llm():
    """Mock OpenAI LLM."""
    llm = Mock()
    llm.invoke = Mock(return_value=Mock(content="Mock response"))
    return llm


@pytest.fixture
def sample_json_data():
    """Sample JSON data for ingestion tests."""
    return {
        "metadata": {
            "file_name": "test_document.json",
            "document_title": "Test Document",
            "reg_number": "123",
            "date_signed": "2024-01-01",
            "authority": "Test Authority"
        },
        "graph_data": [
            {
                "chunk_id": "chunk1",
                "original_text": "Test text",
                "nodes": [
                    {
                        "id": "node1",
                        "type": "Entity",
                        "properties": {"name": "Test Node"}
                    }
                ],
                "relationships": []
            }
        ]
    }
