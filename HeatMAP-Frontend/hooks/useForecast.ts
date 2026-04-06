/**
 * useForecast Hook
 *
 * Fetches the latest 30-day AI heatwave forecast from the backend and
 * exposes it along with derived helpers: risk calendar, summary stats,
 * and the individual days.
 *
 * The hook auto-fetches on mount and exposes a `refresh` function for
 * manual re-fetches (e.g. pull-to-refresh).
 */

import { useState, useEffect, useCallback, useRef } from 'react';
import {
  getLatestForecast,
  type ForecastDay,
} from '../services/forecastService';

// ─── Types ────────────────────────────────────────────────────────────────────

/** 3-tier risk:
 *  safe    — predicted_heatwave = 0
 *  caution — predicted_heatwave = 1, probability < 0.70
 *  danger  — predicted_heatwave = 1, probability ≥ 0.70
 */
export type RiskLevel = 'safe' | 'caution' | 'danger';

export interface CalendarDay {
  date: Date;
  dayOfMonth: number;
  riskLevel: RiskLevel;
  probability: number;
  temperature_c: number;
  isHeatwave: boolean;
  isToday: boolean;
}

export interface ForecastSummary {
  totalDays:        number;
  heatwaveDays:     number;
  avgProbability:   number;
  maxTemperature:   number;
  avgTemperature:   number;
  avgHumidity:      number;
  /** Today's forecast entry (or null if not found) */
  today:            ForecastDay | null;
}

export interface UseForecastReturn {
  days:       ForecastDay[];
  calendar:   CalendarDay[];
  summary:    ForecastSummary;
  loading:    boolean;
  error:      string | null;
  lastFetched: Date | null;
  refresh:    () => Promise<void>;
}

// ─── Defaults ─────────────────────────────────────────────────────────────────

const EMPTY_SUMMARY: ForecastSummary = {
  totalDays:      0,
  heatwaveDays:   0,
  avgProbability: 0,
  maxTemperature: 0,
  avgTemperature: 0,
  avgHumidity:    0,
  today:          null,
};

// ─── Helpers ──────────────────────────────────────────────────────────────────

function buildCalendar(days: ForecastDay[]): CalendarDay[] {
  if (days.length === 0) return [];

  const todayStr = new Date().toISOString().split('T')[0];

  return days.map((d): CalendarDay => {
    const date = new Date(d.date);
    return {
      date,
      dayOfMonth:  date.getDate(),
      riskLevel:   d.predicted_heatwave !== 1
        ? 'safe'
        : d.heatwave_probability >= 0.70 ? 'danger' : 'caution',
      probability: d.heatwave_probability,
      temperature_c: d.temperature_c,
      isHeatwave:  d.predicted_heatwave === 1,
      isToday:     d.date === todayStr,
    };
  });
}

function buildSummary(days: ForecastDay[]): ForecastSummary {
  if (days.length === 0) return EMPTY_SUMMARY;

  const todayStr = new Date().toISOString().split('T')[0];
  const today    = days.find((d) => d.date === todayStr) ?? null;

  const heatwaveDays   = days.filter((d) => d.predicted_heatwave === 1).length;
  const avgProbability = days.reduce((s, d) => s + d.heatwave_probability, 0) / days.length;
  const maxTemperature = Math.max(...days.map((d) => d.temperature_c));
  const avgTemperature = days.reduce((s, d) => s + d.temperature_c, 0) / days.length;
  const avgHumidity    = days.reduce((s, d) => s + d.humidity_est,   0) / days.length;

  return {
    totalDays:    days.length,
    heatwaveDays,
    avgProbability,
    maxTemperature,
    avgTemperature,
    avgHumidity,
    today,
  };
}

// ─── Hook ────────────────────────────────────────────────────────────────────

export function useForecast(cycle = 1): UseForecastReturn {
  const [days,       setDays]       = useState<ForecastDay[]>([]);
  const [loading,    setLoading]    = useState(true);
  const [error,      setError]      = useState<string | null>(null);
  const [lastFetched, setLastFetched] = useState<Date | null>(null);

  // Prevent duplicate concurrent fetches
  const fetchingRef = useRef(false);

  const fetchForecast = useCallback(async () => {
    if (fetchingRef.current) return;
    fetchingRef.current = true;

    setLoading(true);
    setError(null);

    try {
      const data = await getLatestForecast();

      if (data.error) {
        setError(data.error);
        return;
      }

      if (!data.forecast || data.forecast.length === 0) {
        setError('No forecast data available. Please generate a forecast first.');
        return;
      }

      // Filter by the requested cycle
      const filtered = data.forecast.filter((d) => d.forecast_cycle === cycle);
      setDays(filtered.length > 0 ? filtered : data.forecast);
      setLastFetched(new Date());
    } catch (err: any) {
      setError(
        err.name === 'NetworkError'
          ? 'Cannot reach backend. Check your internet connection and API URL.'
          : `Failed to load forecast: ${err.message}`,
      );
    } finally {
      setLoading(false);
      fetchingRef.current = false;
    }
  }, [cycle]);

  useEffect(() => {
    fetchForecast();
  }, [fetchForecast]);

  const calendar = buildCalendar(days);
  const summary  = buildSummary(days);

  return {
    days,
    calendar,
    summary,
    loading,
    error,
    lastFetched,
    refresh: fetchForecast,
  };
}
