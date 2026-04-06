/**
 * useWeather Hook
 *
 * Fetches current weather conditions and hourly forecast from Open-Meteo.
 * Accepts an optional lat/lng (e.g. from useLocation) and falls back to
 * Bangkok (13.75°N, 100.50°E) when no location is available.
 *
 * Data is cached for 10 minutes to avoid hammering the free API.
 */

import { useState, useEffect, useCallback, useRef } from 'react';
import {
  getAllWeatherData,
  wetBulbApprox,
  weatherCodeToIcon,
  type WeatherData,
  type HourlyForecastPoint,
  type DailyForecastPoint,
} from '../services/weatherService';

// ─── Types ────────────────────────────────────────────────────────────────────

export interface HourlyItem {
  label:   string;
  icon:    string;
  temp:    number;
  time:    string;
}

export interface DailyItem {
  date:        string;   // YYYY-MM-DD
  dayLabel:    string;   // "Today", "Mon", "Tue", …
  icon:        string;
  tempMax:     number;
  tempMin:     number;
  precipProb:  number;   // 0-100
}

export interface UseWeatherReturn {
  temperature:    number;
  feelsLike:      number;
  humidity:       number;
  uvIndex:        number;
  wetBulb:        number;
  windSpeed:      number;
  aqi:            number;
  aqiLabel:       string;
  hourly:         HourlyItem[];
  daily:          DailyItem[];
  loading:        boolean;
  error:          string | null;
  lastFetched:    Date | null;
  refresh:        () => Promise<void>;
}

// ─── Constants ────────────────────────────────────────────────────────────────

const CACHE_TTL_MS = 10 * 60 * 1000; // 10 minutes
const DEFAULT_LAT  = 13.75;
const DEFAULT_LNG  = 100.50;

// ─── Helpers ──────────────────────────────────────────────────────────────────

function formatLabel(point: HourlyForecastPoint, index: number): string {
  if (index === 0) return 'Now';
  const date = new Date(point.time);
  const h    = date.getHours();
  return `${h}:00`;
}

function buildHourly(points: HourlyForecastPoint[]): HourlyItem[] {
  return points.slice(0, 5).map((p, i) => ({
    label: formatLabel(p, i),
    icon:  weatherCodeToIcon(p.weather_code),
    temp:  Math.round(p.temperature_c),
    time:  p.time,
  }));
}

const DAY_NAMES = ['Sun', 'Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat'];

function buildDaily(points: DailyForecastPoint[]): DailyItem[] {
  const todayStr = new Date().toISOString().split('T')[0];
  return points.map((p) => {
    const d = new Date(`${p.date}T00:00:00Z`);
    return {
      date:       p.date,
      dayLabel:   p.date === todayStr ? 'Today' : DAY_NAMES[d.getUTCDay()],
      icon:       weatherCodeToIcon(p.weather_code),
      tempMax:    Math.round(p.temp_max_c),
      tempMin:    Math.round(p.temp_min_c),
      precipProb: p.precipitation_probability,
    };
  });
}

// ─── Hook ────────────────────────────────────────────────────────────────────

export function useWeather(
  latitude?:  number | null,
  longitude?: number | null,
): UseWeatherReturn {
  const lat = latitude  ?? DEFAULT_LAT;
  const lng = longitude ?? DEFAULT_LNG;

  const [data,       setData]       = useState<WeatherData | null>(null);
  const [loading,    setLoading]    = useState(true);
  const [error,      setError]      = useState<string | null>(null);
  const [lastFetched, setLastFetched] = useState<Date | null>(null);

  const fetchingRef  = useRef(false);
  const lastFetchRef = useRef<number>(0);

  const fetchWeather = useCallback(async (force = false) => {
    if (fetchingRef.current) return;

    // Skip if still within cache window (unless forced)
    if (!force && Date.now() - lastFetchRef.current < CACHE_TTL_MS) return;

    fetchingRef.current = true;
    setLoading(true);
    setError(null);

    try {
      const result = await getAllWeatherData(lat, lng);
      setData(result);
      setLastFetched(new Date());
      lastFetchRef.current = Date.now();
    } catch (err: any) {
      setError(`Weather data unavailable: ${err.message}`);
    } finally {
      setLoading(false);
      fetchingRef.current = false;
    }
  }, [lat, lng]);

  useEffect(() => {
    fetchWeather(true);
  }, [lat, lng]); // re-fetch if location changes

  // ── Derived values ──
  const temperature = data?.current.temperature_c          ?? 34;
  const feelsLike   = data?.current.apparent_temperature_c ?? 36;
  const humidity    = data?.current.relative_humidity      ?? 60;
  const uvIndex     = data?.current.uv_index               ?? 0;
  const windSpeed   = data?.current.wind_speed_kmh         ?? 0;
  const wetBulb     = Math.round(wetBulbApprox(temperature, humidity) * 10) / 10;
  const aqi         = data?.airQuality.european_aqi        ?? 0;
  const aqiLabel    = data?.airQuality.label               ?? 'Unknown';
  const hourly      = buildHourly(data?.hourly ?? []);
  const daily       = buildDaily(data?.daily ?? []);

  return {
    temperature,
    feelsLike,
    humidity,
    uvIndex,
    wetBulb,
    windSpeed,
    aqi,
    aqiLabel,
    hourly,
    daily,
    loading,
    error,
    lastFetched,
    refresh: () => fetchWeather(true),
  };
}
