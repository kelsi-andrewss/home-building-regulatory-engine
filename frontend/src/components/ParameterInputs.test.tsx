import { render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { describe, it, expect, vi, beforeEach } from 'vitest';
import type { ProjectParams } from '../context/AssessmentContext';
import ParameterInputs from './ParameterInputs';

// Mocked context values
const mockDispatch = vi.fn();
const mockReassess = vi.fn();

interface MockContext {
  assessment: null;
  designConstraints: null;
  projectParams: ProjectParams;
  feedbackMap: Record<string, 'up' | 'down'>;
  isDirty: boolean;
  loading: boolean;
  dispatch: typeof mockDispatch;
  reassess: typeof mockReassess;
}

let mockContextValue: MockContext = {
  assessment: null,
  designConstraints: null,
  projectParams: { bedrooms: null, bathrooms: null, sqft: null },
  feedbackMap: {},
  isDirty: false,
  loading: false,
  dispatch: mockDispatch,
  reassess: mockReassess,
};

vi.mock('../context/AssessmentContext', () => ({
  useAssessment: () => mockContextValue,
}));

describe('ParameterInputs', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    mockContextValue = {
      assessment: null,
      designConstraints: null,
      projectParams: { bedrooms: null, bathrooms: null, sqft: null },
      feedbackMap: {},
      isDirty: false,
      loading: false,
      dispatch: mockDispatch,
      reassess: mockReassess,
    };
  });

  it('renders three labeled inputs', () => {
    render(<ParameterInputs />);

    expect(screen.getByLabelText('Bedrooms')).toBeInTheDocument();
    expect(screen.getByLabelText('Bathrooms')).toBeInTheDocument();
    expect(screen.getByLabelText('Sq Ft')).toBeInTheDocument();
  });

  it('dispatches SET_PARAMS with numeric value when user types', async () => {
    const user = userEvent.setup();
    render(<ParameterInputs />);

    const bedroomsInput = screen.getByLabelText('Bedrooms');
    await user.type(bedroomsInput, '3');

    expect(mockDispatch).toHaveBeenCalledWith({
      type: 'SET_PARAMS',
      payload: { bedrooms: 3 },
    });
  });

  it('dispatches SET_PARAMS with null when input is cleared', async () => {
    mockContextValue.projectParams = { bedrooms: 3, bathrooms: null, sqft: null };
    const user = userEvent.setup();
    render(<ParameterInputs />);

    const bedroomsInput = screen.getByLabelText('Bedrooms');
    await user.clear(bedroomsInput);

    expect(mockDispatch).toHaveBeenCalledWith({
      type: 'SET_PARAMS',
      payload: { bedrooms: null },
    });
  });

  it('disables reassess button when not dirty', () => {
    render(<ParameterInputs />);

    const button = screen.getByRole('button');
    expect(button).toBeDisabled();
  });

  it('enables reassess button when dirty', () => {
    mockContextValue.isDirty = true;
    render(<ParameterInputs />);

    const button = screen.getByRole('button');
    expect(button).toBeEnabled();
  });

  it('calls reassess when button clicked while dirty', async () => {
    mockContextValue.isDirty = true;
    const user = userEvent.setup();
    render(<ParameterInputs />);

    await user.click(screen.getByRole('button'));
    expect(mockReassess).toHaveBeenCalledOnce();
  });

  it('shows pending badge when dirty', () => {
    mockContextValue.isDirty = true;
    render(<ParameterInputs />);

    expect(screen.getByText('Pending Re-analysis')).toBeInTheDocument();
  });

  it('hides pending badge when not dirty', () => {
    render(<ParameterInputs />);

    expect(screen.queryByText('Pending Re-analysis')).not.toBeInTheDocument();
  });

  it('disables reassess button while loading', () => {
    mockContextValue.isDirty = true;
    mockContextValue.loading = true;
    render(<ParameterInputs />);

    expect(screen.getByRole('button')).toBeDisabled();
  });
});
