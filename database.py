"""
database.py — SQLite access layer.
No Flask imports here — pure Python, fully testable standalone.
"""

import sqlite3
from config import DB_PATH


def get_db():
    """
    Open a SQLite connection and ensure the table exists.
    Uses row_factory so rows behave like dicts.
    Always call conn.close() when done.
    """
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("""
        CREATE TABLE IF NOT EXISTS access_logs (
            id              INTEGER PRIMARY KEY AUTOINCREMENT,
            timestamp       TEXT    NOT NULL,
            username        TEXT,
            captcha_type    TEXT,
            risk_score      INTEGER DEFAULT 0,
            bot_probability REAL    DEFAULT 0,
            mouse_moves     INTEGER DEFAULT 0,
            fill_time_ms    INTEGER DEFAULT 0,
            focus_switches  INTEGER DEFAULT 0,
            used_paste      INTEGER DEFAULT 0,
            honeypot        INTEGER DEFAULT 0,
            rhythm_score    INTEGER DEFAULT -1,
            is_bot          INTEGER DEFAULT 0,
            access_denied   INTEGER DEFAULT 0,
            success         INTEGER DEFAULT 0,
            ip              TEXT
        )
    """)
    conn.commit()
    return conn


def log_entry(entry: dict):
    """Insert one access-log row from a plain dict."""
    conn = get_db()
    conn.execute("""
        INSERT INTO access_logs
          (timestamp, username, captcha_type, risk_score, bot_probability,
           mouse_moves, fill_time_ms, focus_switches, used_paste, honeypot,
           rhythm_score, is_bot, access_denied, success, ip)
        VALUES
          (:timestamp, :username, :captcha_type, :risk_score, :bot_probability,
           :mouse_moves, :fill_time_ms, :focus_switches, :used_paste, :honeypot,
           :rhythm_score, :is_bot, :access_denied, :success, :ip)
    """, {
        "timestamp":       entry.get("timestamp", ""),
        "username":        entry.get("username", ""),
        "captcha_type":    entry.get("captcha_type", ""),
        "risk_score":      entry.get("risk_score", 0),
        "bot_probability": entry.get("bot_probability", 0.0),
        "mouse_moves":     entry.get("mouse_moves", 0),
        "fill_time_ms":    entry.get("fill_time_ms", 0),
        "focus_switches":  entry.get("focus_switches", 0),
        "used_paste":      1 if entry.get("used_paste") else 0,
        "honeypot":        1 if entry.get("honeypot") else 0,
        "rhythm_score":    entry.get("rhythm_score", -1),
        "is_bot":          1 if entry.get("is_bot") else 0,
        "access_denied":   1 if entry.get("access_denied") else 0,
        "success":         1 if entry.get("success") else 0,
        "ip":              entry.get("ip", ""),
    })
    conn.commit()
    conn.close()


def fetch_logs(limit: int = 50) -> list[dict]:
    """Return the most recent rows, newest first, as plain dicts."""
    conn = get_db()
    rows = conn.execute(
        "SELECT * FROM access_logs ORDER BY id DESC LIMIT ?", (limit,)
    ).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def fetch_stats() -> dict:
    """Return aggregate counts for the dashboard overview cards."""
    conn = get_db()
    row = conn.execute("""
        SELECT
            COUNT(*)                                    AS total,
            SUM(is_bot)                                 AS bots,
            SUM(CASE WHEN is_bot = 0 THEN 1 ELSE 0 END) AS humans,
            SUM(success)                                AS success,
            SUM(access_denied)                          AS denied
        FROM access_logs
    """).fetchone()
    conn.close()
    return dict(row) if row else {
        "total": 0, "bots": 0, "humans": 0, "success": 0, "denied": 0
    }