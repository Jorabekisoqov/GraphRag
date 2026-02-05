# Server Deployment Guide

This guide covers deploying the GraphRAG system on a production server.

## Prerequisites

- **Server**: Linux server (Ubuntu 20.04+, CentOS 7+, or similar)
- **Python**: 3.10+ (or Docker installed)
- **Neo4j**: Can be local or remote
- **OpenAI API Key**: Valid API key
- **Telegram Bot Token**: From @BotFather

## Option 1: Docker Deployment (Recommended for Production)

### Step 1: Install Docker and Docker Compose

```bash
# Ubuntu/Debian
sudo apt-get update
sudo apt-get install -y docker.io docker-compose

# CentOS/RHEL
sudo yum install -y docker docker-compose

# Start Docker service
sudo systemctl start docker
sudo systemctl enable docker
```

### Step 2: Clone and Setup

```bash
# Clone repository
git clone https://github.com/Jorabekisoqov/GraphRag
cd GraphRag

# Create .env file
cp .env.example .env
nano .env  # Edit with your credentials
```

### Step 3: Configure .env File

```bash
# Required variables
OPENAI_API_KEY=sk-your-openai-key-here
NEO4J_URI=bolt://neo4j:7687  # For Docker, use service name
NEO4J_USERNAME=neo4j
NEO4J_PASSWORD=your_secure_password_here
TELEGRAM_BOT_TOKEN=your_telegram_bot_token_here
```

### Step 4: Update docker-compose.yml

Edit `docker-compose.yml` and update the Neo4j password in two places:
- Line 11: `NEO4J_AUTH=neo4j/your_password_here`
- Line 18: In the healthcheck command

### Step 5: Start Services

```bash
# Build and start containers
docker-compose up -d

# Check logs
docker-compose logs -f

# Check status
docker-compose ps
```

### Step 6: Ingest Data

```bash
# Run ingestion (includes new files: 1364, 3540, 1996)
docker-compose exec graphrag-app python3 -m src.data.ingestion
```

### Step 7: Verify Bot is Running

```bash
# Check bot logs
docker-compose logs -f graphrag-app

# Test bot in Telegram
# Send /start to your bot
```

### Step 8: Keep Bot Running (Production)

The bot runs automatically with `restart: unless-stopped` in docker-compose.yml. To ensure it restarts on server reboot:

```bash
# Make sure Docker starts on boot
sudo systemctl enable docker
```

## Option 2: Manual Deployment

### Step 1: Server Setup

```bash
# Clone repository
git clone https://github.com/Jorabekisoqov/GraphRag
cd GraphRag

# Make scripts executable
chmod +x deploy.sh install_python.sh
```

### Step 2: Check Python Version

```bash
python3 --version
# Should be 3.10 or higher
```

If Python < 3.10:
```bash
sudo ./install_python.sh
# This will take 5-10 minutes
```

### Step 3: Run Deployment Script

```bash
./deploy.sh
```

Follow the prompts:
1. Creates virtual environment
2. Installs dependencies
3. Checks for .env file
4. Offers to run ingestion or start bot

### Step 4: Create .env File

```bash
nano .env
```

Add:
```bash
OPENAI_API_KEY=sk-your-key-here
NEO4J_URI=bolt://your-neo4j-host:7687
NEO4J_USERNAME=neo4j
NEO4J_PASSWORD=your_password
TELEGRAM_BOT_TOKEN=your_token
```

### Step 5: Run Data Ingestion

```bash
source .venv/bin/activate
python3 -m src.data.ingestion
```

### Step 6: Start Bot with Systemd (Production)

Create a systemd service file:

```bash
sudo nano /etc/systemd/system/graphrag-bot.service
```

Add:
```ini
[Unit]
Description=GraphRAG Telegram Bot
After=network.target

[Service]
Type=simple
User=your_username
WorkingDirectory=/path/to/GraphRag
Environment="PATH=/path/to/GraphRag/.venv/bin"
ExecStart=/path/to/GraphRag/.venv/bin/python3 -m src.bot.telegram_bot
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
```

Enable and start:
```bash
sudo systemctl daemon-reload
sudo systemctl enable graphrag-bot
sudo systemctl start graphrag-bot
sudo systemctl status graphrag-bot
```

## Post-Deployment Checklist

- [ ] Neo4j is accessible and healthy
- [ ] Data ingestion completed successfully
- [ ] Bot responds to `/start` command
- [ ] Bot responds to `/health` command
- [ ] Bot can answer queries
- [ ] Logs are being generated
- [ ] Service auto-restarts on failure (systemd or Docker)

## Monitoring

### Check Bot Status

**Docker:**
```bash
docker-compose ps
docker-compose logs -f graphrag-app
```

**Manual:**
```bash
sudo systemctl status graphrag-bot
journalctl -u graphrag-bot -f
```

### Check Neo4j

```bash
# Docker
docker-compose exec neo4j cypher-shell -u neo4j -p your_password

# Manual
cypher-shell -u neo4j -p your_password -a bolt://localhost:7687
```

### View Logs

Logs are stored in:
- Docker: `docker-compose logs`
- Manual: Systemd journal or console output

## Troubleshooting

### Bot Not Starting

1. Check .env file exists and has correct values
2. Check Neo4j connection: `echo $NEO4J_URI`
3. Check OpenAI API key is valid
4. Check Telegram bot token is correct

### Data Ingestion Fails

1. Verify Neo4j is running and accessible
2. Check JSON files are in `src/data/source/Json/`
3. Check file permissions
4. Review ingestion logs

### Bot Not Responding

1. Check bot is running: `docker-compose ps` or `systemctl status`
2. Check logs for errors
3. Verify Telegram bot token is correct
4. Test with `/health` command

## Updating the System

### Update Code

```bash
git pull origin main
```

### Docker: Rebuild and Restart

```bash
docker-compose down
docker-compose build
docker-compose up -d
docker-compose exec graphrag-app python3 -m src.data.ingestion
```

### Manual: Restart Service

```bash
sudo systemctl restart graphrag-bot
```

## Backup Neo4j Data

```bash
# Docker
docker-compose exec neo4j neo4j-admin database dump neo4j --to-path=/backups/

# Manual
neo4j-admin database dump neo4j --to-path=/backups/
```

## Security Considerations

1. **Change default Neo4j password** in production
2. **Use environment variables** for sensitive data
3. **Restrict Neo4j ports** to localhost if not needed externally
4. **Use firewall rules** to protect server
5. **Keep dependencies updated**: `pip install --upgrade -r requirements.txt`
6. **Monitor logs** for suspicious activity

## Performance Tuning

### Neo4j Memory

Edit `docker-compose.yml` or Neo4j config:
```yaml
environment:
  - NEO4J_dbms_memory_heap_max__size=2G
```

### Bot Rate Limiting

Adjust in `src/bot/rate_limiter.py` if needed.

## Support

For issues, check:
- Logs: `docker-compose logs` or `journalctl -u graphrag-bot`
- Health endpoint: `/health` command in Telegram
- Neo4j browser: `http://your-server:7474`
