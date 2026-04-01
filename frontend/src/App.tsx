import { useEffect, useReducer, useState } from 'react';
import 'mapbox-gl/dist/mapbox-gl.css';
import type { AssessmentResponse, BuildingType, Constraint, GeocodingResult } from './api/client';
import { assessParcel } from './api/client';
import AddressSearch from './components/AddressSearch';
import BuildingTypeSelector from './components/BuildingTypeSelector';
import BuildabilityReport from './components/BuildabilityReport';
import CitationsPanel from './components/CitationsPanel';
import MapboxMap from './components/MapboxMap';
import AdminDashboard from './pages/AdminDashboard';

interface AppState {
  assessment: AssessmentResponse | null;
  selectedType: BuildingType;
  isSearching: boolean;
  hoveredConstraint: string | null;
}

type Action =
  | { type: 'SELECT_PARCEL' }
  | { type: 'SET_ASSESSMENT'; payload: AssessmentResponse }
  | { type: 'SEARCH_FAILED' }
  | { type: 'SET_BUILDING_TYPE'; payload: BuildingType }
  | { type: 'SET_HOVERED_CONSTRAINT'; payload: string | null };

const initialState: AppState = {
  assessment: null,
  selectedType: 'SFH',
  isSearching: false,
  hoveredConstraint: null,
};

function appReducer(state: AppState, action: Action): AppState {
  switch (action.type) {
    case 'SELECT_PARCEL':
      return { ...state, isSearching: true };
    case 'SET_ASSESSMENT':
      return { ...state, isSearching: false, assessment: action.payload };
    case 'SEARCH_FAILED':
      return { ...state, isSearching: false };
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

  return <MainApp />;
}

function MainApp() {
  const [state, dispatch] = useReducer(appReducer, initialState);

  async function handleParcelSelect(candidate: GeocodingResult) {
    dispatch({ type: 'SELECT_PARCEL' });
    try {
      const result = await assessParcel({ address: candidate.address, apn: candidate.apn });
      dispatch({ type: 'SET_ASSESSMENT', payload: result });
    } catch (err) {
      console.error('Assessment failed:', err);
      dispatch({ type: 'SEARCH_FAILED' });
    }
  }

  const availableTypes: BuildingType[] = state.assessment
    ? (state.assessment.building_types.map((bt) => bt.type) as BuildingType[])
    : [];

  const currentConstraints: Constraint[] = state.assessment
    ? (state.assessment.building_types.find((bt) => bt.type === state.selectedType)?.constraints ?? [])
    : [];

  return (
    <div style={{ display: 'grid', gridTemplateColumns: '400px 1fr', height: '100vh' }}>
      {/* Sidebar */}
      <div
        style={{
          overflowY: 'auto',
          borderRight: '1px solid #e5e7eb',
          padding: '20px 16px',
          background: '#fff',
        }}
      >
        <h1 style={{ fontSize: '18px', fontWeight: 700, color: '#111827', margin: '0 0 16px' }}>
          Building Regulatory Engine
        </h1>
        <AddressSearch onSelect={handleParcelSelect} />

        {state.assessment && (
          <div style={{ marginTop: '20px' }}>
            <BuildingTypeSelector
              selectedType={state.selectedType}
              availableTypes={availableTypes}
              onSelect={(t) => dispatch({ type: 'SET_BUILDING_TYPE', payload: t })}
            />
            <BuildabilityReport
              assessment={state.assessment}
              selectedType={state.selectedType}
              onHoverConstraint={(name) =>
                dispatch({ type: 'SET_HOVERED_CONSTRAINT', payload: name })
              }
            />
            <CitationsPanel constraints={currentConstraints} />
          </div>
        )}

        {!state.assessment && !state.isSearching && (
          <div style={{ marginTop: '40px', textAlign: 'center', color: '#9ca3af', fontSize: '14px' }}>
            Search for an address to get started.
          </div>
        )}
      </div>

      {/* Map panel */}
      <div style={{ position: 'relative' }}>
        <MapboxMap
          assessment={state.assessment}
          hoveredConstraint={state.hoveredConstraint}
        />
        {state.isSearching && (
          <div
            style={{
              position: 'absolute',
              inset: 0,
              background: 'rgba(255,255,255,0.6)',
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'center',
              zIndex: 5,
            }}
          >
            <div
              style={{
                width: '40px',
                height: '40px',
                border: '3px solid #d1d5db',
                borderTopColor: '#3b82f6',
                borderRadius: '50%',
                animation: 'spin 0.6s linear infinite',
              }}
            />
          </div>
        )}
      </div>
    </div>
  );
}
