import { useEffect, useReducer, useState } from 'react';
import 'mapbox-gl/dist/mapbox-gl.css';
import type { AssessmentResponse, BuildingType, Constraint, DesignConstraintResponse, GeocodingResult } from './api/client';
import { assessParcel, fetchDesignConstraints } from './api/client';
import AddressSearch from './components/AddressSearch';
import BuildingTypeSelector from './components/BuildingTypeSelector';
import BuildabilityReport from './components/BuildabilityReport';
import ChatInterface from './components/ChatInterface';
import CitationsPanel from './components/CitationsPanel';
import MapboxMap from './components/MapboxMap';
import AdminDashboard from './pages/AdminDashboard';
import { AssessmentProvider, useAssessment } from './context/AssessmentContext';

interface AppState {
  assessment: AssessmentResponse | null;
  designConstraints: DesignConstraintResponse | null;
  selectedType: BuildingType;
  isSearching: boolean;
  hoveredConstraint: string | null;
}

type Action =
  | { type: 'SELECT_PARCEL' }
  | { type: 'SET_ASSESSMENT'; payload: AssessmentResponse }
  | { type: 'SET_DESIGN_CONSTRAINTS'; payload: DesignConstraintResponse }
  | { type: 'SEARCH_FAILED' }
  | { type: 'SET_BUILDING_TYPE'; payload: BuildingType }
  | { type: 'SET_HOVERED_CONSTRAINT'; payload: string | null };

const initialState: AppState = {
  assessment: null,
  designConstraints: null,
  selectedType: 'SFH',
  isSearching: false,
  hoveredConstraint: null,
};

function appReducer(state: AppState, action: Action): AppState {
  switch (action.type) {
    case 'SELECT_PARCEL':
      return { ...state, isSearching: true };
    case 'SET_ASSESSMENT':
      return { ...state, isSearching: false, assessment: action.payload, designConstraints: null };
    case 'SET_DESIGN_CONSTRAINTS':
      return { ...state, designConstraints: action.payload };
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

  return (
    <AssessmentProvider>
      <MainApp />
    </AssessmentProvider>
  );
}

function MainApp() {
  const [state, dispatch] = useReducer(appReducer, initialState);
  const { dispatch: ctxDispatch } = useAssessment();

  async function handleParcelSelect(candidate: GeocodingResult) {
    dispatch({ type: 'SELECT_PARCEL' });
    try {
      const result = await assessParcel({ address: candidate.address, apn: candidate.apn });
      const resultApn = result.parcel.apn;
      dispatch({ type: 'SET_ASSESSMENT', payload: result });
      ctxDispatch({ type: 'SET_ASSESSMENT', payload: result });

      try {
        const dc = await fetchDesignConstraints({ address: candidate.address, apn: candidate.apn });
        if (dc.parcel_apn === resultApn) {
          dispatch({ type: 'SET_DESIGN_CONSTRAINTS', payload: dc });
          ctxDispatch({ type: 'SET_DESIGN_CONSTRAINTS', payload: dc });
        }
      } catch (dcErr) {
        console.error('Design constraints fetch failed:', dcErr);
      }
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
    <div className="app-container">
      {/* Sidebar */}
      <aside className="sidebar">
        <div className="sidebar-content">
          <header>
            <h1 className="sidebar-title">Regulatory Engine</h1>
            <p className="sidebar-subtitle">LA County Residential Building Code Search</p>
          </header>
          
          <AddressSearch onSelect={handleParcelSelect} />

          {state.assessment && (
            <div style={{ display: 'flex', flexDirection: 'column', gap: '32px' }}>
              <BuildingTypeSelector
                selectedType={state.selectedType}
                availableTypes={availableTypes}
                onSelect={(t) => dispatch({ type: 'SET_BUILDING_TYPE', payload: t })}
              />
              <BuildabilityReport
                assessment={state.assessment}
                selectedType={state.selectedType}
                designConstraints={state.designConstraints}
                onHoverConstraint={(name) =>
                  dispatch({ type: 'SET_HOVERED_CONSTRAINT', payload: name })
                }
              />
              <CitationsPanel constraints={currentConstraints} />
            </div>
          )}

          {!state.assessment && !state.isSearching && (
            <div style={{ marginTop: '32px', textAlign: 'center', color: 'var(--text-muted)', fontSize: '15px', lineHeight: 1.6 }}>
              Enter a property address to analyze development potential and building constraints.
            </div>
          )}
        </div>
      </aside>

      {/* Map panel */}
      <main className="map-container">
        <MapboxMap
          assessment={state.assessment}
          hoveredConstraint={state.hoveredConstraint}
          designConstraints={state.designConstraints}
        />
        {state.isSearching && (
          <div className="loading-overlay">
            <div className="spinner" />
          </div>
        )}
      </main>
      <ChatInterface />
    </div>
  );
}
