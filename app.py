"""
app.py — application entry point.

Responsibilities:
  1. Create the Flask app
  2. Register blueprints
  3. Ensure static folders and DB table exist
  4. Run dev server

Nothing else lives here.  All logic is in:
  config.py          — constants
  database.py        — SQLite
  risk.py            — scoring
  captcha_engine.py  — CAPTCHA generation / validation
  routes/auth.py     — /login /logout /reset
  routes/dashboard.py — /dashboard /api/logs
"""

import os
from flask import Flask

from config   import CAPTCHA_FOLDER, MATH_FOLDER
from database import get_db
from routes.auth      import auth
from routes.dashboard import dashboard


def create_app() -> Flask:
    app = Flask(__name__)
    app.secret_key = "supersecretkey"

    # Ensure required static folders exist
    for folder in [CAPTCHA_FOLDER, MATH_FOLDER]:
        os.makedirs(folder, exist_ok=True)

    # Ensure DB table exists (idempotent)
    get_db().close()

    # Register blueprints
    app.register_blueprint(auth)
    app.register_blueprint(dashboard)

    return app


app = create_app()

if __name__ == "__main__":
    app.run(debug=True)