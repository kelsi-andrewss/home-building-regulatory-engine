import { useEffect, useState } from 'react';

interface FragmentDetail {
  constraint_type: string;
  value: number | null;
  value_text: string | null;
  unit: string | null;
  confidence: 'verified' | 'interpreted' | 'unknown';
  source_section: string | null;
  extraction_reasoning: string | null;
}

interface DocumentStats {
  name: string;
  fragment_count: number;
  status: string;
  last_updated: string | null;
  fragments: FragmentDetail[];
}

interface AdminStats {
  totalDocs: number;
  totalFragments: number;
  errorCount: number;
  confidenceDistribution: {
    verified: number;
    interpreted: number;
    unknown: number;
  };
  documents: DocumentStats[];
}

const CONF_COLORS: Record<string, string> = {
  verified: '#16a34a',
  interpreted: '#d97706',
  unknown: '#dc2626',
};

const CONF_BG: Record<string, string> = {
  verified: '#dcfce7',
  interpreted: '#fef3c7',
  unknown: '#fee2e2',
};

const BASE_URL = import.meta.env.VITE_API_BASE_URL || '/api';

export default function AdminDashboard() {
  const [stats, setStats] = useState<AdminStats | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [expandedDoc, setExpandedDoc] = useState<string | null>(null);
  const [sortKey, setSortKey] = useState<'name' | 'fragment_count'>('name');
  const [sortAsc, setSortAsc] = useState(true);
  const [ingestForm, setIngestForm] = useState({ name: '', url: '', specificPlan: '' });
  const [isIngesting, setIsIngesting] = useState(false);
  const [ingestStatus, setIngestStatus] = useState<{ type: 'success' | 'error'; message: string } | null>(null);

  function fetchStats() {
    fetch(`${BASE_URL}/admin/stats`)
      .then((r) => {
        if (!r.ok) throw new Error(`${r.status}`);
        return r.json();
      })
      .then(setStats)
      .catch((e) => setError(e.message));
  }

  useEffect(() => {
    fetchStats();
  }, []);

  async function handleIngest(e: React.FormEvent) {
    e.preventDefault();
    setIsIngesting(true);
    setIngestStatus(null);

    try {
      const res = await fetch(`${BASE_URL}/admin/ingest`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          ...(import.meta.env.VITE_ADMIN_API_KEY
            ? { Authorization: `Bearer ${import.meta.env.VITE_ADMIN_API_KEY}` }
            : {}),
        },
        body: JSON.stringify({
          name: ingestForm.name,
          url: ingestForm.url,
          specific_plan: ingestForm.specificPlan,
        }),
      });

      if (!res.ok) {
        const detail = await res.json().catch(() => null);
        throw new Error(detail?.detail || `HTTP ${res.status}`);
      }

      const data = await res.json();
      if (data.status === 'completed') {
        setIngestStatus({
          type: 'success',
          message: `Ingested ${data.fragments_extracted} fragments (${data.fragments_flagged} flagged)`,
        });
        setIngestForm({ name: '', url: '', specificPlan: '' });
        fetchStats();
      } else {
        setIngestStatus({
          type: 'error',
          message: data.errors?.join('; ') || 'Ingestion failed',
        });
      }
    } catch (err) {
      setIngestStatus({
        type: 'error',
        message: err instanceof Error ? err.message : 'Unknown error',
      });
    } finally {
      setIsIngesting(false);
    }
  }

  if (error) {
    return (
      <div style={{ padding: 40, fontFamily: 'system-ui, sans-serif' }}>
        <h1 style={{ fontSize: 20, fontWeight: 700 }}>Admin Dashboard</h1>
        <p style={{ color: '#dc2626', marginTop: 12 }}>Failed to load stats: {error}</p>
      </div>
    );
  }

  if (!stats) {
    return (
      <div style={{ padding: 40, fontFamily: 'system-ui, sans-serif' }}>
        <h1 style={{ fontSize: 20, fontWeight: 700 }}>Admin Dashboard</h1>
        <p style={{ color: '#6b7280', marginTop: 12 }}>Loading...</p>
      </div>
    );
  }

  const total =
    stats.confidenceDistribution.verified +
    stats.confidenceDistribution.interpreted +
    stats.confidenceDistribution.unknown;

  const sortedDocs = [...stats.documents].sort((a, b) => {
    if (sortKey === 'name') {
      return sortAsc ? a.name.localeCompare(b.name) : b.name.localeCompare(a.name);
    }
    return sortAsc ? a.fragment_count - b.fragment_count : b.fragment_count - a.fragment_count;
  });

  function handleSort(key: 'name' | 'fragment_count') {
    if (sortKey === key) {
      setSortAsc(!sortAsc);
    } else {
      setSortKey(key);
      setSortAsc(true);
    }
  }

  return (
    <div style={{ padding: '32px 40px', fontFamily: 'system-ui, sans-serif', maxWidth: 1100 }}>
      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: 24 }}>
        <h1 style={{ fontSize: 20, fontWeight: 700, margin: 0, color: '#111827' }}>
          Admin Dashboard
        </h1>
        <a href="/" style={{ fontSize: 13, color: '#6b7280', textDecoration: 'none' }}>
          Back to app
        </a>
      </div>

      {/* Ingestion form */}
      <div
        style={{
          padding: '20px 24px',
          marginBottom: 24,
          background: 'rgba(255, 255, 255, 0.85)',
          backdropFilter: 'blur(12px)',
          border: '1px solid #e5e7eb',
          borderRadius: 12,
        }}
      >
        <h2 style={{ fontSize: 14, fontWeight: 600, color: '#374151', marginTop: 0, marginBottom: 16 }}>
          Ingest New Regulation
        </h2>
        <form onSubmit={handleIngest}>
          <div style={{ display: 'grid', gridTemplateColumns: 'repeat(3, 1fr)', gap: 12, marginBottom: 16 }}>
            <input
              type="text"
              placeholder="Document name"
              required
              disabled={isIngesting}
              value={ingestForm.name}
              onChange={(e) => setIngestForm({ ...ingestForm, name: e.target.value })}
              style={{
                padding: '8px 12px',
                border: '1px solid #d1d5db',
                borderRadius: 6,
                fontSize: 13,
                outline: 'none',
              }}
            />
            <input
              type="url"
              placeholder="PDF URL"
              required
              disabled={isIngesting}
              value={ingestForm.url}
              onChange={(e) => setIngestForm({ ...ingestForm, url: e.target.value })}
              style={{
                padding: '8px 12px',
                border: '1px solid #d1d5db',
                borderRadius: 6,
                fontSize: 13,
                outline: 'none',
              }}
            />
            <input
              type="text"
              placeholder="Specific plan name"
              required
              disabled={isIngesting}
              value={ingestForm.specificPlan}
              onChange={(e) => setIngestForm({ ...ingestForm, specificPlan: e.target.value })}
              style={{
                padding: '8px 12px',
                border: '1px solid #d1d5db',
                borderRadius: 6,
                fontSize: 13,
                outline: 'none',
              }}
            />
          </div>
          <div style={{ display: 'flex', alignItems: 'center', gap: 12 }}>
            {ingestStatus && (
              <span
                style={{
                  fontSize: 13,
                  color: ingestStatus.type === 'success' ? '#16a34a' : '#dc2626',
                }}
              >
                {ingestStatus.message}
              </span>
            )}
            <button
              type="submit"
              disabled={isIngesting}
              style={{
                marginLeft: 'auto',
                padding: '8px 20px',
                background: isIngesting ? '#9ca3af' : '#2563eb',
                color: '#fff',
                border: 'none',
                borderRadius: 6,
                fontSize: 13,
                fontWeight: 600,
                cursor: isIngesting ? 'not-allowed' : 'pointer',
              }}
            >
              {isIngesting ? 'Ingesting...' : 'Ingest'}
            </button>
          </div>
        </form>
      </div>

      {/* Stats cards */}
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(3, 1fr)', gap: 16, marginBottom: 28 }}>
        <StatCard label="Total Documents" value={stats.totalDocs} />
        <StatCard label="Rule Fragments" value={stats.totalFragments} />
        <StatCard label="Errors / Unknown" value={stats.errorCount} color="#dc2626" />
      </div>

      {/* Confidence distribution bar */}
      <div style={{ marginBottom: 28 }}>
        <h2 style={{ fontSize: 14, fontWeight: 600, color: '#374151', marginBottom: 8 }}>
          Confidence Distribution
        </h2>
        {total > 0 ? (
          <>
            <div
              style={{
                display: 'flex',
                height: 28,
                borderRadius: 6,
                overflow: 'hidden',
                border: '1px solid #e5e7eb',
              }}
            >
              {(['verified', 'interpreted', 'unknown'] as const).map((level) => {
                const count = stats.confidenceDistribution[level];
                if (count === 0) return null;
                const pct = (count / total) * 100;
                return (
                  <div
                    key={level}
                    style={{
                      width: `${pct}%`,
                      background: CONF_COLORS[level],
                      display: 'flex',
                      alignItems: 'center',
                      justifyContent: 'center',
                      color: '#fff',
                      fontSize: 12,
                      fontWeight: 600,
                      fontFamily: 'ui-monospace, monospace',
                      minWidth: count > 0 ? 32 : 0,
                    }}
                    title={`${level}: ${count}`}
                  >
                    {count}
                  </div>
                );
              })}
            </div>
            <div style={{ display: 'flex', gap: 16, marginTop: 6 }}>
              {(['verified', 'interpreted', 'unknown'] as const).map((level) => (
                <span key={level} style={{ fontSize: 12, color: '#6b7280' }}>
                  <span
                    style={{
                      display: 'inline-block',
                      width: 10,
                      height: 10,
                      borderRadius: 2,
                      background: CONF_COLORS[level],
                      marginRight: 4,
                      verticalAlign: 'middle',
                    }}
                  />
                  {level} ({stats.confidenceDistribution[level]})
                </span>
              ))}
            </div>
          </>
        ) : (
          <p style={{ color: '#9ca3af', fontSize: 13 }}>No fragments ingested yet.</p>
        )}
      </div>

      {/* Document table */}
      <div>
        <h2 style={{ fontSize: 14, fontWeight: 600, color: '#374151', marginBottom: 8 }}>
          Documents
        </h2>
        <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: 13 }}>
          <thead>
            <tr style={{ borderBottom: '2px solid #e5e7eb', textAlign: 'left' }}>
              <th style={{ padding: '8px 12px', width: 28 }} />
              <SortableHeader
                label="Document Name"
                active={sortKey === 'name'}
                asc={sortAsc}
                onClick={() => handleSort('name')}
              />
              <SortableHeader
                label="Fragments"
                active={sortKey === 'fragment_count'}
                asc={sortAsc}
                onClick={() => handleSort('fragment_count')}
              />
              <th style={{ padding: '8px 12px' }}>Status</th>
              <th style={{ padding: '8px 12px' }}>Last Updated</th>
            </tr>
          </thead>
          <tbody>
            {sortedDocs.map((doc) => {
              const isExpanded = expandedDoc === doc.name;
              return (
                <DocRow
                  key={doc.name}
                  doc={doc}
                  isExpanded={isExpanded}
                  onToggle={() => setExpandedDoc(isExpanded ? null : doc.name)}
                />
              );
            })}
            {sortedDocs.length === 0 && (
              <tr>
                <td colSpan={5} style={{ padding: 20, textAlign: 'center', color: '#9ca3af' }}>
                  No documents found.
                </td>
              </tr>
            )}
          </tbody>
        </table>
      </div>
    </div>
  );
}

function StatCard({ label, value, color }: { label: string; value: number; color?: string }) {
  return (
    <div
      style={{
        padding: '16px 20px',
        border: '1px solid #e5e7eb',
        borderRadius: 8,
        background: '#fff',
      }}
    >
      <div style={{ fontSize: 12, color: '#6b7280', marginBottom: 4 }}>{label}</div>
      <div
        style={{
          fontSize: 28,
          fontWeight: 700,
          fontFamily: 'ui-monospace, monospace',
          color: color || '#111827',
        }}
      >
        {value}
      </div>
    </div>
  );
}

function SortableHeader({
  label,
  active,
  asc,
  onClick,
}: {
  label: string;
  active: boolean;
  asc: boolean;
  onClick: () => void;
}) {
  return (
    <th
      style={{ padding: '8px 12px', cursor: 'pointer', userSelect: 'none' }}
      onClick={onClick}
    >
      {label} {active ? (asc ? '\u25B2' : '\u25BC') : ''}
    </th>
  );
}

function ConfidenceBadge({
  level,
  reasoning,
}: {
  level: string;
  reasoning: string | null;
}) {
  return (
    <span
      title={reasoning || undefined}
      style={{
        display: 'inline-block',
        padding: '2px 8px',
        borderRadius: 4,
        fontSize: 11,
        fontWeight: 600,
        background: CONF_BG[level] || '#f3f4f6',
        color: CONF_COLORS[level] || '#374151',
        cursor: reasoning ? 'help' : 'default',
      }}
    >
      {level}
    </span>
  );
}

function DocRow({
  doc,
  isExpanded,
  onToggle,
}: {
  doc: DocumentStats;
  isExpanded: boolean;
  onToggle: () => void;
}) {
  const statusColor = doc.status === 'ingested' ? '#16a34a' : '#9ca3af';
  return (
    <>
      <tr
        style={{
          borderBottom: '1px solid #f3f4f6',
          cursor: 'pointer',
          background: isExpanded ? '#f9fafb' : 'transparent',
        }}
        onClick={onToggle}
      >
        <td style={{ padding: '8px 12px', fontSize: 12, color: '#9ca3af' }}>
          {isExpanded ? '\u25BC' : '\u25B6'}
        </td>
        <td style={{ padding: '8px 12px', fontWeight: 500 }}>{doc.name}</td>
        <td style={{ padding: '8px 12px', fontFamily: 'ui-monospace, monospace' }}>
          {doc.fragment_count}
        </td>
        <td style={{ padding: '8px 12px' }}>
          <span
            style={{
              display: 'inline-block',
              padding: '2px 8px',
              borderRadius: 4,
              fontSize: 11,
              fontWeight: 600,
              background: doc.status === 'ingested' ? '#dcfce7' : '#f3f4f6',
              color: statusColor,
            }}
          >
            {doc.status}
          </span>
        </td>
        <td style={{ padding: '8px 12px', color: '#6b7280', fontSize: 12, fontFamily: 'ui-monospace, monospace' }}>
          {doc.last_updated ? new Date(doc.last_updated).toLocaleString() : '--'}
        </td>
      </tr>
      {isExpanded && (
        <tr>
          <td colSpan={5} style={{ padding: '0 12px 12px 40px', background: '#f9fafb' }}>
            <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: 12, marginTop: 4 }}>
              <thead>
                <tr style={{ borderBottom: '1px solid #e5e7eb', color: '#6b7280' }}>
                  <th style={{ padding: '6px 8px', textAlign: 'left' }}>Constraint</th>
                  <th style={{ padding: '6px 8px', textAlign: 'left' }}>Value</th>
                  <th style={{ padding: '6px 8px', textAlign: 'left' }}>Unit</th>
                  <th style={{ padding: '6px 8px', textAlign: 'left' }}>Confidence</th>
                  <th style={{ padding: '6px 8px', textAlign: 'left' }}>Source Section</th>
                </tr>
              </thead>
              <tbody>
                {doc.fragments.map((frag, i) => (
                  <tr key={i} style={{ borderBottom: '1px solid #f3f4f6' }}>
                    <td style={{ padding: '6px 8px', fontFamily: 'ui-monospace, monospace' }}>
                      {frag.constraint_type}
                    </td>
                    <td style={{ padding: '6px 8px', fontFamily: 'ui-monospace, monospace' }}>
                      {frag.value != null ? frag.value : frag.value_text || '--'}
                    </td>
                    <td style={{ padding: '6px 8px' }}>{frag.unit || '--'}</td>
                    <td style={{ padding: '6px 8px' }}>
                      <ConfidenceBadge level={frag.confidence} reasoning={frag.extraction_reasoning} />
                    </td>
                    <td style={{ padding: '6px 8px', color: '#6b7280' }}>
                      {frag.source_section || '--'}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </td>
        </tr>
      )}
    </>
  );
}
