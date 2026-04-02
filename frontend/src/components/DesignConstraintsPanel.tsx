import { useState } from 'react';
import type { Confidence, DesignConstraintResponse } from '../api/client';
import FeedbackButton from './FeedbackButton';

const CONFIDENCE_COLORS: Record<Confidence, string> = {
  verified: '#10b981',
  interpreted: '#f59e0b',
  unknown: '#ef4444',
};

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
      <div
        onClick={() => setIsExpanded((prev) => !prev)}
        style={{
          display: 'flex',
          alignItems: 'center',
          gap: '6px',
          marginTop: '16px',
          padding: '8px 0',
          borderBottom: '1px solid #e5e7eb',
          cursor: 'pointer',
        }}
      >
        <span style={{ fontSize: '12px', color: '#374151' }}>
          {isExpanded ? '\u25BC' : '\u25B6'}
        </span>
        <span style={{ fontSize: '15px', fontWeight: 600, color: '#374151' }}>
          Design Constraints
        </span>
      </div>

      {isExpanded && (
        <div>
          {/* Section 1: Per-edge setbacks */}
          <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: '13px', marginTop: '8px' }}>
            <thead>
              <tr style={{ borderBottom: '2px solid #e5e7eb', textAlign: 'left' }}>
                <th style={{ padding: '6px 8px', fontWeight: 600, color: '#374151' }}>Edge</th>
                <th style={{ padding: '6px 8px', fontWeight: 600, color: '#374151' }}>Setback</th>
                <th style={{ padding: '6px 8px', fontWeight: 600, color: '#374151' }}>Confidence</th>
                <th style={{ padding: '6px 4px', fontWeight: 600, color: '#374151', width: '40px' }}></th>
                <th style={{ padding: '6px 4px', fontWeight: 600, color: '#374151', width: '56px' }}></th>
              </tr>
            </thead>
            <tbody>
              {data.per_edge_setbacks.map((setback) => (
                <tr key={setback.edge}>
                  <td colSpan={5} style={{ padding: 0 }}>
                    <table style={{ width: '100%', borderCollapse: 'collapse' }}>
                      <tbody>
                        <tr style={{ borderBottom: '1px solid #f3f4f6' }}>
                          <td style={{ padding: '8px', color: '#374151' }}>
                            {EDGE_LABELS[setback.edge] || setback.edge}
                          </td>
                          <td style={{ padding: '8px', color: '#374151' }}>
                            {setback.setback_ft} ft
                          </td>
                          <td style={{ padding: '8px' }}>
                            <span
                              style={{
                                display: 'inline-block',
                                padding: '2px 8px',
                                borderRadius: '10px',
                                fontSize: '11px',
                                fontWeight: 600,
                                color: '#fff',
                                background: CONFIDENCE_COLORS[setback.confidence],
                              }}
                            >
                              {setback.confidence}
                            </span>
                          </td>
                          <td style={{ padding: '8px 4px', width: '40px', textAlign: 'center' }}>
                            {setback.citation && (
                              <button
                                onClick={() => toggleCitation(setback.edge)}
                                style={{
                                  background: 'none',
                                  border: 'none',
                                  cursor: 'pointer',
                                  fontSize: '12px',
                                  color: '#3b82f6',
                                  fontWeight: 600,
                                  padding: '2px 4px',
                                }}
                                title="Show citation"
                              >
                                {expandedCitations.has(setback.edge) ? '\u25B2' : 'cite'}
                              </button>
                            )}
                          </td>
                          <td style={{ padding: '4px', width: '56px', textAlign: 'center' }}>
                            <FeedbackButton constraintName={`setback_${setback.edge}`} />
                          </td>
                        </tr>
                        {expandedCitations.has(setback.edge) && (
                          <tr>
                            <td
                              colSpan={5}
                              style={{
                                padding: '8px 12px 12px',
                                background: '#f9fafb',
                                fontSize: '12px',
                                color: '#4b5563',
                                lineHeight: 1.5,
                              }}
                            >
                              <strong>Citation:</strong> {setback.citation}
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

          {/* Section 2: Height envelope */}
          <div
            style={{
              marginTop: '16px',
              padding: '12px',
              border: '1px solid #e5e7eb',
              borderRadius: '8px',
            }}
          >
            <div style={{ fontSize: '13px', color: '#6b7280' }}>Max Height</div>
            <div style={{ display: 'flex', alignItems: 'center', gap: '8px', marginTop: '4px' }}>
              <span style={{ fontSize: '16px', fontWeight: 700, color: '#111827' }}>
                {data.height_envelope.max_height_ft} ft
              </span>
              <span
                style={{
                  display: 'inline-block',
                  padding: '2px 8px',
                  borderRadius: '10px',
                  fontSize: '11px',
                  fontWeight: 600,
                  color: '#fff',
                  background: CONFIDENCE_COLORS[data.height_envelope.confidence],
                }}
              >
                {data.height_envelope.confidence}
              </span>
              {data.height_envelope.citation && (
                <button
                  onClick={() => toggleCitation('height')}
                  style={{
                    background: 'none',
                    border: 'none',
                    cursor: 'pointer',
                    fontSize: '12px',
                    color: '#3b82f6',
                    fontWeight: 600,
                    padding: '2px 4px',
                  }}
                  title="Show citation"
                >
                  {expandedCitations.has('height') ? '\u25B2' : 'cite'}
                </button>
              )}
            </div>
            {expandedCitations.has('height') && (
              <div
                style={{
                  marginTop: '8px',
                  padding: '8px 12px',
                  background: '#f9fafb',
                  borderRadius: '6px',
                  fontSize: '12px',
                  color: '#4b5563',
                  lineHeight: 1.5,
                }}
              >
                <strong>Citation:</strong> {data.height_envelope.citation}
              </div>
            )}
          </div>

          {/* Section 3: Panel fit feasibility */}
          <div
            style={{
              marginTop: '16px',
              padding: '12px 16px',
              borderRadius: '8px',
              background: data.panel_fit.feasible ? '#d1fae5' : '#fce7f3',
              color: data.panel_fit.feasible ? '#065f46' : '#9f1239',
            }}
          >
            <div style={{ fontSize: '13px', fontWeight: 700 }}>
              {data.panel_fit.feasible ? 'PANEL FIT: FEASIBLE' : 'PANEL FIT: NOT FEASIBLE'}
            </div>

            {data.panel_fit.feasible && (
              <div style={{ fontSize: '12px', color: '#6b7280', marginTop: '8px' }}>
                Min side clearance: {data.panel_fit.min_side_clearance_ft} ft | Min envelope width: {data.panel_fit.min_envelope_width_ft} ft
              </div>
            )}

            {!data.panel_fit.feasible && data.panel_fit.failures.length > 0 && (
              <ul style={{ listStyle: 'disc', paddingLeft: '20px', marginTop: '8px', marginBottom: 0 }}>
                {data.panel_fit.failures.map((f, i) => (
                  <li key={i} style={{ color: '#ef4444', fontSize: '13px', marginBottom: '4px' }}>
                    {f}
                  </li>
                ))}
              </ul>
            )}

            {!data.panel_fit.feasible && data.panel_fit.mitigations.length > 0 && (
              <div style={{ marginTop: '8px' }}>
                <div style={{ fontSize: '13px', fontWeight: 600 }}>Mitigations:</div>
                <ul style={{ listStyle: 'disc', paddingLeft: '20px', marginTop: '4px', marginBottom: 0 }}>
                  {data.panel_fit.mitigations.map((m, i) => (
                    <li key={i} style={{ color: '#3b82f6', fontSize: '13px', marginBottom: '4px' }}>
                      {m}
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
