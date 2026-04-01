"""
prediction/predict.py
CLI entry point for running predictions with a trained model.

Usage:
    python prediction/predict.py --model xgboost --input data/processed/sample.csv
    python prediction/predict.py --model lightgbm --input new_data.csv --output results.csv
"""
import os
import sys
import argparse
import logging
import pandas as pd

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from prediction.predictor import Predictor, MODEL_REGISTRY

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger(__name__)


def parse_args():
    parser = argparse.ArgumentParser(
        description="HEATWAVE-AI — Prediction CLI",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=f"Available models: {', '.join(MODEL_REGISTRY.keys())}",
    )
    parser.add_argument("--model", required=True,
                        help="Model to use (e.g. xgboost, lightgbm, kan, mlp, balanced_rf)")
    parser.add_argument("--input", required=True,
                        help="Path to input CSV file")
    parser.add_argument("--output", default=None,
                        help="Optional path to save prediction CSV")
    parser.add_argument("--config", default="config/config.yaml",
                        help="Config file path (default: config/config.yaml)")
    parser.add_argument("--proba", action="store_true",
                        help="Also output class probabilities")
    return parser.parse_args()


def main():
    args = parse_args()

    # Load input
    if not os.path.isfile(args.input):
        print(f"❌ Input file not found: {args.input}")
        sys.exit(1)

    print(f"\n{'=' * 50}")
    print(f"  HEATWAVE-AI  |  Prediction")
    print(f"{'=' * 50}")
    print(f"  Model : {args.model}")
    print(f"  Input : {args.input}")

    try:
        df = pd.read_csv(args.input)
        print(f"  Rows  : {len(df):,}")
    except Exception as e:
        print(f"❌ Could not read CSV: {e}")
        sys.exit(1)

    # Run prediction
    predictor = Predictor(config_path=args.config)
    try:
        predictions = predictor.predict(args.model, df)
    except FileNotFoundError as e:
        print(f"\n❌ {e}")
        sys.exit(1)
    except Exception as e:
        print(f"\n❌ Prediction failed: {e}")
        sys.exit(1)

    # Display results
    print(f"\n{'=' * 50}")
    print(f"  Prediction Results")
    print(f"  Model: {args.model.upper()}")
    print(f"  Predicted Labels:")
    print(f"  {predictions.tolist()}")

    unique, counts = _count_classes(predictions)
    for label, count in zip(unique, counts):
        pct = 100 * count / len(predictions)
        name = "Heatwave" if label == 1 else "No heatwave"
        print(f"    {name} ({label}): {count} ({pct:.1f}%)")

    if args.proba:
        probas = predictor.predict_proba(args.model, df)
        print(f"\n  Probabilities (positive class):")
        print(f"  {[round(float(p), 4) for p in probas[:20]]}{'...' if len(probas) > 20 else ''}")

    # Save output if requested
    if args.output:
        out_df = df.copy()
        out_df["predicted_heatwave"] = predictions
        if args.proba:
            out_df["heatwave_probability"] = predictor.predict_proba(args.model, df)
        out_df.to_csv(args.output, index=False)
        print(f"\n  Saved to: {args.output}")

    print(f"{'=' * 50}\n")


def _count_classes(arr):
    import numpy as np
    unique, counts = np.unique(arr, return_counts=True)
    return unique, counts


if __name__ == "__main__":
    main()
