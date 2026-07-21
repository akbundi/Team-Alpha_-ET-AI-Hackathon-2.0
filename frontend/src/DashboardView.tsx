
import {
  Activity,
  FileText,
  Settings,
  ShieldCheck,
  Database,
  Trash2,
  BookOpen
} from 'lucide-react';

interface DocumentItem {
  document_name: string;
  page_count: number;
  max_page: number;
}

interface SystemStatus {
  status: string;
  llm_mode: string;
  tesseract_ocr: string;
  embedding_model: string;
  reranker_model: string;
  xgboost_model: string;
  chroma_collection: string;
}

interface DashboardViewProps {
  documents: DocumentItem[];
  sysStatus: SystemStatus | null;
  handleDeleteDoc: (docName: string) => Promise<void> | void;
}

export default function DashboardView({
  documents,
  sysStatus,
  handleDeleteDoc
}: DashboardViewProps) {
  const totalDocs = documents.length;
  const totalPages = documents.reduce((acc, doc) => acc + doc.page_count, 0);

  return (
    <div className="dashboard-view">
      <div className="grid-4" style={{ marginBottom: '28px' }}>
        <div className="card">
          <div className="card-title" style={{ fontSize: '0.9rem', color: 'var(--text-muted)' }}>
            <Database className="nav-icon" style={{ color: 'var(--color-primary)' }} />
            INDEXED MANUALS
          </div>
          <div style={{ fontSize: '2.2rem', fontWeight: 700, marginTop: '8px', color: 'var(--text-title)' }}>
            {totalDocs}
          </div>
          <p style={{ fontSize: '0.8rem', color: 'var(--text-muted)', marginTop: '4px' }}>
            Active documents in ChromaDB
          </p>
        </div>

        <div className="card">
          <div className="card-title" style={{ fontSize: '0.9rem', color: 'var(--text-muted)' }}>
            <BookOpen className="nav-icon" style={{ color: 'var(--color-secondary)' }} />
            KNOWLEDGE PAGES
          </div>
          <div style={{ fontSize: '2.2rem', fontWeight: 700, marginTop: '8px', color: 'var(--text-title)' }}>
            {totalPages}
          </div>
          <p style={{ fontSize: '0.8rem', color: 'var(--text-muted)', marginTop: '4px' }}>
            Total indexed text segments
          </p>
        </div>

        <div className="card">
          <div className="card-title" style={{ fontSize: '0.9rem', color: 'var(--text-muted)' }}>
            <ShieldCheck className="nav-icon" style={{ color: 'var(--color-success)' }} />
            AVG COMPLIANCE
          </div>
          <div style={{ fontSize: '2.2rem', fontWeight: 700, marginTop: '8px', color: 'var(--text-title)' }}>
            86.4%
          </div>
          <p style={{ fontSize: '0.8rem', color: 'var(--text-muted)', marginTop: '4px' }}>
            Statutory safety checklist score
          </p>
        </div>

        <div className="card">
          <div className="card-title" style={{ fontSize: '0.9rem', color: 'var(--text-muted)' }}>
            <Activity className="nav-icon" style={{ color: 'var(--color-danger)' }} />
            ASSET ALERTS
          </div>
          <div style={{ fontSize: '2.2rem', fontWeight: 700, marginTop: '8px', color: 'var(--text-title)' }}>
            1 Warning
          </div>
          <p style={{ fontSize: '0.8rem', color: 'var(--text-muted)', marginTop: '4px' }}>
            Predictive asset failure alarms
          </p>
        </div>
      </div>

      <div className="grid-2">
        <div className="card">
          <div className="card-header">
            <span className="card-title">
              <Settings className="nav-icon" style={{ color: 'var(--color-primary)' }} />
              Platform System Settings
            </span>
          </div>
          {sysStatus ? (
            <div style={{ display: 'flex', flexDirection: 'column', gap: '14px', fontSize: '0.9rem' }}>
              <div style={{ display: 'flex', justifyContent: 'space-between', borderBottom: '1px solid var(--border-muted)', paddingBottom: '8px' }}>
                <span style={{ color: 'var(--text-muted)' }}>AI Core Engine:</span>
                <span style={{ fontFamily: 'var(--font-mono)', fontWeight: 600 }}>{sysStatus.llm_mode}</span>
              </div>
              <div style={{ display: 'flex', justifyContent: 'space-between', borderBottom: '1px solid var(--border-muted)', paddingBottom: '8px' }}>
                <span style={{ color: 'var(--text-muted)' }}>OCR Capabilities:</span>
                <span style={{ color: sysStatus.tesseract_ocr === 'AVAILABLE' ? 'var(--color-success)' : 'var(--color-warning)', fontWeight: 600 }}>
                  {sysStatus.tesseract_ocr}
                </span>
              </div>
              <div style={{ display: 'flex', justifyContent: 'space-between', borderBottom: '1px solid var(--border-muted)', paddingBottom: '8px' }}>
                <span style={{ color: 'var(--text-muted)' }}>Embedding Weights:</span>
                <span style={{ fontFamily: 'var(--font-mono)', fontSize: '0.8rem' }}>{sysStatus.embedding_model}</span>
              </div>
              <div style={{ display: 'flex', justifyContent: 'space-between', borderBottom: '1px solid var(--border-muted)', paddingBottom: '8px' }}>
                <span style={{ color: 'var(--text-muted)' }}>Reranking Engine:</span>
                <span style={{ fontFamily: 'var(--font-mono)', fontSize: '0.8rem' }}>{sysStatus.reranker_model}</span>
              </div>
              <div style={{ display: 'flex', justifyContent: 'space-between' }}>
                <span style={{ color: 'var(--text-muted)' }}>XGBoost Telemetry ML:</span>
                <span style={{ color: 'var(--color-primary)', fontWeight: 600 }}>{sysStatus.xgboost_model}</span>
              </div>
            </div>
          ) : (
            <p>Fetching platform configs...</p>
          )}
        </div>

        <div className="card">
          <div className="card-header">
            <span className="card-title">
              <FileText className="nav-icon" style={{ color: 'var(--color-secondary)' }} />
              Active Knowledge Libraries
            </span>
          </div>
          {documents.length > 0 ? (
            <div className="table-container">
              <table className="table-view">
                <thead>
                  <tr>
                    <th>Document Name</th>
                    <th>Pages</th>
                    <th>Action</th>
                  </tr>
                </thead>
                <tbody>
                  {documents.map((doc, idx) => (
                    <tr key={idx}>
                      <td style={{ fontWeight: 550, color: 'var(--text-title)' }}>{doc.document_name}</td>
                      <td style={{ fontFamily: 'var(--font-mono)' }}>{doc.page_count}</td>
                      <td>
                        <button
                          className="btn btn-danger"
                          style={{ padding: '6px 10px', fontSize: '0.8rem' }}
                          onClick={() => handleDeleteDoc(doc.document_name)}
                        >
                          <Trash2 style={{ width: '12px', height: '12px' }} />
                        </button>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          ) : (
            <div style={{ textAlign: 'center', padding: '30px', color: 'var(--text-muted)' }}>
              <Database style={{ width: '32px', height: '32px', marginBottom: '10px' }} />
              <p>No documents uploaded yet. Go to Ingestion Center to index PDF manuals.</p>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
