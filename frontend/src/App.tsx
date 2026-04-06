import { useEffect, useReducer, useState } from 'react';
import 'mapbox-gl/dist/mapbox-gl.css';
import type { BuildingType, GeocodingResult } from './api/client';
import { assessParcel, fetchDesignConstraints } from './api/client';
import AddressSearch from './components/AddressSearch';
import BuildingTypeSelector from './components/BuildingTypeSelector';
import BuildabilityReport from './components/BuildabilityReport';
import MapboxMap from './components/MapboxMap';
import AdminDashboard from './pages/AdminDashboard';
import { AssessmentProvider, useAssessment } from './context/AssessmentContext';

interface ZoneError {
  address: string;
  detail: string;
}

interface AppState {
  selectedType: BuildingType;
  isSearching: boolean;
  hoveredConstraint: string | null;
  zoneError: ZoneError | null;
  error: string | null;
}

type Action =
  | { type: 'SELECT_PARCEL' }
  | { type: 'ASSESSMENT_LOADED' }
  | { type: 'SEARCH_FAILED' }
  | { type: 'SET_ZONE_ERROR'; payload: ZoneError }
  | { type: 'SET_ERROR'; payload: string }
  | { type: 'CLEAR_ERROR' }
  | { type: 'SET_BUILDING_TYPE'; payload: BuildingType }
  | { type: 'SET_HOVERED_CONSTRAINT'; payload: string | null };

const initialState: AppState = {
  selectedType: 'SFH',
  isSearching: false,
  hoveredConstraint: null,
  zoneError: null,
  error: null,
};

function appReducer(state: AppState, action: Action): AppState {
  switch (action.type) {
    case 'SELECT_PARCEL':
      return { ...state, isSearching: true, zoneError: null, error: null };
    case 'ASSESSMENT_LOADED':
      return { ...state, isSearching: false, zoneError: null, error: null };
    case 'SEARCH_FAILED':
      return { ...state, isSearching: false };
    case 'SET_ZONE_ERROR':
      return { ...state, isSearching: false, zoneError: action.payload, error: null };
    case 'SET_ERROR':
      return { ...state, isSearching: false, error: action.payload };
    case 'CLEAR_ERROR':
      return { ...state, error: null };
    case 'SET_BUILDING_TYPE':
      return { ...state, selectedType: action.payload };
    case 'SET_HOVERED_CONSTRAINT':
      return { ...state, hoveredConstraint: action.payload };
    default:
      return state;
  }
}

function useHashRoute() {
  const [hash, setHash] = useState(window.location.hash);
  useEffect(() => {
    const onHashChange = () => setHash(window.location.hash);
    window.addEventListener('hashchange', onHashChange);
    return () => window.removeEventListener('hashchange', onHashChange);
  }, []);
  return hash;
}

export default function App() {
  const hash = useHashRoute();

  if (hash === '#/admin') {
    return <AdminDashboard />;
  }

  return (
    <AssessmentProvider>
      <MainApp />
    </AssessmentProvider>
  );
}

function MainApp() {
  const [state, dispatch] = useReducer(appReducer, initialState);
  const { assessment, designConstraints, dispatch: ctxDispatch } = useAssessment();

  async function handleParcelSelect(candidate: GeocodingResult) {
    dispatch({ type: 'SELECT_PARCEL' });
    try {
      const result = await assessParcel({ address: candidate.address, apn: candidate.apn });
      const resultApn = result.parcel.apn;
      dispatch({ type: 'ASSESSMENT_LOADED' });
      ctxDispatch({ type: 'SET_ASSESSMENT', payload: result });

      try {
        const dc = await fetchDesignConstraints({ address: candidate.address, apn: candidate.apn, building_type: state.selectedType });
        if (dc.parcel_apn === resultApn) {
          ctxDispatch({ type: 'SET_DESIGN_CONSTRAINTS', payload: dc });
        }
      } catch (dcErr) {
        console.error('Design constraints fetch failed:', dcErr);
      }
    } catch (err) {
      ctxDispatch({ type: 'CLEAR_ASSESSMENT' });
      const raw = err instanceof Error ? err.message : String(err);
      let detail = raw;
      try {
        const parsed = JSON.parse(raw);
        if (parsed.detail) detail = parsed.detail;
      } catch { /* not JSON, use raw */ }

      if (detail.includes('not supported')) {
        dispatch({ type: 'SET_ZONE_ERROR', payload: { address: candidate.address, detail } });
      } else if (detail.includes('Upstream lookup failed')) {
        dispatch({ type: 'SET_ERROR', payload: 'Government data unavailable for this parcel — try again later' });
      } else {
        dispatch({ type: 'SET_ERROR', payload: 'Something went wrong — try a different address' });
      }
    }
  }

  useEffect(() => {
    if (!assessment) return;
    fetchDesignConstraints({
      address: assessment.parcel.address,
      apn: assessment.parcel.apn,
      building_type: state.selectedType,
    })
      .then((dc) => ctxDispatch({ type: 'SET_DESIGN_CONSTRAINTS', payload: dc }))
      .catch((err) => console.error('Design constraints fetch failed:', err));
  }, [state.selectedType]);

  const availableTypes: BuildingType[] = assessment
    ? (assessment.building_types.map((bt) => bt.type) as BuildingType[])
    : [];

  return (
    <div className="app-container">
      {/* Sidebar */}
      <aside className="sidebar">
        <div className="sidebar-content">
          <header>
            <h1 className="sidebar-title">Regulatory Engine</h1>
            <p className="sidebar-subtitle">LA County Residential Building Code Search</p>
          </header>
          
          <AddressSearch onSelect={handleParcelSelect} />

          {state.error && (
            <div style={{
              marginTop: '8px',
              padding: '12px',
              background: '#fef2f2',
              border: '1px solid #fca5a5',
              borderRadius: '8px',
              color: '#991b1b',
              fontSize: '13px',
              display: 'flex',
              justifyContent: 'space-between',
              alignItems: 'flex-start',
              gap: '8px',
            }}>
              <span>{state.error}</span>
              <button
                onClick={() => dispatch({ type: 'CLEAR_ERROR' })}
                style={{
                  background: 'none',
                  border: 'none',
                  color: '#991b1b',
                  cursor: 'pointer',
                  fontSize: '16px',
                  lineHeight: 1,
                  padding: 0,
                  flexShrink: 0,
                }}
                aria-label="Dismiss error"
              >
                &times;
              </button>
            </div>
          )}

          {assessment && (
            <div style={{ display: 'flex', flexDirection: 'column', gap: '32px' }}>
              {(assessment.parcel.existing_units != null || assessment.parcel.existing_sqft != null) && (
                <div style={{
                  padding: '16px 20px',
                  background: 'var(--bg-card)',
                  borderRadius: 'var(--radius-lg)',
                  border: '1px solid var(--border-color)',
                }}>
                  <div style={{ fontSize: '13px', fontWeight: 700, color: 'var(--text-main)', marginBottom: '8px' }}>Existing Structure</div>
                  <div style={{ display: 'flex', gap: '24px', fontSize: '12px', fontWeight: 600, color: 'var(--text-muted)' }}>
                    {assessment.parcel.existing_units != null && (
                      <span>Units: {assessment.parcel.existing_units.toLocaleString()}</span>
                    )}
                    {assessment.parcel.existing_sqft != null && (
                      <span>Sq Ft: {assessment.parcel.existing_sqft.toLocaleString()}</span>
                    )}
                  </div>
                </div>
              )}
              <BuildingTypeSelector
                selectedType={state.selectedType}
                availableTypes={availableTypes}
                onSelect={(t) => dispatch({ type: 'SET_BUILDING_TYPE', payload: t })}
              />
              <BuildabilityReport
                assessment={assessment}
                selectedType={state.selectedType}
                designConstraints={designConstraints}
                onHoverConstraint={(name) =>
                  dispatch({ type: 'SET_HOVERED_CONSTRAINT', payload: name })
                }
              />
            </div>
          )}

          {state.zoneError && (
            <div style={{ marginTop: '24px', padding: '20px', background: 'var(--bg-card)', borderRadius: 'var(--radius-lg)', border: '1px solid var(--border)' }}>
              <div style={{ display: 'flex', alignItems: 'center', gap: '8px', marginBottom: '12px' }}>
                <div style={{ width: '8px', height: '8px', borderRadius: '50%', background: '#ef4444', flexShrink: 0 }} />
                <span style={{ fontWeight: 700, fontSize: '14px', color: 'var(--text-main)' }}>Zone Not Supported</span>
              </div>
              <div style={{ fontSize: '13px', color: 'var(--text-muted)', lineHeight: 1.6 }}>
                <div style={{ marginBottom: '8px' }}>
                  <span style={{ fontWeight: 600, color: 'var(--text-main)' }}>{state.zoneError.address}</span>
                </div>
                <div>{state.zoneError.detail}</div>
                <div style={{ marginTop: '12px', padding: '12px', background: 'var(--bg-main)', borderRadius: 'var(--radius-md)', fontSize: '12px' }}>
                  This engine currently supports LA residential zones only: RE, RS, R1–R4, and RD zones.
                </div>
              </div>
            </div>
          )}

          {!assessment && !state.zoneError && !state.error && !state.isSearching && (
            <div style={{ marginTop: '32px', textAlign: 'center', color: 'var(--text-muted)', fontSize: '15px', lineHeight: 1.6 }}>
              Enter a property address to analyze development potential and building constraints.
            </div>
          )}
        </div>
      </aside>

      {/* Map panel */}
      <main className="map-container">
        <MapboxMap
          assessment={assessment}
          hoveredConstraint={state.hoveredConstraint}
          designConstraints={designConstraints}
        />
        {state.isSearching && (
          <div className="loading-overlay">
            <div className="spinner" />
          </div>
        )}
      </main>
    </div>
  );
}
