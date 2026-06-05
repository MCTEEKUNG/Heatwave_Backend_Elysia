import { getSql } from "../db";

/**
 * Query helpers for the private `heatwave` schema (direct Postgres).
 * All queries are parameterized via the postgres tagged template.
 */

/** All provinces ordered by id (name + centroid). */
export async function getProvinces() {
  const sql = getSql();
  const rows = await sql`
    SELECT id, code, name_th, name_en, region, lat, lon
    FROM heatwave.provinces
    ORDER BY id ASC
  `;
  // Return a PLAIN array, not the postgres `Result` (an Array subclass).
  // Elysia/@elysiajs/cors does not append CORS response headers when a handler
  // returns the non-plain `Result` instance, so the actual GET response reaches
  // the browser without `Access-Control-Allow-Origin` (preflight still passes,
  // making the bug subtle). Spreading into a plain array restores CORS headers.
  return [...rows];
}

/**
 * Latest forecast batch for a single province.
 * Picks the newest `generated_at` for that province, then returns the next
 * `days` target_dates from today onward within that batch.
 */
export async function getProvinceForecast(provinceId: number, days: number) {
  const sql = getSql();
  const rows = await sql`
    SELECT province_id, target_date, generated_at, horizon_days,
           probability, predicted_label, swbgt_pred, risk_level, model_version
    FROM heatwave.forecasts
    WHERE province_id = ${provinceId}
      AND generated_at = (
        SELECT MAX(generated_at)
        FROM heatwave.forecasts
        WHERE province_id = ${provinceId}
      )
      AND target_date >= current_date
    ORDER BY target_date ASC
    LIMIT ${days}
  `;
  return [...rows]; // plain array so @elysiajs/cors appends CORS headers (see getProvinces)
}

/**
 * Latest forecast per province for the map: one row each, taken from the
 * freshest `generated_at` run, choosing the soonest upcoming target_date
 * (today's / nearest risk) so the map reflects current conditions.
 *
 * Semantics chosen: freshest run (generated_at DESC) + soonest date
 * (target_date ASC). This is the defensible default for a "current risk" map.
 */
export async function getForecastMap() {
  const sql = getSql();
  const rows = await sql`
    SELECT DISTINCT ON (f.province_id)
           f.province_id, p.lat, p.lon,
           f.target_date, f.generated_at, f.horizon_days,
           f.probability, f.predicted_label, f.swbgt_pred,
           f.risk_level, f.model_version
    FROM heatwave.forecasts f
    JOIN heatwave.provinces p ON p.id = f.province_id
    WHERE f.target_date >= current_date
    ORDER BY f.province_id ASC, f.generated_at DESC, f.target_date ASC
  `;
  return [...rows]; // plain array so @elysiajs/cors appends CORS headers (see getProvinces)
}

/** Threshold rows for a province (per day-of-year, per metric). */
export async function getThresholds(provinceId: number) {
  const sql = getSql();
  return sql`
    SELECT province_id, doy, metric, p90, p95, p975, baseline_period, updated_at
    FROM heatwave.province_thresholds
    WHERE province_id = ${provinceId}
    ORDER BY metric ASC, doy ASC
  `;
}
