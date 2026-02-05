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
        echo "Install Docker and Docker Compose plugin"
        exit 1
    fi
    
    # Detect docker compose command (v2 plugin or v1 standalone)
    if docker compose version &> /dev/null; then
        DOCKER_COMPOSE_CMD="docker compose"
    elif command -v docker-compose &> /dev/null; then
        DOCKER_COMPOSE_CMD="docker-compose"
    else
        echo "Error: Docker Compose is not installed."
        echo "Install Docker Compose plugin: docker compose version"
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
    echo "[✓] Using: $DOCKER_COMPOSE_CMD"
    
    # Build and start
    echo ""
    echo "Building and starting containers..."
    $DOCKER_COMPOSE_CMD up -d --build
    
    echo ""
    echo "Waiting for Neo4j to be ready..."
    sleep 10
    
    echo ""
    echo "=== Deployment Complete ==="
    echo ""
    echo "Next steps:"
    echo "1. Ingest data: $DOCKER_COMPOSE_CMD exec graphrag-app python3 -m src.data.ingestion"
    echo "2. Check logs: $DOCKER_COMPOSE_CMD logs -f graphrag-app"
    echo "3. Check status: $DOCKER_COMPOSE_CMD ps"
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
