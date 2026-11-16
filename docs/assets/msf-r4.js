(function () {
"use strict";
const $ = (s, r) => (r || document).querySelector(s);
const el = (tag, attrs, kids) => {
  const e = document.createElement(tag);
  for (const k in attrs || {}) { const v = attrs[k]; if (v == null || v === false) continue; if (k === "text") e.textContent = v; else if (k.startsWith("on")) e.addEventListener(k.slice(2), v); else e.setAttribute(k, v === true ? (k.startsWith("aria-") ? "true" : "") : v); }
  (kids || []).forEach(c => e.append(c)); return e;
};
const NS = "http://www.w3.org/2000/svg";
const sv = (tag, a) => { const e = document.createElementNS(NS, tag); for (const k in a || {}) e.setAttribute(k, a[k]); return e; };
const tx = (x, y, s, a) => { const e = sv("text", Object.assign({ x, y }, a || {})); e.textContent = s; return e; };
const pc = v => (v * 100).toFixed(0) + "%";
const fmt = n => n.toLocaleString("en-US");
const cap = s => s.charAt(0).toUpperCase() + s.slice(1);
const qtext = q => q < .001 ? "q < 0.001" : "q = " + q.toFixed(3);
const P = window.PAL;
const INK = "#161616", INK2 = "#4A4A4A", INK3 = "#6B6B6B", LINE = "#EBEBEB", ACC = "#161616", ACCBG = "#E7F3F1", NAVY = "#4A4A4A", FEW = "#B45309";

const PARENT = [0, 0, 1, 1, 2, 4, 5, 6, 7, 2, 3, 8, 1, 3, 3];

const load = (w, url) => window[w] ? Promise.resolve(window[w]) : fetch(url).then(r => { if (!r.ok) throw new Error(url + " " + r.status); return r.json(); });
load("MSF_R4", "data/msf/msf-r4.json").then(init).catch(e => {
  document.querySelectorAll(".needs-r4").forEach(n => n.replaceChildren(el("p", { class: "loading", role: "alert", text: "The data file could not be loaded (" + e.message + ")." })));
});

function sections() {
  const secs = [...document.querySelectorAll("section.panel")], links = [...document.querySelectorAll("#secbar a")], bar = $("#secbar");
  if (!secs.length || !bar) return;
  const show = (id, scroll) => {
    secs.forEach(s => { s.hidden = s.id !== id; });
    links.forEach(a => a.setAttribute("aria-current", a.getAttribute("href") === "#" + id ? "true" : "false"));
    window.dispatchEvent(new Event("resize"));
    if (scroll) { const top = bar.getBoundingClientRect().top + scrollY - 2; if (scrollY > top + 4 || bar.getBoundingClientRect().top > innerHeight * .45) scrollTo({ top, behavior: "smooth" }); }
  };
  const route = scroll => {
    const h = decodeURIComponent(location.hash.slice(1));
    if (!h) { show(secs[0].id, false); return; }
    if (/=/.test(h)) { show("map", scroll); return; }
    const el_ = document.getElementById(h); if (!el_) return;
    const sec = el_.closest("section.panel");
    if (sec) { show(sec.id, scroll && el_ === sec); if (el_ !== sec) { const d = el_.closest("details"); if (d) d.open = true; el_.scrollIntoView({ block: d ? "start" : "center" }); } }
    else { const d = el_.closest("details"); if (d) d.open = true; el_.scrollIntoView({ block: "center" }); }
  };
  window.addEventListener("hashchange", () => route(true));
  route(false);
}
sections();

let R, TH = {}, COL = { main: [], sub: [] };
function init(r) {
  R = r; TH.main = R.themes.main; TH.sub = R.themes.sub;
  TH.main.forEach(t => { COL.main[t.id] = P.CAT[t.id]; });
  const sib = {}; TH.sub.forEach(t => { const p = PARENT[t.id]; sib[p] = (sib[p] || 0) + 1; COL.sub[t.id] = P.child(P.CAT[p], sib[p] - 1); });
  const run = [renderResults, renderGlance, renderTalk, renderCountry, renderYears, renderTopics, renderOverlap, renderModel, sideNav];
  run.forEach(f => { try { f(); } catch (err) { console.error(f.name, err); } });
}
const nm = (lv, j) => cap(TH[lv][j].name);
const LVN = { main: "9 themes", sub: "15 sub-themes" };
function levelSeg(state, redraw) {
  return el("div", { class: "seg", role: "group", "aria-label": "Theme level" }, ["main", "sub"].map(v => el("button", { type: "button", "aria-pressed": state.lv === v, text: LVN[v], onclick: () => { state.lv = v; redraw(); } })));
}

function wrapLabel(x, y, text, room, attrs) {
  const t = sv("text", Object.assign({ x, y: y + 4.5 }, attrs));
  if (text.length <= room) { t.textContent = text; return t; }
  const w = text.split(" "); let a = "", k = 0;
  while (k < w.length && (a + " " + w[k]).trim().length <= Math.max(room, Math.ceil(text.length / 2))) { a = (a + " " + w[k]).trim(); k++; }
  let b = w.slice(k).join(" "); if (b.length > room) b = b.slice(0, room - 1) + "…";
  const fs = +(attrs["font-size"] || 13), s1 = sv("tspan", { x, dy: -fs * .55 }), s2 = sv("tspan", { x, dy: fs * 1.15 });
  s1.textContent = a; s2.textContent = b; t.append(s1, s2); return t;
}

function showTip(e, title, lines) {
  const tp = $("#tip"); if (!tp) return;
  tp.replaceChildren(el("b", { text: title }), ...lines.map(s => el("span", { text: s })));
  const x = e.clientX != null ? e.clientX : e.target.getBoundingClientRect().left, y = e.clientY != null ? e.clientY : e.target.getBoundingClientRect().bottom;
  tp.style.left = Math.max(8, Math.min(innerWidth - 356, x + 14)) + "px"; tp.style.top = (y + 16) + "px"; tp.style.opacity = 1;
}
const hideTip = () => { const tp = $("#tip"); if (tp) tp.style.opacity = 0; };
function hoverable(g, title, lines, onClick) {
  g.setAttribute("tabindex", 0); g.setAttribute("class", "hit"); g.setAttribute("aria-label", title + ". " + lines.join(". "));
  g.addEventListener("mousemove", e => showTip(e, title, lines)); g.addEventListener("mouseleave", hideTip);
  g.addEventListener("focus", e => showTip(e, title, lines)); g.addEventListener("blur", hideTip);
  if (onClick) { g.addEventListener("click", onClick); g.addEventListener("keydown", e => { if (e.key === "Enter" || e.key === " ") { e.preventDefault(); onClick(); } }); }
  return g;
}
function showOnMap(lv, id) {
  location.hash = (lv === "sub" ? "level=sub&" : "") + "theme=" + id;
  const f = $("#map"); if (f) f.scrollIntoView({ behavior: "smooth", block: "start" });
}

function barsSVG(lv, o) {
  o = Object.assign({ W: 860, L: 300, rh: lv === "main" ? 34 : 25, bh: lv === "main" ? 18 : 13, fs: lv === "main" ? 14 : 12.5, xmax: lv === "main" ? .7 : .5, click: true, ci: true, axis: true, rows: null }, o || {});
  const rows = o.rows || TH[lv].slice().sort((a, b) => b.pct - a.pct);
  const pw = o.W - o.L - 92, sx = v => o.L + pw * Math.min(v, o.xmax) / o.xmax, T0 = o.axis ? 22 : 4, H = T0 + rows.length * o.rh + 4;
  const svg = sv("svg", { viewBox: "0 0 " + o.W + " " + H, role: "group", "aria-label": "Share of the 893 stories that raise each " + (lv === "main" ? "theme" : "sub-theme") + ", with 95% ranges" });
  if (o.axis) { const st = o.xmax > .55 ? .2 : .1; for (let t = 0; t <= o.xmax + 1e-9; t += st) svg.append(sv("line", { x1: sx(t), x2: sx(t), y1: 16, y2: H - 2, stroke: LINE }), tx(sx(t), 11, pc(t), { "font-size": 11.5, fill: INK3, "text-anchor": "middle", class: "n" })); }
  rows.forEach((t, i) => {
    const y = T0 + i * o.rh, cy = y + o.bh / 2, col = COL[lv][t.id], g = sv("g", {});
    g.append(sv("rect", { class: "bg", x: 0, y: y - (o.rh - o.bh) / 2, width: o.W, height: o.rh, fill: "transparent" }));
    g.append(sv("circle", { cx: 7, cy, r: lv === "main" ? 5.5 : 4.5, fill: col }));
    g.append(wrapLabel(19, cy - 4.5 + o.fs * .3, cap(t.name), Math.floor((o.L - 26) / (o.fs * .52)), { "font-size": o.fs, fill: INK }));
    g.append(sv("rect", { x: sx(0), y, width: Math.max(1, sx(t.pct) - sx(0)), height: o.bh, fill: col, rx: 2 }));
    if (o.ci) g.append(sv("line", { x1: sx(t.lo), x2: sx(t.hi), y1: cy, y2: cy, stroke: INK, "stroke-width": 1.3 }), sv("line", { x1: sx(t.lo), x2: sx(t.lo), y1: cy - 5, y2: cy + 5, stroke: INK }), sv("line", { x1: sx(t.hi), x2: sx(t.hi), y1: cy - 5, y2: cy + 5, stroke: INK }));
    if (t.passage_pct != null && o.ci) { const px = sx(t.passage_pct), d = 5; g.append(sv("path", { d: "M" + px + "," + (cy - d) + " L" + (px + d) + "," + cy + " L" + px + "," + (cy + d) + " L" + (px - d) + "," + cy + " Z", fill: "#fff", stroke: INK, "stroke-width": 1.4 })); }
    const vt = tx(Math.max(sx(t.hi), sx(t.pct)) + 8, y + o.bh * .76, "", { "font-size": o.fs - .5, fill: INK, class: "n" });
    const b = sv("tspan", { "font-weight": 700 }); b.textContent = pc(t.pct); vt.append(b);
    if (o.ci) { const s = sv("tspan", { fill: INK3, "font-size": o.fs - 2.5 }); s.textContent = "  " + (t.lo * 100).toFixed(0) + "–" + (t.hi * 100).toFixed(0); vt.append(s); }
    g.append(vt);
    hoverable(g, cap(t.name), [fmt(t.stories) + " of " + fmt(R.meta.stories) + " stories (" + pc(t.pct) + "), 95% range " + pc(t.lo) + " to " + pc(t.hi), "Share of all " + fmt(R.meta.passages) + " passages: " + pc(t.passage_pct)].concat(o.click ? ["Click to light it up on the map"] : []),
      o.click ? () => showOnMap(lv, t.id) : null);
    svg.append(g);
  });
  return svg;
}

function countSVG(rows, o) {
  o = Object.assign({ W: 440, L: 92, rh: 25, bh: 15, fs: 13, col: NAVY }, o || {});
  const max = Math.max(...rows.map(r => r.n)), pw = o.W - o.L - 44, H = rows.length * o.rh + 4;
  const svg = sv("svg", { viewBox: "0 0 " + o.W + " " + H, role: "img", "aria-label": rows.map(r => r.name + " " + r.n).join(", ") });
  svg.style.maxWidth = Math.round(o.W * 1.2) + "px";
  rows.forEach((r, i) => {
    const y = 2 + i * o.rh, few = r.few;
    svg.append(tx(o.L - 8, y + o.bh * .8, r.name, { "font-size": o.fs, fill: INK, "text-anchor": "end" }),
      sv("rect", { x: o.L, y, width: Math.max(1, pw * r.n / max), height: o.bh, fill: o.col, rx: 2, opacity: few ? .55 : 1 }),
      tx(o.L + pw * r.n / max + 6, y + o.bh * .8, fmt(r.n) + (few ? " · few" : ""), { "font-size": o.fs - 1, fill: few ? FEW : INK2, class: "n", "font-weight": 600 }));
  });
  return svg;
}
const TS = { lv: "main" };
function renderTalk() {
  const box = $("#talk-fig"); if (!box) return;
  const draw = () => box.replaceChildren(el("div", { class: "ctlrow" }, [levelSeg(TS, draw)]),
    el("p", { class: "legend4" }, [el("span", {}, [el("i", { style: "background:" + INK2 }), "share of stories, black line = 95% range"]), el("span", {}, ["◇ share of passages"])]),
    el("div", { class: "figbox" }, [barsSVG(TS.lv, { W: 660, L: 270 })]));
  draw();
  const side = $("#talk-side"); if (!side) return;
  const g = R.groups.country.main, few = n => n < 30;
  side.replaceChildren(el("h3", { class: "subhead", style: "margin-top:0", text: "Who gets reported?" }),
    el("p", { class: "fnote", style: "margin:0 0 6px", text: "Stories per country. Palestine has 14 times more stories than Yemen, so a share for Yemen rests on 23 stories." }),
    el("div", { class: "figbox" }, [countSVG(g.groups.map((c, i) => ({ name: c, n: g.stories[i], few: few(g.stories[i]) })))]),
    el("p", { class: "fnote", style: "margin:10px 0 6px", text: "Stories per year" }),
    el("div", { class: "figbox" }, [countSVG(R.meta.years.map(y => ({ name: String(y), n: R.stories_per_year[String(y)] })), { col: "#9A9A9A" })]),
    el("p", { class: "fnote", text: fmt(R.meta.stories - R.meta.single_country_stories) + " stories also carry other country tags; each story counts once, under the country it was collected for." }));
}

function circleMatrix(cfg) {

  const cols = cfg.cols.length + (cfg.firstCol ? 1 : 0), L = cfg.L || 300, cw = Math.max(cfg.cwMin || 66, Math.min(108, ((cfg.W || 1180) - L) / cols)), rh = cfg.rh || 48, T0 = 62;
  const nr = cfg.rows.length + (cfg.lastRow ? 1 : 0), W = L + cols * cw + 10, H = T0 + nr * rh + 8;
  const svg = sv("svg", { viewBox: "0 0 " + W + " " + H, role: "group", "aria-label": cfg.aria });
  svg.style.maxWidth = Math.round(W * 1.15) + "px";
  const cx = c => L + (c + (cfg.firstCol ? 1 : 0)) * cw + cw / 2;
  const head = (x, h, s, few) => {
    const words = h.split(/(?<=\/)|\s+/), two = h.length > 11 && words.length > 1, cut = Math.ceil(words.length / 2), jn = a => a.map(w => w.endsWith("/") ? w : w + " ").join("").trim(), h1 = two ? jn(words.slice(0, cut)) : h, h2 = two ? jn(words.slice(cut)) : "";
    const hf = Math.max(10.5, Math.min(12.5, (cw - 6) * 1.8 / Math.max(h1.length, h2.length)));
    svg.append(tx(x, two ? 15 : 24, h1, { "text-anchor": "middle", "font-size": hf, "font-weight": 700, fill: INK }));
    if (two) svg.append(tx(x, 29, h2, { "text-anchor": "middle", "font-size": hf, "font-weight": 700, fill: INK }));
    if (s) svg.append(tx(x, two ? 45 : 41, s + (few ? " · few" : ""), { "text-anchor": "middle", "font-size": 11, fill: few ? FEW : INK3, class: "n" }));
  };
  if (cfg.firstCol) { head(L + cw / 2, cfg.firstCol.h, cfg.firstCol.s); svg.append(sv("line", { x1: L + cw, x2: L + cw, y1: 8, y2: H - 8, stroke: LINE })); }
  cfg.cols.forEach((c, k) => head(cx(k), c.h, c.s, c.few));
  const Rmax = rh / 2 - 3;
  const drawCell = (x, y0, d, baseCol) => {
    const y = y0 + rh / 2, g = sv("g", {}), rr = Math.max(1.8, Math.sqrt(Math.max(0, d.v)) * Rmax), fill = d.first ? "#E4E4E4" : d.strong ? baseCol : (d.ring && d.res < 0) ? "#ffffff" : "#D6D6D6";
    g.append(sv("rect", { class: "bg", x: x - cw / 2 + 2, y: y0 + 2, width: cw - 4, height: rh - 4, fill: "transparent", rx: 6 }));
    if (d.v > 0) g.append(sv("circle", Object.assign({ cx: x, cy: y, r: rr, fill, stroke: d.ring && d.res < 0 ? "#8A8A8A" : "none", "stroke-width": 1.4 }, d.ring && d.res < 0 ? { "stroke-dasharray": "3 2.5" } : {})));
    const inside = rr > 15.5, outer = rr;
    g.append(tx(inside ? x : x + outer + 3, y + 4, d.v > 0 ? pc(d.v) : "0", { "text-anchor": inside ? "middle" : "start", "font-size": 11.5, "font-weight": 600, fill: inside ? P.onFill(fill) : d.v > 0 ? INK : INK3, class: "n" }));
    hoverable(g, d.title, d.lines);
    svg.append(g);
  };
  cfg.rows.forEach((r, i) => {
    const y0 = T0 + i * rh, y = y0 + rh / 2;
    svg.append(sv("line", { x1: 0, x2: W, y1: y0, y2: y0, stroke: "#F0EFED" }));
    if (r.color) svg.append(sv("circle", { cx: 10, cy: r.sub ? y - 6 : y, r: 5, fill: r.color }));
    const lx = r.color ? 22 : 4, t = r.label.length > 44 ? r.label.slice(0, 43) + "…" : r.label;
    svg.append(tx(lx, r.sub ? y - 2 : y + 4.5, t, { "font-size": cfg.fs || 14, "font-weight": r.bold ? 700 : 400, fill: INK }));
    if (r.sub) svg.append(tx(lx, y + 13, r.sub, { "font-size": 11, fill: r.subColor || INK3, "font-weight": r.subColor ? 700 : 400 }));
    if (cfg.firstCol) drawCell(L + cw / 2, y0, Object.assign({ first: true }, cfg.cell(i, -1)), r.cellColor || r.color || NAVY);
    cfg.cols.forEach((c, k) => drawCell(cx(k), y0, cfg.cell(i, k), r.cellColor || r.color || NAVY));
  });
  if (cfg.lastRow) {
    const y0 = T0 + cfg.rows.length * rh, y = y0 + rh / 2;
    svg.append(sv("line", { x1: 0, x2: W, y1: y0, y2: y0, stroke: LINE }));
    svg.append(tx(4, y - 2, cfg.lastRow.label, { "font-size": 13, "font-weight": 700, fill: INK }), tx(4, y + 13, cfg.lastRow.sub || "", { "font-size": 11, fill: INK3 }));
    cfg.cols.forEach((c, k) => drawCell(cx(k), y0, Object.assign({ first: true }, cfg.lastRow.cell(k)), "#736C66"));
  }
  return svg;
}

function ppForest(rows, o) {

  o = Object.assign({ W: 900, L: 300, rh: 32, fs: 13.5, unit: " points", head: "", min: 10 }, o || {});
  const ext = Math.max(o.min, ...rows.map(r => Math.max(Math.abs(r.lo), Math.abs(r.hi)))), Rg = Math.min(o.max || 50, Math.ceil(ext / 10) * 10);
  const T0 = o.head ? 26 : 8, H = T0 + rows.length * o.rh + 20, x0 = o.L, pw = o.W - o.L - 10, sx = v => x0 + pw * (Math.max(-Rg, Math.min(Rg, v)) + Rg) / (2 * Rg);
  const svg = sv("svg", { viewBox: "0 0 " + o.W + " " + H, role: "group", "aria-label": (o.head || "Differences") + ", with 95% ranges" });
  svg.style.maxWidth = Math.round(o.W * 1.12) + "px";
  if (o.head) svg.append(tx(x0 + pw / 2, 14, o.head, { "text-anchor": "middle", "font-size": 13, "font-weight": 700, fill: INK }));
  svg.append(sv("rect", { x: x0, y: T0 - 4, width: pw, height: rows.length * o.rh + 8, fill: "none", rx: 6 }));
  [-Rg, -Rg / 2, 0, Rg / 2, Rg].forEach(v => svg.append(sv("line", { x1: sx(v), x2: sx(v), y1: T0 - 4, y2: T0 + rows.length * o.rh + 4, stroke: v === 0 ? INK3 : "#ECEBE9", "stroke-width": v === 0 ? 1.2 : 1 })));
  [-Rg, -Rg / 2, 0, Rg / 2, Rg].forEach(v => svg.append(tx(sx(v) + (v === -Rg ? 2 : v === Rg ? -2 : 0), H - 3, (v > 0 ? "+" : v < 0 ? "−" : "") + Math.abs(v) + (v === 0 ? o.unit : ""), { "text-anchor": v === -Rg ? "start" : v === Rg ? "end" : "middle", "font-size": 10.5, fill: INK3, class: "n" })));
  rows.forEach((r, i) => {
    const y = T0 + i * o.rh + o.rh / 2, g = sv("g", {}), col = r.sig ? r.color : "#9A9A9A";
    g.append(sv("rect", { class: "bg", x: 0, y: y - o.rh / 2 + 1, width: o.W, height: o.rh - 2, fill: "transparent", rx: 4 }));
    g.append(sv("circle", { cx: 7, cy: y, r: 5, fill: r.color }));
    g.append(wrapLabel(19, y, r.label, Math.floor((o.L - 26) / (o.fs * .52)), { "font-size": o.fs, fill: INK, "font-weight": r.sig ? 700 : 400 }));
    g.append(sv("line", { x1: sx(r.lo), x2: sx(r.hi), y1: y, y2: y, stroke: col, "stroke-width": r.sig ? 3 : 2, opacity: r.sig ? 1 : .55, "stroke-linecap": "round" }));
    g.append(sv("circle", { cx: sx(r.v), cy: y, r: r.sig ? 6.5 : 5, fill: r.sig ? col : "#fff", stroke: col, "stroke-width": 2 }));
    let right = r.v >= 0; if (right && sx(r.hi) + 34 > x0 + pw) right = false; else if (!right && sx(r.lo) - 34 < x0) right = true;
    const f = Math.abs(r.v) < .05 ? "0" : (r.v > 0 ? "+" : "−") + Math.abs(r.v).toFixed(Math.abs(r.v) < 10 ? 1 : 0);
    g.append(tx(right ? sx(r.hi) + 6 : sx(r.lo) - 6, y + 4, f, { "text-anchor": right ? "start" : "end", "font-size": 11.5, "font-weight": r.sig ? 700 : 400, fill: r.sig ? INK : INK2, class: "n" }));
    if (r.hi > Rg) g.append(sv("path", { d: "M" + (x0 + pw - 7) + "," + (y - 4) + " L" + (x0 + pw - 1) + "," + y + " L" + (x0 + pw - 7) + "," + (y + 4) + " Z", fill: col }));
    if (r.lo < -Rg) g.append(sv("path", { d: "M" + (x0 + 7) + "," + (y - 4) + " L" + (x0 + 1) + "," + y + " L" + (x0 + 7) + "," + (y + 4) + " Z", fill: col }));
    hoverable(g, r.title || r.label, r.lines.concat([r.sig ? "Holds: the range excludes 0 and the test holds after correction" : "Does not hold after correction"]));
    svg.append(g);
  });
  return svg;
}

const CS = { lv: "main", single: false, k: 1 };
function renderCountry() {
  const box = $("#country-fig"); if (!box) return;
  const tb = R.groups[CS.single ? "country_single" : "country"][CS.lv], lv = CS.lv;
  const order = tb.themes.map((_, j) => j).sort((a, b) => tb.all[b] - tb.all[a]);
  const nTot = tb.stories.reduce((a, b) => a + b, 0), held = tb.q.filter(q => q < .05).length, allHold = held === tb.q.length;
  const svg = circleMatrix({
    aria: "Share of each country's stories that raise each theme", L: 310, rh: lv === "main" ? 50 : 40, fs: lv === "main" ? 14 : 12.5,
    firstCol: { h: "All", s: fmt(R.meta.stories) + " stories" }, cols: tb.groups.map((g, c) => ({ h: g, s: tb.stories[c] + " stories", few: tb.stories[c] < 30 })),

    rows: order.map(j => ({ label: nm(lv, j), color: COL[lv][TH[lv][j].id], bold: !allHold && tb.q[j] < .05, sub: allHold ? "" : tb.q[j] < .05 ? "differs between countries · " + qtext(tb.q[j]) : "no clear difference", subColor: !allHold && tb.q[j] < .05 ? ACC : null })),
    cell: (i, c) => {
      const j = order[i];
      if (c < 0) return { v: tb.all[j], title: "All · " + nm(lv, j), lines: [pc(tb.all[j]) + " of all stories in this view"] };
      const ring = tb.q[j] < .05 && tb.cell_q[c][j] < .05, res = tb.resid[c][j];
      return { v: tb.share[c][j], ring, res, strong: ring && res > 0, title: tb.groups[c] + " · " + nm(lv, j),
        lines: [Math.round(tb.share[c][j] * tb.stories[c]) + " of " + tb.stories[c] + " stories (" + pc(tb.share[c][j]) + "), 95% range " + pc(tb.lo[c][j]) + " to " + pc(tb.hi[c][j]), "All countries together: " + pc(tb.all[j])].concat(ring ? [res > 0 ? "More than expected, and it holds after correction" : "Less than expected, and it holds after correction"] : []) };
    }
  });
  const ctl = [levelSeg(CS, renderCountry), el("div", { class: "seg", role: "group", "aria-label": "Which stories" }, [[false, "All stories"], [true, "One-country stories"]].map(([v, t]) => el("button", { type: "button", "aria-pressed": CS.single === v, text: t, onclick: () => { CS.single = v; renderCountry(); } })))];
  const lost = CS.single ? R.groups.country[lv].themes.filter((n, j) => R.groups.country[lv].q[j] < .05 && tb.q[j] >= .05).map(cap) : [];
  box.replaceChildren(el("div", { class: "ctlrow" }, ctl), el("div", { class: "figbox min900" }, [svg]),
    el("p", { class: "fnote", text: "Circle = share of the country's stories that raise the theme. Colour = more than expected for this country, and it holds after correction; dashed outline = less than expected; grey = no clear difference. " + held + " of " + tb.themes.length + " differ between countries" + (allHold ? (tb.q.every(q => q < .001) ? ", each with q < 0.001" : ", largest q = " + Math.max(...tb.q).toFixed(3)) : "") + " (" + nTot + " stories; 4,000 shuffles of the country between stories). q = p-value corrected for testing many themes at once; below 0.05 = the difference holds." + (CS.single ? " One-country stories only (" + fmt(R.meta.single_country_stories) + "): " + (lost.length ? lost.join(", ") + " no longer differs." : "nothing changes.") : "") }));
  renderContrast();
}
function renderContrast() {
  const box = $("#contrast-fig"); if (!box) return;
  const lv = CS.lv, c = R.contrasts[lv][CS.k], who = c.name.split(" vs ")[0];
  const order = TH[lv].map((_, j) => j).sort((a, b) => TH[lv][b].pct - TH[lv][a].pct);
  const rows = order.map(j => ({ label: nm(lv, j), color: COL[lv][TH[lv][j].id], v: c.pp[j], lo: c.lo[j], hi: c.hi[j], sig: c.sig[j], title: who + " · " + nm(lv, j),
    lines: [(c.pp[j] > 0 ? "+" : "") + c.pp[j].toFixed(1) + " percentage points (95% range " + c.lo[j].toFixed(1) + " to " + c.hi[j].toFixed(1) + ")", who + ": " + c.a_pct[j].toFixed(0) + "% of " + c.a_stories + " stories · all others: " + c.b_pct[j].toFixed(0) + "% of " + c.b_stories] }));
  const sel = el("select", { class: "fsel", "aria-label": "Country", onchange: e => { CS.k = +e.target.value; renderContrast(); } }, R.contrasts[lv].map((x, k) => { const o = el("option", { value: k, text: x.name.split(" vs ")[0] }); if (k === CS.k) o.selected = true; return o; }));
  const pw = R.power.filter(p => p.country === who).map(p => p.mde_points), nHold = c.sig.filter(Boolean).length;
  box.replaceChildren(el("div", { class: "ctlrow" }, [el("label", { class: "fnote", style: "margin:0;align-self:center" }, ["Country: "]), sel]),
    el("div", { class: "figbox" }, [ppForest(rows, { head: who + " (" + c.a_stories + " stories) minus all other countries (" + c.b_stories + ")", L: 310, rh: lv === "main" ? 32 : 26, fs: lv === "main" ? 13.5 : 12.5 })]),
    el("p", { class: "fnote", text: nHold + " of " + rows.length + " differences hold. " + (pw.length ? "With these story counts, this comparison can reliably see a gap of about " + Math.min(...pw).toFixed(0) + " to " + Math.max(...pw).toFixed(0) + " percentage points (80% power); a smaller gap may be missed. " : "") + "Ranges: 2,000 resamples of the stories." }));
}

const YS = { lv: "main" };
function yearPanel(tb, j, lv) {
  const W = 190, H = 132, L = 30, Rt = 26, T = 40, B = 22, ys = R.meta.years, hold = tb.q[j] < .05, col = hold ? COL[lv][TH[lv][j].id] : "#9A9A9A";
  const top = Math.max(.1, Math.ceil(Math.max(...tb.hi.map(h => h[j])) * 10) / 10), sy = v => T + (H - T - B) * (1 - v / top), sx = k => L + 18 + k * ((W - L - Rt - 36) / 2);
  const svg = sv("svg", { viewBox: "0 0 " + W + " " + H, role: "img", "aria-label": nm(lv, j) + ": " + ys.map((y, k) => y + " " + pc(tb.share[k][j])).join(", ") });
  svg.append(wrapLabel(4, 12, nm(lv, j), 25, { "font-size": 13, "font-weight": 700, fill: INK }));
  [0, top].forEach(v => svg.append(sv("line", { x1: L, x2: W - Rt, y1: sy(v), y2: sy(v), stroke: v ? "#F0EFED" : LINE }), tx(L - 4, sy(v) + 4, pc(v), { "font-size": 11, fill: INK3, "text-anchor": "end", class: "n" })));
  svg.append(sv("polyline", { points: ys.map((_, k) => sx(k) + "," + sy(tb.share[k][j])).join(" "), fill: "none", stroke: col, "stroke-width": 2, opacity: .8 }));
  ys.forEach((y, k) => {
    const g = sv("g", {}), x = sx(k), v = tb.share[k][j];
    g.append(sv("rect", { class: "bg", x: x - 26, y: T - 6, width: 52, height: H - T - B + 12, fill: "transparent", rx: 4 }));
    g.append(sv("line", { x1: x, x2: x, y1: sy(tb.lo[k][j]), y2: sy(tb.hi[k][j]), stroke: col, "stroke-width": 3, opacity: .5, "stroke-linecap": "round" }));
    g.append(sv("circle", { cx: x, cy: sy(v), r: 4.5, fill: hold ? col : "#fff", stroke: col, "stroke-width": 2 }));
    g.append(tx(x + 7, sy(v) - 5, pc(v), { "font-size": 11.5, "font-weight": 600, fill: INK, class: "n" }));
    g.append(tx(x, H - 7, String(y), { "font-size": 11.5, fill: INK3, "text-anchor": "middle", class: "n" }));
    hoverable(g, nm(lv, j) + " · " + y, [Math.round(v * tb.stories[k]) + " of " + tb.stories[k] + " stories (" + pc(v) + "), 95% range " + pc(tb.lo[k][j]) + " to " + pc(tb.hi[k][j])]);
    svg.append(g);
  });
  return el("div", { class: "smp" + (hold ? " hold" : "") }, [svg, el("p", { class: "fnote" + (hold ? " hold-t" : ""), style: "margin:0 0 4px;font-size:12px", text: hold ? "differs between years · " + qtext(tb.q[j]) : "no clear difference" })]);
}
function renderYears() {
  const box = $("#years-fig"), side = $("#trend-fig"); if (!box) return;
  const lv = YS.lv, tb = R.groups.year[lv], order = tb.themes.map((_, j) => j).sort((a, b) => tb.all[b] - tb.all[a]);
  box.replaceChildren(el("div", { class: "ctlrow" }, [levelSeg(YS, renderYears)]), el("div", { class: "smgrid yrs" }, order.map(j => yearPanel(tb, j, lv))),
    el("p", { class: "fnote", text: "Dot = share of that year's stories (" + R.meta.years.map(y => y + ": " + R.stories_per_year[String(y)]).join(", ") + "); line = 95% range. Each panel has its own scale. Colour = the theme differs between years after correction; grey = no clear difference." }));
  if (!side) return;
  const tr = R.trend[lv], rows = order.map(j => { const t = tr[j], sig = t.q < .05 && (t.lo > 0 || t.hi < 0); return { label: nm(lv, j), color: COL[lv][TH[lv][j].id], v: t.pp_per_year, lo: t.lo, hi: t.hi, sig, title: nm(lv, j),
    lines: [(t.pp_per_year > 0 ? "+" : "") + t.pp_per_year.toFixed(1) + " percentage points per year (95% range " + t.lo.toFixed(1) + " to " + t.hi.toFixed(1) + "), " + qtext(t.q), "Years taken as ordered steps: 2023 → 2024 → 2025"] }; });
  side.replaceChildren(el("h3", { class: "subhead", style: "margin-top:0", text: "Change per year" }),
    el("p", { class: "fnote", style: "margin:0 0 6px", text: "A straight line through the three years, in percentage points per year." }),
    el("div", { class: "figbox" }, [ppForest(rows, { L: 230, W: 560, rh: lv === "main" ? 34 : 27, fs: lv === "main" ? 12.5 : 11.5, unit: "", min: 5, max: 15 })]),
    el("p", { class: "fnote", text: "Test: 4,000 shuffles of the year between stories, Benjamini–Hochberg; ranges from 2,000 resamples." }));
}

function renderTopics() {
  const box = $("#topics-fig"); if (!box) return;
  const T = R.topics.table, order = R.topics.order, countries = R.meta.countries.filter(c => T.some(t => t.country === c));
  const get = (c, tp) => T.find(t => t.country === c && t.topic === tp);
  const nC = countries.map(c => (get(c, order[0]) || {}).stories || 0);
  const svg = circleMatrix({
    aria: "Share of each country's one-country stories that mention each medical topic", L: 200, rh: 40, fs: 13.5, cwMin: 80, W: 1000,
    cols: countries.map((c, k) => ({ h: c, s: nC[k] + " stories", few: nC[k] < 30 })),
    rows: order.map(tp => ({ label: tp, cellColor: "#4A4A4A" })),
    cell: (i, k) => { const d = get(countries[k], order[i]) || { pct: 0, mentioning: 0, stories: 0, lo: 0, hi: 0 }; const mx = Math.max(...countries.map(c => (get(c, order[i]) || { pct: 0 }).pct));
      return { v: d.pct / 100, strong: d.pct === mx && d.pct > 0, title: countries[k] + " · " + order[i], lines: [d.mentioning + " of " + d.stories + " stories mention it (" + d.pct.toFixed(0) + "%), 95% range " + d.lo.toFixed(0) + "% to " + d.hi.toFixed(0) + "%"] }; }
  });
  box.replaceChildren(el("div", { class: "figbox min900" }, [svg]),
    el("p", { class: "fnote", text: "Circle = share of the country's one-country stories whose text matches the topic's word list; the dark circle in each row is the country where the topic is most frequent. Numbers as reported by notebook 1." }));
}

const OS = { lv: "main" };
function renderOverlap() {
  const box = $("#overlap-fig"); if (!box) return;
  const lv = OS.lv, O = R.overlap[lv], order = O.themes.map((_, j) => j).sort((a, b) => TH[lv][b].pct - TH[lv][a].pct);
  const svg = circleMatrix({
    aria: "Share of each theme's stories that mention each medical topic", L: 300, rh: lv === "main" ? 44 : 36, fs: lv === "main" ? 13.5 : 12.5, cwMin: 62,
    cols: O.topics.map(t => ({ h: t })),
    rows: order.map(j => ({ label: nm(lv, j), color: COL[lv][TH[lv][j].id], sub: TH[lv][j].stories + " stories" })),
    cell: (i, k) => { const j = order[i], v = O.pct[j][k], l = O.lift[j][k];
      return { v, strong: l >= 2, ring: l >= 2, res: 1, title: nm(lv, j) + " · " + O.topics[k], lines: [pc(v) + " of the theme's " + TH[lv][j].stories + " stories mention it", "All stories: " + pc(O.topic_base[k]) + " → ×" + l.toFixed(1) + " the usual rate"].concat(l >= 2 ? ["At least twice the usual rate"] : []) }; },
    lastRow: { label: "All stories", sub: fmt(R.meta.stories) + " stories", cell: k => ({ v: O.topic_base[k], title: "All stories · " + O.topics[k], lines: [pc(O.topic_base[k]) + " of all stories mention it"] }) }
  });
  box.replaceChildren(el("div", { class: "ctlrow" }, [levelSeg(OS, renderOverlap)]), el("div", { class: "figbox min900" }, [svg]),
    el("p", { class: "fnote", text: "Circle = share of the theme's stories whose text matches the topic's word list. Colour = at least twice the rate in all stories; grey = less than twice. The word lists of notebook 1 were applied again to each story; they give the same count as notebook 1 in " + R.meta.lexicon_check.same_cells + " of " + R.meta.lexicon_check.cells + " country × topic cells (largest difference: " + R.meta.lexicon_check.largest_difference + " stories)." }));
}

const MS = { lv: "main", j: 0 };
const fmtOR = v => "×" + (v >= 10 ? v.toFixed(0) : v.toFixed(2));
function orForest(rows, o) {
  o = Object.assign({ W: 900, L: 250, rh: 30, fs: 13.5, maxR: 6 }, o || {});
  let ext = 1; rows.forEach(r => { if (r.fitted) ext = Math.max(ext, Math.abs(Math.log2(r.lo)), Math.abs(Math.log2(r.hi))); });
  const Rg = Math.min(o.maxR, Math.max(2, Math.ceil(ext))), T0 = 8, H = T0 + rows.length * o.rh + 20, x0 = o.L, pw = o.W - o.L - 10;
  const sx = v => x0 + pw * (Math.max(-Rg, Math.min(Rg, Math.log2(v))) + Rg) / (2 * Rg);
  const svg = sv("svg", { viewBox: "0 0 " + o.W + " " + H, role: "group", "aria-label": "Odds ratios with 95% ranges; 1 means no link" });
  svg.style.maxWidth = Math.round(o.W * 1.12) + "px";
  svg.append(sv("rect", { x: x0, y: T0 - 4, width: pw, height: rows.length * o.rh + 8, fill: "none", rx: 6 }));
  for (let e = -Rg; e <= Rg; e++) svg.append(sv("line", { x1: sx(2 ** e), x2: sx(2 ** e), y1: T0 - 4, y2: T0 + rows.length * o.rh + 4, stroke: e === 0 ? INK3 : "#ECEBE9", "stroke-width": e === 0 ? 1.2 : 1 }));
  [-Rg, -Math.round(Rg / 2), 0, Math.round(Rg / 2), Rg].forEach(e => svg.append(tx(sx(2 ** e) + (e === -Rg ? 2 : e === Rg ? -2 : 0), H - 3, e === 0 ? "×1 = no link" : (e < 0 ? "×1/" + 2 ** -e : "×" + 2 ** e), { "text-anchor": e === -Rg ? "start" : e === Rg ? "end" : "middle", "font-size": 10.5, fill: INK3, class: "n" })));
  rows.forEach((r, i) => {
    const y = T0 + i * o.rh + o.rh / 2, g = sv("g", {}), col = r.color;
    if (r.rule) svg.append(sv("line", { x1: 0, x2: o.W, y1: y - o.rh / 2, y2: y - o.rh / 2, stroke: LINE }));
    g.append(sv("rect", { class: "bg", x: 0, y: y - o.rh / 2 + 1, width: o.W, height: o.rh - 2, fill: "transparent", rx: 4 }));
    const sig = r.fitted && r.q < .05, colS = sig ? col : "#9A9A9A";
    g.append(tx(8, y + 4.5, r.label, { "font-size": o.fs, fill: INK, "font-weight": sig ? 700 : 400 }));
    if (!r.fitted) {
      g.append(tx(x0 + pw / 2, y + 4, r.note === "no story in this group raised it" ? "no story in this group raises it" : "could not be estimated", { "text-anchor": "middle", "font-size": 11.5, fill: INK3, "font-style": "italic" }));
      hoverable(g, r.label, [r.note || "could not be estimated"]); svg.append(g); return;
    }
    g.append(sv("line", { x1: sx(r.lo), x2: sx(r.hi), y1: y, y2: y, stroke: colS, "stroke-width": sig ? 3 : 2, opacity: sig ? 1 : .55, "stroke-linecap": "round" }));
    g.append(sv("circle", { cx: sx(r.OR), cy: y, r: sig ? 6.5 : 5, fill: sig ? colS : "#fff", stroke: colS, "stroke-width": 2 }));
    let right = r.OR >= 1; if (right && sx(r.hi) + 44 > x0 + pw) right = false; else if (!right && sx(r.lo) - 44 < x0) right = true;
    g.append(tx(right ? sx(r.hi) + 6 : sx(r.lo) - 6, y + 4, fmtOR(r.OR), { "text-anchor": right ? "start" : "end", "font-size": 11.5, "font-weight": sig ? 700 : 400, fill: sig ? INK : INK2, class: "n" }));
    if (Math.log2(r.hi) > Rg) g.append(sv("path", { d: "M" + (x0 + pw - 7) + "," + (y - 4) + " L" + (x0 + pw - 1) + "," + y + " L" + (x0 + pw - 7) + "," + (y + 4) + " Z", fill: col }));
    if (Math.log2(r.lo) < -Rg) g.append(sv("path", { d: "M" + (x0 + 7) + "," + (y - 4) + " L" + (x0 + 1) + "," + y + " L" + (x0 + 7) + "," + (y + 4) + " Z", fill: col }));
    hoverable(g, r.label, ["Odds ratio " + r.OR.toFixed(2) + " (95% range " + r.lo.toFixed(2) + " to " + r.hi.toFixed(2) + "), " + qtext(r.q), sig ? "Holds after correction" : "Does not hold after correction"]);
    svg.append(g);
  });
  return svg;
}
const FLAB = f => f === "story length (log passages)" ? "Longer story (per ×2.7 passages)" : f.replace(" vs ", " vs ");
function renderModel() {
  const box = $("#model-fig"); if (!box) return;
  const lv = MS.lv; if (MS.j >= TH[lv].length) MS.j = 0;
  const order = TH[lv].map((_, j) => j).sort((a, b) => TH[lv][b].pct - TH[lv][a].pct);
  const theme = TH[lv][MS.j].name, col = COL[lv][TH[lv][MS.j].id];
  const list = R.combined.filter(r => r.level === lv && r.theme === theme);
  const rows = list.map((r, i) => Object.assign({}, r, { label: FLAB(r.factor), color: col, rule: i > 0 && (r.factor.startsWith("2024") || r.factor.startsWith("story")) }));
  const sel = el("select", { class: "fsel", "aria-label": "Theme", onchange: e => { MS.j = +e.target.value; renderModel(); } }, order.map(j => { const o = el("option", { value: j, text: nm(lv, j) }); if (j === MS.j) o.selected = true; return o; }));
  const all = R.combined.filter(r => r.level === lv && r.fitted), hold = f => all.filter(r => r.q < .05 && f(r.factor)).length;
  const nC = hold(f => f.endsWith("vs Palestine")), nY = hold(f => /^20\d\d vs/.test(f)), nL = hold(f => f.startsWith("story"));
  box.replaceChildren(el("div", { class: "ctlrow" }, [levelSeg(MS, () => { MS.j = 0; renderModel(); }), sel]),
    el("div", { class: "figbox" }, [orForest(rows, { L: 230, rh: 30 })]),
    el("p", { class: "fnote", text: "Over all " + LVN[lv] + ": " + nC + " country results, " + nY + (nY === 1 ? " year result" : " year results") + " and " + nL + " story-length results hold after correction. Reference: Palestine (the most reported country) and 2023. One logistic model per theme, robust standard errors, Benjamini–Hochberg over the themes for each factor." }));
}

function renderResults() {
  const box = $("#results"); if (!box) return;
  const M = TH.main, top = M.slice().sort((a, b) => b.pct - a.pct), cm = R.groups.country.main, sm = R.groups.country_single.main;
  const jMal = 2, cs = c => cm.share[cm.groups.indexOf(c)][jMal];
  const lost = cm.themes.filter((n, j) => cm.q[j] < .05 && sm.q[j] >= .05).map(cap);
  const eq = R.trend.main[7], ar = R.trend.sub.find(t => t.theme === "aid restriction");
  const tp = (c, t) => R.topics.table.find(x => x.country === c && x.topic === t);
  const O = R.overlap.main, ov = [[8, "Sexual violence care"], [6, "Maternal/newborn"], [4, "Mental health"], [3, "Infectious disease"]].map(([j, t]) => O.pct[j][O.topics.indexOf(t)]);
  const pw = R.power.map(p => p.mde_points);
  const S = { facts: ["■", "fact", "a count, no test"], holds: ["●", "holds", "holds after correction"], part: ["◐", "partly", "holds alone, not in every check"], none: ["○", "no", "no difference that holds"] };
  const rows = [
    ["#talk", "What do the reports talk about?", cap(top[0].name) + " comes up in " + pc(top[0].pct) + " of stories, " + top[1].name + " in " + pc(top[1].pct) + "; the other seven themes in " + pc(top[8].pct) + " to " + pc(top[2].pct) + ".", pc(top[0].pct) + " and " + pc(top[1].pct) + " of stories", "facts"],
    ["#country", "Which country is reported for what?", "Every theme differs between countries. Children’s malnutrition: Sudan " + pc(cs("Sudan")) + ", Ukraine " + pc(cs("Ukraine")) + ".", "Yes, " + cm.q.filter(q => q < .05).length + " of 9 themes differ", "holds"],
    ["#country", "Does it hold for stories about one country only?", "Yes. With one-country stories only, " + sm.q.filter(q => q < .05).length + " of 9 themes still differ" + (lost.length ? "; " + lost.join(", ").toLowerCase() + " no longer does." : "."), "Yes, " + sm.q.filter(q => q < .05).length + " of 9 themes", "holds"],
    ["#years", "Did it change over time?", "Mostly stable. Earthquake stories fell after 2023; the sub-theme aid restriction rose every year.", "Little: " + R.trend.main.filter(t => t.q < .05).length + " of 9 themes moved", "holds"],
    ["#topics", "What does a fixed health checklist find?", "Infectious disease in " + tp("DR Congo", "Infectious disease").pct.toFixed(0) + "% of DR Congo stories, malnutrition in " + tp("Sudan", "Malnutrition").pct.toFixed(0) + "% of Sudan stories.", "DR Congo " + tp("DR Congo", "Infectious disease").pct.toFixed(0) + "%, Sudan " + tp("Sudan", "Malnutrition").pct.toFixed(0) + "%", "facts"],
    ["#overlap", "Do the two readings agree?", "Yes, where they should: most stories in a health theme also use the words of the matching topic.", "Yes, " + Math.round(Math.min(...ov) * 100) + " to " + Math.round(Math.max(...ov) * 100) + "% match", "facts"],
    ["#trust", "How small a gap can we see?", "About " + Math.min(...pw).toFixed(0) + " points for Palestine, up to " + Math.max(...pw).toFixed(0) + " for Yemen (23 stories).", Math.min(...pw).toFixed(0) + " to " + Math.max(...pw).toFixed(0) + " points", "facts"]
  ];
  box.replaceChildren(el("ul", { class: "qlist" }, rows.map(r => el("li", { title: r[2] }, [el("a", { href: r[0], text: r[1] }), el("b", { text: r[3] })]))),
    el("p", { class: "fnote", text: "Click a question to open its section; point at it for the short answer." }));
}
function renderGlance() {
  const box = $("#glance"); if (!box) return;
  const card = (href, q, h, ans, vis) => el("a", { class: "gcard", href }, [el("p", { class: "q", text: q }), el("h3", { text: h }), el("p", { class: "ans", text: ans }), vis, el("p", { class: "go", text: "Open this section →" })]);
  const top = TH.main.slice().sort((a, b) => b.pct - a.pct).slice(0, 5);
  const cm = R.groups.country.main, j = 2, crow = cm.groups.map((g, c) => ({ name: g, n: Math.round(cm.share[c][j] * 100) })).sort((a, b) => b.n - a.n);
  const ey = R.groups.year.main, eqs = R.meta.years.map((y, k) => ({ name: String(y), n: Math.round(ey.share[k][7] * 100) }));
  const O = R.overlap.main, pairs = [[8, "Sexual violence care"], [6, "Maternal/newborn"], [4, "Mental health"], [3, "Infectious disease"]].map(([jj, t]) => ({ name: t, n: Math.round(O.pct[jj][O.topics.indexOf(t)] * 100) }));
  const pctSVG = (rows, col, L) => { const s = countSVG(rows, { W: 300, L: L || 104, rh: 25, bh: 15, fs: 14, col }); s.querySelectorAll("text.n").forEach(t => { t.textContent = t.textContent.replace(/ · few$/, "") + "%"; }); return s; };
  box.replaceChildren(
    card("#talk", "Themes", "What do the reports talk about?", "Wounded patients come first: " + pc(TH.main[0].pct) + " of stories.", barsSVG("main", { rows: top, W: 310, L: 172, rh: 32, bh: 16, fs: 13.5, ci: false, click: false, axis: false })),
    card("#country", "Country", "Which country is reported for what?", "Children’s malnutrition, for example, by country:", pctSVG(crow, COL.main[2])),
    card("#years", "Years", "Did it change over time?", "Mostly stable. Earthquake stories fell after 2023:", pctSVG(eqs, COL.main[7])),
    card("#overlap", "Method check", "Do the two readings agree?", "Share of a theme’s stories that mention the matching health topic:", pctSVG(pairs, ACC, 158))
  );
}

function sideNav() {
  const links = [...document.querySelectorAll("nav.side a")]; if (!links.length || !("IntersectionObserver" in window)) return;
  const io = new IntersectionObserver(es => es.forEach(e => { if (e.isIntersecting) links.forEach(a => a.classList.toggle("on", a.getAttribute("href") === "#" + e.target.id)); }), { rootMargin: "-30% 0px -60% 0px" });
  links.forEach(a => { const s = document.querySelector(a.getAttribute("href")); if (s) io.observe(s); });
}
})();
