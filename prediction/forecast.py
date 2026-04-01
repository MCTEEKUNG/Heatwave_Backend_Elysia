"""
prediction/forecast.py
Generate 30-day heatwave forecasts using trained models.

Usage:
    python prediction/forecast.py --model balanced_rf --days 30
    python prediction/forecast.py --model balanced_rf --days 30 --cycles 3
"""

import os
import sys
import logging
import numpy as np
import pandas as pd
import yaml
from datetime import datetime, timedelta

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from prediction.predictor import Predictor
from utils.data_loader import ERA5DataLoader

logging.basicConfig(
    level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s"
)
logger = logging.getLogger(__name__)


class ForecastPredictor:
    """Generates rolling 30-day heatwave forecasts."""

    def __init__(self, config_path: str = "config/config.yaml"):
        with open(config_path, "r", encoding="utf-8") as f:
            self.cfg = yaml.safe_load(f)
        self.predictor = Predictor(config_path)
        self.config_path = config_path

    def _generate_forecast_input(self, start_date: datetime, days: int) -> pd.DataFrame:
        """
        Generate synthetic input data for forecast period.
        Pre-computes all derived features the model expects:
        t2m_c, d2m_c, rh, heat_index, wind_speed, sp
        """
        dates = pd.date_range(start=start_date, periods=days, freq="D")
        n = len(dates)

        day_of_year = start_date.timetuple().tm_yday
        seasonal_factor = np.sin(2 * np.pi * (day_of_year - 80) / 365)

        # Base temperature: 33-40°C range
        base_temp_c = 33.0 + 5.0 * seasonal_factor
        temps_c = base_temp_c + np.random.normal(0, 1.5, n)

        # Add heatwave periods (5-10 day stretches of extreme heat)
        np.random.seed(42)
        num_heatwaves = max(1, days // 15)
        for _ in range(num_heatwaves):
            hw_start = np.random.randint(0, max(1, n - 7))
            hw_duration = np.random.randint(3, 8)
            hw_end = min(hw_start + hw_duration, n)
            temps_c[hw_start:hw_end] += np.random.uniform(4.0, 8.0, hw_end - hw_start)

        # Dew point: high during heatwaves
        dews_c = np.where(
            temps_c > 37,
            temps_c - 5.0 + np.random.normal(0, 1.0, n),
            temps_c - 12.0 + np.random.normal(0, 2.0, n),
        )

        # Relative Humidity (August-Roche-Magnus)
        rh = 100 * np.exp(
            (17.625 * dews_c) / (243.04 + dews_c)
            - (17.625 * temps_c) / (243.04 + temps_c)
        )
        rh = np.clip(rh, 0, 100)

        # Heat Index (Rothfusz Regression)
        t_f = temps_c * 9 / 5 + 32
        hi_f = (
            -42.379
            + 2.04901523 * t_f
            + 10.14333127 * rh
            - 0.22475541 * t_f * rh
            - 0.00683783 * t_f**2
            - 0.05481717 * rh**2
            + 0.00122874 * t_f**2 * rh
            + 0.00085282 * t_f * rh**2
            - 0.00000199 * t_f**2 * rh**2
        )
        heat_index = np.where(temps_c >= 26.7, (hi_f - 32) * 5 / 9, temps_c)

        # Wind speed
        u10 = np.where(
            temps_c > 37, np.random.normal(0.5, 1.0, n), np.random.normal(0, 3.0, n)
        )
        v10 = np.where(
            temps_c > 37, np.random.normal(0.5, 1.0, n), np.random.normal(0, 3.0, n)
        )
        wind_speed = np.sqrt(u10**2 + v10**2)

        # Pressure
        sp = np.where(
            temps_c > 37,
            1005.0 + np.random.normal(0, 2.0, n),
            1010.0 + np.random.normal(0, 3.0, n),
        )

        # Build DataFrame with ALL features the model expects
        df = pd.DataFrame(
            {
                "time": dates,
                "t2m": temps_c + 273.15,
                "t2m_c": temps_c,
                "d2m": dews_c + 273.15,
                "d2m_c": dews_c,
                "rh": rh,
                "heat_index": heat_index,
                "wind_speed": wind_speed,
                "sp": sp,
                "u10": u10,
                "v10": v10,
                "latitude": 13.75,
                "longitude": 100.50,
                "year": start_date.year,
            }
        )

        return df

    def forecast(
        self, model: str, start_date: datetime, days: int = 30, cycles: int = 1
    ):
        """
        Generate rolling forecasts.

        Args:
            model: Model key (e.g., "balanced_rf")
            start_date: First day of forecast
            days: Days per forecast cycle
            cycles: Number of consecutive 30-day cycles

        Returns:
            DataFrame with all forecast results
        """
        all_forecasts = []

        current_date = start_date

        for cycle in range(cycles):
            logger.info(
                f"Generating forecast cycle {cycle + 1}/{cycles}: {current_date.strftime('%Y-%m-%d')}"
            )

            forecast_input = self._generate_forecast_input(current_date, days)

            predictions = self.predictor.predict(model, forecast_input)
            probas = self.predictor.predict_proba(model, forecast_input)

            cycle_df = pd.DataFrame(
                {
                    "date": forecast_input["time"].values,
                    "predicted_heatwave": predictions,
                    "heatwave_probability": probas,
                    "forecast_cycle": cycle + 1,
                    "temperature_c": forecast_input["t2m"].values - 273.15,
                    "humidity_est": (
                        forecast_input["t2m"].values - forecast_input["d2m"].values
                    ).clip(0, 100),
                    "forecast_generated": datetime.now().isoformat(),
                }
            )

            all_forecasts.append(cycle_df)

            current_date += timedelta(days=days)

        result = pd.concat(all_forecasts, ignore_index=True)
        return result

    def save_forecast(self, result: pd.DataFrame, output_path: str):
        """Save forecast results to CSV and JSON."""
        os.makedirs(os.path.dirname(output_path), exist_ok=True)

        result.to_csv(output_path, index=False)

        json_path = output_path.replace(".csv", ".json")
        result["date"] = result["date"].astype(str)
        result.to_json(json_path, orient="records", indent=2)

        logger.info(f"Forecast saved to {output_path} and {json_path}")


def main():
    import argparse

    parser = argparse.ArgumentParser(description="Heatwave AI - 30-Day Forecast")
    parser.add_argument("--model", required=True, help="Model to use for forecasting")
    parser.add_argument("--days", type=int, default=30, help="Days per forecast cycle")
    parser.add_argument(
        "--cycles", type=int, default=1, help="Number of consecutive forecast cycles"
    )
    parser.add_argument(
        "--start-date",
        type=str,
        default=None,
        help="Start date (YYYY-MM-DD), defaults to today",
    )
    parser.add_argument("--output", type=str, default=None, help="Output CSV path")
    parser.add_argument(
        "--config", type=str, default="config/config.yaml", help="Config file path"
    )

    args = parser.parse_args()

    start_date = (
        datetime.strptime(args.start_date, "%Y-%m-%d")
        if args.start_date
        else datetime.now()
    )

    print(f"\n{'=' * 60}")
    print(f"  HEATWAVE-AI | {args.days}-Day Forecast Prediction")
    print(f"{'=' * 60}")
    print(f"  Model      : {args.model}")
    print(f"  Start Date : {start_date.strftime('%Y-%m-%d')}")
    print(f"  Days/Cycle : {args.days}")
    print(f"  Cycles     : {args.cycles}")
    print(f"  Total Days : {args.days * args.cycles}")
    print(f"{'=' * 60}\n")

    forecaster = ForecastPredictor(config_path=args.config)
    result = forecaster.forecast(args.model, start_date, args.days, args.cycles)

    heatwave_days = (result["predicted_heatwave"] == 1).sum()
    total_days = len(result)
    avg_prob = result["heatwave_probability"].mean()

    print(f"\n{'=' * 60}")
    print(f"  Forecast Results")
    print(f"{'=' * 60}")
    print(f"  Total Days          : {total_days}")
    print(
        f"  Heatwave Days       : {heatwave_days} ({100 * heatwave_days / total_days:.1f}%)"
    )
    print(f"  Avg Probability     : {avg_prob:.4f}")
    print(f"  Date Range          : {result['date'].min()} to {result['date'].max()}")

    print(f"\n  First 10 days:")
    for _, row in result.head(10).iterrows():
        status = "HEATWAVE" if row["predicted_heatwave"] == 1 else "Normal"
        print(
            f"    {str(row['date'])[:10]} | {status:8s} | Prob: {row['heatwave_probability']:.4f} | Temp: {row['temperature_c']:.1f}C"
        )

    output_path = (
        args.output
        or f"experiments/forecasts/forecast_{args.model}_{start_date.strftime('%Y%m%d')}_{args.days}d.csv"
    )
    forecaster.save_forecast(result, output_path)

    print(f"\n{'=' * 60}\n")


if __name__ == "__main__":
    main()
