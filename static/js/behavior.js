// ═══════════════════════════════════════════════════════
// behavior.js  —  human vs bot behaviour tracking
// Signals: mouse, clicks, typing time, fill speed,
//          focus switches, paste detection, honeypot,
//          keystroke dynamics (dwell + flight time)
// ═══════════════════════════════════════════════════════
console.log("behavior.js loaded");

// ── Shared state ─────────────────────────────────────
let mouseMoves  = 0;
let clicks      = 0;
let typingStart = 0;
let typingTime  = 0;
let pageStart   = Date.now();
let isBot       = false;

// ── Login-phase tracking ──────────────────────────────
let loginStartTime   = null;
let loginEndTime     = null;
let focusSwitches    = 0;
let lastFocusedField = null;
let usedPaste        = false;

// ── DOM references ────────────────────────────────────
const mouseDisplay  = document.getElementById("mouseActivity");
const clicksDisplay = document.getElementById("clicksActivity");
const timeDisplay   = document.getElementById("responseTime");
const captchaInput  = document.getElementById("captchaInput");
const captchaForm   = document.getElementById("captchaInput") ? document.getElementById("loginForm") : null;
const loginForm     = document.getElementById("loginForm");
const usernameField = document.getElementById("username");
const passwordField = document.getElementById("password");
const credForm      = null;  // merged into loginForm


// ═══════════════════════════════════════════════════════
// KEYSTROKE DYNAMICS ENGINE
//
// Tracks per-key dwell (keydown→keyup) and flight
// (keyup→next keydown) times across any input element.
//
// API:
//   KD.attach(inputEl)     — start tracking an element
//   KD.summary()           — { cv, samples, dwells, flights }
//   KD.rhythmScore()       — 0–100  (higher = more human-like)
//   KD.renderChart(canvas) — draw the live bar chart
//   KD.simulateBot(n,d,f)  — inject uniform bot keystrokes
// ═══════════════════════════════════════════════════════
const KD = (function () {

    const events = [];   // { type:'down'|'up', key, t }
    let _dwells  = [];
    let _flights = [];

    // ── Recompute derived series from raw events ──────
    function _recompute() {
        _dwells  = [];
        _flights = [];
        const downMap = {};
        let lastUp    = null;

        for (const ev of events) {
            if (ev.type === "down") {
                downMap[ev.key] = ev.t;
                if (lastUp !== null) {
                    const flight = ev.t - lastUp;
                    // Ignore pauses > 3 s — user stopped to think
                    if (flight > 0 && flight < 3000) _flights.push(flight);
                    lastUp = null;
                }
            } else if (ev.type === "up" && downMap[ev.key] !== undefined) {
                const dwell = ev.t - downMap[ev.key];
                if (dwell >= 0 && dwell < 500) _dwells.push(dwell);
                delete downMap[ev.key];
                lastUp = ev.t;
            }
        }
    }

    // Coefficient of variation: stddev / mean
    // 0 = perfectly uniform (bot), >0.3 = natural variance (human)
    function _cv(arr) {
        if (arr.length < 2) return 0;
        const mean = arr.reduce((a, b) => a + b, 0) / arr.length;
        if (mean === 0) return 0;
        const variance = arr.reduce((s, x) => s + (x - mean) ** 2, 0) / arr.length;
        return Math.sqrt(variance) / mean;
    }

    // ── Attach to an input element ────────────────────
    function attach(inputEl) {
        if (!inputEl) return;

        inputEl.addEventListener("keydown", function (e) {
            if (e.key.length > 1 && !["Backspace", "Delete"].includes(e.key)) return;
            events.push({ type: "down", key: e.key, t: Date.now() });
        });

        inputEl.addEventListener("keyup", function (e) {
            if (e.key.length > 1 && !["Backspace", "Delete"].includes(e.key)) return;
            events.push({ type: "up", key: e.key, t: Date.now() });
            _recompute();
            _updateLiveDisplay();
        });
    }

    // ── Public summary ────────────────────────────────
    function summary() {
        _recompute();
        return {
            dwells:   _dwells.slice(),
            flights:  _flights.slice(),
            cvDwell:  _cv(_dwells),
            cvFlight: _cv(_flights),
            samples:  _dwells.length,
        };
    }

    // ── Rhythm score 0–100 ────────────────────────────
    // < 20  → bot-like  (extremely uniform)
    // 20–50 → ambiguous
    // > 50  → human-like (natural variance)
    function rhythmScore() {
        const s = summary();
        if (s.samples < 3) return 50;   // insufficient data → neutral
        const combined = s.cvDwell * 0.6 + s.cvFlight * 0.4;
        return Math.min(100, Math.round((combined / 0.8) * 100));
    }

    // ── Update live UI elements ───────────────────────
    function _updateLiveDisplay() {
        const canvas = document.getElementById("rhythmChart");
        if (canvas) renderChart(canvas);

        const s     = summary();
        const score = rhythmScore();

        const scoreEl = document.getElementById("rhythmScore");
        const sampEl  = document.getElementById("rhythmSamples");
        const cvEl    = document.getElementById("rhythmCV");

        if (scoreEl) {
            scoreEl.textContent = score;
            scoreEl.style.color = score > 50
                ? "var(--green)"
                : score > 25 ? "var(--amber)" : "var(--red)";
        }
        if (sampEl) sampEl.textContent = s.samples + " keys";
        if (cvEl)   cvEl.textContent   = s.cvDwell.toFixed(2);
    }

    // ── Bar chart ─────────────────────────────────────
    // Dwell bars: green (slow/normal) → amber → red (very fast/bot)
    // Flight connectors: cyan, proportional to gap time
    function renderChart(canvas) {
        const s   = summary();
        const ctx = canvas.getContext("2d");
        const W   = canvas.width;
        const H   = canvas.height;
        ctx.clearRect(0, 0, W, H);

        if (s.dwells.length === 0) {
            ctx.fillStyle = "rgba(107,130,168,0.45)";
            ctx.font      = "10px 'Space Mono', monospace";
            ctx.textAlign = "center";
            ctx.fillText("Start typing to see keystroke rhythm...", W / 2, H / 2 + 4);
            return;
        }

        const maxVal = Math.max(...s.dwells, ...s.flights, 1);
        const n      = s.dwells.length;
        // Scale bar width so up to 20 keys fit comfortably
        const barW   = Math.max(4, Math.min(18, Math.floor((W - 12) / (n * 2.2))));
        const gap    = Math.max(2, Math.round(barW * 0.55));
        const totalW = n * (barW + gap) - gap;
        let   x      = Math.floor((W - totalW) / 2);
        const chartH = H - 22;  // leave room for labels

        s.dwells.forEach(function (dwell, i) {
            // Colour encodes speed: fast (red) = suspicious, slow (green) = natural
            const hue = dwell < 40
                ? "#ff4d6d"
                : dwell < 100 ? "#ffb347" : "#00e5a0";

            const barH = Math.max(2, Math.round((dwell / maxVal) * chartH));
            ctx.fillStyle = hue;
            ctx.beginPath();
            if (ctx.roundRect) {
                ctx.roundRect(x, chartH - barH + 2, barW, barH, 2);
            } else {
                ctx.rect(x, chartH - barH + 2, barW, barH);
            }
            ctx.fill();

            // Key index below bar
            ctx.fillStyle = "rgba(107,130,168,0.55)";
            ctx.font      = "7px 'Space Mono', monospace";
            ctx.textAlign = "center";
            ctx.fillText(i + 1, x + barW / 2, H - 3);

            // Flight-time connector to next bar
            if (i < s.flights.length) {
                const flightH = Math.max(1, Math.round((s.flights[i] / maxVal) * chartH));
                ctx.fillStyle = "rgba(0,200,255,0.30)";
                ctx.fillRect(x + barW, chartH - flightH + 2, gap, flightH);
            }

            x += barW + gap;
        });

        // Legend (top-left)
        ctx.font      = "8px 'Space Mono', monospace";
        ctx.textAlign = "left";
        [
            ["#00e5a0", "slow"],
            ["#ffb347", "medium"],
            ["#ff4d6d", "fast"],
            ["rgba(0,200,255,0.7)", "flight"],
        ].forEach(function ([color, label], li) {
            ctx.fillStyle = color;
            ctx.fillRect(4 + li * 46, 3, 7, 7);
            ctx.fillStyle = "rgba(107,130,168,0.7)";
            ctx.fillText(label, 13 + li * 46, 11);
        });
    }

    // ── Bot simulator: inject uniform keystrokes ──────
    // dwellMs and flightMs are the perfectly uniform intervals
    // a scripted bot would produce — zero natural variance.
    function simulateBot(n, dwellMs, flightMs) {
        n        = n        || 8;
        dwellMs  = dwellMs  || 14;
        flightMs = flightMs || 11;

        events.length = 0;
        let t = Date.now() - (n * (dwellMs + flightMs) + 50);
        for (let i = 0; i < n; i++) {
            const key = String.fromCharCode(65 + (i % 26));
            events.push({ type: "down", key: key, t: t });
            t += dwellMs;
            events.push({ type: "up",   key: key, t: t });
            t += flightMs;
        }
        _recompute();
        _updateLiveDisplay();
    }

    return { attach, summary, rhythmScore, renderChart, simulateBot };

})();   // end KD module


// ═══════════════════════════════════════════════════════
// ATTACH KEYSTROKE TRACKING to all inputs
// ═══════════════════════════════════════════════════════
KD.attach(captchaInput);
KD.attach(usernameField);
KD.attach(passwordField);


// ═══════════════════════════════════════════════════════
// MOUSE TRACKING
// ═══════════════════════════════════════════════════════
document.addEventListener("mousemove", function () {
    mouseMoves++;
    if (mouseDisplay) mouseDisplay.innerText = mouseMoves + " moves";
});


// ═══════════════════════════════════════════════════════
// CLICK TRACKING
// ═══════════════════════════════════════════════════════
document.addEventListener("click", function () {
    clicks++;
    if (clicksDisplay) clicksDisplay.innerText = clicks + " clicks";
});


// ═══════════════════════════════════════════════════════
// CAPTCHA INPUT — legacy typing time (kept for backend)
// ═══════════════════════════════════════════════════════
if (captchaInput) {
    captchaInput.addEventListener("focus", function () { typingStart = Date.now(); });
    captchaInput.addEventListener("keyup",  function () { typingTime  = Date.now() - typingStart; });
}


// ═══════════════════════════════════════════════════════
// LOGIN FIELD TRACKING
// ═══════════════════════════════════════════════════════
function trackLoginField(field) {
    if (!field) return;
    field.addEventListener("focus", function () {
        if (loginStartTime === null) loginStartTime = Date.now();
        if (lastFocusedField !== null && lastFocusedField !== field.id) focusSwitches++;
        lastFocusedField = field.id;
    });
    field.addEventListener("keyup",  function () { loginEndTime = Date.now(); });
    field.addEventListener("paste",  function () { usedPaste = true; });
}
trackLoginField(usernameField);
trackLoginField(passwordField);


// ═══════════════════════════════════════════════════════
// LIVE DISPLAY TICKER
// ═══════════════════════════════════════════════════════
setInterval(function () {
    if (timeDisplay)   timeDisplay.innerText   = (Date.now() - pageStart) + " ms";
    if (mouseDisplay)  mouseDisplay.innerText  = mouseMoves + " moves";
    if (clicksDisplay) clicksDisplay.innerText = clicks + " clicks";
}, 200);


// ═══════════════════════════════════════════════════════
// HELPER — inject / replace a hidden form field
// ═══════════════════════════════════════════════════════
function addHidden(form, name, value) {
    const existing = form.querySelector('input[name="' + name + '"]');
    if (existing) existing.remove();
    const field = document.createElement("input");
    field.type  = "hidden";
    field.name  = name;
    field.value = value;
    form.appendChild(field);
}


// ═══════════════════════════════════════════════════════
// CAPTCHA FORM SUBMIT
// ═══════════════════════════════════════════════════════
if (loginForm) {
    loginForm.addEventListener("submit", function () {
        if (isBot) return;
        const fillTime = (loginStartTime && loginEndTime)
            ? (loginEndTime - loginStartTime) : 0;
        addHidden(loginForm, "mouse_moves",    mouseMoves);
        addHidden(loginForm, "clicks",         clicks);
        addHidden(loginForm, "typing_time",    typingTime);
        addHidden(loginForm, "time_spent",     Date.now() - pageStart);
        addHidden(loginForm, "fill_time_ms",   fillTime);
        addHidden(loginForm, "focus_switches", focusSwitches);
        addHidden(loginForm, "used_paste",     usedPaste ? "true" : "false");
        addHidden(loginForm, "rhythm_score",   KD.rhythmScore());
        addHidden(loginForm, "rhythm_samples", KD.summary().samples);
    });
}


// ═══════════════════════════════════════════════════════
// CREDENTIALS FORM SUBMIT
// ═══════════════════════════════════════════════════════
// credForm merged into loginForm — handled above


// ═══════════════════════════════════════════════════════
// BOT SIMULATOR — Character CAPTCHA
// ═══════════════════════════════════════════════════════
function simulateBot() {
    const form = document.getElementById("captchaForm");
    if (!form) return;
    isBot = true;

    const botAnswerEl = document.getElementById("botAnswer");
    if (botAnswerEl && captchaInput) captchaInput.value = botAnswerEl.value;

    KD.simulateBot(6, 14, 11);   // perfectly uniform: exposes bot

    addHidden(form, "mouse_moves",    0);
    addHidden(form, "clicks",         1);
    addHidden(form, "typing_time",    10);
    addHidden(form, "time_spent",     80);
    addHidden(form, "rhythm_score",   KD.rhythmScore());
    addHidden(form, "rhythm_samples", KD.summary().samples);
    form.submit();
}


// ═══════════════════════════════════════════════════════
// BOT SIMULATOR — Tile CAPTCHA
// ═══════════════════════════════════════════════════════
function simulateBotTile() {
    const form = document.getElementById("tileCaptchaForm");
    if (!form) return;
    isBot = true;

    const correctEl      = document.getElementById("correctTiles");
    const correctIndices = correctEl
        ? correctEl.value.split(",").map(Number).filter(function(n){ return !isNaN(n); })
        : [];

    document.querySelectorAll("#tileGrid img").forEach(function(img){ img.classList.remove("selected"); });
    correctIndices.forEach(function (idx) {
        const img = document.querySelectorAll("#tileGrid img")[idx];
        if (img) img.classList.add("selected");
    });

    const selectedField = document.getElementById("selectedTilesField");
    if (selectedField) selectedField.value = correctIndices.sort().join(",");

    addHidden(form, "mouse_moves",  0);
    addHidden(form, "clicks",       1);
    addHidden(form, "typing_time",  10);
    addHidden(form, "time_spent",   80);

    setTimeout(function(){ form.submit(); }, 600);
}


// ═══════════════════════════════════════════════════════
// BOT SIMULATOR — Credentials
// ═══════════════════════════════════════════════════════
function simulateBotLogin() {
    const form = document.getElementById("credentialsForm");
    if (!form) return;
    isBot = true;

    const uField = document.getElementById("username");
    const pField = document.getElementById("password");
    if (uField) uField.value = "admin";
    if (pField) pField.value = "password123";

    KD.simulateBot(13, 14, 11);   // 5+8 = 13 characters, perfectly uniform

    addHidden(form, "mouse_moves",    0);
    addHidden(form, "clicks",         1);
    addHidden(form, "typing_time",    8);
    addHidden(form, "time_spent",     120);
    addHidden(form, "fill_time_ms",   90);
    addHidden(form, "focus_switches", 0);
    addHidden(form, "used_paste",     "false");
    addHidden(form, "rhythm_score",   KD.rhythmScore());
    addHidden(form, "rhythm_samples", KD.summary().samples);

    console.log("Bot rhythm score:", KD.rhythmScore(), "| CV dwell:", KD.summary().cvDwell.toFixed(3));
    setTimeout(function(){ form.submit(); }, 400);
}


// ═══════════════════════════════════════════════════════
// TILE SELECTION
// ═══════════════════════════════════════════════════════
const tileGrid = document.getElementById("tileGrid");
if (tileGrid) {
    const selectedTiles = new Set();
    const selectedField = document.getElementById("selectedTilesField");

    tileGrid.querySelectorAll("img").forEach(function (img) {
        img.addEventListener("click", function () {
            const idx = parseInt(img.dataset.index);
            if (selectedTiles.has(idx)) {
                selectedTiles.delete(idx);
                img.classList.remove("selected");
            } else {
                selectedTiles.add(idx);
                img.classList.add("selected");
            }
            if (selectedField) selectedField.value = Array.from(selectedTiles).sort().join(",");
        });
    });
}


// ═══════════════════════════════════════════════════════
// AUDIO CAPTCHA
// ═══════════════════════════════════════════════════════
function playAudioCaptcha() {
    const botAnswerEl = document.getElementById("botAnswer");
    if (!botAnswerEl || !window.speechSynthesis) return;
    const text = botAnswerEl.value.split("").join("... ");
    const utterance = new SpeechSynthesisUtterance(text);
    utterance.rate  = 0.75;
    utterance.pitch = 1.0;
    window.speechSynthesis.speak(utterance);
}


// ═══════════════════════════════════════════════════════
// CHART INIT — render empty state on page load
// ═══════════════════════════════════════════════════════
window.addEventListener("load", function () {
    const canvas = document.getElementById("rhythmChart");
    if (canvas) KD.renderChart(canvas);
});