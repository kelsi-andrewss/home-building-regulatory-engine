import { createContext, useContext, useReducer, useCallback } from 'react';
import type { ReactNode } from 'react';
import type { AssessmentResponse } from '../api/client';
import { assessParcel } from '../api/client';

export interface ProjectParams {
  bedrooms: number | null;
  bathrooms: number | null;
  sqft: number | null;
}

export interface AssessmentState {
  assessment: AssessmentResponse | null;
  projectParams: ProjectParams;
  feedbackMap: Record<string, 'up' | 'down'>;
  isDirty: boolean;
  loading: boolean;
}

type Action =
  | { type: 'SET_ASSESSMENT'; payload: AssessmentResponse }
  | { type: 'SET_PARAMS'; payload: Partial<ProjectParams> }
  | { type: 'SET_DIRTY'; payload: boolean }
  | { type: 'SET_FEEDBACK'; payload: { name: string; vote: 'up' | 'down' | null } }
  | { type: 'SET_LOADING'; payload: boolean };

const initialState: AssessmentState = {
  assessment: null,
  projectParams: { bedrooms: null, bathrooms: null, sqft: null },
  feedbackMap: {},
  isDirty: false,
  loading: false,
};

function reducer(state: AssessmentState, action: Action): AssessmentState {
  switch (action.type) {
    case 'SET_ASSESSMENT':
      return { ...state, assessment: action.payload, loading: false, isDirty: false };
    case 'SET_PARAMS':
      return {
        ...state,
        projectParams: { ...state.projectParams, ...action.payload },
        isDirty: true,
      };
    case 'SET_DIRTY':
      return { ...state, isDirty: action.payload };
    case 'SET_FEEDBACK': {
      const next = { ...state.feedbackMap };
      if (action.payload.vote === null) {
        delete next[action.payload.name];
      } else {
        next[action.payload.name] = action.payload.vote;
      }
      return { ...state, feedbackMap: next };
    }
    case 'SET_LOADING':
      return { ...state, loading: action.payload };
    default:
      return state;
  }
}

interface ContextValue extends AssessmentState {
  dispatch: React.Dispatch<Action>;
  reassess: () => Promise<void>;
}

const AssessmentContext = createContext<ContextValue | null>(null);

export function AssessmentProvider({ children }: { children: ReactNode }) {
  const [state, dispatch] = useReducer(reducer, initialState);

  const reassess = useCallback(async () => {
    if (!state.assessment) return;
    dispatch({ type: 'SET_LOADING', payload: true });
    try {
      const result = await assessParcel({
        address: state.assessment.parcel.address,
        apn: state.assessment.parcel.apn,
        ...state.projectParams,
      });
      dispatch({ type: 'SET_ASSESSMENT', payload: result });
    } catch (err) {
      console.error('Reassessment failed:', err);
      dispatch({ type: 'SET_LOADING', payload: false });
    }
  }, [state.assessment, state.projectParams]);

  return (
    <AssessmentContext.Provider value={{ ...state, dispatch, reassess }}>
      {children}
    </AssessmentContext.Provider>
  );
}

export function useAssessment(): ContextValue {
  const ctx = useContext(AssessmentContext);
  if (!ctx) throw new Error('useAssessment must be used within AssessmentProvider');
  return ctx;
}
