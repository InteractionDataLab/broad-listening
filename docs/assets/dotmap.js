(function () {
"use strict";
const P = window.PAL, NONE = "#D2D2D2", FAM = '"Atkinson Next","Segoe UI",system-ui,sans-serif';
const cap = s => s.charAt(0).toUpperCase() + s.slice(1);
const SRC = { igem: ["IGEM_DOTS", "data/igem/igem-dots.json"], msf: ["MSF_DOTS", "data/msf/msf-dots.json"] };
const cache = {};
const load = k => cache[k] || (cache[k] = window[SRC[k][0]] ? Promise.resolve(window[SRC[k][0]]) : fetch(SRC[k][1]).then(r => { if (!r.ok) throw new Error(r.status); return r.json(); }));

function colours(k, D) {
  const c = {};
  if (k === "msf") D.themes.forEach(t => { c[t.id] = P.CAT[t.id]; });
  else D.themes.slice().sort((a, b) => b.n - a.n).forEach((t, i) => { c[t.id] = P.CAT[i]; });
  return c;
}
function draw(cv, D, col, labels, r) {
  const W = cv.clientWidth, H = cv.clientHeight, dpr = Math.max(1, window.devicePixelRatio || 1), fs = W < 420 ? 12 : 13.5, pad = 14;
  cv.width = Math.round(W * dpr); cv.height = Math.round(H * dpr);
  const c = cv.getContext("2d"); c.setTransform(dpr, 0, 0, dpr, 0, 0); c.clearRect(0, 0, W, H);
  const xs = D.x, ys = D.y, n = xs.length;
  let x0 = 1e9, x1 = -1e9, y0 = 1e9, y1 = -1e9;
  for (let i = 0; i < n; i++) { if (xs[i] < x0) x0 = xs[i]; if (xs[i] > x1) x1 = xs[i]; if (ys[i] < y0) y0 = ys[i]; if (ys[i] > y1) y1 = ys[i]; }
  const k = Math.min((W - 2 * pad) / (x1 - x0), (H - 2 * pad) / (y1 - y0)), ox = (W - k * (x1 - x0)) / 2, oy = (H - k * (y1 - y0)) / 2;
  const X = i => ox + (xs[i] - x0) * k, Y = i => H - oy - (ys[i] - y0) * k, rr = W < 420 ? r * .8 : r;
  c.globalAlpha = .8;
  for (const pass of [0, 1]) for (let i = 0; i < n; i++) {
    const none = D.t[i] < 0; if ((pass === 0) !== none) continue;
    c.fillStyle = none ? NONE : col[D.t[i]]; c.beginPath(); c.arc(X(i), Y(i), none ? rr * .8 : rr, 0, 6.2832); c.fill();
  }
  c.globalAlpha = 1;
  const med = a => { const s = a.slice().sort((p, q) => p - q); return s[s.length >> 1]; };
  c.font = "600 " + fs + "px " + FAM; c.textAlign = "center"; c.textBaseline = "middle"; c.lineJoin = "round";
  const lh = fs * 1.18;

  const small = (px, py, w, h) => { const sp = a => { const s = a.slice().sort((p, q) => p - q); return s[Math.floor(s.length * .75)] - s[Math.floor(s.length * .25)]; }; return sp(px) < w * .8 && sp(py) < h * 1.6; };
  const L = labels.map(l => {
    const px = [], py = []; for (let i = 0; i < n; i++) if (D.t[i] === l.id) { px.push(X(i)); py.push(Y(i)); }
    let lines = [l.text];
    if (l.text.length > 24) { const w = l.text.split(" "); let a = "", j = 0; while (j < w.length && (a + " " + w[j]).trim().length <= Math.ceil(l.text.length / 2) + 2) { a = (a + " " + w[j]).trim(); j++; } lines = [a, w.slice(j).join(" ")].filter(Boolean); }
    const w = Math.max(...lines.map(s => c.measureText(s).width));

    const mx = med(px), my = med(py); let kb = 0, db = 1e18;
    for (let i = 0; i < px.length; i++) { const d = (px[i] - mx) * (px[i] - mx) + (py[i] - my) * (py[i] - my); if (d < db) { db = d; kb = i; } }
    return { id: l.id, lines, color: l.color, w, h: lines.length * lh, x: Math.max(w / 2 + 4, Math.min(W - w / 2 - 4, px[kb])), y: py[kb] + (small(px, py, w, lines.length * lh) ? (py[kb] > H - lines.length * lh - 30 ? -1 : 1) * (lines.length * lh / 2 + 12) : 0) };
  });
  for (let it = 0; it < 24; it++) for (let a = 0; a < L.length; a++) for (let b = a + 1; b < L.length; b++) {
    const p = L[a], q = L[b], needY = (p.h + q.h) / 2 + 3;
    if (Math.abs(p.x - q.x) < (p.w + q.w) / 2 + 8 && Math.abs(p.y - q.y) < needY) { const d = (needY - Math.abs(p.y - q.y)) / 2 + .5; if (p.y <= q.y) { p.y -= d; q.y += d; } else { p.y += d; q.y -= d; } }
  }
  L.forEach(l => {
    l.y = Math.max(l.h / 2 + 2, Math.min(H - l.h / 2 - 2, l.y));
    l.lines.forEach((s, j) => { const y = l.y - l.h / 2 + lh * (j + .5); c.strokeStyle = "#ffffff"; c.lineWidth = 4; c.strokeText(s, l.x, y); c.fillStyle = l.color; c.fillText(s, l.x, y); });
  });
  return L;
}
function setup(cv) {
  const k = cv.dataset.dots, nLab = +(cv.dataset.labels || 99);
  load(k).then(D => {
    const col = colours(k, D), top = D.themes.slice().sort((a, b) => b.n - a.n), tot = D.t.length, none = D.t.filter(v => v < 0).length;
    const labels = top.slice(0, nLab).map(t => ({ id: t.id, text: cap(t.name), color: P.ink(col[t.id], "#ffffff") }));
    cv.setAttribute("aria-label", "Map of " + tot.toLocaleString("en-US") + " texts, one dot each, coloured by theme. " + D.themes.length + " themes; the largest is " + cap(top[0].name) + "." + (none ? " " + none + " texts have no theme and are grey." : ""));
    let boxes = [];
    const paint = () => { if (cv.clientWidth) boxes = draw(cv, D, col, labels, +(cv.dataset.r || 2)); };
    (document.fonts && document.fonts.load ? document.fonts.load('600 13px "Atkinson Next"') : Promise.resolve()).then(paint, paint);
    let tm; window.addEventListener("resize", () => { clearTimeout(tm); tm = setTimeout(paint, 150); });
    if (cv.dataset.jump) {
      const hit = e => { const r = cv.getBoundingClientRect(), x = e.clientX - r.left, y = e.clientY - r.top; return boxes.find(b => Math.abs(x - b.x) <= b.w / 2 + 4 && Math.abs(y - b.y) <= b.h / 2 + 3); };
      cv.style.cursor = "pointer";
      cv.addEventListener("click", e => { const b = hit(e); location.hash = b ? "theme=" + b.id : "map"; });
    }
  }).catch(() => {});
}

function fitCharts() {
  if (window.innerWidth >= 760) return;
  document.querySelectorAll(".figbox svg").forEach(s => { const vb = s.viewBox && s.viewBox.baseVal; if (vb && vb.width >= 420 && !s.style.minWidth) s.style.minWidth = Math.round(vb.width * .9) + "px"; });
}
function start() {
  document.querySelectorAll("canvas[data-dots]").forEach(setup);
  fitCharts();
  if ("MutationObserver" in window) new MutationObserver(fitCharts).observe(document.body, { childList: true, subtree: true });
  window.addEventListener("beforeprint", () => document.querySelectorAll("details.notesbox, details.fold").forEach(d => { d.open = true; }));
}
if (document.readyState === "loading") document.addEventListener("DOMContentLoaded", start); else start();
})();
