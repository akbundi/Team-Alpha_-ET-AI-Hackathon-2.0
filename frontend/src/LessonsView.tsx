import React from 'react';
import { BookOpen, Database } from 'lucide-react';

interface LessonsViewProps {
  lessDesc: string;
  setLessDesc: React.Dispatch<React.SetStateAction<string>>;
  lessEqType: string;
  setLessEqType: React.Dispatch<React.SetStateAction<string>>;
  lessLoading: boolean;
  lessResult: any;
  handleLessons: (e: React.FormEvent) => Promise<void> | void;
}

export default function LessonsView({
  lessDesc,
  setLessDesc,
  lessEqType,
  setLessEqType,
  lessLoading,
  lessResult,
  handleLessons
}: LessonsViewProps) {
  return (
    <div className="grid-2">
      <div className="card">
        <div className="card-header">
          <span className="card-title">
            <BookOpen className="nav-icon" style={{ color: 'var(--color-primary)' }} />
            New Incident Reporter
          </span>
        </div>
        <form onSubmit={handleLessons}>
          <div className="form-group">
            <label className="form-label">Asset Equipment Class</label>
            <select
              className="input-field"
              value={lessEqType}
              onChange={(e) => setLessEqType(e.target.value)}
            >
              <option value="Centrifugal Pump">Centrifugal Pump</option>
              <option value="Steam Turbine">Steam Turbine</option>
              <option value="Reciprocating Compressor">Reciprocating Compressor</option>
              <option value="Boiler Unit">Boiler Unit</option>
            </select>
          </div>

          <div className="form-group">
            <label className="form-label">New Incident Description (Symptoms/Observations)</label>
            <textarea
              className="input-field textarea-field"
              placeholder="e.g. Pump coupling shaft sheared during startup calibration unit 3. Severe bearing lockup and alignment deviation observed. Oil reservoir was empty."
              value={lessDesc}
              onChange={(e) => setLessDesc(e.target.value)}
              style={{ minHeight: '180px' }}
              required
            />
          </div>

          <button type="submit" className="btn btn-primary" style={{ width: '100%', padding: '12px' }} disabled={lessLoading}>
            {lessLoading ? (
              <>
                <span className="spinner"></span> Querying logs database...
              </>
            ) : (
              "Analyze Historical Lessons Learned"
            )}
          </button>
        </form>
      </div>

      <div className="card" style={{ maxHeight: '600px', overflowY: 'auto' }}>
        <div className="card-header">
          <span className="card-title">
            <Database className="nav-icon" style={{ color: 'var(--color-secondary)' }} />
            Retrieved Failures Trends & Patterns
          </span>
        </div>
        {lessResult ? (
          <div>
            <div style={{ marginBottom: '20px' }}>
              <h4 style={{ color: 'var(--text-title)', marginBottom: '8px' }}>Incident Summary:</h4>
              <p style={{ fontSize: '0.9rem', color: 'var(--text-main)', lineHeight: 1.4 }}>{lessResult.new_incident_summary}</p>
            </div>

            <div style={{ marginBottom: '20px' }}>
              <h4 style={{ color: 'var(--text-title)', marginBottom: '10px' }}>Similar Historical Failures:</h4>
              <div style={{ display: 'flex', flexDirection: 'column', gap: '10px' }}>
                {lessResult.similar_historical_events.map((e: any, idx: number) => (
                  <div key={idx} style={{ backgroundColor: 'rgba(0,0,0,0.2)', padding: '12px', borderRadius: '8px', border: '1px solid var(--border-muted)' }}>
                    <div style={{ display: 'flex', justifyContent: 'space-between', fontWeight: 600, fontSize: '0.85rem', color: 'var(--color-primary)' }}>
                      <span>{e.source_doc} (Page {e.page})</span>
                      <span>{(e.similarity_score * 100).toFixed(0)}% match</span>
                    </div>
                    <p style={{ fontSize: '0.85rem', marginTop: '6px', color: 'var(--text-title)' }}>
                      <strong>Root Cause:</strong> {e.root_cause}
                    </p>
                    <p style={{ fontSize: '0.8rem', color: 'var(--text-muted)', marginTop: '4px' }}>
                      <strong>Preventive Action:</strong> {e.recomm_action}
                    </p>
                  </div>
                ))}
              </div>
            </div>

            <div style={{ marginBottom: '20px' }}>
              <h4 style={{ color: 'var(--text-title)', marginBottom: '8px' }}>Recurring Failure Patterns:</h4>
              <ul style={{ paddingLeft: '20px', display: 'flex', flexDirection: 'column', gap: '6px', fontSize: '0.85rem' }}>
                {lessResult.recurring_patterns.map((p: string, idx: number) => (
                  <li key={idx} style={{ color: 'var(--color-warning)' }}>{p}</li>
                ))}
              </ul>
            </div>

            <div>
              <h4 style={{ color: 'var(--text-title)', marginBottom: '8px' }}>Preventive Directives:</h4>
              <ul style={{ paddingLeft: '20px', display: 'flex', flexDirection: 'column', gap: '6px', fontSize: '0.85rem' }}>
                {lessResult.preventive_measures.map((m: string, idx: number) => (
                  <li key={idx}>{m}</li>
                ))}
              </ul>
            </div>
          </div>
        ) : (
          <div style={{ textAlign: 'center', padding: '60px 0', color: 'var(--text-muted)' }}>
            <BookOpen style={{ width: '48px', height: '48px', margin: '0 auto 16px', opacity: 0.5 }} />
            <p>Log a new incident. The agent compares safety reports to predict systemic failure trends.</p>
          </div>
        )}
      </div>
    </div>
  );
}
