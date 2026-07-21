import React from 'react';
import { AlertTriangle, FileText } from 'lucide-react';

interface RcaViewProps {
  rcaDesc: string;
  setRcaDesc: React.Dispatch<React.SetStateAction<string>>;
  rcaEqId: string;
  setRcaEqId: React.Dispatch<React.SetStateAction<string>>;
  rcaComp: string;
  setRcaComp: React.Dispatch<React.SetStateAction<string>>;
  rcaLoading: boolean;
  rcaResult: any;
  handleRca: (e: React.FormEvent) => Promise<void> | void;
}

export default function RcaView({
  rcaDesc,
  setRcaDesc,
  rcaEqId,
  setRcaEqId,
  rcaComp,
  setRcaComp,
  rcaLoading,
  rcaResult,
  handleRca
}: RcaViewProps) {
  return (
    <div className="grid-2">
      <div className="card">
        <div className="card-header">
          <span className="card-title">
            <AlertTriangle className="nav-icon" style={{ color: 'var(--color-secondary)' }} />
            Initiate Root Cause Diagnostics
          </span>
        </div>
        <form onSubmit={handleRca}>
          <div className="grid-2">
            <div className="form-group">
              <label className="form-label">Equipment ID / Tag</label>
              <input
                type="text"
                className="input-field"
                placeholder="e.g. TURB-04"
                value={rcaEqId}
                onChange={(e) => setRcaEqId(e.target.value)}
              />
            </div>
            <div className="form-group">
              <label className="form-label">Target Component</label>
              <input
                type="text"
                className="input-field"
                placeholder="e.g. thrust bearing"
                value={rcaComp}
                onChange={(e) => setRcaComp(e.target.value)}
              />
            </div>
          </div>

          <div className="form-group">
            <label className="form-label">Incident Symptoms / Failure Log Description</label>
            <textarea
              className="input-field textarea-field"
              placeholder="e.g. Steam turbine experienced massive shaft vibration spike up to 8.5 mm/s. Housing temperature reached 98C before automatic safety trip. Suspected seal leak or blade misalignment."
              value={rcaDesc}
              onChange={(e) => setRcaDesc(e.target.value)}
              required
            />
          </div>

          <button type="submit" className="btn btn-primary" style={{ width: '100%', padding: '12px' }} disabled={rcaLoading}>
            {rcaLoading ? (
              <>
                <span className="spinner"></span> Running Diagnostics...
              </>
            ) : (
              "Run Root Cause Analysis"
            )}
          </button>
        </form>
      </div>

      <div className="card" style={{ maxHeight: '600px', overflowY: 'auto' }}>
        <div className="card-header">
          <span className="card-title">
            <FileText className="nav-icon" style={{ color: 'var(--color-primary)' }} />
            RCA Diagnostic & CAPA Report
          </span>
        </div>
        {rcaResult ? (
          <div style={{ fontSize: '0.95rem' }}>
            <div className="confidence-wrapper" style={{ marginBottom: '20px' }}>
              <span className="confidence-label">Diagnostic Confidence:</span>
              <div className="confidence-bar">
                <div
                  className="confidence-fill"
                  style={{
                    width: `${rcaResult.overall_confidence * 100}%`,
                    backgroundColor: 'var(--color-success)'
                  }}
                ></div>
              </div>
              <span className="confidence-value" style={{ color: 'var(--color-success)' }}>
                {(rcaResult.overall_confidence * 100).toFixed(0)}%
              </span>
            </div>

            <div style={{ marginBottom: '20px' }}>
              <h4 style={{ color: 'var(--text-title)', marginBottom: '10px' }}>Probable Causes:</h4>
              <div style={{ display: 'flex', flexDirection: 'column', gap: '10px' }}>
                {rcaResult.probable_causes.map((c: any, i: number) => (
                  <div key={i} style={{ backgroundColor: 'rgba(0,0,0,0.2)', padding: '12px', borderRadius: '8px', border: '1px solid var(--border-muted)' }}>
                    <div style={{ display: 'flex', justifyContent: 'space-between', fontWeight: 600 }}>
                      <span style={{ color: 'var(--text-title)' }}>{c.cause}</span>
                      <span style={{ color: 'var(--color-secondary)' }}>{(c.probability * 100).toFixed(0)}% Prob.</span>
                    </div>
                    <p style={{ fontSize: '0.85rem', color: 'var(--text-muted)', marginTop: '4px' }}>{c.explanation}</p>
                  </div>
                ))}
              </div>
            </div>

            <div style={{ marginBottom: '20px' }}>
              <h4 style={{ color: 'var(--text-title)', marginBottom: '10px' }}>Immediate Corrective Actions:</h4>
              <div className="table-container">
                <table className="table-view">
                  <thead>
                    <tr>
                      <th>Action</th>
                      <th>Priority</th>
                      <th>Detail</th>
                    </tr>
                  </thead>
                  <tbody>
                    {rcaResult.corrective_actions.map((act: any, idx: number) => (
                      <tr key={idx}>
                        <td style={{ fontWeight: 600 }}>{act.action}</td>
                        <td>
                          <span className={`badge ${act.priority === 'HIGH' ? 'badge-critical' : 'badge-major'}`}>
                            {act.priority}
                          </span>
                        </td>
                        <td style={{ fontSize: '0.85rem' }}>{act.description}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </div>

            <div>
              <h4 style={{ color: 'var(--text-title)', marginBottom: '10px' }}>Preventive Actions (Standardized):</h4>
              <ul style={{ paddingLeft: '20px', display: 'flex', flexDirection: 'column', gap: '6px', fontSize: '0.9rem' }}>
                {rcaResult.preventive_actions.map((a: string, idx: number) => (
                  <li key={idx}>{a}</li>
                ))}
              </ul>
            </div>
          </div>
        ) : (
          <div style={{ textAlign: 'center', padding: '60px 0', color: 'var(--text-muted)' }}>
            <AlertTriangle style={{ width: '48px', height: '48px', margin: '0 auto 16px', opacity: 0.5 }} />
            <p>Run diagnostics on the left. The agent will crawl historical manuals to identify root causes.</p>
          </div>
        )}
      </div>
    </div>
  );
}
