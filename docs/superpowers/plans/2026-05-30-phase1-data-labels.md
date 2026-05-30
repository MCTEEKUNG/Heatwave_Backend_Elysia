# Phase 1: Data & Labels Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** สร้างชั้นข้อมูล: ดึง Open-Meteo รายจังหวัด → คำนวณ sWBGT → percentile climatology เฉพาะจังหวัด → label heatwave (มี persistence) → temporal split — เพื่อตัด target leakage และ temporal leakage

**Architecture:** โมดูล Python เล็ก ๆ แยกหน้าที่ชัด (provinces / swbgt / openmeteo_client / climatology / labels) + แก้ `src/preprocessing.py` ให้ใช้ temporal split + สคริปต์ orchestration `pipeline/build_dataset.py` เขียนผลลง `data/processed/`. ที่เก็บลง Supabase ทำในเฟส 3

**Tech Stack:** Python 3, pandas, numpy, requests, pytest, lightgbm/scikit-learn (เฟส 2)

---

## File Structure (เฟส 1)

- Create: `data/provinces.csv` — seed 77 จังหวัด (id, code, name_th, name_en, region, lat, lon)
- Create: `src/provinces.py` — โหลด province centroids
- Create: `src/swbgt.py` — คำนวณ sWBGT
- Create: `src/openmeteo_client.py` — ดึง Open-Meteo history/forecast
- Create: `src/climatology.py` — day-of-year windowed percentiles
- Create: `src/labels.py` — heatwave label + persistence
- Modify: `src/preprocessing.py` — แทน random split ด้วย temporal split
- Create: `pipeline/build_dataset.py` — orchestration
- Create: `tests/__init__.py`, `tests/conftest.py`, และ test ต่อโมดูล

**ติดตั้งก่อน:** `pip install requests pandas numpy pytest` และสร้าง `tests/__init__.py` ว่าง

---

### Task 1: Province seed + loader

**Files:**
- Create: `data/provinces.csv`
- Create: `src/provinces.py`
- Test: `tests/test_provinces.py`

- [ ] **Step 1: สร้าง `data/provinces.csv` (header + ตัวอย่างจริง 10 จังหวัด)**

```csv
id,code,name_th,name_en,region,lat,lon
1,BKK,กรุงเทพมหานคร,Bangkok,Central,13.7563,100.5018
2,CNX,เชียงใหม่,Chiang Mai,North,18.7883,98.9853
3,TAK,ตาก,Tak,North,16.8839,99.1258
4,KKN,ขอนแก่น,Khon Kaen,Northeast,16.4419,102.8360
5,NMA,นครราชสีมา,Nakhon Ratchasima,Northeast,14.9799,102.0978
6,SKA,สงขลา,Songkhla,South,7.1896,100.5945
7,HKT,ภูเก็ต,Phuket,South,7.8804,98.3923
8,UBN,อุบลราชธานี,Ubon Ratchathani,Northeast,15.2448,104.8473
9,UDN,อุดรธานี,Udon Thani,Northeast,17.4138,102.7870
10,CBI,ชลบุรี,Chon Buri,East,13.3611,100.9847
```

> หมายเหตุ (data entry, ไม่ใช่ logic): เติมอีก 67 จังหวัดด้วยพิกัด **อำเภอเมือง** จากแหล่งมาตรฐาน (เช่น simplemaps Thailand / GADM). ครบ 77 ก่อนรัน `build_dataset.py` จริง — แต่ test/โค้ดทำงานได้กับจำนวนเท่าใดก็ได้

- [ ] **Step 2: เขียน test ที่ fail**

```python
# tests/test_provinces.py
from src.provinces import load_provinces

def test_load_provinces_has_required_columns():
    df = load_provinces("data/provinces.csv")
    assert {"id", "name_th", "lat", "lon"}.issubset(df.columns)
    assert len(df) >= 10
    assert df["lat"].between(5, 21).all()      # ไทยอยู่ ~5–21°N
    assert df["lon"].between(97, 106).all()    # ~97–106°E
```

- [ ] **Step 3: รัน test ให้ fail**

Run: `python -m pytest tests/test_provinces.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'src.provinces'`

- [ ] **Step 4: เขียน `src/provinces.py`**

```python
# src/provinces.py
import pandas as pd

def load_provinces(path: str = "data/provinces.csv") -> pd.DataFrame:
    df = pd.read_csv(path)
    required = {"id", "code", "name_th", "name_en", "region", "lat", "lon"}
    missing = required - set(df.columns)
    if missing:
        raise ValueError(f"provinces.csv missing columns: {missing}")
    return df
```

- [ ] **Step 5: รัน test ให้ผ่าน**

Run: `python -m pytest tests/test_provinces.py -v`
Expected: PASS

- [ ] **Step 6: Commit**

```bash
git add data/provinces.csv src/provinces.py tests/test_provinces.py
git commit -m "feat(phase1): province centroid seed + loader"
```

---

### Task 2: sWBGT computation

**Files:**
- Create: `src/swbgt.py`
- Test: `tests/test_swbgt.py`

- [ ] **Step 1: เขียน test ที่ fail**

```python
# tests/test_swbgt.py
import numpy as np
from src.swbgt import vapor_pressure_hpa, swbgt

def test_vapor_pressure_at_30c_50rh():
    # e = 0.5 * 6.105 * exp(17.27*30/(237.7+30)) ≈ 21.2 hPa
    assert abs(vapor_pressure_hpa(30.0, 50.0) - 21.2) < 0.5

def test_swbgt_hot_humid_higher_than_hot_dry():
    hot_humid = swbgt(35.0, 70.0)
    hot_dry   = swbgt(35.0, 20.0)
    assert hot_humid > hot_dry          # ความชื้นสูง → sWBGT สูงกว่า

def test_swbgt_vectorized():
    ta = np.array([30.0, 35.0]); rh = np.array([50.0, 70.0])
    out = swbgt(ta, rh)
    assert out.shape == (2,)
    assert (out > ta - 5).all()          # sanity
```

- [ ] **Step 2: รัน test ให้ fail**

Run: `python -m pytest tests/test_swbgt.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'src.swbgt'`

- [ ] **Step 3: เขียน `src/swbgt.py`**

```python
# src/swbgt.py
"""Simplified shade WBGT (Australian BoM). NOT full ISO 7243 WBGT (no globe temp)."""
import numpy as np

def vapor_pressure_hpa(ta_c, rh_pct):
    """Water vapor pressure (hPa) from air temp (°C) and RH (%)."""
    ta = np.asarray(ta_c, dtype=float)
    rh = np.asarray(rh_pct, dtype=float)
    return (rh / 100.0) * 6.105 * np.exp(17.27 * ta / (237.7 + ta))

def swbgt(ta_c, rh_pct):
    """Simplified shade WBGT (°C)."""
    ta = np.asarray(ta_c, dtype=float)
    e = vapor_pressure_hpa(ta, rh_pct)
    return 0.567 * ta + 0.393 * e + 3.94
```

- [ ] **Step 4: รัน test ให้ผ่าน**

Run: `python -m pytest tests/test_swbgt.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add src/swbgt.py tests/test_swbgt.py
git commit -m "feat(phase1): sWBGT (simplified shade WBGT) computation"
```

---

### Task 3: Open-Meteo client (history)

**Files:**
- Create: `src/openmeteo_client.py`
- Test: `tests/test_openmeteo_client.py`

- [ ] **Step 1: เขียน test ที่ fail (mock network ด้วย monkeypatch)**

```python
# tests/test_openmeteo_client.py
import pandas as pd
from src import openmeteo_client as om

FAKE = {
    "daily": {
        "time": ["2020-01-01", "2020-01-02"],
        "temperature_2m_max": [33.0, 34.0],
        "temperature_2m_min": [22.0, 23.0],
        "relative_humidity_2m_mean": [55.0, 60.0],
    }
}

def test_fetch_history_returns_dataframe(monkeypatch):
    def fake_get(url, params=None, timeout=None):
        class R:
            status_code = 200
            def raise_for_status(self): pass
            def json(self): return FAKE
        return R()
    monkeypatch.setattr(om.requests, "get", fake_get)

    df = om.fetch_history(13.75, 100.50, "2020-01-01", "2020-01-02")
    assert isinstance(df, pd.DataFrame)
    assert list(df["time"]) == [pd.Timestamp("2020-01-01"), pd.Timestamp("2020-01-02")]
    assert "temperature_2m_max" in df.columns
    assert len(df) == 2
```

- [ ] **Step 2: รัน test ให้ fail**

Run: `python -m pytest tests/test_openmeteo_client.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'src.openmeteo_client'`

- [ ] **Step 3: เขียน `src/openmeteo_client.py`**

```python
# src/openmeteo_client.py
"""Open-Meteo client (no API key). History for training, forecast for inference."""
import pandas as pd
import requests

ARCHIVE_URL = "https://archive-api.open-meteo.com/v1/archive"
FORECAST_URL = "https://api.open-meteo.com/v1/forecast"

DAILY_VARS = [
    "temperature_2m_max", "temperature_2m_min", "temperature_2m_mean",
    "relative_humidity_2m_mean", "wind_speed_10m_max",
    "shortwave_radiation_sum", "surface_pressure_mean",
]

def _daily_to_df(payload: dict) -> pd.DataFrame:
    daily = payload["daily"]
    df = pd.DataFrame(daily)
    df["time"] = pd.to_datetime(df["time"])
    return df

def fetch_history(lat: float, lon: float, start: str, end: str) -> pd.DataFrame:
    params = {
        "latitude": lat, "longitude": lon,
        "start_date": start, "end_date": end,
        "daily": ",".join(DAILY_VARS),
        "timezone": "Asia/Bangkok",
    }
    r = requests.get(ARCHIVE_URL, params=params, timeout=60)
    r.raise_for_status()
    return _daily_to_df(r.json())

def fetch_forecast(lat: float, lon: float, days: int = 16) -> pd.DataFrame:
    params = {
        "latitude": lat, "longitude": lon,
        "daily": ",".join(DAILY_VARS),
        "forecast_days": days,
        "timezone": "Asia/Bangkok",
    }
    r = requests.get(FORECAST_URL, params=params, timeout=60)
    r.raise_for_status()
    return _daily_to_df(r.json())
```

> หมายเหตุ: ชื่อตัวแปร daily ของ Open-Meteo อาจต่างเล็กน้อย — ยืนยันกับเอกสาร https://open-meteo.com/en/docs/historical-weather-api ตอนรันจริง (test ใช้ mock จึงไม่กระทบ)

- [ ] **Step 4: รัน test ให้ผ่าน**

Run: `python -m pytest tests/test_openmeteo_client.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add src/openmeteo_client.py tests/test_openmeteo_client.py
git commit -m "feat(phase1): Open-Meteo history/forecast client"
```

---

### Task 4: Day-of-year windowed percentiles (climatology)

**Files:**
- Create: `src/climatology.py`
- Test: `tests/test_climatology.py`

- [ ] **Step 1: เขียน test ที่ fail**

```python
# tests/test_climatology.py
import numpy as np
import pandas as pd
from src.climatology import compute_doy_percentiles

def test_percentiles_per_doy_window():
    rng = pd.date_range("1991-01-01", "2020-12-31", freq="D")
    # ค่า sWBGT จำลอง: ฐาน 28 + รายปีคงที่
    np.random.seed(0)
    df = pd.DataFrame({"time": rng, "swbgt_max": 28 + np.random.normal(0, 2, len(rng))})
    out = compute_doy_percentiles(df, value_col="swbgt_max", window=7,
                                  baseline=(1991, 2020))
    assert {"doy", "p90", "p95", "p975"}.issubset(out.columns)
    assert len(out) == 366                       # ครบทุก doy รวม 29 ก.พ.
    assert (out["p975"] >= out["p95"]).all()
    assert (out["p95"]  >= out["p90"]).all()
```

- [ ] **Step 2: รัน test ให้ fail**

Run: `python -m pytest tests/test_climatology.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'src.climatology'`

- [ ] **Step 3: เขียน `src/climatology.py`**

```python
# src/climatology.py
"""Per-location day-of-year windowed percentiles over a WMO baseline."""
import numpy as np
import pandas as pd

def compute_doy_percentiles(df: pd.DataFrame, value_col: str = "swbgt_max",
                            window: int = 7, baseline=(1991, 2020)) -> pd.DataFrame:
    d = df.copy()
    d["time"] = pd.to_datetime(d["time"])
    d = d[(d["time"].dt.year >= baseline[0]) & (d["time"].dt.year <= baseline[1])]
    d["doy"] = d["time"].dt.dayofyear

    rows = []
    for doy in range(1, 367):
        lo, hi = doy - window, doy + window
        # หน้าต่างแบบวน (wrap) รอบปลายปี
        mask = d["doy"].apply(lambda x: _within_circular(x, lo, hi, 366))
        vals = d.loc[mask, value_col].dropna()
        if len(vals) == 0:
            continue
        rows.append({
            "doy": doy,
            "p90": float(np.percentile(vals, 90)),
            "p95": float(np.percentile(vals, 95)),
            "p975": float(np.percentile(vals, 97.5)),
        })
    return pd.DataFrame(rows)

def _within_circular(x, lo, hi, period):
    if lo < 1:
        return x >= lo + period or x <= hi
    if hi > period:
        return x >= lo or x <= hi - period
    return lo <= x <= hi
```

- [ ] **Step 4: รัน test ให้ผ่าน**

Run: `python -m pytest tests/test_climatology.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add src/climatology.py tests/test_climatology.py
git commit -m "feat(phase1): day-of-year windowed climatology percentiles"
```

---

### Task 5: Heatwave label with persistence

**Files:**
- Create: `src/labels.py`
- Test: `tests/test_labels.py`

- [ ] **Step 1: เขียน test ที่ fail**

```python
# tests/test_labels.py
import pandas as pd
from src.labels import label_heatwave

def test_isolated_hot_day_not_heatwave():
    # threshold p95 = 30 ทุก doy; วันร้อนเดี่ยว ๆ ไม่นับ heatwave
    df = pd.DataFrame({
        "time": pd.to_datetime(["2024-04-01","2024-04-02","2024-04-03"]),
        "swbgt_max": [31, 25, 31],   # ร้อน-เย็น-ร้อน (ไม่ต่อเนื่อง)
    })
    thr = pd.DataFrame({"doy": range(1,367), "p95": [30]*366})
    out = label_heatwave(df, thr, value_col="swbgt_max", min_run=2)
    assert out["heatwave"].tolist() == [0, 0, 0]

def test_run_of_two_is_heatwave():
    df = pd.DataFrame({
        "time": pd.to_datetime(["2024-04-01","2024-04-02","2024-04-03"]),
        "swbgt_max": [31, 31, 25],   # ร้อนติดกัน 2 วัน
    })
    thr = pd.DataFrame({"doy": range(1,367), "p95": [30]*366})
    out = label_heatwave(df, thr, value_col="swbgt_max", min_run=2)
    assert out["heatwave"].tolist() == [1, 1, 0]
```

- [ ] **Step 2: รัน test ให้ fail**

Run: `python -m pytest tests/test_labels.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'src.labels'`

- [ ] **Step 3: เขียน `src/labels.py`**

```python
# src/labels.py
"""Region-specific percentile + persistence heatwave label."""
import pandas as pd

def label_heatwave(df: pd.DataFrame, thresholds: pd.DataFrame,
                   value_col: str = "swbgt_max", min_run: int = 2) -> pd.DataFrame:
    d = df.copy()
    d["time"] = pd.to_datetime(d["time"])
    d["doy"] = d["time"].dt.dayofyear
    d = d.merge(thresholds[["doy", "p95"]], on="doy", how="left")
    d["is_hot"] = (d[value_col] >= d["p95"]).astype(int)

    # persistence: hot day นับเป็น heatwave ก็ต่อเมื่ออยู่ใน run ยาว >= min_run
    d = d.sort_values("time").reset_index(drop=True)
    grp = (d["is_hot"] != d["is_hot"].shift()).cumsum()
    run_len = d.groupby(grp)["is_hot"].transform("size")
    d["heatwave"] = ((d["is_hot"] == 1) & (run_len >= min_run)).astype(int)
    return d.drop(columns=["doy"])
```

- [ ] **Step 4: รัน test ให้ผ่าน**

Run: `python -m pytest tests/test_labels.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add src/labels.py tests/test_labels.py
git commit -m "feat(phase1): percentile+persistence heatwave label"
```

---

### Task 6: Temporal split (แก้ leakage ใน preprocessing)

**Files:**
- Create: `src/splits.py`
- Test: `tests/test_splits.py`
- Modify: `src/preprocessing.py` (ทำให้ default ไม่ใช่ random split)

- [ ] **Step 1: เขียน test ที่ fail**

```python
# tests/test_splits.py
import pandas as pd
from src.splits import temporal_split

def test_temporal_split_no_year_overlap():
    df = pd.DataFrame({
        "time": pd.to_datetime(
            ["2022-06-01","2023-06-01","2024-06-01","2025-06-01"]),
        "x": [1,2,3,4],
    })
    tr, va, te = temporal_split(df, train_end=2023, val_year=2024, test_year=2025)
    assert tr["time"].dt.year.max() <= 2023
    assert (va["time"].dt.year == 2024).all()
    assert (te["time"].dt.year == 2025).all()
    # ไม่มีปีซ้ำข้าม split
    assert set(tr["time"].dt.year) & set(va["time"].dt.year) == set()
    assert set(va["time"].dt.year) & set(te["time"].dt.year) == set()
```

- [ ] **Step 2: รัน test ให้ fail**

Run: `python -m pytest tests/test_splits.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'src.splits'`

- [ ] **Step 3: เขียน `src/splits.py`**

```python
# src/splits.py
"""Temporal (year-based) split — replaces random stratified split to kill temporal leakage."""
import pandas as pd

def temporal_split(df: pd.DataFrame, time_col: str = "time",
                   train_end: int = 2023, val_year: int = 2024, test_year: int = 2025):
    d = df.copy()
    d[time_col] = pd.to_datetime(d[time_col])
    y = d[time_col].dt.year
    train = d[y <= train_end]
    val   = d[y == val_year]
    test  = d[y == test_year]
    return train, val, test
```

- [ ] **Step 4: รัน test ให้ผ่าน**

Run: `python -m pytest tests/test_splits.py -v`
Expected: PASS

- [ ] **Step 5: ชี้ `src/preprocessing.py` มาใช้ temporal split (กัน random split เผลอถูกเรียก)**

ใน `src/preprocessing.py` ที่ฟังก์ชัน `fit_transform`, แทนบล็อกที่เรียก `train_test_split(...)` ด้วยการ raise เพื่อบังคับใช้ temporal split:

```python
# src/preprocessing.py — แทนที่ส่วน random split เดิม
from src.splits import temporal_split  # ใช้ temporal split เท่านั้น

# เดิม: train_test_split(X, y, test_size=..., stratify=...)
# ใหม่: ห้าม random split — บังคับ pipeline ใหม่ผ่าน build_dataset.py
raise NotImplementedError(
    "Random split removed (temporal leakage). Use src.splits.temporal_split via "
    "pipeline/build_dataset.py. See docs/superpowers/specs/2026-05-30-region-thresholds-line-oa-design.md §4.5"
)
```

- [ ] **Step 6: รัน test ทั้งหมดให้ผ่าน**

Run: `python -m pytest tests/ -v`
Expected: PASS (test เดิมของ preprocessing ที่พึ่ง random split อาจต้องปรับ/skip — ระบุเหตุผลใน commit)

- [ ] **Step 7: Commit**

```bash
git add src/splits.py tests/test_splits.py src/preprocessing.py
git commit -m "feat(phase1): temporal split; disable random split (fixes temporal leakage)"
```

---

### Task 7: Orchestration — build_dataset.py

**Files:**
- Create: `pipeline/__init__.py`
- Create: `pipeline/build_dataset.py`
- Test: `tests/test_build_dataset.py`

- [ ] **Step 1: เขียน test ที่ fail (mock fetch, 1 จังหวัด)**

```python
# tests/test_build_dataset.py
import numpy as np
import pandas as pd
from pipeline import build_dataset as bd

def test_build_one_province(monkeypatch, tmp_path):
    rng = pd.date_range("1991-01-01", "2025-12-31", freq="D")
    np.random.seed(1)
    fake = pd.DataFrame({
        "time": rng,
        "temperature_2m_max": 33 + np.random.normal(0, 3, len(rng)),
        "relative_humidity_2m_mean": 60 + np.random.normal(0, 10, len(rng)),
    })
    monkeypatch.setattr(bd.openmeteo_client, "fetch_history",
                        lambda lat, lon, s, e: fake.copy())

    prov = pd.DataFrame([{"id":1,"code":"BKK","name_th":"กทม","name_en":"Bangkok",
                          "region":"Central","lat":13.75,"lon":100.5}])
    ds, thr = bd.build_for_provinces(prov, start="1991-01-01", end="2025-12-31")
    assert {"province_id","time","swbgt_max","heatwave"}.issubset(ds.columns)
    assert {"province_id","doy","p95"}.issubset(thr.columns)
    assert ds["heatwave"].isin([0,1]).all()
    assert 0 < ds["heatwave"].mean() < 0.3        # rate สมเหตุสมผล
```

- [ ] **Step 2: รัน test ให้ fail**

Run: `python -m pytest tests/test_build_dataset.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'pipeline'`

- [ ] **Step 3: เขียน `pipeline/build_dataset.py`**

```python
# pipeline/build_dataset.py
"""Build training dataset + per-province thresholds from Open-Meteo."""
import os
import pandas as pd
from src import openmeteo_client
from src.swbgt import swbgt
from src.climatology import compute_doy_percentiles
from src.labels import label_heatwave
from src.provinces import load_provinces

def build_for_provinces(provinces: pd.DataFrame, start: str, end: str):
    all_rows, all_thr = [], []
    for _, p in provinces.iterrows():
        raw = openmeteo_client.fetch_history(p["lat"], p["lon"], start, end)
        raw["swbgt_max"] = swbgt(raw["temperature_2m_max"],
                                 raw["relative_humidity_2m_mean"])
        thr = compute_doy_percentiles(raw, value_col="swbgt_max",
                                      window=7, baseline=(1991, 2020))
        labeled = label_heatwave(raw, thr, value_col="swbgt_max", min_run=2)
        labeled["province_id"] = p["id"]
        thr["province_id"] = p["id"]
        all_rows.append(labeled)
        all_thr.append(thr)
    return pd.concat(all_rows, ignore_index=True), pd.concat(all_thr, ignore_index=True)

def main():
    provinces = load_provinces("data/provinces.csv")
    ds, thr = build_for_provinces(provinces, "1991-01-01", "2025-12-31")
    os.makedirs("data/processed", exist_ok=True)
    ds.to_parquet("data/processed/dataset.parquet", index=False)
    thr.to_parquet("data/processed/province_thresholds.parquet", index=False)
    print(f"dataset rows={len(ds)} provinces={ds['province_id'].nunique()} "
          f"heatwave_rate={ds['heatwave'].mean():.4f}")

if __name__ == "__main__":
    main()
```

- [ ] **Step 4: รัน test ให้ผ่าน**

Run: `python -m pytest tests/test_build_dataset.py -v`
Expected: PASS

- [ ] **Step 5: รัน test ทั้งชุด + commit**

Run: `python -m pytest tests/ -v`
Expected: PASS ทั้งหมด

```bash
git add pipeline/ tests/test_build_dataset.py
git commit -m "feat(phase1): build_dataset orchestration (Open-Meteo -> sWBGT -> labels)"
```

- [ ] **Step 6: (ทำจริง เมื่อ provinces.csv ครบ 77) รัน pipeline จริง**

Run: `python -m pipeline.build_dataset`
Expected: พิมพ์ `dataset rows=... provinces=77 heatwave_rate=0.0X` และได้ไฟล์ใน `data/processed/`
> ถ้า rate ผิดปกติ (0% หรือ >30%) ให้ตรวจ threshold/persistence ก่อนไปเฟส 2

---

## Self-Review (เทียบ spec §4)

- ✅ Open-Meteo ingest → Task 3
- ✅ sWBGT → Task 2
- ✅ percentile รายจังหวัด (doy-windowed, baseline 1991–2020) → Task 4
- ✅ label percentile + persistence ≥2 วัน → Task 5
- ✅ temporal split + ลบ random split → Task 6
- ✅ orchestration + persist thresholds → Task 7
- ✅ Acceptance (label rate สมเหตุสมผล, ไม่มี feature ที่นิยาม label อยู่ในชุด train) → ตรวจที่ Task 7 Step 6 + เฟส 2 จะคุม feature list

**หมายเหตุ leakage:** `swbgt_max` ของ "วันเป้าหมาย" คือฐานของ label — ในเฟส 2 ห้ามใช้เป็น feature; ใช้เฉพาะ lagged/anomaly ของอดีต (ดู spec §5.2)

**ที่เก็บลง Supabase** ของ `province_thresholds` ทำในเฟส 3 (เฟส 1 เก็บเป็น parquet ก่อน)
