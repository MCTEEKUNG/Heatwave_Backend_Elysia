import { getSql } from "../db";

/**
 * Query helpers for the private `heatwave` schema (direct Postgres).
 * All queries are parameterized via the postgres tagged template.
 */

/** All provinces ordered by id (name + centroid). */
export async function getProvinces() {
  const sql = getSql();
  return sql`
    SELECT id, code, name_th, name_en, region, lat, lon
    FROM heatwave.provinces
    ORDER BY id ASC
  `;
}

/**
 * Latest forecast batch for a single province.
 * Picks the newest `generated_at` for that province, then returns the next
 * `days` target_dates from today onward within that batch.
 */
export async function getProvinceForecast(provinceId: number, days: number) {
  const sql = getSql();
  return sql`
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
  return sql`
    SELECT DISTINCT ON (province_id)
           province_id, target_date, generated_at, horizon_days,
           probability, predicted_label, swbgt_pred, risk_level, model_version
    FROM heatwave.forecasts
    WHERE target_date >= current_date
    ORDER BY province_id ASC, generated_at DESC, target_date ASC
  `;
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
