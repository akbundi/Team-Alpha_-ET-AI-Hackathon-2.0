import React from 'react';
import { ShieldCheck } from 'lucide-react';

interface ComplianceViewProps {
  compText: string;
  setCompText: React.Dispatch<React.SetStateAction<string>>;
  compLoading: boolean;
  compResult: any;
  handleCompliance: (e: React.FormEvent) => Promise<void> | void;
}

export default function ComplianceView({
  compText,
  setCompText,
  compLoading,
  compResult,
  handleCompliance
}: ComplianceViewProps) {
  return (
    <div className="grid-2">
      <div className="card">
        <div className="card-header">
          <span className="card-title">
            <ShieldCheck className="nav-icon" style={{ color: 'var(--color-success)' }} />
            SOP Regulatory Auditor
          </span>
        </div>
        <form onSubmit={handleCompliance}>
          <div className="form-group">
            <label className="form-label">SOP / Maintenance checklist procedure content</label>
            <textarea
              className="input-field textarea-field"
              placeholder="e.g. Standard procedures for boiler inspection. 1. Turn off heat source. 2. Remove casing guard. 3. Visually inspect interior tubes for scale build-up. 4. Re-fit guard casing and start burner."
              value={compText}
              onChange={(e) => setCompText(e.target.value)}
              style={{ minHeight: '260px' }}
              required
            />
          </div>
          <button type="submit" className="btn btn-primary" style={{ width: '100%', padding: '12px' }} disabled={compLoading}>
            {compLoading ? (
              <>
                <span className="spinner"></span> Auditing guidelines...
              </>
            ) : (
              "Check Compliance (Factory Act & OISD)"
            )}
          </button>
        </form>
      </div>

      <div className="card" style={{ maxHeight: '600px', overflowY: 'auto' }}>
        <div className="card-header">
          <span className="card-title">
            <ShieldCheck className="nav-icon" style={{ color: 'var(--color-primary)' }} />
            Compliance Verification Report
          </span>
        </div>
        {compResult ? (
          <div>
            <div style={{ display: 'flex', alignItems: 'center', gap: '24px', marginBottom: '24px' }}>
              <div className="radial-gauge">
                <svg width="120" height="120" viewBox="0 0 120 120">
                  <circle cx="60" cy="60" r="50" fill="none" stroke="var(--border-muted)" strokeWidth="8" />
                  <circle
                    cx="60"
                    cy="60"
                    r="50"
                    fill="none"
                    stroke={compResult.compliance_score > 80 ? 'var(--color-success)' : compResult.compliance_score > 60 ? 'var(--color-warning)' : 'var(--color-danger)'}
                    strokeWidth="8"
                    strokeDasharray={`${2 * Math.PI * 50}`}
                    strokeDashoffset={`${2 * Math.PI * 50 * (1 - compResult.compliance_score / 100)}`}
                    transform="rotate(-90 60 60)"
                  />
                </svg>
                <div className="gauge-inner">
                  <div className="gauge-value">{compResult.compliance_score.toFixed(0)}%</div>
                  <div className="gauge-label">SCORE</div>
                </div>
              </div>
              <div>
                <h4 style={{ color: 'var(--text-title)' }}>Audit Status: {compResult.compliance_score >= 85 ? 'PASSED' : 'NEEDS ACTION'}</h4>
                <p style={{ fontSize: '0.9rem', color: 'var(--text-muted)', marginTop: '4px' }}>
                  Audited against Factory Act (1948) Sections and safety guidelines.
                </p>
              </div>
            </div>

            <div style={{ marginBottom: '20px' }}>
              <h4 style={{ color: 'var(--text-title)', marginBottom: '10px' }}>Violations Detected:</h4>
              <div style={{ display: 'flex', flexDirection: 'column', gap: '10px' }}>
                {compResult.violations.map((v: any, i: number) => (
                  <div key={i} style={{ backgroundColor: 'rgba(0,0,0,0.2)', padding: '12px', borderLeft: `4px solid ${v.severity === 'CRITICAL' ? 'var(--color-danger)' : 'var(--color-warning)'}`, borderRadius: '0 8px 8px 0' }}>
                    <div style={{ display: 'flex', justifyContent: 'space-between', fontWeight: 600 }}>
                      <span style={{ color: 'var(--text-title)' }}>{v.section}</span>
                      <span className={`badge ${v.severity === 'CRITICAL' ? 'badge-critical' : 'badge-major'}`}>{v.severity}</span>
                    </div>
                    <p style={{ fontSize: '0.85rem', color: 'var(--text-main)', marginTop: '4px' }}>{v.description}</p>
                    <p style={{ fontSize: '0.85rem', color: 'var(--color-primary)', marginTop: '6px', fontWeight: 550 }}>Remediation: {v.remediation}</p>
                  </div>
                ))}
              </div>
            </div>

            <div style={{ marginTop: '20px' }}>
              <h4 style={{ color: 'var(--text-title)', marginBottom: '10px' }}>Audit Log Explanation:</h4>
              <p style={{ fontSize: '0.9rem', lineHeight: 1.5 }}>{compResult.explanation}</p>
            </div>
          </div>
        ) : (
          <div style={{ textAlign: 'center', padding: '60px 0', color: 'var(--text-muted)' }}>
            <ShieldCheck style={{ width: '48px', height: '48px', margin: '0 auto 16px', opacity: 0.5 }} />
            <p>Paste SOP text and run audit. The compliance checker evaluates clauses line-by-line.</p>
          </div>
        )}
      </div>
    </div>
  );
}
