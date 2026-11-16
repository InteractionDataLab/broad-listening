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
  (kids || []).forEach(c => e.append(c && c.nodeType ? c : document.createTextNode(c)));
  return e;
};
const fmt = n => n.toLocaleString("en-US");
const pct = (v, d) => (v * 100).toFixed(d == null ? 1 : d) + "%";
const MAIN_COL = window.PAL.CAT;
function shade(hex, f) {
  const n = parseInt(hex.slice(1), 16), r = n >> 16, g = (n >> 8) & 255, b = n & 255;
  const m = c => Math.max(0, Math.min(255, Math.round(f > 0 ? c + (255 - c) * f : c * (1 + f))));
  return "#" + [m(r), m(g), m(b)].map(c => c.toString(16).padStart(2, "0")).join("");
}
const LANG = { en: "EN", fr: "FR", es: "ES", de: "DE" };
let D, MAINS, SUBS, SUBCOL = {}, MAINIDX = {}, CNT;
const S = { tab: "map", level: "main", sel: null, country: null, passage: null, labels: true, zoom: 1, px: 0, py: 0, hov: -1, thin: 30, own: false, qt: "typical", tc: null, tm: "same", R: null };
const newR = () => ({ q: "", th: null, ctr: [], lang: [], year: null, place: "all", sort: "fit", shown: 12, seed: 1 });
S.R = newR();

const TABS = [["map", "Map of themes"], ["themes", "Theme reports"], ["reader", "Read the passages"]];

function focusExplorer() { const t = S.tab === "map" ? $("#app") : $("#drawer"); if (t && !t.hidden) { const r = t.getBoundingClientRect(); if (r.top < 0 || r.top > window.innerHeight * 0.6) t.scrollIntoView({ block: "start", behavior: "smooth" }); } }
const GO = {
  map(o) { if (o.level) S.level = o.level; if ("sel" in o) S.sel = o.sel; if ("country" in o) S.country = o.country; if ("passage" in o) S.passage = o.passage; if ("own" in o) S.own = o.own; S.tab = "map"; render(); focusExplorer(); },
  themes(level, id) { S.level = level; S.sel = id; S.passage = null; S.tab = "themes"; render(); focusExplorer(); },
  reader(patch) { S.R = Object.assign(newR(), patch); S.tab = "reader"; render(); focusExplorer(); },
  tab(t) { S.tab = t; render(); focusExplorer(); }
};

let started = false;
function start() {
  if (started) return; started = true;
  $("#app").replaceChildren(el("p", { class: "loading", role: "status", text: "Loading 3,912 passages (about 5 MB, less when compressed)…" }));
  (window.MSF_DATA ? Promise.resolve(window.MSF_DATA) : fetch("data/msf/msf-data.json").then(r => { if (!r.ok) throw new Error(r.status); return r.json(); })).then(init).catch(err => {
    $("#app").replaceChildren(el("p", { class: "loading", role: "alert", text: "The data file could not be loaded (" + err.message + "). If you opened this page as a local file, open it through a web address instead." }));
  });
}
const isMapHash = () => /=/.test(location.hash);
if (isMapHash() || !("IntersectionObserver" in window)) start();
else { const io = new IntersectionObserver(es => { if (es.some(e => e.isIntersecting)) { io.disconnect(); start(); } }, { rootMargin: "900px 0px" }); io.observe($("#app")); }
window.addEventListener("hashchange", () => { if (isMapHash()) start(); });

function init(d) {
  D = d;
  MAINS = D.clusters.filter(c => c.level === "main").sort((a, b) => a.id - b.id);
  SUBS = D.clusters.filter(c => c.level === "sub").sort((a, b) => a.id - b.id);
  MAINS.forEach(c => MAINIDX[c.id] = c);
  const sib = {};
  SUBS.forEach(c => { sib[c.parent] = (sib[c.parent] || 0) + 1; const k = sib[c.parent] - 1; SUBCOL[c.id] = window.PAL.child(MAIN_COL[c.parent], k); });

  const nC = D.countries.length;
  CNT = { country: new Array(nC).fill(0), main: MAINS.map(() => new Array(nC).fill(0)), sub: SUBS.map(() => new Array(nC).fill(0)) };
  for (let i = 0; i < D.x.length; i++) { const c = ctry(i); CNT.country[c]++; CNT.main[D.main[i]][c]++; CNT.sub[D.sub[i]][c]++; }
  if ($("#facts")) $("#facts").replaceChildren(...[
    [fmt(D.header.stories), "stories (one version each)"], [fmt(D.header.passages), "passages grouped"],
    [D.header.themes + " + " + D.header.subthemes, "themes + sub-themes"], [String(nC), "countries"], ["4", "languages"]
  ].map(a => el("div", { class: "fact" }, [el("b", { text: a[0] }), el("span", { text: a[1] })])));
  window.MSFX.init({ D, S, MAINS, SUBS, MAIN_COL, SUBCOL, CNT, el, svgEl, txt, fmt, pct, cap, LANG, render, writeHash, newR, selCluster, go: GO });
  if ($("#gauges")) buildGauges();
  if ($("#findings")) window.MSFX.renderFindings($("#findings"));
  if ($("#funnel")) window.MSFX.renderFunnel($("#funnel"));
  if ($("#downloads")) window.MSFX.renderDownloads($("#downloads"));
  buildApp();
  readHash();
  window.addEventListener("hashchange", () => { if (!isMapHash()) return; readHash(); render(); });
  render();
}

const ctry = i => D.docs[D.doc[i]][1];
const clOf = i => S.level === "main" ? D.main[i] : D.sub[i];
const clusters = () => S.level === "main" ? MAINS : SUBS;
const colOf = (id) => S.level === "main" ? MAIN_COL[id] : SUBCOL[id];
const selCluster = () => S.sel == null ? null : clusters()[S.sel];

function writeHash() {
  const p = [], e = encodeURIComponent;
  if (S.tab !== "map") p.push("view=" + S.tab);
  if (S.tab === "reader") {
    const R = S.R;
    if (R.q) p.push("q=" + e(R.q));
    if (R.th) p.push("rth=" + (R.th[0] === "main" ? "m" : "s") + R.th[1]);
    if (R.ctr.length) p.push("rc=" + R.ctr.join("."));
    if (R.lang.length) p.push("rl=" + R.lang.join("."));
    if (R.year) p.push("ry=" + R.year);
    if (R.place !== "all") p.push("rj=" + R.place);
    if (R.sort !== "fit") p.push("rs=" + R.sort);
  } else {
    if (S.level !== "main") p.push("level=sub");
    if (S.sel != null) p.push("theme=" + S.sel);
    if (S.tab === "map" || S.tab === "matrix") { if (S.country != null) p.push("country=" + e(D.countries[S.country])); }
    if (S.tab === "map") { if (S.passage != null) p.push("passage=" + S.passage); if (S.own) p.push("own=1"); }
    if (S.tab === "topics" && S.country != null) p.push("country=" + e(D.countries[S.country]));
    if (S.tab === "time") { if (S.tc != null) p.push("tc=" + S.tc); if (S.tm === "own") p.push("tm=own"); }
  }
  const h = p.length ? "#" + p.join("&") : "";
  if (!p.length && location.hash && !isMapHash()) return;
  if (location.hash !== h) history.replaceState(null, "", location.pathname + location.search + h);
}
function readHash() {
  const p = new URLSearchParams(location.hash.slice(1));
  const v = p.get("view"); S.tab = TABS.some(t => t[0] === v) ? v : "map";
  S.level = p.get("level") === "sub" ? "sub" : "main";
  const t = p.get("theme"); S.sel = t != null && /^\d+$/.test(t) && clusters()[+t] ? +t : null;
  const c = D.countries.indexOf(p.get("country")); S.country = c >= 0 ? c : null;
  const ps = p.get("passage"); S.passage = ps != null && /^\d+$/.test(ps) && +ps < D.x.length ? +ps : null;
  if (S.passage != null && S.sel == null) { S.level = "main"; S.sel = D.main[S.passage]; }
  S.own = p.get("own") === "1";
  const R = newR(); R.q = p.get("q") || "";
  const rth = p.get("rth");
  if (rth && /^[ms]\d+$/.test(rth)) { const lv = rth[0] === "m" ? "main" : "sub", id = +rth.slice(1); if ((lv === "main" ? MAINS : SUBS)[id]) R.th = [lv, id]; }
  R.ctr = (p.get("rc") || "").split(".").filter(x => /^\d+$/.test(x)).map(Number).filter(i => i < D.countries.length);
  R.lang = (p.get("rl") || "").split(".").filter(l => ["en", "fr", "es", "de"].includes(l));
  R.year = ["2023", "2024", "2025"].includes(p.get("ry")) ? p.get("ry") : null;
  R.place = ["own", "joined"].includes(p.get("rj")) ? p.get("rj") : "all";
  R.sort = ["new", "old", "random"].includes(p.get("rs")) ? p.get("rs") : "fit";
  S.R = R;
  const tc = p.get("tc"); S.tc = tc != null && /^\d+$/.test(tc) && +tc < D.countries.length ? +tc : null;
  S.tm = p.get("tm") === "own" ? "own" : "same";
}

let canvas, ctx, W = 0, Hh = 0, dpr = 1, bounds, labelsCache = {};
function buildApp() {
  const app = $("#app"); app.replaceChildren();

  const legend = el("div", { class: "legend", id: "legend" });
  const mapwrap = el("div", { class: "mapwrap", id: "mapwrap" });
  canvas = el("canvas", { id: "cv", tabindex: "0", role: "img", "aria-label": "Map of 3,912 passages. Each dot is a passage, coloured by theme. Use the theme list to read the themes, and the card for their passages." });
  mapwrap.append(canvas,
    el("div", { class: "tools" }, [
      el("button", { type: "button", "aria-label": "Zoom in", text: "+", onclick: () => zoomBy(1.4) }),
      el("button", { type: "button", "aria-label": "Zoom out", text: "−", onclick: () => zoomBy(1 / 1.4) }),
      el("button", { type: "button", "aria-label": "Reset the view", text: "↺", onclick: () => { S.zoom = 1; S.px = 0; S.py = 0; draw(); } })]),
    el("div", { class: "mapnote", text: "Distances show similarity of topic, not of place." }));
  const nOwn = D.ab.filter(v => !v).length;
  const opts = el("div", { class: "opts" }, [
    el("label", {}, [el("input", { type: "checkbox", id: "lab", checked: true, onchange: e => { S.labels = e.target.checked; draw(); if (MAP3) MAP3.draw(); } }), "Theme labels"]),
    el("label", { title: "The density method left about half of the passages unplaced. They were added to the nearest sub-theme afterwards." }, [el("input", { type: "checkbox", id: "own", onchange: e => { S.own = e.target.checked; S.passage = null; render(); } }), "Only passages the method placed itself (" + fmt(nOwn) + ")"]),
    el("span", { id: "filters" })]);
  const card = el("aside", { class: "card", id: "card", "aria-live": "polite", "aria-label": "Theme card" });

  const has3 = Array.isArray(D.x3) && D.x3.length === D.x.length;
  const box3 = el("div", { class: "mapwrap map3", id: "map3box", hidden: true });
  const viewSeg = has3 ? el("div", { class: "seg", role: "group", "aria-label": "View", id: "viewseg" }) : "";
  const pMap = el("div", { class: "panel", id: "p-map", role: "tabpanel", "aria-labelledby": "t-map" }, [
    el("div", { class: "explorer" }, [legend, el("div", {}, [viewSeg, mapwrap, box3, opts]), card])]);
  if (has3) { S.view = S.view || "3d"; setTimeout(setView, 0, S.view); }
  app.append(pMap);
  const drawer = el("div", { id: "drawer", class: "drawer", hidden: true }, [
    el("div", { class: "drawer-head" }, [el("span", { id: "drawer-title" }), el("button", { type: "button", class: "drawer-x", text: "Close ×", "aria-label": "Close and go back to the map", onclick: () => { S.tab = "map"; render(); focusExplorer(); } })]),
    ...TABS.slice(1).map(t => el("div", { class: "panel", id: "p-" + t[0], role: "region", "aria-label": t[1], hidden: true }))]);
  app.append(drawer);
  ctx = canvas.getContext("2d");
  new ResizeObserver(resize).observe(mapwrap);
  bindMap();

  if (document.fonts && document.fonts.load) document.fonts.load("600 14px 'Atkinson Next'").then(() => { if (S.tab === "map") draw(); }).catch(() => {});
}
function setTab(t) { S.tab = t; render(); writeHash(); }

let MAP3 = null;
const filtOn = () => S.sel != null || S.country != null || S.own;
function centre3(id) {
  const xs = [], ys = [], zs = [], x2 = [], y2 = [];
  for (let i = 0; i < D.x.length; i++) if (clOf(i) === id) { xs.push(D.x3[i]); ys.push(D.y3[i]); zs.push(D.z3[i]); x2.push(D.x[i]); y2.push(D.y[i]); }
  const med = a => { const s = a.slice().sort((p, q) => p - q); return s[Math.floor(s.length / 2)]; };
  return xs.length ? { x3: med(xs), y3: med(ys), z3: med(zs), x2: med(x2), y2: med(y2) } : null;
}
function setView(v) {
  S.view = v;
  const seg = $("#viewseg");
  if (seg) seg.replaceChildren(...[["3d", "3-D"], ["2d", "Flat"]].map(([k, t]) => el("button", { type: "button", "aria-pressed": S.view === k, text: t, onclick: () => setView(k) })));
  $("#mapwrap").hidden = v === "3d"; $("#map3box").hidden = v !== "3d";
  if (v === "3d" && !MAP3) {
    MAP3 = window.Map3D($("#map3box"), {
      x3: D.x3, y3: D.y3, z3: D.z3, x2: D.x, y2: D.y, mode: "3d",
      ariaLabel: "Map of 3,912 passages in three dimensions. Each dot is a passage, coloured by theme. Drag to turn the map.",
      color: i => colOf(clOf(i)), active: i => !filtOn() || isActive(i), anyActive: filtOn,
      light: c => window.PAL.lum(c) > .6, ink: c => window.PAL.ink(c), group: i => clOf(i),
      labels: () => S.labels ? clusters().filter(c => S.sel == null || c.id === S.sel).map(c => { const p = centre3(c.id); return p && Object.assign(p, { id: c.id, text: cap(c.name), color: window.PAL.ink(colOf(c.id), "#ffffff"), small: S.level === "sub" }); }).filter(Boolean) : [],
      onHover: (h, e) => {
        const tip = $("#tip");
        if (h < 0 || !e) { tip.style.opacity = 0; return; }
        const d = D.docs[D.doc[h]], t = D.txt[h];
        tip.replaceChildren(el("b", { text: d[0] }), el("em", { text: D.countries[d[1]] + " · " + d[2] }), el("br"), document.createTextNode(t.length > 150 ? t.slice(0, 150).replace(/\s+\S*$/, "") + "…" : t));
        tip.style.left = Math.min(window.innerWidth - 336, e.clientX + 14) + "px"; tip.style.top = (e.clientY + 16) + "px"; tip.style.opacity = 1;
      },
      onClick: h => { if (h >= 0) { S.passage = h; S.sel = clOf(h); render(); } }
    });
  }
  if (v === "3d" && MAP3) { MAP3.select(S.passage == null ? -1 : S.passage); MAP3.draw(); } else resize();
}

function render() {
  TABS.forEach(([t]) => {
    const on = S.tab === t;
    if (t !== "map") $("#p-" + t).hidden = !on;
  });
  $("#drawer").hidden = S.tab === "map"; $("#drawer-title").textContent = S.tab === "themes" ? "Theme report" : S.tab === "reader" ? "Read the passages" : "";
  { renderLegend();
    renderCard(); renderFilters(); resize(); if (MAP3 && S.view === "3d") { MAP3.select(S.passage == null ? -1 : S.passage); MAP3.draw(); } }
  if (S.tab === "matrix") renderMatrix();
  if (S.tab === "topics") renderTopics();
  if (S.tab === "themes") window.MSFX.renderThemes($("#p-themes"));
  if (S.tab === "reader") window.MSFX.renderReader($("#p-reader"));
  if (S.tab === "time") window.MSFX.renderTime($("#p-time"));
  writeHash();
}

function renderLegend() {
  const lg = $("#legend"); lg.replaceChildren();
  lg.append(el("div", { class: "seg", role: "group", "aria-label": "Level of detail" }, [
    el("button", { type: "button", "aria-pressed": S.level === "main", text: "Themes (" + MAINS.length + ")", onclick: () => { S.level = "main"; S.sel = null; render(); } }),
    el("button", { type: "button", "aria-pressed": S.level === "sub", text: "Sub-themes (" + SUBS.length + ")", onclick: () => { S.level = "sub"; S.sel = null; render(); } })]));
  const ul = el("ul");
  clusters().slice().sort((a, b) => b.size - a.size).forEach(c => {
    const idx = c.id;
    const mixed = c.flags.includes("incoherent");
    ul.append(el("li", {}, [el("button", { class: "lg", type: "button", "aria-pressed": S.sel === idx, onclick: () => { S.sel = S.sel === idx ? null : idx; S.passage = null; render(); } }, [
      el("i", { style: "background:" + colOf(idx) }),
      el("span", { class: "nm", text: cap(c.name) }),
      el("span", { class: "mt" }, [fmt(c.size) + " · " + pct(c.share, 0), el("span", { class: "bar2" }, [el("b", { style: "width:" + (c.share / .36 * 100).toFixed(0) + "%;background:" + colOf(idx) })]), mixed ? el("span", { class: "tag", text: "mixed" }) : ""])])]));
  });
  lg.append(ul);
}
const cap = s => s.charAt(0).toUpperCase() + s.slice(1);

function renderFilters() {
  const f = $("#filters"); f.replaceChildren();
  $("#own").checked = S.own;
  if (S.country != null || S.sel != null || S.passage != null || S.own) {
    f.append(el("button", { class: "chip", type: "button", text: "Clear selection", onclick: () => { S.sel = null; S.country = null; S.passage = null; S.own = false; render(); } }));
  }
  if (S.country != null) f.append(" ", el("span", { text: "Showing passages from " + D.countries[S.country] }));
}

function renderCard() {
  const card = $("#card"); card.replaceChildren();
  const c = selCluster();

  const sumBlock = () => c && c.summary ? [el("p", { class: "msum" }, [el("span", { class: "msumk", text: "Machine summary" }), document.createTextNode(c.summary)]),
    el("p", { class: "small", text: "Written by a language model and checked against the passages." })] : [];
  if (S.passage != null && !c) card.append(passageBox(S.passage));
  if (!c) {
    card.append(el("p", { class: "kicker", text: "Overview" }), el("h3", { text: "Pick a theme" }),
      el("p", { class: "small", text: "Choose a theme in the list, or click any dot on the map. The card shows what the theme is about, which words set it apart, which countries it comes from, and passages that sit at its centre." }),
      el("p", { class: "small", text: "The largest theme, about wounded patients and injuries, holds a third of the passages. Themes marked “mixed” in brown italics are less reliable." }));
    return;
  }
  card.append(el("p", { class: "kicker", text: c.level === "main" ? "Theme " + (c.id + 1) + " of " + MAINS.length : "Sub-theme of “" + MAINIDX[c.parent].name + "”" }),
    el("h3", { text: cap(c.name) }));
  if (S.passage != null) card.append(...sumBlock(), passageBox(S.passage));
  card.append(el("p", { class: "kv" }, [
    el("span", {}, [el("b", { text: fmt(c.size) }), " passages"]), el("span", {}, [el("b", { text: pct(c.share) }), " of the corpus"]),
    el("span", {}, [el("b", { text: fmt(c.documents) }), " stories"]), el("span", {}, ["coherence ", el("b", { text: (Math.abs(c.coherence) < .005 ? 0 : c.coherence).toFixed(2) })])]));
  if (c.flags.includes("incoherent")) card.append(el("div", { class: "warnbox", text: "Mixed theme. Its passages do not share one clear topic, so read it as a collection of related subjects." }));
  if (c.flags.includes("not reproduced by a second model")) card.append(el("div", { class: "warnbox", text: "A second embedding model grouped this part differently" + (c.jaccard2 != null ? " (overlap " + c.jaccard2.toFixed(2) + ")" : "") + ". Treat its edges as uncertain." }));
  if (S.passage == null) card.append(...sumBlock());
  if (c.terms.length) card.append(el("div", { class: "sec" }, [el("h4", { text: "Words that set it apart" }), el("div", { class: "words" }, c.terms.slice(0, 10).map(t => el("span", { text: t[0] })))]));
  if (c.countries.length) {
    const sec = el("div", { class: "sec" }, [el("h4", { text: "Where it is reported" }), el("p", { class: "small", text: "Share of each country’s stories that voice this theme." })]);
    c.countries.slice().sort((a, b) => b[2] - a[2]).forEach(r => {
      sec.append(el("button", { class: "crow", type: "button", "aria-pressed": S.country === r[0], title: "Show only passages from " + D.countries[r[0]], onclick: () => { S.country = S.country === r[0] ? null : r[0]; render(); } }, [
        el("span", { class: "cn", text: D.countries[r[0]] }), el("span", { class: "tr" }, [el("b", { style: "width:" + Math.min(100, r[2] * 100) + "%" })]), el("span", { class: "vv", text: pct(r[2], 0) })]));
    });
    card.append(sec);
  }
  if (c.level === "main") {
    const kids = SUBS.filter(s => s.parent === c.id);
    if (kids.length > 1) card.append(el("div", { class: "sec" }, [el("h4", { text: "Sub-themes inside" }), el("div", { class: "kids" }, kids.map(k => el("button", { type: "button", text: cap(k.name) + " (" + fmt(k.size) + ")", onclick: () => { S.level = "sub"; S.sel = k.id; S.passage = null; render(); } })))]));
  }
  const pk = window.MSFX.pick(c.level, c.id);
  const sec = el("div", { class: "sec" }, [el("h4", { text: "Typical passages" }), el("p", { class: "small", text: "The best-fitting passages, one per story, from different countries where possible." })]);
  pk.typical.slice(0, 3).forEach(i => sec.append(window.MSFX.passageCard(i, { compact: true, limit: 360, noactions: true })));
  sec.append(el("div", { class: "acts" }, [
    el("button", { class: "btn", type: "button", text: "Open the full theme report", onclick: () => GO.themes(c.level, c.id) }),
    el("button", { class: "btn", type: "button", text: "Read all " + fmt(c.size), onclick: () => GO.reader({ th: [c.level, c.id] }) })]));
  card.append(sec);
}
function passageBox(i) {
  return el("div", { class: "passage" }, [
    el("button", { class: "x", type: "button", "aria-label": "Close passage", text: "×", onclick: () => { S.passage = null; render(); } }),
    el("p", { class: "kicker", text: "Selected passage" }),
    window.MSFX.passageCard(i, { limit: 1800, sumOpen: true })]);
}

function resize() {
  const r = canvas.getBoundingClientRect();
  dpr = Math.min(window.devicePixelRatio || 1, 2);
  W = r.width; Hh = r.height;
  if (!W) return;
  canvas.width = Math.round(W * dpr); canvas.height = Math.round(Hh * dpr);
  draw();
}
function getBounds() {
  if (bounds) return bounds;
  const q = (arr, p) => { const s = arr.slice().sort((a, b) => a - b); return s[Math.max(0, Math.min(s.length - 1, Math.floor(p * (s.length - 1))))]; };
  return (bounds = { x0: q(D.x, .004), x1: q(D.x, .996), y0: q(D.y, .004), y1: q(D.y, .996) });
}
function tf() {
  const B = getBounds(), pad = 28;
  const k = Math.min((W - 2 * pad) / (B.x1 - B.x0), (Hh - 2 * pad) / (B.y1 - B.y0)) * S.zoom;
  const cx = (B.x0 + B.x1) / 2, cy = (B.y0 + B.y1) / 2;
  return { k, sx: x => (x - cx) * k + W / 2 + S.px, sy: y => -(y - cy) * k + Hh / 2 + S.py };
}
function isActive(i) {
  const sel = S.sel, cn = S.country;
  return (sel == null || clOf(i) === sel) && (cn == null || ctry(i) === cn) && !(S.own && D.ab[i]);
}
function draw() {
  if (!ctx || !W) return;
  ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
  ctx.clearRect(0, 0, W, Hh);
  const T = tf(), n = D.x.length, filt = S.sel != null || S.country != null || S.own;
  const base = S.zoom > 3 ? 2.6 : 2.0;

  for (let pass = 0; pass < 2; pass++) {
    for (let i = 0; i < n; i++) {
      const act = !filt || isActive(i);
      if ((pass === 0) === act) continue;
      const x = T.sx(D.x[i]), y = T.sy(D.y[i]);
      if (x < -6 || y < -6 || x > W + 6 || y > Hh + 6) continue;
      ctx.globalAlpha = act ? (filt ? .9 : .62) : .07;
      const cc = act ? colOf(clOf(i)) : "#555";
      ctx.fillStyle = cc;
      ctx.beginPath(); ctx.arc(x, y, base * (act && filt ? 1.15 : 1), 0, 6.2832); ctx.fill();
      if (act && window.PAL.light(cc)) { ctx.globalAlpha = .5; ctx.lineWidth = .6; ctx.strokeStyle = window.PAL.ink(cc); ctx.stroke(); }
    }
  }
  ctx.globalAlpha = 1;
  if (S.labels) drawLabels(T);
  if (S.hov >= 0) { ring(T, S.hov, "#17181b", 2); }
  if (S.passage != null) { ring(T, S.passage, "#17181b", 2.5); }
}
function ring(T, i, col, w) {
  ctx.lineWidth = w; ctx.strokeStyle = "#fff"; ctx.beginPath(); ctx.arc(T.sx(D.x[i]), T.sy(D.y[i]), 6.5, 0, 6.2832); ctx.stroke();
  ctx.lineWidth = 1.6; ctx.strokeStyle = col; ctx.beginPath(); ctx.arc(T.sx(D.x[i]), T.sy(D.y[i]), 6.5, 0, 6.2832); ctx.stroke();
}
function centres() {
  const key = S.level;
  if (labelsCache[key]) return labelsCache[key];
  const groups = {};
  for (let i = 0; i < D.x.length; i++) { (groups[clOf(i)] = groups[clOf(i)] || []).push(i); }
  const med = arr => { const s = arr.slice().sort((a, b) => a - b); return s[Math.floor(s.length / 2)]; };
  const out = [];
  for (const id in groups) { const idx = groups[id]; out.push({ id: +id, x: med(idx.map(i => D.x[i])), y: med(idx.map(i => D.y[i])), n: idx.length }); }
  return (labelsCache[key] = out);
}
function drawLabels(T) {
  ctx.textBaseline = "middle"; ctx.textAlign = "center";
  const placed = [];
  const list = centres().slice().sort((a, b) => b.n - a.n);
  const small = S.level === "sub";
  list.forEach(c => {
    if (S.sel != null && c.id !== S.sel) return;
    if (S.country != null && S.sel == null && c.n < 150) return;
    const cl = clusters()[c.id];
    const fs = small ? 11.5 : 14;
    ctx.font = "600 " + fs + "px 'Atkinson Next', 'Segoe UI', sans-serif";
    let name = cap(cl.name); const mw = small ? 150 : 190;
    const words = name.split(" "), lines = []; let cur = "";
    words.forEach(w => { const t = cur ? cur + " " + w : w; if (ctx.measureText(t).width > mw && cur) { lines.push(cur); cur = w; } else cur = t; });
    lines.push(cur);
    const x = T.sx(c.x), y = T.sy(c.y), lh = fs * 1.15, wd = Math.max(...lines.map(l => ctx.measureText(l).width)), ht = lh * lines.length;
    const box = { x0: x - wd / 2 - 4, x1: x + wd / 2 + 4, y0: y - ht / 2 - 3, y1: y + ht / 2 + 3 };
    if (x < 0 || x > W || y < 0 || y > Hh) return;
    if (placed.some(p => box.x0 < p.x1 && box.x1 > p.x0 && box.y0 < p.y1 && box.y1 > p.y0)) return;
    placed.push(box);
    lines.forEach((l, k) => {
      const ly = y - ht / 2 + lh * (k + .5);
      ctx.lineWidth = 4; ctx.strokeStyle = "rgba(255,255,255,.92)"; ctx.strokeText(l, x, ly);
      ctx.fillStyle = window.PAL.ink(colOf(c.id), "#ffffff"); ctx.fillText(l, x, ly);
    });
  });
}
function zoomBy(f, ax, ay) {
  const T = tf(); ax = ax == null ? W / 2 : ax; ay = ay == null ? Hh / 2 : ay;
  const nz = Math.max(1, Math.min(14, S.zoom * f)), r = nz / S.zoom;
  S.px = (S.px - (ax - W / 2)) * r + (ax - W / 2); S.py = (S.py - (ay - Hh / 2)) * r + (ay - Hh / 2);
  S.zoom = nz; if (nz === 1) { S.px = 0; S.py = 0; } draw();
}
function nearest(mx, my) {
  const T = tf(); let best = -1, bd = 100, filt = S.sel != null || S.country != null || S.own;
  for (let i = 0; i < D.x.length; i++) {
    if (filt && !isActive(i)) continue;
    const dx = T.sx(D.x[i]) - mx, dy = T.sy(D.y[i]) - my, d = dx * dx + dy * dy;
    if (d < bd) { bd = d; best = i; }
  }
  return best;
}
function bindMap() {
  const tip = $("#tip");
  let drag = null, moved = false;
  canvas.addEventListener("pointerdown", e => { try { canvas.setPointerCapture(e.pointerId); } catch (_) {} drag = { x: e.clientX, y: e.clientY, px: S.px, py: S.py }; moved = false; canvas.classList.add("drag"); });
  canvas.addEventListener("pointermove", e => {
    const r = canvas.getBoundingClientRect(), mx = e.clientX - r.left, my = e.clientY - r.top;
    if (drag) {
      const dx = e.clientX - drag.x, dy = e.clientY - drag.y;
      if (Math.abs(dx) + Math.abs(dy) > 4) moved = true;
      if (moved) { S.px = drag.px + dx; S.py = drag.py + dy; tip.style.opacity = 0; draw(); return; }
    }
    const h = nearest(mx, my);
    if (h !== S.hov) { S.hov = h; draw(); }
    if (h >= 0) {
      const d = D.docs[D.doc[h]], txt = D.txt[h];
      tip.replaceChildren(el("b", { text: d[0] }), el("em", { text: D.countries[d[1]] + " · " + d[2] + " · " + (LANG[d[3]] || d[3]) }), el("br"), document.createTextNode(txt.length > 150 ? txt.slice(0, 150).replace(/\s+\S*$/, "") + "…" : txt));
      tip.style.left = Math.min(window.innerWidth - 336, e.clientX + 14) + "px"; tip.style.top = (e.clientY + 16) + "px"; tip.style.opacity = 1;
    } else tip.style.opacity = 0;
  });
  canvas.addEventListener("pointerup", e => {
    canvas.classList.remove("drag");
    if (drag && !moved) {
      const r = canvas.getBoundingClientRect(), h = nearest(e.clientX - r.left, e.clientY - r.top);
      if (h >= 0) { S.passage = h; S.sel = clOf(h); render(); } else if (S.passage != null) { S.passage = null; render(); }
    }
    drag = null;
  });
  canvas.addEventListener("pointerleave", () => { tip.style.opacity = 0; if (S.hov !== -1) { S.hov = -1; draw(); } });
  canvas.addEventListener("wheel", e => { e.preventDefault(); const r = canvas.getBoundingClientRect(); zoomBy(e.deltaY < 0 ? 1.18 : 1 / 1.18, e.clientX - r.left, e.clientY - r.top); }, { passive: false });
  canvas.addEventListener("keydown", e => {
    const k = e.key;
    if (k === "+" || k === "=") zoomBy(1.4); else if (k === "-") zoomBy(1 / 1.4);
    else if (k === "ArrowLeft") { S.px += 40; draw(); } else if (k === "ArrowRight") { S.px -= 40; draw(); }
    else if (k === "ArrowUp") { S.py += 40; draw(); } else if (k === "ArrowDown") { S.py -= 40; draw(); }
    else if (k === "0") { S.zoom = 1; S.px = 0; S.py = 0; draw(); } else return;
    e.preventDefault();
  });
}

function renderMatrix() {

  const p = $("#p-matrix"); p.replaceChildren();
  const lv = S.mlv || "main", T = D.r3 && D.r3[lv], cl = lv === "main" ? MAINS : SUBS, col = id => lv === "main" ? MAIN_COL[id] : SUBCOL[id];
  const nC = D.countries.length, order = D.countries.map((_, i) => i).sort((a, b) => CNT.country[b] - CNT.country[a]);
  const rows = cl.slice().sort((a, b) => b.size - a.size);
  p.append(el("div", { class: "seg", role: "group", "aria-label": "Theme level" }, [["main", "Themes (" + MAINS.length + ")"], ["sub", "Sub-themes (" + SUBS.length + ")"]].map(([v, t]) =>
    el("button", { type: "button", "aria-pressed": lv === v, text: t, onclick: () => { S.mlv = v; renderMatrix(); } }))));
  const L = 300, T0 = 78, cw = 84, rh = lv === "main" ? 50 : 42, Wd = L + nC * cw + 30, Ht = T0 + rows.length * rh + 24;
  const svg = svgEl("svg", { viewBox: "0 0 " + Wd + " " + Ht, role: "group", "aria-label": "Share of each country's passages in each " + (lv === "main" ? "theme" : "sub-theme") });
  order.forEach((ci, j) => {
    const x = L + j * cw + cw / 2, thin = D.medical.single_country_docs[ci] < S.thin;
    svg.append(txt(x, 22, D.countries[ci], { "text-anchor": "middle", "font-size": 13, "font-weight": 600 }),
      txt(x, 40, fmt(CNT.country[ci]) + " passages", { "text-anchor": "middle", "font-size": 11, fill: "#52555c" }),
      txt(x, 55, D.medical.single_country_docs[ci] + " stories" + (thin ? " · thin" : ""), { "text-anchor": "middle", "font-size": 11, fill: thin ? "#a85d00" : "#52555c" }));
  });
  rows.forEach((m, r) => {
    const y = T0 + r * rh + rh / 2, k = T ? T.ids.indexOf(m.id) : -1, q = k >= 0 ? T.country.q[k] : null;
    svg.append(svgEl("line", { x1: 0, x2: Wd, y1: T0 + r * rh, y2: T0 + r * rh, stroke: "#eceae3" }));
    svg.append(svgEl("circle", { cx: 10, cy: y, r: 5, fill: col(m.id) }));
    svg.append(txt(24, y - (q != null ? 2 : -4), cap(m.name).length > 44 ? cap(m.name).slice(0, 43) + "…" : cap(m.name), { "font-size": 13 }));
    if (q != null) svg.append(txt(24, y + 13, q < .05 ? "differs between countries, q " + (q < .001 ? "< 0.001" : "= " + q.toFixed(3)) : "no difference, q = " + q.toFixed(2), { "font-size": 11, fill: q < .05 ? "#2b2620" : "#7a7166" }));
    order.forEach((ci, j) => {
      const n = CNT[lv][m.id][ci], share = n / CNT.country[ci], x = L + j * cw + cw / 2, rad = Math.sqrt(share / (lv === "main" ? .6 : .4)) * 21;
      const res = k >= 0 ? T.country.resid[ci][k] : 0, flag = k >= 0 && q < .05 && T.country.cell_q[ci][k] < .05;
      const g = svgEl("g", { class: "cell", tabindex: 0, role: "button", "aria-label": D.countries[ci] + ", " + m.name + ": " + pct(share, 0) + " of " + fmt(CNT.country[ci]) + " passages. Press to see them on the map." });
      g.append(svgEl("circle", { cx: x, cy: y, r: Math.max(2, Math.min(rad, rh / 2 - 2)), fill: col(m.id), stroke: window.PAL.light(col(m.id)) ? window.PAL.ink(col(m.id)) : "none", "stroke-width": .8 }));
      if (flag) g.append(svgEl("circle", { cx: x, cy: y, r: Math.max(6, Math.min(rad, rh / 2 - 2)) + 3.5, fill: "none", stroke: "#2b2620", "stroke-width": 1.6, "stroke-dasharray": res > 0 ? "none" : "3 2.5" }));
      const rr = Math.max(2, Math.min(rad, rh / 2 - 2)), big = rr > 13, outer = flag ? Math.max(6, rr) + 3.5 : rr;
      g.append(txt(x, y + 4, pct(share, 0), { "text-anchor": "middle", "font-size": big ? 12 : 11, fill: big ? window.PAL.onFill(col(m.id)) : "#17181b", dy: big ? 0 : -outer - 5 }));
      const go = () => { S.level = lv; S.sel = m.id; S.country = ci; S.passage = null; S.tab = "map"; render(); };
      g.addEventListener("click", go); g.addEventListener("keydown", e => { if (e.key === "Enter" || e.key === " ") { e.preventDefault(); go(); } });
      g.append(svgEl("title", {})); g.lastChild.textContent = D.countries[ci] + " · " + cap(m.name) + ": " + n + " of " + CNT.country[ci] + " passages" + (k >= 0 ? " · residual " + (res > 0 ? "+" : "") + res.toFixed(1) + (flag ? (res > 0 ? " (more than expected)" : " (less than expected)") : "") : "");
      svg.append(g);
    });
  });
  const notes = [];
  if (T) {
    const lost = T.ids.map((id, k) => k).filter(k => T.country.q[k] < .05 && T.country_single.q[k] >= .05).map(k => cap(T.themes[k]));
    notes.push("Test: shuffles of the country label between whole stories (4,000), corrected for the number of " + (lv === "main" ? "themes" : "sub-themes") + ". " + T.ids.filter((id, k) => T.country.q[k] < .05).length + " of " + T.ids.length + " differ between countries. A solid ring marks a country that writes about it more than expected, a dashed ring less than expected (both hold after correction).");
    notes.push("With only the stories tagged with one country, " + (lost.length ? "the picture stays the same except for " + lost.join(", ") + ", which rests on stories tagged with several countries." : "the picture stays the same."));
  }
  p.append(el("div", { class: "fig" }, [svg]), ...notes.map(n => el("p", { class: "fignote", text: n })),
    el("p", { class: "caption", text: "Each circle shows the share of a country’s passages that belong to a theme. Read across a row to see which countries a theme comes from, and down a column to see what a country’s reports talk about. Click a circle to see those passages on the map. “Thin” marks a country with fewer than 30 single-country stories: read its row with care. These shares show how visible a topic is in the reports. They do not count cases." }));
}

const TOPIC_MEANING = {
  "Trauma/surgery": "War wounds, blast and gunshot injuries, surgery",
  "Infectious disease": "Cholera, measles, malaria and other outbreaks",
  "Malnutrition": "Severe and acute malnutrition",
  "Mental health": "Mental health, psychological support, psychiatric care",
  "Maternal/newborn": "Pregnancy, birth and care of newborn babies",
  "Child health": "Child and paediatric care, children under five",
  "Sexual violence care": "Care after sexual and gender-based violence",
  "Vaccination": "Vaccination campaigns and immunisation",
  "Water/sanitation": "Drinking water, sanitation and hygiene",
  "Chronic disease": "Diabetes and other long-term illness",
  "Disability/rehab": "Physiotherapy, rehabilitation, prostheses",
  "Access & disruption": "Hospitals damaged, closed or forced to stop work"
};
function renderTopics() {
  const p = $("#p-topics"); p.replaceChildren();
  const M = D.medical, nC = D.countries.length, few = M.single_country_docs.map(n => n < 30);
  const topics = M.topics.slice().sort((a, b) => (b.all_pct || 0) - (a.all_pct || 0));
  p.append(el("p", { class: "lead2", text: "How often do the reports from each country mention twelve medical topics? Each box is the share of a country’s stories that mention the topic. Read along a row to compare countries: within each row, the darkest box is the country that mentions the topic most." }));
  const t = el("table", { class: "heat topics" });
  const hr = el("tr", {}, [el("th", { class: "rh", text: "Medical topic" })]);
  D.countries.forEach((c, i) => hr.append(el("th", { scope: "col" }, [el("span", { text: c }), el("small", { text: M.single_country_docs[i] + " stories" + (few[i] ? " · few" : "") })])));
  hr.append(el("th", { scope: "col", class: "allc" }, [el("span", { text: "All" }), el("small", { text: "8 countries" })]));
  t.append(el("thead", {}, [hr]));
  const tb = el("tbody");
  topics.forEach(tp => {
    const vals = tp.rows.map(v => v ? v[1] : 0), mx = Math.max(...vals) || 1, ok = tp.precision && tp.precision.informative;
    const tr = el("tr", {}, [el("th", { scope: "row", class: "rh" }, [el("span", { text: tp.long }), el("small", { text: (TOPIC_MEANING[tp.name] || "") }), ok ? "" : el("small", { class: "unc", text: "† search not confirmed" })])]);
    tp.rows.forEach((v, ci) => {
      if (!v) { tr.append(el("td", { class: "na", text: "–" })); return; }
      const bg = window.PAL.heat(v[1] / mx), dark = window.PAL.lum(bg) < .3;
      tr.append(el("td", { class: few[ci] ? "few" : "", style: "background:" + bg + ";color:" + (dark ? "#fff" : "#1a1a1a"),
        title: D.countries[ci] + " · " + tp.long + ": " + v[0] + " of " + M.single_country_docs[ci] + " stories (" + v[1].toFixed(1) + "%), 95% interval " + v[2].toFixed(0) + " to " + v[3].toFixed(0) + "%" + (few[ci] ? ". Few stories: read with care." : "") }, [Math.round(v[1]) + "%"]));
    });
    tr.append(el("td", { class: "allc", text: tp.all_pct != null ? Math.round(tp.all_pct) + "%" : "" }));
    tb.append(tr);
  });
  t.append(tb);
  p.append(el("div", { class: "heatwrap" }, [t]),
    el("p", { class: "fignote", text: "† For these topics the machine check could not tell good matches from bad ones, so some counted mentions may be false; the table below gives the details. Only stories about one country are counted (one story can mention several topics). Countries marked “few” have fewer than 30 such stories, so their shares can move a lot. As everywhere on this page, a share shows how often the reports write about a topic." }));
  window.MSFX.topicsExtra(p);
}

function buildGauges() {
  const plain = {
    "position between no themes and clean themes": ["Are there real themes at all?", "0 means the passages behave like data with no themes, 1 like data with clean ones."],
    "theme agreement under resampling": ["Do the same themes come back?", "Agreement between these themes and the themes found again on 80% of the passages (adjusted Rand index)."],
    "second coder against the clustering": ["Does a second coder agree?", "A language model acted as second coder on 180 passages (Cohen’s kappa). No person has coded a sample yet."],
    "summaries kept": ["Were the summaries grounded?", "Share of theme summaries that stayed after a check against the passages."]
  };
  const g = $("#gauges");
  D.trust.forEach(t => {
    const pl = plain[t.label] || [t.label, t.note];
    const below = t.floor != null && t.value < t.floor;
    g.append(el("div", { class: "gauge" }, [el("h4", { text: pl[0] }),
      el("div", { class: "gval", text: t.value.toFixed(2) }),
      el("div", { class: "gtrack", role: "img", "aria-label": t.value.toFixed(2) + (t.floor != null ? ", minimum " + t.floor : "") }, [el("b", { style: "width:" + (t.value * 100) + "%" }), t.floor != null ? el("u", { style: "left:" + (t.floor * 100) + "%" }) : ""]),
      el("p", { class: "gnote" }, [t.floor != null ? el("span", { class: below ? "below" : "ok", text: below ? "Below the minimum we set (" + t.floor + "). " : "Above the minimum we set (" + t.floor + "). " }) : "", pl[1]])]));
  });
}

function svgEl(tag, attrs) { const e = document.createElementNS("http://www.w3.org/2000/svg", tag); for (const k in attrs) e.setAttribute(k, attrs[k]); return e; }
function txt(x, y, s, attrs) { const e = svgEl("text", Object.assign({ x, y }, attrs || {})); e.textContent = s; return e; }
})();
