import logging
from typing import Dict, Any, List
from app.models import LessonsLearnedRequest, LessonsLearnedResponse, HistoricalIncident
from app.rag import rag_engine
from app.llm import llm_service

logger = logging.getLogger(__name__)

def run_lessons_learned_agent(req: LessonsLearnedRequest) -> LessonsLearnedResponse:
    """
    Analyzes new incidents against historical incident logs to find recurring patterns and preventative measures.
    """
    logger.info(f"Lessons Learned Agent running. New Incident: '{req.new_incident_description[:60]}...'")
    
    # 1. Retrieve similar historical incidents from ChromaDB
    search_query = req.new_incident_description
    if req.equipment_type:
        search_query = f"{req.equipment_type} {search_query}"
        
    logger.info(f"Lessons Learned Agent searching ChromaDB for: '{search_query}'")
    retrieved_incidents = rag_engine.retrieve(
        query=search_query,
        top_k=8,
        rerank_top_n=3
    )
    
    # 2. Format historical reports context
    history_context = ""
    historical_events: List[HistoricalIncident] = []
    
    for idx, chunk in enumerate(retrieved_incidents):
        content = chunk["content"]
        source = chunk["metadata"]["source"]
        page = chunk["metadata"]["page"]
        sim_score = chunk["confidence"]
        
        history_context += (
            f"--- HISTORICAL INCIDENT {idx+1} ---\n"
            f"Source Document: {source}, Page: {page}\n"
            f"Record Content: {content}\n\n"
        )
        
        # We also attempt to pre-populate elements for historical_events
        # These will be enriched or returned directly to the user
        historical_events.append(HistoricalIncident(
            source_doc=source,
            page=int(page),
            summary=content[:150] + "...",
            failure_mode="Detected failure mode from logs",
            root_cause="Refer to document text",
            recomm_action="Verify SOP steps",
            similarity_score=float(sim_score)
        ))
        
    # 3. Construct the prompt for the LLM
    prompt = (
        f"You are a Safety Director and Industrial Reliability Engineer specializing in Lessons Learned analysis.\n\n"
        f"A new incident has just been reported:\n"
        f"Description: {req.new_incident_description}\n"
        f"Equipment Type: {req.equipment_type or 'Not Specified'}\n\n"
        f"Here are relevant historical incident reports, audit logs, and near-miss records retrieved from the database:\n"
        f"{history_context if history_context else 'No matching historical reports found in database.'}\n\n"
        f"Task:\n"
        f"1. Summarize the new incident briefly.\n"
        f"2. Fill in the specific details of similar historical events (up to 3 items) returned in the context. For each item, extract:\n"
        f"   - source_doc and page (strictly match the retrieved items)\n"
        f"   - summary of what happened\n"
        f"   - failure_mode (e.g. seal degradation, pressure spike)\n"
        f"   - root_cause of that historical event\n"
        f"   - recomm_action (preventive/corrective recommendations from that event)\n"
        f"   - similarity_score (use the numbers: {[h.similarity_score for h in historical_events]})\n"
        f"3. Identify recurring patterns or common failure modes across these historical events.\n"
        f"4. Propose critical preventive measures for the new incident to ensure this type of event does not happen again."
    )
    
    system_prompt = "You are a Lessons Learned AI Agent specializing in analyzing historical industrial failure records."
    
    # 4. Call LLM Service
    res = llm_service.generate_structured(
        prompt=prompt,
        response_model=LessonsLearnedResponse,
        system_prompt=system_prompt
    )
    
    # Ensure similar historical events has similarity scores populated if LLM did not fill them
    if res.similar_historical_events:
        for idx, event in enumerate(res.similar_historical_events):
            if idx < len(historical_events):
                event.similarity_score = historical_events[idx].similarity_score
    else:
        # Fallback if LLM failed to populate
        res.similar_historical_events = historical_events
        
    return res
