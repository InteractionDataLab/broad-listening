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
const P = window.PAL;
const NEG = "#C9653A", MID = "#C9C9C9", POS = "#3A78B5",    INK = "#161616", INK2 = "#4A4A4A", INK3 = "#6B6B6B", LINE = "#EBEBEB", ACC = "#161616", ACCBG = "none";

const load = (w, url) => window[w] ? Promise.resolve(window[w]) : fetch(url).then(r => { if (!r.ok) throw new Error(url + " " + r.status); return r.json(); });
Promise.all([load("IGEM_R4", "data/igem/igem-r4.json"), load("IGEM_DATA", "data/igem/igem-data.json"), load("IGEM_R5", "data/igem/igem-r5.json")]).then(([r, d, r5]) => { R5 = r5; init(r, d); }).catch(e => {
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

let R5, R, DD, COL = {}, SUBC = {}, MAINS, SUBS, QTXT = {}, NAMED = {}, TIER = {}, BYNAME = {}, SUMMARY = {};
function init(r, d) {
  R = r; DD = d;
  MAINS = R.themes.main; SUBS = R.themes.sub;
  MAINS.slice().sort((a, b) => b.answers - a.answers).forEach((m, k) => { COL[m.id] = P.CAT[k]; });
  MAINS.forEach(m => SUBS.filter(s => s.parent === m.id).sort((a, b) => b.answers - a.answers).forEach((s, k) => { SUBC[s.id] = P.child(COL[m.id], k); }));
  DD.questions.forEach(q => { QTXT[q.q] = q.text; });
  DD.themes.forEach(t => { NAMED[t.level + t.id] = t.named ? t.name : "Label withheld (sub-theme " + t.id + ")"; TIER[t.level + t.id] = t.tier; if (t.summary_kind === "summary") SUMMARY[t.level + t.id] = t.summary; });
  MAINS.forEach(t => { BYNAME["main|" + t.name] = t; }); SUBS.forEach(t => { BYNAME["sub|" + t.name] = t; });
  renderGlance(); renderTalk(); renderFlow(); renderTone(); renderCombined();
  MATRICES.forEach(m => m.type === "ladder" ? renderLadder(m) : m.type === "bars" ? renderBars(m) : renderMatrix(m));
  renderResults();
  renderFrance();
  sideNav();
}
const label = (lv, t) => lv === "main" ? t.name : NAMED["sub" + t.id];
const fullName = (lv, t) => lv === "main" ? t.name : NAMED["sub" + t.id];
const colOf = (lv, t) => lv === "main" ? COL[t.id] : SUBC[t.id];

function wrapLabel(x, y, text, room, attrs) {
  const t = sv("text", Object.assign({ x, y: y + 4.5 }, attrs));
  if (text.length <= room) { t.textContent = text; return t; }
  const w = text.split(" "); let a = "", k = 0;
  while (k < w.length && (a + " " + w[k]).trim().length <= Math.max(room, Math.ceil(text.length / 2))) { a = (a + " " + w[k]).trim(); k++; }
  let b = w.slice(k).join(" "); if (b.length > room) b = b.slice(0, room - 1) + "\u2026";
  const fs = +(attrs["font-size"] || 13), s1 = sv("tspan", { x, dy: -fs * .55 }), s2 = sv("tspan", { x, dy: fs * 1.15 });
  s1.textContent = a; s2.textContent = b; t.setAttribute("y", y + 4.5); t.append(s1, s2); return t;
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

function toneLines(t) {
  const sm = SUMMARY[(t.parent == null || t.parent === undefined ? "main" : "sub") + t.id];
  const n = t.tone.n || 1, f = k => pc(t.tone[k] / n);
  return (sm ? ["Machine summary: " + sm] : []).concat(["Tone of its " + t.tone.n + " scored answers: " + f("neg") + " negative, " + f("mix") + " mixed, " + f("neu") + " neutral, " + f("pos") + " positive",
          "Mostly answers to: “" + (QTXT[t.top_q] || t.top_q) + "” (" + pc(t.top_q_share) + ")"]);
}
function barsSVG(rows, lv, o) {
  o = Object.assign({ W: 900, L: lv === "main" ? 320 : 330, rh: lv === "main" ? 38 : 22, bh: lv === "main" ? 20 : 14, xmax: lv === "main" ? .8 : .4, ci: true, click: true, fs: lv === "main" ? 14 : 12.5 }, o || {});
  const pw = o.W - o.L - 92, sx = v => o.L + pw * Math.min(v, o.xmax) / o.xmax;
  const H = 24 + rows.length * o.rh + 6, svg = sv("svg", { viewBox: "0 0 " + o.W + " " + H, role: "group", "aria-label": "Share of people who raised each " + (lv === "main" ? "theme" : "sub-theme") + ", split by the tone of their answers" });
  const ticks = o.xmax >= .8 ? [0, .2, .4, .6, .8] : [0, .1, .2, .3, .4];
  ticks.forEach(t => svg.append(sv("line", { x1: sx(t), x2: sx(t), y1: 18, y2: H - 4, stroke: LINE }), tx(sx(t), 12, pc(t), { "font-size": 11.5, fill: INK3, "text-anchor": "middle", class: "n" })));
  let y = 24;
  rows.forEach(r => {
    if (r.head) {
      svg.append(sv("circle", { cx: 6, cy: y + o.rh * .55, r: 5, fill: COL[r.head.id] }), tx(16, y + o.rh * .55 + 4.5, r.head.name + " · " + pc(r.head.pct) + " of people", { "font-size": 13.5, "font-weight": 700, fill: INK }));
      y += o.rh; return;
    }
    const t = r.t, n = t.tone.n || 1, g = sv("g", {});
    g.append(sv("rect", { class: "bg", x: 0, y: y - 2, width: o.W, height: o.rh, fill: "transparent" }));
    const name = label(lv, t), tier = lv === "sub" ? TIER["sub" + t.id] : "CLAIMABLE";
    if (lv === "main") g.append(sv("circle", { cx: 7, cy: y + o.bh / 2, r: 5.5, fill: COL[t.id] }), tx(20, y + o.bh * .74, name, { "font-size": o.fs, fill: INK }));
    else g.append(tx(o.L - 12, y + o.bh * .74, name + (tier !== "CLAIMABLE" ? " †" : ""), { "font-size": o.fs, fill: tier === "CLAIMABLE" ? INK : INK2, "text-anchor": "end" }));
    let xs = sx(0);
    [[t.tone.neg / n, NEG], [(t.tone.neu + t.tone.mix) / n, MID], [t.tone.pos / n, POS]].forEach(([s, c]) => {
      const w = (sx(t.pct) - sx(0)) * s; if (w > 0) g.append(sv("rect", { x: xs, y, width: w, height: o.bh, fill: c })); xs += w;
    });
    const cy = y + o.bh / 2;
    if (o.ci) g.append(sv("line", { x1: sx(t.lo), x2: sx(t.hi), y1: cy, y2: cy, stroke: INK, "stroke-width": 1.3 }), sv("line", { x1: sx(t.lo), x2: sx(t.lo), y1: cy - 5, y2: cy + 5, stroke: INK }), sv("line", { x1: sx(t.hi), x2: sx(t.hi), y1: cy - 5, y2: cy + 5, stroke: INK }));
    const vt = tx(Math.max(sx(t.hi), sx(t.pct)) + 8, y + o.bh * .76, "", { "font-size": o.fs - .5, fill: INK, class: "n" });
    const b = sv("tspan", { "font-weight": 700 }); b.textContent = pc(t.pct); vt.append(b);
    if (o.ci) { const s = sv("tspan", { fill: INK3, "font-size": o.fs - 2.5 }); s.textContent = "  " + (t.lo * 100).toFixed(0) + "–" + (t.hi * 100).toFixed(0); vt.append(s); }
    g.append(vt);
    hoverable(g, fullName(lv, t), [t.people + " of " + R.meta.base_people + " people (" + pc(t.pct) + "), 95% range " + pc(t.lo) + " to " + pc(t.hi) + ", from " + t.teams + " teams"].concat(toneLines(t), o.click ? ["Click to light it up on the map"] : []),
      o.click ? () => showOnMap(lv, t.id) : null);
    svg.append(g); y += o.rh;
  });
  return svg;
}
const TS = { lv: "main" };
function renderTalk() {
  const box = $("#talk-fig"); if (!box) return;
  const seg = el("div", { class: "seg", role: "group", "aria-label": "Theme level" }, [["main", "7 themes"], ["sub", "39 sub-themes"]].map(([v, t]) =>
    el("button", { type: "button", "aria-pressed": TS.lv === v, text: t, onclick: () => { TS.lv = v; renderTalk(); } })));
  let rows;
  if (TS.lv === "main") rows = MAINS.slice().sort((a, b) => b.pct - a.pct).map(t => ({ t }));
  else { rows = []; MAINS.slice().sort((a, b) => b.pct - a.pct).forEach(m => { rows.push({ head: m }); SUBS.filter(s => s.parent === m.id).sort((a, b) => b.pct - a.pct).forEach(t => rows.push({ t })); }); }
  box.replaceChildren(el("div", { class: "ctlrow" }, [seg]), legend4(), el("div", { class: "figbox" }, [barsSVG(rows, TS.lv, TS.lv === "main" ? { W: 700, L: 285, fs: 13.5, rh: 34 } : { W: 760, L: 300, fs: 12, rh: 20 })]),
    el("p", { class: "fnote", text: TS.lv === "main" ? "Hover a bar for its numbers and the question it mostly answers; click it to light the theme up on the map." :
      "† = describe only: fewer than 15 people, unstable when the grouping is repeated, or a name that failed the checks (then withheld). Hover for numbers; click to see it on the map." }));
}
function legend4() {
  const k = (c, t) => el("span", {}, [el("i", { style: "background:" + c }), document.createTextNode(t)]);
  const ci = el("span", {}); ci.innerHTML = '<svg width="26" height="10" aria-hidden="true"><line x1="1" y1="5" x2="25" y2="5" stroke="#1C1917" stroke-width="1.4"/><line x1="1" y1="1" x2="1" y2="9" stroke="#1C1917"/><line x1="25" y1="1" x2="25" y2="9" stroke="#1C1917"/></svg> 95% range';
  return el("div", { class: "legend4" }, [k(NEG, "negative"), k(MID, "neutral or mixed"), k(POS, "positive"), ci]);
}

const MATRICES = [
  { box: "#country-fig", views: [["country", "Countries"]], full: true, what: "country", first: true },
  { box: "#region-fig", views: [["region", "All teams"], ["region_undergrad", "Undergraduate teams only"], ["europe", "Inside Europe"]], full: true, what: "region", type: "bars" },
  { box: "#school-fig", views: [["school", "All teams"]], full: true, what: "school level", type: "bars", ordered: true },
  { box: "#awards-fig", views: [["award_ladder", "Award ladder"], ["medal", "Medal ladder"]], full: true, what: "award", type: "ladder" }
];
const qtext = q => q < .001 ? "q < 0.001" : "q = " + q.toFixed(3);
function renderMatrix(m) {
  const box = $(m.box); if (!box) return;
  m.v = m.v || 0; m.lv = m.lv || "main";
  const key = m.views[m.v][0], tb = R.groups[key][m.lv], lv = m.lv;
  const ctl = [];
  if (m.views.length > 1) ctl.push(el("div", { class: "seg", role: "group", "aria-label": "Which groups" }, m.views.map(([k, t], i) => el("button", { type: "button", "aria-pressed": m.v === i, text: t, onclick: () => { m.v = i; renderMatrix(m); } }))));
  ctl.push(el("div", { class: "seg", role: "group", "aria-label": "Theme level" }, [["main", "7 themes"], ["sub", R.meta.n_sub_tested + " sub-themes"]].map(([v, t]) => el("button", { type: "button", "aria-pressed": m.lv === v, text: t, onclick: () => { m.lv = v; renderMatrix(m); } }))));
  const G = tb.groups.length, cols = G + 1, L = 320, cw = Math.max(76, Math.min(112, (1180 - L) / cols)), rh = lv === "main" ? 54 : 40, T0 = 64;
  const order = tb.themes.map((_, j) => j).sort((a, b) => tb.all[b] - tb.all[a]);
  const toneH = 64, W = L + cols * cw + 10, H = T0 + order.length * rh + toneH + 10;
  const svg = sv("svg", { viewBox: "0 0 " + W + " " + H, role: "group", "aria-label": "Share of people in each group who raised each " + (lv === "main" ? "theme" : "sub-theme") });
  svg.style.maxWidth = Math.round(W * 1.15) + "px";
  const cx = c => L + c * cw + cw / 2;

  svg.append(tx(cx(0), 22, "All", { "text-anchor": "middle", "font-size": 13, "font-weight": 700, fill: INK2 }), tx(cx(0), 39, tb.people.reduce((a, b) => a + b, 0) + " people", { "text-anchor": "middle", "font-size": 11, fill: INK3, class: "n" }));
  svg.append(sv("line", { x1: L + cw, x2: L + cw, y1: 8, y2: H - 8, stroke: LINE }));
  tb.groups.forEach((g, c) => {
    const few = tb.teams[c] < 5, x = cx(c + 1), words = g.split(" ");
    const pre = words.length === 1 && /^Bio(?=[a-z]{9,})/.test(g);
    const two = g.length > 13 && (words.length > 1 || pre), h1 = !two ? g : pre ? "Bio-" : words.slice(0, Math.ceil(words.length / 2)).join(" "), h2 = !two ? "" : pre ? g.slice(3) : words.slice(Math.ceil(words.length / 2)).join(" ");
    const hf = Math.min(12.5, (cw - 6) * 1.75 / Math.max(h1.length, h2.length));
    svg.append(tx(x, two ? 14 : 22, h1, { "text-anchor": "middle", "font-size": hf, "font-weight": 700, fill: INK }));
    if (two) svg.append(tx(x, 28, h2, { "text-anchor": "middle", "font-size": hf, "font-weight": 700, fill: INK }));
    svg.append(tx(x, two ? 43 : 39, tb.teams[c] + " teams" + (few ? " · few" : ""), { "text-anchor": "middle", "font-size": 11, fill: few ? "#B45309" : INK3, class: "n" }),
      tx(x, two ? 56 : 52, tb.people[c] + " people", { "text-anchor": "middle", "font-size": 11, fill: INK3, class: "n" }));
  });
  const Rmax = rh / 2 - 3;
  order.forEach((j, r) => {
    const y0 = T0 + r * rh, y = y0 + rh / 2, name = tb.themes[j], t = BYNAME[lv + "|" + name], col = colOf(lv, t), q = tb.q[j], holds = q < .05;
    if (holds) svg.append(sv("rect", { x: 0, y: y0 + 1, width: W, height: rh - 2, fill: ACCBG, rx: 6 }));
    svg.append(sv("line", { x1: 0, x2: W, y1: y0, y2: y0, stroke: "#F0EFED" }));
    svg.append(sv("circle", { cx: 10, cy: y - 6, r: 5, fill: col }));
    const nm = label(lv, t); svg.append(tx(22, y - 2, nm.length > 44 ? nm.slice(0, 43) + "…" : nm, { "font-size": lv === "main" ? 14 : 12.5, "font-weight": holds ? 700 : 400, fill: INK }));
    svg.append(tx(22, y + 13, holds ? "differs between groups · " + qtext(q) : "no clear difference", { "font-size": 11, fill: holds ? ACC : INK3, "font-weight": holds ? 700 : 400 }));
    const cell = (c, share, lo, hi, n, people, ring, res, gname) => {
      const x = cx(c), rr = Math.max(2, Math.sqrt(share) * Rmax), fill = c === 0 ? "#E4E4E4" : (ring && res > 0) ? col : (ring ? "#ffffff" : holds ? P.mix(col, P.light(col) ? .38 : .62) : "#D6D6D6");
      const g = sv("g", {});
      g.append(sv("rect", { class: "bg", x: x - cw / 2 + 2, y: y0 + 2, width: cw - 4, height: rh - 4, fill: "transparent", rx: 6 }));
      g.append(sv("circle", Object.assign({ cx: x, cy: y, r: rr, fill, stroke: ring && res < 0 ? "#8A8A8A" : "none", "stroke-width": 1.4 }, ring && res < 0 ? { "stroke-dasharray": "3 2.5" } : {})));
      const inside = rr > 15.5, outer = rr;
      g.append(tx(inside ? x : x + outer + 3, y + 4, pc(share), { "text-anchor": inside ? "middle" : "start", "font-size": 11.5, "font-weight": 600, fill: inside ? P.onFill(fill) : INK, class: "n" }));
      const lines = c === 0 ? [pc(share) + " of all " + people + " people in this view"] :
        [Math.round(share * people) + " of " + people + " people (" + pc(share) + "), 95% range " + pc(lo) + " to " + pc(hi), "All groups together: " + pc(tb.all[j])];
      if (ring) lines.push(res > 0 ? "More than expected, and it holds after correction" : "Less than expected, and it holds after correction");
      hoverable(g, (c === 0 ? "All" : gname) + " · " + fullName(lv, t), lines);
      svg.append(g);
    };
    cell(0, tb.all[j], null, null, null, tb.people.reduce((a, b) => a + b, 0), false, 0, "All");
    tb.groups.forEach((g, c) => cell(c + 1, tb.share[c][j], tb.lo[c][j], tb.hi[c][j], null, tb.people[c], holds && tb.cell_q[c][j] < .05, tb.resid[c][j], g));
  });

  const yT = T0 + order.length * rh + 8, tp = tb.tone.p;
  svg.append(sv("line", { x1: 0, x2: W, y1: yT - 4, y2: yT - 4, stroke: LINE }));
  svg.append(tx(22, yT + 22, "Tone of their answers", { "font-size": 13, "font-weight": 700, fill: INK }),
    tx(22, yT + 38, tp < .05 ? "differs (p = " + tp.toFixed(3) + ", one test of ten: describe only)" : "no clear difference (p = " + tp.toFixed(3) + ")", { "font-size": 11, fill: INK3 }));
  const toneCell = (c, pos, neg, gname) => {
    const x = cx(c), bw = cw - 22, x0 = x - bw / 2, mid = 1 - pos - neg, g = sv("g", {});
    g.append(sv("rect", { class: "bg", x: x - cw / 2 + 2, y: yT, width: cw - 4, height: toneH - 12, fill: "transparent", rx: 6 }));
    [[neg, NEG], [mid, MID], [pos, POS]].reduce((xs, [s, c2]) => { g.append(sv("rect", { x: xs, y: yT + 14, width: bw * s, height: 12, fill: c2 })); return xs + bw * s; }, x0);
    g.append(tx(x, yT + 42, pc(pos) + " positive", { "text-anchor": "middle", "font-size": 11, fill: INK2, class: "n" }));
    hoverable(g, gname + " · tone", [pc(neg) + " negative, " + pc(mid) + " neutral or mixed, " + pc(pos) + " positive (scored answers)"]);
    svg.append(g);
  };
  if (m.full) {
    const tot = Object.values(R.tone_q).reduce((a, d) => { for (const k in d) a[k] = (a[k] || 0) + d[k]; return a; }, {}), n = tot.neg + tot.mix + tot.neu + tot.pos;
    toneCell(0, tot.pos / n, tot.neg / n, "All");
  }
  tb.groups.forEach((g, c) => toneCell(c + 1, tb.tone.pos[c], tb.tone.neg[c], g));

  const hold = order.filter(j => tb.q[j] < .05);
  const notes = [];
  const robust = hold.filter(j => tb.loo[tb.themes[j]] != null);
  if (robust.length) notes.push("Still holds with any one team left out: " + robust.map(j => label(lv, BYNAME[lv + "|" + tb.themes[j]]) + " (largest p = " + tb.loo[tb.themes[j]].toFixed(3) + ")").join("; ") + ".");

  box.replaceChildren(el("div", { class: "ctlrow" }, ctl), el("div", { class: "figbox min900" }, [svg]),
    ...notes.map(s => el("p", { class: "fnote", text: s })), ...(m.first ? [
    el("p", { class: "fnote", text: "Circle size = share of the group’s people who raised the theme; the first column is everyone in this view. A row in colour = the theme differs between the groups, and it holds after correction; a full-colour circle = this group alone is above what is expected; dashed outline = below; grey = no clear difference. Test: 4,000 shuffles of the group label between whole teams, Benjamini–Hochberg correction over the " + tb.themes.length + (lv === "main" ? " themes" : " sub-themes") + "." })] : [
    el("p", { class: "fnote", text: "Circle size = share of the group’s people who raised the theme; the first column is everyone in this view. A row in colour = the theme differs between the groups after correction; grey = no clear difference." })]), ...forestBlock(m, key));
}

const rowsOf = lv => lv === "sub" ? R.contrasts.rows_sub : R.contrasts.rows;
const rowTheme = (lv, j) => { const nmR = rowsOf(lv); return j < nmR.length - 1 ? BYNAME[lv + "|" + nmR[j]] : null; };
const rowName = j => rowTheme("main", j);
function forestSVG(cons, o) {
  o = Object.assign({ W: 1000, L: 200, rh: 34, fs: 13.5, head: true, labels: true, compact: false, lv: "main" }, o || {});
  const LV = o.lv, sfx = LV === "sub" ? "_sub" : "", RT = j => rowTheme(LV, j), RC = t => t ? colOf(LV, t) : POS;
  const nm = rowsOf(LV).length - 1, n = cons.length, gap = 26, pw = (o.W - o.L - gap * (n - 1)) / n;
  const V = (c, f) => c[f + sfx];
  const rows = rowsOf(LV).map((_, j) => j).sort((a, b) => ((a === nm) - (b === nm)) || (((RT(b) || {}).pct || 0) - ((RT(a) || {}).pct || 0)));
  const MINI = { 0: "Innovation", 1: "Inspiring but hard", 2: "Money", 3: "Teamwork", 4: "Time, school", 5: "Team bonds", 6: "Confidence" };
  const fmtv = v => Math.abs(v) < .5 ? "0" : (v > 0 ? "+" : "−") + Math.abs(v).toFixed(0);
  const ext = Math.max(10, ...cons.map(c => Math.max(...V(c, "lo").map(Math.abs), ...V(c, "hi").map(Math.abs))));
  const Rg = Math.min(50, Math.ceil(ext / 10) * 10), T0 = o.head ? 50 : 8, H = T0 + rows.length * o.rh + 18;
  const svg = sv("svg", { viewBox: "0 0 " + o.W + " " + H, role: "group", "aria-label": "Differences between groups in percentage points, with 95% ranges" });
  svg.style.maxWidth = Math.round(o.W * 1.1) + "px";
  rows.forEach((j, r) => {
    const y = T0 + r * o.rh + o.rh / 2, t = RT(j), tone = !t, any = cons.some(c => V(c, "sig")[j]);
    if (tone) svg.append(sv("line", { x1: 0, x2: o.W, y1: y - o.rh / 2, y2: y - o.rh / 2, stroke: LINE }));
    if (o.labels) {
      let nmT = tone ? "Positive tone" : label(LV, t);
      svg.append(sv("circle", { cx: 7, cy: y, r: LV === "sub" ? 4 : 5, fill: RC(t) }));
      svg.append(wrapLabel(19, y, nmT, Math.floor((o.L - 26) / (o.fs * .52)), { "font-size": o.fs, fill: INK, "font-weight": tone || any ? 700 : 400 }));
    }
  });
  cons.forEach((c, k) => {
    const x0 = o.L + k * (pw + gap), sx = v => x0 + pw * (Math.max(-Rg, Math.min(Rg, v)) + Rg) / (2 * Rg);
    if (o.head) {
      svg.append(tx(x0 + pw / 2, 15, c.name, { "text-anchor": "middle", "font-size": o.compact ? 12 : 13, "font-weight": 700, fill: INK }),
        tx(x0 + pw / 2, 31, c.a_people != null ? c.a_people + " people (" + c.a_teams + " teams) vs " + c.b_people + " (" + c.b_teams + " teams)" : c.a_teams + " vs " + c.b_teams + " teams", { "text-anchor": "middle", "font-size": 11, fill: INK3, class: "n" }));
    }
    svg.append(sv("rect", { x: x0, y: T0 - 4, width: pw, height: rows.length * o.rh + 8, fill: "none", rx: 6 }));
    [-Rg, -Rg / 2, 0, Rg / 2, Rg].forEach(v => svg.append(sv("line", { x1: sx(v), x2: sx(v), y1: T0 - 4, y2: T0 + rows.length * o.rh + 4, stroke: v === 0 ? INK3 : "#ECEBE9", "stroke-width": v === 0 ? 1.2 : 1 })));
    [-Rg, 0, Rg].forEach(v => svg.append(tx(sx(v) + (v < 0 ? 2 : v > 0 ? -2 : 0), H - 2, (v > 0 ? "+" : v < 0 ? "−" : "") + Math.abs(v) + (v === 0 ? " points" : ""), { "text-anchor": v < 0 ? "start" : v > 0 ? "end" : "middle", "font-size": 10.5, fill: INK3, class: "n" })));
    rows.forEach((j, r) => {
      const y = T0 + r * o.rh + o.rh / 2, t = RT(j), v = V(c, "pp")[j], lo = V(c, "lo")[j], hi = V(c, "hi")[j], sig = V(c, "sig")[j], col = sig ? RC(t) : "#9A9A9A";
      const g = sv("g", {});
      g.append(sv("rect", { class: "bg", x: x0, y: y - o.rh / 2 + 1, width: pw, height: o.rh - 2, fill: "transparent", rx: 4 }));
      g.append(sv("line", { x1: sx(lo), x2: sx(hi), y1: y, y2: y, stroke: col, "stroke-width": sig ? 3 : 2, opacity: sig ? 1 : .55, "stroke-linecap": "round" }));
      g.append(sv("circle", { cx: sx(v), cy: y, r: sig ? 6.5 : 5, fill: sig ? col : "#fff", stroke: col, "stroke-width": 2 }));
      let right = v >= 0; if (right && sx(hi) + 30 > x0 + pw) right = false; else if (!right && sx(lo) - 30 < x0) right = true;
      const lx = right ? sx(hi) + 6 : sx(lo) - 6;
      g.append(tx(lx, y + 4, fmtv(v), { "text-anchor": right ? "start" : "end", "font-size": 11.5, "font-weight": sig ? 700 : 400, fill: sig ? INK : INK2, class: "n" }));
      if (hi > Rg) g.append(sv("path", { d: "M" + (x0 + pw - 7) + "," + (y - 4) + " L" + (x0 + pw - 1) + "," + y + " L" + (x0 + pw - 7) + "," + (y + 4) + " Z", fill: col }));
      if (lo < -Rg) g.append(sv("path", { d: "M" + (x0 + 7) + "," + (y - 4) + " L" + (x0 + 1) + "," + y + " L" + (x0 + 7) + "," + (y + 4) + " Z", fill: col }));
      const ab = c.name.split(" vs ");
      hoverable(g, c.name + " · " + (t ? fullName(LV, t) : "Positive tone of answers"),
        [(v > 0 ? "+" : "") + v.toFixed(1) + " percentage points (95% range " + lo.toFixed(1) + " to " + hi.toFixed(1) + ")",
         (t ? "Share of people who raised it" : "Share of answers with a positive tone") + ": " + ab[0] + " minus " + (ab[1] || "the rest"),
         ...(c.a_pct ? [ab[0] + ": " + V(c, "a_pct")[j].toFixed(0) + "% " + "·" + " " + (ab[1] || "the rest") + ": " + V(c, "b_pct")[j].toFixed(0) + "%"] : []),
         sig ? "Holds: the range excludes 0 and the test holds after correction" : "Does not hold after correction"]);
      svg.append(g);
    });
  });
  return svg;
}
const FMAP = { country: ["country", true], region: ["region"], region_undergrad: ["region_undergrad"], europe: ["europe", true], school: ["school"],
  school_asia: ["school_asia"], village: ["village", true] };
const POWER_OF = { school: ["Undergraduate vs high school"], school_asia: ["Undergraduate vs high school"], region: ["Asia vs Europe"], region_undergrad: ["Asia vs Europe"],
  medal: ["gold medal vs other teams", "special prize vs none"], special: ["gold medal vs other teams", "special prize vs none"], nominated: ["gold medal vs other teams", "special prize vs none"] };
function powerLine(key) {
  const ps = POWER_OF[key]; if (!ps) return [];
  const txt = ps.map(p => { const v = R5.power.filter(r => r.comparison === p).map(r => r.mde_points); return p + ": about " + Math.round(Math.min(...v)) + " to " + Math.round(Math.max(...v)) + " points"; }).join("; ");
  return [el("p", { class: "fnote", text: "Smallest difference these groups could reveal (80% power, teams taken into account): " + txt + ". Smaller gaps may exist and stay hidden." })];
}
function forestBlock(m, key) {
  if (key === "medal" || key === "special" || key === "nominated") return ladderBlock(m).concat(powerLine(key));
  const fm = FMAP[key]; if (!fm) return [];
  const set = fm[0], pick = !!fm[1], all = R.contrasts[set]; m.pick = m.pick || {};
  if (pick && m.pick[set] == null) {
    const best = all.map((c, i) => [Math.max(0, ...c.pp.map(Math.abs).filter((_, j) => c.sig[j])), i]).sort((a, b) => b[0] - a[0])[0]; m.pick[set] = best[1];
  }
  const cons = pick ? [all[m.pick[set]]] : all;
  const parts = [];
  if (m.first) parts.push(el("p", { class: "fnote", text: "Each dot is a difference in percentage points between two groups, with its 95% range. Filled dot and thick line = holds after correction. The last row compares the share of positive answers. Base: people with at least one answer that has a theme; “all other teams” = every team outside the group, together." }));
  if (pick) {
    const sel = el("select", { class: "fsel", "aria-label": "Group to compare with all others", onchange: e => { m.pick[set] = +e.target.value; renderMatrix(m); } },
      all.map((c, i) => { const op = el("option", { value: i, text: c.name }); if (i === m.pick[set]) op.selected = true; return op; }));
    parts.push(el("div", { class: "ctlrow" }, [sel]));
  }
  const sub = m.lv === "sub";
  parts.push(el("div", { class: "figbox" }, [forestSVG(cons, { W: pick || cons.length === 1 ? (sub ? 820 : 760) : 1000, L: sub ? 300 : 300, rh: sub ? 24 : 34, fs: sub ? 12.5 : 13.5, lv: m.lv })]));
  return [fold(m.box + "|forest", "How big are the differences?", parts.concat(powerLine(key)))];
}

const OPEN = {};
function fold(key, title, nodes) {
  const d = el("details", { class: "more fold" }, [el("summary", { text: title }), ...nodes]);
  d.open = !!OPEN[key];
  d.addEventListener("toggle", () => { OPEN[key] = d.open; });
  return d;
}

const fmtOR = v => "\u00d7" + (v >= 10 ? v.toFixed(0) : v.toFixed(2));
function orForestSVG(panels, rows, o) {

  o = Object.assign({ W: 1000, L: 230, rh: 32, fs: 13.5, head: true, maxR: 3 }, o || {});
  const n = panels.length, gap = 26, pw = (o.W - o.L - gap * (n - 1)) / n, T0 = o.head ? 50 : 8, H = T0 + rows.length * o.rh + 18;
  let ext = 1; panels.forEach(p => rows.forEach(r => { const v = p.get(r.key); if (v && v.fitted) ext = Math.max(ext, Math.abs(Math.log2(v.lo)), Math.abs(Math.log2(v.hi))); }));
  const Rg = Math.min(o.maxR, Math.max(1, Math.ceil(ext)));
  const svg = sv("svg", { viewBox: "0 0 " + o.W + " " + H, role: "group", "aria-label": "Odds ratios with 95% ranges; 1 means no link" });
  svg.style.maxWidth = Math.round(o.W * 1.1) + "px";
  rows.forEach((r, i) => {
    const y = T0 + i * o.rh + o.rh / 2;
    if (r.rule) svg.append(sv("line", { x1: 0, x2: o.W, y1: y - o.rh / 2, y2: y - o.rh / 2, stroke: LINE }));
    svg.append(sv("circle", { cx: 7, cy: y, r: 5, fill: r.color }));
    const any = panels.some(p => { const v = p.get(r.key); return v && v.fitted && v.q < .05; });
    svg.append(wrapLabel(19, y, r.label, Math.floor((o.L - 26) / (o.fs * .52)), { "font-size": o.fs, fill: INK, "font-weight": any ? 700 : 400 }));
  });
  panels.forEach((p, k) => {
    const x0 = o.L + k * (pw + gap), sx = v => x0 + pw * (Math.max(-Rg, Math.min(Rg, Math.log2(v))) + Rg) / (2 * Rg);
    if (o.head) svg.append(tx(x0 + pw / 2, 15, p.title, { "text-anchor": "middle", "font-size": 13, "font-weight": 700, fill: INK }),
      tx(x0 + pw / 2, 31, p.sub || "", { "text-anchor": "middle", "font-size": 11, fill: INK3 }));
    svg.append(sv("rect", { x: x0, y: T0 - 4, width: pw, height: rows.length * o.rh + 8, fill: "none", rx: 6 }));
    for (let e = -Rg; e <= Rg; e++) svg.append(sv("line", { x1: sx(2 ** e), x2: sx(2 ** e), y1: T0 - 4, y2: T0 + rows.length * o.rh + 4, stroke: e === 0 ? INK3 : "#ECEBE9", "stroke-width": e === 0 ? 1.2 : 1 }));
    [-Rg, 0, Rg].forEach(e => svg.append(tx(sx(2 ** e) + (e < 0 ? 2 : e > 0 ? -2 : 0), H - 2, e === 0 ? "\u00d71 = no link" : (e < 0 ? "\u00d71/" + 2 ** -e : "\u00d7" + 2 ** e), { "text-anchor": e < 0 ? "start" : e > 0 ? "end" : "middle", "font-size": 10.5, fill: INK3, class: "n" })));
    rows.forEach((r, i) => {
      const y = T0 + i * o.rh + o.rh / 2, v = p.get(r.key), g = sv("g", {});
      g.append(sv("rect", { class: "bg", x: x0, y: y - o.rh / 2 + 1, width: pw, height: o.rh - 2, fill: "transparent", rx: 4 }));
      if (!v || !v.fitted) {
        g.append(tx(x0 + pw / 2, y + 4, "\u2013", { "text-anchor": "middle", "font-size": 12, fill: INK3 }));
        hoverable(g, p.title + " \u00b7 " + r.label, [v && v.note ? v.note : "could not be estimated"]); svg.append(g); return;
      }
      const sig = v.q < .05, col = sig ? r.color : "#9A9A9A";
      g.append(sv("line", { x1: sx(v.lo), x2: sx(v.hi), y1: y, y2: y, stroke: col, "stroke-width": sig ? 3 : 2, opacity: sig ? 1 : .55, "stroke-linecap": "round" }));
      g.append(sv("circle", { cx: sx(v.OR), cy: y, r: sig ? 6.5 : 5, fill: sig ? col : "#fff", stroke: col, "stroke-width": 2 }));
      let right = v.OR >= 1; if (right && sx(v.hi) + 44 > x0 + pw) right = false; else if (!right && sx(v.lo) - 44 < x0) right = true;
      g.append(tx(right ? sx(v.hi) + 6 : sx(v.lo) - 6, y + 4, fmtOR(v.OR), { "text-anchor": right ? "start" : "end", "font-size": 11.5, "font-weight": sig ? 700 : 400, fill: sig ? INK : INK2, class: "n" }));
      if (Math.log2(v.hi) > Rg) g.append(sv("path", { d: "M" + (x0 + pw - 7) + "," + (y - 4) + " L" + (x0 + pw - 1) + "," + y + " L" + (x0 + pw - 7) + "," + (y + 4) + " Z", fill: col }));
      if (Math.log2(v.lo) < -Rg) g.append(sv("path", { d: "M" + (x0 + 7) + "," + (y - 4) + " L" + (x0 + 1) + "," + y + " L" + (x0 + 7) + "," + (y + 4) + " Z", fill: col }));
      hoverable(g, p.title + " \u00b7 " + r.label, ["Odds ratio " + v.OR.toFixed(2) + " (95% range " + v.lo.toFixed(2) + " to " + v.hi.toFixed(2) + "), q = " + v.q.toFixed(3)].concat(v.extra || [],
        [sig ? "Holds after correction" : "Does not hold after correction"]));
      svg.append(g);
    });
  });
  return svg;
}
const themeRows = (lv, have) => (lv === "sub" ? SUBS : MAINS).filter(t => !have || have.has(t.name)).sort((a, b) => b.pct - a.pct).map(t => ({ key: t.name, label: label(lv, t), color: colOf(lv, t) }));
const tested = (list, lv) => new Set(list.filter(r => r.level === lv).map(r => r.theme));
function ladderBlock(m) {
  const lv = m.lv || "main", get = out => key => R5.ordinal.find(r => r.outcome === out && r.level === lv && r.theme === key);
  const ex = r => r ? [r.p_shuffle != null ? "Team shuffle: p = " + r.p_shuffle : "", r.gold_OR != null ? "Gold vs other teams: odds ratio " + r.gold_OR.toFixed(2) + ", q = " + r.gold_q.toFixed(3) : "",
    r.po_flag ? "The ladder assumption is doubtful for this theme (separate cuts differ)" : ""].filter(Boolean) : [];
  const wrap = out => key => { const r = get(out)(key); return r ? Object.assign({}, r, { extra: ex(r) }) : null; };
  const L5 = R5.meta;
  const panels = [{ title: "Award ladder", sub: "none " + L5.award_ladder[0] + " \u2192 nominated " + L5.award_ladder[1] + " \u2192 special prize " + L5.award_ladder[2] + " teams", get: wrap("award ladder") },
                  { title: "Medal ladder", sub: "none " + L5.medal_ladder[0] + " \u2192 bronze " + L5.medal_ladder[1] + " \u2192 silver " + L5.medal_ladder[2] + " \u2192 gold " + L5.medal_ladder[3], get: wrap("medal ladder") }];
  return [el("h3", { class: "subhead", text: "Does talking more about a theme go with climbing the ladder?" }),
    el("p", { class: "fnote", text: "Ordinal model per theme, one row per theme: the odds of a higher step when 10% more of a team\u2019s people raised the theme, allowing for region, school level and team size. \u00d71 = no link; filled = holds after correction." }),
    el("div", { class: "figbox" }, [orForestSVG(panels, themeRows(lv, tested(R5.ordinal, lv)), { W: 1000, L: 300, rh: lv === "sub" ? 24 : 32, fs: lv === "sub" ? 12.5 : 13.5 })])];
}
const FACTOR_ROWS = [["Asia vs Europe", "North America vs Europe", "Other regions vs Europe"], ["Undergraduate vs high school", "Graduate vs high school", "medal ladder (+1 step)"],
                     ["award ladder (+1 step)", "team respondents (log)", "answer length (log words)"]];
const CS = { lv: "main" };
function renderCombined() {
  const box = $("#combined-fig"); if (!box) return;
  const lv = CS.lv, rows = themeRows(lv, tested(R5.combined, lv));
  const seg = el("div", { class: "seg", role: "group", "aria-label": "Theme level" }, [["main", "7 themes"], ["sub", R.meta.n_sub_tested + " sub-themes"]].map(([v, t]) =>
    el("button", { type: "button", "aria-pressed": CS.lv === v, text: t, onclick: () => { CS.lv = v; renderCombined(); } })));
  const get = f => key => R5.combined.find(r => r.level === lv && r.theme === key && r.factor === f);
  const nice = f => f.replace("(+1 step)", "(per step)").replace("team respondents (log)", "team size (log)").replace("answer length (log words)", "longer answers (log words)");
  box.replaceChildren(el("div", { class: "ctlrow" }, [seg]),
    ...FACTOR_ROWS.map(fr => el("div", { class: "figbox" }, [orForestSVG(fr.map(f => ({ title: nice(f), sub: "", get: get(f) })), rows,
      { W: 1000, L: lv === "sub" ? 280 : 310, rh: lv === "sub" ? 22 : 34, fs: lv === "sub" ? 12 : 13.5 })])),
    el("p", { class: "fnote", text: "One model per theme, on people (328), with people grouped by team (generalised estimating equations). Each panel is one factor, all factors in the same model. \u2013 = not estimable: nobody in that group raised the theme, or the model did not fit." }));
}

function renderTone() {
  const box = $("#tone-fig"); if (!box) return;
  const QN = { "Connection": "Feeling connected", "Team Work": "Teamwork", "Beyond iGEM": "Purpose and career", "Conditions": "What supported or limited you", "One Word": "One word" };
  const rows = Object.keys(R.tone_q).map(k => { const d = R.tone_q[k], n = d.neg + d.mix + d.neu + d.pos; return { k, n, neg: d.neg / n, mid: (d.mix + d.neu) / n, pos: d.pos / n }; }).sort((a, b) => b.pos - a.pos);
  const W = 620, L = 226, rh = 42, bh = 20, pw = W - L - 112, H = 26 + rows.length * rh;
  const svg = sv("svg", { viewBox: "0 0 " + W + " " + H, role: "group", "aria-label": "Tone of the answers to each of the five questions" });
  [0, .5, 1].forEach(t => svg.append(sv("line", { x1: L + pw * t, x2: L + pw * t, y1: 18, y2: H - 6, stroke: LINE }), tx(L + pw * t, 12, pc(t), { "font-size": 11.5, fill: INK3, "text-anchor": "middle", class: "n" })));
  rows.forEach((r, i) => {
    const y = 28 + i * rh, g = sv("g", {});
    g.append(sv("rect", { class: "bg", x: 0, y: y - 6, width: W, height: rh - 4, fill: "transparent" }));
    g.append(tx(0, y + bh * .74, QN[r.k] || r.k, { "font-size": 13.5, fill: INK }));
    let xs = L; [[r.neg, NEG], [r.mid, MID], [r.pos, POS]].forEach(([s, c]) => { g.append(sv("rect", { x: xs, y, width: pw * s, height: bh, fill: c })); xs += pw * s; });
    const vt = tx(L + pw + 8, y + bh * .76, "", { "font-size": 13, fill: INK, class: "n" }), b = sv("tspan", { "font-weight": 700 }), s2 = sv("tspan", { fill: INK3, "font-size": 11.5 });
    b.textContent = pc(r.pos); s2.textContent = " positive"; vt.append(b, s2); g.append(vt);
    hoverable(g, "Question: " + (QTXT[r.k] || QN[r.k] || r.k), [pc(r.neg) + " negative, " + pc(r.mid) + " neutral or mixed, " + pc(r.pos) + " positive", r.n + " scored answers"]);
    svg.append(g);
  });
  const R2 = R5.tone_r2;
  box.replaceChildren(el("div", { class: "figbox" }, [svg]),
    el("p", { class: "fnote", text: "Each bar is every scored answer to one question (" + R5.meta.scored_answers + " in all): orange = negative, grey = neutral or mixed, blue = positive. In a model of the tone, the questions alone explain " + R2["question only"].toFixed(2) + " of it (McFadden pseudo R²); region, school level, medals and awards alone explain " + R2["groups only"].toFixed(3) + "." }));
}

function flowSVG(o) {
  o = Object.assign({ W: 1000, H: 430, labels: true, nodeW: 12, padL: 300, padR: 330, gap: 8 }, o || {});
  const F = R.flow, Qn = F.questions.map((q, i) => F.counts[i].reduce((a, b) => a + b, 0)), tot = Qn.reduce((a, b) => a + b, 0);
  const tN = F.themes.map((_, j) => F.counts.reduce((a, r) => a + r[j], 0));
  const tOrder = F.themes.map((t, j) => j).sort((a, b) => ((F.themes[a] < 0) - (F.themes[b] < 0)) || (tN[b] - tN[a]));
  const k = (o.H - 10 - o.gap * (Math.max(F.questions.length, F.themes.length) - 1)) / tot, xL = o.padL, xR = o.W - o.padR;
  const svg = sv("svg", { viewBox: "0 0 " + o.W + " " + o.H, role: "group", "aria-label": "Which question each theme comes from" });
  svg.style.maxWidth = Math.round(o.W * 1.1) + "px";
  const qy = [], ty = []; let y = 5; F.questions.forEach((q, i) => { qy[i] = y; y += Qn[i] * k + o.gap; });
  y = 5; tOrder.forEach(j => { ty[j] = y; y += tN[j] * k + o.gap; });
  const qoff = qy.slice(), toff = ty.slice(), colT = j => F.themes[j] < 0 ? "#C9C5C0" : COL[F.themes[j]];
  const nameT = j => F.themes[j] < 0 ? "No theme" : MAINS.find(t => t.id === F.themes[j]).name;
  F.questions.forEach((q, i) => tOrder.forEach(j => {
    const c = F.counts[i][j]; if (!c) return; const h = c * k, y0 = qoff[i], y1 = toff[j]; qoff[i] += h; toff[j] += h;
    const mx = (xL + o.nodeW + xR) / 2, d = "M" + (xL + o.nodeW) + "," + y0 + " C" + mx + "," + y0 + " " + mx + "," + y1 + " " + xR + "," + y1 +
      " L" + xR + "," + (y1 + h) + " C" + mx + "," + (y1 + h) + " " + mx + "," + (y0 + h) + " " + (xL + o.nodeW) + "," + (y0 + h) + " Z";
    const g = sv("g", {}); g.append(sv("path", { d, fill: colT(j), opacity: .5 }));
    if (o.labels) hoverable(g, (QTXT[q] || q) + " → " + nameT(j), [c + " answers", pc(c / Qn[i]) + " of the answers to this question", pc(c / tN[j]) + " of the answers in this theme"]);
    svg.append(g);
  }));
  F.questions.forEach((q, i) => {
    svg.append(sv("rect", { x: xL, y: qy[i], width: o.nodeW, height: Qn[i] * k, fill: INK, rx: 2 }));
    if (o.labels) svg.append(tx(xL - 10, qy[i] + Qn[i] * k / 2 - 2, QTXT[q] || q, { "text-anchor": "end", "font-size": 13, fill: INK }), tx(xL - 10, qy[i] + Qn[i] * k / 2 + 13, Qn[i] + " answers", { "text-anchor": "end", "font-size": 11, fill: INK3, class: "n" }));
  });
  tOrder.forEach(j => {
    svg.append(sv("rect", { x: xR, y: ty[j], width: o.nodeW, height: Math.max(1, tN[j] * k), fill: colT(j), rx: 2 }));
    if (o.labels) svg.append(tx(xR + o.nodeW + 10, ty[j] + tN[j] * k / 2 + 4.5, nameT(j), { "font-size": 13, fill: INK }), tx(o.W - 2, ty[j] + tN[j] * k / 2 + 4.5, tN[j] + "", { "text-anchor": "end", "font-size": 11, fill: INK3, class: "n" }));
  });
  return svg;
}
function renderFlow() {
  const box = $("#flow-fig"); if (!box) return;
  box.replaceChildren(el("div", { class: "figbox" }, [flowSVG()]), el("p", { class: "fnote", text: "Each band is a group of answers: from the question they answer (left) to the theme they were given (right). Band width = number of answers (final theme assignment, all 1,505 answers). Hover a band for its numbers." }));
}

const SHORTG = { "North America": "N. America", "Other regions": "Other", "Undergraduate": "Undergrad.", "High school": "High school", "Northern Europe": "North Eu.",
  "Southern Europe": "South Eu.", "Central-Eastern Europe": "C.-East Eu.", "Netherlands": "Netherl.", "Special prize": "Special", "No award": "None" };
function panelSVG(title, color, sub, subStrong, bars, ymax, o) {
  o = Object.assign({ W: 300, H: 230, shade: false }, o || {});
  const T0 = 58, B = o.H - 40, n = bars.length, bw = Math.min(46, (o.W - 30) / n - 10), x = k => 22 + (o.W - 30) * (k + .5) / n, y = v => T0 + (B - T0) * (1 - Math.min(v, ymax) / ymax);
  const svg = sv("svg", { viewBox: "0 0 " + o.W + " " + o.H, role: "group", "aria-label": title });
  svg.append(sv("circle", { cx: 8, cy: 14, r: 5, fill: color }), wrapLabel(19, 14, title, 34, { "font-size": 13, "font-weight": 700, fill: INK }));
  svg.append(tx(19, 46, sub, { "font-size": 11.5, fill: subStrong ? ACC : INK3, "font-weight": subStrong ? 700 : 400 }));
  [0, .5, 1].filter(t => t * ymax <= ymax + 1e-9).forEach(t => svg.append(sv("line", { x1: 14, x2: o.W - 4, y1: y(t * ymax), y2: y(t * ymax), stroke: t ? "#F0EFED" : "#D9D6D2" })));
  bars.forEach((b, k) => {
    const base = o.signal === false ? "#BDBDBD" : color, fill = o.shade ? P.mix(base, .62 - .62 * k / Math.max(1, n - 1)) : base, g = sv("g", {});
    g.append(sv("rect", { class: "bg", x: x(k) - bw / 2 - 4, y: T0 - 6, width: bw + 8, height: B - T0 + 30, fill: "transparent", rx: 4 }));
    g.append(sv("rect", { x: x(k) - bw / 2, y: y(b.v), width: bw, height: B - y(b.v), fill, rx: 2, stroke: b.mark ? INK : "none", "stroke-width": b.mark ? 1.6 : 0 }));
    if (b.lo != null) g.append(sv("line", { x1: x(k), x2: x(k), y1: y(b.lo), y2: y(b.hi), stroke: INK, "stroke-width": 1.2 }), sv("line", { x1: x(k) - 5, x2: x(k) + 5, y1: y(b.hi), y2: y(b.hi), stroke: INK }), sv("line", { x1: x(k) - 5, x2: x(k) + 5, y1: y(b.lo), y2: y(b.lo), stroke: INK }));
    g.append(tx(x(k), Math.min(y(b.hi != null ? b.hi : b.v), y(b.v)) - 5, Math.round(b.v * 100) + "%", { "text-anchor": "middle", "font-size": 11.5, "font-weight": 700, fill: INK, class: "n" }));
    g.append(tx(x(k), B + 15, SHORTG[b.label] || b.label, { "text-anchor": "middle", "font-size": 11, fill: b.few ? "#B45309" : INK2 }));
    g.append(tx(x(k), B + 29, b.people + "", { "text-anchor": "middle", "font-size": 10, fill: INK3, class: "n" }));
    hoverable(g, b.label + " · " + title, [Math.round(b.v * b.people) + " of " + b.people + " people (" + Math.round(b.v * 100) + "%)" + (b.lo != null ? ", 95% range " + Math.round(b.lo * 100) + "% to " + Math.round(b.hi * 100) + "%" : "")].concat(b.few ? ["Few teams: read with care"] : []));
    svg.append(g);
  });
  return svg;
}
function smallMultiples(tb, order, lv, opts) {
  opts = opts || {};
  const gi = order.map(g => tb.groups.indexOf(g)), rows = tb.themes.map((name, j) => ({ j, name, t: BYNAME[lv + "|" + name] })).sort((a, b) => tb.all[b.j] - tb.all[a.j]);
  const ymax = Math.min(1, Math.ceil(Math.max(...rows.map(r => Math.max(...gi.map(g => tb.hi[g][r.j])))) * 10) / 10);
  const panels = rows.map(r => {
    const info = opts.info ? opts.info(r) : { sub: tb.q[r.j] < .05 ? "differs · " + qtext(tb.q[r.j]) : "no clear difference", strong: tb.q[r.j] < .05 };
    const bars = gi.map(g => ({ label: tb.groups[g], v: tb.share[g][r.j], lo: tb.lo[g][r.j], hi: tb.hi[g][r.j], people: tb.people[g], few: tb.teams[g] < 5,
      mark: !opts.info && tb.q[r.j] < .05 && tb.cell_q[g][r.j] < .05 }));
    return el("div", { class: "smp" + (info.strong ? " hold" : "") }, [panelSVG(label(lv, r.t), colOf(lv, r.t), info.sub, info.strong, bars, ymax, { shade: !!opts.shade, signal: !!info.strong })]);
  });
  if (tb.tone) {
    const bars = gi.map(g => ({ label: tb.groups[g], v: tb.tone.pos[g], people: tb.people[g], few: tb.teams[g] < 5 }));
    panels.push(el("div", { class: "smp" }, [panelSVG("Positive tone of answers", POS, tb.tone.p < .05 ? "differs (p = " + tb.tone.p.toFixed(3) + ")" : "no clear difference (p = " + tb.tone.p.toFixed(3) + ")", false, bars, 1, { shade: !!opts.shade, signal: tb.tone.p < .05 })]));
  }
  return el("div", { class: "smgrid" }, panels);
}
function levelSeg2(m, rerender) {
  return el("div", { class: "seg", role: "group", "aria-label": "Theme level" }, [["main", "7 themes"], ["sub", R.meta.n_sub_tested + " sub-themes"]].map(([v, t]) =>
    el("button", { type: "button", "aria-pressed": m.lv === v, text: t, onclick: () => { m.lv = v; rerender(m); } })));
}

const GROUPCOL = ["#E69F00", "#56B4E9", "#009E73", "#CC79A7", "#D55E00", "#0072B2"];
function dotRowTable(tb, order, lv, o) {
  o = Object.assign({ shade: false, effect: null, effTitle: "", ci: false }, o || {});
  const gi = order.map(g => tb.groups.indexOf(g)), sub = lv === "sub";
  const rows = tb.themes.map((name, j) => ({ j, name, t: BYNAME[lv + "|" + name] })).sort((a, b) => tb.all[b.j] - tb.all[a.j]);
  const W = 1000, L = sub ? 300 : 320, EW = o.effect ? 230 : 0, Xw = W - L - EW - 40, step = sub ? 10 : 13, rh = o.ci ? gi.length * step + (sub ? 10 : 16) : (sub ? 26 : 38), T0 = 48, H = T0 + rows.length * rh + 26;
  const xmax = Math.min(1, Math.ceil(Math.max(...rows.map(r => Math.max(...gi.map(g => o.ci ? tb.hi[g][r.j] : tb.share[g][r.j])))) * 10 + .5) / 10), sx = v => L + Xw * Math.min(v, xmax) / xmax;
  const ex0 = L + Xw + 40, Rg = 1, ex = v => ex0 + EW * (Math.max(-Rg, Math.min(Rg, Math.log2(v))) + Rg) / (2 * Rg);
  const dotCol = (r, k) => o.shade ? P.mix(colOf(lv, r.t), .62 - .62 * k / Math.max(1, gi.length - 1)) : GROUPCOL[k % GROUPCOL.length];
  const svg = sv("svg", { viewBox: "0 0 " + W + " " + H, role: "group", "aria-label": "Share of people raising each theme in each group" });
  svg.style.maxWidth = Math.round(W * 1.1) + "px";

  let lx = L;
  gi.forEach((g, k) => {
    const c = o.shade ? P.mix("#57534E", .62 - .62 * k / Math.max(1, gi.length - 1)) : GROUPCOL[k % GROUPCOL.length], few = tb.teams[g] < 5;
    svg.append(sv("circle", { cx: lx + 6, cy: 14, r: 6, fill: c }), tx(lx + 16, 18.5, tb.groups[g] + " (" + tb.people[g] + ")" + (few ? " few" : ""), { "font-size": 12, fill: few ? "#B45309" : INK2 }));
    lx += 30 + (tb.groups[g].length + String(tb.people[g]).length + (few ? 4 : 0)) * 6.6;
  });
  if (o.effect) svg.append(tx(ex0 + EW / 2, 18.5, o.effTitle, { "text-anchor": "middle", "font-size": 12, "font-weight": 700, fill: INK }),
    sv("line", { x1: ex(1), x2: ex(1), y1: T0 - 8, y2: H - 22, stroke: INK3 }), tx(ex(.5), H - 6, "×1/2", { "text-anchor": "start", "font-size": 10.5, fill: INK3 }),
    tx(ex(1), H - 6, "×1 = no link", { "text-anchor": "middle", "font-size": 10.5, fill: INK3 }), tx(ex(2), H - 6, "×2", { "text-anchor": "end", "font-size": 10.5, fill: INK3 }));
  [0, .25, .5, .75, 1].filter(t => t <= xmax + 1e-9).forEach(t => svg.append(sv("line", { x1: sx(t), x2: sx(t), y1: T0 - 8, y2: H - 22, stroke: "#EFEEEC" }), tx(sx(t), H - 6, Math.round(t * 100) + "%", { "text-anchor": "middle", "font-size": 10.5, fill: INK3, class: "n" })));
  rows.forEach((r, i) => {
    const y = T0 + i * rh + rh / 2, col = colOf(lv, r.t), eff = o.effect ? o.effect(r) : null, holds = eff ? (eff.fitted && eff.q < .05) : tb.q[r.j] < .05, g = sv("g", {});
    if (holds) g.append(sv("rect", { x: 0, y: y - rh / 2 + 1, width: W, height: rh - 2, fill: ACCBG, rx: 5 }));
    g.append(sv("rect", { class: "bg", x: 0, y: y - rh / 2 + 1, width: W, height: rh - 2, fill: "transparent", rx: 5 }));
    g.append(sv("circle", { cx: 7, cy: y, r: sub ? 4 : 5, fill: col }));
    g.append(wrapLabel(19, y, label(lv, r.t), Math.floor((L - 30) / ((sub ? 12 : 13.5) * .52)), { "font-size": sub ? 12 : 13.5, fill: INK, "font-weight": holds ? 700 : 400 }));
    const vals = gi.map(gg => tb.share[gg][r.j]), xs = vals.map(sx);
    if (o.ci) {
      gi.forEach((gg, k) => {
        const yk = y + (k - (gi.length - 1) / 2) * step, c = dotCol(r, k);
        g.append(sv("line", { x1: sx(tb.lo[gg][r.j]), x2: sx(tb.hi[gg][r.j]), y1: yk, y2: yk, stroke: c, "stroke-width": sub ? 2 : 2.6, "stroke-linecap": "round" }),
          sv("circle", { cx: xs[k], cy: yk, r: sub ? 3.6 : 4.6, fill: c, stroke: "#57534E", "stroke-width": .7 }));
        if (!sub) g.append(tx(sx(tb.hi[gg][r.j]) + 5, yk + 3.8, Math.round(vals[k] * 100) + "%", { "font-size": 10.5, fill: INK2, class: "n" }));
      });
    } else {
      g.append(sv("line", { x1: Math.min(...xs), x2: Math.max(...xs), y1: y, y2: y, stroke: "#D6D3D1", "stroke-width": 2 }));
      if (o.shade) g.append(sv("polyline", { points: xs.map(x => x + "," + y).join(" "), fill: "none", stroke: col, "stroke-width": 1.2, opacity: .5 }));
      gi.forEach((gg, k) => g.append(sv("circle", { cx: xs[k], cy: y, r: sub ? 5 : 6.5, fill: dotCol(r, k), stroke: "#736C66", "stroke-width": .7 })));
    }
    if (!o.effect) g.append(tx(L + Xw + 8, y + 4, holds ? "differs · " + qtext(tb.q[r.j]) : "", { "font-size": 11, fill: ACC, "font-weight": 700 }));
    if (eff && eff.fitted) {
      const sig = eff.q < .05;
      g.append(sv("line", { x1: ex(eff.lo), x2: ex(eff.hi), y1: y, y2: y, stroke: col, "stroke-width": sig ? 3 : 2, opacity: sig ? 1 : .55, "stroke-linecap": "round" }),
        sv("circle", { cx: ex(eff.OR), cy: y, r: sig ? 6 : 4.5, fill: sig ? col : "#fff", stroke: col, "stroke-width": 2 }));
      const right = eff.OR >= 1 && ex(eff.hi) + 40 < ex0 + EW;
      g.append(tx(right ? ex(eff.hi) + 5 : ex(eff.lo) - 5, y + 4, "×" + eff.OR.toFixed(2), { "text-anchor": right ? "start" : "end", "font-size": 11, fill: sig ? INK : INK2, "font-weight": sig ? 700 : 400, class: "n" }));
    }
    const lines = gi.map(gg => tb.groups[gg] + ": " + Math.round(tb.share[gg][r.j] * 100) + "% of " + tb.people[gg] + " people (95% range " + Math.round(tb.lo[gg][r.j] * 100) + "% to " + Math.round(tb.hi[gg][r.j] * 100) + "%)");
    if (eff && eff.fitted) lines.push(o.effTitle + ": odds ratio " + eff.OR.toFixed(2) + " (95% range " + eff.lo.toFixed(2) + " to " + eff.hi.toFixed(2) + "), q = " + eff.q.toFixed(3));
    else if (!o.effect) lines.push(tb.q[r.j] < .05 ? "Differs between groups after correction (" + qtext(tb.q[r.j]) + ")" : "No clear difference between groups");
    hoverable(g, fullName(lv, r.t), lines);
    svg.append(g);
  });
  return el("div", { class: "figbox" }, [svg]);
}
function renderBars(m) {
  const box = $(m.box); if (!box) return;
  m.v = m.v || 0; m.lv = m.lv || "main";
  const key = m.views[m.v][0], tb = R.groups[key][m.lv], ctl = [];
  if (m.views.length > 1) ctl.push(el("div", { class: "seg", role: "group", "aria-label": "Which groups" }, m.views.map(([k, t], i) => el("button", { type: "button", "aria-pressed": m.v === i, text: t, onclick: () => { m.v = i; renderBars(m); } }))));
  if (!m.noSub) ctl.push(levelSeg2(m, renderBars));
  const robust = tb.themes.map((_, j) => j).filter(j => tb.q[j] < .05 && tb.loo[tb.themes[j]] != null);
  const sub = m.lv === "sub";
  box.replaceChildren(...(ctl.length ? [el("div", { class: "ctlrow" }, ctl)] : []), sub ? dotRowTable(tb, tb.groups, m.lv, { shade: !!m.ordered }) : smallMultiples(tb, tb.groups, m.lv, { shade: !!m.ordered }),
    el("p", { class: "fnote", text: sub ? "One row per sub-theme: each dot is the share of a group’s people who raised it (hover for the 95% range). Bold row = differs between groups after correction." :
      "Each panel is one theme: the share of each group’s people who raised it, with its 95% range. Number under a bar = people in the group. Coloured panel = the theme differs between groups after correction; grey = no clear difference; a dark outline marks the group that stands out." }),
    ...(robust.length ? [el("p", { class: "fnote", text: "Still holds with any one team left out: " + robust.map(j => label(m.lv, BYNAME[m.lv + "|" + tb.themes[j]]) + " (largest p = " + tb.loo[tb.themes[j]].toFixed(3) + ")").join("; ") + "." })] : []),
    ...forestBlock(m, key));
}

function ladderAB(lv, outName, ladderTxt) {
  const ords = R5.ordinal.filter(r => r.outcome === outName && r.level === lv), trs = (R5.trend || []).filter(r => r.outcome === outName && r.level === lv);
  const rows = (lv === "sub" ? SUBS : MAINS).filter(t => ords.some(o => o.theme === t.name)).sort((a, b) => b.pct - a.pct);
  const sub = lv === "sub", W = 1000, L = sub ? 300 : 320, gap = 40, pw = (W - L - gap) / 2, rh = sub ? 24 : 34, T0 = 66, H = T0 + rows.length * rh + 30;
  const UP = "#3F7F45", DOWN = "#7569B0";
  const aExt = Math.max(1, ...ords.filter(o => o.fitted).map(o => Math.max(Math.abs(Math.log2(o.lo)), Math.abs(Math.log2(o.hi))))), aR = Math.min(2, Math.ceil(aExt * 2) / 2);
  const bExt = Math.max(5, ...trs.map(t => Math.max(Math.abs(t.lo), Math.abs(t.hi)))), bR = Math.min(40, Math.ceil(bExt / 5) * 5);
  const xa = v => L + pw * (Math.max(-aR, Math.min(aR, v)) + aR) / (2 * aR), xb = v => L + pw + gap + pw * (Math.max(-bR, Math.min(bR, v)) + bR) / (2 * bR);
  const svg = sv("svg", { viewBox: "0 0 " + W + " " + H, role: "group", "aria-label": "Ladder regressions A and B for each theme" });
  svg.style.maxWidth = Math.round(W * 1.1) + "px";
  const head = (x0, t1, t2) => svg.append(tx(x0 + pw / 2, 16, t1, { "text-anchor": "middle", "font-size": 13, "font-weight": 700, fill: INK }), tx(x0 + pw / 2, 33, t2, { "text-anchor": "middle", "font-size": 11, fill: INK3 }));
  head(L, "A · Do these teams sit higher on the " + ladderTxt + "?", "odds of a higher step, per 10 points more of the team raising it");
  head(L + pw + gap, "B · Does the share rise step by step?", "change in the share raising it, per step up the " + ladderTxt);
  [[L, xa, [-aR, 0, aR], v => v === 0 ? "×1 = no link" : v < 0 ? "×1/" + 2 ** -v : "×" + 2 ** v], [L + pw + gap, xb, [-bR, 0, bR], v => v === 0 ? "0 = no change" : (v > 0 ? "+" : "−") + Math.abs(v) + " points"]].forEach(([x0, xf, ticks, lab]) => {
    svg.append(sv("rect", { x: x0, y: T0 - 6, width: pw, height: rows.length * rh + 10, fill: "none", rx: 6 }));
    ticks.forEach(v => svg.append(sv("line", { x1: xf(v), x2: xf(v), y1: T0 - 6, y2: T0 + rows.length * rh + 4, stroke: v === 0 ? INK3 : "#ECEBE9", "stroke-width": v === 0 ? 1.3 : 1 }),
      tx(xf(v) + (v < 0 ? 2 : v > 0 ? -2 : 0), H - 8, lab(v), { "text-anchor": v < 0 ? "start" : v > 0 ? "end" : "middle", "font-size": 10.5, fill: INK3 })));
    svg.append(tx(x0 + 4, T0 - 12, "← lower", { "font-size": 10.5, fill: INK3 }), tx(x0 + pw - 4, T0 - 12, "higher →", { "text-anchor": "end", "font-size": 10.5, fill: INK3 }));
  });
  rows.forEach((t, i) => {
    const y = T0 + i * rh + rh / 2, o = ords.find(z => z.theme === t.name), b = trs.find(z => z.theme === t.name), g = sv("g", {});
    const aH = o && o.fitted && o.q < .05, bH = b && b.q < .05;
    if (aH || bH) g.append(sv("rect", { x: 0, y: y - rh / 2 + 1, width: W, height: rh - 2, fill: ACCBG, rx: 5 }));
    g.append(sv("rect", { class: "bg", x: 0, y: y - rh / 2 + 1, width: W, height: rh - 2, fill: "transparent", rx: 5 }));
    g.append(sv("circle", { cx: 7, cy: y, r: sub ? 4 : 5, fill: colOf(lv, t) }), wrapLabel(19, y, label(lv, t), Math.floor((L - 30) / ((sub ? 12 : 13.5) * .52)), { "font-size": sub ? 12 : 13.5, fill: INK, "font-weight": aH || bH ? 700 : 400 }));
    const bar = (x0v, xv, lov, hiv, holds, txt) => {
      const c = holds ? colOf(lv, t) : "#BDBDBD", bh = sub ? 10 : 14;
      g.append(sv("rect", { x: Math.min(x0v, xv), y: y - bh / 2, width: Math.abs(xv - x0v), height: bh, fill: c, rx: 2 }));
      g.append(sv("line", { x1: lov, x2: hiv, y1: y, y2: y, stroke: INK, "stroke-width": 1.2 }), sv("line", { x1: lov, x2: lov, y1: y - 4, y2: y + 4, stroke: INK }), sv("line", { x1: hiv, x2: hiv, y1: y - 4, y2: y + 4, stroke: INK }));
      if (holds) g.append(tx(hiv + 4, y - 2, "*", { "font-size": 16, "font-weight": 700, fill: INK }));
      if (!sub) g.append(tx(xv >= x0v ? Math.max(hiv, xv) + (holds ? 14 : 5) : Math.min(lov, xv) - 5, y + 4, txt, { "text-anchor": xv >= x0v ? "start" : "end", "font-size": 11, fill: holds ? INK : INK2, "font-weight": holds ? 700 : 400, class: "n" }));
    };
    if (o && o.fitted) bar(xa(0), xa(Math.log2(o.OR)), xa(Math.log2(o.lo)), xa(Math.log2(o.hi)), aH, "×" + o.OR.toFixed(2));
    else g.append(tx(xa(0), y + 4, "–", { "text-anchor": "middle", fill: INK3 }));
    if (b) bar(xb(0), xb(b.pp_per_step), xb(b.lo), xb(b.hi), bH, (b.pp_per_step > 0 ? "+" : b.pp_per_step < 0 ? "−" : "") + Math.abs(b.pp_per_step).toFixed(1));
    const lines = [];
    if (o && o.fitted) lines.push("A: odds of a higher step ×" + o.OR.toFixed(2) + " per 10 points (95% range " + o.lo.toFixed(2) + " to " + o.hi.toFixed(2) + "), q = " + o.q.toFixed(3) + (aH ? " → holds" : ""));
    if (b) lines.push("B: " + (b.pp_per_step > 0 ? "+" : "") + b.pp_per_step.toFixed(1) + " points per step (95% range " + b.lo.toFixed(1) + " to " + b.hi.toFixed(1) + "), q = " + b.q.toFixed(3) + (bH ? " → holds" : ""));
    hoverable(g, fullName(lv, t), lines);
    svg.append(g);
  });
  return el("div", { class: "figbox" }, [svg]);
}

function stepPanels(key, outcome, steps, stepNames) {
  const tb = R.groups[key].main, idx = steps.map(s => tb.groups.indexOf(s));
  const rows = MAINS.slice().sort((a, b) => b.pct - a.pct), n = rows.length;
  const W = 1184, ML = 42, gap = 18, pw = (W - ML - gap * (n - 1)) / n, T = 60, PH = 150, H = T + PH + 88, y = v => T + PH - v * PH;
  const sg = v => (v > 0 ? "+" : v < 0 ? "−" : "") + Math.abs(v).toFixed(1);
  const svg = sv("svg", { viewBox: "0 0 " + W + " " + H, role: "group", "aria-label": "Share of people who raised each theme at each step of the " + outcome });
  [0, .5, 1].forEach(v => svg.append(tx(ML - 8, y(v) + 4, pc(v), { "text-anchor": "end", "font-size": 10.5, fill: INK3, class: "n" })));
  rows.forEach((t, k) => {
    const j = tb.themes.indexOf(t.name), x0 = ML + k * (pw + gap), g = sv("g", {}), col = colOf("main", t);
    const tr = (R5.trend || []).find(z => z.outcome === outcome && z.level === "main" && z.theme === t.name), od = R5.ordinal.find(z => z.outcome === outcome && z.level === "main" && z.theme === t.name);
    const bH = !!tr && tr.q < .05, aH = !!od && od.fitted && od.q < .05, both = aH && bH, one = aH !== bH, c = both ? col : "#9A9A9A";
    g.append(sv("rect", { class: "bg", x: x0 - 6, y: 0, width: pw + 12, height: H, fill: "transparent", rx: 6 }));
    g.append(sv("circle", { cx: x0 + 6, cy: 12, r: 5, fill: col }));
    const lines = [""]; label("main", t).split(" ").forEach(w => { const cur = lines[lines.length - 1]; if (cur && (cur + " " + w).length > 23) lines.push(w); else lines[lines.length - 1] = (cur + " " + w).trim(); });
    lines.slice(0, 2).forEach((s, i) => g.append(tx(x0 + 17, 16 + i * 14.5, s, { "font-size": 12, "font-weight": 700, fill: INK })));
    [0, .5, 1].forEach(v => g.append(sv("line", { x1: x0, x2: x0 + pw, y1: y(v), y2: y(v), stroke: LINE })));
    const xs = idx.map((_, i) => x0 + pw * (i + .5) / idx.length), ys = idx.map(gi => y(tb.share[gi][j]));
    g.append(sv("polyline", { points: xs.map((x, i) => x.toFixed(1) + "," + ys[i].toFixed(1)).join(" "), fill: "none", stroke: c, "stroke-width": 2 }));
    idx.forEach((gi, i) => {
      const few = tb.teams[gi] < 5;
      g.append(sv("line", { x1: xs[i], x2: xs[i], y1: y(tb.lo[gi][j]), y2: y(tb.hi[gi][j]), stroke: c, "stroke-width": 3, "stroke-opacity": .4 }),
        sv("circle", { cx: xs[i], cy: ys[i], r: 4.5, fill: both ? c : "#ffffff", stroke: c, "stroke-width": 1.8 }),
        tx(xs[i], y(tb.hi[gi][j]) - 6, pc(tb.share[gi][j]), { "text-anchor": "middle", "font-size": 11, "font-weight": 700, fill: INK, class: "n" }),
        tx(xs[i], T + PH + 15, stepNames[i], { "text-anchor": "middle", "font-size": 10, fill: INK2 }),
        tx(xs[i], T + PH + 28, tb.people[gi] + (few ? " · few" : ""), { "text-anchor": "middle", "font-size": 9.5, fill: few ? "#8A4B00" : INK3, class: "n" }));
    });
    if (tr) g.append(tx(x0, T + PH + 52, sg(tr.pp_per_step) + " points per step", { "font-size": 11.5, "font-weight": both || one ? 700 : 400, fill: both || one ? INK : INK2 }),
      tx(x0, T + PH + 67, "95% range " + sg(tr.lo) + " to " + sg(tr.hi), { "font-size": 10.5, fill: INK3 }));
    g.append(tx(x0, T + PH + 82, both ? "holds in both tests" : one ? "a hint: one test of two" : "no clear trend", { "font-size": 10.5, fill: both || one ? INK : INK3, "font-weight": both || one ? 700 : 400 }));
    const tip = idx.map((gi, i) => steps[i] + ": " + pc(tb.share[gi][j]) + " of " + tb.people[gi] + " people (95% range " + pc(tb.lo[gi][j]) + " to " + pc(tb.hi[gi][j]) + ")");
    if (tr) tip.push("Change per step: " + sg(tr.pp_per_step) + " points (95% range " + sg(tr.lo) + " to " + sg(tr.hi) + "), q = " + tr.q.toFixed(3));
    if (od && od.fitted) tip.push("Odds of a higher step when 10 points more of a team raise it: ×" + od.OR.toFixed(2) + " (95% range " + od.lo.toFixed(2) + " to " + od.hi.toFixed(2) + "), q = " + od.q.toFixed(3));
    hoverable(g, fullName("main", t), tip);
    svg.append(g);
  });
  return el("div", { class: "figbox min900" }, [svg]);
}
function renderLadder(m) {
  const box = $(m.box); if (!box) return;
  m.v = m.v || 0; m.lv = m.lv || "main";
  const lvSeg = levelSeg2(m, renderLadder);
  if (m.lv === "main") {
    box.replaceChildren(el("div", { class: "ctlrow" }, [lvSeg]),
      el("h3", { class: "subhead", text: "Award ladder: no award, nominated, special prize" }),
      stepPanels("award_ladder", "award ladder", ["No award", "Nominated", "Special prize"], ["No award", "Nominated", "Special"]),
      el("h3", { class: "subhead", text: "Medal ladder: none, bronze, silver, gold" }),
      stepPanels("medal", "medal ladder", ["None", "Bronze", "Silver", "Gold"], ["None", "Bronze", "Silver", "Gold"]),
      el("p", { class: "fnote", text: "Each panel is one theme; the steps of the ladder go from left to right. Dot = share of the people at that step who raised the theme; pale bar = its 95% range; number under a step = people. A flat line = the theme is raised as often at every step. Grey = no clear trend; colour = the trend holds in both tests. Points per step = change in the share for one step up the ladder." }),
      ...powerLine("medal"));
    return;
  }

  const key = m.views[m.v][0], tb = R.groups[key].sub, medal = key === "medal";
  const order = medal ? ["None", "Bronze", "Silver", "Gold"] : ["No award", "Nominated", "Special prize"], outName = medal ? "medal ladder" : "award ladder";
  const ladSeg = el("div", { class: "seg", role: "group", "aria-label": "Which ladder" }, m.views.map(([k, t], i) => el("button", { type: "button", "aria-pressed": m.v === i, text: t, onclick: () => { m.v = i; renderLadder(m); } })));
  box.replaceChildren(el("div", { class: "ctlrow" }, [ladSeg, lvSeg]),
    el("h3", { class: "subhead", text: "How often is each sub-theme raised at each step of the " + outName + "?" }),
    dotRowTable(tb, order, "sub", { shade: true, ci: true }),
    el("p", { class: "fnote", text: "One block per sub-theme, one line per step (" + order.join(" → ") + "; light = lowest, dark = highest). Dot = share of the step’s people who raised the sub-theme; line = its 95% range." }),
    fold(m.box + "|reg", "Two regressions on the " + outName + ", sub-theme by sub-theme", [ladderAB("sub", outName, outName),
      el("p", { class: "fnote", text: "A: ordinal logistic regression with the ladder step as the outcome (odds of a higher step when 10% more of a team’s people raised the sub-theme, allowing for region, school level and team size). B: change in the share per step up, tested by shuffling the ladder between teams. Coloured bar with * = holds after correction; grey = does not." })]),
    ...powerLine("medal"));
}

function renderResults() {
  const box = $("#results"); if (!box) return;
  const M_ = id => MAINS.find(t => t.id === id), pcI = v => Math.round(v * 100) + "%";
  const ct = R.groups.country.main, jm = ct.themes.indexOf(M_(2).name), cs = g => ct.share[ct.groups.indexOf(g)][jm];
  const fr = R.contrasts.country.find(c => c.name.startsWith("France")), rg = R.groups.region.main, ji = rg.themes.indexOf(M_(1).name);
  const st = R.groups.school.main, sj = st.themes.indexOf(M_(2).name), comb = R5.combined.find(r => r.level === "main" && r.theme === M_(2).name && r.factor === "Undergraduate vs high school");
  const med = R5.ordinal.find(r => r.outcome === "medal ladder" && r.level === "main" && r.theme === M_(6).name), awq = R5.ordinal.filter(r => r.outcome === "award ladder" && r.level === "main" && r.q < .05).length;
  const tq = R5.tone.find(t => t.factor === "question: Conditions"), vil = R.groups.village.main.q.filter(q => q < .05).length;
  const top = MAINS.slice().sort((a, b) => b.pct - a.pct);
  const posQ = Object.values(R.tone_q).map(d => d.pos / (d.neg + d.mix + d.neu + d.pos));
  const nFr = fr.sig.slice(0, 7).filter((s, j) => s && fr.pp[j] < 0).length;
  const S = { facts: ["■", "fact", "a count, no test"], holds: ["●", "holds", "holds after correction"], part: ["◐", "partly", "holds alone, not in every check"], none: ["○", "no", "no difference that holds"] };
  const rows = [
    ["#talk", "What did people talk about?", "Four themes were each raised by 6 to 7 people in 10; " + M_(2).name + " by 1 in 5.", "4 themes, " + pcI(top[3].pct) + " to " + pcI(top[0].pct) + " of people", "facts"],
    ["#talk", "Does the question set the tone?", "Yes: the share of positive answers runs from " + pcI(Math.min(...posQ)) + " (what limited participation) to " + pcI(Math.max(...posQ)) + " (purpose and career); groups add almost nothing.", "Yes: " + pcI(Math.min(...posQ)) + " to " + pcI(Math.max(...posQ)) + " positive", "holds"],
    ["#country", "Does it change by country?", M_(2).name + " differs most: India " + pcI(cs("India")) + ", Canada " + pcI(cs("Canada")) + ", Taiwan and Hong Kong " + pcI(cs("Taiwan")) + ".", "Yes: India " + pcI(cs("India")) + ", Taiwan " + pcI(cs("Taiwan")), "holds"],
    ["#france", "What about France?", "Like the others, except fewer French participants raised " + M_(2).name + " and " + M_(1).name + ".", "Mostly the same, " + nFr + " themes lower", "holds"],
    ["#region", "Does it change by region?", "Asian teams raised " + M_(1).name + " more often; shorter answers explain part of it.", rg.groups[0] + " " + pcI(rg.share[0][ji]) + ", " + rg.groups[1] + " " + pcI(rg.share[1][ji]), "holds"],
    ["#school", "Does it change with school level?", M_(2).name + ": undergraduates far more than high-school students, but not once region is in the same model.", (comb && comb.q < .05 ? "Yes: " : "Partly: ") + pcI(st.share[st.groups.indexOf("Undergraduate")][sj]) + " vs " + pcI(st.share[st.groups.indexOf("High school")][sj]), comb && comb.q < .05 ? "holds" : "part"],
    ["#awards-s", "Does any theme go with winning?", "Award ladder: " + (awq ? awq + " theme(s)" : "no link") + ". Medal ladder: one hint, " + M_(6).name + ".", (med.q < .05 || awq ? "One hint, not firm" : "No link"), med.q < .05 ? "part" : "none"],
  ];
  box.replaceChildren(el("ul", { class: "qlist" }, rows.map(r => el("li", { title: r[2] }, [el("a", { href: r[0], text: r[1] }), el("b", { text: r[3] })]))),
    el("p", { class: "fnote", text: "Click a question to open its section; point at it for the short answer." }));
}

const FS = { lv: "main" };
function renderFrance() {
  const box = $("#france-fig"); if (!box || !R.france) return;
  const lv = FS.lv, c = R.contrasts.country.find(k => k.name.startsWith("France")), F = R.france, sfx = lv === "sub" ? "_sub" : "";
  const names = lv === "sub" ? R.contrasts.rows_sub : R.contrasts.rows, tone = names.length - 1;
  const tb = R.groups.country[lv], gi = tb.groups.indexOf("France");
  const seg = el("div", { class: "seg", role: "group", "aria-label": "Theme level" }, [["main", "7 themes"], ["sub", R.meta.n_sub_tested + " sub-themes"]].map(([v, t]) =>
    el("button", { type: "button", "aria-pressed": FS.lv === v, text: t, onclick: () => { FS.lv = v; renderFrance(); } })));
  const schK = ["High school", "Undergraduate", "Graduate"].filter(k => F.school[k]), sch = schK.map(k => F.school[k]).join(" + "), schL = schK.map(k => k.toLowerCase()).join(" + ") + " teams";
  const facts = el("div", { class: "frfacts" }, [[F.teams, "teams"], [F.people_answered, "people answered"], [F.answers, "answers"], [sch, schL],
    [F.median_words + " words", "median answer (others: " + F.median_words_rest + ")"], [(F.medal.Gold || 0) + " of " + F.teams, "teams with gold"]].map(([b, t]) => el("div", {}, [el("b", { text: String(b) }), el("span", { text: t })])));
  const rows = names.map((name, j) => ({ j, name, t: j === tone ? null : BYNAME[lv + "|" + name] })).filter(r => r.t || r.j === tone)
    .sort((a, b) => (a.j === tone) - (b.j === tone) || (b.t ? b.t.pct : 0) - (a.t ? a.t.pct : 0));
  const W = 1000, Lw = 320, rh = lv === "sub" ? 22 : 34, T0 = 34, H = T0 + rows.length * rh + 26, xmax = lv === "sub" ? .5 : 1, Rw = 120;
  const sx = v => Lw + (W - Lw - Rw) * Math.min(v, xmax) / xmax;
  const svg = sv("svg", { viewBox: "0 0 " + W + " " + H, role: "group", "aria-label": "France compared with all other teams, for each theme" });
  svg.style.maxWidth = Math.round(W * 1.1) + "px";
  svg.append(tx(W - Rw + 14, 16, "France minus others", { "font-size": 11.5, fill: INK3 }));
  [0, .25, .5, .75, 1].filter(t => t <= xmax + 1e-9).forEach(t => svg.append(sv("line", { x1: sx(t), x2: sx(t), y1: T0 - 6, y2: H - 22, stroke: "#EFEEEC" }), tx(sx(t), H - 6, Math.round(t * 100) + "%", { "text-anchor": "middle", "font-size": 11, fill: INK3, class: "n" })));
  const FR = "#1F4E9E";
  rows.forEach((r, i) => {
    const yy = T0 + i * rh + rh / 2, a = c["a_pct" + sfx][r.j] / 100, b = c["b_pct" + sfx][r.j] / 100, d = c["pp" + sfx][r.j], sig = c["sig" + sfx][r.j];
    const col = r.t ? colOf(lv, r.t) : POS, g = sv("g", {});
    if (r.j === tone) svg.append(sv("line", { x1: 0, x2: W, y1: yy - rh / 2, y2: yy - rh / 2, stroke: LINE }));
    g.append(sv("rect", { class: "bg", x: 0, y: yy - rh / 2 + 1, width: W, height: rh - 2, fill: "transparent", rx: 4 }));
    g.append(sv("circle", { cx: 7, cy: yy, r: lv === "sub" ? 4 : 5, fill: col }));
    const nm = r.t ? label(lv, r.t) : "Positive tone of answers", room = Math.floor((Lw - 26) / ((lv === "sub" ? 12 : 13.5) * .52));
    g.append(tx(19, yy + 4.5, nm.length > room ? nm.slice(0, room - 1) + "…" : nm, { "font-size": lv === "sub" ? 12 : 13.5, fill: INK, "font-weight": sig ? 700 : 400 }));
    if (r.t) { const k = tb.themes.indexOf(r.name); if (k >= 0) g.append(sv("line", { x1: sx(tb.lo[gi][k]), x2: sx(tb.hi[gi][k]), y1: yy, y2: yy, stroke: FR, "stroke-width": 1.6, opacity: .35 })); }
    g.append(sv("line", { x1: sx(Math.min(a, b)), x2: sx(Math.max(a, b)), y1: yy, y2: yy, stroke: sig ? FR : "#B8B3AD", "stroke-width": sig ? 3.5 : 2.2 }));
    g.append(sv("circle", { cx: sx(b), cy: yy, r: lv === "sub" ? 4 : 5.5, fill: "#fff", stroke: "#736C66", "stroke-width": 2 }));
    g.append(sv("circle", { cx: sx(a), cy: yy, r: lv === "sub" ? 4.5 : 6.5, fill: FR }));
    g.append(tx(W - Rw + 14, yy + 4.5, (d > 0 ? "+" : d < 0 ? "−" : "") + Math.abs(d).toFixed(0) + " points", { "font-size": lv === "sub" ? 11.5 : 13, fill: sig ? FR : INK3, "font-weight": sig ? 700 : 400, class: "n" }));
    hoverable(g, (r.t ? fullName(lv, r.t) : "Positive tone of answers"), ["France: " + Math.round(a * 100) + "% of " + c.a_people + " people (" + F.teams + " teams)", "All other teams: " + Math.round(b * 100) + "% of " + c.b_people + " people",
      "Difference " + (d > 0 ? "+" : "") + d.toFixed(1) + " points (95% range " + c["lo" + sfx][r.j].toFixed(1) + " to " + c["hi" + sfx][r.j].toFixed(1) + ")", sig ? "Holds after correction" : "Does not hold after correction"]);
    svg.append(g);
  });
  const nmain = R.contrasts.rows.length - 1, within = R.contrasts.rows.slice(0, nmain).filter((_, j) => Math.max(Math.abs(c.lo[j]), Math.abs(c.hi[j])) < 20).length;
  const leg = el("div", { class: "legend4" }, []); leg.innerHTML = '<span><svg width="14" height="14" aria-hidden="true"><circle cx="7" cy="7" r="6" fill="' + FR + '"/></svg> France</span><span><svg width="14" height="14" aria-hidden="true"><circle cx="7" cy="7" r="5" fill="#fff" stroke="#736C66" stroke-width="2"/></svg> all other teams</span><span><svg width="26" height="10" aria-hidden="true"><line x1="1" y1="5" x2="25" y2="5" stroke="' + FR + '" stroke-width="1.6" opacity=".35"/></svg> 95% range for France</span>';
  box.replaceChildren(facts, el("div", { class: "ctlrow" }, [seg]), leg, el("div", { class: "figbox" }, [svg]),
    el("p", { class: "fnote", text: "Share of people (with a themed answer) who raised each theme: France (" + c.a_people + " people) against all other teams (" + c.b_people + "). Blue line and bold = the difference holds after correction. For " + within + " of the " + nmain + " main themes, the 95% range of the difference rules out a gap larger than 20 points." }));
}

function dotRows(rows, o) {
  o = Object.assign({ W: 380, L: 108, rh: 26, hl: new Set(), xmax: 1 }, o || {});
  const sx = v => o.L + (o.W - o.L - 60) * Math.min(v, o.xmax) / o.xmax, H = 20 + rows.length * o.rh;
  const svg = sv("svg", { viewBox: "0 0 " + o.W + " " + H, "aria-hidden": "true" });
  [0, .5, 1].filter(t => t <= o.xmax).forEach(t => svg.append(sv("line", { x1: sx(t), x2: sx(t), y1: 12, y2: H - 2, stroke: LINE }), tx(sx(t), 9, pc(t), { "font-size": 10.5, fill: INK3, "text-anchor": "middle", class: "n" })));
  rows.forEach((r, i) => {
    const y = 24 + i * o.rh, c = o.col || (o.hl.has(r.name) ? ACC : INK);
    svg.append(tx(o.L - 8, y + 4.5, r.name, { "font-size": 12.5, fill: INK, "text-anchor": "end" }));
    if (r.lo != null) svg.append(sv("line", { x1: sx(r.lo), x2: sx(r.hi), y1: y, y2: y, stroke: c, "stroke-width": 1.6, opacity: .55 }));
    svg.append(sv("circle", { cx: sx(r.v), cy: y, r: 4.8, fill: c }), tx(sx(r.hi != null ? Math.max(r.hi, r.v) : r.v) + 7, y + 4.5, pc(r.v), { "font-size": 12, fill: c, "font-weight": 700, class: "n" }));
  });
  return svg;
}
function miniMap(W, H) {
  const A = DD.points, sp = {}; SUBS.forEach(s => { sp[s.id] = s.parent; });
  const q = (v, p) => v.slice().sort((a, b) => a - b)[Math.floor(p * (v.length - 1))];
  const x0 = q(A.x, .01), x1 = q(A.x, .99), y0 = q(A.y, .01), y1 = q(A.y, .99), k = Math.min((W - 16) / (x1 - x0), (H - 16) / (y1 - y0));
  const ox = (W - k * (x1 - x0)) / 2, oy = (H - k * (y1 - y0)) / 2, svg = sv("svg", { viewBox: "0 0 " + W + " " + H, "aria-hidden": "true" });
  const idx = A.x.map((_, i) => i).sort((a, b) => (A.sw[a] >= 0) - (A.sw[b] >= 0));
  idx.forEach(i => { const x = A.x[i], y = A.y[i]; if (x < x0 || x > x1 || y < y0 || y > y1) return; const s = A.sw[i];
    svg.append(sv("circle", { cx: (ox + k * (x - x0)).toFixed(1), cy: (oy + k * (y1 - y)).toFixed(1), r: 1.9, fill: s >= 0 ? COL[sp[s]] : "#D6D3D1", opacity: .85 })); });
  return svg;
}
function questionBars() {

  const W = 380, L = 0, rh = 40, svg = sv("svg", { viewBox: "0 0 " + W + " " + (DD.questions.length * rh + 4), "aria-hidden": "true" });
  DD.questions.forEach((q, i) => {
    const y = i * rh, d = R.tone_q[q.q], n = d.neg + d.mix + d.neu + d.pos, bw = W - 60;
    svg.append(tx(L, y + 13, q.text, { "font-size": 12.5, fill: INK }));
    let x = L; [[d.neg, NEG], [d.mix + d.neu, MID], [d.pos, POS]].forEach(([k, c]) => { svg.append(sv("rect", { x, y: y + 19, width: bw * k / n, height: 10, fill: c })); x += bw * k / n; });
    svg.append(tx(W, y + 28, q.n + " answers", { "font-size": 11, fill: INK3, "text-anchor": "end", class: "n" }));
  });
  return svg;
}
function renderGlance() {
  const box = $("#glance"); if (!box) return;
  const card = (href, q, h, ans, vis, wide) => el("a", { class: "gcard" + (wide ? " w2" : ""), href }, [el("p", { class: "q", text: q }), el("h3", { text: h }), vis, el("p", { class: "go", text: "Open this section →" })]);
  const M = MAINS.slice().sort((a, b) => b.pct - a.pct), money = MAINS.find(t => t.id === 2);
  const ct = R.groups.country.main, jm = ct.themes.indexOf(money.name);
  const crow = ct.groups.map((g, c) => ({ name: g, v: ct.share[c][jm], lo: ct.lo[c][jm], hi: ct.hi[c][jm] })).filter(r => r.name !== "Other countries").sort((a, b) => b.v - a.v);
  const st = R.groups.school.main, bonds = MAINS.find(t => t.id === 5), jb = st.themes.indexOf(bonds.name);
  const srow = st.groups.map((g, c) => ({ name: g, v: st.share[c][jm], lo: st.lo[c][jm], hi: st.hi[c][jm] }));
  const rg = R.groups.region.main, insp = MAINS.find(t => t.id === 1), ji = rg.themes.indexOf(insp.name);
  const rrow = rg.groups.slice(0, 3).map((g, c) => ({ name: g, v: rg.share[c][ji], lo: rg.lo[c][ji], hi: rg.hi[c][ji] }));
  const s = c => st.share[st.groups.indexOf(c)];
  const award = ["medal", "special", "nominated"].reduce((a, k) => a + R.groups[k].main.q.filter(q => q < .05).length, 0);
  const lims = el("ul", {}, [["A language model named the themes and read the tone.", " No person has checked a sample yet."], ["Topics follow the questions.", " 98% of money answers answer the question on conditions."], ["193 answers (13%) have no theme.", " Mostly very short or mixed answers."], ["People chose to answer.", " 332 people from 125 teams, not all of iGEM."]].map(([b, t]) => el("li", {}, [el("b", { text: b }), document.createTextNode(t)])));
  box.replaceChildren(
    card("#talk", "Themes and tone", "What did people talk about, and how did it feel?", "Four topics were each raised by 6 to 7 people in 10. Money and time were the hard parts.", el("div", {}, [legend4(), barsSVG(M.map(t => ({ t })), "main", { W: 820, L: 300, rh: 31, bh: 17, ci: false, click: false, fs: 13.5 })]), true),
    card("#map", "Map", "Where do the answers sit?", "Answers that say similar things sit close together. The full map turns in 3-D.", miniMap(380, 250)),
    card("#country", "Country", "Does it change by country?", "Money does: " + pc(crow[0].v) + " of people in " + crow[0].name + " teams raised it, none in " + crow.filter(r => r.v === 0).map(r => r.name).join(" or ") + ".", dotRows(crow, { L: 96, rh: 22, col: P.ink(COL[money.id]) })),
    card("#school", "School level", "Does it change with school level?", "Undergraduates raise money " + R.contrasts.school[0].pp[2].toFixed(0) + " points more often than high-school students, and team bonds " + Math.abs(R.contrasts.school[0].pp[5]).toFixed(0) + " points less often. Tone: the same.", mini(R.contrasts.school[0])),
    card("#region", "Region", "Does it change by region?", "Asia is " + R.contrasts.region[0].pp[1].toFixed(0) + " points higher on “inspiring but hard”. Shorter answers explain part of it, not all. Nothing else holds.", mini(R.contrasts.region[0])),
    card("#awards-s", "Awards", "Does any theme go with winning?", "Not on the award ladder. On the medal ladder, one: confidence and career (\u00d7" + R5.ordinal.find(r => r.outcome === "medal ladder" && r.level === "main" && r.theme === "Increased Confidence and Career Clarity").OR.toFixed(2) + " per 10 points).", miniLadder()),
    card("#talk-flow", "Questions", "Where do the topics come from?", "", flowSVG({ W: 380, H: 240, labels: false, padL: 6, padR: 6, gap: 5, nodeW: 8 }))
  );
  function miniLadder() {
    const get = key => R5.ordinal.find(r => r.outcome === "medal ladder" && r.level === "main" && r.theme === key);
    const rows = themeRows("main");
    return el("div", {}, [el("p", { class: "fnote", style: "margin:0 0 4px", text: "Medal ladder \u00b7 odds ratio per 10 points" }), orForestSVG([{ title: "", get }], rows, { W: 400, L: 170, rh: 30, fs: 11.5, head: false, maxR: 1 })]);
  }
  function mini(c) { return el("div", {}, [el("p", { class: "fnote", style: "margin:0 0 4px", text: c.name + " · difference in percentage points" }), forestSVG([c], { W: 400, L: 170, rh: 30, fs: 11.5, head: false, compact: true })]); }
}

function sideNav() {
  const links = [...document.querySelectorAll("nav.side a")]; if (!links.length || !("IntersectionObserver" in window)) return;
  const io = new IntersectionObserver(es => es.forEach(e => { if (e.isIntersecting) links.forEach(a => a.classList.toggle("on", a.getAttribute("href") === "#" + e.target.id)); }), { rootMargin: "-30% 0px -60% 0px" });
  links.forEach(a => { const s = document.querySelector(a.getAttribute("href")); if (s) io.observe(s); });
}
})();
