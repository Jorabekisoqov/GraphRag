#!/bin/bash

# GraphRAG Deployment Script

set -e  # Exit correctly on error

echo "========================================"
echo "   GraphRAG Server Deployment Helper"
echo "========================================"

# 1. Check Python Version
PYTHON_CMD=""

if command -v python3.10 &> /dev/null; then
    PYTHON_CMD="python3.10"
elif command -v python3 &> /dev/null; then
    PYTHON_CMD="python3"
else
    echo "Error: python3 could not be found."
    exit 1
fi

PYTHON_VERSION=$($PYTHON_CMD -c 'import sys; print(f"{sys.version_info.major}.{sys.version_info.minor}")')
REQUIRED_MAJOR=3
REQUIRED_MINOR=10

# Check version using python itself to avoid strict dependency on bc or shell math quirks
IS_COMPATIBLE=$($PYTHON_CMD -c "import sys; print(int(sys.version_info >= ($REQUIRED_MAJOR, $REQUIRED_MINOR)))")

if [ "$IS_COMPATIBLE" -ne 1 ]; then
    echo "Error: Python $REQUIRED_MAJOR.$REQUIRED_MINOR or higher is required. Found $PYTHON_VERSION"
    echo "Please run 'sudo ./install_python.sh' to install Python 3.10."
    exit 1
fi

echo "[✓] Using $PYTHON_CMD ($PYTHON_VERSION)"

# 2. Setup Virtual Environment
if [ ! -d ".venv" ]; then
    echo "Creating virtual environment..."
    $PYTHON_CMD -m venv .venv
else
    echo "[✓] Virtual environment (.venv) already exists."
fi

# 3. Activate and Install Dependencies
echo "Activating virtual environment and installing dependencies..."
source .venv/bin/activate
pip install --upgrade pip
pip install -r requirements.txt -c constraints-langchain.txt

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
        $PYTHON_CMD -m src.data.ingestion
        ;;
    2)
        echo "Starting Telegram bot..."
        $PYTHON_CMD -m src.bot.telegram_bot
        ;;
    3)
        echo "Exiting. You can run commands manually using 'source .venv/bin/activate'."
        ;;
    *)
        echo "Invalid choice."
        ;;
esac
