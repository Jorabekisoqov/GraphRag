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

## Deployment on Server

For easy deployment on a Linux server, you can use the provided `deploy.sh` script.

1.  **Clone the repository**:
    ```bash
    git clone https://github.com/Jorabekisoqov/GraphRag.git
    cd GraphRag
    ```

2.  **Run the Deployment Script**:
    ```bash
    ./deploy.sh
    ```
    This script will:
    - Check for Python 3.10+
    - Create and activate a virtual environment
    - Install necessary dependencies
    - Check for your `.env` file (you'll need to create one if it doesn't exist)
    - Give you options to run the Ingestion script or start the Telegram Bot

3.  **Manual Execution** (Optional):
    If you prefer to run commands manually after setup:
    ```bash
    source .venv/bin/activate
    python3 -m src.data.ingestion      # To ingest data
    python3 -m src.bot.telegram_bot    # To start the bot
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
