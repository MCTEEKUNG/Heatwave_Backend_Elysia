# pipeline/build_ndvi.py
"""Build the NDVI cache from Google Earth Engine (run once you have GEE auth).

Prerequisites:
  pip install earthengine-api
  earthengine authenticate          # interactive, once
  export GEE_PROJECT=<your-gee-project>   # e.g. gen-lang-client-0381821743

Then:
  python -m pipeline.build_ndvi     # writes data/processed/ndvi.csv

Range comes from OPENMETEO_START_YEAR / OPENMETEO_END_YEAR (defaults match
build_dataset). After this, build_dataset/train pick up the `ndvi` feature.
"""
import os

from src.provinces import load_provinces
from src.gee_ndvi import build_ndvi_cache


def main():
    start_year = int(os.environ.get("OPENMETEO_START_YEAR", "2010"))
    end_year = int(os.environ.get("OPENMETEO_END_YEAR", "2025"))
    provinces = load_provinces("data/provinces.csv")
    print(f"Fetching MODIS NDVI for {len(provinces)} provinces, "
          f"{start_year}-{end_year} from Google Earth Engine ...")
    df = build_ndvi_cache(provinces, f"{start_year}-01-01", f"{end_year}-12-31")
    print(f"NDVI cache: {len(df)} province-months, "
          f"provinces={df['province_id'].nunique()}, "
          f"ndvi {df['ndvi'].min():.3f}..{df['ndvi'].max():.3f}")


if __name__ == "__main__":
    main()
