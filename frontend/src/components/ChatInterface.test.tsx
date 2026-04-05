import { render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { describe, it, expect, vi, beforeEach } from 'vitest';
import ChatInterface from './ChatInterface';
import type { AssessmentResponse } from '../api/client';

// jsdom doesn't implement scrollIntoView
Element.prototype.scrollIntoView = vi.fn();

const mockAssessment: AssessmentResponse = {
  parcel: {
    apn: '1234',
    address: '123 Main St, Los Angeles, CA',
    geometry: { type: 'Polygon', coordinates: [[[0, 0], [1, 0], [1, 1], [0, 1], [0, 0]]] },
    lot_area_sf: 5000,
    lot_width_ft: 50,
    year_built: 1950,
    existing_units: null,
    existing_sqft: null,
  },
  zoning: {
    zone_complete: 'R1-1',
    zone_class: 'R1',
    height_district: '1',
    general_plan_land_use: 'Low Residential',
    specific_plan: null,
    historic_overlay: null,
  },
  building_types: [],
  setback_geometry: null,
  summary: 'Test summary',
  assessment_id: 'test-id',
  conflicts: [],
};

let mockContextValue: {
  assessment: AssessmentResponse | null;
};

vi.mock('../context/AssessmentContext', () => ({
  useAssessment: () => mockContextValue,
}));

// Mock chatFollowup as an async generator
const mockChatFollowup = vi.fn();
vi.mock('../api/client', () => ({
  chatFollowup: (...args: unknown[]) => mockChatFollowup(...args),
}));

describe('ChatInterface', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    mockContextValue = { assessment: null };
  });

  it('renders the chat FAB button when closed', () => {
    render(<ChatInterface />);

    expect(screen.getByLabelText('Open chat')).toBeInTheDocument();
  });

  it('opens the chat window when FAB is clicked', async () => {
    const user = userEvent.setup();
    render(<ChatInterface />);

    await user.click(screen.getByLabelText('Open chat'));

    expect(screen.getByText('Regulatory Assistant')).toBeInTheDocument();
  });

  it('closes the chat window when close button is clicked', async () => {
    const user = userEvent.setup();
    render(<ChatInterface />);

    await user.click(screen.getByLabelText('Open chat'));
    expect(screen.getByText('Regulatory Assistant')).toBeInTheDocument();

    await user.click(screen.getByLabelText('Close chat'));
    expect(screen.queryByText('Regulatory Assistant')).not.toBeInTheDocument();
    expect(screen.getByLabelText('Open chat')).toBeInTheDocument();
  });

  it('shows disabled placeholder when no assessment is loaded', async () => {
    const user = userEvent.setup();
    render(<ChatInterface />);

    await user.click(screen.getByLabelText('Open chat'));

    expect(screen.getByText('Please select a parcel to start chatting.')).toBeInTheDocument();
    expect(screen.getByPlaceholderText('Select an address...')).toBeDisabled();
  });

  it('enables textarea when assessment is loaded', async () => {
    mockContextValue = { assessment: mockAssessment };
    const user = userEvent.setup();
    render(<ChatInterface />);

    await user.click(screen.getByLabelText('Open chat'));

    const textarea = screen.getByPlaceholderText('Ask about local regulations...');
    expect(textarea).not.toBeDisabled();
  });

  it('shows the parcel address in the header when assessment is loaded', async () => {
    mockContextValue = { assessment: mockAssessment };
    const user = userEvent.setup();
    render(<ChatInterface />);

    await user.click(screen.getByLabelText('Open chat'));

    expect(screen.getByText('123 Main St')).toBeInTheDocument();
  });

  it('disables Send button when textarea is empty', async () => {
    mockContextValue = { assessment: mockAssessment };
    const user = userEvent.setup();
    render(<ChatInterface />);

    await user.click(screen.getByLabelText('Open chat'));

    expect(screen.getByText('Send')).toBeDisabled();
  });

  it('enables Send button when user types a message', async () => {
    mockContextValue = { assessment: mockAssessment };
    const user = userEvent.setup();
    render(<ChatInterface />);

    await user.click(screen.getByLabelText('Open chat'));
    await user.type(screen.getByPlaceholderText('Ask about local regulations...'), 'Hello');

    expect(screen.getByText('Send')).not.toBeDisabled();
  });

  it('sends message and displays user message in chat', async () => {
    mockContextValue = { assessment: mockAssessment };

    // Return an async generator that yields nothing (resolve immediately)
    async function* emptyGenerator() {
      yield 'Response text';
    }
    mockChatFollowup.mockReturnValue(emptyGenerator());

    const user = userEvent.setup();
    render(<ChatInterface />);

    await user.click(screen.getByLabelText('Open chat'));
    await user.type(screen.getByPlaceholderText('Ask about local regulations...'), 'What is the height limit?');
    await user.click(screen.getByText('Send'));

    expect(screen.getByText('What is the height limit?')).toBeInTheDocument();
    expect(mockChatFollowup).toHaveBeenCalledWith('test-id', 'What is the height limit?');
  });

  it('sends message on Enter key press (not Shift+Enter)', async () => {
    mockContextValue = { assessment: mockAssessment };

    async function* emptyGenerator() {
      yield '';
    }
    mockChatFollowup.mockReturnValue(emptyGenerator());

    const user = userEvent.setup();
    render(<ChatInterface />);

    await user.click(screen.getByLabelText('Open chat'));
    const textarea = screen.getByPlaceholderText('Ask about local regulations...');
    await user.type(textarea, 'Test message');
    await user.keyboard('{Enter}');

    expect(screen.getByText('Test message')).toBeInTheDocument();
    expect(mockChatFollowup).toHaveBeenCalled();
  });

  it('displays error message when chat request fails', async () => {
    mockContextValue = { assessment: mockAssessment };

    async function* failingGenerator() {
      throw new Error('Network error');
      // This yield is unreachable but needed for TypeScript to infer the generator type
      yield '';
    }
    mockChatFollowup.mockReturnValue(failingGenerator());

    const user = userEvent.setup();
    render(<ChatInterface />);

    await user.click(screen.getByLabelText('Open chat'));
    await user.type(screen.getByPlaceholderText('Ask about local regulations...'), 'Hello');
    await user.click(screen.getByText('Send'));

    // Wait for the error message to appear
    expect(await screen.findByText('Failed to get response.')).toBeInTheDocument();
  });
});
