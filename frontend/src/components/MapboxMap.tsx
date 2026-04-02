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
          'fill-color': '#3b82f6',
          'fill-opacity': 0.1,
        },
      });

      map.addLayer({
        id: 'design-envelope-fill',
        type: 'fill',
        source: 'design-envelope',
        paint: {
          'fill-color': '#f97316',
          'fill-opacity': 0.15,
        },
      });

      map.addLayer({
        id: 'parcel-stroke',
        type: 'line',
        source: 'parcel',
        paint: {
          'line-color': '#3b82f6',
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
          'line-dasharray': [4, 4],
        },
      });

      map.addLayer({
        id: 'design-envelope-stroke',
        type: 'line',
        source: 'design-envelope',
        paint: {
          'line-color': '#a855f7',
          'line-width': 2.5,
        },
      });

      map.addLayer({
        id: 'zoning-label',
        type: 'symbol',
        source: 'parcel',
        layout: {
          'text-field': ['get', 'zone_complete'],
          'text-size': 14,
          'text-anchor': 'center',
        },
        paint: {
          'text-color': '#1e3a5f',
          'text-halo-color': '#ffffff',
          'text-halo-width': 1,
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
      { padding: 80 }
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
      map.setPaintProperty('buildable-envelope', 'line-opacity', 1);
    } else {
      map.setPaintProperty('buildable-envelope', 'line-width', 2);
      map.setPaintProperty('buildable-envelope', 'line-opacity', 0.8);
    }
  }, [hoveredConstraint]);

  return (
    <div style={{ position: 'relative', width: '100%', height: '100%', minHeight: '100vh' }}>
      <div
        ref={containerRef}
        style={{ width: '100%', height: '100%' }}
      />
      {assessment && (
        <div
          style={{
            position: 'absolute',
            bottom: 24,
            left: 24,
            zIndex: 2,
            background: 'rgba(255,255,255,0.9)',
            backdropFilter: 'blur(4px)',
            borderRadius: 8,
            boxShadow: '0 2px 8px rgba(0,0,0,0.15)',
            padding: '12px 16px',
            fontSize: 13,
          }}
        >
          <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 6 }}>
            <span
              style={{
                display: 'inline-block',
                width: 16,
                height: 16,
                background: '#3b82f61a',
                border: '2px solid #3b82f6',
                borderRadius: 2,
                flexShrink: 0,
              }}
            />
            <span>Parcel Boundary</span>
          </div>
          <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 6 }}>
            <span
              style={{
                display: 'inline-block',
                width: 16,
                height: 0,
                borderTop: '2px dashed #10b981',
                flexShrink: 0,
              }}
            />
            <span>Setback Area</span>
          </div>
          <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
            <span
              style={{
                display: 'inline-block',
                width: 16,
                height: 16,
                background: '#f9731626',
                border: '2px solid #a855f7',
                borderRadius: 2,
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
