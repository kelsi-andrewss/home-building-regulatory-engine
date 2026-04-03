import { useState } from 'react';
import type { DesignConstraintResponse } from '../api/client';
import FeedbackButton from './FeedbackButton';

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
    <div>
      <div className="section-header" onClick={() => setIsExpanded((prev) => !prev)}>
        <span style={{ fontSize: '10px', color: 'var(--text-muted)' }}>
          {isExpanded ? '\u25BC' : '\u25B6'}
        </span>
        <span className="section-title">Design Constraints</span>
      </div>

      {isExpanded && (
        <div>
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
                          <td style={{ padding: '12px 8px', color: 'var(--text-main)', width: '30%' }}>
                            {EDGE_LABELS[setback.edge] || setback.edge}
                          </td>
                          <td style={{ padding: '12px 8px', color: 'var(--text-main)', width: '25%' }}>
                            {setback.setback_ft} ft
                          </td>
                          <td style={{ padding: '12px 8px' }}>
                            <span className={`badge badge-confidence-${setback.confidence}`}>
                              {setback.confidence}
                            </span>
                          </td>
                          <td style={{ padding: '12px 4px', width: '40px', textAlign: 'center' }}>
                            {setback.citation && (
                              <button
                                onClick={() => toggleCitation(setback.edge)}
                                className="btn-secondary"
                                style={{ padding: '2px 6px', fontSize: '11px' }}
                                title="Show citation"
                              >
                                {expandedCitations.has(setback.edge) ? '\u25B4' : 'cite'}
                              </button>
                            )}
                          </td>
                          <td style={{ padding: '12px 4px', width: '56px', textAlign: 'center' }}>
                            <FeedbackButton constraintName={`setback_${setback.edge}`} />
                          </td>
                        </tr>
                        {expandedCitations.has(setback.edge) && (
                          <tr>
                            <td colSpan={5}>
                              <div className="expansion-content">
                                <strong>Citation:</strong> {setback.citation}
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

          <div style={{ marginTop: '20px', padding: '16px', border: '1px solid var(--border-color)', borderRadius: 'var(--radius-md)' }}>
            <div style={{ fontSize: '12px', color: 'var(--text-muted)', fontWeight: 600, textTransform: 'uppercase', letterSpacing: '0.05em' }}>Max Height</div>
            <div style={{ display: 'flex', alignItems: 'center', gap: '12px', marginTop: '8px' }}>
              <span style={{ fontSize: '20px', fontWeight: 700, color: 'var(--text-main)' }}>
                {data.height_envelope.max_height_ft} ft
              </span>
              <span className={`badge badge-confidence-${data.height_envelope.confidence}`}>
                {data.height_envelope.confidence}
              </span>
              {data.height_envelope.citation && (
                <button
                  onClick={() => toggleCitation('height')}
                  className="btn-secondary"
                  style={{ padding: '2px 8px', fontSize: '11px' }}
                >
                  {expandedCitations.has('height') ? '\u25B4' : 'cite'}
                </button>
              )}
            </div>
            {expandedCitations.has('height') && (
              <div className="expansion-content" style={{ marginTop: '12px', marginLeft: 0, marginRight: 0 }}>
                <strong>Citation:</strong> {data.height_envelope.citation}
              </div>
            )}
          </div>

          <div
            style={{
              marginTop: '16px',
              padding: '16px',
              borderRadius: 'var(--radius-md)',
              background: data.panel_fit.feasible ? '#f0fdf4' : '#fef2f2',
              border: `1px solid ${data.panel_fit.feasible ? '#bbf7d0' : '#fecaca'}`,
            }}
          >
            <div style={{ fontSize: '13px', fontWeight: 700, color: data.panel_fit.feasible ? '#166534' : '#991b1b', display: 'flex', alignItems: 'center', gap: '8px' }}>
              <span style={{ fontSize: '18px' }}>{data.panel_fit.feasible ? '\u2705' : '\u274C'}</span>
              {data.panel_fit.feasible ? 'PANEL FIT: FEASIBLE' : 'PANEL FIT: NOT FEASIBLE'}
            </div>

            {data.panel_fit.feasible && (
              <div style={{ fontSize: '12px', color: 'var(--text-muted)', marginTop: '8px', lineHeight: 1.5 }}>
                Min side clearance: <strong>{data.panel_fit.min_side_clearance_ft} ft</strong><br />
                Min envelope width: <strong>{data.panel_fit.min_envelope_width_ft} ft</strong>
              </div>
            )}

            {!data.panel_fit.feasible && data.panel_fit.failures.length > 0 && (
              <ul style={{ listStyle: 'none', padding: 0, marginTop: '12px' }}>
                {data.panel_fit.failures.map((f, i) => (
                  <li key={i} style={{ color: '#dc2626', fontSize: '13px', marginBottom: '6px', display: 'flex', gap: '8px' }}>
                    <span>&bull;</span> {f}
                  </li>
                ))}
              </ul>
            )}

            {!data.panel_fit.feasible && data.panel_fit.mitigations.length > 0 && (
              <div style={{ marginTop: '12px', paddingTop: '12px', borderTop: '1px solid #fecaca' }}>
                <div style={{ fontSize: '13px', fontWeight: 600, color: '#991b1b' }}>Mitigations:</div>
                <ul style={{ listStyle: 'none', padding: 0, marginTop: '8px' }}>
                  {data.panel_fit.mitigations.map((m, i) => (
                    <li key={i} style={{ color: 'var(--primary)', fontSize: '13px', marginBottom: '6px', display: 'flex', gap: '8px' }}>
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
