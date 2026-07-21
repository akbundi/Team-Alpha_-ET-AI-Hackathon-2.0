import React from 'react';
import { Search, Database } from 'lucide-react';

interface EntityViewProps {
  extractText: string;
  setExtractText: React.Dispatch<React.SetStateAction<string>>;
  extractLoading: boolean;
  extractedEntities: any[];
  handleExtract: (e: React.FormEvent) => Promise<void> | void;
}

export default function EntityView({
  extractText,
  setExtractText,
  extractLoading,
  extractedEntities,
  handleExtract
}: EntityViewProps) {
  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: '24px' }}>
      <div className="card">
        <div className="card-header">
          <span className="card-title">
            <Search className="nav-icon" style={{ color: 'var(--color-primary)' }} />
            Industrial Entity Extractor
          </span>
        </div>
        <form onSubmit={handleExtract}>
          <div className="form-group">
            <label className="form-label">Paste Maintenance Logs, Inspection Sheets, or Work Orders</label>
            <textarea
              className="input-field textarea-field"
              placeholder="Example: On 2026-06-15, technician John Doe completed repair on pump PMP-102 at Pump House 3. The impeller was experiencing severe cavitation damage. Replaced impeller blades and calibrated shaft. Refer to Factory Act Sec 21 for safety casing guards."
              value={extractText}
              onChange={(e) => setExtractText(e.target.value)}
              disabled={extractLoading}
            />
          </div>
          <button type="submit" className="btn btn-primary" disabled={extractLoading || !extractText.trim()}>
            {extractLoading ? (
              <>
                <span className="spinner"></span> Running NLP Extraction Models...
              </>
            ) : (
              "Extract Structured JSON Entities"
            )}
          </button>
        </form>
      </div>

      <div className="card">
        <div className="card-header">
          <span className="card-title">
            <Database className="nav-icon" style={{ color: 'var(--color-secondary)' }} />
            Extracted Structured Entity Grid
          </span>
        </div>
        {extractedEntities.length > 0 ? (
          <div className="table-container">
            <table className="table-view">
              <thead>
                <tr>
                  <th>Equipment ID</th>
                  <th>Component</th>
                  <th>Failure Mode</th>
                  <th>Technician</th>
                  <th>Date</th>
                  <th>Action Taken</th>
                  <th>Regulations</th>
                  <th>Location</th>
                </tr>
              </thead>
              <tbody>
                {extractedEntities.map((ent, idx) => (
                  <tr key={idx}>
                    <td style={{ fontFamily: 'var(--font-mono)', fontWeight: 600, color: 'var(--color-primary)' }}>
                      {ent.equipment_id || 'N/A'}
                    </td>
                    <td style={{ textTransform: 'capitalize' }}>{ent.component_name || 'N/A'}</td>
                    <td style={{ color: ent.failure_type ? 'var(--color-danger)' : 'var(--text-main)' }}>
                      {ent.failure_type || 'N/A'}
                    </td>
                    <td>{ent.technician || 'N/A'}</td>
                    <td style={{ fontFamily: 'var(--font-mono)' }}>{ent.inspection_date || 'N/A'}</td>
                    <td>{ent.maintenance_action || 'N/A'}</td>
                    <td>
                      {ent.regulatory_references && ent.regulatory_references.length > 0 ? (
                        ent.regulatory_references.map((r: string, rIdx: number) => (
                          <span key={rIdx} className="badge badge-minor" style={{ marginRight: '4px' }}>{r}</span>
                        ))
                      ) : (
                        'N/A'
                      )}
                    </td>
                    <td>{ent.location || 'N/A'}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        ) : (
          <div style={{ textAlign: 'center', padding: '40px', color: 'var(--text-muted)' }}>
            <p>No entities extracted yet. Enter text and run extraction above.</p>
          </div>
        )}
      </div>
    </div>
  );
}
