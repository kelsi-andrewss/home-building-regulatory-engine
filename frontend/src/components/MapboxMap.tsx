import { useRef, useEffect } from 'react';
import mapboxgl from 'mapbox-gl';
import type { AssessmentResponse } from '../api/client';

interface Props {
  assessment: AssessmentResponse | null;
  hoveredConstraint: string | null;
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

const SETBACK_CONSTRAINTS = new Set([
  'front_setback', 'side_setback', 'rear_setback',
  'Front Setback', 'Side Setback', 'Rear Setback',
]);

export default function MapboxMap({ assessment, hoveredConstraint }: Props) {
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

    const bbox = computeBBox(assessment.parcel.geometry.coordinates);
    map.fitBounds(
      [
        [bbox[0], bbox[1]],
        [bbox[2], bbox[3]],
      ],
      { padding: 80 }
    );
  }, [assessment]);

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
    <div
      ref={containerRef}
      style={{ width: '100%', height: '100%', minHeight: '100vh' }}
    />
  );
}
