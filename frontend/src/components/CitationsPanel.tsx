import { useState } from 'react';
import type { Constraint } from '../api/client';

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
    <div style={{ marginTop: '24px' }}>
      <h3 className="section-title" style={{ marginBottom: '12px' }}>
        Regulations & Citations
      </h3>
      <div className="citations-list">
        {constraints.map((c) => {
          const isOpen = openItems.has(c.name);
          return (
            <div key={c.name} className="citation-item">
              <button
                onClick={() => toggle(c.name)}
                className="citation-trigger"
              >
                <span
                  style={{
                    transform: isOpen ? 'rotate(90deg)' : 'rotate(0deg)',
                    transition: 'transform 0.2s',
                    fontSize: '10px',
                    color: 'var(--text-muted)',
                  }}
                >
                  {'\u25B6'}
                </span>
                <span style={{ flex: 1, fontSize: '13px', fontWeight: 600, color: 'var(--text-main)' }}>
                  {c.name}
                </span>
                <span className={`badge badge-confidence-${c.confidence}`}>
                  {c.confidence}
                </span>
              </button>

              {isOpen && (
                <div className="expansion-content" style={{ margin: '0 16px 16px 36px' }}>
                  <div style={{ marginBottom: '8px' }}>
                    <strong>Regulation:</strong> {c.citation}
                  </div>
                  {c.confidence === 'interpreted' && c.explanation && (
                    <div style={{ marginBottom: '8px' }}>
                      <strong>AI Reasoning:</strong> {c.explanation}
                    </div>
                  )}
                  <div>
                    <strong>Value:</strong> <span style={{ color: 'var(--primary)', fontWeight: 600 }}>{c.value}</span>
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
