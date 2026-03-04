"""
Ingest a single document (in-memory) into Neo4j.
Used by Telegram bot file upload and programmatic ingestion.
"""
from typing import Dict, List, Any
from src.data.neo4j_client import get_neo4j_graph
from src.data.ingestion import validate_json_structure
from src.core.logging_config import get_logger

logger = get_logger(__name__)


def ingest_single_document(metadata: Dict[str, Any], graph_data: List[Dict[str, Any]]) -> None:
    """
    Ingest a single document's metadata and graph_data into Neo4j.

    Args:
        metadata: Must include 'file_name'. May include document_title, reg_number, date_signed, authority.
        graph_data: List of chunks, each with chunk_id, original_text, section, chapter, nodes, relationships.

    Raises:
        ValueError: If validation fails.
    """
    payload = {"metadata": metadata, "graph_data": graph_data}
    is_valid, error_message = validate_json_structure(payload)
    if not is_valid:
        raise ValueError(error_message)

    graph = get_neo4j_graph()
    file_name = metadata.get("file_name")

    # Create Document Node
    doc_cypher = """
    MERGE (d:Document {file_name: $file_name})
    SET d.title = $title,
        d.reg_number = $reg_number,
        d.date_signed = $date_signed,
        d.authority = $authority
    """
    graph.query(doc_cypher, {
        "file_name": file_name,
        "title": metadata.get("document_title"),
        "reg_number": metadata.get("reg_number"),
        "date_signed": metadata.get("date_signed"),
        "authority": metadata.get("authority"),
    })

    for chunk in graph_data:
        chunk_id = chunk.get("chunk_id")
        original_text = chunk.get("original_text")
        section = chunk.get("section", "")
        chapter = chunk.get("chapter", "")

        chunk_cypher = """
        MERGE (c:Chunk {id: $chunk_id})
        SET c.text = $text,
            c.document_file = $file_name,
            c.section = $section,
            c.chapter = $chapter
        WITH c
        MATCH (d:Document {file_name: $file_name})
        MERGE (d)-[:CONTAINS]->(c)
        """
        graph.query(chunk_cypher, {
            "chunk_id": f"{file_name}_{chunk_id}",
            "text": original_text,
            "file_name": file_name,
            "section": section,
            "chapter": chapter,
        })

        for node in chunk.get("nodes", []):
            node_id = node.get("id")
            node_type = node.get("type", "Entity")
            properties = node.get("properties", {})
            safe_label = "".join(filter(str.isalnum, node_type)) or "Entity"

            node_cypher = f"MERGE (n:{safe_label} {{id: $id}}) SET n += $props"
            graph.query(node_cypher, {"id": node_id, "props": properties})

            link_cypher = f"""
            MATCH (c:Chunk {{id: $chunk_id}})
            MATCH (n:{safe_label} {{id: $node_id}})
            MERGE (c)-[:MENTIONS]->(n)
            """
            graph.query(link_cypher, {
                "chunk_id": f"{file_name}_{chunk_id}",
                "node_id": node_id,
            })

        for rel in chunk.get("relationships", []):
            source_id = rel.get("source")
            target_id = rel.get("target")
            rel_type = rel.get("type", "RELATED_TO")
            safe_rel_type = "".join(filter(lambda x: x.isalnum() or x == "_", rel_type)).upper() or "RELATED_TO"

            rel_cypher = f"""
            MATCH (a {{id: $source_id}}), (b {{id: $target_id}})
            MERGE (a)-[r:{safe_rel_type}]->(b)
            """
            graph.query(rel_cypher, {"source_id": source_id, "target_id": target_id})

    logger.info("ingest_single_complete", file_name=file_name, chunks=len(graph_data))
    graph.refresh_schema()
