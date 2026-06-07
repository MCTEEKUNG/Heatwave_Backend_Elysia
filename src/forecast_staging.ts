import { readFileSync } from "fs";

/**
 * Local staging forecast source — mirrors the `heatwave.forecasts` queries in
 * src/routes/forecast.ts but reads from a JSON file written by
 * `run_daily_forecast.py --staging`. Lets the backend serve a promoted candidate's
 * forecasts for a pre-deploy local test WITHOUT touching Supabase. Active only when
 * `HEATWAVE_FORECAST_FILE` is set.
 */
export interface StagingRow {
  province_id: number;
  lat: number | null;
  lon: number | null;
  target_date: string;
  generated_at: string;
  horizon_days: number;
  probability: number;
  predicted_label: boolean;
  swbgt_pred: number | null;
  risk_level: string;
  model_version?: string;
}

const dateOnly = (s: string): string => String(s).slice(0, 10);

export function readStaging(path: string): StagingRow[] {
  const data = JSON.parse(readFileSync(path, "utf-8"));
  if (!Array.isArray(data)) throw new Error("staging file is not a JSON array");
  return data as StagingRow[];
}

/**
 * One row per province for the map: from the freshest `generated_at` run, the
 * soonest upcoming `target_date` (>= today). Mirrors the DISTINCT ON query.
 */
export function stagingMap(rows: StagingRow[], today: string): StagingRow[] {
  const best = new Map<number, StagingRow>();
  for (const r of rows) {
    if (dateOnly(r.target_date) < today) continue; // only upcoming
    const cur = best.get(r.province_id);
    if (
      !cur ||
      r.generated_at > cur.generated_at ||
      (r.generated_at === cur.generated_at && r.target_date < cur.target_date)
    ) {
      best.set(r.province_id, r);
    }
  }
  return [...best.values()];
}

/** Latest batch for one province: freshest generated_at, upcoming dates, up to `days`. */
export function stagingProvince(
  rows: StagingRow[], provinceId: number, days: number, today: string,
): StagingRow[] {
  const mine = rows.filter((r) => r.province_id === provinceId);
  if (mine.length === 0) return [];
  const maxGen = mine.reduce((m, r) => (r.generated_at > m ? r.generated_at : m), "");
  return mine
    .filter((r) => r.generated_at === maxGen && dateOnly(r.target_date) >= today)
    .sort((a, b) => (a.target_date < b.target_date ? -1 : 1))
    .slice(0, days);
}
