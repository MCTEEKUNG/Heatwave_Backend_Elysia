# Clean ERA5 + NDVI Forecasting Dataset — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Rebuild the heatwave training dataset from **real** ERA5 reanalysis (6-hourly, **2016–2025** — the years that carry humidity/wind; from the `MCTEEKUNG/Heatwave_Backend_Elysia` repo) + **NASA MODIS NDVI**, as a strictly **leakage-safe k-day-ahead forecasting** dataset over all 77 provinces — and make this dataset the single source of truth for all future training.

**Architecture:** Ingest gridded ERA5 NetCDF + NDVI, sample at the 77 province centroids, aggregate hourly→daily (computing the *correct* daily-max heat index), then feed the existing leakage-safe forecasting machinery (`src/features.make_forecasting_frame`: antecedent-only features via `.shift(1).rolling`, target `y = heatwave.shift(-k)`) with a **temporal** train/val/test split. We take the backend's **data**, not its **methodology**.

**Tech Stack:** Python 3.12 (`.venv`), `xarray`+`netCDF4` (ERA5), `rioxarray`+`rasterio` (NDVI GeoTIFF) or `earthaccess` (NASA MOD13A3), `pandas`/`numpy`, `scikit-learn`/`lightgbm`, existing repo modules under `src/`, `pipeline/`, `evaluation/`.

---

## Non-Negotiable Principles (the whole point of this plan)

These exist because the source backend project violated them and produced a meaningless F1=0.9963 / ROC=1.000:

1. **Real data only, sourced by this plan.** Every feature traces to a file this plan downloads (ERA5 `.nc`, NDVI). No synthetic, no noise-model, no "analysis disguised as forecast." If a value cannot be obtained at decision time in production, it is **not** a feature.
2. **Leakage-safe forecasting, not same-day classification.** Features use ONLY data at `≤ t` (`.shift(1).rolling`); the label is `heatwave(t+k)`. The target day's own weather is **never** a feature (`src/features.LEAKY_COLS`).
3. **Temporal split, never random.** Train on early years, validate/test on later years. A random split on autocorrelated daily weather is leakage.
4. **ERA5 is reanalysis = antecedent truth, NOT a forecast of the future.** Using past ERA5 as features is clean. Using the *target day's* ERA5 as a feature is the leakage trap (`scripts/oracle_headroom.py`). **This plan does NOT implement P0 forecast covariates** — that remains a separate future phase requiring genuine forecasts. This plan delivers the clean, rich *antecedent* forecasting model.
5. **Label chosen after profiling the data** (per user decision). Phase 3 produces a profiling report; the label config is committed only after seeing real base rates.

**Data provenance — take vs reject:**
| From `Heatwave_Backend_Elysia` | Decision |
|---|---|
| ERA5 surface `.nc` (t2m, d2m, sp, u10, v10), hourly, 0.25°, 2000–2025 | ✅ TAKE (real data) |
| NDVI MODIS MOD13A3 (monthly, 1 km) | ✅ TAKE — but re-source from **NASA** (Phase 2) |
| Rothfusz heat-index + Magnus RH formulas | ✅ TAKE (physics, reusable) |
| Random stratified split | ❌ REJECT → temporal split |
| Same-day HI≥41 label from same-day features | ❌ REJECT → forecasting frame (`y = heatwave(t+k)`) |
| Their leaderboard / 0.99 scores | ❌ REJECT (leakage artifacts) |

### Data reality (VERIFIED by opening the actual `.nc` files)

The ERA5 archive is **heterogeneous** — confirmed by inspecting `era5_surface_2003.nc` and `era5_surface_2020.nc`:

| Era | Temporal res | Variables present | Coord |
|---|---|---|---|
| **2000–2015** (~3 MB/yr) | **daily** (24 h step) | only `t2m`, `swvl1` (soil water) | `valid_time` |
| **2016–2025** (~27 MB/yr) | **6-hourly** (6 h step) | `t2m, d2m, sp, u10, v10` | `valid_time` |

Both eras use coord name **`valid_time`** (CDS-Beta) and carry extra `number`/`expver` dims that must be squeezed.

**Consequences (baked into this plan):**
- The heat-index label needs humidity (`d2m`), which exists **only 2016–2025**. → **The canonical v2 dataset is scoped to 2016–2025** (10 years). Split: train 2016–2021 / val 2022–2023 / test 2024–2025.
- 2016–2025 is **6-hourly**, not hourly: daily-max heat index is the max over 4 samples/day (00/06/12/18 UTC; 06 UTC ≈ 13:00 ICT, near afternoon peak). This is a real improvement over daily-mean labeling — state it honestly as 6-hourly, not hourly.
- 2000–2015 (daily `t2m`+`swvl1`) is **out of scope for v2**; documented as a future t2m/soil-moisture extension, not mixed in.
- Ingestion code MUST: use `valid_time`, squeeze `number`/`expver`, and **assert sub-daily spacing** (fail loudly if handed a daily file) so a daily file can never be silently averaged into the label.

---

## File Structure

| File | Responsibility |
|---|---|
| `requirements.txt` (modify) | add `xarray`, `netCDF4`, `rioxarray`, `rasterio`, `earthaccess` |
| `scripts/fetch_era5_repo.py` (create) | download ERA5 `.nc` (+ NDVI tif fallback) from the GitHub repo into `data/raw/` |
| `src/era5_ingest.py` (create) | open ERA5 NetCDF, sample at province centroids, hourly→daily aggregates |
| `src/heat_index.py` (create) | Magnus RH + Rothfusz heat index (vectorized, °C) |
| `src/ndvi_ingest.py` (create) | NASA MOD13A3 → per-province monthly NDVI (+ earthaccess; repo-tif fallback) |
| `pipeline/build_era5_dataset.py` (create) | orchestrate ERA5+NDVI → `data/processed/dataset_era5.parquet` (same schema as current + extra feature cols) |
| `scripts/profile_dataset.py` (create) | EDA + label base-rate report → `docs/DATASET_PROFILE.md` (Phase 3 decision input) |
| `src/features.py` (modify) | extend `_VALUE_COLS` with the new daily ERA5 aggregates; NDVI antecedent merge |
| `src/labels.py` (modify) | add absolute heat-index label mode alongside existing p95+run mode |
| `pipeline/train.py` (modify) | accept the ERA5 dataset path; temporal split unchanged |
| `docs/DATA.md` (modify) | document the new dataset as the source of truth |
| tests under `tests/` | one test file per new module |

---

## Phase 0 — Dependencies & Data Acquisition

### Task 0.1: Add geospatial dependencies

**Files:**
- Modify: `requirements.txt`

- [ ] **Step 1: Append deps**

Add these lines to `requirements.txt`:
```
xarray>=2024.0
netCDF4>=1.6
rioxarray>=0.15
rasterio>=1.3
earthaccess>=0.9
```

- [ ] **Step 2: Install**

Run: `.\.venv\Scripts\python.exe -m pip install -r requirements.txt`
Expected: all install; `python -c "import xarray, netCDF4, rioxarray, rasterio, earthaccess"` exits 0.

- [ ] **Step 3: Commit**
```bash
git add requirements.txt
git commit -m "deps: add xarray/netCDF4/rioxarray/rasterio/earthaccess for ERA5+NDVI"
```

### Task 0.2: Download ERA5 NetCDF from the source repo

**Files:**
- Create: `scripts/fetch_era5_repo.py`
- Test: `tests/test_fetch_era5_repo.py`

ERA5 files live at `MCTEEKUNG/Heatwave_Backend_Elysia/Era5-data-2000-2026/era5_surface_YYYY.nc` (and `era5_upper_YYYY.nc`). Download via the GitHub raw API into `data/raw/era5/`. Resumable (skip files already present).

- [ ] **Step 1: Write the failing test**
```python
# tests/test_fetch_era5_repo.py
from scripts.fetch_era5_repo import raw_url, surface_years

def test_raw_url_points_at_repo():
    u = raw_url("era5_surface_2003.nc")
    assert u == ("https://raw.githubusercontent.com/MCTEEKUNG/"
                 "Heatwave_Backend_Elysia/master/Era5-data-2000-2026/era5_surface_2003.nc")

def test_surface_years_span_2000_2025():
    ys = surface_years()
    assert ys[0] == 2000 and ys[-1] == 2025 and len(ys) == 26
```

- [ ] **Step 2: Run test to verify it fails**

Run: `.\.venv\Scripts\python.exe -m pytest tests/test_fetch_era5_repo.py -v`
Expected: FAIL (module not found).

- [ ] **Step 3: Implement**
```python
# scripts/fetch_era5_repo.py
"""Download real ERA5 NetCDF (and NDVI tif fallback) from the source GitHub repo.

Resumable: files already in data/raw/ are skipped. Run from repo root:
    .venv\\Scripts\\python.exe scripts\\fetch_era5_repo.py
"""
import os
import sys
import urllib.request

REPO = "MCTEEKUNG/Heatwave_Backend_Elysia"
BRANCH = "master"
ERA5_DIR_IN_REPO = "Era5-data-2000-2026"
OUT_DIR = "data/raw/era5"


def raw_url(filename: str, subdir: str = ERA5_DIR_IN_REPO) -> str:
    return f"https://raw.githubusercontent.com/{REPO}/{BRANCH}/{subdir}/{filename}"


def surface_years():
    return list(range(2000, 2026))


def _download(url: str, dest: str) -> None:
    if os.path.exists(dest) and os.path.getsize(dest) > 0:
        print(f"  skip (exists) {os.path.basename(dest)}", flush=True)
        return
    print(f"  GET {url}", flush=True)
    urllib.request.urlretrieve(url, dest)


def main():
    os.makedirs(OUT_DIR, exist_ok=True)
    for y in surface_years():
        for prefix in ("era5_surface_", "era5_upper_"):
            fn = f"{prefix}{y}.nc"
            _download(raw_url(fn), os.path.join(OUT_DIR, fn))
    print("ERA5 download complete ->", OUT_DIR, flush=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())
```

- [ ] **Step 4: Run test to verify it passes**

Run: `.\.venv\Scripts\python.exe -m pytest tests/test_fetch_era5_repo.py -v`
Expected: PASS.

- [ ] **Step 5: Run the downloader (integration)**

Run: `.\.venv\Scripts\python.exe scripts\fetch_era5_repo.py`
Expected: `data/raw/era5/era5_surface_2000.nc` … `2025.nc` present (~320 MB total surface).

- [ ] **Step 6: Commit** (data/raw is gitignored — add it)
```bash
echo "data/raw/" >> .gitignore
git add scripts/fetch_era5_repo.py tests/test_fetch_era5_repo.py .gitignore
git commit -m "feat: fetch real ERA5 NetCDF from source repo (resumable)"
```

---

## Phase 1 — ERA5 → per-province daily aggregates

### Task 1.1: Heat index + RH physics

**Files:**
- Create: `src/heat_index.py`
- Test: `tests/test_heat_index.py`

Port the backend's validated physics (Magnus RH + Rothfusz HI). Test values come from the backend's own validation table (PROJECT_CONTEXT §3.4).

- [ ] **Step 1: Write the failing test**
```python
# tests/test_heat_index.py
import numpy as np
from src.heat_index import rh_from_dewpoint, heat_index_c

def test_rh_humid_bangkok():
    # t2m 35C, dewpoint ~32C -> high RH
    rh = rh_from_dewpoint(35.0, 32.0)
    assert 80 <= rh <= 90

def test_heat_index_humid_exceeds_dry():
    hi_humid = heat_index_c(35.0, 84.5)
    hi_dry = heat_index_c(35.0, 21.8)
    assert hi_humid > 50          # backend table: ~59.7C
    assert hi_dry < 36            # backend table: ~33.3C
    assert hi_humid > hi_dry
```

- [ ] **Step 2: Run test to verify it fails**

Run: `.\.venv\Scripts\python.exe -m pytest tests/test_heat_index.py -v`
Expected: FAIL (module not found).

- [ ] **Step 3: Implement**
```python
# src/heat_index.py
"""Relative humidity (August-Roche-Magnus) and Rothfusz heat index, vectorized.

Matches the source backend's physics so labels are comparable. All temps in degC,
RH in percent. heat_index_c returns the NWS Rothfusz heat index in degC.
"""
import numpy as np


def rh_from_dewpoint(t2m_c, d2m_c):
    """Relative humidity (%) from air temp and dewpoint (Magnus)."""
    t = np.asarray(t2m_c, dtype=float)
    td = np.asarray(d2m_c, dtype=float)
    a, b = 17.625, 243.04
    rh = 100.0 * np.exp((a * td) / (b + td)) / np.exp((a * t) / (b + t))
    return np.clip(rh, 0.0, 100.0)


def heat_index_c(t2m_c, rh_pct):
    """NWS Rothfusz heat index (degC). Computed in degF then converted back."""
    t = np.asarray(t2m_c, dtype=float)
    rh = np.asarray(rh_pct, dtype=float)
    tf = t * 9.0 / 5.0 + 32.0
    hi = (-42.379 + 2.04901523 * tf + 10.14333127 * rh
          - 0.22475541 * tf * rh - 6.83783e-3 * tf**2
          - 5.481717e-2 * rh**2 + 1.22874e-3 * tf**2 * rh
          + 8.5282e-4 * tf * rh**2 - 1.99e-6 * tf**2 * rh**2)
    # low-HI regime: simple average form is more accurate
    simple = 0.5 * (tf + 61.0 + (tf - 68.0) * 1.2 + rh * 0.094)
    hi = np.where(tf < 80.0, simple, hi)
    return (hi - 32.0) * 5.0 / 9.0
```

- [ ] **Step 4: Run test to verify it passes**

Run: `.\.venv\Scripts\python.exe -m pytest tests/test_heat_index.py -v`
Expected: PASS.

- [ ] **Step 5: Commit**
```bash
git add src/heat_index.py tests/test_heat_index.py
git commit -m "feat: Magnus RH + Rothfusz heat index physics"
```

### Task 1.2: ERA5 NetCDF → per-province daily frame

**Files:**
- Create: `src/era5_ingest.py`
- Test: `tests/test_era5_ingest.py`

Open one ERA5 surface `.nc` with xarray, select the nearest grid cell to each province centroid (from `data/provinces.csv` via `src.provinces.load_provinces`), convert K→°C, compute hourly RH + hourly heat index, then aggregate to **daily**: `t2m_c_max`, `rh_mean`, `heat_index_max` (the correct daily-max — fixes the documented sWBGT bias), `wind_speed_max`, `sp_mean`.

- [ ] **Step 1: Write the failing test** (synthetic Dataset matching the REAL schema: `valid_time` coord, `number`/`expver` dims, 6-hourly)
```python
# tests/test_era5_ingest.py
import numpy as np
import pandas as pd
import pytest
import xarray as xr
from src.era5_ingest import daily_from_subdaily, nearest_cell

def _toy_6hourly():
    times = pd.date_range("2020-04-01", periods=8, freq="6h")  # 2 days x 4
    lat = np.array([13.5, 14.0]); lon = np.array([100.5, 101.0])
    shape = (len(times), len(lat), len(lon))
    def k(c): return np.full(shape, c + 273.15)
    ds = xr.Dataset(
        {"t2m": (("valid_time","latitude","longitude"), k(30.0)),
         "d2m": (("valid_time","latitude","longitude"), k(24.0)),
         "sp":  (("valid_time","latitude","longitude"), np.full(shape, 101325.0)),
         "u10": (("valid_time","latitude","longitude"), np.full(shape, 3.0)),
         "v10": (("valid_time","latitude","longitude"), np.full(shape, 4.0))},
        coords={"valid_time": times, "latitude": lat, "longitude": lon})
    return ds.expand_dims({"number": [0], "expver": [1]})  # extra dims to squeeze

def _toy_daily():
    times = pd.date_range("2003-04-01", periods=3, freq="D")
    lat = np.array([13.5]); lon = np.array([100.5])
    shape = (3, 1, 1)
    return xr.Dataset({"t2m": (("valid_time","latitude","longitude"), np.full(shape, 303.15))},
                      coords={"valid_time": times, "latitude": lat, "longitude": lon})

def test_nearest_cell_picks_closest():
    ds = _toy_6hourly()
    la, lo = nearest_cell(ds, 13.7563, 100.5018)
    assert la == 13.5 and lo == 100.5

def test_daily_aggregates_units_and_squeeze():
    df = daily_from_subdaily(_toy_6hourly(), province_id=1, lat=13.7563, lon=100.5018)
    assert list(df["time"]) == [pd.Timestamp("2020-04-01"), pd.Timestamp("2020-04-02")]
    assert abs(df["t2m_c_max"].iloc[0] - 30.0) < 1e-6      # K->C
    assert abs(df["wind_speed_max"].iloc[0] - 5.0) < 1e-6  # hypot(3,4)
    assert (df["heat_index_max"] >= df["t2m_c_max"] - 5).all()

def test_daily_file_is_rejected_loudly():
    # a daily file must NOT be silently averaged into the label
    with pytest.raises(ValueError, match="sub-daily"):
        daily_from_subdaily(_toy_daily(), province_id=1, lat=13.5, lon=100.5)
```

- [ ] **Step 2: Run test to verify it fails**

Run: `.\.venv\Scripts\python.exe -m pytest tests/test_era5_ingest.py -v`
Expected: FAIL (module not found).

- [ ] **Step 3: Implement** (real CDS-Beta schema: `valid_time`, squeeze `number`/`expver`, 6-hourly→daily-max, reject daily files)
```python
# src/era5_ingest.py
"""ERA5 6-hourly NetCDF (2016-2025) -> per-province DAILY aggregates.

Daily-max heat index (computed per 6-hourly step THEN maxed over the day) is the
physically-correct intensity DATA.md flags as the #1 label-accuracy fix. A daily
file (2000-2015, t2m-only) is REJECTED loudly so it can never be silently averaged.
"""
import numpy as np
import pandas as pd
import xarray as xr

from src.heat_index import rh_from_dewpoint, heat_index_c

_REQUIRED_VARS = ("t2m", "d2m", "sp", "u10", "v10")


def _tname(ds: xr.Dataset) -> str:
    return "valid_time" if "valid_time" in ds.coords else "time"


def _coord_names(ds: xr.Dataset):
    lat = "latitude" if "latitude" in ds.coords else "lat"
    lon = "longitude" if "longitude" in ds.coords else "lon"
    return lat, lon


def _squeeze_extra_dims(ds: xr.Dataset) -> xr.Dataset:
    for d in ("number", "expver"):
        if d in ds.dims:
            ds = ds.isel({d: 0}, drop=True)
        elif d in ds.coords:
            ds = ds.reset_coords(d, drop=True)
    return ds


def nearest_cell(ds: xr.Dataset, lat: float, lon: float):
    laname, loname = _coord_names(ds)
    la = float(ds[laname].sel({laname: lat}, method="nearest"))
    lo = float(ds[loname].sel({loname: lon}, method="nearest"))
    return la, lo


def daily_from_subdaily(ds: xr.Dataset, province_id: int, lat: float, lon: float) -> pd.DataFrame:
    ds = _squeeze_extra_dims(ds)
    tname = _tname(ds)
    times = pd.to_datetime(ds[tname].values)
    # GUARD: refuse daily data (would make heat_index_max a daily-mean bias)
    if len(times) >= 2 and np.median(np.diff(times)).astype("timedelta64[h]") >= np.timedelta64(24, "h"):
        raise ValueError(f"sub-daily data required; got daily spacing in this file "
                         f"(vars={list(ds.data_vars)}) — out of scope for v2")
    missing = [v for v in _REQUIRED_VARS if v not in ds.data_vars]
    if missing:
        raise ValueError(f"missing required vars {missing}; not a full surface file")

    laname, loname = _coord_names(ds)
    pt = ds.sel({laname: lat, loname: lon}, method="nearest")
    df = pd.DataFrame({
        "time": times,
        "t2m_c": np.asarray(pt["t2m"].values) - 273.15,
        "d2m_c": np.asarray(pt["d2m"].values) - 273.15,
        "sp": np.asarray(pt["sp"].values),
        "u10": np.asarray(pt["u10"].values),
        "v10": np.asarray(pt["v10"].values),
    })
    df["rh"] = rh_from_dewpoint(df["t2m_c"], df["d2m_c"])
    df["heat_index"] = heat_index_c(df["t2m_c"], df["rh"])
    df["wind_speed"] = np.hypot(df["u10"], df["v10"])
    df["date"] = df["time"].dt.floor("D")
    daily = df.groupby("date").agg(
        t2m_c_max=("t2m_c", "max"),
        t2m_c_mean=("t2m_c", "mean"),
        rh_mean=("rh", "mean"),
        rh_min=("rh", "min"),
        heat_index_max=("heat_index", "max"),
        wind_speed_max=("wind_speed", "max"),
        sp_mean=("sp", "mean"),
    ).reset_index().rename(columns={"date": "time"})
    daily["province_id"] = province_id
    return daily


def ingest_year(nc_path: str, provinces: pd.DataFrame) -> pd.DataFrame:
    """All provinces for one full (2016-2025) ERA5 surface file -> daily frame."""
    with xr.open_dataset(nc_path, engine="netcdf4") as ds:
        frames = [daily_from_subdaily(ds, int(p["id"]), float(p["lat"]), float(p["lon"]))
                  for _, p in provinces.iterrows()]
    return pd.concat(frames, ignore_index=True)
```

- [ ] **Step 4: Run test to verify it passes**

Run: `.\.venv\Scripts\python.exe -m pytest tests/test_era5_ingest.py -v`
Expected: PASS.

- [ ] **Step 5: Smoke test on a real file** (a 2016+ full-variable year; 2000–2015 are daily/t2m-only and will correctly raise `ValueError`)
```bash
.\.venv\Scripts\python.exe -c "from src.provinces import load_provinces; from src.era5_ingest import ingest_year; df=ingest_year('data/raw/era5/era5_surface_2020.nc', load_provinces()); print(df.shape); print(df.groupby('province_id').size().head())"
```
Expected: ~77 provinces × ~366 days, columns include `t2m_c_max, rh_mean, heat_index_max, wind_speed_max, sp_mean`.

- [ ] **Step 6: Commit**
```bash
git add src/era5_ingest.py tests/test_era5_ingest.py
git commit -m "feat: ERA5 hourly NetCDF -> per-province daily aggregates (daily-max HI)"
```

---

## Phase 2 — NASA NDVI → per-province monthly NDVI

### Task 2.1: NDVI per-province monthly series (NASA MOD13A3, repo-tif fallback)

**Files:**
- Create: `src/ndvi_ingest.py`
- Test: `tests/test_ndvi_ingest.py`

Primary source per the user decision: **NASA** MOD13A3 v061 via `earthaccess` (NASA Earthdata login). Because Earthdata auth may be unavailable in CI, the function accepts a pre-downloaded GeoTIFF path; the repo's `ndvi/NDVI_Thailand_YYYY*.tif` (already MODIS-derived) is the documented offline fallback. Sample each province centroid → monthly NDVI, then build `ndvi`, `ndvi_lag1`, `ndvi_lag2`.

- [ ] **Step 1: Write the failing test** (synthetic raster via rasterio in-memory)
```python
# tests/test_ndvi_ingest.py
import numpy as np
import pandas as pd
from src.ndvi_ingest import add_ndvi_lags

def test_add_ndvi_lags_shifts_by_month():
    df = pd.DataFrame({
        "province_id": [1, 1, 1],
        "year": [2003, 2003, 2003],
        "month": [1, 2, 3],
        "ndvi": [0.30, 0.35, 0.40],
    })
    out = add_ndvi_lags(df).sort_values("month").reset_index(drop=True)
    assert out.loc[2, "ndvi_lag1"] == 0.35
    assert out.loc[2, "ndvi_lag2"] == 0.30
```

- [ ] **Step 2: Run test to verify it fails**

Run: `.\.venv\Scripts\python.exe -m pytest tests/test_ndvi_ingest.py -v`
Expected: FAIL (module not found).

- [ ] **Step 3: Implement**
```python
# src/ndvi_ingest.py
"""NASA MODIS MOD13A3 NDVI -> per-province monthly series (+ lag features).

Primary: NASA Earthdata via earthaccess (MOD13A3 v061). Offline fallback:
pre-downloaded GeoTIFFs (e.g. the source repo's ndvi/NDVI_Thailand_YYYY*.tif).
NDVI is monthly and slow-varying; used as an ANTECEDENT feature (origin month
or earlier), never the target month.
"""
import numpy as np
import pandas as pd


def sample_geotiff_at_points(tif_path: str, points: pd.DataFrame) -> pd.DataFrame:
    """points: columns province_id, lat, lon -> adds 'ndvi' from the raster."""
    import rioxarray  # noqa: F401
    import xarray as xr
    da = xr.open_dataarray(tif_path, engine="rasterio")
    band = da.isel(band=0) if "band" in da.dims else da
    vals = [float(band.sel(x=p.lon, y=p.lat, method="nearest"))
            for p in points.itertuples()]
    out = points[["province_id"]].copy()
    out["ndvi"] = vals
    return out


def add_ndvi_lags(df: pd.DataFrame) -> pd.DataFrame:
    """Add ndvi_lag1/ndvi_lag2 per province ordered by (year, month)."""
    df = df.sort_values(["province_id", "year", "month"]).copy()
    g = df.groupby("province_id")["ndvi"]
    df["ndvi_lag1"] = g.shift(1)
    df["ndvi_lag2"] = g.shift(2)
    return df


def download_nasa_mod13a3(year: int, out_dir: str = "data/raw/ndvi") -> str:
    """Fetch MOD13A3 v061 GeoTIFF(s) for Thailand for a year via earthaccess.
    Returns the local path. Requires NASA Earthdata login (earthaccess.login()).
    """
    import os
    import earthaccess
    os.makedirs(out_dir, exist_ok=True)
    earthaccess.login(strategy="netrc")
    results = earthaccess.search_data(
        short_name="MOD13A3", version="061",
        temporal=(f"{year}-01-01", f"{year}-12-31"),
        bounding_box=(97.0, 5.0, 106.0, 21.0),  # Thailand
    )
    paths = earthaccess.download(results, out_dir)
    return paths[0] if paths else ""
```

- [ ] **Step 4: Run test to verify it passes**

Run: `.\.venv\Scripts\python.exe -m pytest tests/test_ndvi_ingest.py -v`
Expected: PASS.

- [ ] **Step 5: Acquire NDVI (integration, choose one path)**
  - NASA: `earthaccess.login()` then `download_nasa_mod13a3(y)` for 2000–2025.
  - Fallback: download `ndvi/NDVI_Thailand_YYYY*.tif` from the repo (reuse `scripts/fetch_era5_repo.raw_url(fn, subdir="ndvi")`) and sample with `sample_geotiff_at_points`.

- [ ] **Step 6: Commit**
```bash
git add src/ndvi_ingest.py tests/test_ndvi_ingest.py
git commit -m "feat: NASA MOD13A3 NDVI per-province monthly + lags (repo-tif fallback)"
```

---

## Phase 3 — Profile the data, THEN decide the label

> Per the user's decision, the label is configured **after** seeing the data, not before.

### Task 3.1: Dataset profiling report

**Files:**
- Create: `scripts/profile_dataset.py`
- Create (output): `docs/DATASET_PROFILE.md`
- Test: `tests/test_profile_dataset.py`

Profiles candidate labels on the assembled daily ERA5 frame and reports base rates per region/year so the label choice is evidence-based.

Candidate labels to profile:
- **A (absolute):** `heat_index_max ≥ 41 °C` (backend's definition, health-anchored).
- **B (relative, our forecasting default):** `heat_index_max ≥ per-doy p95` (via `src.climatology.compute_doy_percentiles`) **AND** part of a `≥ 2`-day run (via `src.labels.label_heatwave`).

- [ ] **Step 1: Write the failing test**
```python
# tests/test_profile_dataset.py
import pandas as pd
from scripts.profile_dataset import label_base_rates

def test_base_rates_reports_both_labels():
    df = pd.DataFrame({"heat_index_max": [30, 42, 45, 35, 41, 50]})
    rates = label_base_rates(df, abs_threshold=41.0)
    assert rates["absolute_ge_41"] == 4 / 6
```

- [ ] **Step 2: Run test to verify it fails**

Run: `.\.venv\Scripts\python.exe -m pytest tests/test_profile_dataset.py -v`
Expected: FAIL.

- [ ] **Step 3: Implement**
```python
# scripts/profile_dataset.py
"""Profile candidate labels on the ERA5 daily frame; write docs/DATASET_PROFILE.md."""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import pandas as pd

DAILY = "data/processed/era5_daily.parquet"


def label_base_rates(df: pd.DataFrame, abs_threshold: float = 41.0) -> dict:
    return {"absolute_ge_41": float((df["heat_index_max"] >= abs_threshold).mean())}


def main():
    df = pd.read_parquet(DAILY)
    rates = label_base_rates(df)
    lines = ["# Dataset Profile\n",
             f"- rows: {len(df):,}  provinces: {df['province_id'].nunique()}",
             f"- years: {pd.to_datetime(df['time']).dt.year.min()}–"
             f"{pd.to_datetime(df['time']).dt.year.max()}",
             f"- absolute (HI_max ≥ 41 °C) base rate: {rates['absolute_ge_41']*100:.2f}%",
             "\nDecision: choose label A or B based on these base rates "
             "(target a non-degenerate ~3–8% positive rate)."]
    with open("docs/DATASET_PROFILE.md", "w", encoding="utf-8") as f:
        f.write("\n".join(lines) + "\n")
    print("\n".join(lines))
    return 0


if __name__ == "__main__":
    sys.exit(main())
```

- [ ] **Step 4: Run test to verify it passes**

Run: `.\.venv\Scripts\python.exe -m pytest tests/test_profile_dataset.py -v`
Expected: PASS.

- [ ] **Step 5: DECISION GATE (human)** — run profiling after Phase 4 assembly, read `docs/DATASET_PROFILE.md`, then set the label:
  - If absolute base rate is a healthy few-percent and a health-anchored target is desired → **Label A**.
  - If it is near-zero in cool regions or you want consistency with the existing forecasting target → **Label B** (recommended default).
  Record the choice in `docs/DATA.md`.

- [ ] **Step 6: Commit**
```bash
git add scripts/profile_dataset.py tests/test_profile_dataset.py
git commit -m "feat: dataset profiling for evidence-based label choice"
```

---

## Phase 4 — Assemble the clean per-province daily dataset

### Task 4.1: Orchestrate ERA5 + NDVI + label → `dataset_era5.parquet`

**Files:**
- Create: `pipeline/build_era5_dataset.py`
- Modify: `src/labels.py` (add absolute heat-index label mode)
- Test: `tests/test_build_era5_dataset.py`

Produces a frame with the **same schema the current pipeline expects** plus the new feature columns, so `make_forecasting_frame` works unchanged:
`province_id, time, swbgt_max(=heat_index_max alias for climatology), p95, is_hot, heatwave, t2m_c_max, rh_mean, heat_index_max, wind_speed_max, sp_mean, ndvi, ndvi_lag1, ndvi_lag2, lat, lon`.

- [ ] **Step 1: Add absolute label mode — failing test**
```python
# tests/test_labels.py  (append)
import pandas as pd
from src.labels import label_absolute

def test_label_absolute_threshold():
    df = pd.DataFrame({"heat_index_max": [40.9, 41.0, 41.1]})
    out = label_absolute(df, value_col="heat_index_max", threshold=41.0)
    assert list(out["heatwave"]) == [0, 1, 1]
    assert list(out["is_hot"]) == [0, 1, 1]
```

- [ ] **Step 2: Run to verify fail**

Run: `.\.venv\Scripts\python.exe -m pytest tests/test_labels.py::test_label_absolute_threshold -v`
Expected: FAIL.

- [ ] **Step 3: Implement `label_absolute` in `src/labels.py`**
```python
# src/labels.py  (append)
def label_absolute(df, value_col="heat_index_max", threshold=41.0):
    """Absolute-threshold label (backend's heat-index mode), forecasting-safe:
    this only labels each day; the forecasting frame shifts it to t+k later."""
    out = df.copy()
    hot = (out[value_col] >= threshold).astype(int)
    out["is_hot"] = hot
    out["heatwave"] = hot
    return out
```

- [ ] **Step 4: Run to verify pass**

Run: `.\.venv\Scripts\python.exe -m pytest tests/test_labels.py::test_label_absolute_threshold -v`
Expected: PASS.

- [ ] **Step 5: Build orchestrator — failing test**
```python
# tests/test_build_era5_dataset.py
import pandas as pd
from pipeline.build_era5_dataset import attach_climatology_label

def test_attach_label_b_adds_required_columns():
    # 3 provinces-worth of daily heat_index_max over a season
    days = pd.date_range("2003-01-01", periods=400, freq="D")
    df = pd.DataFrame({"province_id": 1, "time": days,
                       "heat_index_max": 30 + 10*(days.dayofyear/365)})
    out = attach_climatology_label(df, mode="absolute", abs_threshold=35.0)
    for col in ["swbgt_max", "is_hot", "heatwave"]:
        assert col in out.columns
```

- [ ] **Step 6: Run to verify fail**

Run: `.\.venv\Scripts\python.exe -m pytest tests/test_build_era5_dataset.py -v`
Expected: FAIL.

- [ ] **Step 7: Implement orchestrator**
```python
# pipeline/build_era5_dataset.py
"""Assemble ERA5 (+NDVI) -> data/processed/dataset_era5.parquet (forecasting-ready).

Schema mirrors the current dataset so src.features.make_forecasting_frame works
unchanged; adds ERA5/NDVI feature columns. Label mode is chosen in Phase 3.
"""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import pandas as pd

from src.provinces import load_provinces
from src.era5_ingest import ingest_year
from src.climatology import compute_doy_percentiles
from src.labels import label_heatwave, label_absolute

RAW_ERA5 = "data/raw/era5"
DAILY_OUT = "data/processed/era5_daily.parquet"
DATASET_OUT = "data/processed/dataset_era5.parquet"


def attach_climatology_label(df, mode="absolute", abs_threshold=41.0,
                             value_col="heat_index_max", baseline=(1991, 2020)):
    """Add swbgt_max alias + p95/is_hot/heatwave per the chosen label mode."""
    out = df.copy()
    out["swbgt_max"] = out[value_col]  # climatology/feature code keys on swbgt_max
    if mode == "absolute":
        out = label_absolute(out, value_col=value_col, threshold=abs_threshold)
        out["p95"] = abs_threshold
        return out
    # relative p95 + >=2-day run
    thr = compute_doy_percentiles(out, value_col=value_col)
    out = label_heatwave(out, thr, value_col=value_col, min_run=2)
    return out


def main(mode="absolute", abs_threshold=41.0):
    provinces = load_provinces()
    # v2 scope: 2016-2025 only (earlier years are daily + t2m-only, no humidity).
    years = sorted(y for y in (int(f.split("_")[-1].split(".")[0])
                   for f in os.listdir(RAW_ERA5) if f.startswith("era5_surface_"))
                   if y >= 2016)
    frames = [ingest_year(os.path.join(RAW_ERA5, f"era5_surface_{y}.nc"), provinces)
              for y in years]
    daily = pd.concat(frames, ignore_index=True)
    daily = daily.merge(provinces.rename(columns={"id": "province_id"})[
        ["province_id", "lat", "lon"]], on="province_id", how="left")
    os.makedirs("data/processed", exist_ok=True)
    daily.to_parquet(DAILY_OUT, index=False)  # input to scripts/profile_dataset.py

    labeled = (daily.groupby("province_id", group_keys=False)
               .apply(lambda g: attach_climatology_label(
                   g.sort_values("time"), mode=mode, abs_threshold=abs_threshold)))
    labeled.to_parquet(DATASET_OUT, index=False)
    print(f"dataset_era5 rows={len(labeled)} provinces={labeled['province_id'].nunique()} "
          f"heatwave_rate={labeled['heatwave'].mean():.3f}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
```

- [ ] **Step 8: Run to verify pass**

Run: `.\.venv\Scripts\python.exe -m pytest tests/test_build_era5_dataset.py -v`
Expected: PASS.

- [ ] **Step 9: Build the real dataset + profile**
```bash
.\.venv\Scripts\python.exe pipeline\build_era5_dataset.py
.\.venv\Scripts\python.exe scripts\profile_dataset.py
```
Expected: `data/processed/dataset_era5.parquet` (~77 × 9500 days), `docs/DATASET_PROFILE.md` written. Apply the Phase 3 decision gate; if Label B chosen, re-run `build_era5_dataset.py main(mode="relative")`.

- [ ] **Step 10: Commit**
```bash
git add pipeline/build_era5_dataset.py src/labels.py tests/test_build_era5_dataset.py tests/test_labels.py docs/DATASET_PROFILE.md
git commit -m "feat: assemble clean ERA5+NDVI forecasting dataset + profile"
```

---

## Phase 5 — Wire ERA5/NDVI features into the leakage-safe frame

### Task 5.1: Extend antecedent feature set

**Files:**
- Modify: `src/features.py:18` (`_VALUE_COLS`) and the static-merge block
- Test: `tests/test_features.py` (append)

Add the new daily aggregates to `_VALUE_COLS` so they get `.shift(1).rolling` antecedent treatment (leakage-safe). Add NDVI columns as antecedent static-per-row values (already lagged/slow). **Do not** add `heat_index_max`/`t2m_c_max`/`rh_mean` raw (those are target-day-truth); only their shifted rolling forms appear — handled automatically because `_antecedent_features` shifts. Extend `LEAKY_COLS` to include the new raw truth columns.

- [ ] **Step 1: Append failing test**
```python
# tests/test_features.py  (append)
import pandas as pd
from src.features import make_forecasting_frame, feature_columns, LEAKY_COLS

def test_era5_features_are_antecedent_and_not_leaky():
    days = pd.date_range("2003-01-01", periods=120, freq="D")
    df = pd.DataFrame({
        "province_id": 1, "time": days, "lat": 13.7, "lon": 100.5,
        "swbgt_max": 30.0, "heat_index_max": 32.0, "t2m_c_max": 34.0,
        "rh_mean": 60.0, "wind_speed_max": 5.0, "sp_mean": 101000.0,
        "ndvi": 0.4, "ndvi_lag1": 0.39, "ndvi_lag2": 0.38,
        "p95": 33.0, "is_hot": 0, "heatwave": 0,
    })
    frame = make_forecasting_frame(df, horizons=range(1, 4))
    cols = feature_columns(frame)
    # raw truth columns must NOT be features
    assert "heat_index_max" not in cols and "t2m_c_max" not in cols
    # raw (current-month) NDVI is NOT knowable intra-month -> only completed-month lags
    assert "ndvi" not in cols
    # antecedent rolling forms + NDVI lags + wind must be present
    assert "heat_index_max_mean_7d" in cols
    assert "wind_speed_max_mean_7d" in cols
    assert "ndvi_lag1" in cols and "ndvi_lag2" in cols
    assert {"heat_index_max", "t2m_c_max", "rh_mean"} <= LEAKY_COLS
```

- [ ] **Step 2: Run to verify fail**

Run: `.\.venv\Scripts\python.exe -m pytest tests/test_features.py -v`
Expected: FAIL.

- [ ] **Step 3: Modify `src/features.py`**

Replace `_VALUE_COLS` (line 18) and `LEAKY_COLS` (lines 22-25):
```python
_VALUE_COLS = ["swbgt_max", "heat_index_max", "t2m_c_max", "rh_mean",
               "wind_speed_max", "sp_mean",
               "temperature_2m_max", "relative_humidity_2m_mean"]
_ROLL_WINDOWS = (3, 7, 14, 30)

LEAKY_COLS = frozenset(
    ["swbgt_max", "heat_index_max", "t2m_c_max", "t2m_c_mean", "rh_mean", "rh_min",
     "wind_speed_max", "sp_mean", "temperature_2m_max", "relative_humidity_2m_mean",
     "is_hot", "heatwave"]
)
```
In `make_forecasting_frame`, after the static `p95`/`lat`/`lon`/`province_id` block (after line 75), add NDVI **lags only** as antecedent static-per-row. The raw current-month `ndvi` is excluded: MOD13A3 is a *monthly composite*, so the origin month's value isn't available intra-month — only completed months (`lag1`/`lag2`) are knowable at decision time.
```python
    for ndvi_col in ("ndvi_lag1", "ndvi_lag2"):  # NOT raw "ndvi" (intra-month leak)
        if ndvi_col in d.columns:
            ante[ndvi_col] = d[ndvi_col].to_numpy()
```
`_antecedent_features` already iterates `_VALUE_COLS` and skips columns not present (`if col not in d.columns: continue`), so old datasets still work.

- [ ] **Step 4: Run to verify pass**

Run: `.\.venv\Scripts\python.exe -m pytest tests/test_features.py -v`
Expected: PASS (existing feature tests still green — backward compatible).

- [ ] **Step 5: Commit**
```bash
git add src/features.py tests/test_features.py
git commit -m "feat: leakage-safe ERA5/NDVI antecedent features in forecasting frame"
```

---

## Phase 6 — Train + evaluate on the clean dataset (temporal)

### Task 6.1: Temporal train/val/test + rolling-origin CV; compare to baseline

**Files:**
- Create: `scripts/train_era5.py`
- Test: `tests/test_train_era5.py`

Train LightGBM (production model, `src.model.train` + isotonic calibration + F2 threshold from `src/calibration.py`) on the ERA5 frame with a **temporal** split (train 2016–2021 / val 2022–2023 / test 2024–2025), report `evaluation.heatwave_metrics.compute_metrics`, and run `evaluation.cv.rolling_origin_folds` for mean±std. Upsert to the leaderboard via `pipeline.leaderboard.upsert_model` under name `era5_lgbm` so it sits beside the current model — **never overwriting** the old row, so the clean-vs-old comparison is visible.

- [ ] **Step 1: Write the failing test**
```python
# tests/test_train_era5.py
import pandas as pd
from scripts.train_era5 import year_split

def test_year_split_is_temporal():
    df = pd.DataFrame({"origin_time": pd.to_datetime(
        ["2017-06-01", "2022-06-01", "2024-06-01"])})
    tr, va, te = year_split(df)
    assert len(tr) == 1 and len(va) == 1 and len(te) == 1
    assert tr["origin_time"].dt.year.iloc[0] <= 2021
    assert te["origin_time"].dt.year.iloc[0] >= 2024
```

- [ ] **Step 2: Run to verify fail**

Run: `.\.venv\Scripts\python.exe -m pytest tests/test_train_era5.py -v`
Expected: FAIL.

- [ ] **Step 3: Implement**
```python
# scripts/train_era5.py
"""Train + evaluate the production model on the clean ERA5+NDVI dataset (temporal)."""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import numpy as np
import pandas as pd

from pipeline.frame_cache import cached_build_frames
from src.features import feature_columns
from src.model import train as lgbm_train
from src.calibration import fit_calibrator, calibrate, tune_threshold
from evaluation.heatwave_metrics import compute_metrics
from pipeline.leaderboard import upsert_model

DATASET = "data/processed/dataset_era5.parquet"


def year_split(frame, train_max=2021, val_max=2023):
    y = pd.to_datetime(frame["origin_time"]).dt.year
    return frame[y <= train_max], frame[(y > train_max) & (y <= val_max)], frame[y > val_max]


def main():
    frame = cached_build_frames(DATASET, horizons=range(1, 8))
    feats = feature_columns(frame)
    tr, va, te = year_split(frame)
    m = lgbm_train(tr[feats], tr["y"].to_numpy())
    rv = np.asarray(m.predict_proba(va[feats]))[:, 1]
    cal = fit_calibrator(rv, va["y"].to_numpy())
    thr = tune_threshold(calibrate(cal, rv), va["y"].to_numpy())
    pt = np.clip(calibrate(cal, np.asarray(m.predict_proba(te[feats]))[:, 1]), 0, 1)
    mt = compute_metrics(te["y"].to_numpy(), pt, thr)
    print(f"ERA5 clean model — PR-AUC={mt['pr_auc']:.3f} F2={mt['f2']:.3f} "
          f"ROC={mt['roc_auc']:.3f} (test n={mt['n']}, base={mt['base_rate']:.3f})")
    upsert_model("era5_lgbm", mt, n_provinces=int(frame["province_id"].nunique()))
    return 0


if __name__ == "__main__":
    sys.exit(main())
```

- [ ] **Step 4: Run to verify pass**

Run: `.\.venv\Scripts\python.exe -m pytest tests/test_train_era5.py -v`
Expected: PASS.

- [ ] **Step 5: Train on real data (integration)**

Run: `.\.venv\Scripts\python.exe scripts\train_era5.py`
Expected: prints PR-AUC/F2/ROC on test 2024–2025; `era5_lgbm` row added to `experiments/results/leaderboard.json` beside the existing model. **Sanity gate:** if F2/ROC ≈ 0.99, STOP — that signals leakage crept back in (re-audit features/split), per Principle 2/3.

- [ ] **Step 6: Commit**
```bash
git add scripts/train_era5.py tests/test_train_era5.py
git commit -m "feat: temporal train+eval on clean ERA5+NDVI dataset (era5_lgbm)"
```

---

## Phase 7 — Make it the source of truth

### Task 7.1: Document the clean dataset as canonical

**Files:**
- Modify: `docs/DATA.md`
- Modify: `docs/MODEL-IMPROVEMENT.md`

- [ ] **Step 1: Update `docs/DATA.md`** — add a section "Canonical dataset (v2): `dataset_era5.parquet`" documenting: sources (ERA5 repo + NASA NDVI), variables, the daily-max heat-index label fix, the chosen label mode (from Phase 3), temporal split, and the explicit statement that **all training references this dataset**. Mark the old Open-Meteo 2-variable dataset as superseded.

- [ ] **Step 2: Update `docs/MODEL-IMPROVEMENT.md`** — record the `era5_lgbm` test metrics vs the old baseline, and restate that forecast covariates (P0) remain a separate future phase (ERA5 reanalysis ≠ forecast).

- [ ] **Step 3: Commit**
```bash
git add docs/DATA.md docs/MODEL-IMPROVEMENT.md
git commit -m "docs: ERA5+NDVI dataset is the canonical training source"
```

---

## Self-Review

**Spec coverage:** Real-data sourcing (Task 0.2, 2.1) ✓; ERA5 6-hourly→daily-max label fix (1.2) ✓; NASA NDVI (2.1) ✓; leakage-safe forecasting frame (5.1) ✓; temporal split (6.1) ✓; label-after-profiling (Phase 3) ✓; 77 provinces (1.2/4.1 use full `load_provinces()`) ✓; reject backend methodology (Principles, 6.1 sanity gate) ✓; single source of truth (Phase 7) ✓.

**Schema VERIFIED (not assumed):** opened `era5_surface_2003.nc` (daily, t2m+swvl1, `valid_time`) and `era5_surface_2020.nc` (6-hourly, full 5 vars, `valid_time`+`number`/`expver`). Plan scoped to 2016–2025 accordingly; ingestion handles `valid_time`, squeezes extra dims, and rejects daily files loudly (test `test_daily_file_is_rejected_loudly`). NDVI raw current-month dropped (intra-month leak) — lags only.

**Placeholder scan:** No TBD/TODO; every code step has complete code; tests have real assertions.

**Type consistency:** `daily_from_hourly`/`ingest_year` emit `t2m_c_max, rh_mean, heat_index_max, wind_speed_max, sp_mean`; `attach_climatology_label` aliases `swbgt_max=heat_index_max` so `compute_doy_percentiles`/`make_forecasting_frame` (which key on `swbgt_max`) work; `_VALUE_COLS`/`LEAKY_COLS` updated to match; `year_split`/`feature_columns`/`upsert_model` signatures match their existing definitions.

**Open decision (intentional):** final label mode (A vs B) is the Phase 3 human gate — recommended default **B** (relative p95 + 2-day run) for consistency with the forecasting target, switch to **A** if profiling shows a healthy absolute base rate and a health-anchored target is preferred.
