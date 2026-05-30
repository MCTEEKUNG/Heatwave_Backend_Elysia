# pipeline/frame_cache.py
"""Cache the (expensive) forecasting frame keyed by dataset signature + horizons.

The frame is a pure function of dataset.parquet content + horizons, so we key on
a cheap signature (file size + mtime_ns + horizons) -- rebuilding the dataset
changes mtime and invalidates the cache automatically.
"""
import hashlib
import os

import pandas as pd

from pipeline.train import build_frames

DEFAULT_CACHE_DIR = "data/processed/_frame_cache"


def frame_cache_key(dataset_path: str, horizons) -> str:
    st = os.stat(dataset_path)
    sig = f"{os.path.abspath(dataset_path)}|{st.st_size}|{st.st_mtime_ns}|{tuple(horizons)}"
    return hashlib.sha1(sig.encode()).hexdigest()[:16]


def cached_build_frames(dataset_path: str, horizons=range(1, 8),
                        cache_dir: str = DEFAULT_CACHE_DIR) -> pd.DataFrame:
    os.makedirs(cache_dir, exist_ok=True)
    path = os.path.join(cache_dir, f"{frame_cache_key(dataset_path, horizons)}.parquet")
    if os.path.exists(path):
        return pd.read_parquet(path)
    ds = pd.read_parquet(dataset_path)
    if "lat" not in ds.columns:
        prov = pd.read_csv("data/provinces.csv")[["id", "lat", "lon"]]
        ds = ds.merge(prov, left_on="province_id", right_on="id", how="left").drop(columns=["id"])
    frame = build_frames(ds, horizons=horizons)
    frame.to_parquet(path, index=False)
    return frame
