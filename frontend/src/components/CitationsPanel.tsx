import { useState } from 'react';
import type { Constraint, Confidence } from '../api/client';

const CONFIDENCE_COLORS: Record<Confidence, string> = {
  verified: '#10b981',
  interpreted: '#f59e0b',
  unknown: '#ef4444',
};

interface Props {
  constraints: Constraint[];
}

export default function CitationsPanel({ constraints }: Props) {
  const [openItems, setOpenItems] = useState<Set<string>>(new Set());

  if (constraints.length === 0) return null;

  function toggle(name: string) {
    setOpenItems((prev) => {
      const next = new Set(prev);
      if (next.has(name)) next.delete(name);
      else next.add(name);
      return next;
    });
  }

  return (
    <div>
      <h3 style={{ fontSize: '14px', fontWeight: 600, color: '#374151', margin: '16px 0 8px' }}>
        Citations
      </h3>
      <div style={{ border: '1px solid #e5e7eb', borderRadius: '6px', overflow: 'hidden' }}>
        {constraints.map((c, i) => {
          const isOpen = openItems.has(c.name);
          return (
            <div
              key={c.name}
              style={{ borderTop: i > 0 ? '1px solid #e5e7eb' : undefined }}
            >
              <button
                onClick={() => toggle(c.name)}
                style={{
                  display: 'flex',
                  alignItems: 'center',
                  width: '100%',
                  padding: '10px 12px',
                  background: 'none',
                  border: 'none',
                  cursor: 'pointer',
                  gap: '8px',
                  textAlign: 'left',
                }}
              >
                <span
                  style={{
                    transform: isOpen ? 'rotate(90deg)' : 'rotate(0deg)',
                    transition: 'transform 0.15s',
                    fontSize: '10px',
                    color: '#6b7280',
                  }}
                >
                  {'\u25B6'}
                </span>
                <span style={{ flex: 1, fontSize: '13px', fontWeight: 500, color: '#374151' }}>
                  {c.name}
                </span>
                <span
                  style={{
                    padding: '1px 6px',
                    borderRadius: '10px',
                    fontSize: '10px',
                    fontWeight: 600,
                    color: '#fff',
                    background: CONFIDENCE_COLORS[c.confidence],
                  }}
                >
                  {c.confidence}
                </span>
              </button>

              {isOpen && (
                <div
                  style={{
                    padding: '8px 12px 12px 30px',
                    fontSize: '12px',
                    color: '#4b5563',
                    lineHeight: 1.6,
                    background: '#f9fafb',
                  }}
                >
                  <div style={{ marginBottom: '6px' }}>
                    <strong>Citation:</strong> {c.citation}
                  </div>
                  {c.confidence === 'interpreted' && c.explanation && (
                    <div style={{ marginBottom: '6px' }}>
                      <strong>Extraction reasoning:</strong> {c.explanation}
                    </div>
                  )}
                  <div>
                    <strong>Value:</strong> {c.value}
                  </div>
                </div>
              )}
            </div>
          );
        })}
      </div>
    </div>
  );
}
