(function () {
"use strict";
const X = window.MSFX = {};
let A, D, G, QI, NT = null;
const QN = ["2023 Q1", "2023 Q2", "2023 Q3", "2023 Q4", "2024 Q1", "2024 Q2", "2024 Q3", "2024 Q4", "2025 Q1", "2025 Q2", "2025 Q3", "2025 Q4"];
const THIN_Q = 200;
const LANGNAME = { en: "English", fr: "French", es: "Spanish", de: "German" };

X.init = function (a) {
  A = a; D = a.D;
  G = { main: A.MAINS.map(() => []), sub: A.SUBS.map(() => []) };
  QI = new Int8Array(D.x.length);
  for (let i = 0; i < D.x.length; i++) {
    G.main[D.main[i]].push(i); G.sub[D.sub[i]].push(i);
    const dt = D.docs[D.doc[i]][2];
    QI[i] = Math.max(0, Math.min(11, (+dt.slice(0, 4) - 2023) * 4 + Math.floor((+dt.slice(5, 7) - 1) / 3)));
  }
};

const el = (...a) => A.el(...a), svgEl = (...a) => A.svgEl(...a), svgTxt = (...a) => A.txt(...a);
const fmt = n => A.fmt(n), pct = (v, d) => A.pct(v, d), cap = s => A.cap(s);
const pool = (level, id) => level === "main" ? G.main[id] : G.sub[id];
const fitOf = (level, i) => level === "main" ? D.fm[i] : D.fs[i];
const colour = (level, id) => level === "main" ? A.MAIN_COL[id] : A.SUBCOL[id];
const clusterOf = (level, id) => (level === "main" ? A.MAINS : A.SUBS)[id];
const norm = s => s.normalize("NFD").replace(/[̀-ͯ]/g, "").toLowerCase();
const ctryOf = i => D.docs[D.doc[i]][1];
function hash(s) { let h = 2166136261; for (let k = 0; k < s.length; k++) { h ^= s.charCodeAt(k); h = Math.imul(h, 16777619); } return h >>> 0; }
function rng(seed) { let a = seed >>> 0; return () => { a = (a + 0x6D2B79F5) | 0; let t = Math.imul(a ^ (a >>> 15), 1 | a); t = (t + Math.imul(t ^ (t >>> 7), 61 | t)) ^ t; return ((t ^ (t >>> 14)) >>> 0) / 4294967296; }; }
function csvText(rows) { return "﻿" + rows.map(r => r.map(v => { const s = v == null ? "" : String(v); return /[",\n]/.test(s) ? '"' + s.replace(/"/g, '""') + '"' : s; }).join(",")).join("\r\n"); }
function download(name, rows) {
  const blob = new Blob([csvText(rows)], { type: "text/csv;charset=utf-8" });
  const a = el("a", { href: URL.createObjectURL(blob), download: name });
  document.body.append(a); a.click(); a.remove(); setTimeout(() => URL.revokeObjectURL(a.href), 2000);
}
function bar(frac, colr, w) { return el("span", { class: "mini", style: w ? "width:" + w + "px" : null }, [el("b", { style: "width:" + Math.max(0, Math.min(100, frac * 100)).toFixed(1) + "%;background:" + (colr || "var(--ink)") })]); }

const cache = {};
function oneEach(list, n) { const seen = new Set(), sig = new Set(), out = []; for (const i of list) { const d = D.doc[i], s = norm(D.txt[i].slice(0, 60)); if (seen.has(d) || sig.has(s)) continue; seen.add(d); sig.add(s); out.push(i); if (out.length >= n) break; } return out; }
function spread(list, n, level) {
  const top = list.slice(0, 500), seen = new Set(), sig = new Set(), cc = {}, out = [];
  while (out.length < n) {
    let best = -1, bs = -1e9;
    for (const i of top) {
      if (seen.has(D.doc[i]) || out.includes(i) || sig.has(norm(D.txt[i].slice(0, 60)))) continue;
      const s = fitOf(level, i) - 10 * (cc[ctryOf(i)] || 0);
      if (s > bs) { bs = s; best = i; }
    }
    if (best < 0) break;
    out.push(best); seen.add(D.doc[best]); sig.add(norm(D.txt[best].slice(0, 60))); cc[ctryOf(best)] = (cc[ctryOf(best)] || 0) + 1;
  }
  return out;
}
X.pick = function (level, id) {
  const key = level + id; if (cache[key]) return cache[key];
  const p = pool(level, id), ok = (i, lo, hi) => D.txt[i].length >= lo && D.txt[i].length <= hi;
  const typical = spread(p.filter(i => !D.ab[i] && !D.lc[i] && ok(i, 300, 1300)).sort((a, b) => fitOf(level, b) - fitOf(level, a)), 6, level);
  const edge = oneEach(p.filter(i => ok(i, 250, 1300)).sort((a, b) => fitOf(level, a) - fitOf(level, b)), 4);
  const r = rng(hash(key + "msf-2026")), sh = p.filter(i => ok(i, 200, 1400) && !typical.includes(i)).map(i => [r(), i]).sort((a, b) => a[0] - b[0]).map(a => a[1]);
  return (cache[key] = { typical, random: oneEach(sh, 4), edge });
};

function termRegex(terms) {
  if (!terms || !terms.length) return null;
  const cls = { a: "aàáâãäå", e: "eèéêë", i: "iìíîï", o: "oòóôõö", u: "uùúûü", c: "cç", n: "nñ" };
  const parts = terms.map(t => Array.from(t).map(ch => { const l = ch.toLowerCase(); return cls[l] ? "[" + cls[l] + "]" : ch.replace(/[.*+?^${}()|[\]\\]/g, "\\$&"); }).join(""));
  try { return new RegExp("(" + parts.join("|") + ")", "gi"); } catch (e) { return null; }
}
function highlighted(text, re) {
  if (!re) return [document.createTextNode(text)];
  const out = []; let last = 0, m; re.lastIndex = 0;
  while ((m = re.exec(text))) { if (m.index > last) out.push(document.createTextNode(text.slice(last, m.index))); out.push(el("mark", { text: m[0] })); last = m.index + m[0].length; if (m[0].length === 0) re.lastIndex++; }
  if (last < text.length) out.push(document.createTextNode(text.slice(last)));
  return out;
}
X.passageCard = function (i, o) {
  o = o || {};
  const d = D.docs[D.doc[i]], text = D.txt[i], LIM = o.limit || 640;
  const art = el("article", { class: "pc" + (o.compact ? " compact" : "") });
  const head = el("div", { class: "pch" }, [
    el("span", { class: "lang", text: A.LANG[d[3]] || d[3].toUpperCase(), title: LANGNAME[d[3]] || d[3] }),
    el("span", { class: "pcc", text: D.countries[d[1]] }),
    d[6] ? el("span", { class: "tagx", text: "tagged for " + d[7].split("|").length + " countries", title: "ReliefWeb tags: " + d[7].replace(/\|/g, ", ") + ". The country shown is the first tag used in this study." }) : "",
    el("span", { class: "pcd", text: d[2] }), el("span", { class: "pcd", text: d[4] })]);
  const title = el("h5", {}, [el("a", { href: d[5], target: "_blank", rel: "noopener", text: d[0] })]);
  const re = termRegex(o.terms);
  const body = el("p", { class: "pct", lang: d[3] });
  const whole = text.length <= LIM;
  const cut = whole ? text : text.slice(0, LIM).replace(/\s+\S*$/, "") + "…";
  let open = whole;
  const paint = () => { body.replaceChildren(...highlighted(open ? text : cut, re)); };
  paint();
  art.append(head, title, body);
  if (!whole) art.append(el("button", { class: "lk", type: "button", text: "Show the whole passage", onclick: e => { open = !open; paint(); e.target.textContent = open ? "Show less" : "Show the whole passage"; } }));
  if (D.sm[i]) art.append(el("details", { class: "msum", open: o.sumOpen ? true : false }, [el("summary", { text: "Machine summary" }), el("p", { text: D.sm[i] }), el("p", { class: "small", text: "One line written by a language model. Check it against the passage." })]));
  const m = D.main[i], s = D.sub[i], f = D.fm[i] / 100;
  const foot = el("div", { class: "pcf" }, [
    el("button", { type: "button", class: "chipx", title: "Open the theme report", onclick: () => A.go.themes("main", m) }, [el("i", { style: "background:" + A.MAIN_COL[m] }), cap(A.MAINS[m].name)]),
    el("button", { type: "button", class: "chipx", title: "Open the sub-theme report", onclick: () => A.go.themes("sub", s) }, [el("i", { style: "background:" + A.SUBCOL[s] }), cap(A.SUBS[s].name)]),
    el("span", { class: "fitm", title: "Fit to its theme: " + f.toFixed(2) + " (silhouette). Higher means it sits more clearly inside the theme. Below 0 means it is closer to another theme." }, ["fit ", bar((f + .1) / .7, A.MAIN_COL[m], 46), " " + f.toFixed(2)]),
    D.ab[i] ? el("span", { class: "tag", text: "joined afterwards", title: "The density method left this passage unplaced. It was added to the nearest sub-theme afterwards." }) : "",
    D.lc[i] ? el("span", { class: "tag", text: "low confidence" }) : ""]);
  art.append(foot);
  if (!o.noactions) art.append(el("div", { class: "pca" }, [
    el("button", { type: "button", class: "lk", text: "Show on the map", onclick: () => A.go.map({ level: "main", sel: m, country: null, passage: i }) }),
    el("button", { type: "button", class: "lk", text: "Copy link", onclick: e => copyLink("#view=map&theme=" + m + "&passage=" + i, e.target) })]));
  return art;
};
function copyLink(h, btn) {
  const url = location.origin + location.pathname + h, old = btn.textContent;
  const done = () => { btn.textContent = "Link copied"; setTimeout(() => { btn.textContent = old; }, 1600); };
  try { navigator.clipboard.writeText(url).then(done, () => { location.hash = h; btn.textContent = "Link is in the address bar"; }); } catch (e) { location.hash = h; btn.textContent = "Link is in the address bar"; }
}

function squarify(items, x, y, w, h) {
  const total = items.reduce((s, a) => s + a.v, 0), k = w * h / total, rest = items.map(a => ({ a, area: a.v * k })), out = [];
  const worst = (row, sum, side) => row.reduce((m, r) => Math.max(m, Math.max(side * side * r.area / (sum * sum), sum * sum / (side * side * r.area))), 0);
  while (rest.length) {
    const side = Math.min(w, h);
    let row = [rest[0]], sum = rest[0].area, wv = worst(row, sum, side), n = 1;
    for (; n < rest.length; n++) { const nr = row.concat(rest[n]), ns = sum + rest[n].area, nw = worst(nr, ns, side); if (nw > wv) break; row = nr; sum = ns; wv = nw; }
    rest.splice(0, n);
    if (w >= h) { const cw = sum / h; let yy = y; row.forEach(r => { const rh = r.area / cw; out.push({ a: r.a, x, y: yy, w: cw, h: rh }); yy += rh; }); x += cw; w -= cw; }
    else { const rh = sum / w; let xx = x; row.forEach(r => { const rw = r.area / rh; out.push({ a: r.a, x: xx, y, w: rw, h: rh }); xx += rw; }); y += rh; h -= rh; }
  }
  return out;
}
function treemap() {
  const W = 1000, H = 300, svg = svgEl("svg", { viewBox: "0 0 " + W + " " + H, role: "group", "aria-label": "Treemap: nine themes and their sub-themes, sized by number of passages" });
  const tops = squarify(A.MAINS.map(m => ({ m, v: m.size })).sort((a, b) => b.v - a.v), 0, 0, W, H);
  const S = A.S;
  tops.forEach(t => {
    const m = t.a.m, kids = A.SUBS.filter(s => s.parent === m.id).sort((a, b) => b.size - a.size);
    const g = svgEl("g", {});
    const subs = squarify(kids.map(s => ({ s, v: s.size })), t.x, t.y, t.w, t.h);
    subs.forEach(r => {
      const s = r.a.s, on = S.level === "sub" && S.sel === s.id;
      const rect = svgEl("rect", { x: r.x + .75, y: r.y + .75, width: Math.max(0, r.w - 1.5), height: Math.max(0, r.h - 1.5), fill: A.SUBCOL[s.id], stroke: on ? "#17181b" : "#fff", "stroke-width": on ? 3 : 1, class: "tm", tabindex: 0, role: "button", "aria-label": "Sub-theme " + s.name + ", " + s.size + " passages. Open its report." });
      rect.append(svgEl("title", {})); rect.lastChild.textContent = cap(s.name) + " · " + fmt(s.size) + " passages (" + pct(s.share) + ")";
      const go = () => A.go.themes("sub", s.id);
      rect.addEventListener("click", go); rect.addEventListener("keydown", e => { if (e.key === "Enter" || e.key === " ") { e.preventDefault(); go(); } });
      g.append(rect);
      if (r.w > 92 && r.h > 34) {
        const words = cap(s.name).split(" "), lines = []; let cur = "";
        const maxc = Math.max(10, Math.floor((r.w - 14) / 6.6));
        words.forEach(w => { const tt = cur ? cur + " " + w : w; if (tt.length > maxc && cur) { lines.push(cur); cur = w; } else cur = tt; }); lines.push(cur);
        lines.slice(0, Math.max(1, Math.floor((r.h - 14) / 14)) ).forEach((l, k) => { const tx = svgTxt(r.x + 8, r.y + 19 + k * 14, l, { "font-size": 12, fill: window.PAL.onFill(A.SUBCOL[s.id]), "pointer-events": "none" }); g.append(tx); });
      }
    });

    const on = S.level === "main" && S.sel === m.id;
    const out = svgEl("rect", { x: t.x + 1, y: t.y + 1, width: t.w - 2, height: t.h - 2, fill: "none", stroke: on ? "#17181b" : A.MAIN_COL[m.id], "stroke-width": on ? 3.5 : 2, class: "tmo", "pointer-events": "none" });
    g.append(out);
    svg.append(g);
  });

  const names = el("div", { class: "tmnames" }, A.MAINS.slice().sort((a, b) => b.size - a.size).map(m => el("button", { type: "button", class: "chip", "aria-pressed": S.level === "main" && S.sel === m.id, onclick: () => A.go.themes("main", m.id) }, [el("span", { class: "dot", style: "background:" + A.MAIN_COL[m.id] }), cap(m.name) + " " + pct(m.share, 0)])));
  return el("div", { class: "fig tmwrap" }, [svg, names]);
}

function overview() {
  const grid = el("div", { class: "tgrid" });
  A.MAINS.slice().sort((a, b) => b.size - a.size).forEach(m => {
    const first = m.summary ? m.summary.split(/(?<=\.)\s/)[0] : "";
    grid.append(el("button", { type: "button", class: "tcard", style: "border-top-color:" + A.MAIN_COL[m.id], onclick: () => A.go.themes("main", m.id) }, [
      el("h4", { text: cap(m.name) }),
      el("p", { class: "tmeta" }, [el("b", { text: pct(m.share, 0) }), " of passages · " + fmt(m.size) + " · " + fmt(m.documents) + " stories", m.flags.includes("incoherent") ? el("span", { class: "tag", text: "mixed" }) : ""]),
      first ? el("p", { class: "tsum", text: first }) : "",
      el("div", { class: "words" }, m.terms.slice(0, 5).map(t => el("span", { text: t[0] }))),
      el("span", { class: "go", text: "Open the report →" })]));
  });
  return grid;
}

const stabilityBand = v => v >= .85 ? "highly stable" : v >= .75 ? "stable" : v >= .6 ? "uncertain" : "unstable";
function statsFor(c) {
  const p = pool(c.level, c.id), nC = D.countries.length;
  const cc = new Array(nC).fill(0), ll = {}, qq = new Array(12).fill(0), joined = p.reduce((s, i) => s + D.ab[i], 0);
  p.forEach(i => { cc[ctryOf(i)]++; const l = D.docs[D.doc[i]][3]; ll[l] = (ll[l] || 0) + 1; qq[QI[i]]++; });
  return { p, cc, ll, qq, joined };
}
const QT = new Array(12).fill(0);
function quarterTotals() { if (!QT.some(v => v)) for (let i = 0; i < D.x.length; i++) QT[QI[i]]++; return QT; }
function trendChart(st, c) {
  const W = 560, H = 120, L = 6, B = 22, T = 8, bw = (W - L) / 12, qt = quarterTotals();
  const sh = st.qq.map((v, k) => qt[k] ? v / qt[k] : 0), mx = Math.max(.05, ...sh) * 1.15;
  const svg = svgEl("svg", { viewBox: "0 0 " + W + " " + H, role: "img", "aria-label": "Share of each quarter's passages that belong to this theme, 2023 to 2025" });
  const y = v => T + (H - T - B) * (1 - v / mx);
  svg.append(svgEl("line", { x1: L, x2: W, y1: y(0), y2: y(0), stroke: "#c9c4b6" }));
  sh.forEach((v, k) => {
    const thin = qt[k] < THIN_Q;
    const r = svgEl("rect", { x: L + k * bw + 3, y: y(v), width: bw - 6, height: Math.max(0, y(0) - y(v)), fill: colour(c.level, c.id), "fill-opacity": thin ? .4 : .9 });
    r.append(svgEl("title", {})); r.lastChild.textContent = QN[k] + ": " + st.qq[k] + " of " + qt[k] + " passages (" + pct(v, 0) + ")" + (thin ? ". Few passages in this quarter." : "");
    svg.append(r);
    if (k % 2 === 0) svg.append(svgTxt(L + k * bw + bw / 2, H - 6, QN[k].replace(" ", " "), { "font-size": 10.5, "text-anchor": "middle", fill: "#52555c" }));
  });
  svg.append(svgEl("line", { x1: L, x2: W, y1: y(c.share), y2: y(c.share), stroke: "#17181b", "stroke-dasharray": "4 3", "stroke-width": 1 }), svgTxt(W - 2, y(c.share) - 4, "whole period " + pct(c.share, 0), { "font-size": 10.5, "text-anchor": "end", fill: "#17181b" }));
  return svg;
}
function report(c) {
  const S = A.S, st = statsFor(c), col = colour(c.level, c.id), wrap = el("div", { class: "rep", style: "--tc:" + col });
  const parent = c.level === "sub" ? A.MAINS[c.parent] : null;
  wrap.append(el("nav", { class: "crumbs", "aria-label": "Where you are" }, [
    el("button", { type: "button", class: "lk", text: "All themes", onclick: () => A.go.themes("main", null) }), " › ",
    parent ? [el("button", { type: "button", class: "lk", text: cap(parent.name), onclick: () => A.go.themes("main", parent.id) }), " › "] : "", el("b", { text: cap(c.name) })].flat()));
  wrap.append(el("p", { class: "kicker", text: c.level === "main" ? "Theme " + (c.id + 1) + " of " + A.MAINS.length : "Sub-theme of “" + cap(parent.name) + "”" }), el("h3", { text: cap(c.name) }));
  const nCo = st.cc.filter(v => v > 0).length;
  wrap.append(el("div", { class: "facts small" }, [
    [fmt(c.size), "passages"], [pct(c.share), "of the corpus"], [fmt(c.documents), "stories"], [String(nCo), "countries"],
    [(Math.abs(c.coherence) < .005 ? 0 : c.coherence).toFixed(2), "coherence"]].map(a => el("div", { class: "fact" }, [el("b", { text: a[0] }), el("span", { text: a[1] })]))));
  const warn = [];
  if (c.flags.includes("incoherent")) warn.push("Mixed theme. Its passages do not share one clear topic: the average fit of its passages is no better than chance (coherence 0.00). Read it as a collection of related subjects, and use its sub-themes.");
  if (c.flags.includes("not reproduced by a second model")) warn.push("A second embedding model grouped this part differently" + (c.jaccard2 != null ? " (overlap " + c.jaccard2.toFixed(2) + " of 1)" : "") + ". Treat its edges as uncertain.");
  warn.forEach(w => wrap.append(el("div", { class: "warnbox", text: w })));
  if (c.summary) wrap.append(el("p", { class: "summary", text: c.summary }), el("p", { class: "small", text: "Summary written by a language model and kept only after a check against the passages." }));

  const solid = el("div", { class: "sec" }, [el("h4", { text: "How solid is it?" })]);
  const rows = [];
  rows.push(["Coherence " + (Math.abs(c.coherence) < .005 ? 0 : c.coherence).toFixed(2), "The average fit of its passages: how clearly they sit together and away from other themes (silhouette, from −1 to 1). Higher is tighter."]);
  if (c.jaccard_seeds != null) { const mn = Math.min(c.jaccard_seeds, c.jaccard_passages); rows.push(["Found again: " + c.jaccard_seeds.toFixed(2) + " across seeds, " + c.jaccard_passages.toFixed(2) + " across resamples", "The same group came back when the grouping was repeated with other random seeds and on 80% of the passages (1 means identical). Band: " + stabilityBand(mn) + " (bands after Hennig, 2008)."]); }
  if (c.jaccard2 != null) rows.push(["Second embedding model: overlap " + c.jaccard2.toFixed(2), "How much of this group a second model found as one group (1 means identical)."]);
  rows.push(["Placed by the method: " + fmt(c.size - st.joined) + " of " + fmt(c.size) + " (" + pct((c.size - st.joined) / c.size, 0) + ")", fmt(st.joined) + " passages were first left unplaced by the density method and joined to the nearest centre afterwards."]);
  solid.append(el("dl", { class: "dl" }, rows.flatMap(r => [el("dt", { text: r[0] }), el("dd", { text: r[1] })])));
  wrap.append(solid);

  if (c.terms.length) {
    const mx = Math.max(...c.terms.map(t => t[1]));
    wrap.append(el("div", { class: "sec" }, [el("h4", { text: "Words that set it apart" }), el("p", { class: "small", text: "Words that are much more frequent here than elsewhere. The bar shows how much more (lift); the number is how many passages of the theme use the word." }),
      el("div", { class: "wlist" }, c.terms.slice(0, 10).map(t => el("div", { class: "wrow" }, [el("span", { class: "wt", text: t[0] }), bar(t[1] / mx, col), el("span", { class: "wn", text: "×" + t[1].toFixed(1) + " · " + fmt(t[2]) })])))]));
  }

  const order = D.countries.map((_, i) => i).filter(i => st.cc[i] > 0).sort((a, b) => st.cc[b] / c.size - st.cc[a] / c.size);
  const tbl = el("table", { class: "tbl" }, [el("thead", {}, [el("tr", {}, [el("th", { text: "Country" }), el("th", { class: "r", text: "Passages" }), el("th", { text: "Share of this theme" }), el("th", { text: "Share of the country’s passages" })])]),
    el("tbody", {}, order.map(ci => el("tr", {}, [
      el("td", {}, [el("button", { type: "button", class: "lk", text: D.countries[ci], title: "Show these passages on the map", onclick: () => A.go.map({ level: c.level, sel: c.id, country: ci, passage: null }) })]),
      el("td", { class: "r num", text: fmt(st.cc[ci]) }),
      el("td", {}, [bar(st.cc[ci] / c.size, col, 110), " " + pct(st.cc[ci] / c.size, 0)]),
      el("td", {}, [bar(st.cc[ci] / A.CNT.country[ci] / 0.7, col, 110), " " + pct(st.cc[ci] / A.CNT.country[ci], 0)])])))]);
  wrap.append(el("div", { class: "sec" }, [el("h4", { text: "Where it is reported" }), el("p", { class: "small", text: "Two different readings. The first shows which countries this theme comes from. The second shows how much of each country’s reporting is about it. A country with many reports weighs more in the first." }), el("div", { class: "scrollx" }, [tbl])]));

  const lang = Object.keys(st.ll).sort((a, b) => st.ll[b] - st.ll[a]);
  wrap.append(el("div", { class: "sec two" }, [
    el("div", {}, [el("h4", { text: "Over time" }), el("p", { class: "small", text: "Share of each quarter’s passages that belong to this theme. Lighter bars: quarters with few passages. Reporting follows events, so a rise means more reporting. It may or may not mean more suffering." }), el("div", { class: "fig thin" }, [trendChart(st, c)])]),
    el("div", {}, [el("h4", { text: "Languages" }), el("div", { class: "words" }, lang.map(l => el("span", { text: (LANGNAME[l] || l) + " " + fmt(st.ll[l]) }))), el("p", { class: "small", style: "margin-top:8px", text: "Passages are shown in the language of the report. Nothing was translated." })])]));

  if (c.level === "main") {
    const kids = A.SUBS.filter(s => s.parent === c.id).sort((a, b) => b.size - a.size);
    if (kids.length > 1) wrap.append(el("div", { class: "sec" }, [el("h4", { text: "Sub-themes inside" }),
      el("div", { class: "subl" }, kids.map(k => el("button", { type: "button", class: "subrow", onclick: () => A.go.themes("sub", k.id) }, [el("i", { style: "background:" + A.SUBCOL[k.id] }), el("span", { class: "nm", text: cap(k.name) }), el("span", { class: "num", text: fmt(k.size) }), bar(k.size / c.size, A.SUBCOL[k.id], 90), k.flags.includes("not reproduced by a second model") ? el("span", { class: "tag", text: "not reproduced" }) : ""])))]));
  } else {
    const sibs = A.SUBS.filter(s => s.parent === c.parent && s.id !== c.id);
    if (sibs.length) wrap.append(el("div", { class: "sec" }, [el("h4", { text: "Other sub-themes of the same theme" }), el("div", { class: "kids" }, sibs.map(k => el("button", { type: "button", text: cap(k.name) + " (" + fmt(k.size) + ")", onclick: () => A.go.themes("sub", k.id) })))]));
  }

  const pk = X.pick(c.level, c.id), qt = S.qt || "typical";
  const desc = { typical: "The passages that fit this theme best. Chosen by a fixed rule: highest fit, placed by the method itself, one per story, spread over countries. They show the centre of the theme.", random: "Four passages drawn at random with a fixed seed, so every visitor sees the same four. They show the ordinary middle of the theme.", edge: "The passages that fit worst. If they still look like the theme, the theme is solid. If they look like something else, the theme is loose at its edges." };
  const qbox = el("div", { class: "sec" }, [el("h4", { text: "Passages" }),
    el("div", { class: "seg", role: "group", "aria-label": "Which passages" }, [["typical", "Typical (" + pk.typical.length + ")"], ["random", "At random (" + pk.random.length + ")"], ["edge", "On the edge (" + pk.edge.length + ")"]].map(a => el("button", { type: "button", "aria-pressed": qt === a[0], text: a[1], onclick: () => { S.qt = a[0]; A.render(); } }))),
    el("p", { class: "small", text: desc[qt] }),
    el("div", { class: "pclist" }, pk[qt].map(i => X.passageCard(i)))]);
  wrap.append(qbox);

  wrap.append(el("div", { class: "acts" }, [
    el("button", { type: "button", class: "btn", text: "Show on the map", onclick: () => A.go.map({ level: c.level, sel: c.id, country: null, passage: null }) }),
    el("button", { type: "button", class: "btn", text: "Read all " + fmt(c.size) + " passages", onclick: () => A.go.reader({ th: [c.level, c.id] }) }),
    el("button", { type: "button", class: "btn", text: "Download this theme’s numbers (CSV)", onclick: () => download("theme-" + c.key + ".csv", themeRows(c, st, order)) }),
    el("button", { type: "button", class: "btn", text: "Copy link", onclick: e => copyLink("#view=themes&level=" + c.level + "&theme=" + c.id, e.target) })]));
  return wrap;
}
function themeRows(c, st, order) {
  const r = [["item", "value"], ["run", D.header.run], ["level", c.level], ["name", c.name], ["passages", c.size], ["share of corpus", c.share], ["stories", c.documents], ["coherence (mean silhouette)", c.coherence], ["passages joined afterwards", st.joined], ["summary (language-model written)", c.summary], [], ["country", "passages", "share of theme", "share of country's passages"]];
  order.forEach(ci => r.push([D.countries[ci], st.cc[ci], (st.cc[ci] / c.size).toFixed(4), (st.cc[ci] / A.CNT.country[ci]).toFixed(4)]));
  r.push([], ["word", "lift", "passages"]); c.terms.forEach(t => r.push(t));
  r.push([], ["quarter", "passages in theme", "passages in quarter"]); const qt = quarterTotals(); st.qq.forEach((v, k) => r.push([QN[k], v, qt[k]]));
  return r;
}
X.renderThemes = function (panel) {
  panel.replaceChildren();
  panel.append(el("p", { class: "small", style: "max-width:84ch", text: "The nine themes and their fifteen sub-themes, sized by number of passages. Pick one to read its report: what it is about, how solid it is, where and when it appears, and passages that stand for it." }), treemap());
  const c = A.selCluster();
  panel.append(c ? report(c) : overview());
};

function normAll() { if (!NT) NT = D.txt.map((t, i) => norm(D.docs[D.doc[i]][0] + " " + t)); return NT; }
function parseQuery(q) {
  const out = []; q.replace(/"([^"]+)"|(\S+)/g, (m, a, b) => { const t = norm((a || b).trim()); if (t) out.push(t); return ""; }); return out;
}
X.search = function (R) {
  const terms = parseQuery(R.q), nt = terms.length ? normAll() : null, out = [];
  for (let i = 0; i < D.x.length; i++) {
    if (R.th && (R.th[0] === "main" ? D.main[i] : D.sub[i]) !== R.th[1]) continue;
    if (R.ctr.length && !R.ctr.includes(ctryOf(i))) continue;
    if (R.lang.length && !R.lang.includes(D.docs[D.doc[i]][3])) continue;
    if (R.year && D.docs[D.doc[i]][2].slice(0, 4) !== R.year) continue;
    if (R.place === "own" && D.ab[i]) continue;
    if (R.place === "joined" && !D.ab[i]) continue;
    if (nt && !terms.every(t => nt[i].includes(t))) continue;
    out.push(i);
  }
  const lvl = R.th ? R.th[0] : "main", date = i => D.docs[D.doc[i]][2];
  if (R.sort === "fit") out.sort((a, b) => fitOf(lvl, b) - fitOf(lvl, a));
  else if (R.sort === "new") out.sort((a, b) => date(b) < date(a) ? -1 : date(b) > date(a) ? 1 : 0);
  else if (R.sort === "old") out.sort((a, b) => date(a) < date(b) ? -1 : date(a) > date(b) ? 1 : 0);
  else { const r = rng(R.seed || 1); const k = out.map(i => [r(), i]).sort((a, b) => a[0] - b[0]); return { idx: k.map(a => a[1]), terms }; }
  return { idx: out, terms };
};
X.renderReader = function (panel) {
  const R = A.S.R; panel.replaceChildren();
  const results = el("div", { id: "rres" });
  const stats = el("div", { id: "rstats" });
  let timer = null;
  const upd = (keepPage) => { if (!keepPage) R.shown = 12; A.writeHash(); paintResults(); };
  const qin = el("input", { type: "search", id: "rq", class: "qin", placeholder: "Search the passages (one or more words, or “a phrase”)", value: R.q, "aria-label": "Search the passages", oninput: e => { R.q = e.target.value; clearTimeout(timer); timer = setTimeout(upd, 180); } });
  const thSel = el("select", { "aria-label": "Theme", onchange: e => { const v = e.target.value; R.th = v ? [v[0] === "m" ? "main" : "sub", +v.slice(1)] : null; upd(); } }, [el("option", { value: "", text: "All themes" }),
    ...A.MAINS.flatMap(m => [el("option", { value: "m" + m.id, text: cap(m.name), selected: R.th && R.th[0] === "main" && R.th[1] === m.id }), ...A.SUBS.filter(s => s.parent === m.id).map(s => el("option", { value: "s" + s.id, text: "  └ " + cap(s.name), selected: R.th && R.th[0] === "sub" && R.th[1] === s.id }))])]);
  const yrSel = el("select", { "aria-label": "Year", onchange: e => { R.year = e.target.value || null; upd(); } }, [el("option", { value: "", text: "All years" }), ...["2023", "2024", "2025"].map(y => el("option", { value: y, text: y, selected: R.year === y }))]);
  const plSel = el("select", { "aria-label": "How the passage was placed", onchange: e => { R.place = e.target.value; upd(); } }, [["all", "Any placement"], ["own", "Placed by the method"], ["joined", "Joined afterwards"]].map(a => el("option", { value: a[0], text: a[1], selected: R.place === a[0] })));
  const soSel = el("select", { "aria-label": "Sort", onchange: e => { R.sort = e.target.value; if (R.sort === "random") R.seed = (Math.random() * 1e9) | 0; upd(); } }, [["fit", "Best fit first"], ["new", "Newest first"], ["old", "Oldest first"], ["random", "Shuffled"]].map(a => el("option", { value: a[0], text: a[1], selected: R.sort === a[0] })));
  const chips = (arr, get, label, names) => el("div", { class: "opts", role: "group", "aria-label": label }, arr.map(v => el("button", { type: "button", class: "chip", "aria-pressed": get().includes(v), text: names(v), onclick: e => { const g = get(), k = g.indexOf(v); k >= 0 ? g.splice(k, 1) : g.push(v); e.target.setAttribute("aria-pressed", k < 0); upd(); } })));
  panel.append(

    el("div", { class: "rbar" }, [qin, thSel, yrSel, el("button", { type: "button", class: "btn", text: "Clear", onclick: () => { Object.assign(R, A.newR()); A.render(); } })]),
    el("div", { class: "rchips" }, [chips(D.countries.map((_, i) => i), () => R.ctr, "Countries", i => D.countries[i]), chips(["en", "fr", "es", "de"], () => R.lang, "Languages", l => LANGNAME[l])]),
    stats, results);
  function paintResults() {
    const t0 = X.search(R), idx = t0.idx, re = termRegex(t0.terms.map(t => t));

    const byM = A.MAINS.map(() => 0); idx.forEach(i => byM[D.main[i]]++);
    stats.replaceChildren(el("p", { class: "rcount" }, [el("b", { text: fmt(idx.length) }), " of " + fmt(D.x.length) + " passages" + (R.q ? " contain “" + R.q.trim() + "”" : "")]),
      idx.length ? el("div", { class: "rdist", "aria-label": "Themes among the results" }, A.MAINS.map(m => byM[m.id] ? el("button", { type: "button", class: "rd", title: cap(m.name) + ": " + fmt(byM[m.id]) + " passages. Click to keep only this theme.", style: "flex:" + byM[m.id] + ";background:" + A.MAIN_COL[m.id], onclick: () => { R.th = ["main", m.id]; A.render(); }, "aria-label": cap(m.name) + ", " + byM[m.id] }) : "")) : "",
      idx.length ? el("p", { class: "small", text: "Colours show the theme of each result. Click a colour to keep that theme." }) : "");
    results.replaceChildren();
    if (!idx.length) { results.append(el("p", { class: "loading", text: "No passage matches. Try fewer words, or remove a filter." })); return; }
    const hl = termRegex(parseQuery(R.q).map(s => s)), shown = idx.slice(0, R.shown);
    results.append(...shown.map(i => X.passageCard(i, { terms: parseQuery(R.q), sumOpen: false })));
    if (idx.length > shown.length) results.append(el("button", { type: "button", class: "btn more", text: "Show " + Math.min(12, idx.length - shown.length) + " more (" + fmt(idx.length - shown.length) + " left)", onclick: () => { R.shown += 12; paintResults(); } }));
    else results.append(el("p", { class: "small", style: "text-align:center", text: "End of the results." }));
  }
  paintResults();
};

X.renderTime = function (panel) {
  panel.replaceChildren(); const S = A.S;
  const tc = S.tc, own = S.tm === "own", nQ = 12;
  const cnt = A.MAINS.map(() => new Array(nQ).fill(0)), tot = new Array(nQ).fill(0), docs = Array.from({ length: nQ }, () => new Set());
  for (let i = 0; i < D.x.length; i++) { if (tc != null && ctryOf(i) !== tc) continue; cnt[D.main[i]][QI[i]]++; tot[QI[i]]++; docs[QI[i]].add(D.doc[i]); }
  const all = tot.reduce((s, v) => s + v, 0);
  const share = (m, k) => tot[k] ? cnt[m][k] / tot[k] : 0;
  const order = A.MAINS.slice().sort((a, b) => b.size - a.size);
  const gmax = Math.max(.05, ...order.flatMap(m => tot.map((t, k) => share(m.id, k))));

  const VW = 960, VH = 104, VL = 40, vb = (VW - VL - 6) / nQ, vmax = Math.max(1, ...tot);
  const vol = svgEl("svg", { viewBox: "0 0 " + VW + " " + VH, role: "img", "aria-label": "Passages per quarter" + (tc != null ? " for " + D.countries[tc] : "") });
  for (let k = 0; k < nQ; k++) {
    const h = 44 * tot[k] / vmax, thin = tot[k] < THIN_Q, x = VL + k * vb;
    const r = svgEl("rect", { x: x + 6, y: 64 - h, width: vb - 12, height: h, fill: thin ? "#d8d4c8" : "#52555c" });
    r.append(svgEl("title", {})); r.lastChild.textContent = QN[k] + ": " + tot[k] + " passages from " + docs[k].size + " stories";
    vol.append(r, svgTxt(x + vb / 2, 60 - h, fmt(tot[k]), { "text-anchor": "middle", "font-size": 10.5, fill: thin ? "#8f4f00" : "#52555c" }),
      svgTxt(x + vb / 2, 80, QN[k].slice(5), { "text-anchor": "middle", "font-size": 10.5, fill: "#52555c" }));
    if (k % 4 === 0) vol.append(svgTxt(x + 6, 98, QN[k].slice(0, 4), { "font-size": 11.5, "font-weight": 600, fill: "#17181b" }));
  }
  vol.append(svgTxt(0, 42, "passages", { "font-size": 10.5, fill: "#52555c" }));

  const grid = el("div", { class: "smgrid" });
  order.forEach(m => {
    const W = 300, H = 132, L = 30, B = 22, T = 18, bw = (W - L - 4) / nQ;
    const mx = own ? Math.max(.02, ...tot.map((t, k) => share(m.id, k))) * 1.12 : gmax * 1.05;
    const y = v => T + (H - T - B) * (1 - Math.min(v, mx) / mx), col = A.MAIN_COL[m.id];
    const tot_m = cnt[m.id].reduce((s, v) => s + v, 0), whole = all ? tot_m / all : 0;
    const svg = svgEl("svg", { viewBox: "0 0 " + W + " " + H, role: "img", "aria-label": cap(m.name) + ": share of each quarter's passages, " + QN[0] + " to " + QN[11] });
    [0, mx].forEach(v => svg.append(svgEl("line", { x1: L, x2: W, y1: y(v), y2: y(v), stroke: v ? "#eceae3" : "#c9c4b6" }), svgTxt(L - 4, y(v) + 4, Math.round(v * 100) + "%", { "text-anchor": "end", "font-size": 10, fill: "#52555c" })));
    for (let k = 0; k < nQ; k++) {
      const v = share(m.id, k), thin = tot[k] < THIN_Q;
      const r = svgEl("rect", { x: L + k * bw + 2, y: y(v), width: bw - 4, height: Math.max(0, y(0) - y(v)), fill: col, "fill-opacity": thin ? .35 : 1, stroke: window.PAL.light(col) ? window.PAL.ink(col) : "none", "stroke-width": .6 });
      r.append(svgEl("title", {})); r.lastChild.textContent = QN[k] + ": " + cnt[m.id][k] + " of " + tot[k] + " passages (" + pct(v, 0) + ")" + (thin ? ", few passages" : "");
      svg.append(r);
      if (k % 4 === 0) svg.append(svgTxt(L + k * bw + 2, H - 6, QN[k].slice(0, 4), { "font-size": 10, fill: "#52555c" }));
    }
    svg.append(svgEl("line", { x1: L, x2: W, y1: y(whole), y2: y(whole), stroke: "#17181b", "stroke-dasharray": "3 3", "stroke-width": 1 }));
    grid.append(el("button", { type: "button", class: "sm", onclick: () => A.go.themes("main", m.id), "aria-label": "Open the report on " + m.name }, [
      el("span", { class: "smh" }, [el("i", { style: "background:" + col }), el("b", { style: "color:" + window.PAL.ink(col), text: cap(m.name) }), el("span", { class: "small", text: " " + pct(whole, 0) + " over the period" })]), svg]));
  });
  const chipRow = el("div", { class: "opts", role: "group", "aria-label": "Country" }, [el("button", { type: "button", class: "chip", "aria-pressed": tc == null, text: "All countries", onclick: () => { S.tc = null; A.render(); } }), ...D.countries.map((c, i) => el("button", { type: "button", class: "chip", "aria-pressed": tc === i, text: c, onclick: () => { S.tc = tc === i ? null : i; A.render(); } }))]);
  const seg = el("div", { class: "seg", role: "group", "aria-label": "Scale" }, [["same", "Same scale for all"], ["own", "Own scale per theme"]].map(a => el("button", { type: "button", "aria-pressed": (own ? "own" : "same") === a[0], text: a[1], onclick: () => { S.tm = a[0]; A.render(); } })));
  panel.append(el("p", { class: "small", style: "max-width:84ch", text: "One small chart per theme. Each bar is the share of a quarter’s passages that belong to the theme; the dashed line is its share over the whole period. Quarters are dated by the day the report was published. Pale bars and orange numbers mark quarters with fewer than " + THIN_Q + " passages." }),
    el("div", { class: "rsel" }, [seg]), chipRow, el("div", { class: "fig", style: "margin-top:10px" }, [vol]), grid,
    el("p", { class: "caption", text: (own ? "Each chart has its own scale, so small themes can be read, but heights cannot be compared between charts. " : "All charts share one scale, so heights can be compared between themes. ") + "Reporting follows events and projects: a rise shows more writing on a subject in that quarter. The problem itself may not have grown." }));
};

X.topicsExtra = function (panel) {
  const T = D.medical.topics, inf = T.filter(t => t.precision && t.precision.informative).length;
  const body = T.slice().sort((a, b) => (b.all_pct || 0) - (a.all_pct || 0)).map(t => {
    const p = t.precision, np = t.n_patterns;
    return el("tr", {}, [
      el("td", {}, [el("details", { class: "pat" }, [el("summary", { text: t.name }), el("p", { class: "small", text: "Some of the English word patterns used to find this topic (the full lists are in the code; there are also French, Spanish and Arabic lists):" }), el("p", { class: "small mono", text: t.patterns.slice(0, 8).join("  ·  ") })])]),
      el("td", { class: "r num", text: t.all_pct != null ? t.all_pct.toFixed(0) + "%" : "" }),
      el("td", { class: "small", text: np ? [np.en, np.fr, np.es, np.ar].map(v => v || 0).join(" / ") : "" }),
      el("td", { class: "num", text: p ? p.correct + " of " + p.judged : "" }),
      el("td", {}, [p ? el("span", { class: p.informative ? "ok" : "below", text: p.informative ? "yes" : "no" }) : ""])]);
  });
  panel.append(el("div", { class: "sec2" }, [el("h4", { text: "How each topic was searched and checked" }),
    el("p", { class: "small", style: "max-width:84ch", text: "A topic counts for a story when one of its word patterns appears in the story. Patterns exist in English, French, Spanish and Arabic. A language model then reread 20 matches per topic and said how many were correct. The same model also read control passages that had nothing to do with the topic. If it said yes to many of those, its “correct” means little. This test could tell good matches from bad ones for only " + inf + " of the " + T.length + " topics (last column). No person has checked them yet." }),
    el("div", { class: "scrollx" }, [el("table", { class: "tbl" }, [el("thead", {}, [el("tr", {}, [el("th", { text: "Topic" }), el("th", { class: "r", text: "Stories (all)" }), el("th", { text: "Patterns EN / FR / ES / AR" }), el("th", { text: "Machine check" }), el("th", { text: "Test informative?" })])]), el("tbody", {}, body)])])]));
};

X.renderFindings = function (box) {
  const items = [], big = A.MAINS.slice().sort((a, b) => b.size - a.size)[0];
  items.push({ n: pct(big.share, 0), t: "of all passages are about " + big.name + ", found in " + fmt(big.documents) + " of " + fmt(D.header.stories) + " stories.", b: "Read the theme", f: () => A.go.themes("main", big.id) });

  const M = D.medical, ok = M.single_country_docs.map(n => n >= 30);
  const gaps = M.topics.map(t => { let hi = -1, lo = -1; t.rows.forEach((v, ci) => { if (!v || !ok[ci]) return; if (hi < 0 || v[1] > t.rows[hi][1]) hi = ci; if (lo < 0 || v[1] < t.rows[lo][1]) lo = ci; }); return hi >= 0 ? { t, hi, lo, d: t.rows[hi][1] - t.rows[lo][1] } : null; }).filter(Boolean).sort((a, b) => b.d - a.d);
  gaps.slice(0, 2).forEach(g => items.push({ n: g.t.rows[g.hi][1].toFixed(0) + "% vs " + g.t.rows[g.lo][1].toFixed(0) + "%", t: "of single-country stories mention " + g.t.name.toLowerCase() + ": " + D.countries[g.hi] + " against " + D.countries[g.lo] + ".", b: "See all topics", f: () => A.go.tab("topics") }));
  const mixed = A.MAINS.filter(m => m.flags.includes("incoherent"));
  if (mixed.length) items.push({ n: "1 of " + A.MAINS.length, t: "themes is mixed: " + mixed[0].name + ". We say so on its report, and its sub-themes are read separately.", b: "Open it", f: () => A.go.themes("main", mixed[0].id) });
  const joined = D.ab.reduce((s, v) => s + v, 0);
  items.push({ n: pct(joined / D.x.length, 0), t: "of the passages (" + fmt(joined) + ") were first left unplaced by the grouping method and joined to the nearest theme afterwards. Every passage says which it was.", b: "Show on the map", f: () => A.go.map({ level: "main", sel: null, country: null, passage: null, own: true }) });
  box.replaceChildren(...items.map(it => el("div", { class: "find" }, [el("b", { text: it.n }), el("p", { text: it.t }), el("button", { type: "button", class: "lk", text: it.b + " →", onclick: it.f })])));
};
X.renderFunnel = function (box) {
  const steps = [["1,481", "reports collected", "ReliefWeb, Médecins Sans Frontières, 8 countries, 2023 to 2025, about 1.06 million words"], ["1,362", "reports with usable text", "119 had no usable text after cleaning"], [fmt(D.header.stories), "stories", "469 other versions, mostly translations, were kept once"], [fmt(D.header.passages), "passages", "the stories were cut into passages of a few paragraphs"], [String(D.header.subthemes), "sub-themes", "dense areas found by HDBSCAN on a 5-dimension map"], [String(D.header.themes), "themes", "sub-themes merged by Ward linkage"]];
  box.replaceChildren(...steps.map((s, k) => el("li", {}, [el("b", { text: s[0] }), el("span", { class: "fl", text: s[1] }), el("span", { class: "fn", text: s[2] })])));
};
X.renderDownloads = function (box) {
  const th = () => { const r = [["level", "id", "name", "passages", "share of corpus", "stories", "coherence", "flags", "summary (language-model written)"]]; D.clusters.forEach(c => r.push([c.level, c.id, c.name, c.size, c.share, c.documents, c.coherence, c.flags.join("; "), c.summary])); return r; };
  const tc = () => { const r = [["theme", ...D.countries]]; A.MAINS.forEach(m => r.push([m.name, ...A.CNT.main[m.id]])); r.push(["all themes", ...A.CNT.country]); return r; };
  const mt = () => { const r = [["topic", "country", "stories mentioning", "stories of the country (single-country)", "percent", "ci low", "ci high"]]; D.medical.topics.forEach(t => t.rows.forEach((v, ci) => { if (v) r.push([t.name, D.countries[ci], v[0], D.medical.single_country_docs[ci], v[1], v[2], v[3]]); })); return r; };
  box.replaceChildren(
    el("button", { type: "button", class: "btn", text: "Themes and sub-themes (CSV)", onclick: () => download("msf-themes.csv", th()) }),
    el("button", { type: "button", class: "btn", text: "Passages per theme and country (CSV)", onclick: () => download("msf-theme-by-country.csv", tc()) }),
    el("button", { type: "button", class: "btn", text: "Medical topics by country (CSV)", onclick: () => download("msf-medical-topics.csv", mt()) }));
};
})();
