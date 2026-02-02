# GraphRAG System

A Graph Retrieval-Augmented Generation (GraphRAG) system designed to answer questions about legal regulations and accounting standards (BHMS) using a Knowledge Graph stored in Neo4j.

## Features

- **Knowledge Graph Ingestion**: Automatically ingests structured JSON data (Nodes, Relationships, Documents) into Neo4j.
- **Natural Language Understanding**: Uses LLM (GPT-4o) to refine user queries and translate terms (e.g., English -> Uzbek).
- **Graph Retrieval**: Executes specialized Cypher queries to retrieve relevant context from the graph.
- **Intelligent Synthesis**: Combines graph context with LLM capabilities to generate accurate, natural language answers.
- **Telegram Bot Interface**: Provides a user-friendly chat interface for interacting with the system.

## Architecture

The system is built using:
- **Python 3.10+**
- **Neo4j**: Graph Database for storing entities and relationships.
- **LangChain**: Framework for RAG chains and LLM interactions.
- **OpenAI GPT-4o**: Large Language Model for reasoning and generation.
- **python-telegram-bot**: Interface for user interaction.

## Installation

1.  **Clone the repository**:
    ```bash
    git clone <repository_url>
    cd GraphRag
    ```

2.  **Create a Virtual Environment**:
    ```bash
    python3 -m venv .venv
    source .venv/bin/activate
    ```

3.  **Install Dependencies**:
    ```bash
    pip install -r requirements.txt
    ```

4.  **Configuration**:
    Create a `.env` file in the root directory with the following credentials:
    ```env
    OPENAI_API_KEY=your_openai_key
    NEO4J_URI=neo4j+s://your_instance.databases.neo4j.io
    NEO4J_USERNAME=neo4j
    NEO4J_PASSWORD=your_password
    TELEGRAM_BOT_TOKEN=your_telegram_bot_token
    ```

## Usage

### 1. Ingest Data
Load the knowledge graph from the source JSON files:
```bash
python3 -m src.data.ingestion
```

### 2. Run the Bot
Start the Telegram bot to interact with the system:
```bash
python3 -m src.bot.telegram_bot
```

### 3. Test via CLI
You can also run a test query directly from the terminal:
```bash
python3 -m src.core.orchestrator
```

## Project Structure
See `structure.md` for a detailed breakdown of the codebase organization.
