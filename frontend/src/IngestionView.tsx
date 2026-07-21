import React from 'react';
import { Upload, FileBarChart, FileText } from 'lucide-react';

interface IngestionViewProps {
  file: File | null;
  handleFileChange: (e: React.ChangeEvent<HTMLInputElement>) => void;
  forceOcr: boolean;
  setForceOcr: React.Dispatch<React.SetStateAction<boolean>>;
  ingesting: boolean;
  ingestionResult: any;
  handleIngest: (e: React.FormEvent) => Promise<void> | void;
}

export default function IngestionView({
  file,
  handleFileChange,
  forceOcr,
  setForceOcr,
  ingesting,
  ingestionResult,
  handleIngest
}: IngestionViewProps) {
  return (
    <div className="grid-2">
      <div className="card">
        <div className="card-header">
          <span className="card-title">
            <Upload className="nav-icon" style={{ color: 'var(--color-primary)' }} />
            Index New PDF Manual
          </span>
        </div>
        <form onSubmit={handleIngest}>
          <div className="form-group">
            <label className="upload-zone" htmlFor="pdf-file">
              <Upload className="upload-icon" />
              <p style={{ fontWeight: 600, color: 'var(--text-title)' }}>
                {file ? file.name : "Drag & Drop or Click to Browse"}
              </p>
              <p style={{ fontSize: '0.8rem', color: 'var(--text-muted)', marginTop: '6px' }}>
                Supports scanned or digital PDF maintenance logs, SOPs, OEM catalogs
              </p>
              <input
                type="file"
                id="pdf-file"
                accept=".pdf"
                onChange={handleFileChange}
                style={{ display: 'none' }}
              />
            </label>
          </div>

          <div className="form-group" style={{ display: 'flex', alignItems: 'center', gap: '10px', margin: '20px 0' }}>
            <input
              type="checkbox"
              id="force-ocr"
              checked={forceOcr}
              onChange={(e) => setForceOcr(e.target.checked)}
              style={{ width: '16px', height: '16px', cursor: 'pointer' }}
            />
            <label htmlFor="force-ocr" style={{ fontSize: '0.9rem', cursor: 'pointer', fontWeight: 550 }}>
              Force Tesseract OCR (Re-render and scan all text as images)
            </label>
          </div>

          <button
            type="submit"
            className="btn btn-primary"
            style={{ width: '100%', padding: '12px' }}
            disabled={!file || ingesting}
          >
            {ingesting ? (
              <>
                <span className="spinner"></span> Processing Pipeline...
              </>
            ) : (
              "Ingest Document & Index Vectors"
            )}
          </button>
        </form>
      </div>

      <div className="card" style={{ display: 'flex', flexDirection: 'column', maxHeight: '550px', overflowY: 'auto' }}>
        <div className="card-header">
          <span className="card-title">
            <FileBarChart className="nav-icon" style={{ color: 'var(--color-secondary)' }} />
            Ingestion Pipeline Output
          </span>
        </div>
        {ingestionResult ? (
          <div style={{ fontSize: '0.9rem', display: 'flex', flexDirection: 'column', gap: '12px' }}>
            <div style={{ display: 'flex', justifyContent: 'space-between' }}>
              <span style={{ color: 'var(--text-muted)' }}>Document:</span>
              <span style={{ fontWeight: 600, color: 'var(--text-title)' }}>{ingestionResult.document_name}</span>
            </div>
            <div style={{ display: 'flex', justifyContent: 'space-between' }}>
              <span style={{ color: 'var(--text-muted)' }}>Pages Processed:</span>
              <span style={{ fontFamily: 'var(--font-mono)', fontWeight: 600 }}>{ingestionResult.page_count}</span>
            </div>
            <div style={{ display: 'flex', justifyContent: 'space-between' }}>
              <span style={{ color: 'var(--text-muted)' }}>Size:</span>
              <span style={{ fontFamily: 'var(--font-mono)' }}>{(ingestionResult.file_size_bytes / 1024 / 1024).toFixed(2)} MB</span>
            </div>
            
            <div style={{ marginTop: '10px' }}>
              <span style={{ display: 'block', color: 'var(--text-muted)', marginBottom: '6px' }}>Text Extraction Preview:</span>
              <div style={{
                backgroundColor: 'rgba(0, 0, 0, 0.3)',
                padding: '12px',
                borderRadius: '8px',
                fontFamily: 'var(--font-mono)',
                fontSize: '0.8rem',
                maxHeight: '220px',
                overflowY: 'auto',
                whiteSpace: 'pre-wrap',
                border: '1px solid var(--border-muted)',
                lineHeight: 1.4
              }}>
                {ingestionResult.preview}
              </div>
            </div>
          </div>
        ) : (
          <div style={{ textAlign: 'center', padding: '60px 0', color: 'var(--text-muted)' }}>
            <FileText style={{ width: '48px', height: '48px', margin: '0 auto 16px', opacity: 0.5 }} />
            <p>Upload and index a document to view ingestion output, metadata structures, and token logs.</p>
          </div>
        )}
      </div>
    </div>
  );
}
