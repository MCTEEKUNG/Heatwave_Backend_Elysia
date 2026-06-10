import { api } from './apiService';

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
  /** Model that produced this row (e.g. 'lgbm-v1'); used to detect stale
   *  client-side alert thresholds (see ALERT_TUNED_FOR_VERSION). */
  model_version?: string;
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

// ─── MAP colour bands (mirror of DEFAULT_BANDS in src/risk.py) ───────────────
//
// CONSERVATIVE public-facing thresholds so the map stays calm — DECOUPLED from
// the (more sensitive) authority alert thresholds below. The backend writes
// `risk_level` with these bands; the map colours by it.
//   • extreme (red)     p >= 0.45
//   • high    (orange)  p >= 0.30
//   • moderate(yellow)  p >= 0.10
//   • low     (green)   otherwise
// Change policy in src/risk.py FIRST, then sync here.

export const RISK_BANDS = { moderate: 0.10, high: 0.30, extreme: 0.45 } as const;

/**
 * Probability → 4-tier risk level using the SAME bands as the backend
 * (src/risk.py). Prefer the server-provided `risk_level` when available —
 * this exists only for payloads that carry a bare probability.
 */
export function getHeatwaveRiskLevel(probability: number): 'low' | 'moderate' | 'high' | 'extreme' {
  if (probability >= RISK_BANDS.extreme) return 'extreme';
  if (probability >= RISK_BANDS.high) return 'high';
  if (probability >= RISK_BANDS.moderate) return 'moderate';
  return 'low';
}

// ─── Two-tier alert (watch / warning) ────────────────────────────────────────

export type AlertTier = 'warning' | 'watch' | 'none';

// Authority alert thresholds — the MEASURED F2-tuned operating points
// (mirror of ALERT_THRESHOLDS in src/risk.py). DECOUPLED from RISK_BANDS so
// alerts stay sensitive (fire from 0.217) while the map stays calm.
export const ALERT_THRESHOLDS = {
  warning: 0.281,
  watch: 0.217,
} as const;

/**
 * The thresholds above were measured for THIS model version's calibrated
 * probabilities. If the API reports a different `model_version`, the tiers may
 * be stale — `assertAlertThresholdsCurrent` surfaces that in dev.
 */
export const ALERT_TUNED_FOR_VERSION = 'lgbm-v1';

/** Warn (once per session) if served forecasts come from a model version the
 *  alert thresholds were not tuned for. Returns true when versions match. */
let warnedStaleThresholds = false;
export function assertAlertThresholdsCurrent(modelVersion: string | undefined): boolean {
  if (!modelVersion || modelVersion === ALERT_TUNED_FOR_VERSION) return true;
  if (!warnedStaleThresholds) {
    warnedStaleThresholds = true;
    console.warn(
      `[forecastService] ALERT_THRESHOLDS tuned for '${ALERT_TUNED_FOR_VERSION}' ` +
      `but API serves '${modelVersion}' — re-measure the operating points.`,
    );
  }
  return false;
}

/**
 * Server `risk_level` → two-tier alert. EXACT under the unified bands
 * (extreme==warning, high==watch). Prefer this over the probability overload —
 * it can never drift from what the backend wrote.
 */
export function alertTierFromRiskLevel(risk: RiskLevel | string | null | undefined): AlertTier {
  if (risk === 'extreme') return 'warning';
  if (risk === 'high') return 'watch';
  return 'none';
}

/** Classify a calibrated heatwave probability into a two-tier alert level.
 *  Fallback for payloads without `risk_level`; equals alertTierFromRiskLevel
 *  by construction (shared bands). */
export function getAlertTier(probability: number): AlertTier {
  if (probability >= ALERT_THRESHOLDS.warning) return 'warning';
  if (probability >= ALERT_THRESHOLDS.watch) return 'watch';
  return 'none';
}

/** Localized label for an alert tier (th / en). */
export function alertTierLabel(tier: AlertTier, lang: 'th' | 'en' = 'th'): string {
  const map = {
    warning: { th: 'เตือนภัย', en: 'Warning' },
    watch: { th: 'เฝ้าระวัง', en: 'Watch' },
    none: { th: 'ปกติ', en: 'Normal' },
  } as const;
  return map[tier][lang];
}

/** Display color for an alert tier (red / amber / green), dark-mode aware so it
 *  tracks the app theme rather than a single hardcoded palette. */
export function alertTierColor(tier: AlertTier, isDark: boolean = false): string {
  switch (tier) {
    case 'warning': return isDark ? '#ff6b5e' : '#dc2626';
    case 'watch':   return isDark ? '#ffc14d' : '#b45309';
    default:        return isDark ? '#5fa180' : '#3c6e57';
  }
}

export function getRiskColor(risk: string): string {
  switch (risk) {
    case 'extreme': return '#dc2626';
    case 'high': return '#ea580c';
    case 'moderate': return '#ca8a04';
    default: return '#16a34a';
  }
}

/** Calibrated probability (0–1) → integer percent, for public "risk N%" display. */
export function riskPercent(probability: number | null | undefined): number {
  return Math.round(((probability ?? 0) as number) * 100);
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
