"""
main.py
Unified entry point for the HEATWAVE-AI-Prediction system.

Usage:
    python main.py --mode train       # Run full training pipeline
    python main.py --mode dashboard   # Launch web dashboard
    python main.py --mode predict --model xgboost --input data.csv
"""
import os
import sys
import argparse
import logging

# ── Ensure project root in path ──────────────────────────────────
ROOT = os.path.dirname(os.path.abspath(__file__))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s"
)
logger = logging.getLogger(__name__)


def parse_args():
    parser = argparse.ArgumentParser(
        description="HEATWAVE-AI — Unified Entry Point",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python main.py --mode train
  python main.py --mode dashboard
  python main.py --mode predict --model xgboost --input data/processed/sample.csv
        """
    )
    parser.add_argument(
        "--mode", required=True,
        choices=["train", "dashboard", "predict"],
        help="Operation mode"
    )
    parser.add_argument("--config", default="config/config.yaml",
                        help="Path to configuration file")
    # Train-specific
    parser.add_argument(
        "--models", default=None, nargs="+",
        metavar="MODEL",
        help=(
            "One or more models to train. "
            "Choices: balanced_rf xgboost lightgbm mlp kan. "
            "Default: all 5 models."
        )
    )
    # Predict-specific
    parser.add_argument("--model", default=None,
                        help="Model name for prediction (e.g. xgboost, lightgbm, kan, mlp, balanced_rf)")
    parser.add_argument("--input", default=None,
                        help="Input CSV path for prediction")
    parser.add_argument("--output", default=None,
                        help="Output CSV path to save predictions")
    parser.add_argument("--proba", action="store_true",
                        help="Include class probabilities in prediction output")
    return parser.parse_args()


def run_training(config_path: str, selected_models: list = None):
    from pipelines.training_pipeline import TrainingPipeline
    pipeline = TrainingPipeline(config_path)
    pipeline.run(selected_models=selected_models)


def run_dashboard(config_path: str):
    import yaml
    with open(config_path, encoding="utf-8") as f:
        cfg = yaml.safe_load(f)
    dash = cfg.get("dashboard", {})

    from dashboard.app import create_app
    app = create_app(config_path)
    port = dash.get("port", 5000)
    print(f"\n  Dashboard running at: http://localhost:{port}")
    print("  Press Ctrl+C to stop.\n")
    app.run(
        host=dash.get("host", "0.0.0.0"),
        port=port,
        debug=dash.get("debug", False),
    )


def run_predict(args):
    # Re-use the predict.py CLI logic
    import sys
    sys.argv = ["predict.py", "--model", args.model, "--input", args.input]
    if args.output:
        sys.argv += ["--output", args.output]
    if args.proba:
        sys.argv.append("--proba")
    sys.argv += ["--config", args.config]
    from prediction.predict import main as predict_main
    predict_main()


def main():
    args = parse_args()

    if args.mode == "train":
        run_training(args.config, selected_models=args.models)

    elif args.mode == "dashboard":
        run_dashboard(args.config)

    elif args.mode == "predict":
        if not args.model or not args.input:
            print("❌ --model and --input are required for predict mode.")
            sys.exit(1)
        run_predict(args)


if __name__ == "__main__":
    main()
