# pipeline/build_geopotential.py
"""Build the 500 hPa geopotential cache from the Copernicus CDS (run once).

Prerequisites:
  pip install cdsapi xarray netcdf4
  configure ~/.cdsapirc with your CDS key (https://cds.climate.copernicus.eu/how-to-api)

Then:
  python -m pipeline.build_geopotential   # writes data/processed/geopotential.csv

Range via OPENMETEO_START_YEAR / OPENMETEO_END_YEAR (defaults match build_dataset).
CDS requests are queued server-side and may take a few minutes. After this,
build_dataset/train pick up the `hpa500` feature automatically.
"""
import os

from src.provinces import load_provinces
from src.cds_geopotential import build_geopotential_cache


def main():
    start_year = int(os.environ.get("OPENMETEO_START_YEAR", "2010"))
    end_year = int(os.environ.get("OPENMETEO_END_YEAR", "2025"))
    provinces = load_provinces("data/provinces.csv")
    print(f"Downloading ERA5 500 hPa geopotential {start_year}-{end_year} from "
          f"CDS for {len(provinces)} provinces (this can take a few minutes) ...")
    df = build_geopotential_cache(provinces, start_year, end_year)
    print(f"geopotential cache: {len(df)} province-months, "
          f"provinces={df['province_id'].nunique()}, "
          f"height {df['hpa500'].min():.0f}..{df['hpa500'].max():.0f} m")


if __name__ == "__main__":
    main()
