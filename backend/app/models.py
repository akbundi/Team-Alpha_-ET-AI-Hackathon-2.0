from pydantic import BaseModel, Field
from typing import List, Optional, Dict, Any

# Entity Extraction Structured JSON Models
class IndustrialEntity(BaseModel):
    equipment_id: Optional[str] = Field(None, description="Unique identifier/tag of the equipment (e.g., PMP-102, TURB-04, BLR-99)")
    work_order_id: Optional[str] = Field(None, description="Unique identifier/tag of the associated Work Order (e.g., WO-2026-4501)")
    component_name: Optional[str] = Field(None, description="Specific component name (e.g., impeller, ball bearing, mechanical seal, gasket)")
    failure_type: Optional[str] = Field(None, description="Type/Mode of mechanical or electrical failure (e.g., cavitation, fatigue crack, short circuit, corrosion)")
    technician: Optional[str] = Field(None, description="Name of the inspecting technician or engineer")
    inspection_date: Optional[str] = Field(None, description="Date when the inspection or maintenance took place")
    maintenance_action: Optional[str] = Field(None, description="Specific corrective action taken (e.g., replaced oil filter, aligned shaft, welded crack)")
    regulatory_references: List[str] = Field(default=[], description="Referenced safety codes, regulations, or standards (e.g., Factory Act Sec 21, OISD-189)")
    location: Optional[str] = Field(None, description="Physical location or plant unit (e.g., Utility Block, Cooling Tower 2, Refinery Section B)")
    cause: Optional[str] = Field(None, description="Root cause of the mechanical/electrical failure (e.g., misalignment, lubrication failure)")
    recommendation: Optional[str] = Field(None, description="Specific preventive recommendation or suggestion (e.g., implement monthly greasing schedule)")
    manufacturer: Optional[str] = Field(None, description="Manufacturer/Brand of the equipment or component (e.g., Siemens, Sulzer, Flowserve)")

class EntityExtractionResult(BaseModel):
    entities: List[IndustrialEntity] = Field(default=[], description="List of extracted industrial entities from the text")

# Predictive Maintenance
class PredictRequest(BaseModel):
    temperature: float = Field(..., ge=0.0, description="Operating temperature in degrees Celsius")
    vibration: float = Field(..., ge=0.0, description="Vibration speed in mm/s")
    pressure: float = Field(..., ge=0.0, description="Operating pressure in psi")
    operating_hours: float = Field(..., ge=0.0, description="Accumulated operating hours")
    maintenance_history_index: float = Field(..., ge=0.0, le=1.0, description="Index of maintenance status, 0.0 (recent) to 1.0 (long overdue)")
    failure_records_count: int = Field(..., ge=0, description="Number of historical failures recorded for this asset")

class FeatureContribution(BaseModel):
    feature: str
    value: float
    shap_value: float

class PredictResponse(BaseModel):
    failure_probability: float
    status: str  # HEALTHY, WARN, CRITICAL
    contributions: List[FeatureContribution]
    recommendations: List[str]

# RAG & Citations
class RAGQueryRequest(BaseModel):
    query: str
    doc_filter: Optional[str] = None
    top_k: int = 15
    rerank_top_n: int = 5

class ReferenceItem(BaseModel):
    source: str
    page: int
    content: str
    confidence: float

class RAGQueryResponse(BaseModel):
    answer: str
    confidence_score: float
    references: List[ReferenceItem]

# Root Cause Analysis (RCA) Agent
class RCARequest(BaseModel):
    incident_description: str
    equipment_id: Optional[str] = None
    component_name: Optional[str] = None
    metadata_filter: Optional[str] = None

class ProbableCause(BaseModel):
    cause: str
    probability: float  # 0.0 to 1.0
    explanation: str

class CorrectiveAction(BaseModel):
    action: str
    priority: str  # HIGH, MEDIUM, LOW
    description: str

class RCAResponse(BaseModel):
    probable_causes: List[ProbableCause]
    corrective_actions: List[CorrectiveAction]
    preventive_actions: List[str]
    citations: List[ReferenceItem]
    overall_confidence: float

# Compliance Intelligence Agent
class ComplianceRequest(BaseModel):
    text_to_check: str
    guideline_type: Optional[str] = "ALL"  # Factory Act, OISD, Safety Guidelines, ALL

class ViolationDetail(BaseModel):
    section: str
    clause: str
    severity: str  # CRITICAL, MAJOR, MINOR
    description: str
    remediation: str

class ComplianceResponse(BaseModel):
    compliance_score: float  # 0.0 to 100.0
    violations: List[ViolationDetail]
    explanation: str
    audit_ready_report: str

# Lessons Learned Agent
class LessonsLearnedRequest(BaseModel):
    new_incident_description: str
    equipment_type: Optional[str] = None

class HistoricalIncident(BaseModel):
    source_doc: str
    page: int
    summary: str
    failure_mode: str
    root_cause: str
    recomm_action: str
    similarity_score: float

class LessonsLearnedResponse(BaseModel):
    new_incident_summary: str
    similar_historical_events: List[HistoricalIncident]
    recurring_patterns: List[str]
    preventive_measures: List[str]
    confidence_score: float
