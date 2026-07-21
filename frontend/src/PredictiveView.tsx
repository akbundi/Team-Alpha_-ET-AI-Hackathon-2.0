
import { TrendingUp, Activity } from 'lucide-react';

interface TelemetryData {
  temperature: number;
  vibration: number;
  pressure: number;
  operating_hours: number;
  maintenance_history_index: number;
  failure_records_count: number;
}

interface PredictiveViewProps {
  telemetry: TelemetryData;
  predResult: any;
  predLoading: boolean;
  handleSliderChange: (feat: string, val: number) => void;
}

export default function PredictiveView({
  telemetry,
  predResult,
  predLoading,
  handleSliderChange
}: PredictiveViewProps) {
  return (
    <div className="grid-2">
      <div className="card">
        <div className="card-header">
          <span className="card-title">
            <TrendingUp className="nav-icon" style={{ color: 'var(--color-primary)' }} />
            Telemetry Controls (Asset Telemetry Inputs)
          </span>
        </div>
        
        {/* Sliders */}
        <div className="slider-group">
          <div className="slider-header">
            <span>Operating Temperature (°C)</span>
            <span className="slider-val">{telemetry.temperature.toFixed(1)} °C</span>
          </div>
          <input
            type="range"
            className="range-slider"
            min="45"
            max="125"
            step="0.5"
            value={telemetry.temperature}
            onChange={(e) => handleSliderChange('temperature', Number(e.target.value))}
          />
        </div>

        <div className="slider-group">
          <div className="slider-header">
            <span>Vibration Speed (mm/s)</span>
            <span className="slider-val">{telemetry.vibration.toFixed(1)} mm/s</span>
          </div>
          <input
            type="range"
            className="range-slider"
            min="0.2"
            max="12.0"
            step="0.1"
            value={telemetry.vibration}
            onChange={(e) => handleSliderChange('vibration', Number(e.target.value))}
          />
        </div>

        <div className="slider-group">
          <div className="slider-header">
            <span>Suction/Discharge Pressure (psi)</span>
            <span className="slider-val">{telemetry.pressure.toFixed(0)} psi</span>
          </div>
          <input
            type="range"
            className="range-slider"
            min="10"
            max="90"
            step="1"
            value={telemetry.pressure}
            onChange={(e) => handleSliderChange('pressure', Number(e.target.value))}
          />
        </div>

        <div className="slider-group">
          <div className="slider-header">
            <span>Accumulated Operating Hours</span>
            <span className="slider-val">{telemetry.operating_hours.toFixed(0)} hrs</span>
          </div>
          <input
            type="range"
            className="range-slider"
            min="0"
            max="8000"
            step="50"
            value={telemetry.operating_hours}
            onChange={(e) => handleSliderChange('operating_hours', Number(e.target.value))}
          />
        </div>

        <div className="slider-group">
          <div className="slider-header">
            <span>Maintenance Index (0: Recent, 1: Overdue)</span>
            <span className="slider-val">{telemetry.maintenance_history_index.toFixed(2)}</span>
          </div>
          <input
            type="range"
            className="range-slider"
            min="0.0"
            max="1.0"
            step="0.05"
            value={telemetry.maintenance_history_index}
            onChange={(e) => handleSliderChange('maintenance_history_index', Number(e.target.value))}
          />
        </div>

        <div className="slider-group">
          <div className="slider-header">
            <span>Previous Failures History Count</span>
            <span className="slider-val">{telemetry.failure_records_count}</span>
          </div>
          <input
            type="range"
            className="range-slider"
            min="0"
            max="5"
            step="1"
            value={telemetry.failure_records_count}
            onChange={(e) => handleSliderChange('failure_records_count', Number(e.target.value))}
          />
        </div>
      </div>

      <div className="card">
        <div className="card-header">
          <span className="card-title">
            <Activity className="nav-icon" style={{ color: 'var(--color-secondary)' }} />
            XGBoost Probability & SHAP Importance
          </span>
        </div>
        {predResult ? (
          <div>
            <div style={{ display: 'flex', alignItems: 'center', gap: '20px', marginBottom: '24px', backgroundColor: 'rgba(0,0,0,0.2)', padding: '16px', borderRadius: '8px', border: '1px solid var(--border-muted)' }}>
              <div style={{ flexGrow: 1 }}>
                <div style={{ fontSize: '0.85rem', color: 'var(--text-muted)', fontWeight: 600 }}>FAILURE RISK INDEX</div>
                <div style={{ fontSize: '2.5rem', fontWeight: 700, color: predResult.status === 'CRITICAL' ? 'var(--color-danger)' : predResult.status === 'WARN' ? 'var(--color-warning)' : 'var(--color-success)', fontFamily: 'var(--font-mono)' }}>
                  {(predResult.failure_probability * 100).toFixed(1)}%
                </div>
              </div>
              <div>
                <span className={`badge ${predResult.status === 'CRITICAL' ? 'badge-critical' : predResult.status === 'WARN' ? 'badge-major' : 'badge-minor'}`} style={{ fontSize: '1rem', padding: '6px 16px' }}>
                  {predResult.status}
                </span>
              </div>
            </div>

            <div style={{ marginBottom: '24px' }}>
              <h4 style={{ color: 'var(--text-title)', marginBottom: '14px', fontSize: '0.95rem' }}>SHAP Explanation: Feature Contributions Impact</h4>
              <div className="shap-bar-container">
                {predResult.contributions.map((c: any, i: number) => {
                  const val = c.shap_value;
                  const absVal = Math.abs(val);
                  // Calculate width percentage relative to a max threshold (e.g. 0.8 max logit impact)
                  const widthPct = Math.min(100, (absVal / 0.8) * 100);
                  
                  return (
                    <div key={i} className="shap-row">
                      <div className="shap-label">{c.feature.replace(/_/g, ' ')}</div>
                      <div className="shap-track">
                        {val >= 0 ? (
                          <div className="shap-fill-pos" style={{ width: `${widthPct}%` }}></div>
                        ) : (
                          <div className="shap-fill-neg" style={{ width: `${widthPct}%` }}></div>
                        )}
                      </div>
                      <div className="shap-value-text" style={{ color: val >= 0 ? 'var(--color-danger)' : 'var(--color-success)' }}>
                        {val >= 0 ? '+' : ''}{val.toFixed(3)}
                      </div>
                    </div>
                  );
                })}
              </div>
              <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: '0.75rem', color: 'var(--text-muted)', marginTop: '8px' }}>
                <span>← Reduces Failure Risk (SHAP -ve)</span>
                <span>Increases Failure Risk (SHAP +ve) →</span>
              </div>
            </div>

            <div>
              <h4 style={{ color: 'var(--text-title)', marginBottom: '8px', fontSize: '0.95rem' }}>Dynamic Safety Recommendations:</h4>
              <ul style={{ paddingLeft: '20px', display: 'flex', flexDirection: 'column', gap: '6px', fontSize: '0.85rem' }}>
                {predResult.recommendations.map((r: string, i: number) => (
                  <li key={i}>{r}</li>
                ))}
              </ul>
            </div>
          </div>
        ) : (
          predLoading ? (
            <p>Running ML model inference...</p>
          ) : (
            <p>Ready for inference.</p>
          )
        )}
      </div>
    </div>
  );
}
