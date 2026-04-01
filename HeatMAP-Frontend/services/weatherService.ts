/**
 * Weather Service — Open-Meteo Integration
 *
 * Fetches real-time current conditions (temperature, humidity, UV index,
 * apparent temperature) and hourly forecasts for the next 12 hours.
 *
 * Uses the free Open-Meteo API — no API key required.
 * Docs: https://open-meteo.com/en/docs
 *
 * Also uses the Open-Meteo Air Quality API for AQI data.
 */

// ─── Types ────────────────────────────────────────────────────────────────────

export interface CurrentConditions {
  temperature_c: number;
  apparent_temperature_c: number;
  relative_humidity: number;
  uv_index: number;
  wind_speed_kmh: number;
  weather_code: number;
}

export interface HourlyForecastPoint {
  time: string;        // ISO timestamp
  temperature_c: number;
  weather_code: number;
}

export interface AirQuality {
  /** European AQI: 0-20 Good, 20-40 Fair, 40-60 Moderate, 60-80 Poor, 80-100 Very Poor */
  european_aqi: number;
  label: string;
}

export interface WeatherData {
  current: CurrentConditions;
  hourly: HourlyForecastPoint[];
  airQuality: AirQuality;
  location: { latitude: number; longitude: number };
  fetchedAt: string;
}

// ─── Constants ────────────────────────────────────────────────────────────────

const DEFAULT_LAT = 13.75;   // Bangkok / Central Thailand
const DEFAULT_LNG = 100.50;

const TIMEOUT_MS = 10_000;

// ─── Helpers ─────────────────────────────────────────────────────────────────

function aqiLabel(aqi: number): string {
  if (aqi <= 20) return 'Good';
  if (aqi <= 40) return 'Fair';
  if (aqi <= 60) return 'Moderate';
  if (aqi <= 80) return 'Poor';
  return 'Very Poor';
}

/**
 * Approximate wet-bulb temperature using Stull (2011) formula.
 * Input: temperature in °C, relative humidity 0-100.
 */
export function wetBulbApprox(t: number, rh: number): number {
  return (
    t * Math.atan(0.151977 * Math.pow(rh + 8.313659, 0.5)) +
    Math.atan(t + rh) -
    Math.atan(rh - 1.676331) +
    0.00391838 * Math.pow(rh, 1.5) * Math.atan(0.023101 * rh) -
    4.686035
  );
}

async function fetchWithTimeout(url: string): Promise<any> {
  const controller = new AbortController();
  const timer = setTimeout(() => controller.abort(), TIMEOUT_MS);
  try {
    const res = await fetch(url, { signal: controller.signal });
    if (!res.ok) throw new Error(`HTTP ${res.status}`);
    return await res.json();
  } finally {
    clearTimeout(timer);
  }
}

// ─── Main API ─────────────────────────────────────────────────────────────────

/**
 * Fetch current weather conditions from Open-Meteo.
 * Falls back to reasonable defaults if the request fails.
 */
export async function getCurrentWeather(
  latitude = DEFAULT_LAT,
  longitude = DEFAULT_LNG,
): Promise<CurrentConditions> {
  const url =
    `https://api.open-meteo.com/v1/forecast` +
    `?latitude=${latitude}&longitude=${longitude}` +
    `&current=temperature_2m,relative_humidity_2m,apparent_temperature,uv_index,wind_speed_10m,weather_code` +
    `&wind_speed_unit=kmh` +
    `&timezone=Asia%2FBangkok`;

  const data = await fetchWithTimeout(url);
  const c = data.current ?? {};

  return {
    temperature_c:          c.temperature_2m          ?? 34,
    apparent_temperature_c: c.apparent_temperature    ?? 36,
    relative_humidity:      c.relative_humidity_2m    ?? 60,
    uv_index:               c.uv_index               ?? 0,
    wind_speed_kmh:         c.wind_speed_10m          ?? 0,
    weather_code:           c.weather_code            ?? 0,
  };
}

/**
 * Fetch hourly forecast for the next 12 hours from Open-Meteo.
 */
export async function getHourlyForecast(
  latitude = DEFAULT_LAT,
  longitude = DEFAULT_LNG,
): Promise<HourlyForecastPoint[]> {
  const now = new Date();
  const startDate = now.toISOString().split('T')[0];

  const url =
    `https://api.open-meteo.com/v1/forecast` +
    `?latitude=${latitude}&longitude=${longitude}` +
    `&hourly=temperature_2m,weather_code` +
    `&start_date=${startDate}&end_date=${startDate}` +
    `&timezone=Asia%2FBangkok`;

  const data = await fetchWithTimeout(url);
  const times: string[]  = data.hourly?.time          ?? [];
  const temps: number[]  = data.hourly?.temperature_2m ?? [];
  const codes: number[]  = data.hourly?.weather_code   ?? [];

  // Return up to 12 hours starting from current hour
  const currentHour = now.getHours();
  return times
    .map((t, i) => ({ time: t, temperature_c: temps[i] ?? 0, weather_code: codes[i] ?? 0 }))
    .filter((_, i) => i >= currentHour)
    .slice(0, 12);
}

/**
 * Fetch European AQI from Open-Meteo Air Quality API.
 */
export async function getAirQuality(
  latitude = DEFAULT_LAT,
  longitude = DEFAULT_LNG,
): Promise<AirQuality> {
  const url =
    `https://air-quality-api.open-meteo.com/v1/air-quality` +
    `?latitude=${latitude}&longitude=${longitude}` +
    `&current=european_aqi` +
    `&timezone=Asia%2FBangkok`;

  const data = await fetchWithTimeout(url);
  const aqi: number = data.current?.european_aqi ?? 0;
  return { european_aqi: aqi, label: aqiLabel(aqi) };
}

/**
 * Convenience: fetch all weather data in parallel.
 * Errors in individual requests are caught and replaced with defaults
 * so the app always renders something meaningful.
 */
export async function getAllWeatherData(
  latitude = DEFAULT_LAT,
  longitude = DEFAULT_LNG,
): Promise<WeatherData> {
  const [current, hourly, airQuality] = await Promise.all([
    getCurrentWeather(latitude, longitude).catch(() => ({
      temperature_c: 34,
      apparent_temperature_c: 36,
      relative_humidity: 60,
      uv_index: 3,
      wind_speed_kmh: 10,
      weather_code: 0,
    } as CurrentConditions)),

    getHourlyForecast(latitude, longitude).catch(() => [] as HourlyForecastPoint[]),

    getAirQuality(latitude, longitude).catch(() => ({
      european_aqi: 0,
      label: 'Unknown',
    } as AirQuality)),
  ]);

  return {
    current,
    hourly,
    airQuality,
    location: { latitude, longitude },
    fetchedAt: new Date().toISOString(),
  };
}

/**
 * Map WMO weather code to an icon name compatible with IconSymbol.
 * Codes: https://open-meteo.com/en/docs#weathervariables
 */
export function weatherCodeToIcon(code: number): string {
  if (code === 0)              return 'sunny';
  if (code <= 2)               return 'partly_cloudy_day';
  if (code <= 3)               return 'cloud';
  if (code <= 49)              return 'foggy';
  if (code <= 67)              return 'rainy';
  if (code <= 77)              return 'ac_unit';
  if (code <= 82)              return 'rainy';
  if (code <= 99)              return 'thunderstorm';
  return 'sunny';
}
