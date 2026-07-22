import os
os.environ["ANONYMOUS_TELEMETRY"] = "False"
import shutil
import logging
from typing import Dict, Any, List
from fastapi import FastAPI, UploadFile, File, Form, HTTPException, BackgroundTasks
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from app.config import settings
from app.ingestion import ingest_pdf
from app.rag import rag_engine
from app.graph_store import get_graph_store
from app.models import (
    PredictRequest, PredictResponse,
    RAGQueryRequest, RAGQueryResponse,
    RCARequest, RCAResponse,
    ComplianceRequest, ComplianceResponse,
    LessonsLearnedRequest, LessonsLearnedResponse,
    EntityExtractionResult, ReferenceItem
)
from app.ml.predictive_maintenance import pm_model
from app.agents.orchestrator import query_orchestrator
from app.llm import llm_service

# Initialise graph store singleton (gracefully no-ops when Neo4j is disabled)
graph_store = get_graph_store(settings)

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s"
)
logger = logging.getLogger("main")

app = FastAPI(
    title="Industrial Knowledge Intelligence API",
    description="Multi-agent industrial intelligence platform with ingestion, RAG, compliance, and predictive maintenance capabilities.",
    version="1.0.0"
)

# CORS setup for Frontend integration
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # In production, specify frontend URLs
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Create a temp upload folder on startup
UPLOAD_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), "uploads")
os.makedirs(UPLOAD_DIR, exist_ok=True)

class ExtractionRequest(BaseModel):
    text: str

@app.get("/status")
def get_status() -> Dict[str, Any]:
    """
    Returns server health, loaded models, and configuration details.
    """
    neo4j_status = "DISABLED"
    if settings.NEO4J_ENABLED:
        neo4j_status = "CONNECTED" if graph_store.is_connected else "UNREACHABLE"

    return {
        "status": "HEALTHY",
        "llm_mode": "MOCK" if llm_service.is_mock else f"LIVE (Model: {llm_service.model_name})",
        "tesseract_ocr": "AVAILABLE" if os.path.exists(settings.TESSERACT_CMD) else "UNAVAILABLE (Direct PDF text only)",
        "embedding_model": settings.EMBEDDING_MODEL,
        "reranker_model": settings.RERANK_MODEL,
        "xgboost_model": "LOADED" if pm_model.model != "MOCK" else "MOCK FALLBACK",
        "chroma_collection": settings.CHROMA_COLLECTION,
        "neo4j": neo4j_status,
    }

@app.post("/ingest")
async def upload_document(
    file: UploadFile = File(...),
    force_ocr: bool = Form(False),
    doc_version: str = Form("1.0")
) -> Dict[str, Any]:
    """
    Uploads a PDF, processes it with PyMuPDF/OCR, cleans the text,
    stores page embeddings in ChromaDB, and extracts entities into Neo4j.

    Neo4j entity extraction is performed on the WHOLE DOCUMENT (not per-page)
    to prevent equipment nodes from being fragmented across multiple extractions.
    ChromaDB chunk IDs are linked to Neo4j nodes as a vector bridge.
    """
    if not file.filename.endswith(".pdf"):
        raise HTTPException(status_code=400, detail="Only PDF documents are supported.")

    temp_file_path = os.path.join(UPLOAD_DIR, file.filename)

    try:
        # ── 1. Save uploaded file ────────────────────────────────────────────────
        with open(temp_file_path, "wb") as buffer:
            shutil.copyfileobj(file.file, buffer)
        logger.info(f"Saved uploaded file to: {temp_file_path}")

        # ── 2. Parse PDF (PyMuPDF / OCR) ─────────────────────────────────────────
        parsed_doc = ingest_pdf(temp_file_path, force_ocr=force_ocr)

        # ── 3. Index into ChromaDB and collect chunk IDs ──────────────────────────
        chunk_ids = rag_engine.add_document_with_ids(parsed_doc)
        if chunk_ids is None:
            raise HTTPException(status_code=500, detail="Failed to index document in vector database.")

        # ── 4. Clean up temp file ─────────────────────────────────────────────────
        if os.path.exists(temp_file_path):
            os.remove(temp_file_path)

        # ── 5. Neo4j Graph Ingestion (whole-document entity extraction) ───────────
        graph_entities_indexed = 0
        try:
            # Concatenate ALL page text into one document-level string
            full_text = " ".join(
                p["content"] for p in parsed_doc["pages"] if p.get("content")
            )

            # Entity extraction on the full document
            entity_prompt = (
                f"Analyze the following industrial document (full text):\n\"\"\"{full_text[:8000]}\"\"\"\n\n"
                f"Extract all equipment IDs, component names, failure modes, technicians, dates, "
                f"maintenance actions, regulatory references, plant locations, root causes, preventive recommendations, and manufacturers."
            )
            system_ep = "You are an expert Entity Extraction system for industrial maintenance logs."
            extraction: EntityExtractionResult = llm_service.generate_structured(
                prompt=entity_prompt,
                response_model=EntityExtractionResult,
                system_prompt=system_ep
            )

            entities_dicts = [e.model_dump() for e in extraction.entities]

            # Upsert into Neo4j or local cache
            graph_entities_indexed = graph_store.upsert_entities(
                entities=entities_dicts,
                doc_name=parsed_doc["document_name"],
                doc_version=doc_version,
                page_count=parsed_doc["metadata"]["page_count"],
                chunk_ids=chunk_ids,
            )

            if graph_store.is_connected:
                # Build SIMILAR_TO edges across the whole graph
                graph_store.build_similar_failure_edges()

            logger.info(
                f"Graph ingestion complete: {graph_entities_indexed} entities, "
                f"{len(chunk_ids)} chunk IDs linked"
            )
        except Exception as ge:
            logger.error(f"Graph ingestion failed (non-fatal): {ge}")

        return {
            "message": f"Document '{file.filename}' processed and indexed successfully.",
            "document_name": parsed_doc["document_name"],
            "doc_version": doc_version,
            "page_count": parsed_doc["metadata"]["page_count"],
            "file_size_bytes": parsed_doc["metadata"]["file_size_bytes"],
            "metadata": parsed_doc["metadata"],
            "chroma_chunks_indexed": len(chunk_ids),
            "graph_entities_indexed": graph_entities_indexed,
            "preview": parsed_doc["pages"][0]["content"][:300] + "..." if parsed_doc["pages"] else ""
        }
    except Exception as e:
        logger.error(f"Error during ingestion of '{file.filename}': {str(e)}")
        if os.path.exists(temp_file_path):
            os.remove(temp_file_path)
        raise HTTPException(status_code=500, detail=f"Ingestion failed: {str(e)}")

@app.get("/documents")
def list_documents() -> List[Dict[str, Any]]:
    """
    Lists all indexed documents and their page count.
    """
    return rag_engine.list_documents()

@app.delete("/documents/{doc_name}")
def delete_document(doc_name: str) -> Dict[str, Any]:
    """
    Removes a document and its embeddings from ChromaDB and its nodes from Neo4j.
    """
    success = rag_engine.delete_document(doc_name)
    if not success:
        raise HTTPException(status_code=404, detail=f"Document '{doc_name}' not found or deletion failed.")

    # Also clean graph nodes if Neo4j is active
    graph_store.delete_document_nodes(doc_name)

    return {"message": f"Document '{doc_name}' deleted from vector DB and knowledge graph."}


# ── Graph API Endpoints ────────────────────────────────────────────────────────

@app.get("/graph/stats")
def graph_stats() -> Dict[str, Any]:
    """
    Returns Neo4j node and relationship counts.
    Useful for dashboard status widgets.
    """
    return graph_store.get_stats()


@app.get("/graph/equipment/{equipment_id}")
def graph_equipment(equipment_id: str) -> Dict[str, Any]:
    """
    Returns the full knowledge graph neighborhood of an equipment node.
    Includes health score, risk level, failures, actions, technicians,
    regulations, and linked ChromaDB chunks.
    """
    neighborhood = graph_store.get_equipment_neighborhood(equipment_id)
    if not neighborhood.get("graph_available"):
        raise HTTPException(
            status_code=503,
            detail="Neo4j is not connected or is disabled (NEO4J_ENABLED=False)."
        )
    if not neighborhood["nodes"]:
        raise HTTPException(
            status_code=404,
            detail=f"Equipment '{equipment_id.upper()}' not found in knowledge graph."
        )
    return neighborhood


@app.get("/graph/equipment/{equipment_id}/health")
def graph_equipment_health(equipment_id: str) -> Dict[str, Any]:
    """
    Returns health score, risk level, and criticality for a specific equipment.
    """
    health = graph_store.get_equipment_health(equipment_id)
    if health is None:
        raise HTTPException(
            status_code=404,
            detail=f"Equipment '{equipment_id.upper()}' not found or Neo4j unavailable."
        )
    return {"equipment_id": equipment_id.upper(), **health}


@app.delete("/graph/document/{doc_name}")
def delete_graph_document(doc_name: str) -> Dict[str, Any]:
    """
    Removes all graph nodes sourced from a given document without touching ChromaDB.
    """
    success = graph_store.delete_document_nodes(doc_name)
    if not success:
        raise HTTPException(
            status_code=500,
            detail=f"Graph deletion failed for '{doc_name}' — Neo4j may be unavailable."
        )
    return {"message": f"Graph nodes for document '{doc_name}' deleted successfully."}

@app.post("/query")
def orchestrator_query(req: RAGQueryRequest) -> Dict[str, Any]:
    """
    Core entrypoint for the multi-agent system.
    Routes queries using LangGraph and returns the aggregated agent response.
    """
    try:
        output = query_orchestrator(query=req.query, metadata_filter=req.doc_filter)
        return output
    except Exception as e:
        logger.error(f"Orchestrator query execution failed: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Query failed: {str(e)}")

@app.post("/predict", response_model=PredictResponse)
def predict_telemetry(req: PredictRequest):
    """
    Endpoint for predictive maintenance failure classification using XGBoost.
    """
    try:
        res = pm_model.predict(req.model_dump())
        return res
    except Exception as e:
        logger.error(f"Predictive maintenance model prediction failed: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Prediction failed: {str(e)}")

@app.post("/extract", response_model=EntityExtractionResult)
def extract_entities(req: ExtractionRequest):
    """
    Extracts structured industrial entities (Equipment IDs, components, violations) from text using LLM.
    """
    try:
        prompt = (
            f"Analyze the following industrial log, inspection report, or technician notes:\n"
            f"\"\"\"\n{req.text}\n\"\"\"\n\n"
            f"Extract all equipment IDs, component names, failure modes, technicians, dates, "
            f"maintenance actions, regulatory references, plant locations, root causes, preventive recommendations, and manufacturers."
        )
        system_prompt = "You are an expert Entity Extraction system for industrial maintenance logs."
        res = llm_service.generate_structured(
            prompt=prompt,
            response_model=EntityExtractionResult,
            system_prompt=system_prompt
        )
        return res
    except Exception as e:
        logger.error(f"Entity extraction failed: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Entity extraction failed: {str(e)}")

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("app.main:app", host=settings.HOST, port=settings.PORT, reload=True)
