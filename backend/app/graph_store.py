"""
graph_store.py
--------------
Neo4j knowledge graph layer for the Industrial Intelligence Platform.

Graph Schema:
  (:Equipment  {id, name, type, location, health_score, risk_level, criticality})
  (:Component  {name, type})
  (:Failure    {type, date, description, confidence})
  (:Cause      {description, confidence})
  (:Action     {description, priority})
  (:Technician {name})
  (:Regulation {code})
  (:Document   {name, version, upload_date, page_count})
  (:Chunk      {chunk_id, page, source})   -- links Neo4j → ChromaDB

Relationships:
  Equipment  -[:HAS_COMPONENT]->  Component
  Equipment  -[:EXPERIENCED]->    Failure
  Failure    -[:CAUSED_BY]->      Cause
  Failure    -[:FIXED_BY]->       Action
  Failure    -[:INSPECTED_BY]->   Technician
  Failure    -[:REFERENCES]->     Regulation
  Failure    -[:SOURCED_FROM]->   Document
  Failure    -[:ON_DATE {date}]->  (uses date property directly)
  Failure    -[:SIMILAR_TO {score}]-> Failure   (embedding-based similarity)
  Document   -[:HAS_CHUNK]->      Chunk
  Chunk      -[:MENTIONS]->       Equipment
"""

import logging
from datetime import datetime, timezone
from typing import List, Dict, Any, Optional

logger = logging.getLogger(__name__)

import re

def normalize_id(raw_id: str) -> str:
    if not raw_id:
        return ""
    val = raw_id.upper().replace("-", "")
    wo_m = re.match(r'WO(\d{4})(\d{3,5})', val)
    if wo_m:
        return f"WO-{wo_m.group(1)}-{wo_m.group(2)}"
    code_m = re.match(r'([A-Z]{2,4})(\d{2,4})', val)
    if code_m:
        return f"{code_m.group(1)}-{code_m.group(2)}"
    return raw_id.upper()

def normalize_entity_name(val: str) -> str:
    if not val:
        return ""
    # Trim whitespace, remove excessive punctuation, lowercase
    val = val.strip().strip(".,:-").strip()
    val = re.sub(r'\s+', ' ', val)
    return val.lower()

def build_neighborhood_from_entities(entities_list: list, target_id: str) -> Dict[str, Any]:
    target_id = target_id.upper()
    
    # Filter entities matching target_id
    matching_entities = []
    for ent in entities_list:
        eq = (ent.get("equipment_id") or "").upper()
        wo = (ent.get("work_order_id") or "").upper()
        if target_id in (eq, wo):
            matching_entities.append(ent)
            
    nodes = []
    edges = []
    seen_nodes = set()
    seen_edges = set()
    
    def add_node(label: str, node_id: str, properties: dict):
        if not node_id:
            return
        key = f"{label}:{node_id}"
        if key not in seen_nodes:
            seen_nodes.add(key)
            nodes.append({
                "label": label,
                "id": node_id,
                **properties
            })
            
    def add_edge(source: str, target: str, rel_type: str):
        if not source or not target:
            return
        key = f"{source}->{rel_type}->{target}"
        if key not in seen_edges:
            seen_edges.add(key)
            edges.append({
                "source": source,
                "target": target,
                "type": rel_type
            })
            
    for ent in matching_entities:
        raw_eq = ent.get("equipment_id") or ""
        raw_wo = ent.get("work_order_id") or ""
        eq_id = normalize_id(raw_eq) if raw_eq else ""
        wo_id = normalize_id(raw_wo) if raw_wo else ""
        
        # If eq_id is actually a Work Order ID, swap them
        if eq_id.startswith("WO-") and not wo_id:
            wo_id = eq_id
            eq_id = ""
            
        comp_name = normalize_entity_name(ent.get("component_name") or "")
        failure_type = normalize_entity_name(ent.get("failure_type") or "")
        technician = normalize_entity_name(ent.get("technician") or "")
        action = normalize_entity_name(ent.get("maintenance_action") or "")
        location = normalize_entity_name(ent.get("location") or "")
        doc_name = ent.get("documents", ["Document.pdf"])[0] if ent.get("documents") else "Document.pdf"
        
        # 1. Equipment Node
        if eq_id:
            add_node("Equipment", eq_id, {"name": eq_id, "location": location})
            
        # 2. WorkOrder Node
        if wo_id:
            add_node("WorkOrder", wo_id, {"name": wo_id, "date": ent.get("inspection_date", "")})
            if eq_id:
                add_edge(eq_id, wo_id, "BELONGS_TO_WORK_ORDER")
                
        # 3. Component Node
        if eq_id and comp_name:
            add_node("Component", comp_name, {"name": comp_name})
            add_edge(eq_id, comp_name, "HAS_COMPONENT")
            
        # 4. Failure Node
        if failure_type:
            add_node("Failure", failure_type, {"name": failure_type})
            if comp_name:
                add_edge(comp_name, failure_type, "HAS_FAILURE")
            elif eq_id:
                add_edge(eq_id, failure_type, "HAS_FAILURE")
                
        # 5. Action Node
        if failure_type and action:
            add_node("Action", action, {"description": action})
            add_edge(failure_type, action, "RECOMMENDED_ACTION")
            
        # 6. Technician Node
        if action and technician:
            add_node("Technician", technician, {"name": technician})
            add_edge(action, technician, "PERFORMED_BY")
            
        # 7. Document Node
        if failure_type and doc_name:
            add_node("Document", doc_name, {"name": doc_name})
            add_edge(failure_type, doc_name, "SOURCE_DOCUMENT")
            
        # 8. Failure -> WorkOrder link
        if failure_type and wo_id:
            add_edge(failure_type, wo_id, "BELONGS_TO_WORK_ORDER")
            
    return {
        "nodes": nodes,
        "edges": edges,
        "equipment_id": target_id,
        "graph_available": True
    }

NEO4J_AVAILABLE = False
try:
    from neo4j import GraphDatabase, exceptions as neo4j_exceptions
    NEO4J_AVAILABLE = True
except ImportError:
    logger.warning("neo4j Python driver not installed. Graph features will be disabled. "
                   "Install with: pip install neo4j")


class GraphStore:
    """
    Singleton-safe Neo4j interface.
    All public methods degrade gracefully when Neo4j is unavailable
    (NEO4J_AVAILABLE=False) or disabled via config (NEO4J_ENABLED=False).
    """

    def __init__(self, settings):
        self.enabled = getattr(settings, "NEO4J_ENABLED", False)
        self.driver = None
        self._connected = False

        if not self.enabled:
            logger.info("Neo4j is disabled via NEO4J_ENABLED=False. Graph features inactive.")
            return

        if not NEO4J_AVAILABLE:
            logger.warning("neo4j driver not installed. Graph features inactive.")
            return

        try:
            self.driver = GraphDatabase.driver(
                settings.NEO4J_URI,
                auth=(settings.NEO4J_USERNAME, settings.NEO4J_PASSWORD)
            )
            # Verify connectivity
            self.driver.verify_connectivity()
            self._connected = True
            logger.info(f"Neo4j connected at {settings.NEO4J_URI}")
            self._ensure_constraints()
        except Exception as e:
            logger.error(f"Neo4j connection failed: {e}. Graph features disabled.")
            self.driver = None
            self._connected = False

    # ------------------------------------------------------------------
    # Schema Setup
    # ------------------------------------------------------------------

    def _ensure_constraints(self):
        """Creates uniqueness constraints and indexes on first startup."""
        if not self._connected:
            return
        constraints = [
            "CREATE CONSTRAINT IF NOT EXISTS FOR (e:Equipment) REQUIRE e.id IS UNIQUE",
            "CREATE CONSTRAINT IF NOT EXISTS FOR (d:Document) REQUIRE (d.name, d.version) IS UNIQUE",
            "CREATE CONSTRAINT IF NOT EXISTS FOR (r:Regulation) REQUIRE r.code IS UNIQUE",
            "CREATE CONSTRAINT IF NOT EXISTS FOR (c:Chunk) REQUIRE c.chunk_id IS UNIQUE",
            "CREATE INDEX IF NOT EXISTS FOR (f:Failure) ON (f.type)",
            "CREATE INDEX IF NOT EXISTS FOR (e:Equipment) ON (e.health_score)",
        ]
        with self.driver.session() as session:
            for cypher in constraints:
                try:
                    session.run(cypher)
                except Exception as e:
                    logger.warning(f"Constraint/index creation warning: {e}")
        logger.info("Neo4j schema constraints and indexes ensured.")

    # ------------------------------------------------------------------
    # Ingestion: Upsert Entities (whole-document, not per-page)
    # ------------------------------------------------------------------

    def upsert_entities(
        self,
        entities: List[Dict[str, Any]],
        doc_name: str,
        doc_version: str = "1.0",
        page_count: int = 0,
        chunk_ids: Optional[List[str]] = None,
    ) -> int:
        """
        Merges a list of extracted IndustrialEntity dicts into the graph.
        Entities are normalized, deduplicated, and mapped via MERGE for scalability.
        """
        # Always cache to local mock DB for offline usage
        try:
            import os
            import json
            db_path = os.path.join(os.path.dirname(__file__), "mock_graph_db.json")
            db_data = {}
            if os.path.exists(db_path):
                with open(db_path, "r", encoding="utf-8") as f:
                    db_data = json.load(f)
            
            for entity in entities:
                eq_id = normalize_id(entity.get("equipment_id") or "")
                if not eq_id:
                    continue
                if eq_id not in db_data:
                    db_data[eq_id] = {
                        "equipment_id": eq_id,
                        "location": normalize_entity_name(entity.get("location") or "utility block a"),
                        "manufacturer": normalize_entity_name(entity.get("manufacturer") or "sulzer pumps"),
                        "entities": []
                    }
                
                entry = db_data[eq_id]
                if entity.get("location"):
                    entry["location"] = normalize_entity_name(entity.get("location"))
                if entity.get("manufacturer"):
                    entry["manufacturer"] = normalize_entity_name(entity.get("manufacturer"))
                
                norm_ent = {
                    "equipment_id": eq_id,
                    "work_order_id": normalize_id(entity.get("work_order_id") or ""),
                    "component_name": normalize_entity_name(entity.get("component_name") or ""),
                    "failure_type": normalize_entity_name(entity.get("failure_type") or ""),
                    "technician": normalize_entity_name(entity.get("technician") or ""),
                    "inspection_date": entity.get("inspection_date") or "",
                    "maintenance_action": normalize_entity_name(entity.get("maintenance_action") or ""),
                    "regulatory_references": [r.strip() for r in entity.get("regulatory_references", []) if r.strip()],
                    "location": normalize_entity_name(entity.get("location") or ""),
                    "cause": normalize_entity_name(entity.get("cause") or ""),
                    "recommendation": normalize_entity_name(entity.get("recommendation") or ""),
                    "manufacturer": normalize_entity_name(entity.get("manufacturer") or ""),
                    "documents": [doc_name]
                }
                
                duplicate_found = False
                for existing in entry.setdefault("entities", []):
                    if (existing.get("component_name") == norm_ent["component_name"] and
                        existing.get("failure_type") == norm_ent["failure_type"] and
                        existing.get("work_order_id") == norm_ent["work_order_id"] and
                        existing.get("maintenance_action") == norm_ent["maintenance_action"]):
                        duplicate_found = True
                        if doc_name not in existing.setdefault("documents", []):
                            existing["documents"].append(doc_name)
                        break
                if not duplicate_found:
                    entry["entities"].append(norm_ent)
            
            with open(db_path, "w", encoding="utf-8") as f:
                json.dump(db_data, f, indent=2)
        except Exception as e:
            logger.error(f"Failed to save local mock graph: {e}")

        if not self._connected:
            return len(entities)

        upload_ts = datetime.now(timezone.utc).isoformat()
        upserted = 0

        with self.driver.session() as session:
            # 1. Upsert Document node (versioned)
            session.run(
                """
                MERGE (d:Document {name: $name})
                ON CREATE SET d.upload_date = $upload_date, d.page_count = $page_count, d.version = $version
                ON MATCH  SET d.upload_date = $upload_date, d.page_count = $page_count, d.version = $version
                """,
                name=doc_name, version=doc_version,
                upload_date=upload_ts, page_count=page_count
            )

            # 2. Upsert ChromaDB Chunk bridge nodes
            if chunk_ids:
                for cid in chunk_ids:
                    try:
                        parts = cid.split("_p")
                        page_part = int(parts[1].split("_")[0]) if len(parts) > 1 else 0
                    except Exception:
                        page_part = 0
                    session.run(
                        """
                        MERGE (ch:Chunk {chunk_id: $cid})
                        ON CREATE SET ch.source = $source, ch.page = $page
                        WITH ch
                        MATCH (d:Document {name: $source})
                        MERGE (d)-[:HAS_CHUNK]->(ch)
                        """,
                        cid=cid, source=doc_name, page=page_part
                    )

            # 3. Upsert each entity
            for entity in entities:
                eq_id = normalize_id(entity.get("equipment_id") or "")
                if not eq_id:
                    continue

                wo_id = normalize_id(entity.get("work_order_id") or "")
                comp_name = normalize_entity_name(entity.get("component_name") or "")
                failure_type = normalize_entity_name(entity.get("failure_type") or "")
                action = normalize_entity_name(entity.get("maintenance_action") or "")
                technician = normalize_entity_name(entity.get("technician") or "")
                cause = normalize_entity_name(entity.get("cause") or "")
                recommendation = normalize_entity_name(entity.get("recommendation") or "")
                location = normalize_entity_name(entity.get("location") or "")
                manufacturer = normalize_entity_name(entity.get("manufacturer") or "")

                # Merge Equipment node
                session.run(
                    """
                    MERGE (e:Equipment {id: $eq_id})
                    ON CREATE SET e.name = $eq_id, e.health_score = 100.0, e.risk_level = 'LOW', e.criticality = 'MEDIUM'
                    """,
                    eq_id=eq_id
                )

                # Merge Location and connect Equipment
                if location:
                    session.run(
                        """
                        MERGE (l:Location {name: $location})
                        WITH l
                        MATCH (e:Equipment {id: $eq_id})
                        MERGE (e)-[:BELONGS_TO]->(l)
                        """,
                        location=location, eq_id=eq_id
                    )

                # Merge Manufacturer and connect Equipment
                if manufacturer:
                    session.run(
                        """
                        MERGE (m:Manufacturer {name: $manufacturer})
                        WITH m
                        MATCH (e:Equipment {id: $eq_id})
                        MERGE (e)-[:MANUFACTURED_BY]->(m)
                        """,
                        manufacturer=manufacturer, eq_id=eq_id
                    )

                # Merge WorkOrder and connect to Equipment
                if wo_id:
                    session.run(
                        """
                        MERGE (wo:WorkOrder {id: $wo_id})
                        ON CREATE SET wo.name = $wo_id
                        WITH wo
                        MATCH (e:Equipment {id: $eq_id})
                        MERGE (wo)-[:BELONGS_TO_WORK_ORDER]->(e)
                        """,
                        wo_id=wo_id, eq_id=eq_id
                    )

                # Merge Component and connect Equipment
                if comp_name:
                    session.run(
                        """
                        MERGE (c:Component {name: $comp_name})
                        WITH c
                        MATCH (e:Equipment {id: $eq_id})
                        MERGE (e)-[:HAS_COMPONENT]->(c)
                        """,
                        comp_name=comp_name, eq_id=eq_id
                    )

                # Merge Failure and connect relationships
                if failure_type:
                    session.run(
                        """
                        MERGE (f:Failure {name: $failure_type})
                        WITH f
                        MATCH (d:Document {name: $doc_name})
                        MERGE (f)-[:SOURCE_DOCUMENT]->(d)
                        """,
                        failure_type=failure_type, doc_name=doc_name
                    )

                    # Connect Failure to Component or Equipment
                    if comp_name:
                        session.run(
                            """
                            MATCH (c:Component {name: $comp_name})
                            MATCH (f:Failure {name: $failure_type})
                            MERGE (c)-[:HAS_FAILURE]->(f)
                            """,
                            comp_name=comp_name, failure_type=failure_type
                        )
                    else:
                        session.run(
                            """
                            MATCH (e:Equipment {id: $eq_id})
                            MATCH (f:Failure {name: $failure_type})
                            MERGE (e)-[:HAS_FAILURE]->(f)
                            """,
                            eq_id=eq_id, failure_type=failure_type
                        )

                    # Connect Failure to WorkOrder
                    if wo_id:
                        session.run(
                            """
                            MATCH (wo:WorkOrder {id: $wo_id})
                            MATCH (f:Failure {name: $failure_type})
                            MERGE (f)-[:BELONGS_TO_WORK_ORDER]->(wo)
                            """,
                            wo_id=wo_id, failure_type=failure_type
                        )

                    # Merge Cause and connect Failure
                    if cause:
                        session.run(
                            """
                            MERGE (ca:Cause {name: $cause})
                            WITH ca
                            MATCH (f:Failure {name: $failure_type})
                            MERGE (f)-[:CAUSED_BY]->(ca)
                            """,
                            cause=cause, failure_type=failure_type
                        )

                    # Merge Recommendation and connect Failure
                    if recommendation:
                        session.run(
                            """
                            MERGE (r:Recommendation {name: $recommendation})
                            WITH r
                            MATCH (f:Failure {name: $failure_type})
                            MERGE (f)-[:RECOMMENDED_ACTION]->(r)
                            """,
                            recommendation=recommendation, failure_type=failure_type
                        )

                    # Merge Action and connect Failure
                    if action:
                        session.run(
                            """
                            MERGE (a:Action {name: $action})
                            WITH a
                            MATCH (f:Failure {name: $failure_type})
                            MERGE (f)-[:RECOMMENDED_ACTION]->(a)
                            """,
                            action=action, failure_type=failure_type
                        )

                        # Connect Action to Technician
                        if technician:
                            session.run(
                                """
                                MERGE (t:Technician {name: $technician})
                                WITH t
                                MATCH (a:Action {name: $action})
                                MERGE (a)-[:PERFORMED_BY]->(t)
                                """,
                                technician=technician, action=action
                            )

                        # Connect Action to WorkOrder
                        if wo_id:
                            session.run(
                                """
                                MATCH (wo:WorkOrder {id: $wo_id})
                                MATCH (a:Action {name: $action})
                                MERGE (a)-[:BELONGS_TO_WORK_ORDER]->(wo)
                                """,
                                wo_id=wo_id, action=action
                            )

                    elif technician:
                        # Direct connection Failure -> Technician if no action
                        session.run(
                            """
                            MERGE (t:Technician {name: $technician})
                            WITH t
                            MATCH (f:Failure {name: $failure_type})
                            MERGE (f)-[:PERFORMED_BY]->(t)
                            """,
                            technician=technician, failure_type=failure_type
                        )

                # Re-calculate Equipment health score
                session.run(
                    """
                    MATCH (e:Equipment {id: $eq_id})
                    OPTIONAL MATCH (e)-[:HAS_FAILURE]->(f1:Failure)
                    OPTIONAL MATCH (e)-[:HAS_COMPONENT]->()-[:HAS_FAILURE]->(f2:Failure)
                    WITH e, count(f1) + count(f2) AS num_failures
                    SET e.health_score = CASE
                          WHEN 100.0 - (num_failures * 8.0) < 0 THEN 0.0
                          ELSE 100.0 - (num_failures * 8.0)
                        END,
                        e.risk_level = CASE
                          WHEN num_failures >= 5 THEN 'CRITICAL'
                          WHEN num_failures >= 3 THEN 'HIGH'
                          WHEN num_failures >= 1 THEN 'MEDIUM'
                          ELSE 'LOW'
                        END
                    """,
                    eq_id=eq_id
                )

                upserted += 1

        logger.info(f"Graph upsert complete: {upserted} entities from '{doc_name}' v{doc_version}")
        return upserted

    # ------------------------------------------------------------------
    # SIMILAR_TO edges (embedding-based, called post-ingest)
    # ------------------------------------------------------------------

    def build_similar_failure_edges(self, similarity_threshold: float = 0.75):
        """
        Creates SIMILAR_TO relationships between Failure nodes that share
        the same failure type string (as a lightweight heuristic).
        For full embedding-based similarity, call this with precomputed scores.
        """
        if not self._connected:
            return
        try:
            with self.driver.session() as session:
                # Heuristic: same failure type = similar (score 1.0)
                result = session.run(
                    """
                    MATCH (f1:Failure), (f2:Failure)
                    WHERE f1 <> f2
                      AND f1.type = f2.type
                      AND NOT (f1)-[:SIMILAR_TO]->(f2)
                    MERGE (f1)-[:SIMILAR_TO {score: 1.0, method: 'type_match'}]->(f2)
                    RETURN count(*) AS created
                    """
                )
                count = result.single()["created"]
                logger.info(f"SIMILAR_TO edges created/updated: {count}")
        except Exception as e:
            logger.error(f"Failed to build SIMILAR_TO edges: {e}")

    def upsert_similar_failure_edge(
        self,
        failure_id_a: str,
        failure_id_b: str,
        score: float
    ):
        """
        Explicitly creates/updates a SIMILAR_TO edge with an embedding score.
        Called when embedding-based similarity is computed externally.
        """
        if not self._connected:
            return
        try:
            with self.driver.session() as session:
                session.run(
                    """
                    MATCH (f1:Failure {id: $id_a}), (f2:Failure {id: $id_b})
                    MERGE (f1)-[r:SIMILAR_TO]->(f2)
                    SET r.score = $score, r.method = 'embedding'
                    """,
                    id_a=failure_id_a, id_b=failure_id_b, score=score
                )
        except Exception as e:
            logger.error(f"Failed to upsert SIMILAR_TO edge: {e}")

    # ------------------------------------------------------------------
    # Query: Graph Context for RCA Agent
    # ------------------------------------------------------------------

    def get_related_failures(
        self,
        equipment_id: Optional[str],
        component_name: Optional[str] = None,
        limit: int = 5
    ) -> List[Dict[str, Any]]:
        """
        Returns all historically recorded failures for a given equipment,
        including their causes, corrective actions, dates, and confidence scores.
        """
        if not self._connected or not equipment_id:
            return []
        try:
            with self.driver.session() as session:
                cypher = """
                MATCH (e:Equipment {id: $eq_id})-[:EXPERIENCED]->(f:Failure)
                OPTIONAL MATCH (f)-[:FIXED_BY]->(a:Action)
                OPTIONAL MATCH (f)-[:INSPECTED_BY]->(t:Technician)
                OPTIONAL MATCH (f)-[:SOURCED_FROM]->(d:Document)
                OPTIONAL MATCH (f)-[:LINKED_CHUNK]->(ch:Chunk)
                RETURN
                    f.type        AS failure_type,
                    f.date        AS date,
                    f.confidence  AS confidence,
                    f.source_doc  AS source_doc,
                    a.description AS action,
                    a.priority    AS priority,
                    t.name        AS technician,
                    d.name        AS document,
                    d.version     AS doc_version,
                    ch.chunk_id   AS chunk_id
                ORDER BY f.date DESC
                LIMIT $limit
                """
                result = session.run(cypher, eq_id=equipment_id.upper(), limit=limit)
                rows = []
                for record in result:
                    rows.append({
                        "failure_type": record["failure_type"],
                        "date": record["date"],
                        "confidence": record["confidence"],
                        "source_doc": record["source_doc"],
                        "action": record["action"],
                        "priority": record["priority"],
                        "technician": record["technician"],
                        "document": record["document"],
                        "doc_version": record["doc_version"],
                        "chunk_id": record["chunk_id"],  # ChromaDB bridge
                    })
                return rows
        except Exception as e:
            logger.error(f"get_related_failures failed: {e}")
            return []

    def get_causal_chain(
        self,
        failure_type: str,
        depth: int = 3
    ) -> List[Dict[str, Any]]:
        """
        Traverses SIMILAR_TO edges to find historically similar failures
        and their causal chain (depth-limited graph walk).
        """
        if not self._connected or not failure_type:
            return []
        try:
            with self.driver.session() as session:
                cypher = """
                MATCH path = (f:Failure {type: $failure_type})
                             -[:SIMILAR_TO*0..{depth}]->(f2:Failure)
                WHERE f2.confidence IS NOT NULL
                WITH f2, length(path) AS hops
                ORDER BY f2.confidence DESC, hops ASC
                LIMIT 10
                OPTIONAL MATCH (f2)-[:FIXED_BY]->(a:Action)
                RETURN
                    f2.type       AS failure_type,
                    f2.date       AS date,
                    f2.confidence AS confidence,
                    f2.source_doc AS source_doc,
                    a.description AS action,
                    hops
                """.replace("{depth}", str(depth))
                result = session.run(cypher, failure_type=failure_type)
                return [dict(r) for r in result]
        except Exception as e:
            logger.error(f"get_causal_chain failed: {e}")
            return []

    def get_graph_context(
        self,
        equipment_id: Optional[str],
        component_name: Optional[str] = None,
        failure_type: Optional[str] = None
    ) -> str:
        """
        Builds a human-readable graph context block for LLM injection.
        Combines related failures + causal chain + equipment health score.
        """
        if not self._connected:
            return ""

        lines = ["=== KNOWLEDGE GRAPH CONTEXT ==="]

        # Equipment health
        eq_health = self.get_equipment_health(equipment_id)
        if eq_health:
            lines.append(
                f"\nEquipment {equipment_id} — "
                f"Health: {eq_health.get('health_score', 'N/A')}% | "
                f"Risk: {eq_health.get('risk_level', 'N/A')} | "
                f"Criticality: {eq_health.get('criticality', 'N/A')}"
            )

        # Historical failures
        failures = self.get_related_failures(equipment_id, component_name)
        if failures:
            lines.append(f"\nHistorical Failures for {equipment_id}:")
            for f in failures:
                lines.append(
                    f"  • [{f['date'] or 'N/A'}] {f['failure_type']} "
                    f"(confidence={f['confidence'] or 'N/A'}, doc={f['source_doc'] or 'N/A'}"
                    + (f" v{f['doc_version']}" if f.get('doc_version') else "")
                    + f") → Action: {f['action'] or 'N/A'} [{f['priority'] or 'N/A'}]"
                    + (f" | ChromaDB chunk: {f['chunk_id']}" if f.get("chunk_id") else "")
                )

        # Similar failure causal chain
        if failure_type:
            chain = self.get_causal_chain(failure_type)
            if chain:
                lines.append(f"\nSimilar Failure Patterns (SIMILAR_TO traversal for '{failure_type}'):")
                for c in chain:
                    lines.append(
                        f"  → {c['failure_type']} on {c['date'] or 'N/A'} "
                        f"[hops={c['hops']}, conf={c['confidence'] or 'N/A'}]"
                        + (f" | Fix: {c['action']}" if c.get("action") else "")
                    )

        if len(lines) == 1:
            return ""  # No graph data found

        lines.append("=== END GRAPH CONTEXT ===\n")
        return "\n".join(lines)

    # ------------------------------------------------------------------
    # Query: Equipment Health Score
    # ------------------------------------------------------------------

    def get_equipment_health(self, equipment_id: Optional[str]) -> Optional[Dict[str, Any]]:
        """Returns the health score, risk level, and criticality for an equipment node."""
        if not self._connected or not equipment_id:
            return None
        try:
            with self.driver.session() as session:
                result = session.run(
                    """
                    MATCH (e:Equipment {id: $eq_id})
                    RETURN e.health_score AS health_score,
                           e.risk_level   AS risk_level,
                           e.criticality  AS criticality,
                           e.location     AS location
                    """,
                    eq_id=equipment_id.upper()
                )
                record = result.single()
                return dict(record) if record else None
        except Exception as e:
            logger.error(f"get_equipment_health failed: {e}")
            return None

    def update_equipment_health(
        self,
        equipment_id: str,
        health_score: float,
        risk_level: str,
        criticality: str
    ):
        """Allows external updates to the equipment health score (e.g. from predictive model)."""
        if not self._connected:
            return
        try:
            with self.driver.session() as session:
                session.run(
                    """
                    MATCH (e:Equipment {id: $eq_id})
                    SET e.health_score = $health_score,
                        e.risk_level   = $risk_level,
                        e.criticality  = $criticality
                    """,
                    eq_id=equipment_id.upper(),
                    health_score=health_score,
                    risk_level=risk_level,
                    criticality=criticality
                )
        except Exception as e:
            logger.error(f"update_equipment_health failed: {e}")

    def get_equipment_neighborhood(self, equipment_id: str) -> Dict[str, Any]:
        """
        Returns the full knowledge graph neighborhood of an equipment node as a
        JSON-serialisable dict (nodes + relationships) for the frontend.
        """
        eq_key = normalize_id(equipment_id)
        if not self._connected:
            try:
                import os
                import json
                db_path = os.path.join(os.path.dirname(__file__), "mock_graph_db.json")
                if os.path.exists(db_path):
                    with open(db_path, "r", encoding="utf-8") as f:
                        db_data = json.load(f)
                    
                    if eq_key in db_data:
                        entry = db_data[eq_key]
                        nodes_map = {}
                        edges_set = set()

                        def add_node(label, name, properties=None):
                            if not name:
                                return None
                            if label in ("Equipment", "WorkOrder"):
                                n_name = name.upper()
                            else:
                                n_name = name.lower()
                            node_id = f"{label}:{n_name}"
                            if node_id not in nodes_map:
                                nodes_map[node_id] = {
                                    "id": node_id,
                                    "label": label,
                                    "name": n_name,
                                    **(properties or {})
                                }
                            return node_id

                        def add_edge(src_id, tgt_id, r_type):
                            if src_id and tgt_id:
                                edges_set.add((src_id, tgt_id, r_type))

                        # Central Equipment node
                        eq_nid = add_node("Equipment", eq_key, {
                            "location": entry.get("location", "utility block a"),
                            "manufacturer": entry.get("manufacturer", "sulzer pumps"),
                            "health_score": 76.0,
                            "risk_level": "MEDIUM",
                            "criticality": "HIGH"
                        })

                        # Global attributes
                        loc = entry.get("location")
                        if loc:
                            loc_nid = add_node("Location", loc)
                            add_edge(eq_nid, loc_nid, "BELONGS_TO")
                        man = entry.get("manufacturer")
                        if man:
                            man_nid = add_node("Manufacturer", man)
                            add_edge(eq_nid, man_nid, "MANUFACTURED_BY")

                        # Loop over stored entities
                        stored_entities = entry.get("entities")
                        if stored_entities:
                            for ent in stored_entities:
                                wo = ent.get("work_order_id")
                                comp = ent.get("component_name")
                                fail = ent.get("failure_type")
                                action = ent.get("maintenance_action")
                                tech = ent.get("technician")
                                cause = ent.get("cause")
                                rec = ent.get("recommendation")
                                docs = ent.get("documents", [])

                                # Create nodes and connect them semantically
                                wo_nid = add_node("WorkOrder", wo) if wo else None
                                if wo_nid:
                                    add_edge(wo_nid, eq_nid, "BELONGS_TO_WORK_ORDER")

                                comp_nid = add_node("Component", comp) if comp else None
                                if comp_nid:
                                    add_edge(eq_nid, comp_nid, "HAS_COMPONENT")

                                fail_nid = add_node("Failure", fail) if fail else None
                                if fail_nid:
                                    if comp_nid:
                                        add_edge(comp_nid, fail_nid, "HAS_FAILURE")
                                    else:
                                        add_edge(eq_nid, fail_nid, "HAS_FAILURE")
                                    
                                    if wo_nid:
                                        add_edge(fail_nid, wo_nid, "BELONGS_TO_WORK_ORDER")
                                    
                                    if cause:
                                        cause_nid = add_node("Cause", cause)
                                        add_edge(fail_nid, cause_nid, "CAUSED_BY")
                                    
                                    if rec:
                                        rec_nid = add_node("Recommendation", rec)
                                        add_edge(fail_nid, rec_nid, "RECOMMENDED_ACTION")
                                    
                                    if action:
                                        act_nid = add_node("Action", action)
                                        add_edge(fail_nid, act_nid, "RECOMMENDED_ACTION")
                                        if wo_nid:
                                            add_edge(act_nid, wo_nid, "BELONGS_TO_WORK_ORDER")
                                        if tech:
                                            tech_nid = add_node("Technician", tech)
                                            add_edge(act_nid, tech_nid, "PERFORMED_BY")
                                    elif tech:
                                        tech_nid = add_node("Technician", tech)
                                        add_edge(fail_nid, tech_nid, "PERFORMED_BY")

                                    for d in docs:
                                        doc_nid = add_node("Document", d)
                                        add_edge(fail_nid, doc_nid, "SOURCE_DOCUMENT")
                        else:
                            # Backward compatibility for old mock_graph_db.json
                            for comp in entry.get("components", []):
                                comp_nid = add_node("Component", comp)
                                add_edge(eq_nid, comp_nid, "HAS_COMPONENT")
                            for idx, fail in enumerate(entry.get("failures", [])):
                                fail_nid = add_node("Failure", fail)
                                add_edge(eq_nid, fail_nid, "HAS_FAILURE")
                            for act in entry.get("actions", []):
                                act_nid = add_node("Action", act)
                                add_edge(eq_nid, act_nid, "RECOMMENDED_ACTION")
                            tech = entry.get("technician")
                            if tech:
                                tech_nid = add_node("Technician", tech)
                                add_edge(eq_nid, tech_nid, "PERFORMED_BY")
                            for doc in entry.get("documents", []):
                                doc_nid = add_node("Document", doc)
                                add_edge(eq_nid, doc_nid, "SOURCE_DOCUMENT")

                        # Capping mock nodes to 25
                        ordered_nodes = []
                        if eq_nid in nodes_map:
                            ordered_nodes.append(nodes_map[eq_nid])
                        for nid, n in nodes_map.items():
                            if nid != eq_nid:
                                ordered_nodes.append(n)

                        capped_nodes = ordered_nodes[:25]
                        capped_node_ids = {n["id"] for n in capped_nodes}

                        final_edges = []
                        for start_id, end_id, rel_type in edges_set:
                            if start_id in capped_node_ids and end_id in capped_node_ids:
                                final_edges.append({
                                    "source": start_id,
                                    "target": end_id,
                                    "type": rel_type
                                })

                        return {
                            "nodes": capped_nodes,
                            "edges": final_edges,
                            "equipment_id": eq_key,
                            "health_score": None,
                            "graph_available": True
                        }
            except Exception as e:
                logger.error(f"Failed to read mock graph cache: {e}")
            return {"nodes": [], "edges": [], "graph_available": False}
        try:
            with self.driver.session() as session:
                # Query paths up to depth 2 from the equipment
                result = session.run(
                    """
                    MATCH (e:Equipment {id: $eq_id})
                    OPTIONAL MATCH path = (e)-[*1..2]-(neighbor)
                    RETURN path LIMIT 50
                    """,
                    eq_id=equipment_id.upper()
                )

                nodes_map = {}
                edges_set = set()

                def process_node(node):
                    labels = list(node.labels)
                    label = labels[0] if labels else "Unknown"
                    props = dict(node)
                    
                    if label in ("Equipment", "WorkOrder"):
                        name = (props.get("id") or props.get("name") or "").upper()
                    else:
                        name = (props.get("name") or props.get("description") or props.get("type") or "").lower()
                    
                    node_id = f"{label}:{name}"
                    if node_id not in nodes_map:
                        nodes_map[node_id] = {
                            "id": node_id,
                            "label": label,
                            "name": name,
                            **{k: v for k, v in props.items() if k not in ("id", "name")}
                        }
                    return node_id

                # Guarantee the equipment node itself is retrieved
                eq_check = session.run("MATCH (e:Equipment {id: $eq_id}) RETURN e", eq_id=equipment_id.upper())
                eq_record = eq_check.single()
                if eq_record and eq_record["e"]:
                    process_node(eq_record["e"])

                for record in result:
                    path = record["path"]
                    if not path:
                        continue
                    
                    for rel in path.relationships:
                        start_node = rel.start_node
                        end_node = rel.end_node
                        
                        start_id = process_node(start_node)
                        end_id = process_node(end_node)
                        
                        edges_set.add((start_id, end_id, rel.type))

                # Cap nodes count to maximum 25, keeping equipment first
                target_eq_id = f"Equipment:{equipment_id.upper()}"
                ordered_nodes = []
                if target_eq_id in nodes_map:
                    ordered_nodes.append(nodes_map[target_eq_id])
                
                for nid, n in nodes_map.items():
                    if nid != target_eq_id:
                        ordered_nodes.append(n)
                
                capped_nodes = ordered_nodes[:25]
                capped_node_ids = {n["id"] for n in capped_nodes}

                final_edges = []
                for start_id, end_id, rel_type in edges_set:
                    if start_id in capped_node_ids and end_id in capped_node_ids:
                        final_edges.append({
                            "source": start_id,
                            "target": end_id,
                            "type": rel_type
                        })

                return {
                    "nodes": capped_nodes,
                    "edges": final_edges,
                    "equipment_id": equipment_id.upper(),
                    "health_score": None,
                    "graph_available": True
                }
        except Exception as e:
            logger.error(f"get_equipment_neighborhood failed: {e}")
            return {"nodes": [], "edges": [], "graph_available": False}

    # ------------------------------------------------------------------
    # Query: Stats
    # ------------------------------------------------------------------

    def get_stats(self) -> Dict[str, Any]:
        """Returns total node and relationship counts."""
        if not self._connected:
            return {"connected": False}
        try:
            with self.driver.session() as session:
                nodes = session.run("MATCH (n) RETURN count(n) AS c").single()["c"]
                rels  = session.run("MATCH ()-[r]->() RETURN count(r) AS c").single()["c"]
                equip = session.run("MATCH (e:Equipment) RETURN count(e) AS c").single()["c"]
                fails = session.run("MATCH (f:Failure) RETURN count(f) AS c").single()["c"]
                docs  = session.run("MATCH (d:Document) RETURN count(d) AS c").single()["c"]
                return {
                    "connected": True,
                    "total_nodes": nodes,
                    "total_relationships": rels,
                    "equipment_nodes": equip,
                    "failure_nodes": fails,
                    "document_nodes": docs,
                }
        except Exception as e:
            logger.error(f"get_stats failed: {e}")
            return {"connected": False, "error": str(e)}

    # ------------------------------------------------------------------
    # Deletion
    # ------------------------------------------------------------------

    def delete_document_nodes(self, doc_name: str) -> bool:
        """
        Removes all nodes and relationships sourced from a given document.
        Used when a document is deleted from ChromaDB.
        """
        if not self._connected:
            return False
        try:
            with self.driver.session() as session:
                session.run(
                    """
                    MATCH (d:Document {name: $name})
                    OPTIONAL MATCH (d)<-[:SOURCED_FROM]-(f:Failure)
                    OPTIONAL MATCH (d)-[:HAS_CHUNK]->(ch:Chunk)
                    DETACH DELETE d, f, ch
                    """,
                    name=doc_name
                )
            logger.info(f"Deleted graph nodes for document '{doc_name}'")
            return True
        except Exception as e:
            logger.error(f"delete_document_nodes failed: {e}")
            return False

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------

    @property
    def is_connected(self) -> bool:
        return self._connected

    def close(self):
        if self.driver:
            self.driver.close()
            logger.info("Neo4j driver closed.")


# Lazy singleton — initialized in main.py with settings injected
_graph_store_instance: Optional[GraphStore] = None


def get_graph_store(settings=None) -> GraphStore:
    """
    Returns the singleton GraphStore instance.
    Pass settings on first call; subsequent calls return the cached instance.
    """
    global _graph_store_instance
    if _graph_store_instance is None:
        if settings is None:
            from app.config import settings as _settings
            settings = _settings
        _graph_store_instance = GraphStore(settings)
    return _graph_store_instance
