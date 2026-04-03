import { useAssessment } from '../context/AssessmentContext';

export default function ParameterInputs() {
  const { projectParams, isDirty, loading, dispatch, reassess } = useAssessment();

  function handleChange(field: 'bedrooms' | 'bathrooms' | 'sqft', raw: string) {
    const value = raw === '' ? null : Number(raw);
    dispatch({ type: 'SET_PARAMS', payload: { [field]: value } });
  }

  return (
    <div
      style={{
        display: 'flex',
        alignItems: 'center',
        gap: '20px',
        paddingBottom: '24px',
        borderBottom: '1px solid var(--border-color)',
        flexWrap: 'wrap',
      }}
    >
      <div className="param-input-group">
        <label className="param-label">Bedrooms</label>
        <input
          type="number"
          min={0}
          value={projectParams.bedrooms ?? ''}
          onChange={(e) => handleChange('bedrooms', e.target.value)}
          className="param-input"
          style={{ borderColor: isDirty ? 'var(--warning)' : 'var(--border-color)' }}
        />
      </div>

      <div className="param-input-group">
        <label className="param-label">Bathrooms</label>
        <input
          type="number"
          min={0}
          value={projectParams.bathrooms ?? ''}
          onChange={(e) => handleChange('bathrooms', e.target.value)}
          className="param-input"
          style={{ borderColor: isDirty ? 'var(--warning)' : 'var(--border-color)' }}
        />
      </div>

      <div className="param-input-group">
        <label className="param-label">Sq Ft</label>
        <input
          type="number"
          min={0}
          value={projectParams.sqft ?? ''}
          onChange={(e) => handleChange('sqft', e.target.value)}
          className="param-input"
          style={{ width: '90px', borderColor: isDirty ? 'var(--warning)' : 'var(--border-color)' }}
        />
      </div>

      <button
        onClick={reassess}
        disabled={loading || !isDirty}
        className="btn-primary"
        style={{
          width: '42px',
          height: '42px',
          borderRadius: 'var(--radius-md)',
          padding: 0,
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'center',
          marginTop: '18px',
          opacity: isDirty ? 1 : 0.4,
          cursor: isDirty ? 'pointer' : 'not-allowed',
          background: isDirty ? 'var(--primary)' : 'var(--text-muted)',
        }}
      >
        {loading ? (
          <div className="spinner" style={{ width: '18px', height: '18px', borderLeftColor: 'white' }} />
        ) : (
          <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round">
            <path d="M21 12a9 9 0 0 0-9-9 9.75 9.75 0 0 0-6.74 2.74L3 8" />
            <path d="M3 3v5h5" />
            <path d="M3 12a9 9 0 0 0 9 9 9.75 9.75 0 0 0 6.74-2.74L21 16" />
            <path d="M16 16h5v5" />
          </svg>
        )}
      </button>

      {isDirty && (
        <span className="badge badge-warning" style={{ marginTop: '18px' }}>
          Pending Re-analysis
        </span>
      )}
    </div>
  );
}
