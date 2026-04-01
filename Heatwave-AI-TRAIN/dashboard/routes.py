"""
dashboard/routes.py
API and page routes for the HEATWAVE-AI dashboard.
"""
import os
import json
import math
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from flask import Blueprint, render_template, jsonify, current_app
from evaluation.benchmark import Benchmark


def _sanitize(obj):
    """Recursively replace float NaN/Inf with None so jsonify produces valid JSON."""
    if isinstance(obj, list):
        return [_sanitize(v) for v in obj]
    if isinstance(obj, dict):
        return {k: _sanitize(v) for k, v in obj.items()}
    if isinstance(obj, float) and (math.isnan(obj) or math.isinf(obj)):
        return None
    return obj

bp = Blueprint("main", __name__)


def _get_results_dir():
    try:
        import yaml
        config_path = current_app.config.get("CONFIG_PATH", "config/config.yaml")
        with open(config_path, encoding="utf-8") as f:
            cfg = yaml.safe_load(f)
        return cfg["experiments"]["results_dir"]
    except Exception:
        return "experiments/results"


@bp.route("/")
def index():
    return render_template("index.html")


@bp.route("/api/leaderboard")
def leaderboard():
    results_dir = _get_results_dir()
    bench = Benchmark(results_dir)
    records = bench.get_leaderboard_json()
    return jsonify(_sanitize(records))


@bp.route("/api/results")
def all_results():
    results_dir = _get_results_dir()
    results = []
    if os.path.isdir(results_dir):
        for fname in os.listdir(results_dir):
            if fname.endswith(".json") and fname != "leaderboard.json":
                try:
                    with open(os.path.join(results_dir, fname)) as f:
                        results.append(json.load(f))
                except Exception:
                    pass
    return jsonify(_sanitize(results))


@bp.route("/api/best")
def best_model():
    results_dir = _get_results_dir()
    bench = Benchmark(results_dir)
    records = bench.get_leaderboard_json()
    if records:
        return jsonify(_sanitize(records[0]))
    return jsonify({"message": "No results yet. Run training first."}), 404


@bp.route("/api/status")
def status():
    return jsonify({"status": "running", "service": "HEATWAVE-AI Dashboard"})
