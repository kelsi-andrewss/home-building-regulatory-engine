import { useRef, useEffect } from 'react';
import mapboxgl from 'mapbox-gl';
import type { AssessmentResponse, DesignConstraintResponse } from '../api/client';

interface Props {
  assessment: AssessmentResponse | null;
  hoveredConstraint: string | null;
  designConstraints?: DesignConstraintResponse | null;
}

function computeBBox(coords: number[][][]): [number, number, number, number] {
  let minLng = Infinity, minLat = Infinity, maxLng = -Infinity, maxLat = -Infinity;
  for (const ring of coords) {
    for (const [lng, lat] of ring) {
      if (lng < minLng) minLng = lng;
      if (lat < minLat) minLat = lat;
      if (lng > maxLng) maxLng = lng;
      if (lat > maxLat) maxLat = lat;
    }
  }
  return [minLng, minLat, maxLng, maxLat];
}

function unionBBox(
  a: [number, number, number, number],
  b: [number, number, number, number],
): [number, number, number, number] {
  return [
    Math.min(a[0], b[0]),
    Math.min(a[1], b[1]),
    Math.max(a[2], b[2]),
    Math.max(a[3], b[3]),
  ];
}

const SETBACK_CONSTRAINTS = new Set([
  'front_setback', 'side_setback', 'rear_setback',
  'Front Setback', 'Side Setback', 'Rear Setback',
]);

export default function MapboxMap({ assessment, hoveredConstraint, designConstraints }: Props) {
  const containerRef = useRef<HTMLDivElement>(null);
  const mapRef = useRef<mapboxgl.Map | null>(null);
  const mapReady = useRef(false);

  useEffect(() => {
    if (!containerRef.current) return;

    mapboxgl.accessToken = import.meta.env.VITE_MAPBOX_TOKEN || '';

    const map = new mapboxgl.Map({
      container: containerRef.current,
      style: 'mapbox://styles/mapbox/light-v11',
      center: [-118.25, 34.05],
      zoom: 11,
    });

    map.on('load', () => {
      map.addSource('parcel', {
        type: 'geojson',
        data: { type: 'FeatureCollection', features: [] },
      });

      map.addSource('setback', {
        type: 'geojson',
        data: { type: 'FeatureCollection', features: [] },
      });

      map.addSource('design-envelope', {
        type: 'geojson',
        data: { type: 'FeatureCollection', features: [] },
      });

      map.addLayer({
        id: 'parcel-fill',
        type: 'fill',
        source: 'parcel',
        paint: {
          'fill-color': '#4f46e5',
          'fill-opacity': 0.05,
        },
      });

      map.addLayer({
        id: 'design-envelope-fill',
        type: 'fill',
        source: 'design-envelope',
        paint: {
          'fill-color': '#4f46e5',
          'fill-opacity': 0.1,
        },
      });

      map.addLayer({
        id: 'parcel-stroke',
        type: 'line',
        source: 'parcel',
        paint: {
          'line-color': '#4f46e5',
          'line-width': 2,
        },
      });

      map.addLayer({
        id: 'buildable-envelope',
        type: 'line',
        source: 'setback',
        paint: {
          'line-color': '#10b981',
          'line-width': 2,
          'line-dasharray': [3, 2],
        },
      });

      map.addLayer({
        id: 'design-envelope-stroke',
        type: 'line',
        source: 'design-envelope',
        paint: {
          'line-color': '#4f46e5',
          'line-width': 2,
        },
      });

      map.addLayer({
        id: 'zoning-label',
        type: 'symbol',
        source: 'parcel',
        layout: {
          'text-field': ['get', 'zone_complete'],
          'text-size': 13,
          'text-font': ['DIN Offc Pro Medium', 'Arial Unicode MS Regular'],
          'text-anchor': 'center',
          'text-letter-spacing': 0.05,
        },
        paint: {
          'text-color': '#4f46e5',
          'text-halo-color': '#ffffff',
          'text-halo-width': 2,
        },
      });

      mapReady.current = true;
    });

    mapRef.current = map;

    return () => {
      mapReady.current = false;
      map.remove();
    };
  }, []);

  useEffect(() => {
    const map = mapRef.current;
    if (!map || !mapReady.current) return;

    if (!assessment) {
      const empty: GeoJSON.FeatureCollection = { type: 'FeatureCollection', features: [] };
      (map.getSource('parcel') as mapboxgl.GeoJSONSource)?.setData(empty);
      (map.getSource('setback') as mapboxgl.GeoJSONSource)?.setData(empty);
      (map.getSource('design-envelope') as mapboxgl.GeoJSONSource)?.setData(empty);
      return;
    }

    const parcelFeature: GeoJSON.Feature = {
      type: 'Feature',
      geometry: assessment.parcel.geometry,
      properties: {
        zone_complete: assessment.zoning.zone_complete,
        apn: assessment.parcel.apn,
      },
    };

    (map.getSource('parcel') as mapboxgl.GeoJSONSource)?.setData({
      type: 'FeatureCollection',
      features: [parcelFeature],
    });

    if (assessment.setback_geometry) {
      const setbackFeature: GeoJSON.Feature = {
        type: 'Feature',
        geometry: assessment.setback_geometry,
        properties: {},
      };
      (map.getSource('setback') as mapboxgl.GeoJSONSource)?.setData({
        type: 'FeatureCollection',
        features: [setbackFeature],
      });
    } else {
      (map.getSource('setback') as mapboxgl.GeoJSONSource)?.setData({
        type: 'FeatureCollection',
        features: [],
      });
    }

    let bbox = computeBBox(assessment.parcel.geometry.coordinates);
    if (designConstraints?.envelope_geojson) {
      const envBBox = computeBBox(designConstraints.envelope_geojson.coordinates);
      bbox = unionBBox(bbox, envBBox);
    }
    map.fitBounds(
      [
        [bbox[0], bbox[1]],
        [bbox[2], bbox[3]],
      ],
      { padding: { top: 60, bottom: 60, left: 480, right: 60 }, duration: 2000 }
    );
  }, [assessment, designConstraints]);

  useEffect(() => {
    const map = mapRef.current;
    if (!map || !mapReady.current) return;

    const envelopeSource = map.getSource('design-envelope') as mapboxgl.GeoJSONSource;
    if (!envelopeSource) return;

    if (designConstraints?.envelope_geojson) {
      const feature: GeoJSON.Feature = {
        type: 'Feature',
        geometry: designConstraints.envelope_geojson,
        properties: {},
      };
      envelopeSource.setData({ type: 'FeatureCollection', features: [feature] });
    } else {
      envelopeSource.setData({ type: 'FeatureCollection', features: [] });
    }
  }, [designConstraints]);

  useEffect(() => {
    const map = mapRef.current;
    if (!map || !mapReady.current) return;

    if (hoveredConstraint && SETBACK_CONSTRAINTS.has(hoveredConstraint)) {
      map.setPaintProperty('buildable-envelope', 'line-width', 4);
      map.setPaintProperty('buildable-envelope', 'line-color', '#059669');
    } else {
      map.setPaintProperty('buildable-envelope', 'line-width', 2);
      map.setPaintProperty('buildable-envelope', 'line-color', '#10b981');
    }
  }, [hoveredConstraint]);

  return (
    <div style={{ position: 'relative', width: '100%', height: '100%', minHeight: '100vh' }}>
      <div
        ref={containerRef}
        style={{ width: '100%', height: '100%' }}
      />
      {assessment && (assessment.parcel.existing_units != null || assessment.parcel.existing_sqft != null) && (
        <div
          style={{
            position: 'absolute',
            top: 80,
            left: 16,
            zIndex: 2,
            background: 'rgba(255,255,255,0.8)',
            backdropFilter: 'blur(12px)',
            borderRadius: 16,
            border: '1px solid rgba(0,0,0,0.05)',
            boxShadow: '0 10px 25px -5px rgba(0,0,0,0.1)',
            padding: '16px 20px',
            fontSize: 12,
            fontWeight: 600,
            color: '#334155',
            animation: 'slideUp 0.3s ease-out',
          }}
        >
          <div style={{ marginBottom: 8, fontSize: 13, fontWeight: 700 }}>Existing Structure</div>
          {assessment.parcel.existing_units != null && (
            <div style={{ marginBottom: 4 }}>
              Units: {assessment.parcel.existing_units.toLocaleString()}
            </div>
          )}
          {assessment.parcel.existing_sqft != null && (
            <div>
              Sq Ft: {assessment.parcel.existing_sqft.toLocaleString()}
            </div>
          )}
        </div>
      )}
      {assessment && (
        <div
          style={{
            position: 'absolute',
            bottom: 32,
            right: 32,
            zIndex: 2,
            background: 'rgba(255,255,255,0.8)',
            backdropFilter: 'blur(12px)',
            borderRadius: 16,
            border: '1px solid rgba(0,0,0,0.05)',
            boxShadow: '0 10px 25px -5px rgba(0,0,0,0.1)',
            padding: '16px 20px',
            fontSize: 12,
            fontWeight: 600,
            color: '#334155',
            animation: 'slideUp 0.3s ease-out',
          }}
        >
          <div style={{ display: 'flex', alignItems: 'center', gap: 10, marginBottom: 10 }}>
            <span
              style={{
                display: 'inline-block',
                width: 14,
                height: 14,
                background: 'rgba(79, 70, 229, 0.1)',
                border: '2px solid #4f46e5',
                borderRadius: 4,
                flexShrink: 0,
              }}
            />
            <span>Parcel Boundary</span>
          </div>
          <div style={{ display: 'flex', alignItems: 'center', gap: 10, marginBottom: 10 }}>
            <span
              style={{
                display: 'inline-block',
                width: 14,
                height: 0,
                borderTop: '2px dashed #10b981',
                flexShrink: 0,
              }}
            />
            <span>Setback Area</span>
          </div>
          <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
            <span
              style={{
                display: 'inline-block',
                width: 14,
                height: 14,
                background: 'rgba(79, 70, 229, 0.2)',
                border: '2px solid #4f46e5',
                borderRadius: 4,
                flexShrink: 0,
              }}
            />
            <span>Design Envelope</span>
          </div>
        </div>
      )}
    </div>
  );
}
