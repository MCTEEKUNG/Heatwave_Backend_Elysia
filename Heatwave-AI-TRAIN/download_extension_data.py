# -*- coding: utf-8 -*-
"""
download_extension_data.py
==========================
Downloads ERA5 and NDVI data for the EXTENSION period (2016-2025)
to expand the HeatAI training dataset beyond the original 2000-2015 period.

PREREQUISITES
-------------
ERA5  : pip install cdsapi
         Register at https://cds.climate.copernicus.eu and create ~/.cdsapirc
NDVI  : pip install earthengine-api
         earthengine authenticate (already done)
         gee_project set in config/config.yaml

USAGE
-----
# Download both ERA5 + NDVI for 2016-2025
python download_extension_data.py

# ERA5 only
python download_extension_data.py --source era5

# NDVI only
python download_extension_data.py --source ndvi

# Custom year range
python download_extension_data.py --start-year 2016 --end-year 2020
"""
import argparse
import logging
import os
import sys
import time
import yaml

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[
        logging.StreamHandler(sys.stdout),
        logging.FileHandler("download_extension.log", encoding="utf-8"),
    ],
)
logger = logging.getLogger(__name__)

# ── Constants ────────────────────────────────────────────────────────────────
CONFIG_PATH     = "config/config.yaml"
EXTENSION_START = 2016
EXTENSION_END   = 2025

# Thailand bounding box [North, West, South, East] — for CDS API
THAILAND_AREA   = [20.5, 97.5, 5.5, 105.7]   # N/W/S/E

# Thailand bounding box [West, South, East, North] — for GEE
THAILAND_BBOX   = [97.5, 5.5, 105.7, 20.5]

# ERA5 surface variables needed by the pipeline
ERA5_VARIABLES  = ["2m_temperature", "2m_dewpoint_temperature",
                   "surface_pressure", "10m_u_component_of_wind",
                   "10m_v_component_of_wind"]


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# ERA5 DOWNLOADER
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

class ERA5ExtensionDownloader:
    """
    Downloads ERA5 surface data for Thailand (2016-2025) via CDS API.
    Saves one NetCDF file per year: era5_surface_YYYY.nc

    Setup (one-time):
      1. Register at https://cds.climate.copernicus.eu
      2. Accept Terms of Service for ERA5 dataset
      3. Create ~/.cdsapirc with your API key:
            url: https://cds.climate.copernicus.eu/api
            key: YOUR-UID:YOUR-API-KEY
    """

    def __init__(self, output_dir: str = "Era5-data-2000-2026",
                 start_year: int = EXTENSION_START,
                 end_year: int   = EXTENSION_END):
        self.output_dir = output_dir
        self.start_year = start_year
        self.end_year   = end_year
        os.makedirs(output_dir, exist_ok=True)

    def download(self):
        """Download ERA5 for each year in [start_year, end_year]."""
        try:
            import cdsapi
        except ImportError:
            raise ImportError(
                "cdsapi not installed. Run: pip install cdsapi\n"
                "Then set up ~/.cdsapirc — see https://cds.climate.copernicus.eu/how-to-api"
            )

        client = cdsapi.Client()
        years  = list(range(self.start_year, self.end_year + 1))
        logger.info("[ERA5] Starting download for %d years (%d–%d)",
                    len(years), self.start_year, self.end_year)

        for year in years:
            out_path = os.path.join(self.output_dir, f"era5_surface_{year}.nc")

            if os.path.isfile(out_path):
                logger.info("[ERA5] Already exists, skipping: %s", out_path)
                continue

            logger.info("[ERA5] Requesting year %d ...", year)
            try:
                client.retrieve(
                    "reanalysis-era5-single-levels",
                    {
                        "product_type": "reanalysis",
                        "variable":     ERA5_VARIABLES,
                        "year":         str(year),
                        "month":        [f"{m:02d}" for m in range(1, 13)],
                        "day":          [f"{d:02d}" for d in range(1, 32)],
                        "time":         ["00:00", "06:00", "12:00", "18:00"],
                        "area":         THAILAND_AREA,   # N/W/S/E
                        "format":       "netcdf",
                    },
                    out_path,
                )
                logger.info("[ERA5] Downloaded: %s  (%.1f MB)",
                            out_path, os.path.getsize(out_path) / 1e6)
                # Small pause to be polite to CDS servers
                time.sleep(2)

            except Exception as exc:
                logger.error("[ERA5] Failed for year %d: %s", year, exc)

        logger.info("[ERA5] Done. Files saved to: %s", self.output_dir)


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# NDVI EXTENSION DOWNLOADER (GEE)
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

class NDVIExtensionDownloader:
    """
    Submits GEE export tasks for MODIS NDVI (2016-2025) to Google Drive.
    Reuses same logic as NDVIDownloader but for the extension period.
    Files land in Drive folder 'HeatAI_NDVI_Extension'.
    """

    GEE_COLLECTION = "MODIS/061/MOD13A3"

    def __init__(self, gee_project: str,
                 output_dir:  str = "data/ndvi/",
                 start_year:  int = EXTENSION_START,
                 end_year:    int = EXTENSION_END,
                 drive_folder: str = "HeatAI_NDVI_Extension"):
        self.gee_project   = gee_project
        self.output_dir    = output_dir
        self.start_year    = start_year
        self.end_year      = end_year
        self.drive_folder  = drive_folder
        os.makedirs(output_dir, exist_ok=True)

    def submit_tasks(self):
        """Submit one GEE export task per year to Google Drive."""
        try:
            import ee
        except ImportError:
            raise ImportError("Run: pip install earthengine-api>=0.1.380")

        logger.info("[NDVI] Initialising Earth Engine (project=%s) ...",
                    self.gee_project)
        ee.Initialize(project=self.gee_project)

        thailand   = ee.Geometry.Rectangle(THAILAND_BBOX)
        collection = (
            ee.ImageCollection(self.GEE_COLLECTION)
            .filterDate(f"{self.start_year}-01-01", f"{self.end_year}-12-31")
            .filterBounds(thailand)
            .select("NDVI")
        )

        submitted = 0
        years = list(range(self.start_year, self.end_year + 1))
        logger.info("[NDVI] Submitting %d tasks (%d–%d) ...",
                    len(years), self.start_year, self.end_year)

        for year in years:
            monthly = collection.filterDate(f"{year}-01-01", f"{year}-12-31")
            task = ee.batch.Export.image.toDrive(
                image=monthly.toBands(),
                description=f"NDVI_Thailand_{year}_ext",
                folder=self.drive_folder,
                region=thailand,
                scale=1000,         # 1km native MODIS
                crs="EPSG:4326",
                maxPixels=1e9,
            )
            task.start()
            submitted += 1
            logger.info("[NDVI] Task submitted: NDVI_Thailand_%d", year)

        print(
            f"\n[NDVI] {submitted} export tasks submitted.\n"
            f"Monitor: https://code.earthengine.google.com/tasks\n"
            f"After completion, download .tif files from Drive folder "
            f"'{self.drive_folder}' into '{self.output_dir}'.\n"
            f"Then run: python utils/ndvi_processor.py"
        )


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# CONFIG UPDATER
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

def update_config_years(start_year: int, end_year: int,
                        config_path: str = CONFIG_PATH):
    """
    After downloading, update config.yaml so the training pipeline
    recognises the new years. Appends only years not already listed.
    """
    with open(config_path, "r", encoding="utf-8") as f:
        cfg = yaml.safe_load(f)

    existing_years = cfg["data"].get("years", [])
    new_years      = list(range(start_year, end_year + 1))
    added          = [y for y in new_years if y not in existing_years]

    if not added:
        logger.info("[Config] No new years to add (all already in config).")
        return

    cfg["data"]["years"] = sorted(existing_years + added)

    # Also extend ndvi range
    if "ndvi" in cfg:
        cfg["ndvi"]["end_year"] = max(cfg["ndvi"].get("end_year", 2015), end_year)

    with open(config_path, "w", encoding="utf-8") as f:
        yaml.dump(cfg, f, default_flow_style=False, allow_unicode=True,
                  sort_keys=False)

    logger.info("[Config] Added %d years to config.yaml: %s", len(added), added)
    logger.info("[Config] Updated: %s", config_path)


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# MAIN
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

def main():
    parser = argparse.ArgumentParser(
        description="Download ERA5 + NDVI extension data (2016-2025) for HeatAI."
    )
    parser.add_argument("--source",     choices=["era5", "ndvi", "both"],
                        default="both",  help="Which data source to download")
    parser.add_argument("--start-year", type=int, default=EXTENSION_START,
                        help=f"First year to download (default: {EXTENSION_START})")
    parser.add_argument("--end-year",   type=int, default=EXTENSION_END,
                        help=f"Last year to download  (default: {EXTENSION_END})")
    parser.add_argument("--config",     default=CONFIG_PATH,
                        help="Path to config.yaml")
    parser.add_argument("--update-config", action="store_true",
                        help="Automatically add new years to config.yaml after download")
    args = parser.parse_args()

    # Load config
    with open(args.config, "r", encoding="utf-8") as f:
        cfg = yaml.safe_load(f)

    gee_project     = cfg.get("ndvi", {}).get("gee_project", "")
    era5_output_dir = cfg.get("data", {}).get("raw_dir", "Era5-data-2000-2026")
    ndvi_output_dir = cfg.get("ndvi", {}).get("output_dir", "data/ndvi/")

    logger.info("=" * 60)
    logger.info("HeatAI — Extension Data Downloader")
    logger.info("Period : %d – %d", args.start_year, args.end_year)
    logger.info("Source : %s", args.source.upper())
    logger.info("=" * 60)

    # ── ERA5 ──────────────────────────────────────────────────────────
    if args.source in ("era5", "both"):
        print("\n" + "─" * 60)
        print("  STEP 1/2 — Downloading ERA5 data via CDS API")
        print("─" * 60)
        era5_dl = ERA5ExtensionDownloader(
            output_dir=era5_output_dir,
            start_year=args.start_year,
            end_year=args.end_year,
        )
        era5_dl.download()

    # ── NDVI ──────────────────────────────────────────────────────────
    if args.source in ("ndvi", "both"):
        if not gee_project:
            logger.error(
                "[NDVI] gee_project is empty in config.yaml. "
                "Set ndvi.gee_project to your Google Cloud Project ID."
            )
            sys.exit(1)
        print("\n" + "─" * 60)
        print("  STEP 2/2 — Submitting NDVI export tasks via GEE")
        print("─" * 60)
        ndvi_dl = NDVIExtensionDownloader(
            gee_project=gee_project,
            output_dir=ndvi_output_dir,
            start_year=args.start_year,
            end_year=args.end_year,
        )
        ndvi_dl.submit_tasks()

    # ── Update config ─────────────────────────────────────────────────
    if args.update_config:
        print("\n" + "─" * 60)
        print("  Updating config.yaml with new year range ...")
        print("─" * 60)
        update_config_years(args.start_year, args.end_year, args.config)

    print()
    logger.info("=" * 60)
    logger.info("Download script finished.")
    logger.info("Next steps:")
    logger.info("  ERA5  : files saved to %s — ready for training", era5_output_dir)
    logger.info("  NDVI  : wait for GEE tasks, then download .tif files")
    logger.info("          → place in %s", ndvi_output_dir)
    logger.info("          → run: python utils/ndvi_processor.py")
    logger.info("  Retrain : python main.py --mode train")
    logger.info("=" * 60)


if __name__ == "__main__":
    main()
