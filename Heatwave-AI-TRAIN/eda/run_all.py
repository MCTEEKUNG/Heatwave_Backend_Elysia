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

    train_years = cfg["split"].get("train_years", "N/A")
    val_years   = cfg["split"].get("val_years",   "N/A")
    label_method = cfg.get("heatwave_label", {}).get("method", "N/A")
    wbgt_thr     = cfg.get("heatwave_label", {}).get("wbgt", {}).get("threshold_c", "N/A")

    ok_count  = sum(1 for r in results if r["status"] == "ok")
    err_count = len(results) - ok_count

    lines = [
        "# Heatwave-AI EDA Report",
        "",
        "## Configuration",
        f"- **Heatwave label**: `{label_method}`",
        f"- **WBGT threshold**: {wbgt_thr} °C",
        f"- **Train years**: {train_years}",
        f"- **Val years**: {val_years}",
        "",
        "## Step Results",
        "",
        "| Step | Status | Time (s) |",
        "|------|--------|----------|",
    ]
    for r in results:
        icon = "✅" if r["status"] == "ok" else "❌"
        lines.append(f"| {r['step']} | {icon} {r['status']} | {r['elapsed_s']} |")

    lines += [
        "",
        f"**Summary**: {ok_count}/{len(results)} steps passed.",
        "",
        "## Key Outputs",
        "",
        f"- `experiments/eda/coverage_matrix.csv` — data presence per year",
        f"- `experiments/eda/distribution_summary.csv` — per-year stats",
        f"- `experiments/eda/climatology_2000_2019.nc` — percentile baseline",
        f"- `experiments/eda/drift_report.csv` — 2025 vs 2020-2024 PSI/KS",
        f"- `experiments/eda/label_sensitivity.csv` — threshold sweep results",
        f"- `experiments/eda/spatial_summary.csv` — per-cell annual stats",
        f"- `experiments/eda/maps/spatial_maps.png` — visual map (if matplotlib installed)",
        "",
        "## Action Items",
        "",
        "- If `drift_report.csv` shows PSI > 0.25 for any feature: investigate why "
        "2025 differs before using it as val set.",
        "- If `coverage_matrix.csv` shows `completeness_pct` < 90 for any year: "
        "decide whether to exclude that year from training.",
        "- Review `label_sensitivity.csv` to confirm WBGT ≥ 32°C / 2 days gives "
        "a 3–8% positive rate for your region. Adjust if needed.",
    ]

    report_path.write_text("\n".join(lines), encoding="utf-8")
    print(f"\nReport saved: {report_path}")


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
