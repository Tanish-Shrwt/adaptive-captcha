"""
config.py — all project-wide constants.
Import from here instead of scattering magic values across files.
"""

import os

# ── Folders ───────────────────────────────────────────
BASE_DIR        = os.path.dirname(__file__)
CAPTCHA_FOLDER  = "static/captcha_images"
MATH_FOLDER     = "static/math_captcha"
ROTATION_FOLDER = "static/rotation_captcha"
LABELS_PATH     = "static/tile_captcha/labels.json"
DB_PATH         = "access_log.db"

FONT_PATH = "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"
FONT_FALLBACKS = [
    "/usr/share/fonts/truetype/liberation/LiberationSans-Bold.ttf",
    "/usr/share/fonts/truetype/freefont/FreeSansBold.ttf",
]

# ── Demo credentials ──────────────────────────────────
DEMO_USERS = {
    "admin":   "password123",
    "student": "captcha2024",
}

# ── CAPTCHA difficulty ladder ─────────────────────────
# Each tuple: (max_score, captcha_type, risk_label, display_name)
# The first entry whose max_score >= current score is used.
LADDER = [
    (3,   "text",     "Low",      "Text CAPTCHA"),
    (6,   "math",     "Low-Med",  "Math CAPTCHA"),
    (10,  "tile",     "Medium",   "Tile CAPTCHA"),
    (14,  "drag",     "High",     "Drag-to-Match"),
    (999, "rotation", "Critical", "Rotation CAPTCHA"),
]

# ── Rotation tolerance ────────────────────────────────
# Bumped from 18° to 25° — a slider is imprecise; humans need more margin.
ROTATION_TOLERANCE = 25   # degrees — user must be within ±25° of correct

# ── Drag shapes ───────────────────────────────────────
DRAG_SHAPES = ["circle", "square", "triangle", "star", "diamond", "hexagon"]