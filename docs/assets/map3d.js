(function () {
"use strict";
function norm(xs, ys, zs) {

  const med = a => { const s = Array.from(a).sort((p, q) => p - q); return s[Math.floor(s.length / 2)]; };
  const n = xs.length, mx = med(xs), my = med(ys), mz = zs ? med(zs) : 0;
  const d = new Float64Array(n);
  for (let i = 0; i < n; i++) { const a = xs[i] - mx, b = ys[i] - my, c = zs ? zs[i] - mz : 0; d[i] = Math.sqrt(a * a + b * b + c * c); }
  const r = Math.max(1e-9, Array.from(d).sort((p, q) => p - q)[Math.floor(.88 * (n - 1))]);
  const X = new Float32Array(n), Y = new Float32Array(n), Z = new Float32Array(n);
  for (let i = 0; i < n; i++) { X[i] = (xs[i] - mx) / r; Y[i] = (ys[i] - my) / r; Z[i] = zs ? (zs[i] - mz) / r : 0; }
  return { X, Y, Z, f: v => [(v[0] - mx) / r, (v[1] - my) / r, zs ? (v[2] - mz) / r : 0] };
}
function wobblyEllipse(ctx, x, y, rx, ry, seed) {
  let s = seed || 1; const rnd = () => ((s = (s * 9301 + 49297) % 233280) / 233280 - .5);
  ctx.beginPath();
  for (let k = 0; k <= 26; k++) {
    const a = -0.4 + k / 24 * Math.PI * 2.1, j = 1 + rnd() * .07;
    const px = x + Math.cos(a) * rx * j, py = y + Math.sin(a) * ry * j;
    k ? ctx.lineTo(px, py) : ctx.moveTo(px, py);
  }
  ctx.stroke();
}

window.Map3D = function (box, opts) {
  const reduce = window.matchMedia && matchMedia("(prefers-reduced-motion: reduce)").matches;
  const N3 = norm(opts.x3, opts.y3, opts.z3), N2 = norm(opts.x2, opts.y2, null);
  const n = opts.x3.length;

  let fit3 = .38;
  { const d = []; for (let i = 0; i < n; i++) d.push(Math.hypot(N3.X[i], N3.Y[i], N3.Z[i])); d.sort((p, q) => p - q);
    const R = d[Math.floor(.985 * (n - 1))] || 1, z = R * R / 3.2, k = 3.2 * Math.sqrt(Math.max(.01, R * R - z * z)) / (3.2 - z); fit3 = Math.max(.31, Math.min(.38, .47 / k)); }
  const S = { mode: opts.mode || "3d", yaw: -0.6, pitch: 0.35, zoom: 1, px: 0, py: 0, hov: -1, sel: -1, spin: !reduce, spinUntil: 0 };
  const cv = document.createElement("canvas");
  cv.tabIndex = 0; cv.setAttribute("role", "img");
  cv.setAttribute("aria-label", opts.ariaLabel || "Map of answers; drag to turn it");
  box.append(cv);
  const ctx = cv.getContext("2d");
  let W = 0, H = 0, dpr = 1, proj = new Float32Array(n * 4), order = new Uint32Array(n), raf = 0;
  for (let i = 0; i < n; i++) order[i] = i;

  function resize() { const r = cv.getBoundingClientRect(); dpr = Math.min(devicePixelRatio || 1, 2); W = r.width; H = r.height; if (!W) return; cv.width = Math.round(W * dpr); cv.height = Math.round(H * dpr); draw(); }
  const ro = new ResizeObserver(resize); ro.observe(box);

  function project(p) {
    const scale = Math.min(W, H) * (S.mode === "2d" ? 0.44 : fit3) * S.zoom;
    if (S.mode === "2d") return [W / 2 + S.px + p[0] * scale, H / 2 + S.py - p[1] * scale, 0, 1];
    const cy = Math.cos(S.yaw), sy = Math.sin(S.yaw), cp = Math.cos(S.pitch), sp = Math.sin(S.pitch);
    const x1 = p[0] * cy + p[2] * sy, z1 = -p[0] * sy + p[2] * cy;
    const y2 = p[1] * cp - z1 * sp, z2 = p[1] * sp + z1 * cp;
    const f = 3.2 / (3.2 - z2);
    return [W / 2 + S.px + x1 * f * scale, H / 2 + S.py - y2 * f * scale, z2, f];
  }
  function compute() {
    const A = S.mode === "2d" ? N2 : N3;
    for (let i = 0; i < n; i++) { const q = project([A.X[i], A.Y[i], A.Z[i]]); proj[i * 4] = q[0]; proj[i * 4 + 1] = q[1]; proj[i * 4 + 2] = q[2]; proj[i * 4 + 3] = q[3]; }
    if (S.mode === "3d") order.sort((a, b) => proj[a * 4 + 2] - proj[b * 4 + 2]);
  }
  function at(o) { const A = S.mode === "2d" ? N2 : N3; return project(S.mode === "2d" ? A.f([o.x2, o.y2]) : A.f([o.x3, o.y3, o.z3])); }

  function draw() {
    if (!W) return;
    compute();
    ctx.setTransform(dpr, 0, 0, dpr, 0, 0); ctx.clearRect(0, 0, W, H);
    const base = Math.max(2.3, Math.min(3.8, Math.min(W, H) / 175)) * (S.zoom > 2.5 ? 1.25 : 1);
    const any = opts.anyActive ? opts.anyActive() : false;

    const hg = !any && S.hov >= 0 && opts.group ? opts.group(S.hov) : null, lit = hg != null && hg >= 0 ? hg : null;
    for (let pass = 0; pass < 2; pass++) for (let k = 0; k < n; k++) {
      const i = order[k], act = opts.active(i);
      if ((pass === 0) === (act && any)) continue;
      const x = proj[i * 4], y = proj[i * 4 + 1], d = proj[i * 4 + 2], f = proj[i * 4 + 3];
      if (x < -8 || y < -8 || x > W + 8 || y > H + 8) continue;
      const depth = S.mode === "3d" ? Math.max(0, Math.min(1, (d + 1.2) / 2.4)) : .8;
      const dim = lit != null && opts.group(i) !== lit, strong = (act && any) || (lit != null && !dim);
      ctx.globalAlpha = !act ? .55 : dim ? .16 : strong ? .97 : .7 + .28 * depth;
      const c = act ? opts.color(i) : "#DEDEDE";
      ctx.fillStyle = c; ctx.beginPath(); ctx.arc(x, y, base * f * (strong ? 1.15 : 1), 0, 6.2832); ctx.fill();
      if (act && !dim) { ctx.lineWidth = .9; ctx.strokeStyle = "#ffffff"; ctx.stroke(); }
      if (act && !dim && opts.light && opts.light(c)) { ctx.lineWidth = .6; ctx.strokeStyle = opts.ink(c); ctx.stroke(); }
    }
    ctx.globalAlpha = 1;
    if (opts.labels) drawLabels(opts.labels(), lit);
    if (opts.marks) drawMarks(opts.marks());
    ring(S.sel, 2.4); ring(S.hov, 1.6);
    if (S.mode === "3d") gizmo();
  }
  function ring(i, w) {
    if (i < 0) return;
    const x = proj[i * 4], y = proj[i * 4 + 1];
    ctx.lineWidth = w + 2; ctx.strokeStyle = "#fff"; ctx.beginPath(); ctx.arc(x, y, 7, 0, 6.2832); ctx.stroke();
    ctx.lineWidth = w; ctx.strokeStyle = "#1a1a1a"; ctx.beginPath(); ctx.arc(x, y, 7, 0, 6.2832); ctx.stroke();
  }
  function drawLabels(list, lit) {
    const placed = [];
    ctx.textAlign = "center"; ctx.textBaseline = "middle"; ctx.lineJoin = "round";
    if (lit != null && list.some(o => o.id === lit)) list = list.filter(o => o.id === lit);
    list.map(o => Object.assign({ p: at(o) }, o)).sort((a, b) => b.p[2] - a.p[2]).forEach(o => {
      const fs = o.small ? 11.5 : 13.5;
      ctx.font = "600 " + fs + "px 'Atkinson Next', 'Segoe UI', sans-serif";
      const words = o.text.split(" "), lines = []; let cur = "";
      words.forEach(w => { const t = cur ? cur + " " + w : w; if (ctx.measureText(t).width > (o.small ? 130 : 170) && cur) { lines.push(cur); cur = w; } else cur = t; });
      lines.push(cur);
      const [x, y] = o.p, lh = fs * 1.12, wd = Math.max(...lines.map(l => ctx.measureText(l).width)), ht = lh * lines.length;
      const b = { x0: x - wd / 2 - 3, x1: x + wd / 2 + 3, y0: y - ht / 2 - 2, y1: y + ht / 2 + 2 };
      if (x < 0 || x > W || y < 0 || y > H) return;
      if (placed.some(p => b.x0 < p.x1 && b.x1 > p.x0 && b.y0 < p.y1 && b.y1 > p.y0)) return;
      placed.push(b);
      lines.forEach((l, k) => { const ly = y - ht / 2 + lh * (k + .5); ctx.lineWidth = 5; ctx.strokeStyle = "#ffffff"; ctx.strokeText(l, x, ly); ctx.fillStyle = o.color; ctx.fillText(l, x, ly); });
    });
  }
  function drawMarks(list) {
    list.forEach((o, k) => {
      const [x, y] = at(o); if (x < 0 || x > W || y < 0 || y > H) return;
      ctx.strokeStyle = "#c8102e"; ctx.lineWidth = 2; ctx.globalAlpha = .9;
      wobblyEllipse(ctx, x, y, (o.rx || 46) * S.zoom ** .5, (o.ry || 30) * S.zoom ** .5, 7 + k * 13);
      const tx = x + (o.dx || 60), ty = y + (o.dy || -46);
      ctx.beginPath(); ctx.moveTo(x + (o.dx > 0 ? 30 : -30), y + (o.dy > 0 ? 18 : -18)); ctx.quadraticCurveTo(tx - (o.dx > 0 ? 6 : -6), ty + (o.dy > 0 ? -14 : 14), tx, ty); ctx.stroke();
      ctx.globalAlpha = 1; ctx.font = "15px 'Atkinson Next', 'Segoe UI', sans-serif"; ctx.fillStyle = "#c8102e";
      ctx.textAlign = o.dx > 0 ? "left" : "right"; ctx.textBaseline = "middle";
      ctx.lineWidth = 4; ctx.strokeStyle = "rgba(255,255,255,.9)"; ctx.strokeText(o.text, tx + (o.dx > 0 ? 4 : -4), ty); ctx.fillText(o.text, tx + (o.dx > 0 ? 4 : -4), ty);
    });
  }
  function gizmo() {
    const ox = 34, oy = H - 30, L = 16, ax = [[1, 0, 0], [0, 1, 0], [0, 0, 1]];
    const cy = Math.cos(S.yaw), sy = Math.sin(S.yaw), cp = Math.cos(S.pitch), sp = Math.sin(S.pitch);
    ctx.lineWidth = 1.2; ctx.strokeStyle = "#8a8a8a";
    ax.forEach(p => { const x1 = p[0] * cy + p[2] * sy, z1 = -p[0] * sy + p[2] * cy, y2 = p[1] * cp - z1 * sp; ctx.beginPath(); ctx.moveTo(ox, oy); ctx.lineTo(ox + x1 * L, oy - y2 * L); ctx.stroke(); });
  }

  function pick(mx, my) {
    let best = -1, bd = 100, bz = -9;
    for (let i = 0; i < n; i++) {
      const dx = proj[i * 4] - mx, dy = proj[i * 4 + 1] - my, d = dx * dx + dy * dy;
      if (d < 100 && (d < bd - 12 || (d < bd + 12 && proj[i * 4 + 2] > bz))) { bd = d; best = i; bz = proj[i * 4 + 2]; }
    }
    return best;
  }

  let paused = false, resumeT = 0, onScreen = true;
  const wantSpin = () => S.mode === "3d" && !reduce && !paused && onScreen && !document.hidden;
  function loop() { raf = 0; if (!wantSpin()) return; S.yaw += .0016; draw(); raf = requestAnimationFrame(loop); }
  function kick() { if (!raf && wantSpin()) raf = requestAnimationFrame(loop); }
  function stopSpin() { paused = true; clearTimeout(resumeT); if (raf) cancelAnimationFrame(raf); raf = 0; }
  function resumeLater(ms) { clearTimeout(resumeT); resumeT = setTimeout(() => { paused = false; kick(); }, ms || 3000); }
  if ("IntersectionObserver" in window) new IntersectionObserver(es => { onScreen = es[0].isIntersecting; kick(); }).observe(cv);
  document.addEventListener("visibilitychange", kick);
  cv.addEventListener("pointerenter", e => { if (e.pointerType !== "touch") stopSpin(); });

  let drag = null, moved = false;
  cv.addEventListener("pointerdown", e => { stopSpin(); try { cv.setPointerCapture(e.pointerId); } catch (_) {} drag = { x: e.clientX, y: e.clientY, yaw: S.yaw, pitch: S.pitch, px: S.px, py: S.py, pan: e.shiftKey || S.mode === "2d" }; moved = false; });
  cv.addEventListener("pointermove", e => {
    const r = cv.getBoundingClientRect(), mx = e.clientX - r.left, my = e.clientY - r.top;
    if (drag) {
      const dx = e.clientX - drag.x, dy = e.clientY - drag.y;
      if (Math.abs(dx) + Math.abs(dy) > 4) moved = true;
      if (moved) {
        if (drag.pan) { S.px = drag.px + dx; S.py = drag.py + dy; }
        else { S.yaw = drag.yaw + dx * .008; S.pitch = Math.max(-1.45, Math.min(1.45, drag.pitch + dy * .008)); }
        if (opts.onHover) opts.onHover(-1, e); draw(); return;
      }
    }
    const h = pick(mx, my);
    if (h !== S.hov) { S.hov = h; draw(); }
    if (opts.onHover) opts.onHover(h, e);
  });
  cv.addEventListener("pointerup", e => { if (e.pointerType === "touch") resumeLater(3000); if (drag && !moved) { const r = cv.getBoundingClientRect(), h = pick(e.clientX - r.left, e.clientY - r.top); S.sel = h; draw(); if (opts.onClick) opts.onClick(h); } drag = null; });
  cv.addEventListener("pointerleave", () => { resumeLater(3000); if (S.hov !== -1) { S.hov = -1; draw(); } if (opts.onHover) opts.onHover(-1); });
  cv.addEventListener("wheel", e => { e.preventDefault(); stopSpin(); zoomBy(e.deltaY < 0 ? 1.15 : 1 / 1.15); }, { passive: false });
  cv.addEventListener("keydown", e => {
    const k = e.key; stopSpin();
    if (k === "+" || k === "=") zoomBy(1.3); else if (k === "-") zoomBy(1 / 1.3);
    else if (k === "ArrowLeft") { S.mode === "3d" ? S.yaw -= .15 : S.px += 40; draw(); } else if (k === "ArrowRight") { S.mode === "3d" ? S.yaw += .15 : S.px -= 40; draw(); }
    else if (k === "ArrowUp") { S.mode === "3d" ? S.pitch = Math.max(-1.45, S.pitch - .15) : S.py += 40; draw(); } else if (k === "ArrowDown") { S.mode === "3d" ? S.pitch = Math.min(1.45, S.pitch + .15) : S.py -= 40; draw(); }
    else return; e.preventDefault(); resumeLater(5000);
  });
  function zoomBy(f) { S.zoom = Math.max(.6, Math.min(10, S.zoom * f)); draw(); }

  const tools = document.createElement("div"); tools.className = "tools";
  [["+", "Zoom in", () => zoomBy(1.3)], ["−", "Zoom out", () => zoomBy(1 / 1.3)], ["↺", "Reset the view", () => { stopSpin(); S.zoom = 1; S.px = 0; S.py = 0; S.yaw = -.6; S.pitch = .35; draw(); resumeLater(3000); }]].forEach(([t, l, f]) => {
    const b = document.createElement("button"); b.type = "button"; b.textContent = t; b.setAttribute("aria-label", l); b.title = l; b.onclick = f; tools.append(b);
  });
  box.append(tools);

  kick();
  return {
    draw, canvas: cv,
    setMode(m) { S.mode = m; S.zoom = 1; S.px = 0; S.py = 0; draw(); if (m === "3d") { paused = false; kick(); } },
    mode: () => S.mode,
    select(i) { S.sel = i == null ? -1 : i; draw(); },
    destroy() { stopSpin(); clearTimeout(resumeT); ro.disconnect(); cv.remove(); tools.remove(); }
  };
};
})();
