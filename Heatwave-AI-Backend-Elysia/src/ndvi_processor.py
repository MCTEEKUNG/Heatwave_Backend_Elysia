"""
utils/ndvi_processor.py
Processes raw MODIS MOD13A3 GeoTIFF files downloaded from Google Earth Engine:
  1. Apply MODIS scale factor (× 0.0001) — raw integer → true NDVI float
  2. Reproject to WGS84 (EPSG:4326) — MODIS uses Sinusoidal projection
  3. Resample to ERA5 grid (bilinear interpolation, ~25 km)
  4. Fill cloud-masked NaN gaps (linear temporal interpolation + ffill/bfill)
  5. Create lag features: ndvi_lag1 (t-1 month), ndvi_lag2 (t-2 months)
  6. Save aligned dataset → data/ndvi/ndvi_aligned_era5.nc (~200 MB)

Usage:
    python utils/ndvi_processor.py

Prerequisites:
    1. GeoTIFF files in data/ndvi/ (downloaded via ndvi_downloader.py)
    2. ERA5 NetCDF for at least one year (used to read the target grid)
    3. pip install rioxarray>=0.15.0 rasterio>=1.3.0
"""
import logging
import os
import warnings
from pathlib import Path

import numpy as np
import xarray as xr
import yaml

logger = logging.getLogger(__name__)


class NDVIProcessor:
    """
    Processes raw MODIS GeoTIFF files and aligns them to the ERA5 grid.

    Config fields used (from config.yaml → ndvi block):
        output_dir, processed_file, fill_nodata_method, lag_months
    """

    # MODIS stores NDVI as integer × 10000; divide to get true float
    SCALE_FACTOR = 0.0001

    def __init__(self, config: dict):
        ndvi_cfg          = config.get("ndvi", {})
        data_cfg          = config.get("data", {})
        self.input_dir    = ndvi_cfg.get("output_dir",       "data/ndvi/")
        self.output_file  = ndvi_cfg.get("processed_file",   "data/ndvi/ndvi_aligned_era5.nc")
        self.lag_months   = ndvi_cfg.get("lag_months",       [0, 1, 2])
        self.fill_method  = ndvi_cfg.get("fill_nodata_method", "linear")
        self.era5_dir     = data_cfg.get("raw_dir",          "Era5-data-2000-2026")
        self.era5_prefix  = data_cfg.get("surface_prefix",   "era5_surface_")
        self.start_year   = ndvi_cfg.get("start_year",       2000)

        os.makedirs(os.path.dirname(self.output_file), exist_ok=True)

    # ------------------------------------------------------------------
    # Public entry point
    # ------------------------------------------------------------------

    def run(self) -> xr.Dataset:
        """
        Full processing pipeline.
        Loads all .tif files from input_dir, processes them, and saves
        the aligned + lag-enriched dataset to processed_file.
        Returns the processed xr.Dataset.
        """
        era5_ds = self._load_era5_reference()

        logger.info("[NDVIProcessor] Loading and scaling raw MODIS files...")
        ndvi = self._load_and_scale()

        logger.info("[NDVIProcessor] Reprojecting to WGS84...")
        ndvi = self._reproject(ndvi)

        logger.info("[NDVIProcessor] Resampling to ERA5 grid...")
        ndvi = self._resample_to_era5(ndvi, era5_ds)

        logger.info("[NDVIProcessor] Filling cloud-masked gaps...")
        ndvi = self._fill_gaps(ndvi)

        logger.info("[NDVIProcessor] Creating lag features...")
        ds = self._create_lag_features(ndvi)

        logger.info("[NDVIProcessor] Saving → %s", self.output_file)
        ds.to_netcdf(self.output_file)
        logger.info("[NDVIProcessor] Done. Dataset shape: %s", dict(ds.dims))
        return ds

    # ------------------------------------------------------------------
    # Processing steps
    # ------------------------------------------------------------------

    def _load_era5_reference(self) -> xr.Dataset:
        """Load one ERA5 file to determine the target lat/lon grid."""
        fname = os.path.join(self.era5_dir, f"{self.era5_prefix}{self.start_year}.nc")
        if not os.path.isfile(fname):
            raise FileNotFoundError(
                f"ERA5 reference file not found: {fname}. "
                "Adjust data.raw_dir or data.start_year in config.yaml."
            )
        ds = xr.open_dataset(fname, engine="netcdf4")
        logger.info("[NDVIProcessor] ERA5 reference loaded: %s", fname)
        return ds

    def _load_and_scale(self) -> xr.DataArray:
        """Load all .tif files, apply MODIS scale factor, mask out-of-range values."""
        try:
            import rioxarray  # noqa: F401 — side-effect import registers .rio accessor
        except ImportError as exc:
            raise ImportError(
                "rioxarray is not installed. Run: pip install rioxarray>=0.15.0"
            ) from exc

        files = sorted(Path(self.input_dir).glob("*.tif"))
        if not files:
            raise FileNotFoundError(
                f"No .tif files found in {self.input_dir}. "
                "Download MODIS data first via utils/ndvi_downloader.py."
            )

        logger.info("[NDVIProcessor] Found %d .tif files in %s", len(files), self.input_dir)
        arrays = []
        for f in files:
            # Load raw bands (12 months per file)
            da = rioxarray.open_rasterio(f) * self.SCALE_FACTOR
            
            # Extract year from filename (e.g., NDVI_Thailand_2024_ext.tif)
            fname = f.name
            try:
                # Find the 4-digit year in the filename
                import re
                year_match = re.search(r"(\d{4})", fname)
                year = int(year_match.group(1)) if year_match else self.start_year
            except Exception:
                year = self.start_year

            # Rename 'band' to 'time' and create monthly dates for that year
            # MODIS band names from GEE identify as "1", "2", ... "12"
            num_months = da.sizes.get("band", 12)
            dates = [np.datetime64(f"{year}-{m:02d}-01") for m in range(1, num_months + 1)]
            
            da = da.rename({"band": "time"}).assign_coords(time=dates)
            arrays.append(da)

        # Combine all years into one long time series
        da_concat = xr.concat(arrays, dim="time").sortby("time")
        
        # Mask Out-of-Range (Valid NDVI: [-1, 1])
        return da_concat.where(da_concat >= -1.0).where(da_concat <= 1.0)

    def _reproject(self, da: xr.DataArray) -> xr.DataArray:
        """Reproject from MODIS Sinusoidal → WGS84 (EPSG:4326)."""
        return da.rio.reproject("EPSG:4326")

    def _resample_to_era5(self, da: xr.DataArray, era5_ds: xr.Dataset) -> xr.DataArray:
        """
        Bilinear interpolation from 1 km MODIS resolution → ~25 km ERA5 grid.
        Matches latitude and longitude coordinate names used by ERA5.
        """
        lat_coord = "latitude"  if "latitude"  in era5_ds.coords else "y"
        lon_coord = "longitude" if "longitude" in era5_ds.coords else "x"

        return da.interp(
            x=era5_ds[lon_coord].values,
            y=era5_ds[lat_coord].values,
            method="linear"
        )

    def _fill_gaps(self, da: xr.DataArray) -> xr.DataArray:
        """
        Fill NaN values introduced by cloud masking.
        Strategy: linear temporal interpolation → forward fill → backward fill.
        """
        da = da.interpolate_na(dim="time", method=self.fill_method)
        da = da.ffill(dim="time")
        da = da.bfill(dim="time")
        remaining_nan = float(np.isnan(da.values).mean())
        if remaining_nan > 0:
            warnings.warn(
                f"[NDVIProcessor] {remaining_nan:.1%} of values remain NaN after gap fill.",
                UserWarning
            )
        return da

    def _create_lag_features(self, da: xr.DataArray) -> xr.Dataset:
        """
        Create lagged NDVI features for each lag in lag_months.
        lag=0 → ndvi (current month)
        lag=1 → ndvi_lag1 (previous month)
        lag=2 → ndvi_lag2 (2 months ago)
        """
        ds = da.to_dataset(name="ndvi")
        for lag in self.lag_months:
            if lag > 0:
                ds[f"ndvi_lag{lag}"] = da.shift(time=lag)
        return ds

    # ------------------------------------------------------------------
    @classmethod
    def from_config_file(cls, config_path: str = "config/config.yaml") -> "NDVIProcessor":
        """Convenience constructor — load config from YAML file."""
        with open(config_path, "r", encoding="utf-8") as f:
            cfg = yaml.safe_load(f)
        return cls(cfg)


# ------------------------------------------------------------------
if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
    processor = NDVIProcessor.from_config_file()
    ds = processor.run()
    print(f"\nOutput dataset:\n{ds}")
