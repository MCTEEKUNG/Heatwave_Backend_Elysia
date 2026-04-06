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
  days: number = 30,
  cycles: number = 1,
  startDate?: string
): Promise<ForecastResponse> {
  return api.post<ForecastResponse>('/api/forecast', { model, days, cycles, startDate });
}

export function getLatestForecast(): Promise<LatestForecastResponse> {
  // 45s timeout — Render free tier can take 30s+ to wake from sleep
  return api.get<LatestForecastResponse>('/api/forecast/latest', { timeoutMs: 45_000 });
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
