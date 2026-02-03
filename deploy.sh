#!/bin/bash

# GraphRAG Deployment Script

set -e  # Exit correctly on error

echo "========================================"
echo "   GraphRAG Server Deployment Helper"
echo "========================================"

# 1. Check Python Version
if ! command -v python3 &> /dev/null; then
    echo "Error: python3 could not be found."
    exit 1
fi

PYTHON_VERSION=$(python3 -c 'import sys; print(f"{sys.version_info.major}.{sys.version_info.minor}")')
REQUIRED_VERSION="3.10"

if (( $(echo "$PYTHON_VERSION < $REQUIRED_VERSION" | bc -l) )); then
    echo "Error: Python $REQUIRED_VERSION or higher is required. Found $PYTHON_VERSION"
    exit 1
fi

echo "[✓] Python $PYTHON_VERSION detected."

# 2. Setup Virtual Environment
if [ ! -d ".venv" ]; then
    echo "Creating virtual environment..."
    python3 -m venv .venv
else
    echo "[✓] Virtual environment (.venv) already exists."
fi

# 3. Activate and Install Dependencies
echo "Activating virtual environment and installing dependencies..."
source .venv/bin/activate
pip install --upgrade pip
pip install -r requirements.txt

echo "[✓] Dependencies installed."

# 4. Check for .env file
if [ ! -f ".env" ]; then
    echo "----------------------------------------------------------------"
    echo "WARNING: .env file not found!"
    echo "You need to create a .env file with your API keys and Neo4j credentials."
    echo "Example content:"
    echo "OPENAI_API_KEY=..."
    echo "NEO4J_URI=..."
    echo "NEO4J_USERNAME=..."
    echo "NEO4J_PASSWORD=..."
    echo "TELEGRAM_BOT_TOKEN=..."
    echo "----------------------------------------------------------------"
    read -p "Press Enter once you have created the .env file (or Ctrl+C to exit)..."
else
    echo "[✓] .env file found."
fi

echo "========================================"
echo "Deployment Setup Complete!"
echo "========================================"
echo ""
echo "What would you like to do?"
echo "1) Run Data Ingestion (python -m src.data.ingestion)"
echo "2) Start Telegram Bot (python -m src.bot.telegram_bot)"
echo "3) Exit"
echo ""
read -p "Enter your choice [1-3]: " choice

case $choice in
    1)
        echo "Starting ingestion..."
        python3 -m src.data.ingestion
        ;;
    2)
        echo "Starting Telegram bot..."
        python3 -m src.bot.telegram_bot
        ;;
    3)
        echo "Exiting. You can run commands manually using 'source .venv/bin/activate'."
        ;;
    *)
        echo "Invalid choice."
        ;;
esac
