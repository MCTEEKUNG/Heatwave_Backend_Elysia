"""
dashboard/app.py
Flask application factory for the HEATWAVE-AI dashboard.
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from flask import Flask
from dashboard.routes import bp


def create_app(config_path: str = "config/config.yaml") -> Flask:
    app = Flask(
        __name__,
        template_folder=os.path.join(os.path.dirname(__file__), "templates"),
        static_folder=os.path.join(os.path.dirname(__file__), "static"),
    )
    app.config["CONFIG_PATH"] = config_path
    app.register_blueprint(bp)
    return app


if __name__ == "__main__":
    import yaml
    with open("config/config.yaml", encoding="utf-8") as f:
        cfg = yaml.safe_load(f)
    dash = cfg.get("dashboard", {})
    app = create_app()
    print(f"\n  Dashboard running at: http://localhost:{dash.get('port', 5000)}\n")
    app.run(
        host=dash.get("host", "0.0.0.0"),
        port=dash.get("port", 5000),
        debug=dash.get("debug", False),
    )
