import { render, screen } from '@testing-library/react';
import { describe, it, expect, vi, beforeEach } from 'vitest';
import MapboxMap from './MapboxMap';
import type { AssessmentResponse, DesignConstraintResponse } from '../api/client';

const mockSetData = vi.fn();
const mockFitBounds = vi.fn();
const mockSetPaintProperty = vi.fn();
const mockGetSource = vi.fn(() => ({ setData: mockSetData }));
const mockAddSource = vi.fn();
const mockAddLayer = vi.fn();
const mockRemove = vi.fn();
const mockOn = vi.fn();

vi.mock('mapbox-gl', () => {
  const MapClass = vi.fn().mockImplementation(() => ({
    on: mockOn,
    remove: mockRemove,
    getSource: mockGetSource,
    addSource: mockAddSource,
    addLayer: mockAddLayer,
    fitBounds: mockFitBounds,
    setPaintProperty: mockSetPaintProperty,
  }));

  return {
    default: {
      Map: MapClass,
      accessToken: '',
    },
  };
});

function makeAssessment(): AssessmentResponse {
  return {
    parcel: {
      apn: '1234',
      address: '123 Main St, Los Angeles, CA',
      geometry: { type: 'Polygon', coordinates: [[[-118.3, 34.0], [-118.29, 34.0], [-118.29, 34.01], [-118.3, 34.01], [-118.3, 34.0]]] },
      lot_area_sf: 5000,
      lot_width_ft: 50,
      year_built: 1950,
      existing_units: 2,
      existing_sqft: 1800,
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
}

describe('MapboxMap', () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it('renders the map container div', () => {
    render(<MapboxMap assessment={null} hoveredConstraint={null} />);

    // The outermost div has minHeight 100vh
    const container = document.querySelector('div[style*="min-height"]');
    expect(container).toBeTruthy();
  });

  it('creates a mapbox Map instance on mount', async () => {
    const mapboxgl = await import('mapbox-gl');
    const MapConstructor = vi.mocked(mapboxgl.default.Map);
    render(<MapboxMap assessment={null} hoveredConstraint={null} />);

    expect(MapConstructor).toHaveBeenCalledTimes(1);
  });

  it('calls map.remove on unmount', () => {
    const { unmount } = render(<MapboxMap assessment={null} hoveredConstraint={null} />);
    unmount();

    expect(mockRemove).toHaveBeenCalledOnce();
  });

  it('does not render existing structure info (moved to sidebar)', () => {
    const assessment = makeAssessment();

    render(<MapboxMap assessment={assessment} hoveredConstraint={null} />);

    expect(screen.queryByText('Existing Structure')).not.toBeInTheDocument();
  });

  it('shows map legend when assessment is present', () => {
    const assessment = makeAssessment();

    render(<MapboxMap assessment={assessment} hoveredConstraint={null} />);

    expect(screen.getByText('Parcel Boundary')).toBeInTheDocument();
    expect(screen.getByText('Setback Area')).toBeInTheDocument();
    expect(screen.getByText('Design Envelope')).toBeInTheDocument();
  });

  it('does not show map legend when assessment is null', () => {
    render(<MapboxMap assessment={null} hoveredConstraint={null} />);

    expect(screen.queryByText('Parcel Boundary')).not.toBeInTheDocument();
  });

  it('updates setback line style when a setback constraint is hovered', () => {
    // Simulate map load so mapReady is set
    mockOn.mockImplementation((event: string, cb: () => void) => {
      if (event === 'load') cb();
    });

    const assessment = makeAssessment();
    const { rerender } = render(
      <MapboxMap assessment={assessment} hoveredConstraint={null} />,
    );

    rerender(
      <MapboxMap assessment={assessment} hoveredConstraint="front_setback" />,
    );

    expect(mockSetPaintProperty).toHaveBeenCalledWith('buildable-envelope', 'line-width', 4);
    expect(mockSetPaintProperty).toHaveBeenCalledWith('buildable-envelope', 'line-color', '#059669');
  });

  it('resets setback line style when hover leaves a setback constraint', () => {
    mockOn.mockImplementation((event: string, cb: () => void) => {
      if (event === 'load') cb();
    });

    const assessment = makeAssessment();
    const { rerender } = render(
      <MapboxMap assessment={assessment} hoveredConstraint="front_setback" />,
    );

    rerender(
      <MapboxMap assessment={assessment} hoveredConstraint={null} />,
    );

    expect(mockSetPaintProperty).toHaveBeenCalledWith('buildable-envelope', 'line-width', 2);
    expect(mockSetPaintProperty).toHaveBeenCalledWith('buildable-envelope', 'line-color', '#10b981');
  });

  it('does not highlight setback line for non-setback constraints', () => {
    mockOn.mockImplementation((event: string, cb: () => void) => {
      if (event === 'load') cb();
    });

    const assessment = makeAssessment();
    const { rerender } = render(
      <MapboxMap assessment={assessment} hoveredConstraint={null} />,
    );

    mockSetPaintProperty.mockClear();

    rerender(
      <MapboxMap assessment={assessment} hoveredConstraint="max_height" />,
    );

    // Should reset to default, not highlight
    expect(mockSetPaintProperty).toHaveBeenCalledWith('buildable-envelope', 'line-width', 2);
    expect(mockSetPaintProperty).toHaveBeenCalledWith('buildable-envelope', 'line-color', '#10b981');
  });
});
