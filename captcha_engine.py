"""
captcha_engine.py — generates and validates all 5 CAPTCHA types.

Each generator writes files to the static/ folder and stores the
correct answer in Flask's session.  validate_captcha() reads the
session and compares against the submitted form values.
"""

import os, random, string, time, json
import math as pymath

import cv2
import numpy as np
from PIL import Image, ImageDraw, ImageFont, ImageFilter
from captcha.image import ImageCaptcha
from flask import session

from config import (
    CAPTCHA_FOLDER, MATH_FOLDER, ROTATION_FOLDER, LABELS_PATH,
    FONT_PATH, FONT_FALLBACKS,
    DRAG_SHAPES, ROTATION_TOLERANCE,
)


# ═══════════════════════════════════════════════════════
# CAPTCHA 1 — TEXT
# Standard distorted character CAPTCHA.
# ═══════════════════════════════════════════════════════

def generate_text_captcha() -> tuple[str, str]:
    """Generate a 6-char distorted text CAPTCHA image."""
    gen  = ImageCaptcha(width=260, height=80)
    text = "".join(random.choices(string.ascii_uppercase + string.digits, k=6))
    ts   = int(time.time() * 1000)
    fname = f"captcha_{ts}.png"
    path  = os.path.join(CAPTCHA_FOLDER, fname)

    # Remove old images so the folder doesn't grow unboundedly
    for old in os.listdir(CAPTCHA_FOLDER):
        os.remove(os.path.join(CAPTCHA_FOLDER, old))

    gen.write(text, path)
    session["captcha_text"] = text
    session["captcha_file"] = fname
    return text, fname


# ═══════════════════════════════════════════════════════
# CAPTCHA 2 — MATH
# Renders a readable arithmetic equation with a
# gentle sine-wave warp — defeats OCR without being
# painful for humans.
# ═══════════════════════════════════════════════════════

def _load_font(size: int):
    """Try FONT_PATH then each fallback; return an ImageFont."""
    for path in [FONT_PATH] + FONT_FALLBACKS:
        try:
            return ImageFont.truetype(path, size)
        except Exception:
            continue
    return ImageFont.load_default()


def generate_math_captcha() -> tuple[int, str]:
    """Generate a math-equation CAPTCHA image. Returns (answer, filename)."""
    op = random.choice(["+", "-", "*"])
    a  = random.randint(2, 12)
    b  = random.randint(2, 9)

    if op == "+":   ans = a + b
    elif op == "-": a = a + b; ans = a - b   # keep positive
    else:           ans = a * b

    question = f"{a} {op} {b} = ?"

    W, H = 320, 100
    img  = Image.new("RGB", (W, H), (255, 255, 255))
    draw = ImageDraw.Draw(img)
    font = _load_font(48)

    # Centre the equation
    bbox = draw.textbbox((0, 0), question, font=font)
    tw, th = bbox[2] - bbox[0], bbox[3] - bbox[1]
    x = max(10, (W - tw) // 2)
    y = max(8,  (H - th) // 2 - 4)
    draw.text((x, y), question, font=font, fill=(20, 50, 160))

    # Sine-wave column warp — breaks OCR segmentation
    arr   = np.array(img)
    amp   = random.uniform(2.5, 4.0)
    freq  = random.uniform(0.09, 0.14)
    phase = random.uniform(0, 2 * pymath.pi)
    for col in range(W):
        shift = int(amp * pymath.sin(freq * col + phase))
        arr[:, col, :] = np.roll(arr[:, col, :], shift, axis=0)

    img  = Image.fromarray(arr)
    draw = ImageDraw.Draw(img)

    # Four thin noise lines
    for _ in range(4):
        draw.line(
            [random.randint(0,W), random.randint(0,H),
             random.randint(0,W), random.randint(0,H)],
            fill=(random.randint(150,210), random.randint(150,210),
                  random.randint(200,240)),
            width=1
        )

    img = img.filter(ImageFilter.SMOOTH)

    ts    = int(time.time() * 1000)
    fname = f"math_{ts}.png"
    path  = os.path.join(MATH_FOLDER, fname)
    for old_f in os.listdir(MATH_FOLDER):
        os.remove(os.path.join(MATH_FOLDER, old_f))
    img.save(path)

    session["math_answer"] = str(ans)
    session["math_file"]   = fname
    return ans, fname


# ═══════════════════════════════════════════════════════
# CAPTCHA 3 — TILE
# 3×3 grid sliced from a real photo.
# Correct tiles come from labels.json (pre-labelled).
# ═══════════════════════════════════════════════════════

def _load_labels() -> dict:
    if not os.path.exists(LABELS_PATH):
        return {}
    with open(LABELS_PATH) as f:
        return json.load(f)


def _preprocess_image(path: str, size: int = 600) -> np.ndarray:
    """Resize + centre-crop an image to size×size."""
    img = cv2.imread(path)
    if img is None:
        raise FileNotFoundError(path)
    h, w    = img.shape[:2]
    scale   = size / min(h, w)
    nw, nh  = int(w * scale), int(h * scale)
    img     = cv2.resize(img, (nw, nh), interpolation=cv2.INTER_AREA)
    t = (nh - size) // 2
    l = (nw - size) // 2
    return img[t:t + size, l:l + size]


def create_tiles(category: str = "traffic-lights") -> list[str]:
    """
    Slice a random image from `category` into 9 tiles.
    Stores correct tile indices in session.
    Returns list of tile filenames.
    """
    folder = f"static/tile_captcha/{category}"
    labels = _load_labels()
    cat    = labels.get(category, {})

    if not cat:
        raise RuntimeError(f"No labels for '{category}'")

    available = [img for img in cat
                 if os.path.exists(os.path.join(folder, img))]
    if not available:
        raise RuntimeError(f"No image files found for '{category}'")

    name = random.choice(available)
    img  = _preprocess_image(os.path.join(folder, name), 600)

    tile_dir = "static/tiles"
    os.makedirs(tile_dir, exist_ok=True)
    for f in os.listdir(tile_dir):
        os.remove(os.path.join(tile_dir, f))

    tiles = []
    for idx in range(9):
        i, j  = divmod(idx, 3)
        tile  = img[i*200:(i+1)*200, j*200:(j+1)*200]
        fname = f"tile{idx}.jpg"
        cv2.imwrite(os.path.join(tile_dir, fname), tile)
        tiles.append(fname)

    session["correct_tiles"] = sorted(int(x) for x in cat.get(name, []))
    return tiles


# ═══════════════════════════════════════════════════════
# CAPTCHA 4 — DRAG-TO-MATCH
# Pure JS rendering — no image files needed.
# Backend picks shapes; correct index stored in session.
# ═══════════════════════════════════════════════════════

def generate_drag_captcha() -> tuple[str, list[str], int]:
    """
    Pick 3 target shapes and one draggable that matches one of them.
    Returns (draggable_shape, target_shapes, correct_index).
    """
    targets     = random.sample(DRAG_SHAPES, 3)
    draggable   = targets[random.randint(0, 2)]
    random.shuffle(targets)
    correct_idx = targets.index(draggable)

    session["drag_correct"] = correct_idx
    session["drag_targets"] = targets
    session["drag_shape"]   = draggable
    return draggable, targets, correct_idx


# ═══════════════════════════════════════════════════════
# CAPTCHA 5 — ROTATION
# OpenCV rotates a source image by a random angle.
# User must rotate it back using a slider.
# Tolerance: ±ROTATION_TOLERANCE degrees.
# ═══════════════════════════════════════════════════════

def generate_rotation_captcha() -> tuple[str, int]:
    """
    Pick a random image, rotate it, save to static/rotation_captcha/current/.
    Returns (filename, correct_angle_to_rotate_back).
    """
    images = [f for f in os.listdir(ROTATION_FOLDER)
              if f.lower().endswith((".png", ".jpg", ".jpeg"))]
    if not images:
        raise RuntimeError("No images in static/rotation_captcha/")

    path = os.path.join(ROTATION_FOLDER, random.choice(images))
    img  = cv2.imread(path)
    if img is None:
        raise RuntimeError(f"Cannot read {path}")

    img = cv2.resize(img, (300, 300))

    # Avoid angles too close to 0° (trivially solved)
    while True:
        angle = random.randint(0, 359)
        if ROTATION_TOLERANCE < angle < (360 - ROTATION_TOLERANCE):
            break

    cx, cy = 150, 150
    M   = cv2.getRotationMatrix2D((cx, cy), angle, 1.0)
    rot = cv2.warpAffine(img, M, (300, 300),
                         borderMode=cv2.BORDER_CONSTANT,
                         borderValue=(245, 245, 245))

    out_dir = "static/rotation_captcha/current"
    os.makedirs(out_dir, exist_ok=True)
    for f in os.listdir(out_dir):
        os.remove(os.path.join(out_dir, f))

    ts    = int(time.time() * 1000)
    fname = f"rot_{ts}.jpg"
    cv2.imwrite(os.path.join(out_dir, fname), rot)

    # `angle` is how much OpenCV rotated the image clockwise.
    # CSS rotate(Xdeg) is also clockwise, so the user needs to apply
    # the same angle to "undo" the rotation visually.
    # Storing `angle` directly means the correct slider position matches
    # what the user intuitively sees they need to correct.
    correct = angle
    session["rotation_file"]    = fname
    session["rotation_correct"] = correct
    return fname, correct


# ═══════════════════════════════════════════════════════
# VALIDATE — all types
# Returns (passed, message, score_delta)
#   score_delta < 0 → reward (score drops)
#   score_delta > 0 → penalty (score rises)
# ═══════════════════════════════════════════════════════

def validate_captcha(captcha_type: str, form) -> tuple[bool, str, int]:
    if captcha_type == "text":
        user = form.get("captcha_input", "").strip().upper()
        if user == session.get("captcha_text", ""):
            return True,  "✓ Text verification passed.", -2
        return False, "Incorrect characters. Please try again.", +2

    if captcha_type == "math":
        user = form.get("math_input", "").strip()
        if user == session.get("math_answer", ""):
            return True,  "✓ Math verification passed.", -2
        return False, "Wrong answer. Please try again.", +2

    if captcha_type == "tile":
        raw = form.get("selected_tiles", "")
        try:
            selected = sorted(int(x) for x in raw.split(",") if x.strip())
        except ValueError:
            selected = []
        correct_tiles = sorted(int(x) for x in session.get("correct_tiles", []))
        # Guard: empty correct_tiles means session lost — don't let empty match empty
        if not correct_tiles:
            return False, "Session expired — please try again.", 0
        if selected == correct_tiles:
            return True,  "✓ Image verification passed.", -3
        return False, "Wrong tiles selected. Please try again.", +2

    if captcha_type == "drag":
        try:
            user_idx = int(form.get("drag_answer", "-1"))
        except ValueError:
            user_idx = -1
        if user_idx == session.get("drag_correct", -99):
            return True,  "✓ Drag verification passed.", -3
        return False, "Incorrect match. Please try again.", +2

    if captcha_type == "rotation":
        try:
            user_angle = float(form.get("rotation_answer", "-1"))
        except ValueError:
            user_angle = -1
        correct = session.get("rotation_correct", 0)
        diff    = abs((user_angle - correct + 180) % 360 - 180)
        if diff <= ROTATION_TOLERANCE:
            return True,  "✓ Rotation verified.", -4
        return False, f"Not quite — off by {diff:.0f}°. Try again.", +2

    return False, "Unknown CAPTCHA type.", +2


# ═══════════════════════════════════════════════════════
# BUILD CONTEXT — picks the right CAPTCHA for a score
# and returns a flat dict of template variables.
# ═══════════════════════════════════════════════════════

def build_captcha_context(score: int) -> dict:
    from risk import get_captcha_level
    ctype, risk_label, level_name = get_captcha_level(score)

    ctx: dict = {
        "captcha_type": ctype,
        "risk_label":   risk_label,
        "level_name":   level_name,
        # safe defaults so templates never KeyError
        "captcha_file":    "",
        "bot_answer":      "",
        "math_file":       "",
        "math_answer":     "",
        "tiles":           [],
        "tile_label":      "",
        "correct_tiles":   [],
        "drag_shape":      "",
        "drag_targets":    [],
        "drag_correct":    -1,
        "rotation_file":   "",
        "rotation_correct": 0,
    }

    if ctype == "text":
        text, fname = generate_text_captcha()
        ctx.update(captcha_file=fname, bot_answer=text)

    elif ctype == "math":
        ans, fname = generate_math_captcha()
        ctx.update(math_file=fname, math_answer=str(ans))

    elif ctype == "tile":
        try:
            category = random.choice(["traffic-lights", "buses"])
            tiles    = create_tiles(category)
            label    = "traffic lights" if category == "traffic-lights" else "buses"
            ctx.update(tiles=tiles, tile_label=label,
                       correct_tiles=session.get("correct_tiles", []))
        except RuntimeError:
            # No tile images present — fall back to text CAPTCHA
            text, fname = generate_text_captcha()
            ctx.update(captcha_type="text", captcha_file=fname, bot_answer=text)

    elif ctype == "drag":
        shape, targets, correct_idx = generate_drag_captcha()
        ctx.update(drag_shape=shape, drag_targets=targets, drag_correct=correct_idx)

    elif ctype == "rotation":
        try:
            fname, correct = generate_rotation_captcha()
            ctx.update(rotation_file=fname, rotation_correct=correct)
        except RuntimeError:
            text, fname = generate_text_captcha()
            ctx.update(captcha_type="text", captcha_file=fname, bot_answer=text)

    return ctx