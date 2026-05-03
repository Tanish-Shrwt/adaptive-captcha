"""
routes/dashboard.py — /dashboard, /api/logs
"""

from flask import Blueprint, render_template, session, redirect, url_for, jsonify
from database import fetch_logs, fetch_stats

dashboard = Blueprint("dashboard", __name__)


@dashboard.route("/dashboard")
def dashboard_view():
    if not session.get("logged_in"):
        return redirect(url_for("auth.login"))

    stats = fetch_stats()
    logs  = fetch_logs(50)

    return render_template(
        "dashboard.html",
        username = session.get("username", "user"),
        logs     = logs,
        total    = stats.get("total",  0) or 0,
        bots     = stats.get("bots",   0) or 0,
        humans   = stats.get("humans", 0) or 0,
        success  = stats.get("success",0) or 0,
        denied   = stats.get("denied", 0) or 0,
    )


@dashboard.route("/api/logs")
def api_logs():
    if not session.get("logged_in"):
        return jsonify({"error": "unauthorized"}), 401
    return jsonify(fetch_logs(200))