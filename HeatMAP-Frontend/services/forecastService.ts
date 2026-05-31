import { api } from './apiService';

export interface ForecastDay {
  date: string;
  predicted_heatwave: number;
  heatwave_probability: number;
  forecast_cycle: number;
  temperature_c: number;
  humidity_pct: number;
  heat_index_c: number;
  data_source: string;
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

/**
 * Default province (Bangkok, id 1) for the legacy whole-app forecast/alerts
 * screens, which predate the per-province selector. These adapters keep those
 * screens working while the np.random spawn-Python backend endpoints
 * (POST /api/forecast, /api/forecast/latest) are retired — data now comes from
 * the real per-province forecast in the DB (GET /api/forecast/province/:id).
 */
const DEFAULT_PROVINCE_ID = 1;

function toLegacyForecastDays(rows: ProvinceForecastDay[]): ForecastDay[] {
  return rows.map((r) => {
    const isHeatwave =
      typeof r.predicted_label === 'boolean'
        ? r.predicted_label
        : Number(r.predicted_label) > 0;
    const swbgt = Number(r.swbgt_pred);
    return {
      date: r.target_date,
      predicted_heatwave: isHeatwave ? 1 : 0,
      heatwave_probability: Number(r.probability),
      forecast_cycle: 1,
      temperature_c: swbgt, // sWBGT (°C) reused for the legacy temperature field
      humidity_pct: 0,
      heat_index_c: swbgt,
      data_source: 'model',
      forecast_generated: r.generated_at,
    };
  });
}

export async function getLatestForecast(): Promise<LatestForecastResponse> {
  const rows = await getProvinceForecast(DEFAULT_PROVINCE_ID, 7);
  const forecast = toLegacyForecastDays(rows);
  return { forecast, totalDays: forecast.length };
}

/**
 * Forecast generation is now a scheduled server-side job over real Open-Meteo
 * data; the client just reads the latest stored forecast. Kept for API
 * compatibility with the legacy ForecastScreen "generate" button.
 */
export async function runForecast(
  _model: string,
  _days: number = 7,
): Promise<ForecastResponse> {
  const latest = await getLatestForecast();
  return { success: true, forecast: latest.forecast, totalDays: latest.totalDays };
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
