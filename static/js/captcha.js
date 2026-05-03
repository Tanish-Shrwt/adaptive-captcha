// captcha.js — CAPTCHA interaction logic
// Covers: tile selection, drag-to-match, rotation, bot simulator
// Depends on: behavior.js (KD, addHidden must be loaded first)

// ════════════════════════════════════════════════════════
// TILE SELECTION
// ════════════════════════════════════════════════════════
(function () {
  const grid = document.getElementById("tileGrid");
  if (!grid) return;

  const selected = new Set();
  const field    = document.getElementById("selectedTilesField");

  grid.querySelectorAll("img").forEach(function (img) {
    img.addEventListener("click", function () {
      const idx = parseInt(img.dataset.index);
      if (selected.has(idx)) {
        selected.delete(idx);
        img.classList.remove("selected");
      } else {
        selected.add(idx);
        img.classList.add("selected");
      }
      if (field) field.value = Array.from(selected).sort().join(",");
    });
  });
})();


// ════════════════════════════════════════════════════════
// DRAG-TO-MATCH
// Draws shapes on <canvas> and handles drag/click matching.
// ════════════════════════════════════════════════════════
(function () {
  const srcCanvas = document.getElementById("dragSource");
  if (!srcCanvas) return;

  // These data attributes are set by the template
  const dragShape   = srcCanvas.dataset.shape;
  const dragTargets = JSON.parse(document.getElementById("dragTargetsData").value);
  const correctIdx  = parseInt(document.getElementById("dragCorrectIdx").value);
  const answerField = document.getElementById("dragAnswerField");
  const hint        = document.getElementById("dragHint");
  let   answered    = false;

  // Shape colour palette
  const FILLS   = { circle:"#bfdbfe", square:"#d1fae5", triangle:"#fde68a", star:"#fce7f3", diamond:"#ede9fe", hexagon:"#ffedd5" };
  const STROKES = { circle:"#2563eb", square:"#16a34a", triangle:"#b45309", star:"#be185d", diamond:"#7c3aed", hexagon:"#c2410c" };

  function drawShape(canvas, shape, size, fill, stroke) {
    const ctx = canvas.getContext("2d");
    const cx  = canvas.width / 2, cy = canvas.height / 2;
    ctx.clearRect(0, 0, canvas.width, canvas.height);
    ctx.fillStyle   = fill   || FILLS[shape]   || "#dbeafe";
    ctx.strokeStyle = stroke || STROKES[shape] || "#1e293b";
    ctx.lineWidth   = 2.5;

    switch (shape) {
      case "circle":
        ctx.beginPath();
        ctx.arc(cx, cy, size * .42, 0, Math.PI * 2);
        ctx.fill(); ctx.stroke();
        break;

      case "square":
        const s = size * .7, sx = cx - s/2, sy = cy - s/2;
        ctx.beginPath();
        ctx.roundRect(sx, sy, s, s, 4);
        ctx.fill(); ctx.stroke();
        break;

      case "triangle":
        const r = size * .45;
        ctx.beginPath();
        ctx.moveTo(cx, cy - r);
        ctx.lineTo(cx + r * Math.cos(Math.PI/6), cy + r * Math.sin(Math.PI/6));
        ctx.lineTo(cx - r * Math.cos(Math.PI/6), cy + r * Math.sin(Math.PI/6));
        ctx.closePath();
        ctx.fill(); ctx.stroke();
        break;

      case "star":
        const R = size * .42, ri = size * .18, n = 5;
        ctx.beginPath();
        for (let i = 0; i < n * 2; i++) {
          const rad  = (i * Math.PI / n) - Math.PI / 2;
          const dist = i % 2 === 0 ? R : ri;
          i === 0
            ? ctx.moveTo(cx + dist * Math.cos(rad), cy + dist * Math.sin(rad))
            : ctx.lineTo(cx + dist * Math.cos(rad), cy + dist * Math.sin(rad));
        }
        ctx.closePath();
        ctx.fill(); ctx.stroke();
        break;

      case "diamond":
        const dh = size * .48, dw = size * .34;
        ctx.beginPath();
        ctx.moveTo(cx, cy - dh); ctx.lineTo(cx + dw, cy);
        ctx.lineTo(cx, cy + dh); ctx.lineTo(cx - dw, cy);
        ctx.closePath();
        ctx.fill(); ctx.stroke();
        break;

      case "hexagon":
        const hr = size * .42;
        ctx.beginPath();
        for (let i = 0; i < 6; i++) {
          const a = Math.PI / 3 * i - Math.PI / 6;
          i === 0
            ? ctx.moveTo(cx + hr * Math.cos(a), cy + hr * Math.sin(a))
            : ctx.lineTo(cx + hr * Math.cos(a), cy + hr * Math.sin(a));
        }
        ctx.closePath();
        ctx.fill(); ctx.stroke();
        break;
    }
  }

  // Draw source shape and all target shapes
  drawShape(srcCanvas, dragShape, 72);
  dragTargets.forEach(function (shape, i) {
    const tc = document.getElementById("targetCanvas" + i);
    if (tc) drawShape(tc, shape, 52);
  });

  // Handle a pick (click or drop)
  function pick(idx) {
    if (answered) return;
    answered = true;
    if (answerField) answerField.value = idx;
    const tgt = document.getElementById("target" + idx);
    if (idx === correctIdx) {
      tgt.classList.add("correct-drop");
      if (hint) hint.textContent = "✓ Correct match!";
    } else {
      tgt.classList.add("wrong-drop");
      const correct = document.getElementById("target" + correctIdx);
      if (correct) correct.classList.add("correct-drop");
      if (hint) hint.textContent = "✗ Wrong — correct target highlighted";
    }
  }

  // Click-to-match on targets
  document.querySelectorAll(".drag-target").forEach(function (el) {
    el.addEventListener("click", function () { pick(parseInt(el.dataset.idx)); });
  });

  // Drag support (mouse + touch)
  let dragging = false, dragGhost = null;

  function startDrag(cx, cy) {
    dragging   = true;
    dragGhost  = srcCanvas.cloneNode(true);
    const ctx2 = dragGhost.getContext("2d");
    ctx2.drawImage(srcCanvas, 0, 0);
    Object.assign(dragGhost.style, {
      position: "fixed", pointerEvents: "none", opacity: "0.8",
      zIndex: "999", left: cx - 36 + "px", top: cy - 36 + "px", borderRadius: "6px"
    });
    document.body.appendChild(dragGhost);
  }

  function moveDrag(cx, cy) {
    if (!dragging || !dragGhost) return;
    dragGhost.style.left = cx - 36 + "px";
    dragGhost.style.top  = cy - 36 + "px";
    document.querySelectorAll(".drag-target").forEach(function (el) {
      const r = el.getBoundingClientRect();
      if (cx >= r.left && cx <= r.right && cy >= r.top && cy <= r.bottom)
        el.classList.add("over");
      else
        el.classList.remove("over");
    });
  }

  function endDrag(cx, cy) {
    if (!dragging) return;
    dragging = false;
    if (dragGhost) { dragGhost.remove(); dragGhost = null; }
    document.querySelectorAll(".drag-target").forEach(function (el) {
      el.classList.remove("over");
      const r = el.getBoundingClientRect();
      if (cx >= r.left && cx <= r.right && cy >= r.top && cy <= r.bottom)
        pick(parseInt(el.dataset.idx));
    });
  }

  srcCanvas.addEventListener("mousedown",  function (e) { e.preventDefault(); startDrag(e.clientX, e.clientY); });
  document.addEventListener("mousemove",   function (e) { moveDrag(e.clientX, e.clientY); });
  document.addEventListener("mouseup",     function (e) { endDrag(e.clientX, e.clientY); });
  srcCanvas.addEventListener("touchstart", function (e) { e.preventDefault(); startDrag(e.touches[0].clientX, e.touches[0].clientY); }, { passive: false });
  document.addEventListener("touchmove",   function (e) { if (dragging) { e.preventDefault(); moveDrag(e.touches[0].clientX, e.touches[0].clientY); } }, { passive: false });
  document.addEventListener("touchend",    function (e) { endDrag(e.changedTouches[0].clientX, e.changedTouches[0].clientY); });
})();


// ════════════════════════════════════════════════════════
// ROTATION CAPTCHA
// ════════════════════════════════════════════════════════
(function () {
  const slider  = document.getElementById("rotSlider");
  const rotImg  = document.getElementById("rotImg");
  const display = document.getElementById("rotAngleDisplay");
  const field   = document.getElementById("rotationAnswerField");
  if (!slider) return;

  function applyRotation(deg) {
    const a = ((deg % 360) + 360) % 360;
    slider.value = a;
    if (display) display.textContent = a + "°";
    if (rotImg)  rotImg.style.transform = "rotate(" + a + "deg)";
    if (field)   field.value = a;
  }

  slider.addEventListener("input", function () {
    applyRotation(parseInt(slider.value));
  });
})();

// Global helper for the ±15° buttons in the template
window.rotateBy = function (delta) {
  const slider = document.getElementById("rotSlider");
  if (!slider) return;
  const newVal = ((parseInt(slider.value) + delta) % 360 + 360) % 360;
  slider.value = newVal;
  slider.dispatchEvent(new Event("input"));
};


// ════════════════════════════════════════════════════════
// AUDIO CAPTCHA
// ════════════════════════════════════════════════════════
window.playAudioCaptcha = function () {
  const el = document.getElementById("botAnswer");
  if (!el || !window.speechSynthesis) return;
  const utterance = new SpeechSynthesisUtterance(
    el.value.split("").join("... ")
  );
  utterance.rate  = 0.75;
  utterance.pitch = 1.0;
  window.speechSynthesis.speak(utterance);
};


// ════════════════════════════════════════════════════════
// BOT SIMULATOR
// Solves the current CAPTCHA, injects bot-like signals,
// marks is_simulated_bot=true, then submits.
// Backend denies access and logs it as access_denied.
// ════════════════════════════════════════════════════════
window.simulateBotAttack = function () {
  const form  = document.getElementById("loginForm");
  const ctype = form.querySelector('input[name="captcha_type"]').value;

  addHidden(form, "is_simulated_bot", "true");

  document.getElementById("username").value = "admin";
  document.getElementById("password").value = "password123";

  if (ctype === "text") {
    const ci  = document.getElementById("captchaInput");
    const bot = document.getElementById("botAnswer");
    if (ci && bot) ci.value = bot.value;

  } else if (ctype === "math") {
    const mi  = document.getElementById("mathInput");
    const bot = document.getElementById("botAnswer");
    if (mi && bot) mi.value = bot.value;

  } else if (ctype === "tile") {
    const correctEl = document.getElementById("correctTiles");
    const indices   = correctEl
      ? correctEl.value.split(",").map(Number).filter(function (n) { return !isNaN(n); })
      : [];
    document.querySelectorAll("#tileGrid img").forEach(function (img) {
      img.classList.remove("selected");
    });
    indices.forEach(function (idx) {
      const img = document.querySelectorAll("#tileGrid img")[idx];
      if (img) img.classList.add("selected");
    });
    const sf = document.getElementById("selectedTilesField");
    if (sf) sf.value = indices.sort().join(",");

  } else if (ctype === "drag") {
    const ci = parseInt(document.getElementById("dragCorrectIdx").value);
    document.getElementById("dragAnswerField").value = ci;

  } else if (ctype === "rotation") {
    const correct = parseInt(
      document.getElementById("rotationCorrectValue").value || "0"
    );
    document.getElementById("rotationAnswerField").value = correct;
    const slider = document.getElementById("rotSlider");
    if (slider) { slider.value = correct; slider.dispatchEvent(new Event("input")); }
  }

  KD.simulateBot(10, 13, 10);
  addHidden(form, "mouse_moves",    0);
  addHidden(form, "clicks",         1);
  addHidden(form, "typing_time",    9);
  addHidden(form, "time_spent",     95);
  addHidden(form, "fill_time_ms",   90);
  addHidden(form, "focus_switches", 0);
  addHidden(form, "used_paste",     "false");
  addHidden(form, "rhythm_score",   KD.rhythmScore());
  addHidden(form, "rhythm_samples", KD.summary().samples);

  form.submit();
};


// ════════════════════════════════════════════════════════
// INIT — render empty rhythm chart on page load
// ════════════════════════════════════════════════════════
window.addEventListener("load", function () {
  const canvas = document.getElementById("rhythmChart");
  if (canvas) KD.renderChart(canvas);
});