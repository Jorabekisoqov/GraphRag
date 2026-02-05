# GraphRAG System

A Graph Retrieval-Augmented Generation (GraphRAG) system designed to answer questions about legal regulations and accounting standards (BHMS) using a Knowledge Graph stored in Neo4j.

## Features

- **Knowledge Graph Ingestion**: Automatically ingests structured JSON data (Nodes, Relationships, Documents) into Neo4j.
- **Natural Language Understanding**: Uses LLM (GPT-4o) to refine user queries and translate terms (e.g., English -> Uzbek).
- **Graph Retrieval**: Executes specialized Cypher queries to retrieve relevant context from the graph.
- **Intelligent Synthesis**: Combines graph context with LLM capabilities to generate accurate, natural language answers.
- **Telegram Bot Interface**: Provides a user-friendly chat interface for interacting with the system.
- **Rate Limiting**: Built-in protection against abuse with configurable rate limits.
- **Health Checks**: System health monitoring via `/health` command.
- **Structured Logging**: Comprehensive logging with structured output for better observability.
- **Error Handling**: Robust retry logic for API calls and improved error messages.
- **Input Validation**: Validates user queries and ingestion data for security and stability.
- **Monitoring**: Prometheus metrics for query tracking and system health.
- **Docker Support**: Full Docker and Docker Compose setup for easy deployment.
- **CI/CD**: GitHub Actions pipeline for automated testing and linting.

## Architecture

The system is built using:
- **Python 3.10+**
- **Neo4j**: Graph Database for storing entities and relationships.
- **LangChain**: Framework for RAG chains and LLM interactions.
- **OpenAI GPT-4o**: Large Language Model for reasoning and generation.
- **python-telegram-bot**: Interface for user interaction.

## Quick Start

### Option 1: Docker Deployment (Recommended)

1. **Clone the repository**:
   ```bash
   git clone https://github.com/Jorabekisoqov/GraphRag
   cd GraphRag
   ```

2. **Create `.env` file**:
   ```bash
   cp .env.example .env
   # Edit .env with your actual credentials
   ```

3. **Start with Docker Compose**:
   ```bash
   docker compose up -d
   # or if you have docker-compose v1: docker-compose up -d
   ```

4. **Ingest data** (in a separate terminal):
   ```bash
   docker compose exec graphrag-app python3 -m src.data.ingestion
   # or: docker-compose exec graphrag-app python3 -m src.data.ingestion
   ```

The bot will start automatically and Neo4j will be available at `http://localhost:7474`.

### Option 2: Manual Deployment

#### Prerequisites
- Valid OpenAI API Key
- Neo4j Database (Remote or Local)
- Python 3.10+ (The deployment script can parse this for you, and a helper installer is included for older servers)

#### Deployment Steps

1. **Clone the repository**:
   ```bash
   git clone https://github.com/Jorabekisoqov/GraphRag
   cd GraphRag
   ```

2. **Run the deployment helper**:
   ```bash
   ./deploy.sh
   ```
   - The script will check for Python 3.10+.
   - If your server has an older Python version (e.g., CentOS 7 with Python 3.6), it will error out.
   - **Fix for old Python**: Run the included installer:
     ```bash
     sudo ./install_python.sh
     ```
     (This compiles Python 3.10 from source, which may take ~5-10 minutes).
   - Then run `./deploy.sh` again.

3. **Follow the prompts**:
   - The script will ask you to create a `.env` file if missing.
   - Create and activate a virtual environment
   - Install necessary dependencies
   - Check for your `.env` file (you'll need to create one if it doesn't exist)
   - Give you options to run the Ingestion script or start the Telegram Bot

   If you prefer to run commands manually after setup:
   ```bash
   source .venv/bin/activate
   python3 -m src.data.ingestion      # To ingest data
   python3 -m src.bot.telegram_bot    # To start the bot
   ```



## Usage

### Telegram Bot Commands

- `/start` - Start the bot and get a welcome message
- `/health` - Check system health status (Neo4j and OpenAI connectivity)
- Send any text message to query the knowledge graph

### Data Ingestion
Load the knowledge graph from the source JSON files:
```bash
python3 -m src.data.ingestion
```

Or with Docker:
```bash
docker compose exec graphrag-app python3 -m src.data.ingestion
# or: docker-compose exec graphrag-app python3 -m src.data.ingestion
```

### Running the Bot
Start the Telegram bot to interact with the system:
```bash
python3 -m src.bot.telegram_bot
```

Or with Docker:
```bash
docker compose up graphrag-app
# or: docker-compose up graphrag-app
```

### Testing

Run the test suite:
```bash
pytest tests/ -v
```

Run with coverage:
```bash
pytest tests/ --cov=src --cov-report=html
```

### Code Quality

Format code:
```bash
black src/ tests/
ruff check src/ tests/
```

Type checking:
```bash
mypy src/
```

### Backup and Restore

Backup Neo4j data:
```bash
./scripts/backup_neo4j.sh
```

Restore from backup:
```bash
./scripts/restore_neo4j.sh <backup_file.cypher>
```

## Environment Variables

Create a `.env` file based on `.env.example`:

```bash
cp .env.example .env
```

Required variables:
- `OPENAI_API_KEY` - Your OpenAI API key
- `NEO4J_URI` - Neo4j connection URI (e.g., `bolt://localhost:7687` or `neo4j+s://...`)
- `NEO4J_USERNAME` - Neo4j username
- `NEO4J_PASSWORD` - Neo4j password
- `TELEGRAM_BOT_TOKEN` - Your Telegram bot token

## Project Structure

```
GraphRag/
├── src/
│   ├── bot/              # Telegram bot interface
│   ├── core/             # Core orchestration logic
│   ├── data/              # Data ingestion and graph RAG
│   └── api/               # API endpoints (health checks)
├── tests/                 # Test suite
├── scripts/               # Utility scripts (backup, restore)
├── Dockerfile             # Docker image definition
├── docker-compose.yml     # Docker Compose configuration
├── requirements.txt       # Python dependencies
├── pyproject.toml         # Project configuration (black, ruff, mypy)
└── .github/workflows/     # CI/CD pipelines
```

See `structure.md` for a detailed breakdown of the codebase organization.

## Development

### Setting up Development Environment

1. Clone the repository
2. Create a virtual environment:
   ```bash
   python3 -m venv .venv
   source .venv/bin/activate
   ```
3. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```
4. Install pre-commit hooks (optional):
   ```bash
   pip install pre-commit
   pre-commit install
   ```

### Running Tests

```bash
pytest tests/ -v
```

### Code Formatting

The project uses `black` for code formatting and `ruff` for linting:

```bash
black src/ tests/
ruff check src/ tests/
ruff check --fix src/ tests/  # Auto-fix issues
```

## Monitoring

The system includes Prometheus metrics for monitoring:
- Query count and duration
- API call metrics
- System health status

Metrics are available at the application level and can be exposed via a Prometheus endpoint if needed.

## Contributing

1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Run tests and linting
5. Submit a pull request

## License

See LICENSE file for details.
