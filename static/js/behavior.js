// =============================================
// behavior.js  —  tracks human vs bot signals
// and provides a bot simulator for demos
// =============================================

console.log("behavior.js loaded");

// ── Shared state ──────────────────────────────
let mouseMoves  = 0;
let clicks      = 0;
let typingStart = 0;
let typingTime  = 0;
let pageStart   = Date.now();
let isBot       = false;

// ── DOM references ────────────────────────────
const mouseDisplay  = document.getElementById("mouseActivity");
const clicksDisplay = document.getElementById("clicksActivity");
const timeDisplay   = document.getElementById("responseTime");
const captchaInput  = document.getElementById("captchaInput");
const captchaForm   = document.getElementById("captchaForm");

// =============================================
// MOUSE TRACKING
// =============================================
document.addEventListener("mousemove", function () {
    mouseMoves++;
    if (mouseDisplay) {
        mouseDisplay.innerText = mouseMoves + " moves";
    }
});

// =============================================
// CLICK TRACKING
// =============================================
document.addEventListener("click", function () {
    clicks++;
    if (clicksDisplay) {
        clicksDisplay.innerText = clicks + " clicks";
    }
});

// =============================================
// TYPING TRACKING  (character CAPTCHA only)
// =============================================
if (captchaInput) {
    captchaInput.addEventListener("focus", function () {
        typingStart = Date.now();
    });

    captchaInput.addEventListener("keyup", function () {
        typingTime = Date.now() - typingStart;
    });
}

// =============================================
// LIVE DISPLAY — update all three counters
// =============================================
setInterval(function () {
    if (timeDisplay) {
        timeDisplay.innerText = (Date.now() - pageStart) + " ms";
    }
    if (mouseDisplay) {
        mouseDisplay.innerText = mouseMoves + " moves";
    }
    if (clicksDisplay) {
        clicksDisplay.innerText = clicks + " clicks";
    }
}, 200);

// =============================================
// HELPER — append a hidden field to a form
// =============================================
function addHidden(form, name, value) {
    const existing = form.querySelector(`input[name="${name}"]`);
    if (existing) existing.remove();

    const field = document.createElement("input");
    field.type  = "hidden";
    field.name  = name;
    field.value = value;
    form.appendChild(field);
}

// =============================================
// FORM SUBMIT — inject behaviour metrics
// =============================================
if (captchaForm) {
    captchaForm.addEventListener("submit", function () {
        if (isBot) return;

        const timeSpent = Date.now() - pageStart;

        addHidden(captchaForm, "mouse_moves",  mouseMoves);
        addHidden(captchaForm, "clicks",       clicks);
        addHidden(captchaForm, "typing_time",  typingTime);
        addHidden(captchaForm, "time_spent",   timeSpent);
    });
}

// =============================================
// BOT SIMULATOR — Character CAPTCHA
// =============================================
function simulateBot() {
    const form = document.getElementById("captchaForm");
    if (!form) return;

    isBot = true;

    const botAnswerEl = document.getElementById("botAnswer");
    if (botAnswerEl && captchaInput) {
        captchaInput.value = botAnswerEl.value;
    }

    addHidden(form, "mouse_moves",  0);
    addHidden(form, "clicks",       1);
    addHidden(form, "typing_time",  10);
    addHidden(form, "time_spent",   80);

    console.log("🤖 Bot simulated: answer =", botAnswerEl ? botAnswerEl.value : "N/A");

    form.submit();
}

// =============================================
// TILE SELECTION  (tile_captcha.html only)
// =============================================
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

            if (selectedField) {
                selectedField.value = Array.from(selectedTiles).sort().join(",");
            }

            console.log("Selected tiles:", Array.from(selectedTiles));
        });
    });
}

// =============================================
// BOT SIMULATOR — Tile CAPTCHA
// =============================================
function simulateBotTile() {
    const form = document.getElementById("tileCaptchaForm");
    if (!form) return;

    isBot = true;

    const correctEl      = document.getElementById("correctTiles");
    const correctIndices = correctEl
        ? correctEl.value.split(",").map(Number).filter(n => !isNaN(n))
        : [];

    const tileImgs = document.querySelectorAll("#tileGrid img");
    tileImgs.forEach(img => img.classList.remove("selected"));
    correctIndices.forEach(function (idx) {
        const img = tileImgs[idx];
        if (img) img.classList.add("selected");
    });

    const selectedField = document.getElementById("selectedTilesField");
    if (selectedField) {
        selectedField.value = correctIndices.sort().join(",");
    }

    addHidden(form, "mouse_moves",  0);
    addHidden(form, "clicks",       1);
    addHidden(form, "typing_time",  10);
    addHidden(form, "time_spent",   80);

    console.log("🤖 Bot selecting tiles:", correctIndices);

    setTimeout(function () {
        form.submit();
    }, 600);
}

// =============================================
// AUDIO CAPTCHA — reads CAPTCHA text aloud
// Uses Web Speech API (no backend required)
// =============================================
function playAudioCaptcha() {
    const botAnswerEl = document.getElementById("botAnswer");
    if (!botAnswerEl || !window.speechSynthesis) return;

    // Spell out each character with pauses so it's clear
    const text = botAnswerEl.value.split("").join("... ");
    const utterance = new SpeechSynthesisUtterance(text);
    utterance.rate = 0.75;    // slower = clearer
    utterance.pitch = 1.0;
    window.speechSynthesis.speak(utterance);
}