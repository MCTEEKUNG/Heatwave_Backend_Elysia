"""
import_data.py
Import and verify all ERA5 and NDVI data for training.

Usage:
    python import_data.py
"""

import os
import sys
import yaml
import xarray as xr
from pathlib import Path

ROOT = os.path.dirname(os.path.abspath(__file__))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from utils.data_loader import ERA5DataLoader
from utils.ndvi_processor import NDVIProcessor


def check_era5_data(config_path: str = "config/config.yaml"):
    print("\n" + "=" * 60)
    print("  ERA5 Data Check")
    print("=" * 60)

    with open(config_path, "r", encoding="utf-8") as f:
        cfg = yaml.safe_load(f)

    raw_dir = cfg["data"]["raw_dir"]
    surface_prefix = cfg["data"]["surface_prefix"]
    upper_prefix = cfg["data"].get("upper_prefix", "era5_upper_")
    years = cfg["data"]["years"]

    surface_files = []
    upper_files = []

    for year in years:
        sf = os.path.join(raw_dir, f"{surface_prefix}{year}.nc")
        uf = os.path.join(raw_dir, f"{upper_prefix}{year}.nc")

        if os.path.isfile(sf):
            surface_files.append(sf)
        if os.path.isfile(uf):
            upper_files.append(uf)

    print(f"\n  Surface files : {len(surface_files)}/{len(years)}")
    print(f"  Upper files   : {len(upper_files)}/{len(years)}")

    if surface_files:
        ds = xr.open_dataset(surface_files[0], engine="netcdf4")
        print(f"\n  Sample surface file: {os.path.basename(surface_files[0])}")
        print(f"  Variables: {list(ds.data_vars)}")
        print(f"  Dimensions: {dict(ds.dims)}")
        ds.close()

    if upper_files:
        ds = xr.open_dataset(upper_files[0], engine="netcdf4")
        print(f"\n  Sample upper file: {os.path.basename(upper_files[0])}")
        print(f"  Variables: {list(ds.data_vars)}")
        print(f"  Dimensions: {dict(ds.dims)}")
        ds.close()

    return len(surface_files) > 0


def check_ndvi_data(config_path: str = "config/config.yaml"):
    print("\n" + "=" * 60)
    print("  NDVI Data Check")
    print("=" * 60)

    with open(config_path, "r", encoding="utf-8") as f:
        cfg = yaml.safe_load(f)

    ndvi_dir = cfg["ndvi"]["output_dir"]
    processed_file = cfg["ndvi"]["processed_file"]

    tif_files = list(Path(ndvi_dir).glob("*.tif"))
    print(f"\n  NDVI directory: {ndvi_dir}")
    print(f"  TIF files found: {len(tif_files)}")

    if os.path.isfile(processed_file):
        ds = xr.open_dataset(processed_file)
        print(f"\n  Processed NDVI file exists: {processed_file}")
        print(f"  Variables: {list(ds.data_vars)}")
        print(f"  Dimensions: {dict(ds.dims)}")
        ds.close()
        return True
    else:
        print(f"\n  Processed NDVI file not found: {processed_file}")
        if tif_files:
            print("  Running NDVI processor to create aligned file...")
            try:
                processor = NDVIProcessor(cfg)
                ds = processor.run()
                print(f"  NDVI processing complete. Shape: {dict(ds.dims)}")
                return True
            except Exception as e:
                print(f"  NDVI processing failed: {e}")
                return False
        return False


def test_data_loading(config_path: str = "config/config.yaml"):
    print("\n" + "=" * 60)
    print("  Data Loading Test")
    print("=" * 60)

    try:
        loader = ERA5DataLoader(config_path)
        df = loader.load()
        print(f"\n  Loaded DataFrame shape: {df.shape}")
        print(f"  Columns: {list(df.columns)}")
        print(f"\n  Sample rows:")
        print(df.head())
        return True
    except Exception as e:
        print(f"\n  Data loading failed: {e}")
        return False


def main():
    print("\n" + "=" * 60)
    print("  HEATWAVE-AI | Data Import & Verification")
    print("=" * 60)

    config_path = "config/config.yaml"

    era5_ok = check_era5_data(config_path)
    ndvi_ok = check_ndvi_data(config_path)
    loading_ok = test_data_loading(config_path) if era5_ok else False

    print("\n" + "=" * 60)
    print("  Summary")
    print("=" * 60)
    print(f"  ERA5 data  : {'OK' if era5_ok else 'MISSING'}")
    print(f"  NDVI data  : {'OK' if ndvi_ok else 'MISSING'}")
    print(f"  Loading    : {'OK' if loading_ok else 'FAILED'}")

    if era5_ok and loading_ok:
        print("\n  Data is ready for training!")
        print("  Run: python main.py --mode train")
    else:
        print("\n  Data setup incomplete. Check paths in config/config.yaml")


if __name__ == "__main__":
    main()
