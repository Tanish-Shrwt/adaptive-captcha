"""
risk.py — bot risk scoring and difficulty ladder logic.
No Flask imports — pure Python functions.
"""

from config import LADDER


def calculate_risk(mouse_moves, clicks, typing_time, time_spent, failures,
                   fill_time_ms=None, focus_switches=None, used_paste=False,
                   honeypot_filled=False, rhythm_score=None, rhythm_samples=0):
    """
    Compute a risk INTEGER from behaviour signals.
    Higher = more bot-like.

    KEY DESIGN PRINCIPLE:
    - A human who just loaded the page and typed normally should score 0–3.
    - Only clear bot signals (honeypot, zero mouse + instant fill + no time, etc.)
      should push the score high.
    - Behaviour risk is added to the SESSION score ONCE per submit, so signals
      must be conservative — they compound across attempts.
    """
    risk = 0

    # ── Honeypot ───────────────────────────────────────
    # A real user NEVER fills a hidden field.
    if honeypot_filled:
        risk += 20
        return risk   # No need to check anything else

    # ── Mouse movement ─────────────────────────────────
    # 0 moves is suspicious only when combined with other signals.
    # Penalise alone only slightly — some users navigate by keyboard.
    if mouse_moves == 0:
        risk += 1
    elif 0 < mouse_moves < 3:
        risk += 1

    # ── Time on page ───────────────────────────────────
    # < 500ms is nearly impossible for a human (page hasn't even rendered).
    # 500–1500ms is fast but plausible (returning user with password manager).
    if time_spent < 500:
        risk += 3
    elif time_spent < 1500:
        risk += 1

    # ── Typing time (time from first keypress to last in CAPTCHA input) ──
    # < 30ms = definitely not human
    if 0 < typing_time < 30:
        risk += 3
    elif 30 <= typing_time < 100:
        risk += 1

    # ── Strong combo: zero mouse + instant submit ──────
    # This is the classic headless-browser signature.
    if mouse_moves == 0 and time_spent < 800 and typing_time < 100:
        risk += 4

    # ── Login-field fill speed ─────────────────────────
    # fill_time_ms = time from first focus on username to last keyup on password.
    # < 200ms = definitely scripted; 200–600ms = suspiciously fast.
    if fill_time_ms is not None and fill_time_ms > 0:
        if fill_time_ms < 200:
            risk += 4
        elif fill_time_ms < 600:
            risk += 2

    # ── Focus switches ─────────────────────────────────
    # focus_switches == 0 is NORMAL (Tab key, autofill, single-field paste).
    # DO NOT penalise zero switches — it broke legitimate human logins.
    # Only penalise if focus bounced unnaturally many times very fast.
    if focus_switches is not None and focus_switches > 5:
        risk += 1

    # ── Paste detection ────────────────────────────────
    # Paste alone is not suspicious (password managers are common).
    # Only flag when combined with very fast fill.
    if used_paste and fill_time_ms is not None and fill_time_ms < 400:
        risk += 1

    # ── Keystroke dynamics ─────────────────────────────
    # rhythm_score: 0–100 (higher = more human-like variance).
    # Only score when we have enough samples to be reliable.
    if rhythm_score is not None and rhythm_samples >= 6:
        if rhythm_score < 10:
            risk += 4   # Perfectly uniform — clear bot signature
        elif rhythm_score < 20:
            risk += 2

    # ── Past failures ─────────────────────────────────
    # Each previous failure in this session adds a small penalty.
    # Capped at 3 to avoid runaway score from honest mistakes.
    risk += min(failures, 3) * 1

    return risk


def calculate_bot_probability(score: int) -> float:
    """Map risk score to 0–100% bot probability."""
    # Scale: score 0 = 0%, score 15+ = 100%
    return float(round(min(100.0, (score / 15) * 100), 2))


def get_captcha_level(score: int) -> tuple[str, str, str]:
    """
    Return (captcha_type, risk_label, level_name) for a given score.
    Uses the LADDER defined in config.py.
    """
    for threshold, ctype, risk_label, level_name in LADDER:
        if score <= threshold:
            return ctype, risk_label, level_name
    return "rotation", "Critical", "Rotation CAPTCHA"