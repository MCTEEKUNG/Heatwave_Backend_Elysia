/**
 * useProvinceForecast Hook
 *
 * Fetches the per-province heatwave forecast from
 * `GET /api/forecast/province/:id?days=N` (spec §7 / Phase 5) and exposes it
 * with loading / error / empty states plus the `generated_at` ("as of")
 * timestamp of the latest model run.
 *
 * This is intentionally separate from the legacy `useForecast(cycle)` hook,
 * which targets the older `/api/forecast/latest` endpoint and a different
 * response shape — both coexist.
 */

import { useState, useEffect, useCallback, useRef } from 'react';
import {
  getProvinceForecast,
  type ProvinceForecastDay,
} from '../services/forecastService';

export interface UseProvinceForecastReturn {
  days: ProvinceForecastDay[];
  /** ISO timestamp of the latest model run (from the first day), or null. */
  generatedAt: string | null;
  loading: boolean;
  error: string | null;
  refresh: () => Promise<void>;
}

export function useProvinceForecast(
  provinceId: number | null,
  days: number = 7,
): UseProvinceForecastReturn {
  const [forecast, setForecast] = useState<ProvinceForecastDay[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  // Prevent overlapping fetches for the same province
  const fetchingRef = useRef(false);

  const fetchForecast = useCallback(async () => {
    if (provinceId == null) {
      setForecast([]);
      setError(null);
      setLoading(false);
      return;
    }
    if (fetchingRef.current) return;
    fetchingRef.current = true;

    setLoading(true);
    setError(null);

    try {
      const data = await getProvinceForecast(provinceId, days);

      if (!Array.isArray(data) || data.length === 0) {
        setForecast([]);
        setError('No forecast available for this province yet.');
        return;
      }

      setForecast(data);
    } catch (err: any) {
      setForecast([]);
      setError(
        err?.name === 'NetworkError'
          ? 'Cannot reach the forecast service. Check your connection.'
          : `Failed to load forecast: ${err?.message ?? 'unknown error'}`,
      );
    } finally {
      setLoading(false);
      fetchingRef.current = false;
    }
  }, [provinceId, days]);

  useEffect(() => {
    fetchForecast();
  }, [fetchForecast]);

  const generatedAt = forecast.length > 0 ? forecast[0].generated_at : null;

  return { days: forecast, generatedAt, loading, error, refresh: fetchForecast };
}

export default useProvinceForecast;
