import logging
from typing import TypedDict, List, Dict, Any, Optional
import re
from langgraph.graph import StateGraph, END

from app.models import RAGQueryRequest, RCARequest, ComplianceRequest, LessonsLearnedRequest, PredictRequest
from app.rag import rag_engine
from app.llm import llm_service
from app.ml.predictive_maintenance import pm_model
from app.agents.rca_agent import run_rca_agent
from app.agents.compliance_agent import run_compliance_agent
from app.agents.lessons_learned_agent import run_lessons_learned_agent

logger = logging.getLogger(__name__)

# Define LangGraph State
class AgentState(TypedDict):
    query: str
    metadata_filter: Optional[str]
    agent_route: str  # qa, rca, compliance, predictive, lessons
    response: Dict[str, Any]
    history: List[Dict[str, str]]

def route_query_heuristics(query: str) -> str:
    """
    Applies quick regex/keyword heuristics to classify the routing.
    Useful as a fallback or fast path.
    """
    q = query.lower()
    
    # 1. Predictive Maintenance
    if any(k in q for k in ["predict", "probability", "telemetry", "vibration", "vibrations", "operating hours", "sensor", "pressure", "psi"]):
        # But make sure we have telemetry values in query
        if any(char.isdigit() for char in q):
            return "predictive"
            
    # 2. Compliance
    if any(k in q for k in ["audit", "compliance", "violation", "factory act", "oisd", "regulation", "clause", "statutory"]):
        return "compliance"
        
    # 3. Lessons Learned
    if any(k in q for k in ["incident history", "lessons learned", "near-miss", "recurring", "past events", "historical incident"]):
        return "lessons"
        
    # 4. Root Cause Analysis
    if any(k in q for k in ["rca", "root cause", "failure analysis", "cavitation", "broke down", "tripped", "why did", "failure mode"]):
        return "rca"
        
    # Default
    return "qa"

# 1. Router Node
def router_node(state: AgentState) -> Dict[str, Any]:
    query = state["query"]
    logger.info(f"Orchestrator routing query: '{query}'")
    
    # Try LLM routing first
    system_prompt = (
        "You are an Industrial AI Router. Your job is to classify the user's query into one of five categories:\n"
        "- 'qa': For general searches, fact-retrieval from uploaded files, lists of items or events from reports, answering questions about document contents (even safety/compliance documents, e.g., 'What factories lacked PPE?', 'Give me a list of violations'), how-to instructions, and specifications.\n"
        "- 'rca': ONLY for diagnosing a specific failure event described by the user (e.g. 'equipment failed because...', 'why did pump X trip?'). If they are just asking a general question, route to 'qa'.\n"
        "- 'compliance': ONLY when auditing/verifying a provided procedure, checklist, or Standard Operating Procedure (SOP) text against guidelines. If the user is asking a question about compliance facts in the manuals/reports, route to 'qa'.\n"
        "- 'predictive': ONLY for requesting failure forecasts when telemetry metrics (vibration, temperature, etc.) are supplied.\n"
        "- 'lessons': ONLY when comparing a new incident description against historical catalogs to find similar incidents or patterns.\n\n"
        "Return ONLY the category name: 'qa', 'rca', 'compliance', 'predictive', or 'lessons'. No punctuation, no markdown."
    )
    
    route = "qa"
    if not llm_service.is_mock:
        try:
            llm_res = llm_service.generate(prompt=query, system_prompt=system_prompt).strip().lower()
            # Clean response
            llm_res = re.sub(r'[^a-z]', '', llm_res)
            if llm_res in ["qa", "rca", "compliance", "predictive", "lessons"]:
                route = llm_res
                logger.info(f"LLM routed query to: '{route}'")
            else:
                route = route_query_heuristics(query)
                logger.info(f"LLM returned invalid route '{llm_res}'. Heuristic fallback: '{route}'")
        except Exception as e:
            logger.error(f"LLM routing failed: {e}. Falling back to heuristics.")
            route = route_query_heuristics(query)
    else:
        route = route_query_heuristics(query)
        logger.info(f"Mock/Offline mode. Heuristic routed query to: '{route}'")
        
    return {"agent_route": route}

# 2. Expert Q&A / RAG Node
def qa_node(state: AgentState) -> Dict[str, Any]:
    query = state["query"]
    logger.info(f"Running Expert Q&A (RAG) Node for: '{query}'")
    
    # Retrieve documents
    q = query.lower()

    if any(x in q for x in [
        "list",
        "appendix",
        "table",
        "all",
        "every"
    ]):
        top_k = 40
        rerank_top_n = 12
    else:
        top_k = 15
        rerank_top_n = 5

    chunks = rag_engine.retrieve(
        query=query,
        top_k=top_k,
        rerank_top_n=rerank_top_n,
        doc_filter=state.get("metadata_filter")
    )
    
    context_str = ""
    references = []
    for idx, chunk in enumerate(chunks):
        source = chunk["metadata"]["source"]
        page = chunk["metadata"]["page"]
        content = chunk["content"]
        conf = chunk["confidence"]
        
        context_str += f"[Ref {idx+1}] Source: {source}, Page: {page}\nText: {content}\n\n"
        references.append({
            "source": source,
            "page": int(page),
            "content": content,
            "confidence": float(conf)
        })
        
    # Generate response
    prompt = (
        f"You are an Industrial Expert Q&A System. Answer the user's question based on the retrieved documents.\n\n"
        f"Retrieved Context:\n{context_str if context_str else 'No relevant manuals found.'}\n\n"
        f"Question: {query}\n\n"
        f"Instructions:\n"
        f"1. Synthesize a concise, accurate engineering response.\n"
        f"2. Cite your sources directly in the text (e.g. '[Turbine_Manual.pdf, Page 4]'). Only cite from the retrieved context.\n"
        f"3. If the answer cannot be found in the context, state that clearly."
    )
    
    system_prompt = "You are an expert Q&A agent for industrial manuals and SOPs."
    answer = llm_service.generate(prompt=prompt, system_prompt=system_prompt)
    
    # Calculate confidence score using the 5-factor formula
    # Factor 1: Retrieval Quality (30%)
    retrieval_quality = (
        sum(c.get("retrieval_score", 0.0) for c in chunks)
        / len(chunks)
        if chunks else 0.0
    )
    
    # Factor 2: Reranker Quality (25%)
    reranker_quality = (
        sum(c.get("confidence", 0.0) for c in chunks)
        / len(chunks)
        if chunks else 0.0
    )
    
    # Factor 3: Evidence Strength (20%)
    if len(references) >= 5:
        evidence_strength = 1.0
    elif len(references) >= 3:
        evidence_strength = 0.8
    elif len(references) >= 2:
        evidence_strength = 0.6
    elif len(references) == 1:
        evidence_strength = 0.4
    else:
        evidence_strength = 0.0
        
    # Factor 4: Answer Completeness (15%)
    answer_completeness = min(
        len(answer.split()) / 100,
        1.0
    )
    
    # Factor 5: Query Match (10%)
    q = query.lower()
    if any(k in q for k in [
        "list",
        "all",
        "trace",
        "complete",
        "every"
    ]):
        query_match = 1.0 if len(references) >= 3 else 0.6
    else:
        query_match = 1.0
        
    # Final Score Calculation
    weights = {
        "retrieval": 0.30,
        "reranker": 0.25,
        "evidence": 0.20,
        "answer": 0.15,
        "query": 0.10
    }
    
    score = (
        weights["retrieval"] * retrieval_quality +
        weights["reranker"] * reranker_quality +
        weights["evidence"] * evidence_strength +
        weights["answer"] * answer_completeness +
        weights["query"] * query_match
    )
    
    confidence = round(min(max(score, 0.0), 1.0), 2)
    
    logger.info(
        f"Confidence Score Components - "
        f"Retrieval Quality: {retrieval_quality:.4f}, "
        f"Reranker Quality: {reranker_quality:.4f}, "
        f"Evidence Strength: {evidence_strength:.4f}, "
        f"Answer Completeness: {answer_completeness:.4f}, "
        f"Query Match: {query_match:.4f} -> "
        f"Final Confidence: {confidence:.4f}"
    )
        
    response_data = {
        "answer": answer,
        "confidence_score": confidence,
        "references": references
    }
    
    return {"response": response_data}

# 3. Root Cause Analysis Node
def rca_node(state: AgentState) -> Dict[str, Any]:
    query = state["query"]
    logger.info(f"Running RCA Node for: '{query}'")
    
    # Parse equipment and component if possible
    eq_match = re.search(r'(pmp-\d+|turb-\d+|blr-\d+)', query, re.IGNORECASE)
    comp_match = re.search(r'(bearing|impeller|seal|coupling|rotor|blade)', query, re.IGNORECASE)
    
    req = RCARequest(
        incident_description=query,
        equipment_id=eq_match.group(1).upper() if eq_match else None,
        component_name=comp_match.group(1).lower() if comp_match else None,
        metadata_filter=state.get("metadata_filter")
    )
    
    res = run_rca_agent(req)
    return {"response": res.model_dump()}

# 4. Compliance Auditing Node
def compliance_node(state: AgentState) -> Dict[str, Any]:
    query = state["query"]
    logger.info(f"Running Compliance Audit Node for: '{query}'")
    
    # Standard selection
    std = "ALL"
    if "factory act" in query.lower(): std = "Factory Act"
    elif "oisd" in query.lower(): std = "OISD"
    
    req = ComplianceRequest(
        text_to_check=query,
        guideline_type=std
    )
    
    res = run_compliance_agent(req)
    return {"response": res.model_dump()}

# 5. Predictive Maintenance Node
def predictive_node(state: AgentState) -> Dict[str, Any]:
    query = state["query"]
    logger.info(f"Running Predictive Maintenance Node for: '{query}'")
    
    # Extract numeric values from query using regex
    # temperature: temp 90C, 90 C
    # vibration: vib 5.2, 5.2 mm/s
    # pressure: pres 45, 45 psi
    # operating hours: hours 4000, 4000 hrs
    
    def extract_val(pattern: str, text: str, default: float) -> float:
        match = re.search(pattern, text, re.IGNORECASE)
        return float(match.group(1)) if match else default

    temp = extract_val(r'(?:temp|temperature)\D*(\d+(?:\.\d+)?)', query, 75.0)
    vib = extract_val(r'(?:vib|vibration)\D*(\d+(?:\.\d+)?)', query, 2.5)
    pres = extract_val(r'(?:pressure|press|psi)\D*(\d+(?:\.\d+)?)', query, 40.0)
    hours = extract_val(r'(?:hour|hrs|operating)\D*(\d+(?:\.\d+)?)', query, 2000.0)
    maint = extract_val(r'(?:maint|maintenance|index)\D*(0\.\d+|1\.0|0)', query, 0.2)
    fails = int(extract_val(r'(?:fail|failure|records)\D*(\d+)', query, 0.0))
    
    req = PredictRequest(
        temperature=temp,
        vibration=vib,
        pressure=pres,
        operating_hours=hours,
        maintenance_history_index=maint,
        failure_records_count=fails
    )
    
    res = pm_model.predict(req.model_dump())
    return {"response": res}

# 6. Lessons Learned Node
def lessons_node(state: AgentState) -> Dict[str, Any]:
    query = state["query"]
    logger.info(f"Running Lessons Learned Node for: '{query}'")
    
    eq_type = None
    if "pump" in query.lower(): eq_type = "Centrifugal Pump"
    elif "turbine" in query.lower(): eq_type = "Steam Turbine"
    elif "boiler" in query.lower(): eq_type = "Boiler"
    
    req = LessonsLearnedRequest(
        new_incident_description=query,
        equipment_type=eq_type
    )
    
    res = run_lessons_learned_agent(req)
    return {"response": res.model_dump()}

# Define Router decision
def decide_route(state: AgentState) -> str:
    return state["agent_route"]

# Build StateGraph
workflow = StateGraph(AgentState)

# Add Nodes
workflow.add_node("router", router_node)
workflow.add_node("qa", qa_node)
workflow.add_node("rca", rca_node)
workflow.add_node("compliance", compliance_node)
workflow.add_node("predictive", predictive_node)
workflow.add_node("lessons", lessons_node)

# Set Entry Point
workflow.set_entry_point("router")

# Add Conditional Edges
workflow.add_conditional_edges(
    "router",
    decide_route,
    {
        "qa": "qa",
        "rca": "rca",
        "compliance": "compliance",
        "predictive": "predictive",
        "lessons": "lessons"
    }
)

# Connect Nodes to END
workflow.add_edge("qa", END)
workflow.add_edge("rca", END)
workflow.add_edge("compliance", END)
workflow.add_edge("predictive", END)
workflow.add_edge("lessons", END)

# Compile LangGraph Orchestrator
orchestrator_graph = workflow.compile()

def query_orchestrator(query: str, metadata_filter: Optional[str] = None) -> Dict[str, Any]:
    """
    Executes the orchestrator graph with a query.
    """
    initial_state = {
        "query": query,
        "metadata_filter": metadata_filter,
        "agent_route": "qa",
        "response": {},
        "history": []
    }
    
    output = orchestrator_graph.invoke(initial_state)
    return {
        "route": output["agent_route"],
        "response": output["response"]
    }
