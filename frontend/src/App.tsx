import React, { useState, useEffect } from 'react';
import {
  Activity,
  MessageSquare,
  Search,
  AlertTriangle,
  ShieldCheck,
  TrendingUp,
  Database,
  BookOpen,
  Network
} from 'lucide-react';
import "highlight.js/styles/github.css";

import DashboardView from './DashboardView';
import IngestionView from './IngestionView';
import ChatView from './ChatView';
import EntityView from './EntityView';
import RcaView from './RcaView';
import ComplianceView from './ComplianceView';
import PredictiveView from './PredictiveView';
import LessonsView from './LessonsView';
import KnowledgeGraphView from './KnowledgeGraphView';

// API Configurations
const API_BASE = 'http://localhost:8000';

type Tab = 'dashboard' | 'graph' | 'ingestion' | 'qa' | 'entity' | 'rca' | 'compliance' | 'predictive' | 'lessons';

interface SystemStatus {
  status: string;
  llm_mode: string;
  tesseract_ocr: string;
  embedding_model: string;
  reranker_model: string;
  xgboost_model: string;
  chroma_collection: string;
}

interface DocumentItem {
  document_name: string;
  page_count: number;
  max_page: number;
}

interface ChatMessage {
  sender: 'user' | 'agent';
  text: string;
  confidence?: number;
  references?: Array<{
    source: string;
    page: number;
    content: string;
    confidence: number;
  }>;
  route?: string;
}

export default function App() {
  const [activeTab, setActiveTab] = useState<Tab>('dashboard');
  const [sysStatus, setSysStatus] = useState<SystemStatus | null>(null);
  const [documents, setDocuments] = useState<DocumentItem[]>([]);
  const [message, setMessage] = useState<{ text: string; type: 'success' | 'error' } | null>(null);

  // Load Status and Documents on startup
  useEffect(() => {
    fetchStatus();
    fetchDocuments();
  }, []);

  const fetchStatus = async () => {
    try {
      const res = await fetch(`${API_BASE}/status`);
      if (res.ok) {
        const data = await res.json();
        setSysStatus(data);
      }
    } catch (e) {
      console.error("Error fetching server status:", e);
    }
  };

  const fetchDocuments = async () => {
    try {
      const res = await fetch(`${API_BASE}/documents`);
      if (res.ok) {
        const data = await res.json();
        setDocuments(data);
      }
    } catch (e) {
      console.error("Error fetching documents:", e);
    }
  };

  const showMsg = (text: string, type: 'success' | 'error' = 'success') => {
    setMessage({ text, type });
    setTimeout(() => setMessage(null), 5000);
  };



  // ==========================================
  // VIEW: INGESTION
  // ==========================================
  const [file, setFile] = useState<File | null>(null);
  const [forceOcr, setForceOcr] = useState(false);
  const [ingesting, setIngesting] = useState(false);
  const [ingestionResult, setIngestionResult] = useState<any>(null);

  const handleFileChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    if (e.target.files && e.target.files.length > 0) {
      setFile(e.target.files[0]);
    }
  };

  const handleIngest = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!file) return;

    setIngesting(true);
    const formData = new FormData();
    formData.append('file', file);
    formData.append('force_ocr', String(forceOcr));

    try {
      const res = await fetch(`${API_BASE}/ingest`, {
        method: 'POST',
        body: formData,
      });

      if (res.ok) {
        const data = await res.json();
        setIngestionResult(data);
        showMsg("Document ingested successfully!");
        fetchDocuments();
        fetchStatus();
      } else {
        const err = await res.json();
        showMsg(err.detail || "Ingestion failed.", 'error');
      }
    } catch (e) {
      showMsg("Backend connection failed.", 'error');
    } finally {
      setIngesting(false);
      setFile(null);
    }
  };

  const handleDeleteDoc = async (docName: string) => {
    if (!confirm(`Are you sure you want to delete ${docName} from the index?`)) return;
    try {
      const res = await fetch(`${API_BASE}/documents/${docName}`, { method: 'DELETE' });
      if (res.ok) {
        showMsg(`Document ${docName} deleted.`);
        fetchDocuments();
      }
    } catch (e) {
      showMsg("Failed to delete document.", 'error');
    }
  };



  // ==========================================
  // VIEW: EXPERT Q&A / CHAT
  // ==========================================
  const [query, setQuery] = useState('');
  const [chatLog, setChatLog] = useState<ChatMessage[]>([]);
  const [chatLoading, setChatLoading] = useState(false);
  const [filterDoc, setFilterDoc] = useState('');
  const [topK, setTopK] = useState(15);
  const [rerankTopN, setRerankTopN] = useState(5);

  const handleChatSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!query.trim()) return;

    const userMsg = query;
    setQuery('');
    setChatLog(prev => [...prev, { sender: 'user', text: userMsg }]);
    setChatLoading(true);

    try {
      const res = await fetch(`${API_BASE}/query`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          query: userMsg,
          doc_filter: filterDoc || null,
          top_k: topK,
          rerank_top_n: rerankTopN
        })
      });

      if (res.ok) {
        const data = await res.json();
        
        let replyText = "";
        let conf = 0.8;
        let refs = [];
        let agentRoute = data.route;
        
        const responseData = data.response;
        
        // Handle variations based on route return structure
        if (agentRoute === 'qa') {
          replyText = responseData.answer;
          conf = responseData.confidence_score;
          refs = responseData.references;
        } else if (agentRoute === 'rca') {
          replyText = `### ROOT CAUSE DIAGNOSIS REPORT\n\n`;
          replyText += `**Overall Diagnostic Confidence**: ${(responseData.overall_confidence * 100).toFixed(1)}%\n\n`;
          replyText += `#### Probable Failure Causes:\n`;
          responseData.probable_causes.forEach((c: any) => {
            replyText += `- **${c.cause}** (${(c.probability*100).toFixed(0)}% probability):\n  *${c.explanation}*\n`;
          });
          replyText += `\n#### Immediate Corrective Actions (CAPA):\n`;
          responseData.corrective_actions.forEach((a: any) => {
            replyText += `- [${a.priority}] **${a.action}**: ${a.description}\n`;
          });
          replyText += `\n#### Preventive recommendations:\n`;
          responseData.preventive_actions.forEach((a: any) => {
            replyText += `- ${a}\n`;
          });
          conf = responseData.overall_confidence;
          refs = responseData.citations;
        } else if (agentRoute === 'compliance') {
          replyText = responseData.audit_ready_report;
          conf = responseData.compliance_score / 100.0;
          refs = [];
        } else if (agentRoute === 'lessons') {
          replyText = `### Lessons Learned Incident Report\n\n`;
          replyText += `**Summary**: ${responseData.new_incident_summary}\n\n`;
          replyText += `#### Similar Historical Incidents:\n`;
          responseData.similar_historical_events.forEach((e: any) => {
            replyText += `- **${e.source_doc} (Page ${e.page})** [Similarity: ${(e.similarity_score*100).toFixed(0)}%]:\n  * **Summary**: ${e.summary}\n  * **Failure Mode**: ${e.failure_mode}\n  * **Root Cause**: ${e.root_cause}\n  * **Recommendation**: ${e.recomm_action}\n`;
          });
          replyText += `\n#### Recurring Failure Trends:\n`;
          responseData.recurring_patterns.forEach((p: any) => {
            replyText += `- ${p}\n`;
          });
          replyText += `\n#### Preventive Recommendations:\n`;
          responseData.preventive_measures.forEach((m: any) => {
            replyText += `- ${m}\n`;
          });
          conf = responseData.confidence_score;
          refs = [];
        } else if (agentRoute === 'predictive') {
          replyText = `### Predictive Maintenance Alert\n\n`;
          replyText += `**Asset Failure Probability**: ${(responseData.failure_probability*100).toFixed(1)}%\n`;
          replyText += `**Status**: **${responseData.status}**\n\n`;
          replyText += `#### Critical Maintenance Actions:\n`;
          responseData.recommendations.forEach((r: any) => {
            replyText += `- ${r}\n`;
          });
          conf = 1.0 - responseData.failure_probability;
          refs = [];
        }

        setChatLog(prev => [...prev, {
          sender: 'agent',
          text: replyText,
          confidence: conf,
          references: refs,
          route: agentRoute
        }]);
      } else {
        setChatLog(prev => [...prev, {
          sender: 'agent',
          text: "Server error occurred while executing multi-agent graph query."
        }]);
      }
    } catch (e) {
      setChatLog(prev => [...prev, {
        sender: 'agent',
        text: "Could not connect to the backend LangGraph server. Verify the server is running."
      }]);
    } finally {
      setChatLoading(false);
    }
  };



  // ==========================================
  // VIEW: ENTITY EXTRACTION
  // ==========================================
  const [extractText, setExtractText] = useState('');
  const [extractLoading, setExtractLoading] = useState(false);
  const [extractedEntities, setExtractedEntities] = useState<any[]>([]);

  const handleExtract = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!extractText.trim()) return;

    setExtractLoading(true);
    try {
      const res = await fetch(`${API_BASE}/extract`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ text: extractText })
      });

      if (res.ok) {
        const data = await res.json();
        setExtractedEntities(data.entities || []);
        showMsg("Entities extracted successfully!");
      }
    } catch (e) {
      showMsg("Backend connection failed.", 'error');
    } finally {
      setExtractLoading(false);
    }
  };



  // ==========================================
  // VIEW: ROOT CAUSE ANALYSIS (RCA) AGENT
  // ==========================================
  const [rcaDesc, setRcaDesc] = useState('');
  const [rcaEqId, setRcaEqId] = useState('');
  const [rcaComp, setRcaComp] = useState('');
  const [rcaLoading, setRcaLoading] = useState(false);
  const [rcaResult, setRcaResult] = useState<any>(null);

  const handleRca = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!rcaDesc.trim()) return;

    setRcaLoading(true);
    try {
      const res = await fetch(`${API_BASE}/query`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          query: `Analyze root cause for equipment ${rcaEqId || 'unknown'} component ${rcaComp || 'unknown'}: ${rcaDesc}`
        })
      });

      if (res.ok) {
        const data = await res.json();
        setRcaResult(data.response);
        showMsg("RCA completed!");
      }
    } catch (e) {
      showMsg("Backend connection failed.", 'error');
    } finally {
      setRcaLoading(false);
    }
  };



  // ==========================================
  // VIEW: COMPLIANCE AUDITOR
  // ==========================================
  const [compText, setCompText] = useState('');
  const [compLoading, setCompLoading] = useState(false);
  const [compResult, setCompResult] = useState<any>(null);

  const handleCompliance = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!compText.trim()) return;

    setCompLoading(true);
    try {
      const res = await fetch(`${API_BASE}/query`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          query: `Verify compliance for this procedure: ${compText}`
        })
      });

      if (res.ok) {
        const data = await res.json();
        setCompResult(data.response);
        showMsg("Audit completed!");
      }
    } catch (e) {
      showMsg("Backend connection failed.", 'error');
    } finally {
      setCompLoading(false);
    }
  };



  // ==========================================
  // VIEW: PREDICTIVE MAINTENANCE
  // ==========================================
  const [telemetry, setTelemetry] = useState({
    temperature: 80.0,
    vibration: 2.5,
    pressure: 40.0,
    operating_hours: 2500.0,
    maintenance_history_index: 0.25,
    failure_records_count: 0
  });

  const [predResult, setPredResult] = useState<any>(null);
  const [predLoading, setPredLoading] = useState(false);

  // Run prediction on slider change
  useEffect(() => {
    runPredict();
  }, [telemetry]);

  const runPredict = async () => {
    setPredLoading(true);
    try {
      const res = await fetch(`${API_BASE}/predict`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(telemetry)
      });
      if (res.ok) {
        const data = await res.json();
        setPredResult(data);
      }
    } catch (e) {
      console.error("Prediction API failed:", e);
    } finally {
      setPredLoading(false);
    }
  };

  const handleSliderChange = (feat: string, val: number) => {
    setTelemetry(prev => ({ ...prev, [feat]: val }));
  };



  // ==========================================
  // VIEW: LESSONS LEARNED AGENT
  // ==========================================
  const [lessDesc, setLessDesc] = useState('');
  const [lessEqType, setLessEqType] = useState('Centrifugal Pump');
  const [lessLoading, setLessLoading] = useState(false);
  const [lessResult, setLessResult] = useState<any>(null);

  const handleLessons = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!lessDesc.trim()) return;

    setLessLoading(true);
    try {
      const res = await fetch(`${API_BASE}/query`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          query: `Summarize historical patterns and lessons learned for this new incident: ${lessDesc}. Equipment type: ${lessEqType}`
        })
      });

      if (res.ok) {
        const data = await res.json();
        setLessResult(data.response);
        showMsg("Lessons retrieved!");
      }
    } catch (e) {
      showMsg("Backend connection failed.", 'error');
    } finally {
      setLessLoading(false);
    }
  };



  return (
    <div className="app-container">
      {/* Sidebar Navigation */}
      <aside className="sidebar">
        <div className="brand">
          <div className="brand-logo">KI</div>
          <span className="brand-name">Industrial Intelligence</span>
        </div>

        <ul className="nav-menu">
          <li
            className={`nav-item ${activeTab === 'dashboard' ? 'active' : ''}`}
            onClick={() => setActiveTab('dashboard')}
          >
            <Activity className="nav-icon" />
            Dashboard Overview
          </li>
          <li
            className={`nav-item ${activeTab === 'graph' ? 'active' : ''}`}
            onClick={() => setActiveTab('graph')}
          >
            <Network className="nav-icon" />
            Knowledge Graph
          </li>
          <li
            className={`nav-item ${activeTab === 'ingestion' ? 'active' : ''}`}
            onClick={() => setActiveTab('ingestion')}
          >
            <Database className="nav-icon" />
            Ingestion Center
          </li>
          <li
            className={`nav-item ${activeTab === 'qa' ? 'active' : ''}`}
            onClick={() => setActiveTab('qa')}
          >
            <MessageSquare className="nav-icon" />
            Expert Q&A / Chat
          </li>
          <li
            className={`nav-item ${activeTab === 'entity' ? 'active' : ''}`}
            onClick={() => setActiveTab('entity')}
          >
            <Search className="nav-icon" />
            Entity Extraction
          </li>
          <li
            className={`nav-item ${activeTab === 'rca' ? 'active' : ''}`}
            onClick={() => setActiveTab('rca')}
          >
            <AlertTriangle className="nav-icon" />
            Root Cause Agent
          </li>
          <li
            className={`nav-item ${activeTab === 'compliance' ? 'active' : ''}`}
            onClick={() => setActiveTab('compliance')}
          >
            <ShieldCheck className="nav-icon" />
            Compliance Agent
          </li>
          <li
            className={`nav-item ${activeTab === 'predictive' ? 'active' : ''}`}
            onClick={() => setActiveTab('predictive')}
          >
            <TrendingUp className="nav-icon" />
            Predictive Telemetry
          </li>
          <li
            className={`nav-item ${activeTab === 'lessons' ? 'active' : ''}`}
            onClick={() => setActiveTab('lessons')}
          >
            <BookOpen className="nav-icon" />
            Lessons Learned Agent
          </li>
        </ul>

        <div className="sidebar-footer">
          <div className="status-badge">
            <div className="status-dot"></div>
            <span>Platform Online</span>
          </div>
        </div>
      </aside>

      {/* Main Panel Content */}
      <main className="main-content">
        <header className="page-header">
          <div className="page-title">
            <h1 style={{ textTransform: 'capitalize' }}>
              {activeTab === 'dashboard' ? 'Knowledge Overview' : activeTab === 'graph' ? 'Knowledge Graph Explorer' : activeTab.replace(/_/g, ' ') + ' Agent'}
            </h1>
            <p>
              {activeTab === 'dashboard' && 'Statutory checks, asset telemetry risk alerts, and knowledge indices.'}
              {activeTab === 'graph' && 'Explore Neo4j equipment entity graphs, failure histories, and vector-graph bridges.'}
              {activeTab === 'ingestion' && 'Process scanned & digital PDFs using PyMuPDF and Tesseract OCR pipelines.'}
              {activeTab === 'qa' && 'Query manuals and SOPs using LangGraph, ChromaDB vectors, and BGE Rerank.'}
              {activeTab === 'entity' && 'Analyze repair notes to extract structured equipment components and date entities.'}
              {activeTab === 'rca' && 'Perform engineering forensics and generate CAPA recommendations on failures.'}
              {activeTab === 'compliance' && 'Verify maintenance reports against statutory rules (Factory Act / OISD standards).'}
              {activeTab === 'predictive' && 'Input sensor metrics to query real-time failure forecasts from XGBoost & SHAP.'}
              {activeTab === 'lessons' && 'Identify systemic failure patterns from historical accident catalogs.'}
            </p>
          </div>
        </header>

        {/* User alerts indicator */}
        {message && (
          <div
            style={{
              padding: '12px 18px',
              borderRadius: '8px',
              marginBottom: '20px',
              backgroundColor: message.type === 'success' ? 'rgba(16, 185, 129, 0.15)' : 'rgba(244, 63, 94, 0.15)',
              border: `1.5px solid ${message.type === 'success' ? 'var(--color-success)' : 'var(--color-danger)'}`,
              color: message.type === 'success' ? 'var(--color-success)' : 'var(--color-danger)',
              fontWeight: 600,
              display: 'flex',
              alignItems: 'center',
              gap: '10px'
            }}
          >
            <AlertTriangle style={{ width: '16px', height: '16px' }} />
            {message.text}
          </div>
        )}

        {/* Tab switcher */}
        {activeTab === 'dashboard' && (
          <DashboardView
            documents={documents}
            sysStatus={sysStatus}
            handleDeleteDoc={handleDeleteDoc}
          />
        )}
        {activeTab === 'graph' && (
          <KnowledgeGraphView
            apiBase={API_BASE}
            showMsg={showMsg}
          />
        )}
        {activeTab === 'ingestion' && (
          <IngestionView
            file={file}
            handleFileChange={handleFileChange}
            forceOcr={forceOcr}
            setForceOcr={setForceOcr}
            ingesting={ingesting}
            ingestionResult={ingestionResult}
            handleIngest={handleIngest}
          />
        )}
        {activeTab === 'qa' && (
          <ChatView
            query={query}
            setQuery={setQuery}
            chatLog={chatLog}
            chatLoading={chatLoading}
            filterDoc={filterDoc}
            setFilterDoc={setFilterDoc}
            topK={topK}
            setTopK={setTopK}
            rerankTopN={rerankTopN}
            setRerankTopN={setRerankTopN}
            documents={documents}
            handleChatSubmit={handleChatSubmit}
          />
        )}
        {activeTab === 'entity' && (
          <EntityView
            extractText={extractText}
            setExtractText={setExtractText}
            extractLoading={extractLoading}
            extractedEntities={extractedEntities}
            handleExtract={handleExtract}
          />
        )}
        {activeTab === 'rca' && (
          <RcaView
            rcaDesc={rcaDesc}
            setRcaDesc={setRcaDesc}
            rcaEqId={rcaEqId}
            setRcaEqId={setRcaEqId}
            rcaComp={rcaComp}
            setRcaComp={setRcaComp}
            rcaLoading={rcaLoading}
            rcaResult={rcaResult}
            handleRca={handleRca}
          />
        )}
        {activeTab === 'compliance' && (
          <ComplianceView
            compText={compText}
            setCompText={setCompText}
            compLoading={compLoading}
            compResult={compResult}
            handleCompliance={handleCompliance}
          />
        )}
        {activeTab === 'predictive' && (
          <PredictiveView
            telemetry={telemetry}
            predResult={predResult}
            predLoading={predLoading}
            handleSliderChange={handleSliderChange}
          />
        )}
        {activeTab === 'lessons' && (
          <LessonsView
            lessDesc={lessDesc}
            setLessDesc={setLessDesc}
            lessEqType={lessEqType}
            setLessEqType={setLessEqType}
            lessLoading={lessLoading}
            lessResult={lessResult}
            handleLessons={handleLessons}
          />
        )}
      </main>
    </div>
  );
}
