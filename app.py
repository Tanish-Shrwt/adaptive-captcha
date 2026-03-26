from flask import Flask, render_template, request, session
from captcha.image import ImageCaptcha
import random
import string
import os
import cv2
import numpy as np

app = Flask(__name__)
app.secret_key = "supersecretkey"

CAPTCHA_FOLDER = "static/captcha_images"

if not os.path.exists(CAPTCHA_FOLDER):
    os.makedirs(CAPTCHA_FOLDER)


# ---------------------------------------
# Generate CAPTCHA with difficulty
# ---------------------------------------
def generate_captcha(difficulty="easy"):
    image = ImageCaptcha(width=280, height=90)
    captcha_text = "".join(random.choices(string.ascii_uppercase + string.digits, k=6))

    image_path = os.path.join(CAPTCHA_FOLDER, "captcha.png")
    image.write(captcha_text, image_path)

    img = cv2.imread(image_path)

    if difficulty == "medium":
        img = add_noise(img, 30)
        img = add_lines(img, 2)

    elif difficulty == "hard":
        img = add_noise(img, 60)
        img = add_lines(img, 5)
        img = cv2.GaussianBlur(img, (5, 5), 0)

    cv2.imwrite(image_path, img)

    session["captcha"] = captcha_text
    session["difficulty"] = difficulty


# ---------------------------------------
# Add Noise
# ---------------------------------------
def add_noise(img, amount):
    noise = np.random.randint(0, amount, img.shape, dtype="uint8")
    return cv2.add(img, noise)


# ---------------------------------------
# Add Random Lines
# ---------------------------------------
def add_lines(img, count):
    h, w, _ = img.shape
    for _ in range(count):
        x1 = random.randint(0, w)
        y1 = random.randint(0, h)
        x2 = random.randint(0, w)
        y2 = random.randint(0, h)
        color = (random.randint(0, 255), random.randint(0, 255), random.randint(0, 255))
        cv2.line(img, (x1, y1), (x2, y2), color, 2)
    return img


# ---------------------------------------
# Calculate Risk Score
# ---------------------------------------
def calculate_risk(mouse_moves, clicks, typing_time, time_spent, failures):
    risk = 0

    if mouse_moves < 20:
        risk += 2

    if typing_time < 1000:
        risk += 2

    if time_spent < 3000:
        risk += 2

    if clicks > 15:
        risk += 1

    risk += min(failures, 3)

    return risk


# ---------------------------------------
# Convert Risk Score → Bot Probability
# ---------------------------------------
def calculate_bot_probability(risk_score):
    probability = (risk_score / 10) * 100
    probability = max(0, min(100, probability))
    return float(round(probability, 2))


# ---------------------------------------
# Convert Images into tiles
# ---------------------------------------
def create_tiles():
    folder = "static/tile_captcha/traffic-lights"
    image = random.choice(os.listdir(folder))
    image_path = os.path.join(folder, image)

    img = cv2.imread(image_path)

    h, w, _ = img.shape
    tile_h = h // 3
    tile_w = w // 3

    tiles = []
    tile_folder = "static/tiles"

    if not os.path.exists(tile_folder):
        os.makedirs(tile_folder)

    # delete old tiles
    for f in os.listdir(tile_folder):
        os.remove(os.path.join(tile_folder, f))

    count = 0

    for i in range(3):
        for j in range(3):
            tile = img[i * tile_h : (i + 1) * tile_h, j * tile_w : (j + 1) * tile_w]
            name = f"tile{count}.jpg"
            cv2.imwrite(os.path.join(tile_folder, name), tile)
            tiles.append(name)
            count += 1

    return tiles


# ---------------------------------------
# Main Route
# ---------------------------------------
@app.route("/", methods=["GET", "POST"])
def index():

    message = ""
    attempts = session.get("attempts", 0)
    difficulty = "easy"

    if request.method == "POST":

        user_input = request.form.get("captcha_input")

        # -------- Behavior Tracking --------
        mouse_moves = int(request.form.get("mouse_moves", 0))
        clicks = int(request.form.get("clicks", 0))
        typing_time = int(request.form.get("typing_time", 0))
        time_spent = int(request.form.get("time_spent", 0))

        # -------- CAPTCHA VALIDATION --------
        if user_input == session.get("captcha"):
            message = "✅ CAPTCHA Verified!"
            attempts = 0

            # 🔥 RESET EVERYTHING
            risk_score = 0
            bot_probability = 0
            risk_level = "Low"
            difficulty = "easy"

            session["attempts"] = attempts
            session["risk_score"] = risk_score
            session["bot_probability"] = bot_probability
            session["risk_level"] = risk_level

            generate_captcha(difficulty)

            return render_template(
                "captcha.html",
                message=message,
                attempts=attempts,
                difficulty=difficulty,
                risk_score=risk_score,
                risk_level=risk_level,
                bot_probability=bot_probability,
            )

        else:
            attempts += 1
            message = "❌ Incorrect CAPTCHA!"
            session["attempts"] = attempts

        # -------- Risk Calculation (ONLY if wrong) --------
        risk_score = calculate_risk(
            mouse_moves, clicks, typing_time, time_spent, attempts
        )

        bot_probability = calculate_bot_probability(risk_score)

        # -------- Risk Level --------
        if bot_probability < 30:
            risk_level = "Low"
            difficulty = "easy"
        elif bot_probability < 70:
            risk_level = "Medium"
            difficulty = "medium"
        else:
            risk_level = "High"
            difficulty = "hard"

        # -------- Tile CAPTCHA --------
        if bot_probability > 70:
            tiles = create_tiles()

            return render_template(
                "captcha.html",
                message=message,
                attempts=attempts,
                difficulty=difficulty,
                risk_score=risk_score,
                risk_level=risk_level,
                bot_probability=bot_probability,
                mouse_moves=session.get("mouse_moves", 0),
                time_spent=session.get("time_spent", 0),
            )

        # Store in session
        session["risk_score"] = risk_score
        session["bot_probability"] = bot_probability
        session["risk_level"] = risk_level

    # -------- Generate CAPTCHA --------
    generate_captcha(difficulty)

    # Retrieve values
    risk_score = session.get("risk_score", 0)
    risk_level = session.get("risk_level", "Low")
    bot_probability = session.get("bot_probability", 0)

    return render_template(
        "captcha.html",
        message=message,
        attempts=attempts,
        difficulty=difficulty,
        risk_score=risk_score,
        risk_level=risk_level,
        bot_probability=bot_probability,
        mouse_moves=session.get("mouse_moves", 0),
        time_spent=session.get("time_spent", 0),
    )


# ---------------------------------------
# Run App
# ---------------------------------------
if __name__ == "__main__":
    app.run(debug=True)
