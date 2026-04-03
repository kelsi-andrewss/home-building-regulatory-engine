import { useState } from 'react';
import type { Constraint } from '../api/client';
import { toTitleCase } from '../utils/format';

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
    <div style={{ marginTop: '32px' }}>
      <h3 className="section-title" style={{ marginBottom: '16px', fontSize: '15px' }}>
        Regulations & Citations
      </h3>
      <div className="citations-list">
        {constraints.map((c) => {
          const isOpen = openItems.has(c.name);
          return (
            <div key={c.name} className="citation-item">
              <button
                onClick={() => toggle(c.name)}
                className={`citation-trigger ${isOpen ? 'active' : ''}`}
              >
                <span
                  style={{
                    transform: isOpen ? 'rotate(90deg)' : 'rotate(0deg)',
                    transition: 'transform 0.2s cubic-bezier(0.4, 0, 0.2, 1)',
                    fontSize: '10px',
                    color: isOpen ? 'var(--primary)' : 'var(--text-muted)',
                    display: 'flex',
                    alignItems: 'center',
                  }}
                >
                  {'\u25B6'}
                </span>
                <span style={{ flex: 1, fontSize: '13px', fontWeight: 600, color: isOpen ? 'var(--primary)' : 'var(--text-main)' }}>
                  {toTitleCase(c.name)}
                </span>
                <span className={`badge badge-confidence-${c.confidence}`}>
                  {c.confidence}
                </span>
              </button>

              {isOpen && (
                <div className="expansion-content" style={{ margin: '0 16px 16px 40px', background: 'transparent', borderLeft: '2px solid var(--primary-light)', borderRadius: 0 }}>
                  <div style={{ marginBottom: '10px', fontSize: '13px', lineHeight: 1.5 }}>
                    <strong style={{ color: 'var(--text-main)' }}>Regulation:</strong> {c.citation}
                  </div>
                  {c.confidence === 'interpreted' && c.explanation && (
                    <div style={{ marginBottom: '10px', fontSize: '13px', lineHeight: 1.5 }}>
                      <strong style={{ color: 'var(--text-main)' }}>AI Reasoning:</strong> {c.explanation}
                    </div>
                  )}
                  <div style={{ fontSize: '13px' }}>
                    <strong style={{ color: 'var(--text-main)' }}>Value:</strong> <span style={{ color: 'var(--primary)', fontWeight: 700 }}>{c.value}</span>
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

