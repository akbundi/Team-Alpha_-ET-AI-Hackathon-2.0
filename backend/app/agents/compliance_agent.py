import logging
from typing import Dict, Any
from app.models import ComplianceRequest, ComplianceResponse
from app.rag import rag_engine
from app.llm import llm_service

logger = logging.getLogger(__name__)

def run_compliance_agent(req: ComplianceRequest) -> ComplianceResponse:
    """
    Audits a safety procedure, SOP, or report against regulations (Factory Act, OISD, safety guidelines).
    """
    logger.info(f"Compliance Agent running audits for type: {req.guideline_type}")
    
    # 1. Retrieve safety guidelines from ChromaDB
    # We retrieve standard regulations based on key topics in the procedure
    search_keywords = "safety regulations machine guarding hazard lock out tag out LOTO pressure vessel electrical grounding Factory Act OISD"
    
    # Adapt query slightly based on standard type
    if req.guideline_type != "ALL":
        search_keywords = f"{req.guideline_type} {search_keywords}"
        
    logger.info(f"Retrieving compliance rules using terms: '{search_keywords}'")
    retrieved_rules = rag_engine.retrieve(
        query=search_keywords,
        top_k=8,
        rerank_top_n=4
    )
    
    rules_context = ""
    for idx, chunk in enumerate(retrieved_rules):
        rules_context += f"[Reg {idx+1}] Source: {chunk['metadata']['source']}, Page: {chunk['metadata']['page']}\nText: {chunk['content']}\n\n"
        
    # 2. Construct prompt
    prompt = (
        f"You are an Industrial Safety Inspector and Compliance Auditor.\n\n"
        f"Compare the following Standard Operating Procedure (SOP) / maintenance log against standard regulations:\n"
        f"--- START SOP CONTENT ---\n"
        f"{req.text_to_check}\n"
        f"--- END SOP CONTENT ---\n\n"
        f"Here are the relevant statutory regulations (Factory Act, OISD, and OSHA safety standards) retrieved from our database:\n"
        f"{rules_context if rules_context else 'No statutory guidelines found in database. Auditing against general industrial safety standards.'}\n\n"
        f"Task:\n"
        f"1. Audit the SOP and identify any missing safety checks, regulatory violations, or hazards.\n"
        f"2. Calculate a compliance score (0-100) where 100 is fully compliant. Deduct heavily for missing guards, LOTO procedures, or pressure check logs.\n"
        f"3. Detail each violation (Severity: CRITICAL, MAJOR, MINOR), listing the section/clause violated, description, and remediation.\n"
        f"4. Generate a clean, audit-ready markdown report ('audit_ready_report') that summarizes your inspection. Make it look formal and structured."
    )
    
    system_prompt = "You are a Compliance Intelligence AI Agent specialized in industrial safety compliance auditing."
    
    # 3. Call LLM Service
    res = llm_service.generate_structured(
        prompt=prompt,
        response_model=ComplianceResponse,
        system_prompt=system_prompt
    )
    
    return res
