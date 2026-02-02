import json
import os
import glob
from src.data.neo4j_client import get_neo4j_graph

def ingest_json_data(json_dir: str):
    """
    Ingests graph data from JSON files into Neo4j.
    """
    graph = get_neo4j_graph()
    
    # Get all json files
    json_files = glob.glob(os.path.join(json_dir, "*.json"))
    
    print(f"Found {len(json_files)} JSON files in {json_dir}")

    for file_path in json_files:
        print(f"Processing {file_path}...")
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                data = json.load(f)
            
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
                    
        except Exception as e:
            print(f"Error processing {file_path}: {e}")
    
    print("Ingestion complete. Refreshing schema...")
    graph.refresh_schema()
    print("Schema refreshed.")

if __name__ == "__main__":
    base_path = os.path.dirname(os.path.abspath(__file__))
    json_source_dir = os.path.join(base_path, "source", "Json")
    ingest_json_data(json_source_dir)
