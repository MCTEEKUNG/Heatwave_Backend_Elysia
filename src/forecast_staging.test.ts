import { test, expect } from "bun:test";
import { stagingMap, stagingProvince, type StagingRow } from "./forecast_staging";

const rows: StagingRow[] = [
  // province 1 — an older run, then a fresher run with several target dates
  row(1, "2026-06-06T05:00:00Z", "2026-06-07T00:00:00Z", 1),
  row(1, "2026-06-07T05:00:00Z", "2026-06-08T00:00:00Z", 1),
  row(1, "2026-06-07T05:00:00Z", "2026-06-09T00:00:00Z", 2),
  row(1, "2026-06-07T05:00:00Z", "2026-06-05T00:00:00Z", 9), // PAST -> excluded
  // province 2
  row(2, "2026-06-07T05:00:00Z", "2026-06-08T00:00:00Z", 1),
];

function row(pid: number, gen: string, target: string, h: number): StagingRow {
  return {
    province_id: pid, lat: 13.7, lon: 100.5,
    target_date: target, generated_at: gen, horizon_days: h,
    probability: 0.2, predicted_label: false, swbgt_pred: 37.0,
    risk_level: "moderate", model_version: "lgbm-v1",
  };
}

test("stagingMap picks freshest run + soonest upcoming target per province", () => {
  const out = stagingMap(rows, "2026-06-07");
  expect(out.length).toBe(2);
  const p1 = out.find((r) => r.province_id === 1)!;
  expect(p1.generated_at).toBe("2026-06-07T05:00:00Z"); // freshest run
  expect(p1.target_date).toBe("2026-06-08T00:00:00Z");   // soonest upcoming (06-05 excluded)
});

test("stagingProvince returns latest batch, upcoming, sorted, limited", () => {
  const out = stagingProvince(rows, 1, 2, "2026-06-07");
  expect(out.map((r) => r.target_date)).toEqual([
    "2026-06-08T00:00:00Z",
    "2026-06-09T00:00:00Z",
  ]);
});

test("stagingProvince unknown province -> empty", () => {
  expect(stagingProvince(rows, 999, 7, "2026-06-07")).toEqual([]);
});
