"""
prediction/forecast.py
Generate heatwave forecasts using real weather data from Open-Meteo.

Open-Meteo is free, requires no API key, and provides up to 16 days of
real NWP forecast data (temperature, humidity, wind, pressure).

Usage:
    python prediction/forecast.py --model balanced_rf
    python prediction/forecast.py --model balanced_rf --days 7
"""

import json
import os
import sys
import logging
import urllib.request
import numpy as np
import pandas as pd
import yaml
from datetime import datetime
try:
    from zoneinfo import ZoneInfo          # Python 3.9+
except ImportError:
    from backports.zoneinfo import ZoneInfo  # Python 3.8 fallback

ICT = ZoneInfo("Asia/Bangkok")  # UTC+7, no DST

# Open-Meteo free-tier maximum forecast horizon
OPENMETEO_MAX_DAYS = 16

# Thailand coordinates (centre of Bangkok / ERA5 representative point)
DEFAULT_LAT = 13.75
DEFAULT_LON = 100.50

# Seasonal NDVI climatology for Thailand (MODIS MOD13A3 long-term mean)
# Used because real-time NDVI is monthly and unavailable for future dates.
NDVI_SEASONAL = {
    1: 0.42, 2: 0.38, 3: 0.33, 4: 0.31, 5: 0.35,
    6: 0.45, 7: 0.52, 8: 0.55, 9: 0.57, 10: 0.53,
    11: 0.50, 12: 0.46,
}

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from prediction.predictor import Predictor

logging.basicConfig(
    level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s"
)
logger = logging.getLogger(__name__)


class ForecastPredictor:
    """Generates heatwave forecasts using real Open-Meteo weather data."""

    def __init__(self, config_path: str = "config.yaml"):
        with open(config_path, "r", encoding="utf-8") as f:
            self.cfg = yaml.safe_load(f)
        self.predictor = Predictor(config_path)
        self.config_path = config_path

    # ------------------------------------------------------------------
    def _fetch_openmeteo(self, lat: float, lon: float, days: int) -> pd.DataFrame:
        """
        Fetch real hourly forecast from Open-Meteo and aggregate to daily.

        Features returned (all pre-computed, ready for the model):
          t2m, t2m_c, d2m, d2m_c, rh, heat_index,
          wind_speed, u10, v10, sp,
          ndvi, ndvi_lag1, ndvi_lag2,
          latitude, longitude, year, time
        """
        days = min(days, OPENMETEO_MAX_DAYS)

        url = (
            "https://api.open-meteo.com/v1/forecast"
            f"?latitude={lat}&longitude={lon}"
            "&hourly=temperature_2m,dewpoint_2m,relative_humidity_2m"
            ",surface_pressure,wind_speed_10m,wind_direction_10m"
            "&wind_speed_unit=ms"
            "&timezone=Asia%2FBangkok"
            f"&forecast_days={days}"
        )

        logger.info("Fetching Open-Meteo forecast: lat=%.2f lon=%.2f days=%d", lat, lon, days)
        try:
            with urllib.request.urlopen(url, timeout=30) as resp:
                data = json.loads(resp.read())
        except Exception as exc:
            raise RuntimeError(
                f"Failed to fetch Open-Meteo data: {exc}\n"
                "Check internet connectivity on the server."
            ) from exc

        h = data["hourly"]
        df_h = pd.DataFrame({
            "time":          pd.to_datetime(h["time"]),
            "t2m_c":         h["temperature_2m"],
            "d2m_c":         h["dewpoint_2m"],
            "rh":            h["relative_humidity_2m"],
            "sp":            h["surface_pressure"],
            "wind_speed":    h["wind_speed_10m"],
            "wind_dir":      h["wind_direction_10m"],
        })
        df_h["date"] = df_h["time"].dt.date

        # Daily aggregation
        # — temperature: use daily MAX (peak heat is what causes heatwaves)
        # — everything else: daily mean
        daily = df_h.groupby("date").agg(
            t2m_c     =("t2m_c",      "max"),
            d2m_c     =("d2m_c",      "mean"),
            rh        =("rh",         "mean"),
            sp        =("sp",         "mean"),
            wind_speed=("wind_speed", "mean"),
            wind_dir  =("wind_dir",   "mean"),
        ).reset_index()

        daily["time"] = pd.to_datetime(daily["date"])

        # Kelvin columns (for _engineer_features K→C pass-through)
        daily["t2m"] = daily["t2m_c"] + 273.15
        daily["d2m"] = daily["d2m_c"] + 273.15

        # Wind components from speed + direction
        # Meteorological convention: direction = FROM where wind comes
        # u = eastward (+east), v = northward (+north)
        dir_rad = np.radians(daily["wind_dir"])
        daily["u10"] = (-daily["wind_speed"] * np.sin(dir_rad)).values
        daily["v10"] = (-daily["wind_speed"] * np.cos(dir_rad)).values

        # Heat Index — Rothfusz regression
        # Valid only for T >= 26.7°C AND RH >= 40%
        T  = daily["t2m_c"].values
        RH = daily["rh"].values
        t_f  = T * 9.0 / 5.0 + 32.0
        hi_f = (
            -42.379
            + 2.04901523  * t_f
            + 10.14333127 * RH
            - 0.22475541  * t_f * RH
            - 0.00683783  * t_f ** 2
            - 0.05481717  * RH ** 2
            + 0.00122874  * t_f ** 2 * RH
            + 0.00085282  * t_f * RH ** 2
            - 0.00000199  * t_f ** 2 * RH ** 2
        )
        hi_c = (hi_f - 32.0) * 5.0 / 9.0
        daily["heat_index"] = np.where((T >= 26.7) & (RH >= 40.0), hi_c, T)

        # NDVI — seasonal climatology (future dates have no real-time NDVI)
        month = daily["time"].dt.month.iloc[0]
        m1 = month
        m2 = month - 1 if month > 1 else 12
        m3 = month - 2 if month > 2 else month + 10
        daily["ndvi"]      = NDVI_SEASONAL.get(m1, 0.40)
        daily["ndvi_lag1"] = NDVI_SEASONAL.get(m2, 0.40)
        daily["ndvi_lag2"] = NDVI_SEASONAL.get(m3, 0.40)

        daily["latitude"]  = lat
        daily["longitude"] = lon
        daily["year"]      = daily["time"].dt.year

        logger.info(
            "Open-Meteo data ready: %d days (%s → %s) | "
            "temp range %.1f–%.1f°C | rh mean %.0f%%",
            len(daily),
            str(daily["date"].iloc[0]),
            str(daily["date"].iloc[-1]),
            daily["t2m_c"].min(),
            daily["t2m_c"].max(),
            daily["rh"].mean(),
        )
        return daily

    # ------------------------------------------------------------------
    def forecast(
        self,
        model: str,
        start_date: datetime,
        days: int = 7,
        cycles: int = 1,   # ignored — real data has no concept of "cycles"
    ) -> pd.DataFrame:
        """
        Generate a heatwave forecast using real Open-Meteo weather data.

        Args:
            model:      Model key (e.g. "balanced_rf")
            start_date: Ignored — Open-Meteo always starts from today
            days:       Number of forecast days (max 16, Open-Meteo limit)
            cycles:     Unused with real data (kept for API compatibility)

        Returns:
            DataFrame with forecast results
        """
        days = min(days, OPENMETEO_MAX_DAYS)

        forecast_input = self._fetch_openmeteo(DEFAULT_LAT, DEFAULT_LON, days)

        predictions = self.predictor.predict(model, forecast_input)
        probas      = self.predictor.predict_proba(model, forecast_input)

        if predictions is None or probas is None:
            raise ValueError(f"Predictor returned None for model '{model}'")
        if len(predictions) != len(forecast_input) or len(probas) != len(forecast_input):
            raise ValueError(
                f"Predictor output length mismatch: expected {len(forecast_input)}, "
                f"got predictions={len(predictions)}, probas={len(probas)}"
            )

        result = pd.DataFrame({
            "date":                forecast_input["time"].dt.strftime("%Y-%m-%d"),
            "predicted_heatwave":  predictions,
            "heatwave_probability": probas,
            "forecast_cycle":      1,
            "temperature_c":       forecast_input["t2m_c"].values,
            "humidity_pct":        forecast_input["rh"].values.round(1),
            "heat_index_c":        forecast_input["heat_index"].values.round(2),
            "data_source":         "open-meteo",
            "forecast_generated":  datetime.now(tz=ICT).isoformat(),
        })

        return result

    # ------------------------------------------------------------------
    def save_forecast(self, result: pd.DataFrame, output_path: str):
        """Save forecast results to CSV and JSON."""
        os.makedirs(os.path.dirname(output_path), exist_ok=True)

        result.to_csv(output_path, index=False)

        json_path = output_path.replace(".csv", ".json")
        result["date"] = result["date"].astype(str)
        result.to_json(json_path, orient="records", indent=2)

        logger.info("Forecast saved to %s and %s", output_path, json_path)


VALID_MODELS = {"balanced_rf", "xgboost", "lightgbm", "mlp", "kan"}


def main():
    import argparse

    parser = argparse.ArgumentParser(description="Heatwave AI — Real-Data Forecast")
    parser.add_argument("--model",  required=True, help="Model to use (e.g. balanced_rf)")
    parser.add_argument("--days",   type=int, default=7,
                        help=f"Forecast days (max {OPENMETEO_MAX_DAYS})")
    parser.add_argument("--output", type=str, default=None, help="Output CSV path")
    parser.add_argument("--config", type=str, default="config.yaml", help="Config file")

    args = parser.parse_args()

    if args.model not in VALID_MODELS:
        logger.error("Invalid model '%s'. Valid: %s", args.model, sorted(VALID_MODELS))
        sys.exit(1)

    start_date = datetime.now(tz=ICT)
    days       = min(args.days, OPENMETEO_MAX_DAYS)

    print(f"\n{'=' * 60}")
    print(f"  HEATWAVE-AI | {days}-Day Real-Weather Forecast")
    print(f"{'=' * 60}")
    print(f"  Model       : {args.model}")
    print(f"  Start Date  : {start_date.strftime('%Y-%m-%d')} (today, ICT)")
    print(f"  Days        : {days}")
    print(f"  Data source : Open-Meteo (real NWP forecast)")
    print(f"{'=' * 60}\n")

    forecaster = ForecastPredictor(config_path=args.config)
    result     = forecaster.forecast(args.model, start_date, days)

    heatwave_days = (result["predicted_heatwave"] == 1).sum()
    total_days    = len(result)
    avg_prob      = result["heatwave_probability"].mean()

    print(f"\n{'=' * 60}")
    print(f"  Forecast Results")
    print(f"{'=' * 60}")
    print(f"  Total Days   : {total_days}")
    print(f"  Heatwave Days: {heatwave_days} ({100 * heatwave_days / total_days:.1f}%)")
    print(f"  Avg Risk Prob: {avg_prob:.4f}")
    print(f"  Date Range   : {result['date'].min()} → {result['date'].max()}")
    print(f"\n  Daily breakdown:")
    for _, row in result.iterrows():
        status = "HEATWAVE" if row["predicted_heatwave"] == 1 else "Normal  "
        print(
            f"    {str(row['date'])[:10]} | {status} | "
            f"Prob: {row['heatwave_probability']:.3f} | "
            f"Temp: {row['temperature_c']:.1f}°C | "
            f"HI: {row['heat_index_c']:.1f}°C | "
            f"RH: {row['humidity_pct']:.0f}%"
        )

    output_path = (
        args.output
        or f"experiments/forecasts/forecast_{args.model}_{start_date.strftime('%Y%m%d')}_{days}d.csv"
    )
    forecaster.save_forecast(result, output_path)
    print(f"\n  Saved → {output_path}")
    print(f"{'=' * 60}\n")


if __name__ == "__main__":
    main()
