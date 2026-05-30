import { api } from './apiService';

export interface ForecastDay {
  date: string;
  predicted_heatwave: number;
  heatwave_probability: number;
  forecast_cycle: number;
  temperature_c: number;
  humidity_est: number;
  forecast_generated: string;
}

export interface ForecastResponse {
  success: boolean;
  filename?: string;
  forecast?: ForecastDay[];
  totalDays?: number;
  error?: string;
  log?: string;
}

export interface LatestForecastResponse {
  filename?: string;
  forecast?: ForecastDay[];
  totalDays?: number;
  error?: string;
}

export function runForecast(
  model: string,
  days: number = 7,   // max 16 (Open-Meteo real-data limit)
): Promise<ForecastResponse> {
  return api.post<ForecastResponse>('/api/forecast', { model, days });
}

export function getLatestForecast(): Promise<LatestForecastResponse> {
  // 45s timeout — Render free tier can take 30s+ to wake from sleep
  return api.get<LatestForecastResponse>('/api/forecast/latest', { timeoutMs: 45_000 });
}

// ─── Per-province forecast (spec §7 / Phase 5) ────────────────────────────────

/** 4-tier risk level emitted by the backend (calibrated probability → bucket). */
export type RiskLevel = 'low' | 'moderate' | 'high' | 'extreme';

/**
 * One day of per-province forecast.
 * Shape per spec §7:
 *   GET /api/forecast/province/:id?days=7
 *   -> [{ target_date, probability, predicted_label, risk_level, swbgt_pred, generated_at }]
 */
export interface ProvinceForecastDay {
  target_date: string;
  probability: number;
  predicted_label: boolean | number;
  risk_level: RiskLevel;
  swbgt_pred: number;
  generated_at: string;
}

/**
 * Latest forecast value for one province on the map.
 * Shape per spec §7:
 *   GET /api/forecast/map
 *   -> [{ province_id, lat, lon, probability, risk_level, target_date, generated_at }]
 */
export interface MapForecastPoint {
  province_id: number;
  lat: number;
  lon: number;
  probability: number;
  risk_level: RiskLevel;
  target_date: string;
  generated_at: string;
}

/** Fetch the 7-day (default) forecast for a single province. */
export function getProvinceForecast(
  provinceId: number,
  days: number = 7,
): Promise<ProvinceForecastDay[]> {
  // 45s timeout — Render free tier can take 30s+ to wake from sleep
  return api.get<ProvinceForecastDay[]>(
    `/api/forecast/province/${provinceId}?days=${days}`,
    { timeoutMs: 45_000 },
  );
}

/** Fetch the latest forecast value for every province (for the map). */
export function getForecastMap(): Promise<MapForecastPoint[]> {
  return api.get<MapForecastPoint[]>('/api/forecast/map', { timeoutMs: 45_000 });
}

/**
 * Map a backend `risk_level` to the map grid `Severity`. The two vocabularies
 * are identical (low|moderate|high|extreme) so this is an identity with a
 * defensive fallback for unexpected/missing values.
 */
export function riskLevelToSeverity(
  risk: string | null | undefined,
): 'extreme' | 'high' | 'moderate' | 'low' {
  switch (risk) {
    case 'extreme': return 'extreme';
    case 'high':    return 'high';
    case 'moderate':return 'moderate';
    default:        return 'low';
  }
}

/**
 * Format an ISO `generated_at` timestamp into a localized "as of" string.
 * Returns an empty string for missing/invalid input.
 */
export function formatGeneratedAt(iso: string | null | undefined): string {
  if (!iso) return '';
  const d = new Date(iso);
  if (isNaN(d.getTime())) return '';
  return d.toLocaleString('en-US', {
    month: 'short',
    day: 'numeric',
    hour: '2-digit',
    minute: '2-digit',
  });
}

export function getHeatwaveRiskLevel(probability: number): 'low' | 'moderate' | 'high' | 'extreme' {
  if (probability >= 0.8) return 'extreme';
  if (probability >= 0.6) return 'high';
  if (probability >= 0.4) return 'moderate';
  return 'low';
}

export function getRiskColor(risk: string): string {
  switch (risk) {
    case 'extreme': return '#dc2626';
    case 'high': return '#ea580c';
    case 'moderate': return '#ca8a04';
    default: return '#16a34a';
  }
}

export function formatForecastDate(dateStr: string): string {
  // Parse as UTC to avoid the date shifting by one day in negative-offset timezones.
  // Dates from the server are plain YYYY-MM-DD strings (no time component), so we
  // append T00:00:00Z to force UTC interpretation before formatting.
  const normalized = /^\d{4}-\d{2}-\d{2}$/.test(dateStr) ? `${dateStr}T00:00:00Z` : dateStr;
  const date = new Date(normalized);
  return date.toLocaleDateString('en-US', {
    month: 'short',
    day: 'numeric',
    year: 'numeric',
    timeZone: 'UTC',
  });
}
