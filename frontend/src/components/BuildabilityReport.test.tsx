import { render, screen, within } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { describe, it, expect, vi, beforeEach } from 'vitest';
import BuildabilityReport from './BuildabilityReport';
import type { AssessmentResponse, Constraint, DesignConstraintResponse } from '../api/client';

vi.mock('./ParameterInputs', () => ({
  default: ({ maxBedrooms }: { maxBedrooms?: number | null }) => (
    <div data-testid="parameter-inputs" data-max-bedrooms={maxBedrooms ?? ''} />
  ),
}));

vi.mock('./DesignConstraintsPanel', () => ({
  default: ({ data }: { data: DesignConstraintResponse }) => (
    <div data-testid="design-constraints-panel">{data.parcel_apn}</div>
  ),
}));

function makeConstraint(overrides: Partial<Constraint> = {}): Constraint {
  return {
    name: 'max_height',
    value: '35 ft',
    confidence: 'verified',
    citation: 'LAMC 12.21',
    explanation: 'Height limit per zoning code.',
    design_standards: false,
    variance_available: false,
    conflict_notes: null,
    ...overrides,
  };
}

function makeAssessment(overrides: Partial<AssessmentResponse> = {}): AssessmentResponse {
  return {
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
    building_types: [
      {
        type: 'SFH',
        allowed: true,
        confidence: 'verified',
        constraints: [makeConstraint()],
        max_buildable_area_sf: 2500,
        max_units: 1,
        max_bedrooms: null,
      },
    ],
    setback_geometry: null,
    summary: 'Test summary',
    assessment_id: 'test-id',
    conflicts: [],
    ...overrides,
  };
}

describe('BuildabilityReport', () => {
  const mockOnHover = vi.fn();

  beforeEach(() => {
    vi.clearAllMocks();
  });

  it('shows placeholder when assessment is null', () => {
    render(
      <BuildabilityReport
        assessment={null}
        selectedType="SFH"
        onHoverConstraint={mockOnHover}
      />,
    );

    expect(screen.getByText('Search for an address to see buildability constraints.')).toBeInTheDocument();
  });

  it('shows no-data message when selected building type is not in assessment', () => {
    const assessment = makeAssessment();
    render(
      <BuildabilityReport
        assessment={assessment}
        selectedType="ADU"
        onHoverConstraint={mockOnHover}
      />,
    );

    expect(screen.getByText('No data available for this building type.')).toBeInTheDocument();
  });

  it('renders Allowed badge when building type is allowed', () => {
    const assessment = makeAssessment();
    render(
      <BuildabilityReport
        assessment={assessment}
        selectedType="SFH"
        onHoverConstraint={mockOnHover}
      />,
    );

    expect(screen.getByText('Allowed')).toBeInTheDocument();
    expect(screen.getByText('Single Family Home')).toBeInTheDocument();
  });

  it('renders Not Allowed badge when building type is not allowed', () => {
    const assessment = makeAssessment({
      building_types: [
        {
          type: 'SFH',
          allowed: false,
          confidence: 'verified',
          constraints: [makeConstraint()],
          max_buildable_area_sf: null,
          max_units: null,
          max_bedrooms: null,
        },
      ],
    });

    render(
      <BuildabilityReport
        assessment={assessment}
        selectedType="SFH"
        onHoverConstraint={mockOnHover}
      />,
    );

    expect(screen.getByText('Not Allowed')).toBeInTheDocument();
  });

  it('displays constraint rows with name, value, and confidence', () => {
    const assessment = makeAssessment({
      building_types: [
        {
          type: 'SFH',
          allowed: true,
          confidence: 'verified',
          constraints: [
            makeConstraint({ name: 'front_setback', value: '15 ft', confidence: 'interpreted' }),
          ],
          max_buildable_area_sf: 2500,
          max_units: 1,
          max_bedrooms: null,
        },
      ],
    });

    render(
      <BuildabilityReport
        assessment={assessment}
        selectedType="SFH"
        onHoverConstraint={mockOnHover}
      />,
    );

    expect(screen.getByText('Front Setback')).toBeInTheDocument();
    expect(screen.getByText('15 ft')).toBeInTheDocument();
    expect(screen.getByText('interpreted')).toBeInTheDocument();
  });

  it('shows Variance Possible badge when constraint has variance_available', () => {
    const assessment = makeAssessment({
      building_types: [
        {
          type: 'SFH',
          allowed: true,
          confidence: 'verified',
          constraints: [makeConstraint({ variance_available: true })],
          max_buildable_area_sf: 2500,
          max_units: 1,
          max_bedrooms: null,
        },
      ],
    });

    render(
      <BuildabilityReport
        assessment={assessment}
        selectedType="SFH"
        onHoverConstraint={mockOnHover}
      />,
    );

    expect(screen.getByText('Variance Possible')).toBeInTheDocument();
  });

  it('toggles citation/explanation when cite button is clicked', async () => {
    const user = userEvent.setup();
    const assessment = makeAssessment();

    render(
      <BuildabilityReport
        assessment={assessment}
        selectedType="SFH"
        onHoverConstraint={mockOnHover}
      />,
    );

    expect(screen.queryByText(/LAMC 12.21/)).not.toBeInTheDocument();

    await user.click(screen.getByTitle('Show citation'));

    expect(screen.getByText(/LAMC 12.21/)).toBeInTheDocument();
    expect(screen.getByText(/Height limit per zoning code/)).toBeInTheDocument();

    await user.click(screen.getByTitle('Show citation'));

    expect(screen.queryByText(/LAMC 12.21/)).not.toBeInTheDocument();
  });

  it('calls onHoverConstraint on row mouseEnter and mouseLeave', async () => {
    const user = userEvent.setup();
    const assessment = makeAssessment();

    render(
      <BuildabilityReport
        assessment={assessment}
        selectedType="SFH"
        onHoverConstraint={mockOnHover}
      />,
    );

    const row = screen.getByText('Max Height').closest('tr')!;
    await user.hover(row);
    expect(mockOnHover).toHaveBeenCalledWith('max_height');

    await user.unhover(row);
    expect(mockOnHover).toHaveBeenCalledWith(null);
  });

  it('renders conflict warning panel when conflicts exist', () => {
    const assessment = makeAssessment({
      conflicts: [
        {
          constraint_name: 'FAR',
          note: 'Proposed sqft exceeds max buildable area',
          citation: 'LAMC 12.21.1',
        },
      ],
    });

    render(
      <BuildabilityReport
        assessment={assessment}
        selectedType="SFH"
        onHoverConstraint={mockOnHover}
      />,
    );

    expect(screen.getByText('Constraint Conflicts')).toBeInTheDocument();
    expect(screen.getByText('FAR')).toBeInTheDocument();
    expect(screen.getByText('Proposed sqft exceeds max buildable area')).toBeInTheDocument();
  });

  it('does not render conflict panel when conflicts array is empty', () => {
    const assessment = makeAssessment({ conflicts: [] });

    render(
      <BuildabilityReport
        assessment={assessment}
        selectedType="SFH"
        onHoverConstraint={mockOnHover}
      />,
    );

    expect(screen.queryByText('Constraint Conflicts')).not.toBeInTheDocument();
  });

  it('renders DesignConstraintsPanel when designConstraints are provided', () => {
    const assessment = makeAssessment();
    const designConstraints: DesignConstraintResponse = {
      parcel_apn: '1234',
      envelope_geojson: null,
      per_edge_setbacks: [],
      height_envelope: { max_height_ft: 35, confidence: 'verified', citation: 'test' },
      material_requirements: [],
      panel_fit: { feasible: true, min_side_clearance_ft: 3, min_envelope_width_ft: 20, failures: [], mitigations: [] },
    };

    render(
      <BuildabilityReport
        assessment={assessment}
        selectedType="SFH"
        designConstraints={designConstraints}
        onHoverConstraint={mockOnHover}
      />,
    );

    expect(screen.getByTestId('design-constraints-panel')).toBeInTheDocument();
  });

  it('passes max_bedrooms to ParameterInputs', () => {
    const assessment = makeAssessment({
      building_types: [
        {
          type: 'SFH',
          allowed: true,
          confidence: 'verified',
          constraints: [makeConstraint()],
          max_buildable_area_sf: 2500,
          max_units: 1,
          max_bedrooms: 5,
        },
      ],
    });

    render(
      <BuildabilityReport
        assessment={assessment}
        selectedType="SFH"
        onHoverConstraint={mockOnHover}
      />,
    );

    expect(screen.getByTestId('parameter-inputs')).toHaveAttribute('data-max-bedrooms', '5');
  });

  it('does not render DesignConstraintsPanel when designConstraints is null', () => {
    const assessment = makeAssessment();

    render(
      <BuildabilityReport
        assessment={assessment}
        selectedType="SFH"
        designConstraints={null}
        onHoverConstraint={mockOnHover}
      />,
    );

    expect(screen.queryByTestId('design-constraints-panel')).not.toBeInTheDocument();
  });
});
