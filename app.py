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
    captcha_text = ''.join(random.choices(string.ascii_uppercase + string.digits, k=6))

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
    noise = np.random.randint(0, amount, img.shape, dtype='uint8')
    img = cv2.add(img, noise)
    return img


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
        color = (
            random.randint(0,255),
            random.randint(0,255),
            random.randint(0,255)
        )
        cv2.line(img, (x1, y1), (x2, y2), color, 2)
    return img


# ---------------------------------------
# Calculate Risk Score
# ---------------------------------------
def calculate_risk(mouse_moves, clicks, typing_time, time_spent, failures):

    risk = 0

    # Very low mouse movement → bot suspicion
    if mouse_moves < 20:
        risk += 2

    # Extremely fast typing → bot suspicion
    if typing_time < 1000:
        risk += 2

    # Very low time spent → bot suspicion
    if time_spent < 2000:
        risk += 2

    # Too many clicks → suspicious
    if clicks > 15:
        risk += 1

    # Previous failures increase suspicion
    risk += failures

    return risk


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

        print("Mouse Moves:", mouse_moves)
        print("Clicks:", clicks)
        print("Typing Time:", typing_time)
        print("Time Spent:", time_spent)

        # CAPTCHA validation
        if user_input == session.get("captcha"):
            message = "✅ CAPTCHA Verified!"
            attempts = 0
        else:
            attempts += 1
            message = "❌ Incorrect CAPTCHA!"

        session["attempts"] = attempts

        # Calculate risk score
        risk_score = calculate_risk(
            mouse_moves,
            clicks,
            typing_time,
            time_spent,
            attempts
        )

        print("Risk Score:", risk_score)

        # Determine difficulty
        if risk_score < 3:
            difficulty = "easy"
        elif risk_score < 6:
            difficulty = "medium"
        else:
            difficulty = "hard"

    generate_captcha(difficulty)

    # Default values so page never shows empty fields
    risk_score = session.get("risk_score", 0)
    risk_level = session.get("risk_level", "Low")

    return render_template(
        "index.html",
        message=message,
        attempts=attempts,
        difficulty=difficulty,
        risk_score=risk_score,
        risk_level=risk_level
    )


# ---------------------------------------
# Run App
# ---------------------------------------
if __name__ == "__main__":
    app.run(debug=True)