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
