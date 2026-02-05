# Quick Server Commands Reference

## Docker Deployment Commands

### Initial Setup
```bash
# Clone and enter directory
git clone https://github.com/Jorabekisoqov/GraphRag
cd GraphRag

# Create .env file
cp .env.example .env
nano .env  # Add your credentials

# Quick deploy
./server-deploy.sh docker
```

### Daily Operations

**Note:** Use `docker compose` (space) for Docker Compose v2, or `docker-compose` (hyphen) for v1. The script auto-detects which to use.

**Start services:**
```bash
docker compose up -d
# or: docker-compose up -d
```

**Stop services:**
```bash
docker compose down
# or: docker-compose down
```

**View logs:**
```bash
# All services
docker compose logs -f
# or: docker-compose logs -f

# Bot only
docker compose logs -f graphrag-app
# or: docker-compose logs -f graphrag-app

# Neo4j only
docker compose logs -f neo4j
# or: docker-compose logs -f neo4j
```

**Check status:**
```bash
docker compose ps
# or: docker-compose ps
```

**Restart bot:**
```bash
docker compose restart graphrag-app
# or: docker-compose restart graphrag-app
```

**Ingest/Re-ingest data:**
```bash
docker compose exec graphrag-app python3 -m src.data.ingestion
# or: docker-compose exec graphrag-app python3 -m src.data.ingestion
```

**Access Neo4j shell:**
```bash
docker compose exec neo4j cypher-shell -u neo4j -p your_password
# or: docker-compose exec neo4j cypher-shell -u neo4j -p your_password
```

**Update code:**
```bash
git pull
docker compose up -d --build
docker compose exec graphrag-app python3 -m src.data.ingestion
# or: docker-compose up -d --build && docker-compose exec graphrag-app python3 -m src.data.ingestion
```

## Manual Deployment Commands

### Initial Setup
```bash
# Clone and enter directory
git clone https://github.com/Jorabekisoqov/GraphRag
cd GraphRag

# Run deployment script
./deploy.sh

# Or use quick deploy
./server-deploy.sh manual
```

### Daily Operations

**Activate virtual environment:**
```bash
source .venv/bin/activate
```

**Start bot:**
```bash
python3 -m src.bot.telegram_bot
```

**Ingest data:**
```bash
python3 -m src.data.ingestion
```

**Check bot status (if using systemd):**
```bash
sudo systemctl status graphrag-bot
sudo systemctl restart graphrag-bot
sudo systemctl stop graphrag-bot
sudo systemctl start graphrag-bot
```

**View logs (systemd):**
```bash
sudo journalctl -u graphrag-bot -f
```

## Common Tasks

### Check if bot is running
```bash
# Docker
docker-compose ps | grep graphrag-app

# Manual
ps aux | grep telegram_bot
# or
sudo systemctl status graphrag-bot
```

### Test Neo4j connection
```bash
# Docker
docker-compose exec neo4j cypher-shell -u neo4j -p your_password "RETURN 1"

# Manual
cypher-shell -u neo4j -p your_password -a bolt://localhost:7687 "RETURN 1"
```

### Check data in Neo4j
```bash
# Count nodes
docker-compose exec neo4j cypher-shell -u neo4j -p your_password \
  "MATCH (n) RETURN count(n) as node_count"

# List documents
docker-compose exec neo4j cypher-shell -u neo4j -p your_password \
  "MATCH (d:Document) RETURN d.title LIMIT 10"
```

### Backup Neo4j
```bash
# Docker
docker-compose exec neo4j neo4j-admin database dump neo4j --to-path=/backups/

# Manual
neo4j-admin database dump neo4j --to-path=/backups/
```

### View recent errors
```bash
# Docker
docker-compose logs graphrag-app | grep -i error | tail -20

# Manual
journalctl -u graphrag-bot | grep -i error | tail -20
```

## Troubleshooting

### Bot not responding
```bash
# Check if running
docker-compose ps  # or systemctl status

# Check logs for errors
docker-compose logs graphrag-app | tail -50

# Restart bot
docker-compose restart graphrag-app
```

### Neo4j connection issues
```bash
# Check Neo4j is running
docker-compose ps neo4j

# Check Neo4j logs
docker-compose logs neo4j | tail -50

# Test connection
docker-compose exec neo4j cypher-shell -u neo4j -p your_password "RETURN 1"
```

### Data ingestion failed
```bash
# Check JSON files exist
ls -la src/data/source/Json/

# Run ingestion with verbose output
docker-compose exec graphrag-app python3 -m src.data.ingestion

# Check Neo4j for existing data
docker-compose exec neo4j cypher-shell -u neo4j -p your_password \
  "MATCH (n) RETURN count(n)"
```

## Environment Variables

Required in `.env` file:
```bash
OPENAI_API_KEY=sk-...
NEO4J_URI=bolt://neo4j:7687  # or bolt://your-host:7687
NEO4J_USERNAME=neo4j
NEO4J_PASSWORD=your_password
TELEGRAM_BOT_TOKEN=your_token
```

## Ports

- **Neo4j HTTP**: 7474 (browser interface)
- **Neo4j Bolt**: 7687 (application connection)
- **Bot**: No exposed port (uses Telegram API)

## File Locations

- **Logs**: Docker logs or systemd journal
- **Data**: `src/data/source/Json/` and `src/data/source/Raw/`
- **Config**: `.env` file
- **Neo4j Data**: Docker volume `neo4j_data` or `/var/lib/neo4j/data`
