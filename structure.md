# Project Structure

This document outlines the organization of the GraphRAG project codebase.

## Directory Tree

```
GraphRag/
├── src/
│   ├── bot/
│   │   └── telegram_bot.py       # Entry point for the Telegram Bot interface.
│   │
│   ├── core/
│   │   └── orchestrator.py       # Central logic: Refines queries, calls Graph RAG, returns synthesis.
│   │
│   └── data/
│       ├── ingestion.py          # Script to load JSON graph data into Neo4j.
│       ├── graph_rag.py          # Defines the LangChain GraphQA chain and Cypher generation.
│       ├── neo4j_client.py       # Handles connection to the Neo4j database.
│       └── source/               # Data source files.
│           ├── Json/             # Structured data with Nodes/Relationships.
│           └── Raw/              # Original text files (.txt format).
│
├── .env                          # Environment variables (API Keys, DB Creds).
├── requirements.txt              # Python dependencies.
├── README.md                     # General project documentation.
└── structure.md                  # This file.
```

## Key Components

- **src.core.orchestrator**: The "brain" of the application. It receives raw text from the bot, uses an LLM to refine it into a search query (handling language translation if needed), queries the graph, and synthesizes the final answer.
- **src.data.ingestion**: Responsible for populating the database. It reads custom JSON files containing pre-extracted graph elements and runs Cypher queries to insert them.
- **src.data.graph_rag**: Wraps the `GraphCypherQAChain`. It includes custom prompts to ensure the LLM generates valid Cypher queries compatible with the specific schema and language (Uzbek) of the data.
