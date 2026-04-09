from flask import Flask, render_template, request, session
from captcha.image import ImageCaptcha
import random
import string
import os
import time
import cv2
import numpy as np

app = Flask(__name__)
app.secret_key = "supersecretkey"

CAPTCHA_FOLDER = "static/captcha_images"

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
# Generate character CAPTCHA image
# FIX: now returns captcha_text so caller
#      can pass it to the template as bot_answer
# FIX: cache-busting via timestamp in filename
# =======================================
def generate_captcha(difficulty="easy"):
    image = ImageCaptcha(width=280, height=90)
    captcha_text = "".join(
        random.choices(string.ascii_uppercase + string.digits, k=6)
    )

    # Cache-bust: unique filename per generation
    timestamp = int(time.time() * 1000)
    filename = f"captcha_{timestamp}.png"
    image_path = os.path.join(CAPTCHA_FOLDER, filename)

    # Clean up old captcha images to avoid filling disk
    for old in os.listdir(CAPTCHA_FOLDER):
        os.remove(os.path.join(CAPTCHA_FOLDER, old))

    image.write(captcha_text, image_path)
    img = cv2.imread(image_path)

    if difficulty == "medium":
        # Moderate noise + a few distraction lines
        img = add_noise(img, 35)
        img = add_lines(img, 3)

    elif difficulty == "hard":
        # Heavy noise + many lines + blur — hardest for OCR
        img = add_noise(img, 70)
        img = add_lines(img, 7)
        img = cv2.GaussianBlur(img, (5, 5), 0)

    cv2.imwrite(image_path, img)

    # Store text AND filename in session
    session["captcha_text"] = captcha_text
    session["captcha_file"] = filename
    session["difficulty"] = difficulty

    return captcha_text, filename


# =======================================
# Add random pixel noise to image
# =======================================
def add_noise(img, amount):
    noise = np.random.randint(0, amount, img.shape, dtype="uint8")
    return cv2.add(img, noise)


# =======================================
# Add random colored lines to image
# =======================================
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
#
# Signals weighted by how strong they are:
#
# STRONG bot signals (+3 each):
#   - Zero mouse movement
#   - Typing time < 50ms (impossible for human)
#   - Page time < 300ms (impossible for human)
#
# MODERATE signals (+2 each):
#   - Very few mouse moves (< 5) — could be mobile but suspicious
#   - Typing time 50–150ms — very fast
#
# WEAK signals (+1 each):
#   - Excessive clicks (> 15) — scripted clicking
#   - Time 300–700ms — unusually fast
#
# FIX: removed cap on failures — each failure adds to risk
# FIX: combined bot signal (0 moves + fast type + fast time)
#       now gives +5 instead of +2
# =======================================
def calculate_risk(mouse_moves, clicks, typing_time, time_spent, failures):
    risk = 0

    # --- Strong bot signals ---
    if mouse_moves == 0:
        risk += 3                       # Real users almost always move mouse

    if typing_time < 50 and typing_time > 0:
        risk += 3                       # Sub-50ms typing = script

    if time_spent < 300:
        risk += 3                       # Sub-300ms total = definitely automated

    # --- Moderate signals ---
    if 0 < mouse_moves < 5:
        risk += 2                       # Very little movement

    if 50 <= typing_time < 150:
        risk += 2                       # Very fast but not instant

    # --- Weak signals ---
    if clicks > 15:
        risk += 1                       # Scripted click spam

    if 300 <= time_spent < 700:
        risk += 1                       # Fast but not impossible

    # --- Combined "perfect bot" signal ---
    # All three strong signals together = certain bot, add extra penalty
    if mouse_moves == 0 and typing_time < 50 and time_spent < 300:
        risk += 5

    # --- Failure penalty (uncapped) ---
    # FIX: was min(failures, 1) — now every failure adds 2
    risk += failures * 2

    return risk


# =======================================
# Convert raw risk score → bot probability %
# Scaled so score 10 = ~70%, score 15 = ~100%
# More realistic than linear /10 * 100
# =======================================
def calculate_bot_probability(risk_score):
    probability = min(100.0, (risk_score / 15) * 100)
    return float(round(probability, 2))


# =======================================
# Slice one full traffic-light or bus image
# into a 3×3 grid of tiles
#
# FIX: now accepts a `category` parameter
#      so we can randomise between traffic-lights / buses
# FIX: stores correct tile indices in session
#      for server-side validation
# =======================================
def create_tiles(category="traffic-lights"):
    folder = f"static/tile_captcha/{category}"
    image_name = random.choice(os.listdir(folder))
    image_path = os.path.join(folder, image_name)

    img = cv2.imread(image_path)
    h, w, _ = img.shape
    tile_h, tile_w = h // 3, w // 3

    tile_folder = "static/tiles"
    if not os.path.exists(tile_folder):
        os.makedirs(tile_folder)

    # Remove old tiles
    for f in os.listdir(tile_folder):
        os.remove(os.path.join(tile_folder, f))

    tiles = []
    for idx in range(9):
        i, j = divmod(idx, 3)
        tile = img[i * tile_h:(i + 1) * tile_h, j * tile_w:(j + 1) * tile_w]
        name = f"tile{idx}.jpg"
        cv2.imwrite(os.path.join(tile_folder, name), tile)
        tiles.append(name)

    # -------------------------------------------------
    # Store which tiles are "correct" in session
    # so the POST handler can validate server-side.
    #
    # For now we store a placeholder — in production
    # you'd run an object-detection model here.
    # For the demo, we mark tiles 0,1,4 as correct
    # (replace with real labels once you have them).
    # -------------------------------------------------
    session["correct_tiles"] = [0, 1, 4]
    session["tile_category"] = category

    return tiles


# =======================================
# Main route — handles both character
# CAPTCHA and tile CAPTCHA
# =======================================
@app.route("/", methods=["GET", "POST"])
def index():

    # --- Session init ---
    session.setdefault("risk_score", 0)
    session.setdefault("correct_streak", 0)
    session.setdefault("attempts", 0)

    score = session["risk_score"]
    difficulty, risk_level = get_difficulty(score)
    message = ""
    bot_answer = ""         # passed to template for bot simulator

    # ==========================================
    # POST — user submitted a CAPTCHA answer
    # ==========================================
    if request.method == "POST":
        captcha_type = request.form.get("captcha_type", "character")

        mouse_moves  = int(request.form.get("mouse_moves",  0))
        clicks       = int(request.form.get("clicks",       0))
        typing_time  = int(request.form.get("typing_time",  0))
        time_spent   = int(request.form.get("time_spent",   0))

        # --- Behaviour-based risk delta ---
        behavior_risk = calculate_risk(
            mouse_moves, clicks, typing_time, time_spent,
            session["attempts"]
        )
        session["risk_score"] += behavior_risk

        # ======================================
        # Branch A: character CAPTCHA validation
        # ======================================
        if captcha_type == "character":
            user_input = request.form.get("captcha_input", "").strip().upper()
            correct    = session.get("captcha_text", "")

            if user_input == correct:
                message = "✅ Correct! CAPTCHA passed."
                session["correct_streak"] += 1
                session["attempts"] = 0

                # Recovery: correct answers slowly reduce risk
                session["risk_score"] -= 2
                if session["correct_streak"] >= 3:
                    session["risk_score"] -= 1   # small bonus, not a free pass
                # FIX: removed full reset at streak 5 — bots can solve CAPTCHAs
                #      so a streak should NOT zero out accumulated risk

            else:
                message = "❌ Incorrect CAPTCHA. Try again."
                session["attempts"]      += 1
                session["correct_streak"] = 0
                session["risk_score"]    += 3    # wrong answer = strong penalty

        # ======================================
        # Branch B: tile CAPTCHA validation
        # ======================================
        elif captcha_type == "tile":
            # Client sends comma-separated selected indices e.g. "0,3,6"
            raw = request.form.get("selected_tiles", "")
            try:
                selected = sorted([int(x) for x in raw.split(",") if x.strip()])
            except ValueError:
                selected = []

            correct_tiles = sorted(session.get("correct_tiles", []))

            if selected == correct_tiles:
                message = "✅ Correct tiles selected!"
                session["correct_streak"] += 1
                session["attempts"] = 0
                session["risk_score"] -= 2
            else:
                message = "❌ Wrong tiles. Try again."
                session["attempts"]      += 1
                session["correct_streak"] = 0
                session["risk_score"]    += 4    # tile failure = higher penalty

        # Clamp risk to 0 minimum
        session["risk_score"] = max(session["risk_score"], 0)

        # Re-evaluate difficulty after score update
        score = session["risk_score"]
        difficulty, risk_level = get_difficulty(score)

    # ==========================================
    # Render the right CAPTCHA type
    # ==========================================
    bot_probability = calculate_bot_probability(session["risk_score"])

    if difficulty == "hard":
        # --- Tile CAPTCHA ---
        category = random.choice(["traffic-lights", "buses"])
        tiles    = create_tiles(category)
        label    = "traffic lights" if category == "traffic-lights" else "buses"

        return render_template(
            "tile_captcha.html",
            message        = message,
            difficulty     = difficulty,
            risk_score     = session["risk_score"],
            risk_level     = risk_level,
            bot_probability= bot_probability,
            tiles          = tiles,
            tile_label     = label,
            # FIX: pass correct tiles so bot simulator can auto-select them
            correct_tiles  = session.get("correct_tiles", []),
        )

    else:
        # --- Character CAPTCHA ---
        captcha_text, filename = generate_captcha(difficulty)

        # FIX: pass captcha_text as bot_answer so JS simulator can use it
        return render_template(
            "captcha.html",
            message         = message,
            attempts        = session.get("attempts", 0),
            difficulty      = difficulty,
            risk_score      = session["risk_score"],
            risk_level      = risk_level,
            bot_probability = bot_probability,
            captcha_file    = filename,        # cache-busted filename
            bot_answer      = captcha_text,    # FIX: was never passed before
        )


# =======================================
# Run
# =======================================
if __name__ == "__main__":
    app.run(debug=True)