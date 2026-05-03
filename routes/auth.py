"""
routes/auth.py — /login, /logout, /reset

Handles all authentication flow:
  1. Read behaviour signals from form
  2. Validate CAPTCHA
  3. Check credentials (only if CAPTCHA passed)
  4. Block bots / grant access
  5. Log every attempt to the database
"""

from datetime import datetime
from flask import (Blueprint, render_template, request,
                   session, redirect, url_for)

from config       import DEMO_USERS
from database     import log_entry
from risk         import calculate_risk, calculate_bot_probability, get_captcha_level
from captcha_engine import validate_captcha, build_captcha_context

auth = Blueprint("auth", __name__)


# ── helpers ───────────────────────────────────────────

def _read_signals(form):
    """Extract and type-cast all behaviour signals from the POST form."""
    rhythm_score = int(form.get("rhythm_score", -1))

    fill_raw = int(form.get("fill_time_ms", 0))
    return {
        "mouse_moves":     int(form.get("mouse_moves",    0)),
        "clicks":          int(form.get("clicks",         0)),
        "typing_time":     int(form.get("typing_time",    0)),
        "time_spent":      int(form.get("time_spent",     0)),
        # Only treat fill_time as present if it's a real nonzero reading
        "fill_time_ms":    fill_raw if fill_raw > 0 else None,
        "focus_switches":  int(form.get("focus_switches", 0))
                           if "focus_switches" in form else None,
        "used_paste":      form.get("used_paste", "false") == "true",
        "honeypot_filled": bool(form.get("website", "").strip()),
        "rhythm_score":    rhythm_score if rhythm_score != -1 else None,
        "rhythm_samples":  int(form.get("rhythm_samples", 0)),
    }


# ── routes ────────────────────────────────────────────

@auth.route("/")
def home():
    return redirect(url_for("auth.login"))


@auth.route("/reset")
def reset():
    """Reset risk score to 0 — useful for demo walkthroughs."""
    session["risk_score"]     = 0
    session["correct_streak"] = 0
    session["attempts"]       = 0
    return redirect(url_for("auth.login"))


@auth.route("/login", methods=["GET", "POST"])
def login():
    session.setdefault("risk_score",     0)
    session.setdefault("correct_streak", 0)
    session.setdefault("attempts",       0)

    message = login_error = ""

    if request.method == "POST":
        is_simulated = request.form.get("is_simulated_bot", "false") == "true"
        sig          = _read_signals(request.form)

        # ── Accumulate behaviour risk ──────────────────
        # IMPORTANT: We only accumulate behaviour risk when the form is submitted
        # by a simulated bot OR when there are clear bot signals present.
        # For real human submits, behaviour_risk should be 0–3 at most.
        behaviour_risk = calculate_risk(
            sig["mouse_moves"], sig["clicks"],
            sig["typing_time"], sig["time_spent"],
            session["attempts"],
            sig["fill_time_ms"], sig["focus_switches"],
            sig["used_paste"], sig["honeypot_filled"],
            sig["rhythm_score"], sig["rhythm_samples"],
        )

        # For simulated bot, inject a guaranteed high risk delta
        if is_simulated:
            behaviour_risk = max(behaviour_risk, 15)

        session["risk_score"] += behaviour_risk

        # ── Validate CAPTCHA ───────────────────────────
        captcha_type = request.form.get("captcha_type", "text")
        passed, message, delta = validate_captcha(captcha_type, request.form)

        if passed:
            session["correct_streak"] += 1
            session["attempts"]        = 0
            # Correct CAPTCHA answer: reward delta from validate_captcha,
            # plus a streak bonus that grows with consecutive correct answers.
            # This ensures the score visibly drops toward 0 as a human keeps solving.
            streak = session["correct_streak"]
            streak_bonus = -2 if streak >= 2 else (-1 if streak >= 1 else 0)
            # Also apply a hard decay: score drops by at least 4 on any correct answer
            # so a human who was briefly elevated can recover in 2–3 solves.
            hard_decay = min(-4, delta)
            session["risk_score"] = max(
                0, session["risk_score"] + hard_decay + streak_bonus
            )
        else:
            session["attempts"]       += 1
            session["correct_streak"]  = 0
            session["risk_score"]      = max(0, session["risk_score"] + delta)

        # ── Process credentials (only when CAPTCHA passed) ────
        if passed:
            username = request.form.get("username", "").strip().lower()
            password = request.form.get("password", "")

            # is_bot: determined ONLY from THIS submit's signals, not the
            # accumulated session score (which may be poisoned by a prior
            # bot simulation in the same browser session).
            #
            # A real human who just solved a CAPTCHA correctly should NEVER
            # be blocked solely because a bot simulation ran earlier.
            #
            # Bot signals (any one of these is sufficient):
            #   1. Explicitly flagged as simulated bot
            #   2. This submit's behaviour_risk alone is very high (≥ 10)
            #   3. Classic headless signature: no mouse, instant fill, instant page
            this_submit_bot = (
                behaviour_risk >= 10
                or (
                    sig["mouse_moves"] == 0
                    and sig["fill_time_ms"] is not None
                    and sig["fill_time_ms"] < 200
                    and sig["time_spent"] < 500
                )
            )
            is_bot        = is_simulated or this_submit_bot
            access_denied = is_simulated or is_bot

            entry = {
                "timestamp":       datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                "username":        username,
                "captcha_type":    captcha_type,
                "risk_score":      session["risk_score"],
                "bot_probability": calculate_bot_probability(session["risk_score"]),
                "mouse_moves":     sig["mouse_moves"],
                "fill_time_ms":    sig["fill_time_ms"] or 0,
                "focus_switches":  sig["focus_switches"] or 0,
                "used_paste":      sig["used_paste"],
                "honeypot":        sig["honeypot_filled"],
                "rhythm_score":    sig["rhythm_score"] if sig["rhythm_score"] is not None else -1,
                "is_bot":          is_bot,
                "access_denied":   access_denied,
                "success":         False,
                "ip":              request.remote_addr,
            }

            if access_denied:
                login_error = "🚫 Access denied — bot activity detected."
                log_entry(entry)
                # Only pin score high for the simulated bot — NOT for the
                # next real human who uses the same browser after a demo.
                if is_simulated:
                    session["risk_score"] = max(session["risk_score"], 20)

            elif DEMO_USERS.get(username) == password:
                entry["success"] = True
                log_entry(entry)
                session["logged_in"]  = True
                session["username"]   = username
                session["risk_score"] = 0
                return redirect(url_for("dashboard.dashboard_view"))

            else:
                login_error = "Invalid username or password."
                session["risk_score"] += 2
                log_entry(entry)

    # ── Build render context ───────────────────────────
    score                    = session["risk_score"]
    ctype, risk_label, level_name = get_captcha_level(score)
    ctx                      = build_captcha_context(score)

    return render_template(
        "login.html",
        message          = message,
        login_error      = login_error,
        risk_score       = score,
        bot_probability  = calculate_bot_probability(score),
        attempts         = session["attempts"],
        **ctx,
    )


@auth.route("/logout")
def logout():
    session.clear()
    return redirect(url_for("auth.login"))