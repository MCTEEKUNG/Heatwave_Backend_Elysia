import { Platform } from 'react-native';

const getApiUrl = () => {
  if (Platform.OS === 'android') {
    return 'http://10.0.2.2:3000';
  }
  if (Platform.OS === 'web') {
    return 'http://localhost:3000';
  }
  return 'http://localhost:3000';
};

const API_URL = getApiUrl();
console.log('[ForecastService] API URL:', API_URL, 'Platform:', Platform.OS);

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

export async function runForecast(
  model: string,
  days: number = 30,
  cycles: number = 1,
  startDate?: string
): Promise<ForecastResponse> {
  console.log('[Forecast] Running:', { model, days, cycles, startDate, url: `${API_URL}/api/forecast` });
  
  const response = await fetch(`${API_URL}/api/forecast`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ model, days, cycles, startDate })
  });

  const data = await response.json();
  console.log('[Forecast] Response:', JSON.stringify(data).slice(0, 200));
  return data;
}

export async function getLatestForecast(): Promise<LatestForecastResponse> {
  const url = `${API_URL}/api/forecast/latest`;
  console.log('[Forecast] Fetching from:', url);
  
  try {
    const response = await fetch(url);
    console.log('[Forecast] Response status:', response.status);
    
    const data = await response.json();
    console.log('[Forecast] Received:', {
      filename: data.filename,
      totalDays: data.totalDays,
      forecastLength: data.forecast?.length,
      firstDay: data.forecast?.[0]
    });
    return data;
  } catch (error: any) {
    console.error('[Forecast] Error:', error.message);
    throw error;
  }
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
  const date = new Date(dateStr);
  return date.toLocaleDateString('en-US', {
    month: 'short',
    day: 'numeric',
    year: 'numeric'
  });
}
