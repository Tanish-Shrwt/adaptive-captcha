// dashboard.js — chart rendering, table filters, live clock

// ════════════════════════════════════════════════════════
// LIVE CLOCK
// ════════════════════════════════════════════════════════
(function tick() {
  const el = document.getElementById("dashClock");
  if (el) el.textContent = new Date().toLocaleTimeString();
  setTimeout(tick, 1000);
})();


// ════════════════════════════════════════════════════════
// LOG TABLE FILTER
// ════════════════════════════════════════════════════════
document.querySelectorAll(".filter-btn").forEach(function (btn) {
  btn.addEventListener("click", function () {
    document.querySelectorAll(".filter-btn").forEach(function (b) {
      b.classList.remove("active");
    });
    this.classList.add("active");

    const f = this.dataset.filter;
    document.querySelectorAll("#logBody tr[data-is-bot]").forEach(function (row) {
      const bot     = row.dataset.isBot    === "true";
      const success = row.dataset.success  === "true";
      const denied  = row.dataset.denied   === "true";

      row.style.display =
        f === "all"    ? "" :
        f === "bot"    ? (bot     ? "" : "none") :
        f === "human"  ? (!bot    ? "" : "none") :
        f === "fail"   ? (!success ? "" : "none") :
        f === "denied" ? (denied   ? "" : "none") : "";
    });
  });
});


// ════════════════════════════════════════════════════════
// RISK SCORE TIMELINE CHART
// Reads data from rendered table rows (no extra API call).
// Dots are green (human) or red (bot).
// Threshold dashed lines mark each CAPTCHA escalation point.
// ════════════════════════════════════════════════════════
(function () {
  const rows = Array.from(
    document.querySelectorAll("#logBody tr[data-is-bot]")
  ).slice(0, 20);

  if (!rows.length) return;

  const ordered = rows.slice().reverse();   // oldest → newest (left → right)
  const scores  = ordered.map(function (r) {
    const sp = r.querySelector(".risk-mini span");
    return sp ? (parseInt(sp.textContent) || 0) : 0;
  });
  const isBot = ordered.map(function (r) {
    return r.dataset.isBot === "true";
  });

  const canvas = document.getElementById("riskChart");
  if (!canvas) return;

  const W = canvas.parentElement.clientWidth - 40 || 700;
  const H = 170;
  canvas.width  = W;
  canvas.height = H;
  const ctx = canvas.getContext("2d");

  const maxScore = Math.max(...scores, 15);
  const pL = 40, pR = 20, pT = 14, pB = 32;
  const cW = W - pL - pR, cH = H - pT - pB;

  const xOf = function (i) { return pL + (i / Math.max(scores.length - 1, 1)) * cW; };
  const yOf = function (v) { return pT + cH - (v / maxScore) * cH; };

  // Horizontal grid lines
  [0, 0.25, 0.5, 0.75, 1].forEach(function (t) {
    const y = pT + cH * (1 - t);
    ctx.strokeStyle = "#f1f5f9"; ctx.lineWidth = 1;
    ctx.beginPath(); ctx.moveTo(pL, y); ctx.lineTo(W - pR, y); ctx.stroke();
    ctx.fillStyle = "#94a3b8";
    ctx.font = "9px 'JetBrains Mono', monospace";
    ctx.textAlign = "right";
    ctx.fillText(Math.round(maxScore * t), pL - 6, y + 3);
  });

  // CAPTCHA escalation threshold lines
  function drawThreshold(val, color, label) {
    if (val > maxScore) return;
    const y = yOf(val);
    ctx.strokeStyle = color; ctx.lineWidth = 1;
    ctx.setLineDash([4, 4]);
    ctx.beginPath(); ctx.moveTo(pL, y); ctx.lineTo(W - pR, y); ctx.stroke();
    ctx.setLineDash([]);
    ctx.fillStyle = color;
    ctx.font = "9px 'JetBrains Mono', monospace";
    ctx.textAlign = "left";
    ctx.fillText(label, W - pR - 62, y - 3);
  }
  drawThreshold(4,  "rgba(217,119,6,.45)",  "MATH ▲4");
  drawThreshold(7,  "rgba(234,179,8,.45)",  "TILE ▲7");
  drawThreshold(11, "rgba(239,68,68,.4)",   "DRAG ▲11");
  drawThreshold(15, "rgba(190,24,93,.4)",   "ROT ▲15");

  // Area fill
  const grad = ctx.createLinearGradient(0, pT, 0, H - pB);
  grad.addColorStop(0, "rgba(37,99,235,0.15)");
  grad.addColorStop(1, "rgba(37,99,235,0)");
  ctx.beginPath();
  scores.forEach(function (s, i) {
    i === 0 ? ctx.moveTo(xOf(i), yOf(s)) : ctx.lineTo(xOf(i), yOf(s));
  });
  ctx.lineTo(xOf(scores.length - 1), H - pB);
  ctx.lineTo(xOf(0), H - pB);
  ctx.closePath();
  ctx.fillStyle = grad;
  ctx.fill();

  // Line
  ctx.beginPath();
  ctx.strokeStyle = "#2563eb"; ctx.lineWidth = 2; ctx.lineJoin = "round";
  scores.forEach(function (s, i) {
    i === 0 ? ctx.moveTo(xOf(i), yOf(s)) : ctx.lineTo(xOf(i), yOf(s));
  });
  ctx.stroke();

  // Dots coloured by bot (red) vs human (green)
  scores.forEach(function (s, i) {
    ctx.beginPath();
    ctx.arc(xOf(i), yOf(s), 4.5, 0, Math.PI * 2);
    ctx.fillStyle   = isBot[i] ? "#ef4444" : "#16a34a";
    ctx.strokeStyle = "#fff"; ctx.lineWidth = 2;
    ctx.fill(); ctx.stroke();
  });

  // X-axis time labels
  const step = Math.max(1, Math.floor(scores.length / 6));
  ordered.forEach(function (row, i) {
    if (i % step !== 0 && i !== scores.length - 1) return;
    const td = row.querySelector("td.dim");
    const ts = td ? td.textContent.trim().slice(11, 16) : "";
    ctx.fillStyle = "#94a3b8";
    ctx.font = "9px 'JetBrains Mono', monospace";
    ctx.textAlign = "center";
    ctx.fillText(ts, xOf(i), H - pB + 18);
  });

  // Legend
  ctx.textAlign = "left";
  [["#16a34a", "Human"], ["#ef4444", "Bot"]].forEach(function ([c, label], li) {
    const lx = pL + li * 72, ly = H - pB + 18;
    ctx.beginPath(); ctx.arc(lx + 5, ly - 4, 4, 0, Math.PI * 2);
    ctx.fillStyle = c; ctx.fill();
    ctx.fillStyle = "#64748b";
    ctx.font = "9px 'Inter', sans-serif";
    ctx.fillText(label, lx + 13, ly);
  });
})();