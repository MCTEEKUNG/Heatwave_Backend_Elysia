# -*- coding: utf-8 -*-
"""
eda/run_all.py
Run all EDA scripts in order and write a summary report.
Usage: python -m eda.run_all [--config config/config.yaml]
"""
import argparse
import json
import os
import sys
import time
from pathlib import Path

import pandas as pd

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

OUTPUT_DIR = Path("experiments/eda")

STEPS = [
    ("01 Data coverage",        "eda.data_coverage"),
    ("02 Distribution summary", "eda.distribution_summary"),
    ("03 Climatology 2000-2019","eda.climatology_2000_2019"),
    ("04 Year drift 2025",      "eda.year_drift"),
    ("05 Label quality sweep",  "eda.label_quality"),
    ("06 Spatial maps",         "eda.spatial_maps"),
]


def _run_step(name: str, module: str, config_path: str) -> dict:
    import importlib
    print(f"\n{'='*60}")
    print(f"  {name}")
    print(f"{'='*60}")
    t0 = time.time()
    try:
        mod = importlib.import_module(module)
        mod.run(config_path)
        elapsed = round(time.time() - t0, 1)
        print(f"  Done in {elapsed}s")
        return {"step": name, "status": "ok", "elapsed_s": elapsed}
    except Exception as exc:
        elapsed = round(time.time() - t0, 1)
        print(f"  FAILED: {exc}")
        return {"step": name, "status": "error", "error": str(exc), "elapsed_s": elapsed}


def _write_report(results: list, config_path: str) -> None:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    report_path = OUTPUT_DIR / "eda_report.md"

    import yaml
    with open(config_path, encoding="utf-8") as f:
        cfg = yaml.safe_load(f)

    train_years  = cfg["split"].get("train_years", "N/A")
    val_years    = cfg["split"].get("val_years",   "N/A")
    label_method = cfg.get("heatwave_label", {}).get("method", "N/A")
    wbgt_thr     = cfg.get("heatwave_label", {}).get("wbgt", {}).get("threshold_c", 32.0)

    ok_count  = sum(1 for r in results if r["status"] == "ok")
    err_count = len(results) - ok_count

    # ── Parse output files for embedded numbers ────────────────────────────
    verdict, verdict_reasons = _compute_verdict(wbgt_thr)
    coverage_table  = _read_coverage_table()
    drift_table     = _read_drift_table()
    label_rate_line = _read_label_rate(wbgt_thr)

    # ── Build report ───────────────────────────────────────────────────────
    lines = [
        "# Heatwave-AI EDA Report",
        "",
        f"## {verdict}",
        "",
    ]
    if verdict_reasons:
        for reason in verdict_reasons:
            lines.append(f"- {reason}")
        lines.append("")
    else:
        lines += ["All checks passed — proceed to training.", ""]

    lines += [
        "## Configuration",
        "",
        f"| Setting | Value |",
        f"|---------|-------|",
        f"| Heatwave label method | `{label_method}` |",
        f"| WBGT threshold | {wbgt_thr} °C |",
        f"| Train years | {train_years} |",
        f"| Val years | {val_years} |",
        f"| Climatology baseline | 2000–2019 (EHF percentiles only) |",
        "",
        "## Step Results",
        "",
        "| Step | Status | Time (s) |",
        "|------|--------|----------|",
    ]
    for r in results:
        icon = "✅" if r["status"] == "ok" else "❌"
        lines.append(f"| {r['step']} | {icon} {r['status']} | {r['elapsed_s']} |")

    lines += ["", f"**Summary**: {ok_count}/{len(results)} steps passed.", ""]

    if coverage_table:
        lines += ["## Data Coverage", "", coverage_table, ""]

    if drift_table:
        lines += [
            "## Distribution Drift (2025 vs 2020–2024)",
            "",
            "> PSI < 0.1 = Stable  |  0.1–0.25 = Minor shift  |  > 0.25 = Significant shift",
            "",
            drift_table,
            "",
        ]

    if label_rate_line:
        lines += ["## Label Quality", "", label_rate_line, ""]

    lines += [
        "## Plots",
        "",
        "| Plot | Path |",
        "|------|------|",
        "| Coverage heatmap | `experiments/eda/plots/coverage_heatmap.png` |",
        "| Drift histograms | `experiments/eda/plots/drift_histograms.png` |",
        "| Label sensitivity | `experiments/eda/plots/label_sensitivity.png` |",
        "| Climatology seasonal | `experiments/eda/plots/climatology_seasonal.png` |",
        "| Spatial maps | `experiments/eda/maps/spatial_maps.png` |",
        "",
        "## Action Items",
        "",
        "- **Coverage < 90%**: exclude that year from training or investigate missing files.",
        "- **PSI > 0.25**: 2025 is significantly out-of-distribution — "
        "investigate before using as validation year.",
        "- **Label rate < 3% or > 15%**: adjust WBGT threshold or `min_consecutive_days`.",
        "",
        "## Glossary",
        "",
        "| Term | Plain-language meaning |",
        "|------|------------------------|",
        "| **PSI** (Population Stability Index) | Measures how much a feature's distribution "
        "changed between training and validation — < 0.1 is stable, > 0.25 is a red flag. |",
        "| **KS p-value** | Probability that two distributions are the same — "
        "p < 0.05 means they are statistically different. |",
        "| **Cohen's kappa** | Agreement between two labeling methods beyond chance — "
        "0 = no agreement, 1 = perfect agreement, > 0.6 is considered good. |",
        "| **Positive rate** | Fraction of days labeled as heatwave — "
        "target is 3–8% for a balanced model. |",
        "| **WBGT** | Wet-Bulb Globe Temperature — combines heat and humidity "
        "into one number used by Thailand MoPH for occupational heat-stress risk. |",
        "| **EHF** | Excess Heat Factor — flags heat waves that are 'unusually hot "
        "for this location' based on a 20-year historical baseline (2000–2019). |",
    ]

    report_path.write_text("\n".join(lines), encoding="utf-8")
    print(f"\nReport saved: {report_path}")


# ── Verdict helpers ────────────────────────────────────────────────────────

def _compute_verdict(wbgt_thr: float) -> tuple:
    """Return (verdict_string, list_of_reason_strings) from parsed CSV outputs."""
    reasons = []
    level = "green"   # green | yellow | red

    # 1. Coverage check
    cov_path = OUTPUT_DIR / "coverage_matrix.csv"
    if cov_path.exists():
        try:
            cov = pd.read_csv(cov_path)
            if "completeness_pct" in cov.columns:
                low = cov[cov["completeness_pct"] < 70]
                mid = cov[(cov["completeness_pct"] >= 70) & (cov["completeness_pct"] < 90)]
                if not low.empty:
                    level = "red"
                    for _, row in low.iterrows():
                        reasons.append(
                            f"🔴 Coverage {row['completeness_pct']:.0f}% for year "
                            f"{int(row['year'])} — below 70%, consider excluding."
                        )
                elif not mid.empty:
                    if level == "green":
                        level = "yellow"
                    for _, row in mid.iterrows():
                        reasons.append(
                            f"🟡 Coverage {row['completeness_pct']:.0f}% for year "
                            f"{int(row['year'])} — below 90%, review before training."
                        )
        except Exception:
            pass

    # 2. Drift check
    drift_path = OUTPUT_DIR / "drift_report.csv"
    if drift_path.exists():
        try:
            dr = pd.read_csv(drift_path)
            sig = dr[dr["psi"] > 0.25] if "psi" in dr.columns else pd.DataFrame()
            minor = dr[(dr["psi"] >= 0.1) & (dr["psi"] <= 0.25)] if "psi" in dr.columns else pd.DataFrame()
            if not sig.empty:
                level = "red"
                for _, row in sig.iterrows():
                    reasons.append(
                        f"🔴 PSI = {row['psi']:.3f} for `{row['feature']}` → "
                        f"SIGNIFICANT_SHIFT — 2025 may not be a fair held-out year."
                    )
            elif not minor.empty:
                if level == "green":
                    level = "yellow"
                for _, row in minor.iterrows():
                    reasons.append(
                        f"🟡 PSI = {row['psi']:.3f} for `{row['feature']}` → "
                        f"minor shift — monitor but proceed."
                    )
        except Exception:
            pass

    # 3. Label rate check
    label_path = OUTPUT_DIR / "label_sensitivity.csv"
    if label_path.exists():
        try:
            lb = pd.read_csv(label_path)
            row = lb[
                (lb["method"] == "wbgt") &
                (lb["threshold"] == wbgt_thr) &
                (lb["min_days"] == 2)
            ]
            if not row.empty:
                rate = row["positive_rate"].iloc[0]
                if rate < 1.0 or rate > 15.0:
                    level = "red"
                    reasons.append(
                        f"🔴 Label positive rate = {rate:.1f}% at WBGT ≥ {wbgt_thr}°C / 2 days — "
                        "outside safe range [1%, 15%]. Adjust threshold."
                    )
                elif rate < 3.0 or rate > 8.0:
                    if level == "green":
                        level = "yellow"
                    reasons.append(
                        f"🟡 Label positive rate = {rate:.1f}% at WBGT ≥ {wbgt_thr}°C / 2 days — "
                        "outside target [3%, 8%]. Consider tuning threshold."
                    )
                else:
                    reasons.append(
                        f"🟢 Label positive rate = {rate:.1f}% at WBGT ≥ {wbgt_thr}°C / 2 days — "
                        "within target [3%, 8%]."
                    )
        except Exception:
            pass

    emoji = {"green": "🟢", "yellow": "🟡", "red": "🔴"}[level]
    label_map = {"green": "READY TO TRAIN", "yellow": "CAUTION — review before training",
                 "red": "DO NOT TRAIN — fix issues first"}
    return f"{emoji} {label_map[level]}", reasons


def _read_coverage_table() -> str:
    path = OUTPUT_DIR / "coverage_matrix.csv"
    if not path.exists():
        return ""
    try:
        df = pd.read_csv(path)
        cols = ["year", "file_exists", "granularity", "completeness_pct", "time_gaps"]
        df = df[[c for c in cols if c in df.columns]]
        lines = ["| " + " | ".join(str(c) for c in df.columns) + " |",
                 "| " + " | ".join(["---"] * len(df.columns)) + " |"]
        for _, row in df.iterrows():
            lines.append("| " + " | ".join(str(v) for v in row.values) + " |")
        return "\n".join(lines)
    except Exception:
        return ""


def _read_drift_table() -> str:
    path = OUTPUT_DIR / "drift_report.csv"
    if not path.exists():
        return ""
    try:
        df = pd.read_csv(path)
        cols = ["feature", "train_mean", "val_mean", "mean_diff", "psi", "ks_p", "status"]
        df = df[[c for c in cols if c in df.columns]]
        lines = ["| " + " | ".join(str(c) for c in df.columns) + " |",
                 "| " + " | ".join(["---"] * len(df.columns)) + " |"]
        for _, row in df.iterrows():
            lines.append("| " + " | ".join(str(v) for v in row.values) + " |")
        return "\n".join(lines)
    except Exception:
        return ""


def _read_label_rate(wbgt_thr: float) -> str:
    path = OUTPUT_DIR / "label_sensitivity.csv"
    if not path.exists():
        return ""
    try:
        df = pd.read_csv(path)
        row = df[(df["method"] == "wbgt") & (df["threshold"] == wbgt_thr) & (df["min_days"] == 2)]
        if row.empty:
            return ""
        r = row.iloc[0]
        return (f"WBGT ≥ {wbgt_thr}°C / 2 days → **{r['positive_rate']:.1f}%** positive rate, "
                f"mean run length = {r.get('mean_run_len', '?')} days.")
    except Exception:
        return ""


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", default="config/config.yaml")
    parser.add_argument("--steps", nargs="*", help="Run specific steps by 1-based index")
    args = parser.parse_args()

    steps = STEPS
    if args.steps:
        indices = [int(i) - 1 for i in args.steps]
        steps = [STEPS[i] for i in indices if 0 <= i < len(STEPS)]

    print(f"Running {len(steps)} EDA steps against {args.config}")
    results = [_run_step(name, mod, args.config) for name, mod in steps]
    _write_report(results, args.config)

    errors = [r for r in results if r["status"] == "error"]
    if errors:
        print(f"\n{len(errors)} step(s) failed:")
        for r in errors:
            print(f"  - {r['step']}: {r.get('error')}")
        sys.exit(1)
    print("\nAll EDA steps completed successfully.")


if __name__ == "__main__":
    main()
