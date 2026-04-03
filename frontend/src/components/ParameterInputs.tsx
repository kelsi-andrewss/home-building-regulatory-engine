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
        gap: '16px',
        padding: '12px 0',
        marginBottom: '16px',
        borderBottom: '1px solid var(--border-color)',
        flexWrap: 'wrap',
      }}
    >
      <div className="param-input-group">
        <label className="param-label">Beds</label>
        <input
          type="number"
          min={0}
          value={projectParams.bedrooms ?? ''}
          onChange={(e) => handleChange('bedrooms', e.target.value)}
          className="param-input"
          style={{ borderColor: isDirty ? '#f59e0b' : 'var(--border-color)' }}
          aria-label="Bedrooms"
        />
      </div>

      <div className="param-input-group">
        <label className="param-label">Baths</label>
        <input
          type="number"
          min={0}
          value={projectParams.bathrooms ?? ''}
          onChange={(e) => handleChange('bathrooms', e.target.value)}
          className="param-input"
          style={{ borderColor: isDirty ? '#f59e0b' : 'var(--border-color)' }}
          aria-label="Bathrooms"
        />
      </div>

      <div className="param-input-group">
        <label className="param-label">Sqft</label>
        <input
          type="number"
          min={0}
          value={projectParams.sqft ?? ''}
          onChange={(e) => handleChange('sqft', e.target.value)}
          className="param-input"
          style={{ width: '90px', borderColor: isDirty ? '#f59e0b' : 'var(--border-color)' }}
          aria-label="Proposed square footage"
        />
      </div>

      <button
        onClick={reassess}
        disabled={loading || !isDirty}
        title="Re-assess with new parameters"
        className="btn-secondary"
        style={{
          width: '36px',
          height: '36px',
          borderRadius: '50%',
          padding: 0,
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'center',
          marginTop: '18px',
          color: isDirty ? 'var(--primary)' : 'var(--text-muted)',
          borderColor: isDirty ? 'var(--primary)' : 'var(--border-color)',
          background: isDirty ? 'rgba(37, 99, 235, 0.05)' : 'transparent',
        }}
      >
        {loading ? <div className="spinner" style={{ width: '16px', height: '16px', borderWidth: '2px' }} /> : '\u21BB'}
      </button>

      {isDirty && (
        <div
          style={{
            fontSize: '11px',
            color: '#d97706',
            fontWeight: 700,
            marginTop: '18px',
            background: '#fffbeb',
            padding: '4px 8px',
            borderRadius: '4px',
            border: '1px solid #fde68a',
          }}
        >
          Changed
        </div>
      )}
    </div>
  );
}
