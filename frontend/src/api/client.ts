export type Confidence = 'verified' | 'interpreted' | 'unknown';
export type BuildingType = 'SFH' | 'ADU' | 'GH' | 'DUP';

export interface Constraint {
  name: string;
  value: string;
  confidence: Confidence;
  citation: string;
  explanation: string;
}

export interface BuildingTypeAssessment {
  type: BuildingType;
  allowed: boolean;
  confidence: Confidence;
  constraints: Constraint[];
  max_buildable_area_sf: number | null;
  max_units: number | null;
}

export interface ZoningData {
  zone_complete: string;
  zone_class: string;
  height_district: string;
  general_plan_land_use: string;
  specific_plan: string | null;
  historic_overlay: string | null;
}

export interface ParcelData {
  apn: string;
  address: string;
  geometry: GeoJSON.Polygon;
  lot_area_sf: number;
  lot_width_ft: number | null;
  year_built: number | null;
  existing_units: number | null;
  existing_sqft: number | null;
}

export interface AssessmentResponse {
  parcel: ParcelData;
  zoning: ZoningData;
  building_types: BuildingTypeAssessment[];
  setback_geometry: GeoJSON.Polygon | null;
  summary: string;
  assessment_id: string;
}

export interface GeocodingResult {
  address: string;
  apn: string;
  coordinates: [number, number];
}

const BASE_URL = import.meta.env.VITE_API_BASE_URL || '/api';

async function request<T>(url: string, options?: RequestInit): Promise<T> {
  const res = await fetch(url, options);
  if (!res.ok) {
    const body = await res.text();
    throw new Error(body || `Request failed: ${res.status}`);
  }
  return res.json();
}

export function assessParcel(input: {
  address?: string;
  apn?: string;
  bedrooms?: number | null;
  bathrooms?: number | null;
  sqft?: number | null;
}): Promise<AssessmentResponse> {
  return request<AssessmentResponse>(`${BASE_URL}/assess`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(input),
  });
}

export function getParcel(apn: string): Promise<ParcelData & { zoning: ZoningData }> {
  return request<ParcelData & { zoning: ZoningData }>(`${BASE_URL}/parcel/${apn}`);
}

export function geocodeAddress(query: string): Promise<GeocodingResult[]> {
  return request<GeocodingResult[]>(`${BASE_URL}/geocode?q=${encodeURIComponent(query)}`);
}

export async function* chatFollowup(
  assessmentId: string,
  message: string,
): AsyncGenerator<string, void, unknown> {
  const res = await fetch(`${BASE_URL}/chat`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ assessment_id: assessmentId, message }),
  });
  if (!res.ok) {
    throw new Error(`Chat request failed: ${res.status}`);
  }
  const reader = res.body?.getReader();
  if (!reader) return;
  const decoder = new TextDecoder();
  while (true) {
    const { done, value } = await reader.read();
    if (done) break;
    yield decoder.decode(value, { stream: true });
  }
}

export async function sendFeedback(
  assessmentId: string,
  constraintName: string,
  vote: 'up' | 'down' | null,
  reason?: string,
): Promise<void> {
  fetch(`${BASE_URL}/feedback`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
      assessment_id: assessmentId,
      constraint_name: constraintName,
      vote,
      ...(reason ? { reason } : {}),
    }),
  }).catch(() => {});
}
