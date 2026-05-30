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
