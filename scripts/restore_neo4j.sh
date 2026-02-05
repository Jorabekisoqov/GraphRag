#!/bin/bash

# Neo4j Restore Script
# This script restores Neo4j data from a backup file

set -e

# Configuration
BACKUP_FILE="${1:-}"

if [ -z "$BACKUP_FILE" ]; then
    echo "Usage: $0 <backup_file.cypher>"
    echo ""
    echo "Available backups:"
    ls -lh ./backups/*.cypher 2>/dev/null || echo "No backups found"
    exit 1
fi

if [ ! -f "$BACKUP_FILE" ]; then
    echo "Error: Backup file not found: $BACKUP_FILE"
    exit 1
fi

# Load environment variables
if [ -f .env ]; then
    export $(cat .env | grep -v '^#' | xargs)
fi

echo "Restoring Neo4j from: $BACKUP_FILE"
echo ""
echo "WARNING: This will overwrite existing data!"
read -p "Are you sure? (yes/no): " confirm

if [ "$confirm" != "yes" ]; then
    echo "Restore cancelled."
    exit 0
fi

# Check if Neo4j URI is set
if [ -z "$NEO4J_URI" ] || [ -z "$NEO4J_USERNAME" ] || [ -z "$NEO4J_PASSWORD" ]; then
    echo "Error: Neo4j credentials not found in environment variables."
    exit 1
fi

echo "Restoring data..."
echo ""
echo "Note: For production restores, use:"
echo "  docker exec -i graphrag-neo4j neo4j-admin database load neo4j --from-path=/backups/backup.dump --overwrite-destination=true"
echo ""
echo "This script provides a basic structure. Full restore requires neo4j-admin."
