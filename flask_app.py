"""
Dashboard Flask pour la surveillance de l'API ipify.
Routes:
  /            -> dashboard principal avec historique des runs
  /run         -> déclenche manuellement un run de tests
  /api/runs    -> historique JSON (export)
  /api/last    -> dernier run JSON
  /health      -> healthcheck du service
"""

import json
import os
import sqlite3
from datetime import datetime

from flask import Flask, jsonify, render_template, redirect, url_for

# Import du runner
import sys
sys.path.insert(0, os.path.dirname(__file__))
from tests.runner import run_all, DB_PATH, init_db


app = Flask(__name__)


def get_runs(limit=50):
    """Récupère les derniers runs depuis SQLite."""
    init_db()
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    rows = conn.execute(
        "SELECT * FROM runs ORDER BY id DESC LIMIT ?", (limit,)
    ).fetchall()
    conn.close()
    return [dict(r) for r in rows]


@app.route("/")
def dashboard():
    runs = get_runs(limit=50)
    # Parser les détails JSON
    for r in runs:
        try:
            r["details_parsed"] = json.loads(r["details"])
        except Exception:
            r["details_parsed"] = []
    last_run = runs[0] if runs else None
    return render_template("dashboard.html", runs=runs, last_run=last_run)


@app.route("/run")
def trigger_run():
    """Lance un run de tests manuellement."""
    run_all()
    return redirect(url_for("dashboard"))


@app.route("/api/runs")
def api_runs():
    """Export JSON de l'historique."""
    runs = get_runs(limit=100)
    for r in runs:
        try:
            r["details"] = json.loads(r["details"])
        except Exception:
            pass
    return jsonify(runs)


@app.route("/api/last")
def api_last():
    """Dernier run au format JSON."""
    runs = get_runs(limit=1)
    if not runs:
        return jsonify({"message": "Aucun run encore exécuté."}), 404
    r = runs[0]
    try:
        r["details"] = json.loads(r["details"])
    except Exception:
        pass
    return jsonify(r)


@app.route("/health")
def health():
    """Healthcheck du service."""
    return jsonify({
        "status": "ok",
        "service": "ipify-monitor",
        "timestamp": datetime.now().isoformat(timespec="seconds")
    })


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=True)
