#!/bin/bash

# Quick Server Deployment Script for GraphRAG
# Usage: ./server-deploy.sh [docker|manual]

set -e

DEPLOYMENT_TYPE=${1:-docker}

echo "========================================"
echo "   GraphRAG Server Deployment"
echo "========================================"
echo "Deployment type: $DEPLOYMENT_TYPE"
echo ""

if [ "$DEPLOYMENT_TYPE" = "docker" ]; then
    echo "=== Docker Deployment ==="
    
    # Check Docker
    if ! command -v docker &> /dev/null; then
        echo "Error: Docker is not installed."
        echo "Install with: sudo apt-get install docker.io docker-compose"
        exit 1
    fi
    
    # Check .env file
    if [ ! -f ".env" ]; then
        echo "Error: .env file not found!"
        echo "Please create .env file with your credentials."
        echo "See .env.example for reference."
        exit 1
    fi
    
    echo "[✓] Docker found"
    echo "[✓] .env file found"
    
    # Build and start
    echo ""
    echo "Building and starting containers..."
    docker-compose up -d --build
    
    echo ""
    echo "Waiting for Neo4j to be ready..."
    sleep 10
    
    echo ""
    echo "=== Deployment Complete ==="
    echo ""
    echo "Next steps:"
    echo "1. Ingest data: docker-compose exec graphrag-app python3 -m src.data.ingestion"
    echo "2. Check logs: docker-compose logs -f graphrag-app"
    echo "3. Check status: docker-compose ps"
    echo ""
    echo "Neo4j browser: http://localhost:7474"
    
elif [ "$DEPLOYMENT_TYPE" = "manual" ]; then
    echo "=== Manual Deployment ==="
    
    # Run the existing deploy script
    ./deploy.sh
    
else
    echo "Error: Invalid deployment type. Use 'docker' or 'manual'"
    echo "Usage: ./server-deploy.sh [docker|manual]"
    exit 1
fi
