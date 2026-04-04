"""
evaluation/benchmark.py
Loads all experiment results and generates a ranked leaderboard.
"""
import math
import os
import json
import logging
import pandas as pd

logger = logging.getLogger(__name__)


class Benchmark:
    """Reads experiment JSONs and generates a sorted leaderboard."""

    def __init__(self, results_dir: str = "experiments/results"):
        self.results_dir = results_dir

    def load_results(self) -> list:
        """Load all result JSON files from results_dir."""
        results = []
        if not os.path.isdir(self.results_dir):
            logger.warning("Results dir not found: %s", self.results_dir)
            return results

        for fname in os.listdir(self.results_dir):
            if fname.endswith(".json") and fname != "leaderboard.json":
                fpath = os.path.join(self.results_dir, fname)
                try:
                    with open(fpath, "r", encoding="utf-8") as f:
                        data = json.load(f)
                    results.append(data)
                except Exception as e:
                    logger.error("Could not read %s: %s", fname, e)

        return results

    def get_leaderboard(self) -> pd.DataFrame:
        """Return DataFrame sorted by F1 Score descending."""
        results = self.load_results()
        if not results:
            return pd.DataFrame()

        df = pd.DataFrame(results)
        df = df.sort_values("f1_score", ascending=False).reset_index(drop=True)
        df.index += 1  # Rank from 1
        df.index.name = "Rank"
        return df

    def get_leaderboard_json(self) -> list:
        """Return leaderboard as list of dicts (for API / JSON output).
        NaN values are converted to None so they serialize as JSON null.
        """
        df = self.get_leaderboard()
        if df.empty:
            return []
        df = df.reset_index()
        records = df.to_dict(orient="records")
        # pandas reconverts None→nan in numeric columns during to_dict,
        # so sanitize afterwards at the Python level.
        return [
            {k: (None if isinstance(v, float) and not math.isfinite(v) else v)
             for k, v in row.items()}
            for row in records
        ]

    def print_leaderboard(self):
        """Pretty-print the leaderboard to console."""
        df = self.get_leaderboard()
        if df.empty:
            print("No results found.")
            return
        cols = ["model", "f1_score", "accuracy", "precision", "recall", "roc_auc"]
        display_cols = [c for c in cols if c in df.columns]
        print("\n" + "=" * 70)
        print("  EXPERIMENT LEADERBOARD — ranked by F1 Score")
        print("=" * 70)
        print(df[display_cols].to_string())
        print("=" * 70 + "\n")

    def save_leaderboard(self, path: str = "experiments/results/leaderboard.json"):
        """Persist sorted leaderboard to JSON (NaN → null for valid JSON)."""
        records = self.get_leaderboard_json()
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "w") as f:
            # allow_nan=False ensures float nan/inf raise ValueError instead of
            # writing invalid JSON literals; values are already sanitized to None
            # by get_leaderboard_json(), so this is just a safety net.
            json.dump(records, f, indent=2, allow_nan=False)
        logger.info("Leaderboard saved: %s", path)
