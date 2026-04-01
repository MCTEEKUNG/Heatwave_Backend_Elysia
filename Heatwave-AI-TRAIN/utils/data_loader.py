"""
utils/data_loader.py
Loads ERA5 NetCDF surface and upper files and returns a flat pandas DataFrame.
"""

import os
import glob
import yaml
import logging
import numpy as np
import pandas as pd
import xarray as xr
from tqdm import tqdm

logging.basicConfig(
    level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s"
)
logger = logging.getLogger(__name__)


class ERA5DataLoader:
    """Loads ERA5 surface and upper NetCDF files and converts them to a DataFrame."""

    def __init__(self, config_path: str = "config/config.yaml"):
        with open(config_path, "r", encoding="utf-8") as f:
            self.cfg = yaml.safe_load(f)

        self.raw_dir = self.cfg["data"]["raw_dir"]
        self.years = self.cfg["data"]["years"]
        self.surface_prefix = self.cfg["data"]["surface_prefix"]
        self.upper_prefix = self.cfg["data"].get("upper_prefix", "era5_upper_")
        self.features = self.cfg["data"]["features"]
        self.threshold_c = self.cfg["data"]["heatwave_threshold_celsius"]

    # ------------------------------------------------------------------
    def load(self) -> pd.DataFrame:
        """Load all surface and upper files matching configured years, return DataFrame."""
        all_frames = []

        for year in tqdm(self.years, desc="Loading ERA5 years"):
            surface_fname = os.path.join(
                self.raw_dir, f"{self.surface_prefix}{year}.nc"
            )
            upper_fname = os.path.join(self.raw_dir, f"{self.upper_prefix}{year}.nc")

            surface_ds = None
            upper_ds = None

            if os.path.isfile(surface_fname):
                try:
                    surface_ds = xr.open_dataset(surface_fname, engine="netcdf4")
                except Exception as e:
                    logger.error("Error reading surface file %s: %s", surface_fname, e)

            if os.path.isfile(upper_fname):
                try:
                    upper_ds = xr.open_dataset(upper_fname, engine="netcdf4")
                except Exception as e:
                    logger.error("Error reading upper file %s: %s", upper_fname, e)

            if surface_ds is None and upper_ds is None:
                logger.warning("No data files found for year %d, skipping", year)
                continue

            try:
                df = self._merge_datasets(surface_ds, upper_ds, year)
                all_frames.append(df)
            except Exception as e:
                logger.error("Error merging datasets for year %d: %s", year, e)
            finally:
                if surface_ds:
                    surface_ds.close()
                if upper_ds:
                    upper_ds.close()

        if not all_frames:
            raise RuntimeError(
                "No ERA5 data files could be loaded. Check raw_dir in config."
            )

        full_df = pd.concat(all_frames, ignore_index=True)
        logger.info(
            "Loaded %d total samples across %d years", len(full_df), len(self.years)
        )
        return full_df

    # ------------------------------------------------------------------
    def _merge_datasets(
        self, surface_ds: xr.Dataset, upper_ds: xr.Dataset, year: int
    ) -> pd.DataFrame:
        """
        Merge surface and upper xarray Datasets and convert to flat DataFrame.
        """
        if surface_ds is not None and upper_ds is not None:
            common_vars = set(surface_ds.data_vars) & set(upper_ds.data_vars)
            upper_vars = set(upper_ds.data_vars) - common_vars
            combined_vars = list(surface_ds.data_vars) + list(upper_vars)
            ds = xr.merge([surface_ds, upper_ds], compat="no_conflicts")
        elif surface_ds is not None:
            ds = surface_ds
        else:
            ds = upper_ds

        return self._dataset_to_df(ds, year)

    # ------------------------------------------------------------------
    def _dataset_to_df(self, ds: xr.Dataset, year: int) -> pd.DataFrame:
        """
        Convert an xarray Dataset to a flat DataFrame row per (time, lat, lon).
        Includes time, latitude, and longitude coordinates.
        """
        available_vars = list(ds.data_vars)
        load_vars = [v for v in self.features if v in available_vars]

        df = ds[load_vars].to_dataframe().reset_index()

        rename_map = {
            "valid_time": "time",
            "lat": "latitude",
            "lon": "longitude",
            "y": "latitude",
            "x": "longitude",
        }
        df = df.rename(columns={k: v for k, v in rename_map.items() if k in df.columns})

        drop_cols = ["number", "expver"]
        df = df.drop(columns=[c for c in drop_cols if c in df.columns], errors="ignore")

        df["year"] = year

        for var in self.features:
            if var not in df.columns:
                df[var] = np.nan

        return df


# ------------------------------------------------------------------
def load_data(config_path: str = "config/config.yaml") -> pd.DataFrame:
    """Convenience function used by the pipeline."""
    loader = ERA5DataLoader(config_path)
    return loader.load()


if __name__ == "__main__":
    df = load_data()
    print(f"Shape: {df.shape}")
    print(df.head())
