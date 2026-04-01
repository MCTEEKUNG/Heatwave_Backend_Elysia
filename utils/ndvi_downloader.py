"""
utils/ndvi_downloader.py
Downloads MODIS MOD13A3 Monthly NDVI for Thailand (2000–2015)
via Google Earth Engine (GEE) Python API.

Setup (one-time):
    pip install earthengine-api
    earthengine authenticate     ← run once in terminal

After export tasks complete in GEE console:
    1. Download GeoTIFF files from Google Drive folder "HeatAI_NDVI"
    2. Place files into data/ndvi/ directory
    3. Run utils/ndvi_processor.py to align them to ERA5 grid
    4. Set ndvi.enabled: true in config/config.yaml

GEE Task Monitor: https://code.earthengine.google.com/tasks
"""
import logging
import os
import yaml

logger = logging.getLogger(__name__)


class NDVIDownloader:
    """
    Downloads MODIS MOD13A3 Monthly NDVI for Thailand (2000–2015)
    via Google Earth Engine Python API.

    Config fields used (from config.yaml → ndvi block):
        start_year, end_year, output_dir
    """

    # Bounding box that covers all of Thailand [west, south, east, north]
    THAILAND_BBOX = [97.5, 5.5, 105.7, 20.5]

    # GEE ImageCollection ID for MODIS MOD13A3 v061
    GEE_COLLECTION = "MODIS/061/MOD13A3"

    def __init__(self, config: dict):
        ndvi_cfg         = config.get("ndvi", {})
        self.start_year  = ndvi_cfg.get("start_year", 2000)
        self.end_year    = ndvi_cfg.get("end_year",   2015)
        self.output_dir  = ndvi_cfg.get("output_dir", "data/ndvi/")
        self.gee_project = ndvi_cfg.get("gee_project", "").strip()
        os.makedirs(self.output_dir, exist_ok=True)

    # ------------------------------------------------------------------
    def download_to_drive(self, drive_folder: str = "HeatAI_NDVI"):
        """
        Submit GEE export tasks — one per year — to Google Drive.
        Each task exports monthly NDVI bands as a multi-band GeoTIFF.

        Args:
            drive_folder: Name of the Google Drive folder to export into.
        """
        try:
            import ee
        except ImportError as exc:
            raise ImportError(
                "earthengine-api is not installed. "
                "Run: pip install earthengine-api>=0.1.380"
            ) from exc

        logger.info("[NDVIDownloader] Initialising Earth Engine...")
        if not self.gee_project:
            raise ValueError(
                "[NDVIDownloader] gee_project is not set in config.yaml.\n"
                "Please set ndvi.gee_project to your Google Cloud Project ID.\n"
                "Example: gee_project: \"my-project-123456\"\n"
                "Find it at: https://console.cloud.google.com/"
            )
        ee.Initialize(project=self.gee_project)

        thailand = ee.Geometry.Rectangle(self.THAILAND_BBOX)

        collection = (
            ee.ImageCollection(self.GEE_COLLECTION)
            .filterDate(f"{self.start_year}-01-01", f"{self.end_year}-12-31")
            .filterBounds(thailand)
            .select("NDVI")
        )

        logger.info(
            "[NDVIDownloader] Submitting export tasks for years %d–%d ...",
            self.start_year, self.end_year
        )
        tasks_submitted = 0
        for year in range(self.start_year, self.end_year + 1):
            monthly = collection.filterDate(f"{year}-01-01", f"{year}-12-31")

            task = ee.batch.Export.image.toDrive(
                image=monthly.toBands(),
                description=f"NDVI_Thailand_{year}",
                folder=drive_folder,
                region=thailand,
                scale=1000,           # 1km native MODIS resolution
                crs="EPSG:4326",
                maxPixels=1e9,
            )
            task.start()
            tasks_submitted += 1
            logger.info("  ✓ Task submitted: NDVI_Thailand_%d", year)

        print(
            f"\n[NDVIDownloader] {tasks_submitted} export tasks submitted.\n"
            f"Monitor at: https://code.earthengine.google.com/tasks\n"
            f"After completion, download files from Drive folder '{drive_folder}' "
            f"into '{self.output_dir}' then run utils/ndvi_processor.py."
        )

    # ------------------------------------------------------------------
    @classmethod
    def from_config_file(cls, config_path: str = "config/config.yaml") -> "NDVIDownloader":
        """Convenience constructor — load config from YAML file."""
        with open(config_path, "r", encoding="utf-8") as f:
            cfg = yaml.safe_load(f)
        return cls(cfg)


# ------------------------------------------------------------------
if __name__ == "__main__":
    import sys
    logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
    downloader = NDVIDownloader.from_config_file()
    downloader.download_to_drive()
