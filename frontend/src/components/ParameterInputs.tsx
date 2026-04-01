import { useAssessment } from '../context/AssessmentContext';

export default function ParameterInputs() {
  const { projectParams, isDirty, loading, dispatch, reassess } = useAssessment();

  function handleChange(field: 'bedrooms' | 'bathrooms' | 'sqft', raw: string) {
    const value = raw === '' ? null : Number(raw);
    dispatch({ type: 'SET_PARAMS', payload: { [field]: value } });
  }

  const borderColor = isDirty ? '#f59e0b' : '#d1d5db';

  const inputStyle: React.CSSProperties = {
    width: '72px',
    padding: '4px 8px',
    border: `1.5px solid ${borderColor}`,
    borderRadius: '6px',
    fontSize: '13px',
    outline: 'none',
    textAlign: 'center',
  };

  const labelStyle: React.CSSProperties = {
    fontSize: '11px',
    color: '#6b7280',
    fontWeight: 600,
    textTransform: 'uppercase',
    letterSpacing: '0.5px',
  };

  return (
    <div
      style={{
        display: 'flex',
        alignItems: 'center',
        gap: '12px',
        padding: '10px 0',
        marginBottom: '12px',
        borderBottom: '1px solid #e5e7eb',
        flexWrap: 'wrap',
      }}
    >
      <div style={{ display: 'flex', flexDirection: 'column', gap: '2px' }}>
        <label style={labelStyle}>Beds</label>
        <input
          type="number"
          min={0}
          value={projectParams.bedrooms ?? ''}
          onChange={(e) => handleChange('bedrooms', e.target.value)}
          style={inputStyle}
          aria-label="Bedrooms"
        />
      </div>

      <div style={{ display: 'flex', flexDirection: 'column', gap: '2px' }}>
        <label style={labelStyle}>Baths</label>
        <input
          type="number"
          min={0}
          value={projectParams.bathrooms ?? ''}
          onChange={(e) => handleChange('bathrooms', e.target.value)}
          style={inputStyle}
          aria-label="Bathrooms"
        />
      </div>

      <div style={{ display: 'flex', flexDirection: 'column', gap: '2px' }}>
        <label style={labelStyle}>Sqft</label>
        <input
          type="number"
          min={0}
          value={projectParams.sqft ?? ''}
          onChange={(e) => handleChange('sqft', e.target.value)}
          style={{ ...inputStyle, width: '88px' }}
          aria-label="Proposed square footage"
        />
      </div>

      <button
        onClick={reassess}
        disabled={loading || !isDirty}
        title="Re-assess with new parameters"
        aria-label="Re-assess"
        style={{
          width: '32px',
          height: '32px',
          borderRadius: '50%',
          border: '1.5px solid #d1d5db',
          background: loading || !isDirty ? '#f3f4f6' : '#fff',
          cursor: loading || !isDirty ? 'not-allowed' : 'pointer',
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'center',
          fontSize: '14px',
          color: loading || !isDirty ? '#9ca3af' : '#3b82f6',
          marginTop: '14px',
          flexShrink: 0,
        }}
      >
        {'\u21BB'}
      </button>

      {isDirty && (
        <span
          style={{
            fontSize: '11px',
            color: '#f59e0b',
            fontWeight: 600,
            marginTop: '14px',
          }}
        >
          Parameters changed
        </span>
      )}
    </div>
  );
}
