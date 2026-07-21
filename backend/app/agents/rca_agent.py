import re
import logging
from typing import Dict, Any
from app.models import RCARequest, RCAResponse
from app.rag import rag_engine
from app.llm import llm_service
from app.graph_store import get_graph_store

logger = logging.getLogger(__name__)

# Lightweight failure-type heuristic for causal chain traversal
_FAILURE_PATTERNS = [
    (r"cavit",              "cavitation"),
    (r"bearing",            "bearing failure"),
    (r"seal",               "seal failure"),
    (r"overheat|temperature","overheating"),
    (r"vibrat",             "vibration"),
    (r"corros",             "corrosion"),
    (r"leak",               "leakage"),
    (r"crack|fractur",      "fatigue crack"),
]


def _detect_failure_type(text: str) -> str:
    """Extracts a normalised failure type keyword from free text."""
    text_l = text.lower()
    for pattern, label in _FAILURE_PATTERNS:
        if re.search(pattern, text_l):
            return label
    return ""


def run_rca_agent(req: RCARequest) -> RCAResponse:
    """
    Analyzes equipment failures using a dual-context approach:
      1. ChromaDB semantic retrieval  — document text similarity
      2. Neo4j graph traversal        — structured failure history + causal chain

    The combined context is injected into the LLM for a richer, evidence-backed
    Root Cause Analysis with CAPA recommendations.
    """
    logger.info(f"RCA Agent running for equipment: {req.equipment_id or 'Unknown'}")

    # ── 1. Build ChromaDB search query ─────────────────────────────────────────
    search_query = req.incident_description
    if req.component_name:
        search_query += f" component {req.component_name}"
    if req.equipment_id:
        search_query += f" equipment {req.equipment_id}"

    logger.info(f"RCA Agent retrieving ChromaDB context for: '{search_query}'")
    retrieved_chunks = rag_engine.retrieve(
        query=search_query,
        top_k=8,
        rerank_top_n=3,
        doc_filter=req.metadata_filter
    )

    # ── 2. Format ChromaDB context ──────────────────────────────────────────────
    chroma_context = ""
    references = []

    for idx, chunk in enumerate(retrieved_chunks):
        ref_text = chunk["content"]
        source   = chunk["metadata"]["source"]
        page     = chunk["metadata"]["page"]
        conf     = chunk["confidence"]

        chroma_context += f"[Ref {idx+1}] Source: {source}, Page: {page}\nText: {ref_text}\n\n"
        references.append({
            "source":     source,
            "page":       int(page),
            "content":    ref_text,
            "confidence": float(conf)
        })

    # ── 3. Neo4j Graph Context ──────────────────────────────────────────────────
    graph_store = get_graph_store()
    failure_type = _detect_failure_type(req.incident_description)

    graph_context = graph_store.get_graph_context(
        equipment_id=req.equipment_id,
        component_name=req.component_name,
        failure_type=failure_type or None
    )

    if graph_context:
        logger.info(
            f"RCA Agent: Neo4j graph context retrieved for {req.equipment_id} "
            f"(failure_type='{failure_type}')"
        )
    else:
        logger.info("RCA Agent: No Neo4j graph context available (disabled or no data).")

    # ── 4. Construct combined LLM Prompt ───────────────────────────────────────
    prompt = (
        f"You are a Senior Industrial Forensic Engineer and Root Cause Analysis Specialist.\n\n"
        f"Analyze the following equipment failure incident:\n"
        f"Equipment ID : {req.equipment_id or 'Not Specified'}\n"
        f"Component    : {req.component_name or 'Not Specified'}\n"
        f"Description  : {req.incident_description}\n\n"
    )

    # Inject Neo4j graph context first (structured facts > text similarity)
    if graph_context:
        prompt += (
            f"--- KNOWLEDGE GRAPH (Neo4j) ---\n"
            f"{graph_context}\n"
            f"--- END KNOWLEDGE GRAPH ---\n\n"
        )

    # Then inject ChromaDB semantic context
    prompt += (
        f"--- RETRIEVED DOCUMENT CONTEXT (ChromaDB) ---\n"
        f"{chroma_context if chroma_context else 'No historical matches or documents found.'}\n"
        f"--- END DOCUMENT CONTEXT ---\n\n"
        f"Task:\n"
        f"1. Identify the most probable root causes with realistic probability scores (sum <= 1.0).\n"
        f"2. Formulate immediate corrective actions to restore operations.\n"
        f"3. Formulate preventive actions to prevent recurrence.\n"
        f"4. Assign priority (HIGH, MEDIUM, LOW) to each action.\n"
        f"5. Use the Knowledge Graph data (equipment health, historical failure dates, "
        f"confidence scores) in your reasoning. Reference ChromaDB sources for textual evidence.\n"
        f"6. If the graph shows prior similar failures via SIMILAR_TO traversal, factor their "
        f"root causes into your analysis."
    )

    system_prompt = "You are a Root Cause Analysis AI Agent specializing in industrial equipment diagnostics."

    # ── 5. Call LLM Service ──────────────────────────────────────────────────────
    res = llm_service.generate_structured(
        prompt=prompt,
        response_model=RCAResponse,
        system_prompt=system_prompt
    )

    # Attach references if LLM didn't populate citations
    if not res.citations and references:
        res.citations = references

    return res
