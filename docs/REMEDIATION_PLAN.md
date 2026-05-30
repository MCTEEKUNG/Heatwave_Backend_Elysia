# Heatwave AI — Remediation Plan (heat-map-frontend.vercel.app)

> Status: PLAN ONLY — no code changed, nothing deployed. Produced 2026-05-30.
> Diagnosis confirmed via live network capture, backend 404 probing, screenshot,
> and direct Supabase queries. Detail blueprints from 3 parallel investigations.

## Root cause (one line)
The repo moved ahead to a per-province + Supabase + LINE architecture, but **neither
the Vercel frontend nor the Render backend were redeployed**, and the forecast DB is
only seeded for 3 of 77 provinces. Three layers are out of sync.

---

## ⛔ Phase 0 — BLOCKING: confirm the backend deploy target
`package.json` `repository` = `github.com/MCTEEKUNG/Heatwave_Backend_Elysia.git`, but the
working code lives in the `Heatwave_AI` monorepo and there is no `render.yaml`. The Render
service may build from a **different repo/branch**. If so, every backend fix below must be
pushed *there*, or the redeploy is a no-op.
- **Action (user):** In Render dashboard → service `heatwave-backend-elysia` → Settings,
  read the connected Repository + Branch + Root Directory + Dockerfile path.
- Decide: push fixes to that repo/branch, OR repoint Render at `Heatwave_AI` (branch with the fix).

---

## Phase 1 — Data layer (longest lead time; can start immediately, in parallel)
Goal: populate `heatwave.forecasts` for all 77 provinces.

The real bottleneck is **thresholds**, not the DB:
- `data/processed/province_thresholds.parquet` covers only **20/77** provinces (p95 per day-of-year).
- A province with no p95 → NaN feature → `make_forecasting_frame` drops the row → **0 forecasts**.
- The current 3 provinces (ids 1, 29, 77) came from `scripts/run_forecast_live.py:37` (hardcoded smoke-test default `[1,29,77]`), not a bug.
- The model (`models/heatwave_model.pkl`, lgbm-v1) is **trained on 20/77** (`models/model_card.json`). The other 57 will score mechanically but are statistically **unvalidated**.

Steps (from repo root, `.venv`):
1. `python scripts/build_full_dataset.py` — regenerate thresholds+dataset for all 77 (resumable; skips 20 cached `_parts/`; ~20+ min; Open-Meteo paced 20s/call, watch for 429s).
2. Export `DATABASE_URL` (Supabase pooler, port 6543), then `python -m pipeline.run_forecast` — generates + upserts ~77×7 = 539 rows. (Writer: `src/db_write.py:74`, `ON CONFLICT (province_id,target_date,generated_at) DO UPDATE`.)
3. (Optional, serving layer) `python -m pipeline.load_thresholds` — sync parquet → `heatwave.province_thresholds` (DB table currently EMPTY; not required for generation).
4. Verify (read-only):
   ```sql
   select count(distinct province_id) provinces, count(*) rows
   from heatwave.forecasts
   where generated_at = (select max(generated_at) from heatwave.forecasts);
   -- expect provinces = 77, rows = 539
   ```

**Decision needed:** mechanically populate all 77 now (fast, 57 unvalidated) vs. retrain the
model on the full 77-province dataset first (slower, higher quality). PRODUCTION.md flags
"expand coverage 20→77" as the P0 quality lever.

---

## Phase 2 — Backend code fixes (single redeploy; after Phase 0, ideally after Phase 1 data)
Files in `Heatwave_AI/src/`.

1. **`/api/forecast/map` is missing `lat`/`lon`** — `src/routes/forecast.ts:49-59`. Frontend
   `nearestPoint()` needs them; without, every distance is NaN and coloring breaks. Fix query:
   ```ts
   export async function getForecastMap() {
     const sql = getSql();
     return sql`
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
   }
   ```
2. **`/api/forecast/province/:id` returns an object, frontend expects a bare array** —
   `src/index.ts:340-347`. **DECISION: return the bare array** (spec §7; matches `/provinces` &
   `/map`; zero frontend change for this item). Replace the `return { province_id, days,
   generated_at, forecast: rows }` with `return rows;` (keep the `days` clamp + LIMIT).

**Required Render env vars:**
| Var | Need | Note |
|---|---|---|
| `DATABASE_URL` | **Mandatory** | else `getSql()` throws → endpoints 503. Supabase pooler :6543 `?sslmode=require` |
| `ALLOWED_ORIGINS` | **Mandatory** | must include `https://heat-map-frontend.vercel.app` (else CORS blocks browser even if curl 200) |
| `LINE_CHANNEL_SECRET`/`_ACCESS_TOKEN` | optional | only `/api/line/webhook` |
| `PORT` | auto | Render-injected; don't set |

Build/start: Docker via `Dockerfile.render` → `bun run src/index.ts`. Verify after deploy:
```bash
curl -s .../api/forecast/map | head                          # 404→200, rows include lat/lon
curl -s ".../api/forecast/province/1?days=7"                 # 404→200, BARE array
curl -s .../api/provinces | head                             # 404→200
curl -sI -H "Origin: https://heat-map-frontend.vercel.app" .../api/forecast/map | grep -i access-control-allow-origin
```

---

## Phase 3 — Frontend code fixes (single redeploy; ONLY after backend verified)
Files in `Heatwave_AI/HeatMAP-Frontend/`. (Item "province object/array" is handled backend-side, so it's dropped here.)

1. **LIVE bug — `getSeverityBorderColor`** (`components/map/MapGrid.tsx:217-228`) only handles
   `extreme|medium|low`; `'medium'` isn't a valid Severity, so `high`/`moderate` cells render
   with no border. Fix to `extreme|high|moderate|low`.
2. **`humidity_pct` → `humidity_est`** — `services/forecastService.ts:3-13` (rename field; drop
   unused `heat_index_c`/`data_source`) and `hooks/useForecast.ts:103` (`d.humidity_pct` →
   `d.humidity_est`; currently makes avgHumidity NaN).
3. **Dead mock cleanup** — `MapGrid.tsx`: delete `seededRandom` (74-78), `generateMockSeverity`
   (80-103), `generateMockTemperature` (105-117), `generateMockProbability` (119-130),
   `MOCK_GRID_DATA` (202); drop `mockData` param + `if(mockData)` block (145-176); change
   `MapGrid` default `gridData = MOCK_GRID_DATA` → `generateThailandGrid()` (470).
   `components/map/index.ts:5` remove `MOCK_GRID_DATA` export. Fix misleading comments
   (`MapGrid.tsx:8`, `services/nearbyPlaces.ts:1-12` — it already uses Google Places + OSM, not mock).
   **KEEP** `generateThailandGrid`, `getSeverityColor`, `getSeverityBorderColor`.
4. **Zoom +/- buttons dead** (`app/(tabs)/map.tsx:295-304`, no onPress). Recommended: set Leaflet
   `zoomControl={true}` (`MapGrid.tsx:344`) and delete the custom button block + unused styles.

Env: `EXPO_PUBLIC_API_URL=https://heatwave-backend-elysia.onrender.com` in Vercel (inlined at
build). Build: `npx expo export --platform web`. Redeploy via Vercel.

---

## Phase 4 — End-to-end verification (browser)
On `/map`: per-province colors (not all-red), province panel shows 7-day data on select,
"as of" timestamp present, forecast tab humidity not NaN, zoom works.

---

## Ordering & dependencies
- **Phase 0 blocks Phase 2 deploy.**
- **Phase 1 (data)** independent of code — start now; map is only meaningful once populated.
- **Phase 2 (backend) MUST deploy before Phase 3 (frontend).** Frontend-first → `/api/forecast/map`
  404 → blank/neutral grid (worse than today).
- Phase 3 edits are safe in any order among themselves.

## Mock-data verdict
No active mock data in production (MapGrid generators gated off; `nearbyPlaces` is real). Remaining
items are dead code + misleading comments → cleanup (Phase 3 item 3), not a runtime bug.
