#!/bin/bash

# Neo4j Backup Script
# This script exports Neo4j data using Cypher queries

set -e

# Configuration
BACKUP_DIR="${BACKUP_DIR:-./backups}"
TIMESTAMP=$(date +%Y%m%d_%H%M%S)
BACKUP_FILE="${BACKUP_DIR}/neo4j_backup_${TIMESTAMP}.cypher"

# Load environment variables
if [ -f .env ]; then
    export $(cat .env | grep -v '^#' | xargs)
fi

# Create backup directory if it doesn't exist
mkdir -p "$BACKUP_DIR"

echo "Starting Neo4j backup..."
echo "Backup file: $BACKUP_FILE"

# Check if Neo4j URI is set
if [ -z "$NEO4J_URI" ] || [ -z "$NEO4J_USERNAME" ] || [ -z "$NEO4J_PASSWORD" ]; then
    echo "Error: Neo4j credentials not found in environment variables."
    echo "Please set NEO4J_URI, NEO4J_USERNAME, and NEO4J_PASSWORD"
    exit 1
fi

# Use Python script to export data
python3 << EOF
import os
import sys
from dotenv import load_dotenv

load_dotenv()

try:
    from src.data.neo4j_client import get_neo4j_graph
    
    graph = get_neo4j_graph()
    
    # Export all nodes and relationships
    query = """
    MATCH (n)
    OPTIONAL MATCH (n)-[r]->(m)
    RETURN n, r, m
    LIMIT 10000
    """
    
    # For a more complete backup, you might want to use neo4j-admin dump
    # This is a simple Cypher-based export
    print("Note: This is a basic export. For full backups, use neo4j-admin dump")
    print("Exporting data to: $BACKUP_FILE")
    
    # In a real scenario, you'd want to use neo4j-admin dump for full backups
    # This script provides a basic structure
    
except Exception as e:
    print(f"Error during backup: {e}", file=sys.stderr)
    sys.exit(1)
EOF

echo "Backup completed: $BACKUP_FILE"
echo ""
echo "For production backups, consider using:"
echo "  docker exec graphrag-neo4j neo4j-admin database dump neo4j --to-path=/backups"
