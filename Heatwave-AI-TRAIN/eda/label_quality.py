# -*- coding: utf-8 -*-
"""
eda/05_label_quality.py
Sweep thresholds for each labeler and report label quality metrics.
Helps choose the best default thresholds for Thailand before final training.

Metrics per (method, threshold):
  positive_rate  — % of time steps labeled as heatwave
  mean_run_len   — average length of heatwave events
  pct_single_day — % of events that are single-day spikes (noise indicator)
  cohen_kappa    — agreement between this labeler and the WBGT default

Run from Heatwave-AI-TRAIN/: python eda/05_label_quality.py
"""
import os
import sys
import warnings

import numpy as np
import pandas as pd
import xarray as xr
import yaml
from pathlib import Path

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

OUTPUT_DIR = Path("experiments/eda")
KELVIN_OFFSET = 273.15
EVAL_YEARS = list(range(2020, 2026))   # compare methods on the recent period


def _detect_time_dim(ds):
    for n in ("valid_time", "time"):
        if n in ds.dims or n in ds.coords:
            return n
    return None


def _compute_wbgt(t_c, rh):
    e = (rh / 100.0) * 6.105 * np.exp(17.27 * t_c / (237.7 + t_c))
    return 0.567 * t_c + 0.393 * e + 3.94


def _mean_run_len(labels: np.ndarray) -> float:
    """Mean length of contiguous heatwave events."""
    runs = []
    count = 0
    for v in labels:
        if v:
            count += 1
        elif count:
            runs.append(count)
            count = 0
    if count:
        runs.append(count)
    return float(np.mean(runs)) if runs else 0.0


def _pct_single(labels: np.ndarray) -> float:
    """Fraction of heatwave events that are single-step (noise)."""
    runs = []
    count = 0
    for v in labels:
        if v:
            count += 1
        elif count:
            runs.append(count)
            count = 0
    if count:
        runs.append(count)
    if not runs:
        return 0.0
    return 100 * sum(1 for r in runs if r == 1) / len(runs)


def _cohen_kappa(a: np.ndarray, b: np.ndarray) -> float:
    n = len(a)
    if n == 0:
        return 0.0
    po = (a == b).mean()
    pa = a.mean()
    pb = b.mean()
    pe = pa * pb + (1 - pa) * (1 - pb)
    return (po - pe) / (1 - pe) if (1 - pe) > 1e-10 else 1.0


def _mark_runs(s: pd.Series, min_len: int) -> np.ndarray:
    groups   = (s != s.shift()).cumsum()
    run_lens = s.groupby(groups).transform("sum")
    return ((s == 1) & (run_lens >= min_len)).astype(int).values


def run(config_path: str = "config/config.yaml") -> pd.DataFrame:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    with open(config_path, encoding="utf-8") as f:
        cfg = yaml.safe_load(f)

    raw_dir = cfg["data"]["raw_dir"]
    prefix  = cfg["data"]["surface_prefix"]

    # Load and engineer features for eval years
    frames = []
    for year in EVAL_YEARS:
        path = os.path.join(raw_dir, f"{prefix}{year}.nc")
        if not os.path.isfile(path):
            continue
        try:
            with xr.open_dataset(path, engine="netcdf4") as ds:
                time_dim = _detect_time_dim(ds)
                df = ds[["t2m", "d2m"]].to_dataframe().reset_index()
            if time_dim and time_dim in df.columns:
                df = df.rename(columns={time_dim: "time"})
            for col in ("t2m", "d2m"):
                if col in df.columns and df[col].median() > 200:
                    df[f"{col}_c"] = df[col] - KELVIN_OFFSET
                else:
                    df[f"{col}_c"] = df.get(col, np.nan)
            if "t2m_c" in df.columns and "d2m_c" in df.columns:
                rh = 100 * np.exp(
                    17.625 * df["d2m_c"] / (243.04 + df["d2m_c"])
                    - 17.625 * df["t2m_c"] / (243.04 + df["t2m_c"])
                )
                df["rh"] = np.clip(rh, 0, 100)
                df["wbgt"] = _compute_wbgt(df["t2m_c"].values, df["rh"].values)
                T_f = df["t2m_c"] * 9 / 5 + 32
                RH  = df["rh"]
                HI_f = (-42.379 + 2.04901523*T_f + 10.14333127*RH
                        - 0.22475541*T_f*RH - 0.00683783*T_f**2
                        - 0.05481717*RH**2 + 0.00122874*T_f**2*RH
                        + 0.00085282*T_f*RH**2 - 0.00000199*T_f**2*RH**2)
                df["heat_index"] = np.where(
                    (df["t2m_c"] >= 26.7) & (RH >= 40),
                    (HI_f - 32) * 5 / 9,
                    df["t2m_c"],
                )
            df["year"] = year
            frames.append(df)
        except Exception as exc:
            print(f"  {year}: ERROR — {exc}")

    if not frames:
        print("No data loaded.")
        return pd.DataFrame()

    df = pd.concat(frames, ignore_index=True)
    # Use a single representative cell (mean-lat, mean-lon) for the sweep
    # to keep the sweep fast; full-grid sweeps can be done offline
    if "latitude" in df.columns and "longitude" in df.columns:
        lat_mid = df["latitude"].median()
        lon_mid = df["longitude"].median()
        df = df[
            (df["latitude"].round(2) == round(lat_mid, 2)) &
            (df["longitude"].round(2) == round(lon_mid, 2))
        ].copy().sort_values("time").reset_index(drop=True)
    print(f"Evaluating on {len(df):,} time steps, years {EVAL_YEARS}")

    # Sweep configs
    hi_thresholds   = [33, 34, 35, 36, 37, 38, 39, 40, 41]
    wbgt_thresholds = [28, 29, 30, 31, 32, 33, 34]
    min_days_vals   = [1, 2, 3]

    rows = []
    wbgt_ref = None   # reference WBGT>=32°C/2days for kappa comparison

    for min_days in min_days_vals:
        # WBGT sweep
        for thr in wbgt_thresholds:
            hot = (df["wbgt"] >= thr).astype(int) if "wbgt" in df.columns else pd.Series(dtype=int)
            if hot.empty:
                continue
            labels = _mark_runs(hot, min_days)
            rec = {
                "method": "wbgt",
                "threshold": thr,
                "min_days": min_days,
                "positive_rate": round(100 * labels.mean(), 2),
                "mean_run_len": round(_mean_run_len(labels), 2),
                "pct_single_day": round(_pct_single(labels), 1),
            }
            if wbgt_ref is None and thr == 32 and min_days == 2:
                wbgt_ref = labels.copy()
            if wbgt_ref is not None:
                rec["cohen_kappa_vs_wbgt32"] = round(_cohen_kappa(labels, wbgt_ref), 3)
            rows.append(rec)

        # HI sweep
        for thr in hi_thresholds:
            hot = (df["heat_index"] >= thr).astype(int) if "heat_index" in df.columns else pd.Series(dtype=int)
            if hot.empty:
                continue
            labels = _mark_runs(hot, min_days)
            rec = {
                "method": "heat_index",
                "threshold": thr,
                "min_days": min_days,
                "positive_rate": round(100 * labels.mean(), 2),
                "mean_run_len": round(_mean_run_len(labels), 2),
                "pct_single_day": round(_pct_single(labels), 1),
            }
            if wbgt_ref is not None:
                rec["cohen_kappa_vs_wbgt32"] = round(_cohen_kappa(labels, wbgt_ref), 3)
            rows.append(rec)

    df_out = pd.DataFrame(rows)
    df_out.to_csv(OUTPUT_DIR / "label_sensitivity.csv", index=False)

    print("\n=== WBGT threshold sweep (min_days=2) ===")
    mask = (df_out["method"] == "wbgt") & (df_out["min_days"] == 2)
    print(df_out[mask][["threshold", "positive_rate", "mean_run_len", "pct_single_day",
                          "cohen_kappa_vs_wbgt32"]].to_string(index=False))

    print("\n=== HI threshold sweep (min_days=2) ===")
    mask = (df_out["method"] == "heat_index") & (df_out["min_days"] == 2)
    print(df_out[mask][["threshold", "positive_rate", "mean_run_len", "pct_single_day",
                          "cohen_kappa_vs_wbgt32"]].to_string(index=False))

    print(f"\nSaved: {OUTPUT_DIR}/label_sensitivity.csv")

    wbgt_thr = cfg.get("heatwave_label", {}).get("wbgt", {}).get("threshold_c", 32.0)
    _plot_label_sensitivity(df_out, wbgt_thr)
    return df_out


def _plot_label_sensitivity(df_out: pd.DataFrame, current_wbgt_thr: float = 32.0) -> None:
    """Heatwave positive rate vs threshold for WBGT and HI, current threshold marked."""
    try:
        import matplotlib
        matplotlib.use("Agg")
        import matplotlib.pyplot as plt
    except ImportError:
        print("  [plot] matplotlib not installed — skipping label sensitivity plot")
        return

    plots_dir = OUTPUT_DIR / "plots"
    plots_dir.mkdir(parents=True, exist_ok=True)

    fig, ax = plt.subplots(figsize=(9, 5))

    for method, color, label in [
        ("wbgt",        "#4e79a7", "WBGT"),
        ("heat_index",  "#f28e2b", "Heat Index"),
    ]:
        subset = df_out[(df_out["method"] == method) & (df_out["min_days"] == 2)]
        if subset.empty:
            continue
        ax.plot(subset["threshold"], subset["positive_rate"],
                marker="o", color=color, label=label, linewidth=2, markersize=5)

    # Mark current WBGT threshold
    wbgt_row = df_out[
        (df_out["method"] == "wbgt") &
        (df_out["threshold"] == current_wbgt_thr) &
        (df_out["min_days"] == 2)
    ]
    if not wbgt_row.empty:
        rate = wbgt_row["positive_rate"].iloc[0]
        ax.axvline(current_wbgt_thr, color="#d73027", linestyle="--", linewidth=1.5,
                   label=f"Current WBGT thr = {current_wbgt_thr}°C ({rate:.1f}%)")
        ax.axhline(rate, color="#d73027", linestyle=":", linewidth=1, alpha=0.6)

    # Target zone
    ax.axhspan(3, 8, alpha=0.08, color="green", label="Target zone 3–8%")
    ax.axhspan(1, 3, alpha=0.06, color="orange")
    ax.axhspan(8, 15, alpha=0.06, color="orange")

    ax.set_xlabel("Threshold (°C)", fontsize=10)
    ax.set_ylabel("Heatwave positive rate (%)", fontsize=10)
    ax.set_title("Label sensitivity: positive rate vs threshold (min_days=2)\n"
                 "Green band = target 3–8%, Orange = caution, outside = too rare/common", fontsize=9)
    ax.legend(fontsize=8)
    ax.grid(True, alpha=0.3)
    plt.tight_layout()
    out = plots_dir / "label_sensitivity.png"
    fig.savefig(out, dpi=120, bbox_inches="tight")
    plt.close(fig)
    print(f"  [plot] Saved: {out}")


if __name__ == "__main__":
    run()
