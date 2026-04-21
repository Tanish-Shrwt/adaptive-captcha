from flask import Flask, render_template, request, session
from captcha.image import ImageCaptcha
import random
import string
import os
import time
import json
import cv2
import numpy as np

app = Flask(__name__)
app.secret_key = "supersecretkey"

CAPTCHA_FOLDER = "static/captcha_images"
LABELS_PATH    = "static/tile_captcha/labels.json"

if not os.path.exists(CAPTCHA_FOLDER):
    os.makedirs(CAPTCHA_FOLDER)


# =======================================
# RISK THRESHOLDS
# Easy  : score 0–3   → character CAPTCHA, no distortion
# Medium: score 4–7   → character CAPTCHA, noise + lines
# High  : score 8+    → tile CAPTCHA (traffic lights / buses)
# =======================================
def get_difficulty(score):
    if score <= 3:
        return "easy", "Low"
    elif score <= 7:
        return "medium", "Medium"
    else:
        return "hard", "High"


# =======================================
# Normalise any image to a fixed 600×600
# square before slicing into 3×3 tiles.
# =======================================
def preprocess_image(image_path, size=600):
    img = cv2.imread(image_path)
    if img is None:
        raise FileNotFoundError(f"Could not read image: {image_path}")

    h, w = img.shape[:2]
    scale = size / min(h, w)
    new_w = int(w * scale)
    new_h = int(h * scale)
    img = cv2.resize(img, (new_w, new_h), interpolation=cv2.INTER_AREA)

    top  = (new_h - size) // 2
    left = (new_w - size) // 2
    img  = img[top:top + size, left:left + size]
    return img


# =======================================
# Generate character CAPTCHA image
# =======================================
def generate_captcha(difficulty="easy"):
    image = ImageCaptcha(width=280, height=90)
    captcha_text = "".join(
        random.choices(string.ascii_uppercase + string.digits, k=6)
    )

    timestamp  = int(time.time() * 1000)
    filename   = f"captcha_{timestamp}.png"
    image_path = os.path.join(CAPTCHA_FOLDER, filename)

    for old in os.listdir(CAPTCHA_FOLDER):
        os.remove(os.path.join(CAPTCHA_FOLDER, old))

    image.write(captcha_text, image_path)
    img = cv2.imread(image_path)

    if difficulty == "medium":
        img = add_noise(img, 35)
        img = add_lines(img, 3)
    elif difficulty == "hard":
        img = add_noise(img, 70)
        img = add_lines(img, 7)
        img = cv2.GaussianBlur(img, (5, 5), 0)

    cv2.imwrite(image_path, img)

    session["captcha_text"] = captcha_text
    session["captcha_file"] = filename
    session["difficulty"]   = difficulty

    return captcha_text, filename


def add_noise(img, amount):
    noise = np.random.randint(0, amount, img.shape, dtype="uint8")
    return cv2.add(img, noise)


def add_lines(img, count):
    h, w, _ = img.shape
    for _ in range(count):
        x1, y1 = random.randint(0, w), random.randint(0, h)
        x2, y2 = random.randint(0, w), random.randint(0, h)
        color = (
            random.randint(0, 255),
            random.randint(0, 255),
            random.randint(0, 255),
        )
        cv2.line(img, (x1, y1), (x2, y2), color, 2)
    return img


# =======================================
# Bot behavior scoring
# =======================================
def calculate_risk(mouse_moves, clicks, typing_time, time_spent, failures):
    risk = 0

    # Strong bot signals
    if mouse_moves == 0:
        risk += 3
    if typing_time < 50 and typing_time > 0:
        risk += 3
    if time_spent < 300:
        risk += 3

    # Medium signals
    if 0 < mouse_moves < 5:
        risk += 2
    if 50 <= typing_time < 150:
        risk += 2

    # Weak signals
    if clicks > 15:
        risk += 1
    if 300 <= time_spent < 700:
        risk += 1

    # Combo bonus — all three strong signals together
    if mouse_moves == 0 and typing_time < 50 and time_spent < 300:
        risk += 5

    risk += failures * 2
    return risk


def calculate_bot_probability(risk_score):
    probability = min(100.0, (risk_score / 15) * 100)
    return float(round(probability, 2))


# =======================================
# Load labels.json
#
# Supports NESTED format:
# {
#   "traffic-lights": {
#     "img1.jpeg": [1, 2],
#     "img10.jpg": [4]
#   },
#   "buses": {
#     "bus_img1.jpg": [4, 5]
#   }
# }
# =======================================
def load_labels():
    if not os.path.exists(LABELS_PATH):
        return {}
    with open(LABELS_PATH, "r") as f:
        return json.load(f)


# =======================================
# Slice one tile-CAPTCHA image into 3×3
# =======================================
def create_tiles(category="traffic-lights"):
    folder = f"static/tile_captcha/{category}"
    labels = load_labels()

    # FIX: nested lookup — labels["traffic-lights"]["img1.jpeg"] = [1, 2]
    category_labels = labels.get(category, {})

    if not category_labels:
        raise RuntimeError(
            f"No labelled images found for category '{category}' in {LABELS_PATH}."
        )

    available = [
        img for img in category_labels.keys()
        if os.path.exists(os.path.join(folder, img))
    ]

    if not available:
        raise RuntimeError(
            f"Labels exist for '{category}' but no matching image files found in {folder}."
        )

    image_name = random.choice(available)
    image_path = os.path.join(folder, image_name)

    img       = preprocess_image(image_path, size=600)
    tile_size = 200

    tile_folder = "static/tiles"
    os.makedirs(tile_folder, exist_ok=True)
    for f in os.listdir(tile_folder):
        os.remove(os.path.join(tile_folder, f))

    tiles = []
    for idx in range(9):
        i, j = divmod(idx, 3)
        tile = img[
            i * tile_size : (i + 1) * tile_size,
            j * tile_size : (j + 1) * tile_size,
        ]
        name = f"tile{idx}.jpg"
        cv2.imwrite(os.path.join(tile_folder, name), tile)
        tiles.append(name)

    # FIX: two-level lookup for nested labels.json
    correct = category_labels.get(image_name, [])
    session["correct_tiles"] = sorted(correct)
    session["tile_category"] = category
    session["tile_image"]    = image_name

    return tiles


# =======================================
# Main route
# =======================================
@app.route("/", methods=["GET", "POST"])
def index():

    session.setdefault("risk_score",     0)
    session.setdefault("correct_streak", 0)
    session.setdefault("attempts",       0)

    score = session["risk_score"]
    difficulty, risk_level = get_difficulty(score)
    message = ""

    # ==========================================
    # POST — user submitted a CAPTCHA answer
    # ==========================================
    if request.method == "POST":
        captcha_type = request.form.get("captcha_type", "character")

        mouse_moves = int(request.form.get("mouse_moves",  0))
        clicks      = int(request.form.get("clicks",       0))
        typing_time = int(request.form.get("typing_time",  0))
        time_spent  = int(request.form.get("time_spent",   0))

        behavior_risk = calculate_risk(
            mouse_moves, clicks, typing_time, time_spent,
            session["attempts"]
        )
        session["risk_score"] += behavior_risk

        # ── Character CAPTCHA ──────────────────
        if captcha_type == "character":
            user_input = request.form.get("captcha_input", "").strip().upper()
            correct    = session.get("captcha_text", "")

            if user_input == correct:
                message = "✅ Correct! CAPTCHA passed."
                session["correct_streak"] += 1
                session["attempts"]        = 0
                session["risk_score"]     -= 2
                if session["correct_streak"] >= 3:
                    session["risk_score"] -= 1
            else:
                message = "❌ Incorrect CAPTCHA. Try again."
                session["attempts"]       += 1
                session["correct_streak"]  = 0
                session["risk_score"]     += 3

        # ── Tile CAPTCHA ───────────────────────
        elif captcha_type == "tile":
            raw = request.form.get("selected_tiles", "")
            try:
                selected = sorted([int(x) for x in raw.split(",") if x.strip()])
            except ValueError:
                selected = []

            correct_tiles = sorted(session.get("correct_tiles", []))

            if selected == correct_tiles:
                message = "✅ Correct tiles selected!"
                session["correct_streak"] += 1
                session["attempts"]        = 0
                # FIX: a correct tile solve drops risk aggressively enough
                #      to actually exit "hard" mode (score ≥ 8).
                #      Previously -2 barely moved a score of 56.
                #      Now: cut score in half, then subtract 4 more,
                #      capped at 0. This guarantees transition to medium/easy.
                session["risk_score"] = max(0, session["risk_score"] // 2 - 4)
            else:
                message = "❌ Wrong tiles. Try again."
                session["attempts"]       += 1
                session["correct_streak"]  = 0
                session["risk_score"]     += 4

        session["risk_score"] = max(session["risk_score"], 0)
        score = session["risk_score"]
        difficulty, risk_level = get_difficulty(score)

    # ==========================================
    # Render
    # ==========================================
    bot_probability = calculate_bot_probability(session["risk_score"])

    if difficulty == "hard":
        category = random.choice(["traffic-lights", "buses"])
        tiles    = create_tiles(category)
        label    = "traffic lights" if category == "traffic-lights" else "buses"

        return render_template(
            "tile_captcha.html",
            message         = message,
            difficulty      = difficulty,
            risk_score      = session["risk_score"],
            risk_level      = risk_level,
            bot_probability = bot_probability,
            tiles           = tiles,
            tile_label      = label,
            correct_tiles   = session.get("correct_tiles", []),
        )

    else:
        captcha_text, filename = generate_captcha(difficulty)

        return render_template(
            "captcha.html",
            message         = message,
            attempts        = session.get("attempts", 0),
            difficulty      = difficulty,
            risk_score      = session["risk_score"],
            risk_level      = risk_level,
            bot_probability = bot_probability,
            captcha_file    = filename,
            bot_answer      = captcha_text,
        )


if __name__ == "__main__":
    app.run(debug=True)