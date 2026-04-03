import { useState } from 'react';
import type { DesignConstraintResponse } from '../api/client';
import FeedbackButton from './FeedbackButton';
import { toTitleCase } from '../utils/format';

const EDGE_LABELS: Record<string, string> = {
  front: 'Front',
  left_side: 'Left Side',
  right_side: 'Right Side',
  rear: 'Rear',
};

interface Props {
  data: DesignConstraintResponse;
}

export default function DesignConstraintsPanel({ data }: Props) {
  const [isExpanded, setIsExpanded] = useState(true);
  const [expandedCitations, setExpandedCitations] = useState<Set<string>>(new Set());

  function toggleCitation(key: string) {
    setExpandedCitations((prev) => {
      const next = new Set(prev);
      if (next.has(key)) next.delete(key);
      else next.add(key);
      return next;
    });
  }

  return (
    <div style={{ marginTop: '32px' }}>
      <div className="section-header" onClick={() => setIsExpanded((prev) => !prev)}>
        <span style={{ fontSize: '10px', color: 'var(--text-muted)' }}>
          {isExpanded ? '\u25BC' : '\u25B6'}
        </span>
        <span className="section-title">Design Constraints</span>
      </div>

      {isExpanded && (
        <div style={{ animation: 'slideDown 0.3s ease-out' }}>
          <table className="data-table" style={{ marginTop: '8px' }}>
            <thead>
              <tr>
                <th>Edge</th>
                <th>Setback</th>
                <th>Confidence</th>
                <th style={{ width: '40px' }}></th>
                <th style={{ width: '56px' }}></th>
              </tr>
            </thead>
            <tbody>
              {data.per_edge_setbacks.map((setback) => (
                <tr key={setback.edge}>
                  <td colSpan={5} style={{ padding: 0 }}>
                    <table style={{ width: '100%', borderCollapse: 'collapse' }}>
                      <tbody>
                        <tr>
                          <td style={{ padding: '14px 8px', color: 'var(--text-main)', width: '30%', fontWeight: 500 }}>
                            {EDGE_LABELS[setback.edge] || toTitleCase(setback.edge)}
                          </td>
                          <td style={{ padding: '14px 8px', color: 'var(--text-main)', width: '25%', fontWeight: 600 }}>
                            {setback.setback_ft} ft
                          </td>
                          <td style={{ padding: '14px 8px' }}>
                            <span className={`badge badge-confidence-${setback.confidence}`}>
                              {setback.confidence}
                            </span>
                          </td>
                          <td style={{ padding: '14px 4px', width: '40px', textAlign: 'center' }}>
                            {setback.citation && (
                              <button
                                onClick={() => toggleCitation(setback.edge)}
                                className={`btn-cite ${expandedCitations.has(setback.edge) ? 'active' : ''}`}
                                title="Show citation"
                              >
                                cite
                              </button>
                            )}
                          </td>
                          <td style={{ padding: '14px 4px', width: '56px', textAlign: 'center' }}>
                            <FeedbackButton constraintName={`setback_${setback.edge}`} />
                          </td>
                        </tr>
                        {expandedCitations.has(setback.edge) && (
                          <tr>
                            <td colSpan={5}>
                              <div className="expansion-content">
                                <strong style={{ color: 'var(--text-main)' }}>Citation:</strong> {setback.citation}
                              </div>
                            </td>
                          </tr>
                        )}
                      </tbody>
                    </table>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>

          <div style={{ marginTop: '20px', padding: '20px', background: 'white', border: '1px solid var(--border-color)', borderRadius: 'var(--radius-md)', boxShadow: 'var(--shadow-sm)' }}>
            <div style={{ fontSize: '11px', color: 'var(--text-muted)', fontWeight: 700, textTransform: 'uppercase', letterSpacing: '0.08em' }}>Max Building Height</div>
            <div style={{ display: 'flex', alignItems: 'center', gap: '16px', marginTop: '12px' }}>
              <span style={{ fontSize: '24px', fontWeight: 800, color: 'var(--text-main)', letterSpacing: '-0.02em' }}>
                {data.height_envelope.max_height_ft} ft
              </span>
              <span className={`badge badge-confidence-${data.height_envelope.confidence}`}>
                {data.height_envelope.confidence}
              </span>
              {data.height_envelope.citation && (
                <button
                  onClick={() => toggleCitation('height')}
                  className={`btn-cite ${expandedCitations.has('height') ? 'active' : ''}`}
                >
                  cite
                </button>
              )}
            </div>
            {expandedCitations.has('height') && (
              <div className="expansion-content" style={{ marginTop: '16px', marginLeft: 0, marginRight: 0 }}>
                <strong style={{ color: 'var(--text-main)' }}>Citation:</strong> {data.height_envelope.citation}
              </div>
            )}
          </div>

          <div
            style={{
              marginTop: '16px',
              padding: '20px',
              borderRadius: 'var(--radius-md)',
              background: data.panel_fit.feasible ? '#f0fdf4' : '#fef2f2',
              border: `1px solid ${data.panel_fit.feasible ? '#bbf7d0' : '#fecaca'}`,
              boxShadow: 'var(--shadow-sm)',
            }}
          >
            <div style={{ fontSize: '14px', fontWeight: 800, color: data.panel_fit.feasible ? '#166534' : '#991b1b', display: 'flex', alignItems: 'center', gap: '10px' }}>
              <span style={{ fontSize: '20px' }}>{data.panel_fit.feasible ? '\u2714' : '\u2718'}</span>
              {data.panel_fit.feasible ? 'PANEL FIT: FEASIBLE' : 'PANEL FIT: NOT FEASIBLE'}
            </div>

            {data.panel_fit.feasible && (
              <div style={{ fontSize: '13px', color: '#374151', marginTop: '12px', lineHeight: 1.6 }}>
                Min side clearance: <strong>{data.panel_fit.min_side_clearance_ft} ft</strong><br />
                Min envelope width: <strong>{Math.round(data.panel_fit.min_envelope_width_ft * 100) / 100} ft</strong>
              </div>
            )}

            {!data.panel_fit.feasible && data.panel_fit.failures.length > 0 && (
              <ul style={{ listStyle: 'none', padding: 0, marginTop: '12px' }}>
                {data.panel_fit.failures.map((f, i) => (
                  <li key={i} style={{ color: '#dc2626', fontSize: '13px', marginBottom: '8px', display: 'flex', gap: '10px' }}>
                    <span style={{ color: '#ef4444' }}>&bull;</span> {f}
                  </li>
                ))}
              </ul>
            )}

            {!data.panel_fit.feasible && data.panel_fit.mitigations.length > 0 && (
              <div style={{ marginTop: '16px', paddingTop: '16px', borderTop: '1px solid rgba(153, 27, 27, 0.1)' }}>
                <div style={{ fontSize: '13px', fontWeight: 700, color: '#991b1b', marginBottom: '8px' }}>Recommended Mitigations:</div>
                <ul style={{ listStyle: 'none', padding: 0 }}>
                  {data.panel_fit.mitigations.map((m, i) => (
                    <li key={i} style={{ color: 'var(--primary)', fontSize: '13px', marginBottom: '8px', display: 'flex', gap: '10px' }}>
                      <span>&rarr;</span> {m}
                    </li>
                  ))}
                </ul>
              </div>
            )}
          </div>
        </div>
      )}
    </div>
  );
}

