(function () {
"use strict";
const $ = (s, r) => (r || document).querySelector(s);
const el = (tag, attrs, kids) => {
  const e = document.createElement(tag);
  for (const k in (attrs || {})) {
    if (k === "text") e.textContent = attrs[k];
    else if (k.startsWith("on")) e.addEventListener(k.slice(2), attrs[k]);
    else if (attrs[k] !== false && attrs[k] != null) e.setAttribute(k, attrs[k] === true ? "" : attrs[k]);
  }
  (kids || []).forEach(c => e.append(c && c.nodeType ? c : document.createTextNode(c == null ? "" : c)));
  return e;
};
const NS = "http://www.w3.org/2000/svg";
const svgEl = (tag, a) => { const e = document.createElementNS(NS, tag); for (const k in a) e.setAttribute(k, a[k]); return e; };
const txt = (x, y, s, a) => { const e = svgEl("text", Object.assign({ x, y }, a || {})); e.textContent = s; return e; };
const tip = (node, s) => { const t = svgEl("title", {}); t.textContent = s; node.append(t); return node; };
const fmt = n => n.toLocaleString("en-US"), pct = (v, d) => (v * 100).toFixed(d == null ? 0 : d) + "%";
const sg = (v, d) => (v > 0 ? "+" : v < 0 ? "−" : "") + Math.abs(v).toFixed(d == null ? 2 : d);
const P = window.PAL;
const TONE = ["strongly negative", "negative", "mixed", "neutral", "positive", "strongly positive"];
const STAB = { claimable: ["stable", "Jaccard 0.75 or more over 25 refits"], pattern: ["a pattern", "Jaccard 0.60 to 0.75 over 25 refits"], provisional: ["provisional", "Jaccard under 0.60 over 25 refits"] };
const USE = { CLAIMABLE: "can carry a finding", DESCRIPTIVE: "describe only", ARTIFACT: "artifact of the method" };
function reason(r) {
  if (!r) return "";
  let m = r.match(/under-supported: (\d+) participants/); if (m) return "Voiced by only " + m[1] + " participants (the rule asks for 15).";
  m = r.match(/Jaccard ([\d.]+) < 0\.60/); if (m) return "Unstable: it came back with a Jaccard of only " + m[1] + " over 25 refits.";
  if (/judge rejected/.test(r)) return "Its name was rejected by a separate check.";
  if (/not grounded/.test(r)) return "Its name was not supported by the answers it was built from.";
  return r;
}

let D, A, MAINS, SUBS, COL = {}, SUBC = {}, ORDER, MAP = null;
const S = { level: "main", sel: null, ans: -1, place: "wide", rq: -1, rs: "", rn: 25, mode: "3d", al: "main", cmp: "region" };

(window.IGEM_DATA ? Promise.resolve(window.IGEM_DATA) : fetch("data/igem/igem-data.json").then(r => { if (!r.ok) throw new Error(r.status); return r.json(); })).then(init).catch(e => {
  document.querySelectorAll(".needs-data").forEach(n => n.replaceChildren(el("p", { class: "loading", role: "alert", text: "The data file could not be loaded (" + e.message + ")." })));
});

function init(d) {
  D = d; A = d.points;
  MAINS = D.themes.filter(t => t.level === "main").sort((a, b) => a.id - b.id);
  SUBS = D.themes.filter(t => t.level === "sub").sort((a, b) => a.id - b.id);
  ORDER = MAINS.slice().sort((a, b) => b.n_wide - a.n_wide);
  ORDER.forEach((m, k) => { COL[m.id] = P.CAT[k]; });
  MAINS.forEach(m => kidsOf(m).forEach((s, k) => { SUBC[s.id] = P.child(COL[m.id], k); }));
  readHash();
  buildMap();
  window.addEventListener("hashchange", () => { if (!/=/.test(location.hash)) return; readHash(); render(); });
  render();
  if (document.fonts && document.fonts.load) document.fonts.load("600 14px 'Atkinson Next'").then(() => MAP && MAP.draw()).catch(() => {});
}
const kidsOf = m => SUBS.filter(s => s.parent === m.id).sort((a, b) => b.n_wide - a.n_wide);
const theme = (lv, id) => (lv === "main" ? MAINS : SUBS)[id];
const colour = (lv, id) => id < 0 ? P.NONE : lv === "main" ? COL[id] : SUBC[id];
const subOf = i => S.place === "wide" ? A.sw[i] : A.s[i];
const mainOf = i => { const s = subOf(i); return s < 0 ? -1 : SUBS[s].parent; };
const groupOf = i => S.level === "main" ? mainOf(i) : subOf(i);
const nOf = t => S.place === "wide" ? t.n_wide : t.n_core;
const inTheme = (i, lv, id) => lv === "main" ? mainOf(i) === id : subOf(i) === id;

function writeHash() {
  const p = [];
  if (S.level !== "main") p.push("level=sub");
  if (S.sel != null) p.push("theme=" + S.sel);
  if (S.ans >= 0) p.push("answer=" + S.ans);
  if (S.place !== "wide") p.push("place=hdbscan");
  const h = p.length ? "#" + p.join("&") : "";
  if (!p.length && location.hash && !/=/.test(location.hash)) return;
  if (location.hash !== h) history.replaceState(null, "", location.pathname + location.search + h);
}
function readHash() {
  const p = new URLSearchParams(location.hash.slice(1));
  S.level = p.get("level") === "sub" ? "sub" : "main";
  const t = p.get("theme"); S.sel = t != null && /^\d+$/.test(t) && theme(S.level, +t) ? +t : null;
  const a = p.get("answer"); S.ans = a != null && /^\d+$/.test(a) && +a < A.a.length ? +a : -1;
  S.place = p.get("place") === "hdbscan" ? "core" : "wide";
}
function selectTheme(lv, id) { S.level = lv; S.sel = id; S.rn = 25; render(); }
function selectAnswer(i, scroll) {
  S.ans = i; if (MAP) MAP.select(i); renderMapCard(); writeHash();
  if (scroll) { const f = $("#fig-map"); if (f) f.scrollIntoView({ behavior: "smooth", block: "start" }); }
}
function render() {
  if (MAP) { MAP.select(S.ans); MAP.draw(); }
  renderMapControls(); renderMapCard(); renderThemes(); renderReader(); renderTone(); renderWho(); renderModel(); renderAwards();
  writeHash();
}

function centre(lv, id) {
  const xs = [], ys = [], zs = [], x2 = [], y2 = [];
  for (let i = 0; i < A.x.length; i++) if (inTheme(i, lv, id)) { xs.push(A.x3[i]); ys.push(A.y3[i]); zs.push(A.z3[i]); x2.push(A.x[i]); y2.push(A.y[i]); }
  const med = a => { const s = a.slice().sort((p, q) => p - q); return s[Math.floor(s.length / 2)]; };
  return xs.length ? { x3: med(xs), y3: med(ys), z3: med(zs), x2: med(x2), y2: med(y2) } : null;
}
function buildMap() {
  const box = $("#map3d"); if (!box) return;
  box.replaceChildren();
  MAP = window.Map3D(box, {
    x3: A.x3, y3: A.y3, z3: A.z3, x2: A.x, y2: A.y, mode: S.mode,
    ariaLabel: "Map of the 1,505 answers in three dimensions. Each dot is one answer; answers that say similar things sit close together. Drag to turn the map.",
    color: i => colour(S.level, groupOf(i)),
    active: i => S.sel == null || groupOf(i) === S.sel,
    anyActive: () => S.sel != null,
    light: c => P.lum(c) > .6, ink: c => P.ink(c),
    group: i => groupOf(i),
    labels: () => {
      const list = S.sel != null && S.level === "sub" ? [theme("sub", S.sel)] : S.level === "main" ? ORDER.filter(m => S.sel == null || m.id === S.sel) : SUBS.filter(s => s.named && s.n_wide >= 25);
      return list.map(t => { const c = centre(t.level, t.id); return c && Object.assign(c, { id: t.id, text: t.named ? t.name : "label withheld", color: P.ink(colour(t.level, t.id), "#ffffff"), small: t.level === "sub" }); }).filter(Boolean);
    },
    onHover: hover, onClick: i => { if (i >= 0) selectAnswer(i); }
  });
  if (S.ans >= 0) MAP.select(S.ans);
}
function hover(i, e) {
  const tp = $("#tip"); if (!tp) return;
  if (i < 0 || !e) { tp.style.opacity = 0; return; }
  const g = groupOf(i), t = g >= 0 ? theme(S.level, g) : null, s = A.a[i];
  tp.replaceChildren(el("b", { text: t ? t.name : "No theme" }), el("span", { text: "“" + (s.length > 140 ? s.slice(0, 137) + "…" : s) + "”" }));
  tp.style.left = Math.min(innerWidth - 336, e.clientX + 14) + "px"; tp.style.top = (e.clientY + 16) + "px"; tp.style.opacity = 1;
}
function renderMapControls() {
  const c = $("#map-controls"); if (!c) return;
  const seg = (label, items, cur, f) => el("div", { class: "seg", role: "group", "aria-label": label }, items.map(([v, t]) => el("button", { type: "button", "aria-pressed": cur === v, text: t, onclick: () => f(v) })));
  c.replaceChildren(
    seg("View", [["3d", "3-D"], ["2d", "Flat"]], S.mode, v => { S.mode = v; MAP.setMode(v); renderMapControls(); }),
    seg("Colour by", [["main", "Main themes"], ["sub", "Sub-themes"]], S.level, v => { S.level = v; S.sel = null; render(); }),
    S.sel != null ? el("button", { type: "button", class: "lk", text: "Show all themes", onclick: () => selectTheme(S.level, null) }) : "");
}
function quote(i, opts) {
  const o = opts || {}, s = A.a[i], sub = subOf(i), m = mainOf(i);
  const meta = [D.questions[A.q[i]].q, sub >= 0 ? theme("sub", sub).name : "no theme", A.sl[i] >= 0 ? "tone: " + TONE[A.sl[i]] : "tone not scored"];
  let body = s;
  if (o.short && s.length > o.short) body = s.slice(0, o.short - 1) + "…";
  const bq = el("blockquote", { class: "ans" + (o.small ? " small" : ""), lang: "" });
  const p = el("p");
  if (o.mark) { const rx = new RegExp("(" + o.mark.replace(/[.*+?^${}()|[\]\\]/g, "\\$&") + ")", "ig"); body.split(rx).forEach((part, k) => p.append(k % 2 ? el("mark", { text: part }) : part)); }
  else p.textContent = body;
  bq.append(el("i", { class: "sw", style: "background:" + colour("main", m), "aria-hidden": "true" }), p, el("footer", { text: meta.join(" · ") }));
  if (o.onClick) { bq.classList.add("clk"); bq.tabIndex = 0; bq.setAttribute("role", "button"); bq.addEventListener("click", o.onClick); bq.addEventListener("keydown", e => { if (e.key === "Enter" || e.key === " ") { e.preventDefault(); o.onClick(); } }); }
  return bq;
}
function renderMapCard() {
  const c = $("#map-card"); if (!c) return;
  c.replaceChildren();
  if (S.ans < 0) {
    if (S.sel != null) { themeSummary(c, theme(S.level, S.sel)); return; }
    c.append(el("h3", { text: "Click a dot" }),
      el("p", { text: "Each dot is one answer. Click one to read it here, with the five answers whose meaning is closest to it." }),
      el("p", { class: "small", text: "Grey dots are answers without a theme. Drag to turn the map; hold Shift to move it." }));
    const item = t => el("button", { type: "button", class: "lg-item", onclick: () => selectTheme(t.level, t.id) }, [el("i", { style: "background:" + colour(t.level, t.id) }), document.createTextNode(t.named ? t.name : "Label withheld"), el("small", { text: " " + fmt(nOf(t)) })]);
    const lg = el("div", { class: "lg-list" }, [el("h4", { text: S.level === "main" ? "The 7 themes (click one)" : "The 39 sub-themes (click one)" })]);
    if (S.level === "main") ORDER.forEach(m => lg.append(item(m)));
    else ORDER.forEach(m => { lg.append(el("p", { class: "lg-head", style: "color:" + P.ink(colour("main", m.id)), text: m.name })); kidsOf(m).forEach(s => lg.append(item(s))); });
    c.append(lg);
    return;
  }
  const i = S.ans, q = D.questions[A.q[i]];

  const sb = subOf(i), mn = mainOf(i), tMain = mn >= 0 ? theme("main", mn) : null, tSub = sb >= 0 ? theme("sub", sb) : null;
  if (tMain) {
    const tt = tSub && tSub.named ? tSub : tMain, col = colour(tt.level, tt.id), sm = tt.summary_kind === "summary" ? tt : tMain.summary_kind === "summary" ? tMain : null;
    c.append(el("p", { class: "qline", text: tt.level === "sub" ? "Sub-theme of “" + tMain.name + "”" : "Main theme" }),
      el("h3", {}, [el("button", { type: "button", class: "tlink", style: "color:" + P.ink(col), title: "Show this theme on the map", text: tt.name, onclick: () => selectTheme(tt.level, tt.id) })]));
    if (sm) c.append(el("p", { class: "msum" }, [el("span", { class: "msumk", text: sm === tt ? "Machine summary" : "Machine summary of the main theme" }), document.createTextNode(sm.summary)]));
    else c.append(el("p", { class: "small", text: "No machine summary is shown for this theme: its wording was not found in the answers." }));
    c.append(el("h4", { text: "The answer you clicked" }));
  } else c.append(el("p", { class: "small", text: "This answer has no theme." }));
  c.append(el("p", { class: "qline", text: q.text }), quote(i), );
  if (A.t[i] === 1 || A.t[i] === 2) c.append(el("p", { class: "small", text: "This answer was given to its nearest theme after the grouping (see note 2)." }));
  c.append(el("h4", { text: "Closest in meaning" }), el("div", { class: "nnlist" }, A.nn[i].map(j => quote(j, { small: true, short: 150, onClick: () => selectAnswer(j) }))));
  c.append(el("button", { type: "button", class: "lk", text: "Close", onclick: () => selectAnswer(-1) }));
}
function themeSummary(c, t) {
  const col = colour(t.level, t.id), parent = t.level === "sub" ? theme("main", t.parent) : null;
  c.append(el("p", { class: "qline", text: t.level === "main" ? "Main theme" : "Sub-theme of “" + parent.name + "”" }), el("h3", { style: "color:" + P.ink(col), text: t.name }));
  c.append(el("p", {}, [el("b", { text: fmt(nOf(t)) }), " answers from ", el("b", { text: fmt(t.n_part) }), " participants (" + pct(t.rate) + " of all) in " + fmt(t.n_teams) + " teams."]));

  if (t.summary_kind === "summary") c.append(el("p", { class: "msum" }, [el("span", { class: "msumk", text: "Machine summary" }), document.createTextNode(t.summary)]));
  else if (t.summary_kind === "withheld") c.append(el("p", { class: "small", text: "No summary is shown: the model’s wording was not found in the answers it was given" + (t.summary_terms ? ". Most typical words: " + t.summary_terms + "." : ".") }));
  if (!t.named) c.append(el("p", { class: "warn", text: "The proposed name failed a check, so it is not printed. " + reason(t.tier_reason) }));
  else if (t.tier !== "CLAIMABLE") c.append(el("p", { class: "warn", text: "Describe only. " + reason(t.tier_reason) }));
  if (t.instrument_bound) c.append(el("p", { class: "small", text: pct(t.top_q_share) + " of its answers answer the question “" + t.top_q + "”." }));
  const ids = []; for (let i = 0; i < A.a.length; i++) if (inTheme(i, t.level, t.id)) ids.push(i);
  const pick = ids.filter((_, k) => k % Math.max(1, Math.floor(ids.length / 3)) === 0).slice(0, 3);
  c.append(el("h4", { text: "Three of its answers" }), el("div", { class: "nnlist" }, pick.map(j => quote(j, { small: true, short: 160, onClick: () => selectAnswer(j) }))));
  c.append(el("a", { class: "lk", href: "#reader-box", text: "Read all " + fmt(ids.length) + " →", onclick: () => { const b = $("#reader-box"); if (b) b.open = true; } }));
}

function placeSwitch() {
  return el("div", { class: "seg", role: "group", "aria-label": "Which answers count" }, [
    ["wide", "After the nearest-theme step (" + fmt(D.header.answers - D.header.no_theme_wide) + ")"], ["core", "Placed by HDBSCAN only (" + fmt(D.header.core) + ")"]].map(a => el("button", { type: "button", "aria-pressed": S.place === a[0], text: a[1], onclick: () => { S.place = a[0]; render(); } })));
}
const tags = t => {
  const out = [];
  if (!t.named) out.push(el("span", { class: "tag", text: "label withheld" }));
  if (t.stability_tier !== "claimable") out.push(el("span", { class: "tag", text: STAB[t.stability_tier][0], title: STAB[t.stability_tier][1] }));
  if (t.tier !== "CLAIMABLE") out.push(el("span", { class: "tag", text: USE[t.tier], title: reason(t.tier_reason) }));
  if (t.instrument_bound) out.push(el("span", { class: "tagx", text: "mostly “" + t.top_q + "”", title: pct(t.top_q_share) + " of its answers come from this question" }));
  return out;
};
function rateBar(t, col) {
  const w = 150;
  return el("span", { class: "ci", title: t.n_part + " of " + D.header.participants + " participants (" + pct(t.rate, 1) + "), 95% interval " + pct(t.lo, 1) + " to " + pct(t.hi, 1) }, [
    el("span", { class: "citrack", style: "width:" + w + "px" }, [el("i", { style: "left:" + (t.lo * 100) + "%;width:" + ((t.hi - t.lo) * 100) + "%;background:" + col }), el("b", { style: "left:" + (t.rate * 100) + "%;background:" + P.ink(col) })]),
    el("span", { class: "num", text: pct(t.rate) })]);
}
function renderThemes() {
  const p = $("#themes"); if (!p) return;
  p.replaceChildren(el("div", { class: "rsel" }, [placeSwitch()]));
  const list = el("div", { class: "hlist" });
  ORDER.forEach(m => {
    const col = COL[m.id];
    const box = el("section", { class: "hm" + (S.level === "main" && S.sel === m.id ? " on" : "") });
    box.append(el("button", { type: "button", class: "hmh", onclick: () => selectTheme("main", m.id) }, [
      el("i", { style: "background:" + col }), el("span", { class: "nm", text: m.name }), el("span", { class: "num small", text: fmt(nOf(m)) + " answers" }), rateBar(m, col), el("span", { class: "tg" }, tags(m))]));
    if (m.summary_kind === "summary") box.append(el("p", { class: "msum inlist", text: m.summary }));
    box.append(el("ul", {}, kidsOf(m).map(s => el("li", {}, [el("button", { type: "button", class: "hs" + (S.level === "sub" && S.sel === s.id ? " on" : ""), title: s.summary_kind === "summary" ? "Machine summary: " + s.summary : null, onclick: () => selectTheme("sub", s.id) }, [
      el("i", { style: "background:" + SUBC[s.id] }), el("span", { class: "nm" + (s.named ? "" : " muted"), text: s.name }), el("span", { class: "num small", text: fmt(nOf(s)) }), rateBar(s, SUBC[s.id]), el("span", { class: "tg" }, tags(s))])]))));
    list.append(box);
  });
  const none = S.place === "wide" ? D.header.no_theme_wide : D.header.no_theme_core;
  list.append(el("p", { class: "small" }, [el("i", { class: "sq", style: "background:" + P.NONE }), " No theme: " + fmt(none) + " answers."]));
  p.append(list);
}

function renderReader() {
  const p = $("#reader"); if (!p) return;
  const keep = document.activeElement && document.activeElement.id === "rq-search";
  p.replaceChildren();
  const sel = el("select", { id: "rq-theme", "aria-label": "Theme" });
  sel.append(el("option", { value: "all", text: "All answers (" + fmt(A.a.length) + ")" }));
  ORDER.forEach(m => {
    const og = el("optgroup", { label: m.name });
    og.append(el("option", { value: "main:" + m.id, text: m.name + " — all (" + fmt(nOf(m)) + ")" }));
    kidsOf(m).forEach(s => og.append(el("option", { value: "sub:" + s.id, text: s.name + " (" + fmt(nOf(s)) + ")" })));
    sel.append(og);
  });
  sel.append(el("option", { value: "none", text: "No theme (" + fmt(S.place === "wide" ? D.header.no_theme_wide : D.header.no_theme_core) + ")" }));
  sel.value = S.sel == null ? (S.noneOnly ? "none" : "all") : S.level + ":" + S.sel;
  sel.addEventListener("change", () => { const v = sel.value; S.noneOnly = v === "none"; if (v === "all" || v === "none") { S.sel = null; } else { const [lv, id] = v.split(":"); S.level = lv; S.sel = +id; } S.rn = 25; render(); });
  const qs = el("select", { "aria-label": "Question" }, [el("option", { value: -1, text: "All five questions" }), ...D.questions.map((q, k) => el("option", { value: k, text: q.q }))]);
  qs.value = S.rq; qs.addEventListener("change", () => { S.rq = +qs.value; S.rn = 25; renderReader(); });
  const se = el("input", { id: "rq-search", type: "search", placeholder: "Search a word, e.g. funding", value: S.rs, "aria-label": "Search the answers" });
  se.addEventListener("input", () => { S.rs = se.value; S.rn = 25; renderReader(); });
  p.append(el("div", { class: "rsel" }, [sel, qs, se]));
  const term = S.rs.trim().toLowerCase();
  const ids = [];
  for (let i = 0; i < A.a.length; i++) {
    if (S.noneOnly && S.sel == null && subOf(i) >= 0) continue;
    if (S.sel != null && !inTheme(i, S.level, S.sel)) continue;
    if (S.rq >= 0 && A.q[i] !== S.rq) continue;
    if (term && A.a[i].toLowerCase().indexOf(term) < 0) continue;
    ids.push(i);
  }
  ids.sort((a, b) => A.a[b].length - A.a[a].length);
  p.append(el("p", { class: "rcount", text: fmt(ids.length) + " answer" + (ids.length === 1 ? "" : "s") + (ids.length > 1 ? ", longest first" : "") }));
  const list = el("div", { class: "anslist" });
  ids.slice(0, S.rn).forEach(i => list.append(quote(i, { mark: term || null, onClick: () => selectAnswer(i, true) })));
  p.append(list);
  if (ids.length > S.rn) p.append(el("button", { type: "button", class: "btn more", text: "Show 25 more", onclick: () => { S.rn += 25; renderReader(); } }));
  if (keep) { const s = $("#rq-search"); s.focus(); s.setSelectionRange(s.value.length, s.value.length); }
}

const INK = "#2b2620", SOFT = "#6b6257", FAINT = "#b9b0a2", BAND = "#ebe5d8", MARK = "#b0302a";
const TONECOL = ["#b5541c", "#e3a857", "#d6d0c4", "#2e6e96"], TONELAB = ["Negative", "Mixed", "Neutral", "Positive"];
const R3 = () => D.r3 && D.r3[S.al];
const byName = (lv, name) => D.themes.find(t => t.level === lv && t.name === name);
const tcol = (lv, name) => { const t = byName(lv, name); return t ? (lv === "main" ? COL[t.id] : SUBC[t.id]) : FAINT; };
const qtxt = q => q < 0.001 ? "q < 0.001" : "q = " + q.toFixed(3);
function levelSeg() {
  const nSub = D.r3 ? D.r3.sub.tables.region.themes.length : 0;
  return el("div", { class: "seg", role: "group", "aria-label": "Theme level" }, [["main", "Main themes (7)"], ["sub", "Sub-themes (" + nSub + ")"]].map(([v, t]) =>
    el("button", { type: "button", "aria-pressed": S.al === v, text: t, onclick: () => { S.al = v; renderTone(); renderWho(); renderModel(); renderAwards(); } })));
}

function renderTone() {
  const p = $("#sentiment"); if (!p) return;
  p.replaceChildren(el("div", { class: "rsel" }, [levelSeg()]));
  const lv = S.al, names = D.r3[lv].tables.region.themes;
  const rows = names.map(nm => {
    const t = byName(lv, nm), c = [0, 0, 0, 0];
    if (t) for (let i = 0; i < A.sl.length; i++) {
      if (A.sl[i] < 0 || (lv === "main" ? mainOf(i) : subOf(i)) !== t.id) continue;
      c[[0, 0, 1, 2, 3, 3][A.sl[i]]]++;
    }
    const n = c[0] + c[1] + c[2] + c[3];
    return { nm, c, n, net: n ? (c[3] - c[0]) / n : 0 };
  }).filter(r => r.n > 0).sort((a, b) => a.net - b.net);
  const L = 300, R = 70, rh = lv === "main" ? 30 : 24, bh = rh - 10, T0 = 30, Wd = 900, Ht = T0 + rows.length * rh + 30;
  const mid = L + (Wd - L - R) / 2, sc = (Wd - L - R) / 2;
  const svg = svgEl("svg", { viewBox: "0 0 " + Wd + " " + Ht, role: "img", "aria-label": "Share of negative, mixed, neutral and positive answers in each theme" });
  TONELAB.forEach((l, k) => svg.append(svgEl("rect", { x: L + k * 110, y: 4, width: 12, height: 12, rx: 2, fill: TONECOL[k] }), txt(L + k * 110 + 18, 14, l, { "font-size": 12.5 })));
  rows.forEach((r, k) => {
    const y = T0 + k * rh, f = r.c.map(v => v / r.n); let x = mid - (f[0] + f[1] + f[2] / 2) * sc; const left = x;
    svg.append(txt(L - 12, y + bh * .75, r.nm.length > 42 ? r.nm.slice(0, 41) + "…" : r.nm, { "text-anchor": "end", "font-size": 12.5 }));
    f.forEach((v, j) => { svg.append(tip(svgEl("rect", { x, y, width: Math.max(0, v * sc), height: bh, fill: TONECOL[j] }), r.nm + " · " + TONELAB[j] + ": " + pct(v) + " of " + r.n + " scored answers")); x += v * sc; });
    svg.append(txt(left - 6, y + bh * .75, pct(f[0]), { "text-anchor": "end", "font-size": 11.5, fill: TONECOL[0], "font-weight": 600 }), txt(x + 6, y + bh * .75, pct(f[3]), { "font-size": 11.5, fill: TONECOL[3], "font-weight": 600 }));
  });
  svg.append(svgEl("line", { x1: mid, x2: mid, y1: T0 - 6, y2: Ht - 22, stroke: INK }), txt(mid - 8, Ht - 6, "← more negative", { "text-anchor": "end", "font-size": 12, fill: SOFT }), txt(mid + 8, Ht - 6, "more positive →", { "font-size": 12, fill: SOFT }));
  const T = D.r3.main.tone, g = k => T[k].groups.map((n, i) => n + " " + sg(T[k].mean[i])).join(", ");
  p.append(el("div", { class: "fig" }, [svg]), el("p", { class: "fignote", text: "Tone by group (mean from −1 to +1): " + g("region") + " (" + qtxt(T.region.q) + "); " + g("school") + " (" + qtxt(T.school.q) + "); medal: " + g("medal") + " (" + qtxt(T.medal.q) + "). No group difference in tone holds after correction." }));
}

const CMP = [["region", "Region"], ["region_undergrad", "Region, undergraduates"], ["country", "Country"], ["europe", "Europe"], ["school", "School level"], ["school_asia", "School level, Asia"], ["village", "Village"], ["medal", "Medal"]];
const MODEL_FACTORS = { region: ["Europe vs Asia", "North America vs Asia"], region_undergrad: ["Europe vs Asia", "North America vs Asia"], school: ["Undergraduate vs high school", "Graduate vs high school"], school_asia: ["Undergraduate vs high school"], medal: ["Gold medal"] };
function renderWho() {
  const p = $("#who"); if (!p || !D.r3) return;
  const key = S.cmp || "region", lv = S.al, tab = R3().tables[key];
  const cmpSeg = el("div", { class: "seg wrapseg", role: "group", "aria-label": "Compare by" }, CMP.map(([k, t]) => el("button", { type: "button", "aria-pressed": key === k, text: t, onclick: () => { S.cmp = k; renderWho(); } })));
  p.replaceChildren(el("div", { class: "rsel" }, [levelSeg()]), el("div", { class: "rsel" }, [cmpSeg]));
  const G = tab.groups.length, tot = tab.answers.reduce((a, b) => a + b, 0);
  const rows = tab.themes.map((nm, j) => ({ nm, j, all: tab.share.reduce((s, sh, g) => s + sh[j] * tab.answers[g], 0) / tot })).sort((a, b) => b.all - a.all);
  const xmax = Math.max(.1, Math.ceil(Math.max(...tab.share.flat()) * 20) / 20);
  const L = 300, R = 30, rh = lv === "main" ? 44 : 34, T0 = 34, Wd = 900, Ht = T0 + rows.length * rh + 28, x = v => L + v / xmax * (Wd - L - R);
  const svg = svgEl("svg", { viewBox: "0 0 " + Wd + " " + Ht, role: "group", "aria-label": "Share of answers in each theme, by " + CMP.find(c => c[0] === key)[1] });
  for (let v = 0; v <= xmax + 1e-9; v += xmax > .3 ? .1 : .05) svg.append(svgEl("line", { x1: x(v), x2: x(v), y1: T0 - 6, y2: Ht - 22, stroke: "#e7e1d4" }), txt(x(v), Ht - 6, Math.round(v * 100) + "%", { "text-anchor": "middle", "font-size": 11.5, fill: SOFT }));
  svg.append(svgEl("rect", { x: L, y: 6, width: 26, height: 10, fill: BAND }), txt(L + 32, 15, "chance range", { "font-size": 12, fill: SOFT }),
    svgEl("circle", { cx: L + 150, cy: 11, r: 4.5, fill: "#fff", stroke: SOFT, "stroke-width": 1.5 }), txt(L + 160, 15, "one group", { "font-size": 12, fill: SOFT }),
    svgEl("circle", { cx: L + 250, cy: 11, r: 5.5, fill: MARK }), txt(L + 260, 15, "differs after correction", { "font-size": 12, fill: SOFT }));
  rows.forEach((r, k) => {
    const y = T0 + k * rh + rh / 2, sig = tab.q[r.j] < .05, band = tab.chance_band[r.j];
    svg.append(svgEl("line", { x1: L, x2: Wd - R, y1: y, y2: y, stroke: "#efe9dd" }));
    svg.append(svgEl("rect", { x: x(Math.max(0, r.all - band)), y: y - 8, width: x(r.all + band) - x(Math.max(0, r.all - band)), height: 16, fill: BAND, rx: 3 }));
    svg.append(svgEl("line", { x1: x(r.all), x2: x(r.all), y1: y - 10, y2: y + 10, stroke: SOFT, "stroke-width": 1.4 }));
    const label = r.nm.length > 40 ? r.nm.slice(0, 39) + "…" : r.nm;
    svg.append(svgEl("rect", { x: 0, y: y - 9, width: 4, height: 18, fill: tcol(lv, r.nm) }), txt(12, y - 1, label, { "font-size": 13, "font-weight": sig ? 700 : 400, fill: INK }),
      txt(12, y + 13, sig ? "differs, " + qtxt(tab.q[r.j]) : "no difference, " + qtxt(tab.q[r.j]), { "font-size": 11, fill: sig ? MARK : SOFT }));
    let lab = 0;
    tab.groups.map((g, gi) => gi).sort((a, b) => (tab.cell_q[a][r.j] < .05) - (tab.cell_q[b][r.j] < .05)).forEach(gi => {
      const v = tab.share[gi][r.j], flag = tab.cell_q[gi][r.j] < .05 && sig, few = tab.teams[gi] < 8;
      const info = tab.groups[gi] + ": " + pct(v, 1) + " of " + fmt(tab.answers[gi]) + " answers (95% interval " + pct(tab.lo[gi][r.j], 1) + " to " + pct(tab.hi[gi][r.j], 1) + "), " + tab.teams[gi] + " teams" + (few ? " (few teams)" : "") + "; residual " + sg(tab.resid[gi][r.j]);
      svg.append(tip(svgEl("circle", { cx: x(v), cy: y, r: flag ? 5.5 : 4.2, fill: flag ? MARK : "#fff", stroke: flag ? MARK : SOFT, "stroke-width": 1.5, "fill-opacity": flag ? 1 : .9 }), info));
      if (flag) { svg.append(txt(x(v) + 8, y + (lab++ % 2 ? 14 : -6), tab.groups[gi] + (tab.resid[gi][r.j] > 0 ? " ↑" : " ↓"), { "font-size": 11.5, "font-weight": 600, fill: MARK, stroke: "#f6f1e7", "stroke-width": 3, "paint-order": "stroke" })); }
    });
    if (sig && !lab) {
      const sh = tab.groups.map((g, gi) => [tab.share[gi][r.j], gi]).sort((a, b) => a[0] - b[0]), lowest = sh[0], highest = sh[sh.length - 1];
      [[highest, -6], [lowest, 14]].forEach(([[v, gi], dy]) => svg.append(txt(x(v) + 7, y + dy, tab.groups[gi] + " " + pct(v, 1), { "font-size": 11, fill: INK, stroke: "#f6f1e7", "stroke-width": 3, "paint-order": "stroke" })));
    }
  });

  const RR = R3(), notes = [];
  rows.filter(r => tab.q[r.j] < .05).forEach(r => {
    const bits = [];
    if (tab.wide_q) bits.push("wider theme assignment " + qtxt(tab.wide_q[r.j]));
    const lo = RR.loo[tab.name + "|" + r.nm]; if (lo != null) bits.push("leaving out any one team, p stays at or below " + lo.toFixed(3));
    const fac = MODEL_FACTORS[key], m = RR.model[r.nm];
    if (fac && m && !m.error) { const ok = fac.some(f => m[f] && m[f].q < .05); bits.push(ok ? "holds in the combined model" : "does not hold in the combined model, which also allows for answer length and question (Figure 6)"); }
    notes.push(r.nm + " differs (" + qtxt(tab.q[r.j]) + ")" + (bits.length ? ". Checks: " + bits.join("; ") : "") + ".");
  });
  const nNo = rows.length - notes.length;
  notes.push(nNo + " of " + rows.length + (lv === "main" ? " themes" : " sub-themes") + " show no difference.");
  if (key === "medal") { const tr = RR.trend, best = tr.reduce((a, b) => a.q < b.q ? a : b); notes.push("Ordered trend from no medal to gold: no theme rises or falls with the medal (smallest q = " + best.q.toFixed(2) + "). Bronze (4 teams) and no medal (5 teams) are few teams: read them with care."); }
  p.append(el("div", { class: "fig" }, [svg]),
    el("p", { class: "fignote", text: "Groups: " + tab.groups.map((g, i) => g + " " + tab.teams[i]).join(" · ") + " teams." }),
    ...notes.map(n => el("p", { class: "fignote", text: n })));
}

function renderModel() {
  const p = $("#model"); if (!p || !D.r3) return;
  const lv = S.al, M = R3().model, F = [["Europe vs Asia", "Europe vs Asia"], ["North America vs Asia", "N. America vs Asia"], ["Undergraduate vs high school", "Undergrad vs high school"], ["Graduate vs high school", "Graduate vs high school"], ["Gold medal", "Gold medal"], ["log answer length", "Longer answer"]];
  const t = el("table", { class: "model" });
  t.append(el("thead", {}, [el("tr", {}, [el("th", { text: lv === "main" ? "Main theme" : "Sub-theme" }), ...F.map(f => el("th", { scope: "col", text: f[1] }))])]));
  const tb = el("tbody");
  Object.keys(M).filter(k => k !== "(no theme)").forEach(nm => {
    const m = M[nm], only = m._scope && m._scope.indexOf("only") === 0;
    const tr = el("tr", {}, [el("th", { scope: "row" }, [el("i", { class: "sq", style: "background:" + tcol(lv, nm) }), " " + nm + (only ? " †" : "")])]);
    F.forEach(([f]) => {
      const v = m[f];
      if (!v) { tr.append(el("td", { class: "na", text: "–", title: m.error ? "The model did not fit for this theme" : "" })); return; }
      const sig = v.q != null && v.q < .05;
      tr.append(el("td", { class: sig ? "sig" : "", text: "×" + v.or.toFixed(2), title: nm + " · " + f + ": odds × " + v.or.toFixed(2) + " (95% interval " + v.lo.toFixed(2) + " to " + v.hi.toFixed(2) + "), p = " + v.p.toFixed(3) + (v.q != null ? ", q = " + v.q.toFixed(3) : "") + (m._scope ? ". Model on " + m._scope + "." : "") }));
    });
    tb.append(tr);
  });
  t.append(tb);
  p.replaceChildren(el("div", { class: "rsel" }, [levelSeg()]), el("div", { class: "heatwrap" }, [t]),
    el("p", { class: "fignote", text: "×1.00 means no change in the odds that an answer belongs to the theme; above 1, more likely; below 1, less likely. Red: holds after correction over the " + (lv === "main" ? "7 themes" : Object.keys(M).length + " sub-themes") + ". “Longer answer” is per step on a log scale of words. † This theme comes almost only from one question, so its model uses the answers to that question only." }));
}

function renderAwards() {
  const p = $("#awards"); if (!p || !D.r3) return;
  const lv = S.al, AW = R3().awards, OUT = [["gold", "Gold medal"], ["special", "Special prize"], ["nominated", "Nomination"]];
  const names = AW.gold.rows.map(r => r.theme), n = names.length;
  const L = 300, cw = 190, gap = 16, rh = lv === "main" ? 34 : 26, T0 = 54, Wd = L + OUT.length * (cw + gap), Ht = T0 + n * rh + 34, lo = Math.log(.4), hi = Math.log(2.5);
  const svg = svgEl("svg", { viewBox: "0 0 " + Wd + " " + Ht, role: "img", "aria-label": "Odds ratio per 10 percentage points for each theme and each award" });
  OUT.forEach(([k, label], j) => {
    const o = AW[k], x0 = L + j * (cw + gap), x = v => x0 + (Math.max(lo, Math.min(hi, Math.log(v))) - lo) / (hi - lo) * cw;
    svg.append(txt(x0 + cw / 2, 18, label, { "text-anchor": "middle", "font-size": 15, "font-weight": 600 }), txt(x0 + cw / 2, 36, o.teams_with + " of 125 teams", { "text-anchor": "middle", "font-size": 12.5, fill: SOFT }));
    [.5, 1, 2].forEach(v => svg.append(svgEl("line", { x1: x(v), x2: x(v), y1: T0 - 6, y2: T0 + n * rh, stroke: v === 1 ? SOFT : "#e7e1d4", "stroke-width": v === 1 ? 1.4 : 1 }), txt(x(v), T0 + n * rh + 18, String(v), { "text-anchor": "middle", "font-size": 12, fill: SOFT })));
    o.rows.forEach((r, i) => {
      const y = T0 + i * rh + rh / 2, sig = r.q < .05;
      svg.append(svgEl("line", { x1: x(r.lo), x2: x(r.hi), y1: y, y2: y, stroke: sig ? MARK : SOFT, "stroke-width": 1.8 }),
        tip(svgEl("circle", { cx: x(r.or), cy: y, r: 5, fill: sig ? MARK : "#fff", stroke: sig ? MARK : INK, "stroke-width": 1.6 }), label + " · " + r.theme + ": odds × " + r.or.toFixed(2) + " per 10 points (95% interval " + r.lo.toFixed(2) + " to " + r.hi.toFixed(2) + "), p = " + r.p.toFixed(3) + ", q = " + r.q.toFixed(2)));
    });
  });
  names.forEach((nm, i) => { const y = T0 + i * rh + rh / 2; svg.append(svgEl("rect", { x: 0, y: y - 6, width: 4, height: 12, fill: tcol(lv, nm) }), txt(12, y + 5, nm.length > 40 ? nm.slice(0, 39) + "…" : nm, { "font-size": 13 })); });
  const best = Math.min(...OUT.map(([k]) => Math.min(...AW[k].rows.map(r => r.q))));
  p.replaceChildren(el("div", { class: "rsel" }, [levelSeg()]), el("div", { class: "fig" }, [svg]),
    el("p", { class: "fignote", text: (best < .05 ? "" : "No theme holds after correction for any award (smallest q = " + best.toFixed(2) + "). ") + (lv === "main" ? "One model per award weighs the seven themes together." : "One model per sub-theme and award.") + " Every model allows for region, school level and team size. Hover a dot for its numbers." }));
}

})();
