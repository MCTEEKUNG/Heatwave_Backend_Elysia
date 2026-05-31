# src/gee_ndvi.py
"""MODIS NDVI (vegetation index) per province from Google Earth Engine.

NDVI captures the vegetation / urbanization state — urban growth lowers NDVI and
strengthens the urban-heat signal — a research-backed land-surface modulator of
heatwaves and a key differentiator for this project.

Auth (needs `earthengine-api` + a Google Earth Engine project):
  * Interactive / local: run ``earthengine authenticate`` once, then set GEE_PROJECT.
  * Headless / CI: set GEE_SERVICE_ACCOUNT (email) + GEE_SERVICE_ACCOUNT_JSON
    (path to, or contents of, the service-account key) and GEE_PROJECT.

NDVI is fetched MONTHLY (MOD13A3) and attached as the PREVIOUS month's value
(lag-1, so it is always known at time t — no look-ahead leakage).
"""
import os

import pandas as pd

COLLECTION = "MODIS/061/MOD13A3"   # monthly NDVI, ~1 km
NDVI_SCALE = 0.0001                # MODIS NDVI integer -> [-1, 1]
CACHE_PATH = "data/processed/ndvi.csv"


def init_ee(project: str = None):
    """Initialize Earth Engine from env (service account if provided, else OAuth)."""
    import ee
    project = project or os.environ.get("GEE_PROJECT")
    sa_json = os.environ.get("GEE_SERVICE_ACCOUNT_JSON")
    if sa_json:
        email = os.environ.get("GEE_SERVICE_ACCOUNT")
        if os.path.isfile(sa_json):
            creds = ee.ServiceAccountCredentials(email, key_file=sa_json)
        else:
            creds = ee.ServiceAccountCredentials(email, key_data=sa_json)
        ee.Initialize(creds, project=project)
    else:
        ee.Initialize(project=project)


def _parse_province_ndvi(features, province_id, scale: float = NDVI_SCALE):
    """Parse a getInfo() feature list -> NDVI rows (pure; unit-testable)."""
    rows = []
    for f in features:
        props = f.get("properties", {})
        if props.get("ndvi") is None:
            continue
        year, month = str(props["t"]).split("-")[:2]
        rows.append({
            "province_id": int(province_id),
            "year": int(year),
            "month": int(month),
            "ndvi": float(props["ndvi"]) * scale,
        })
    return rows


def fetch_ndvi(provinces, start, end, collection: str = COLLECTION,
               buffer_m: int = 5000) -> pd.DataFrame:
    """Monthly NDVI per province -> DataFrame[province_id, year, month, ndvi].

    One Earth Engine round-trip per province (reduceRegion mapped over the monthly
    collection at the province centroid + buffer).
    """
    import ee
    col = ee.ImageCollection(collection).select("NDVI").filterDate(start, end)
    rows = []
    for _, p in provinces.iterrows():
        pt = ee.Geometry.Point([float(p["lon"]), float(p["lat"])]).buffer(buffer_m)

        def _reduce(img):
            val = img.reduceRegion(ee.Reducer.mean(), pt, 1000).get("NDVI")
            return ee.Feature(None, {"t": img.date().format("YYYY-MM"), "ndvi": val})

        features = col.map(_reduce).getInfo()["features"]
        rows.extend(_parse_province_ndvi(features, p["id"]))
    df = pd.DataFrame(rows)
    if df.empty:
        raise RuntimeError("GEE NDVI: no data returned (check auth / date range)")
    return df


def build_ndvi_cache(provinces, start, end, cache_path: str = CACHE_PATH,
                     project: str = None) -> pd.DataFrame:
    """Authenticate, fetch NDVI for all provinces, and cache to CSV."""
    init_ee(project)
    df = fetch_ndvi(provinces, start, end)
    os.makedirs(os.path.dirname(cache_path) or ".", exist_ok=True)
    df.to_csv(cache_path, index=False)
    return df


def load_ndvi(cache_path: str = CACHE_PATH):
    """Load cached NDVI, or return None if it hasn't been built yet."""
    if os.path.isfile(cache_path):
        return pd.read_csv(cache_path)
    return None


def attach_ndvi(daily: pd.DataFrame, ndvi_df: pd.DataFrame,
                time_col: str = "time") -> pd.DataFrame:
    """Merge the PREVIOUS month's NDVI per province onto each daily row (lag-1)."""
    d = daily.copy()
    prev = pd.to_datetime(d[time_col]).dt.to_period("M") - 1
    d["_y"] = prev.dt.year
    d["_m"] = prev.dt.month
    e = ndvi_df.rename(columns={"year": "_y", "month": "_m"})
    d = d.merge(e[["province_id", "_y", "_m", "ndvi"]],
                on=["province_id", "_y", "_m"], how="left")
    return d.drop(columns=["_y", "_m"])
