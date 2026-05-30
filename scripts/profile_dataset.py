"""Profile candidate labels on the ERA5 daily frame; write docs/DATASET_PROFILE.md."""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import pandas as pd

DAILY = "data/processed/era5_daily.parquet"


def label_base_rates(df: pd.DataFrame, abs_threshold: float = 41.0) -> dict:
    return {"absolute_ge_41": float((df["heat_index_max"] >= abs_threshold).mean())}


def main():
    df = pd.read_parquet(DAILY)
    rates = label_base_rates(df)
    lines = ["# Dataset Profile\n",
             f"- rows: {len(df):,}  provinces: {df['province_id'].nunique()}",
             f"- years: {pd.to_datetime(df['time']).dt.year.min()}–"
             f"{pd.to_datetime(df['time']).dt.year.max()}",
             f"- absolute (HI_max ≥ 41 °C) base rate: {rates['absolute_ge_41']*100:.2f}%",
             "\nDecision: choose label A or B based on these base rates "
             "(target a non-degenerate ~3–8% positive rate)."]
    with open("docs/DATASET_PROFILE.md", "w", encoding="utf-8") as f:
        f.write("\n".join(lines) + "\n")
    print("\n".join(lines))
    return 0


if __name__ == "__main__":
    sys.exit(main())
