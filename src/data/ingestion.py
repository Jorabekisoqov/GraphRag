import json
import os
import glob
from typing import Dict, List, Any
from src.data.neo4j_client import get_neo4j_graph
from src.core.logging_config import get_logger

logger = get_logger(__name__)

def validate_json_structure(data: Dict[str, Any]) -> tuple[bool, str]:
    """
    Validates the structure of JSON data for ingestion.
    
    Args:
        data: The JSON data dictionary to validate.
        
    Returns:
        Tuple of (is_valid, error_message). If valid, error_message is empty.
    """
    if not isinstance(data, dict):
        return False, "Data must be a dictionary."
    
    # Check for required top-level keys
    if "metadata" not in data:
        return False, "Missing required 'metadata' field."
    
    if "graph_data" not in data:
        return False, "Missing required 'graph_data' field."
    
    metadata = data.get("metadata", {})
    if not isinstance(metadata, dict):
        return False, "Metadata must be a dictionary."
    
    # Check required metadata fields
    required_metadata_fields = ["file_name"]
    for field in required_metadata_fields:
        if field not in metadata:
            return False, f"Missing required metadata field: {field}"
    
    graph_data = data.get("graph_data", [])
    if not isinstance(graph_data, list):
        return False, "graph_data must be a list."
    
    # Validate each chunk in graph_data
    for idx, chunk in enumerate(graph_data):
        if not isinstance(chunk, dict):
            return False, f"Chunk at index {idx} must be a dictionary."
        
        if "chunk_id" not in chunk:
            return False, f"Chunk at index {idx} missing 'chunk_id' field."
        
        # Validate nodes
        if "nodes" in chunk:
            if not isinstance(chunk["nodes"], list):
                return False, f"Chunk at index {idx}: 'nodes' must be a list."
            for node_idx, node in enumerate(chunk["nodes"]):
                if not isinstance(node, dict):
                    return False, f"Chunk {idx}, node {node_idx}: must be a dictionary."
                if "id" not in node:
                    return False, f"Chunk {idx}, node {node_idx}: missing 'id' field."
        
        # Validate relationships
        if "relationships" in chunk:
            if not isinstance(chunk["relationships"], list):
                return False, f"Chunk at index {idx}: 'relationships' must be a list."
            for rel_idx, rel in enumerate(chunk["relationships"]):
                if not isinstance(rel, dict):
                    return False, f"Chunk {idx}, relationship {rel_idx}: must be a dictionary."
                if "source" not in rel or "target" not in rel:
                    return False, f"Chunk {idx}, relationship {rel_idx}: missing 'source' or 'target' field."
    
    return True, ""

def ingest_json_data(json_dir: str) -> None:
    """
    Ingests graph data from JSON files into Neo4j.
    
    Args:
        json_dir: Directory path containing JSON files to ingest.
        
    Raises:
        ValueError: If json_dir is invalid or data validation fails.
    """
    if not os.path.isdir(json_dir):
        raise ValueError(f"Invalid directory: {json_dir}")
    
    graph = get_neo4j_graph()
    
    # Get all json files
    json_files = glob.glob(os.path.join(json_dir, "*.json"))
    
    logger.info(f"Found {len(json_files)} JSON files in {json_dir}")

    for file_path in json_files:
        logger.info(f"Processing {file_path}...")
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                data = json.load(f)
            
            # Validate JSON structure
            is_valid, error_message = validate_json_structure(data)
            if not is_valid:
                logger.error("json_validation_failed", file=file_path, error=error_message)
                continue
            
            metadata = data.get("metadata", {})
            graph_data = data.get("graph_data", [])
            
            # Create Document Node
            doc_cypher = """
            MERGE (d:Document {file_name: $file_name})
            SET d.title = $title,
                d.reg_number = $reg_number,
                d.date_signed = $date_signed,
                d.authority = $authority
            """
            graph.query(doc_cypher, {
                "file_name": metadata.get("file_name"),
                "title": metadata.get("document_title"),
                "reg_number": metadata.get("reg_number"),
                "date_signed": metadata.get("date_signed"),
                "authority": metadata.get("authority")
            })

            for chunk in graph_data:
                chunk_id = chunk.get("chunk_id")
                original_text = chunk.get("original_text")
                
                # Create Chunk Node (optional, but good for grounding)
                chunk_cypher = """
                MERGE (c:Chunk {id: $chunk_id})
                SET c.text = $text,
                    c.document_file = $file_name
                WITH c
                MATCH (d:Document {file_name: $file_name})
                MERGE (d)-[:CONTAINS]->(c)
                """
                graph.query(chunk_cypher, {
                    "chunk_id": f"{metadata.get('file_name')}_{chunk_id}",
                    "text": original_text,
                    "file_name": metadata.get("file_name")
                })
                
                # Create Nodes
                for node in chunk.get("nodes", []):
                    node_id = node.get("id")
                    node_type = node.get("type", "Entity")
                    properties = node.get("properties", {})
                    
                    # Dynamic label creation isn't directly supported in parameterized queries easily without APOC or string formatting.
                    # For safety, we limit label characters or sanitise.
                    # Assuming node_type is safe (alphanumeric).
                    safe_label = "".join(filter(str.isalnum, node_type))
                    if not safe_label: safe_label = "Entity"

                    # Construct Cypher for Node
                    # We use MERGE on 'id' property.
                    node_cypher = f"""
                    MERGE (n:{safe_label} {{id: $id}})
                    SET n += $props
                    """
                    graph.query(node_cypher, {"id": node_id, "props": properties})
                    
                    # Link Node to Chunk (MENTIONS)
                    link_cypher = f"""
                    MATCH (c:Chunk {{id: $chunk_id}})
                    MATCH (n:{safe_label} {{id: $node_id}})
                    MERGE (c)-[:MENTIONS]->(n)
                    """
                    graph.query(link_cypher, {
                        "chunk_id": f"{metadata.get('file_name')}_{chunk_id}",
                        "node_id": node_id
                    })

                # Create Relationships
                for rel in chunk.get("relationships", []):
                    source_id = rel.get("source")
                    target_id = rel.get("target")
                    rel_type = rel.get("type", "RELATED_TO")
                    
                    # Sanitize Rel Type
                    safe_rel_type = "".join(filter(lambda x: x.isalnum() or x == '_', rel_type)).upper()
                    if not safe_rel_type: safe_rel_type = "RELATED_TO"

                    # We don't know the exact labels of source/target here efficiently without querying or multiple passes.
                    # But Cypher can match by ID if ID is unique across labels or if we rely on the id property index.
                    # Assuming 'id' is unique for the entities in this context. 
                    # A more robust way is to Match (a), (b) WHERE a.id = $s AND b.id = $t
                    
                    rel_cypher = f"""
                    MATCH (a {{id: $source_id}}), (b {{id: $target_id}})
                    MERGE (a)-[r:{safe_rel_type}]->(b)
                    """
                    graph.query(rel_cypher, {"source_id": source_id, "target_id": target_id})
                    
        except json.JSONDecodeError as e:
            logger.error("invalid_json", file=file_path, error=str(e))
        except Exception as e:
            logger.error("ingestion_error", file=file_path, error=str(e), exc_info=True)
    
    logger.info("ingestion_complete")
    graph.refresh_schema()
    logger.info("schema_refreshed")

if __name__ == "__main__":
    base_path = os.path.dirname(os.path.abspath(__file__))
    json_source_dir = os.path.join(base_path, "source", "Json")
    ingest_json_data(json_source_dir)
