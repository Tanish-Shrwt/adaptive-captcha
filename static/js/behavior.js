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

// FIX: isBot was referenced but never declared — caused ReferenceError
//      that silently broke ALL real-user form submissions.
//      It is now a proper flag set only by simulateBot().
let isBot = false;

// ── DOM references (safe — checked before use) ──
const mouseDisplay = document.getElementById("mouseActivity");
const timeDisplay  = document.getElementById("responseTime");
const captchaInput = document.getElementById("captchaInput");
const captchaForm  = document.getElementById("captchaForm");

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
});

// =============================================
// TYPING TRACKING  (character CAPTCHA only)
// Records time from first focus to last keyup.
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
// LIVE RESPONSE-TIME DISPLAY
// Updates the "Response Time" stat every 200ms
// =============================================
setInterval(function () {
    if (timeDisplay) {
        timeDisplay.innerText = (Date.now() - pageStart) + " ms";
    }
}, 200);

// =============================================
// HELPER — append a hidden field to a form
// =============================================
function addHidden(form, name, value) {
    // Remove any existing field with same name first
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
// Runs for both character and tile forms.
// FIX: was guarded by undefined `isBot` variable.
//      Now uses the properly declared flag above.
// =============================================
if (captchaForm) {
    captchaForm.addEventListener("submit", function () {
        if (isBot) return;   // bot simulator handles its own fields

        const timeSpent = Date.now() - pageStart;

        addHidden(captchaForm, "mouse_moves",  mouseMoves);
        addHidden(captchaForm, "clicks",       clicks);
        addHidden(captchaForm, "typing_time",  typingTime);
        addHidden(captchaForm, "time_spent",   timeSpent);
    });
}

// =============================================
// BOT SIMULATOR — Character CAPTCHA
//
// Called by the "🤖 Simulate Bot Attack" button
// on captcha.html.
//
// FIX: bot_answer is now actually passed from
//      app.py so this correctly fills the answer.
//
// Injects bot-like behaviour metrics so the
// risk engine detects it and escalates.
// =============================================
function simulateBot() {
    const form = document.getElementById("captchaForm");
    if (!form) return;

    isBot = true;   // prevent the submit listener from overwriting our values

    // Fill in the correct answer (read from hidden field set by app.py)
    const botAnswerEl = document.getElementById("botAnswer");
    if (botAnswerEl && captchaInput) {
        captchaInput.value = botAnswerEl.value;
    }

    // Inject worst-case bot behaviour metrics
    // These values will trigger all the strong-signal checks in calculate_risk()
    addHidden(form, "mouse_moves",  0);    // zero mouse movement
    addHidden(form, "clicks",       1);    // single programmatic click
    addHidden(form, "typing_time",  10);   // 10ms — impossible for human
    addHidden(form, "time_spent",   80);   // 80ms total page time — impossible

    console.log("🤖 Bot simulated: answer =", botAnswerEl ? botAnswerEl.value : "N/A");

    form.submit();
}

// =============================================
// TILE SELECTION  (tile_captcha.html only)
//
// Handles click-to-select on the 3×3 image grid.
// Keeps a Set of selected indices and updates
// the hidden "selected_tiles" field before submit.
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

            // Keep hidden field in sync
            if (selectedField) {
                selectedField.value = Array.from(selectedTiles).sort().join(",");
            }

            console.log("Selected tiles:", Array.from(selectedTiles));
        });
    });
}

// =============================================
// BOT SIMULATOR — Tile CAPTCHA
//
// Called by the "🤖 Simulate Bot Attack" button
// on tile_captcha.html.
//
// Reads correct tile indices from the hidden
// "correctTiles" field (set by app.py),
// visually selects them, injects bot metrics,
// and submits.
// =============================================
function simulateBotTile() {
    const form = document.getElementById("tileCaptchaForm");
    if (!form) return;

    isBot = true;

    // Read correct tile indices passed from app.py
    const correctEl = document.getElementById("correctTiles");
    const correctIndices = correctEl
        ? correctEl.value.split(",").map(Number).filter(n => !isNaN(n))
        : [];

    // Visually highlight the tiles being "selected" by the bot
    const tileImgs = document.querySelectorAll("#tileGrid img");
    tileImgs.forEach(img => img.classList.remove("selected"));

    correctIndices.forEach(function (idx) {
        const img = tileImgs[idx];
        if (img) img.classList.add("selected");
    });

    // Set the hidden selected_tiles field
    const selectedField = document.getElementById("selectedTilesField");
    if (selectedField) {
        selectedField.value = correctIndices.sort().join(",");
    }

    // Inject bot behaviour metrics
    addHidden(form, "mouse_moves",  0);
    addHidden(form, "clicks",       1);
    addHidden(form, "typing_time",  10);
    addHidden(form, "time_spent",   80);

    // Short delay so the professor can SEE the tiles being selected
    // before the form submits
    console.log("🤖 Bot selecting tiles:", correctIndices);

    setTimeout(function () {
        form.submit();
    }, 600);
}