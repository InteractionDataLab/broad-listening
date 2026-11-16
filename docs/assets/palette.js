(function () {
"use strict";

const CAT = ["#5259B2", "#AD3420", "#078762", "#3BBCCE", "#E59F6A", "#989503", "#9F82E2", "#7B2D6A", "#D55C8E"];
const PAPER = "#ffffff", NONE = "#b9b6ad";
const rgb = h => { const n = parseInt(h.slice(1), 16); return [n >> 16, (n >> 8) & 255, n & 255]; };
const hex = a => "#" + a.map(c => Math.max(0, Math.min(255, Math.round(c))).toString(16).padStart(2, "0")).join("");
const lin = c => { c /= 255; return c <= 0.04045 ? c / 12.92 : Math.pow((c + 0.055) / 1.055, 2.4); };
const lum = h => { const [r, g, b] = rgb(h); return 0.2126 * lin(r) + 0.7152 * lin(g) + 0.0722 * lin(b); };
const contrast = (a, b) => { const x = lum(a), y = lum(b); return (Math.max(x, y) + 0.05) / (Math.min(x, y) + 0.05); };
function mix(h, f) { const c = rgb(h); return hex(c.map(v => f > 0 ? v + (255 - v) * f : v * (1 + f))); }
const inkCache = {};
function ink(h, bg) { const k = h + (bg || ""); if (inkCache[k]) return inkCache[k]; let c = h, n = 0; while (contrast(c, bg || PAPER) < 4.6 && n < 30) { c = mix(c, -0.07); n++; } return (inkCache[k] = c); }
const light = h => lum(h) > 0.32;
const onFill = h => contrast("#17181b", h) >= contrast("#ffffff", h) ? "#17181b" : "#ffffff";

function child(h, k) { const steps = light(h) ? [0, -0.22, -0.40, -0.12] : [0, 0.24, -0.22, 0.40];    return mix(h, steps[k % steps.length]); }

const COUNTRY = ["#0072B2", "#E69F00", "#009E73", "#CC79A7", "#56B4E9", "#D55E00", "#17181b", "#8a8a8a"];

const SEQ = ["#ffffff", "#e8eef7", "#c7d6ec", "#9cb7dd", "#6b92c8", "#3f6eb0", "#1f4f93", "#123572"];
function heat(v) { const x = Math.max(0, Math.min(1, v)) * (SEQ.length - 1), i = Math.floor(x), f = x - i; if (i >= SEQ.length - 1) return SEQ[SEQ.length - 1]; const a = rgb(SEQ[i]), b = rgb(SEQ[i + 1]); return hex(a.map((c, k) => c + (b[k] - c) * f)); }
window.PAL = { CAT, NONE, PAPER, COUNTRY, ink, light, onFill, child, contrast, mix, lum, heat };
})();
