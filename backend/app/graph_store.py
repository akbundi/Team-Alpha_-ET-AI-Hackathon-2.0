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
        Entities are from the whole document (not per-page) to avoid fragmentation.
        
        Parameters
        ----------
        entities   : List of IndustrialEntity dicts (from LLM extraction)
        doc_name   : Source document filename
        doc_version: Semantic version of the document (e.g. "1.0", "2.1")
        page_count : Total page count for Document node
        chunk_ids  : ChromaDB chunk IDs to link as :Chunk nodes → ChromaDB bridge

        Returns
        -------
        Number of equipment nodes upserted.
        """
        if not self._connected:
            return 0

        upload_ts = datetime.now(timezone.utc).isoformat()
        upserted = 0

        with self.driver.session() as session:
            # 1. Upsert Document node (versioned)
            session.run(
                """
                MERGE (d:Document {name: $name, version: $version})
                ON CREATE SET d.upload_date = $upload_date, d.page_count = $page_count
                ON MATCH  SET d.upload_date = $upload_date, d.page_count = $page_count
                """,
                name=doc_name, version=doc_version,
                upload_date=upload_ts, page_count=page_count
            )

            # 2. Upsert ChromaDB Chunk bridge nodes
            if chunk_ids:
                for cid in chunk_ids:
                    # chunk_id format: {doc_name}_p{page}_c{idx}_{hex}
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
                        MATCH (d:Document {name: $source, version: $version})
                        MERGE (d)-[:HAS_CHUNK]->(ch)
                        """,
                        cid=cid, source=doc_name,
                        page=page_part, version=doc_version
                    )

            # 3. Upsert each entity
            for entity in entities:
                eq_id = entity.get("equipment_id") or ""
                comp_name = entity.get("component_name") or ""
                failure_type = entity.get("failure_type") or ""
                technician = entity.get("technician") or ""
                inspection_date = entity.get("inspection_date") or upload_ts
                action = entity.get("maintenance_action") or ""
                regs = entity.get("regulatory_references", [])
                location = entity.get("location") or ""
                confidence = float(entity.get("confidence", 0.85))

                if not eq_id:
                    continue  # Skip entities without a grounded equipment ID

                # Equipment node
                session.run(
                    """
                    MERGE (e:Equipment {id: $eq_id})
                    ON CREATE SET
                        e.name     = $eq_id,
                        e.location = $location,
                        e.health_score  = 100.0,
                        e.risk_level    = 'LOW',
                        e.criticality   = 'MEDIUM'
                    ON MATCH SET
                        e.location = CASE WHEN $location <> '' THEN $location ELSE e.location END
                    """,
                    eq_id=eq_id, location=location
                )

                # Component node + relationship
                if comp_name:
                    session.run(
                        """
                        MATCH (e:Equipment {id: $eq_id})
                        MERGE (c:Component {name: $comp_name})
                        ON CREATE SET c.type = $comp_name
                        MERGE (e)-[:HAS_COMPONENT]->(c)
                        """,
                        eq_id=eq_id, comp_name=comp_name
                    )

                # Failure node + relationship (with confidence + date)
                if failure_type:
                    failure_node_id = f"{eq_id}_{failure_type}_{inspection_date[:10]}"
                    session.run(
                        """
                        MATCH (e:Equipment {id: $eq_id})
                        MERGE (f:Failure {id: $fid})
                        ON CREATE SET
                            f.type        = $failure_type,
                            f.date        = $date,
                            f.description = $failure_type,
                            f.confidence  = $confidence,
                            f.source_doc  = $doc_name
                        MERGE (e)-[:EXPERIENCED]->(f)
                        WITH e, f
                        MATCH (d:Document {name: $doc_name, version: $version})
                        MERGE (f)-[:SOURCED_FROM]->(d)
                        """,
                        eq_id=eq_id,
                        fid=failure_node_id,
                        failure_type=failure_type,
                        date=inspection_date,
                        confidence=confidence,
                        doc_name=doc_name,
                        version=doc_version
                    )

                    # Cause node + link to Chunk (ChromaDB bridge)
                    if chunk_ids:
                        for cid in chunk_ids[:1]:  # link first chunk as representative
                            session.run(
                                """
                                MATCH (f:Failure {id: $fid})
                                MATCH (ch:Chunk {chunk_id: $cid})
                                MERGE (f)-[:LINKED_CHUNK]->(ch)
                                """,
                                fid=failure_node_id, cid=cid
                            )

                    # Corrective Action node
                    if action:
                        session.run(
                            """
                            MATCH (f:Failure {id: $fid})
                            MERGE (a:Action {description: $action})
                            ON CREATE SET a.priority = 'MEDIUM'
                            MERGE (f)-[:FIXED_BY]->(a)
                            """,
                            fid=failure_node_id, action=action
                        )

                    # Technician node
                    if technician:
                        session.run(
                            """
                            MATCH (f:Failure {id: $fid})
                            MERGE (t:Technician {name: $tech})
                            MERGE (f)-[:INSPECTED_BY]->(t)
                            """,
                            fid=failure_node_id, tech=technician
                        )

                    # Regulation nodes
                    for reg in regs:
                        if reg.strip():
                            session.run(
                                """
                                MATCH (f:Failure {id: $fid})
                                MERGE (r:Regulation {code: $reg})
                                MERGE (f)-[:REFERENCES]->(r)
                                """,
                                fid=failure_node_id, reg=reg.strip()
                            )

                    # Update Equipment health score (lower health per failure)
                    session.run(
                        """
                        MATCH (e:Equipment {id: $eq_id})-[:EXPERIENCED]->(f:Failure)
                        WITH e, count(f) AS num_failures
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

    # ------------------------------------------------------------------
    # Query: Full Equipment Neighborhood (for API / frontend)
    # ------------------------------------------------------------------

    def get_equipment_neighborhood(self, equipment_id: str) -> Dict[str, Any]:
        """
        Returns the full graph neighborhood of an equipment node as a
        JSON-serialisable dict (nodes + relationships) for the frontend.
        """
        if not self._connected:
            return {"nodes": [], "edges": [], "graph_available": False}
        try:
            with self.driver.session() as session:
                result = session.run(
                    """
                    MATCH (e:Equipment {id: $eq_id})
                    OPTIONAL MATCH (e)-[:HAS_COMPONENT]->(c:Component)
                    OPTIONAL MATCH (e)-[:EXPERIENCED]->(f:Failure)
                    OPTIONAL MATCH (f)-[:FIXED_BY]->(a:Action)
                    OPTIONAL MATCH (f)-[:INSPECTED_BY]->(t:Technician)
                    OPTIONAL MATCH (f)-[:REFERENCES]->(r:Regulation)
                    OPTIONAL MATCH (f)-[:SOURCED_FROM]->(d:Document)
                    OPTIONAL MATCH (f)-[:SIMILAR_TO]->(sf:Failure)
                    RETURN
                        e, c, f, a, t, r, d, sf,
                        e.health_score AS health_score,
                        e.risk_level   AS risk_level
                    """,
                    eq_id=equipment_id.upper()
                )

                nodes, edges = [], []
                seen_nodes = set()

                def add_node(label, props):
                    key = f"{label}:{props.get('id') or props.get('name') or props.get('type') or props.get('description') or props.get('code', '')}"
                    if key not in seen_nodes:
                        seen_nodes.add(key)
                        nodes.append({"label": label, **{k: v for k, v in props.items() if v is not None}})

                for record in result:
                    e = record["e"]
                    if e:
                        add_node("Equipment", dict(e))
                    for label, key, rel in [
                        ("Component", "c", "HAS_COMPONENT"),
                        ("Failure",   "f", "EXPERIENCED"),
                        ("Action",    "a", "FIXED_BY"),
                        ("Technician","t", "INSPECTED_BY"),
                        ("Regulation","r", "REFERENCES"),
                        ("Document",  "d", "SOURCED_FROM"),
                        ("Failure",   "sf","SIMILAR_TO"),
                    ]:
                        node = record.get(key)
                        if node:
                            props = dict(node)
                            add_node(label, props)

                return {
                    "nodes": nodes,
                    "edges": edges,
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
