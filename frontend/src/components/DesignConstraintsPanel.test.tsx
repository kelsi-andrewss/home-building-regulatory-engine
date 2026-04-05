import { render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { describe, it, expect, vi, beforeEach } from 'vitest';
import DesignConstraintsPanel from './DesignConstraintsPanel';
import type { DesignConstraintResponse } from '../api/client';

function makeData(overrides: Partial<DesignConstraintResponse> = {}): DesignConstraintResponse {
  return {
    parcel_apn: '1234',
    envelope_geojson: null,
    per_edge_setbacks: [
      { edge: 'front', setback_ft: 15, confidence: 'verified', citation: 'LAMC 12.08 C.1' },
      { edge: 'left_side', setback_ft: 5, confidence: 'interpreted', citation: 'LAMC 12.08 C.2' },
      { edge: 'right_side', setback_ft: 5, confidence: 'interpreted', citation: 'LAMC 12.08 C.2' },
      { edge: 'rear', setback_ft: 15, confidence: 'verified', citation: 'LAMC 12.08 C.3' },
    ],
    height_envelope: {
      max_height_ft: 35,
      confidence: 'verified',
      citation: 'LAMC 12.21.1 height limit',
    },
    material_requirements: [],
    panel_fit: {
      feasible: true,
      min_side_clearance_ft: 3,
      min_envelope_width_ft: 20.5,
      failures: [],
      mitigations: [],
    },
    ...overrides,
  };
}

describe('DesignConstraintsPanel', () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it('renders section header with Design Constraints title', () => {
    render(<DesignConstraintsPanel data={makeData()} />);

    expect(screen.getByText('Design Constraints')).toBeInTheDocument();
  });

  it('renders per-edge setback rows with labels and values', () => {
    render(<DesignConstraintsPanel data={makeData()} />);

    expect(screen.getByText('Front')).toBeInTheDocument();
    expect(screen.getByText('Left Side')).toBeInTheDocument();
    expect(screen.getByText('Right Side')).toBeInTheDocument();
    expect(screen.getByText('Rear')).toBeInTheDocument();
    expect(screen.getAllByText('15 ft')).toHaveLength(2);
    expect(screen.getAllByText('5 ft')).toHaveLength(2);
  });

  it('renders max building height value', () => {
    render(<DesignConstraintsPanel data={makeData()} />);

    expect(screen.getByText('35 ft')).toBeInTheDocument();
    expect(screen.getByText('Max Building Height')).toBeInTheDocument();
  });

  it('renders panel fit feasible status', () => {
    render(<DesignConstraintsPanel data={makeData()} />);

    expect(screen.getByText('PANEL FIT: FEASIBLE')).toBeInTheDocument();
    expect(screen.getByText(/Min side clearance:/)).toBeInTheDocument();
    expect(screen.getByText(/Min envelope width:/)).toBeInTheDocument();
  });

  it('renders panel fit not feasible with failures and mitigations', () => {
    const data = makeData({
      panel_fit: {
        feasible: false,
        min_side_clearance_ft: 0,
        min_envelope_width_ft: 0,
        failures: ['Lot too narrow for panel delivery'],
        mitigations: ['Consider crane delivery from front'],
      },
    });

    render(<DesignConstraintsPanel data={data} />);

    expect(screen.getByText('PANEL FIT: NOT FEASIBLE')).toBeInTheDocument();
    expect(screen.getByText('Lot too narrow for panel delivery')).toBeInTheDocument();
    expect(screen.getByText('Recommended Mitigations:')).toBeInTheDocument();
    expect(screen.getByText('Consider crane delivery from front')).toBeInTheDocument();
  });

  it('collapses and expands the panel when header is clicked', async () => {
    const user = userEvent.setup();
    render(<DesignConstraintsPanel data={makeData()} />);

    // Initially expanded
    expect(screen.getByText('Front')).toBeInTheDocument();

    // Click to collapse
    await user.click(screen.getByText('Design Constraints'));
    expect(screen.queryByText('Front')).not.toBeInTheDocument();

    // Click to expand again
    await user.click(screen.getByText('Design Constraints'));
    expect(screen.getByText('Front')).toBeInTheDocument();
  });

  it('toggles setback citation when cite button is clicked', async () => {
    const user = userEvent.setup();
    render(<DesignConstraintsPanel data={makeData()} />);

    // Citation not visible initially
    expect(screen.queryByText(/LAMC 12.08 C.1/)).not.toBeInTheDocument();

    // Click the first cite button
    const citeButtons = screen.getAllByTitle('Show citation');
    await user.click(citeButtons[0]);

    expect(screen.getByText(/LAMC 12.08 C.1/)).toBeInTheDocument();

    // Click again to collapse
    await user.click(citeButtons[0]);
    expect(screen.queryByText(/LAMC 12.08 C.1/)).not.toBeInTheDocument();
  });

  it('toggles height citation when cite button is clicked', async () => {
    const user = userEvent.setup();
    render(<DesignConstraintsPanel data={makeData()} />);

    expect(screen.queryByText(/LAMC 12.21.1 height limit/)).not.toBeInTheDocument();

    // The height cite button is the last one (after 4 setback cite buttons)
    const citeButtons = screen.getAllByText('cite');
    const heightCite = citeButtons[citeButtons.length - 1];
    await user.click(heightCite);

    expect(screen.getByText(/LAMC 12.21.1 height limit/)).toBeInTheDocument();

    await user.click(heightCite);
    expect(screen.queryByText(/LAMC 12.21.1 height limit/)).not.toBeInTheDocument();
  });

  it('displays confidence badges for setbacks', () => {
    render(<DesignConstraintsPanel data={makeData()} />);

    expect(screen.getAllByText('verified').length).toBeGreaterThanOrEqual(2);
    expect(screen.getAllByText('interpreted').length).toBeGreaterThanOrEqual(2);
  });
});
