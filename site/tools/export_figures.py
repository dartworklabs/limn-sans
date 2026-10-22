"""The figures of the design-system portfolio (Figma), drawn from limn-brand.js and the font files, and a manifest of
every number they show.

This is a development/brand export, not a specimen or certification of the 1.000
release. Hangul and logo studies remain research/trademark material. The README
release specimen is produced separately by docs/assets/render-release-specimen.py.

  uv run --no-project --with playwright --with pillow --with fonttools --with brotli --with uharfbuzz \
    python3 tools/export_figures.py --out figures

Writes into --out (make figures: site/figures, not committed), one SVG per figure, PNGs where a raster is useful, and
manifest.json. Nothing is drawn by hand:
  logo/   LIMN.wordmark · rim · the BI's lockup, construction, clear space and don'ts, called the way the BI page calls
          them; minsize-<h> is the wordmark h px tall with its optical pin gap (LIMN.gdFor)
  icon/   LIMN.icon on the Apple grid, the ramp of sizes, the 16 20 24 32 px pixel drawings (LIMN.ICON_PX), the
          browser favicon (LIMN.favicon) on a light and a dark tab, the 180 px home-screen icon
  color/  LIMN.COLOR
  type/   set by the font files: HarfBuzz shapes each run over the .woff2 (the files @font-face serves) and the SVG
          carries its outlines; the PNG is the same figure drawn by Chromium from @font-face, and every run's width
          there must equal HarfBuzz's (checked, manifest "fontface"). glyph-grid-<w> for every weight,
          features-<tag> for every GSUB/GPOS feature of the files
  motion/ the curves and durations of limn-pages.css (the BI's motion table), with their bezier handles
  use/    app-light/app-dark: the Limn app on a sample manuscript (title and label "Sample paper"), served by a
          throwaway instance on 127.0.0.1 (state and HOME in a temporary folder, stopped by its own process group
          whatever ends the run; see app_screens); tab and dock: the favicon and icon in a tab strip and a Dock
Captions carry no typed numbers: a caption with a number is built from the data by its figure. Labels are marked
class "label" (text in data-label) and dimension, grid and axis lines class "guide", so the check can see that no
guide runs through a label.
Every frame is the ink bounds: the geometry box (getBBox, exact for curves, so overshoot and bezier handles are
inside), each stroke's half width around its element, and where the painted pixels run more than one pixel past
that (a shadow), those pixels. Numbers come from the data files (limn-font-play.js,
limn-font.js, limn-brand.js, fonts/*.ttf cmap, limn-pages.css); tools/check_figures.py checks them against it and
scans every file for what the public file must not show.
Needs make play, font, fonts (and refs for one don't, the name typed in another typeface), Playwright's Chromium, and
for the app screens uv, latexmk and pdftotext (--no-app skips them).
"""
import argparse
import base64
import io
import json
import math
import os
import re
import shutil
import signal
import socket
import subprocess
import sys
import tempfile
import time
import unicodedata
import urllib.request
from pathlib import Path

import uharfbuzz as hb
from fontTools.pens.recordingPen import RecordingPen
from fontTools.pens.svgPathPen import SVGPathPen
from fontTools.pens.transformPen import TransformPen
from fontTools.ttLib import TTFont
from fontTools.ttLib.woff2 import decompress
from PIL import Image
from playwright.sync_api import sync_playwright

from check_figures import FORBIDDEN, lum  # one list of what may never go public, one luminance

SITE = Path(__file__).resolve().parent.parent
ORIGIN = "http://limn.figures/"  # the page's origin; Playwright answers it from SITE, no server or port
LIMN_FROM = "git+https://github.com/dartworklabs/limn@v0.3.8"
LABEL = "Sample paper"
APP_VIEW = (1440, 900)
GROUPS = ("logo", "icon", "color", "type", "motion", "use")
# the public colour tokens (LIMN.COLOR keys), in the order the swatches show them
TOKENS = ({"key": "ink", "name": "Ink", "use": "strokes and text"},
          {"key": "ver", "name": "Vermilion", "use": "the pin, and only the pin"},
          {"key": "paper", "name": "Paper", "use": "light ground"},
          {"key": "bone", "name": "Bone", "use": "app icon ground"},
          {"key": "cream", "name": "Cream", "use": "strokes on ink"},
          {"key": "sky", "name": "On vermilion", "use": "strokes and pin on vermilion"})
CHIP_TEXT_CONTRAST = 4.5  # WCAG 1.4.3: the demo's label chip sets its text on the accent
# CSS keyword curves as cubic-bezier control points (CSS Easing Functions Level 1)
KEYWORD_CURVES = {"linear": [0, 0, 1, 1], "ease": [0.25, 0.1, 0.25, 1], "ease-in": [0.42, 0, 1, 1],
                  "ease-out": [0, 0, 0.58, 1], "ease-in-out": [0.42, 0, 0.58, 1]}


# ---------------------------------------------------------------- data files

def load_js(path, marker):
    """The JSON a generated data file assigns after marker."""
    if not path.exists():
        sys.exit(f"export_figures: {path.name} missing - run make play font fonts first")
    t = path.read_text(encoding="utf-8")
    i = t.index(marker) + len(marker)
    return json.loads(t[i:t.rindex(";")])


def git(*args):
    return subprocess.run(["git", "-C", str(SITE), *args], capture_output=True, text=True, check=True).stdout.strip()


def weights_of(play, files):
    """manifest weights: the play data of each weight (S = stroke), its file name"""
    names = {str(f["w"]): f["name"] for f in files["files"]}
    out = {}
    for w, W in sorted(play.items(), key=lambda kv: int(kv[0])):
        p = W["pin"]
        out[w] = {"name": names.get(w), "S": W["s"], "xh": W["xh"], "xo": W["xo"], "cap": W["cap"], "asc": W["asc"],
                  "desc": W["desc"], "pin_r": p["r"], "pin_gap": p["gap"], "pin_top": round(W["xh"] + p["gap"] + 2 * p["r"], 2),
                  "quote_r": p["qr"], "quote_gap": p["qgap"]}
    return out


def char_class(cp):
    """coverage class of a code point; the classes partition the cmap"""
    ch = chr(cp)
    if 0xAC00 <= cp <= 0xD7A3:
        return "hangul"
    if 0x1100 <= cp <= 0x11FF or 0x3130 <= cp <= 0x318F or 0xA960 <= cp <= 0xA97F or 0xD7B0 <= cp <= 0xD7FF:
        return "jamo"
    name, cat = unicodedata.name(ch, ""), unicodedata.category(ch)
    if name.startswith("LATIN "):
        return "latin"
    if name.startswith(("GREEK ", "COPTIC ")):
        return "greek"
    if name.startswith("CYRILLIC "):
        return "cyrillic"
    if cat == "Nd":
        return "digits"
    if cat.startswith("P"):
        return "punctuation"
    if cat.startswith("Z") or cat == "Cf":
        return "spaces"
    return "symbols"


def coverage(cmap):
    out = {k: 0 for k in ("total", "hangul", "jamo", "latin", "greek", "cyrillic", "digits", "punctuation", "spaces", "symbols")}
    out["total"] = len(cmap)
    for cp in cmap:
        out[char_class(cp)] += 1
    return out


def font_features(tt):
    tags = set()
    for t in ("GSUB", "GPOS"):
        if t in tt and tt[t].table.FeatureList:
            tags |= {fr.FeatureTag for fr in tt[t].table.FeatureList.FeatureRecord}
    return sorted(tags)


# ---------------------------------------------------------------- motion: limn-pages.css

def css_parse(css):
    """(rules: selector -> {prop: value}, keyframes: name -> [(offsets, {prop: value})])"""
    css = re.sub(r"/\*.*?\*/", "", css, flags=re.S)
    frames = {}
    for m in re.finditer(r"@keyframes\s+([\w-]+)\s*\{((?:[^{}]*\{[^{}]*\})*)\s*\}", css):
        steps = []
        for sel, body in re.findall(r"([^{}]+)\{([^{}]*)\}", m.group(2)):
            offs = [0.0 if o.strip() == "from" else 100.0 if o.strip() == "to" else float(o.strip().rstrip("%"))
                    for o in sel.split(",")]
            steps.append((offs, decls(body)))
        frames[m.group(1)] = steps
    rest = re.sub(r"@keyframes\s+[\w-]+\s*\{(?:[^{}]*\{[^{}]*\})*\s*\}", "", css)
    rest = re.sub(r"@media[^{]*\{(?:[^{}]*\{[^{}]*\})*\s*\}", "", rest)
    rules = {}
    for sel, body in re.findall(r"([^{}]+)\{([^{}]*)\}", rest):
        for s in sel.split(","):
            rules.setdefault(s.strip(), {}).update(decls(body))
    return rules, frames


def decls(body):
    out = {}
    for d in body.split(";"):
        if ":" in d:
            k, v = d.split(":", 1)
            out[k.strip()] = v.strip()
    return out


def animation(rules, sel):
    """name, duration (s) and curve (cubic-bezier control points) of the animation shorthand on sel"""
    v = rules[sel]["animation"]
    curve = re.search(r"cubic-bezier\(([^)]*)\)", v)
    words = re.sub(r"cubic-bezier\([^)]*\)", " ", v).split()
    dur = next(float(w[:-1]) if w.endswith("s") and not w.endswith("ms") else float(w[:-2]) / 1000
               for w in words if re.fullmatch(r"[\d.]+m?s", w))
    if curve:
        pts = [float(x) for x in curve.group(1).split(",")]
    else:
        pts = next(KEYWORD_CURVES[w] for w in words if w in KEYWORD_CURVES)
    return words[0], dur, pts


def at(steps):
    """keyframes flattened to (offset, props), in offset order"""
    return sorted(((o, p) for offs, p in steps for o in offs), key=lambda t: t[0])


def motion(css_path):
    """The BI's four motions, read from the stylesheet every page runs:
      drop    .w .pt   the pin falls onto the wordmark (saved; first screen)
      write   .w .gl   each letter is wiped in, left to right (loading)
      ripple  .ic-ring the ring after a new pin: from the frame it shows to the frame its growth ends
      light   .lm-light the sweep (first transform segment) and the gathering into the dot (the segment whose scale
                        changes)"""
    rules, frames = css_parse(css_path.read_text(encoding="utf-8"))
    out = {}
    for key, sel in (("drop", ".w .pt"), ("write", ".w .gl")):
        name, dur, pts = animation(rules, sel)
        out[key] = {"source": f"limn-pages.css {sel} ({name})", "duration_s": dur, "curve": pts}
    name, cycle, pts = animation(rules, ".ic-ring")
    ks = at(frames[name])
    shows = next(o for o, p in ks if "opacity" in p and float(p["opacity"]) > 0)
    final = [p["transform"] for o, p in ks if "transform" in p][-1]
    grown = next(o for o, p in ks if p.get("transform") == final)
    out["ripple"] = {"source": f"limn-pages.css .ic-ring ({name})", "duration_s": round(cycle * (grown - shows) / 100, 3),
                     "curve": pts, "cycle_s": cycle, "span_pct": [shows, grown]}
    name, cycle, pts = animation(rules, ".lm-light")
    ts = [(o, p["transform"]) for o, p in at(frames[name]) if "transform" in p]
    segs = list(zip(ts, ts[1:]))
    scale = lambda t: (re.search(r"scale\(([^)]*)\)", t) or [None, None])[1]
    sweep = segs[0]
    gather = next(s for s in segs if scale(s[0][1]) != scale(s[1][1]))
    out["light"] = {"source": f"limn-pages.css .lm-light ({name})", "curve": pts, "cycle_s": cycle,
                    "sweep_s": round(cycle * (sweep[1][0] - sweep[0][0]) / 100, 3),
                    "gather_s": round(cycle * (gather[1][0] - gather[0][0]) / 100, 3)}
    return out


# ---------------------------------------------------------------- text: HarfBuzz over the font files

class Shaper:
    """Runs set by the font files: font 'LS<w>' is the .woff2 of weight w (as @font-face serves it), 'ref:<name>' a
    reference font of site/refs. shape() gives the run's outline (an SVG path, y down, baseline at 0, x from 0, in
    the units of size = 1 em) and its advance."""

    def __init__(self, files):
        self.src = {f"LS{f['w']}": SITE / f["woff2"] for f in files["files"]}
        self.fonts = {}

    def font(self, key):
        if key not in self.fonts:
            if key.startswith("ref:"):
                p = SITE / "refs" / (key[4:] + ".ttf")
                if not p.exists():
                    raise ValueError(f"{p.name} missing - run make refs")
                data = p.read_bytes()
            else:
                src, dst = io.BytesIO(self.src[key].read_bytes()), io.BytesIO()
                decompress(src, dst)
                data = dst.getvalue()
            tt = TTFont(io.BytesIO(data))
            face = hb.Face(data)
            self.fonts[key] = {"hb": hb.Font(face), "upm": face.upem, "gs": tt.getGlyphSet(), "order": tt.getGlyphOrder(),
                               "cmap": tt.getBestCmap(), "rec": {}}
        return self.fonts[key]

    def shape(self, jobs):
        out = []
        for text, key, size, feats in jobs:
            F = self.font(key)
            missing = sorted({c for c in text if ord(c) not in F["cmap"] and c not in "\n"})
            if missing:
                raise ValueError(f"{key} has no glyph for {missing!r} in {text!r}")
            buf = hb.Buffer()
            buf.add_str(text)
            buf.guess_segment_properties()
            hb.shape(F["hb"], buf, {k: bool(v) for k, v in (feats or {}).items()})
            k = size / F["upm"]
            pen = SVGPathPen(None, ntos=num)
            x, run = 0, []
            for info, pos in zip(buf.glyph_infos, buf.glyph_positions):
                name = F["order"][info.codepoint]
                if name not in F["rec"]:
                    rp = RecordingPen()
                    F["gs"][name].draw(rp)
                    F["rec"][name] = rp
                F["rec"][name].replay(TransformPen(pen, (k, 0, 0, -k, (x + pos.x_offset) * k, -pos.y_offset * k)))
                run.append(f"{name}@{x + pos.x_offset},{pos.y_offset}")
                x += pos.x_advance
            # g: the glyphs and their places, so two feature settings can be told apart (or found the same)
            out.append({"d": pen.getCommands() or "M0 0", "adv": round(x * k, 3), "g": " ".join(run)})
        return out


def num(v):
    s = f"{v:.2f}".rstrip("0").rstrip(".")
    return "0" if s in ("-0", "") else s


# ---------------------------------------------------------------- the page

PAGE = """<!doctype html><html><head><meta charset="utf-8"><style>
html,body{margin:0;padding:0;background:transparent}
#stage{position:absolute;left:0;top:0;line-height:0}#stage svg{display:block}
%(faces)s
</style>
</head><body><div id="stage"></div>
<script>window.FIGDATA=%(data)s;</script>
<script src="limn-font.js"></script><script src="limn-brand.js"></script><script src="figures.js"></script>
</body></html>"""

FIGURES_JS = r"""
/* the figures (tools/export_figures.py): each is built from LIMN (limn-brand.js) and text set by the font files */
(function () {
"use strict";
const L = LIMN, C = L.COLOR, F = L.F, M = L.MINIM, D = window.FIGDATA;
const NS = "http://www.w3.org/2000/svg";
const f = L.f, r2 = v => +(+v).toFixed(2);
const esc = s => String(s).replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;");
let LIVE = false, DPR = 1, RUNS = [];
// a seeded Math.random per figure: the icon's filter ids come out the same on every run
let SEED = 1;
Math.random = () => { SEED = (SEED + 0x6D2B79F5) | 0; let t = SEED; t = Math.imul(t ^ (t >>> 15), t | 1); t ^= t + Math.imul(t ^ (t >>> 7), t | 61); return ((t ^ (t >>> 14)) >>> 0) / 4294967296; };

const shaped = new Map();
async function shape(str, font, size, feat) {
  const k = JSON.stringify([str, font, size, feat]);
  if (!shaped.has(k)) shaped.set(k, (await window.limnShape([[str, font, size, feat]]))[0]);
  return shaped.get(k);
}
/* one run of text: o = {w | font, size, x, y (baseline), anchor, fill, opacity, feat {tag: bool}, halo, haloW, sample}.
   Outlines from the font file; in live mode a <text> in the @font-face font at the same place. A run is a label
   (class "label", its text in data-label: tools/check_figures.py keeps guides out of it) unless o.sample (type
   specimens, glyph cells, the typed don't). RUNS keeps each run's text and size (user units). */
async function tx(str, o = {}) {
  const font = o.font || `LS${o.w || 400}`, size = o.size || 16, feat = o.feat || {};
  const t = await shape(str, font, size, feat);
  let x = o.x || 0; const y = o.y || 0;
  if (o.anchor === "middle") x -= t.adv / 2; else if (o.anchor === "end") x -= t.adv;
  RUNS.push([str, size]);
  const cls = o.sample ? "" : ` class="label" data-label="${esc(str).replace(/"/g, "&quot;")}"`;
  const paint = `fill="${o.fill || C.ink}"` + (o.opacity != null ? ` opacity="${o.opacity}"` : "");
  // a halo is its own run drawn first (paint-order is not read by every SVG importer)
  const halo = o.halo ? `class="label halo" fill="${o.halo}" stroke="${o.halo}" stroke-width="${o.haloW || size * 0.3}" stroke-linejoin="round"` : null;
  let one;
  if (LIVE && font.startsWith("LS")) {
    const ffs = Object.entries(feat).map(([k, v]) => `'${k}' ${v ? 1 : 0}`).join(", ") || "normal";
    one = p => `<text x="${r2(x)}" y="${r2(y)}" font-family="${font}" font-size="${size}" data-adv="${t.adv}" style="font-feature-settings:${ffs};font-kerning:${feat.kern === false ? "none" : "normal"};white-space:pre" ${p}>${esc(str)}</text>`;
  } else one = p => `<path transform="translate(${r2(x)} ${r2(y)})" d="${t.d}" ${p}/>`;
  return { svg: (halo ? one(halo) : "") + one(paint + cls), adv: t.adv, x0: x, x1: x + t.adv, g: t.g };
}
const T = async (str, o) => (await tx(str, o)).svg;
const inner = svg => svg.replace(/^<svg[^>]*>/, "").replace(/<\/svg>\s*$/, "");
const place = (svg, x, y) => `<g transform="translate(${r2(x)} ${r2(y)})">${svg}</g>`;

/* ---------- frames: the ink bounds ---------- */
const host = document.createElementNS(NS, "svg");
host.setAttribute("width", "1"); host.setAttribute("height", "1");
host.setAttribute("style", "position:absolute;left:-60000px;top:0;overflow:visible");
document.body.appendChild(host);
// the geometry's ink: getBBox (fills, exact for curves), each stroked element's box grown by half its stroke width
function geomBox(body, defs) {
  host.innerHTML = `${defs ? `<defs>${defs}</defs>` : ""}<g>${body}</g>`;
  const g = host.lastElementChild, b = g.getBBox(), inv = host.getScreenCTM().inverse();
  let [x0, y0, x1, y1] = [b.x, b.y, b.x + b.width, b.y + b.height];
  for (const el of g.querySelectorAll("path,rect,line,circle,ellipse,polyline,polygon,text")) {
    const cs = getComputedStyle(el), sw = parseFloat(cs.strokeWidth) || 0;
    if (cs.stroke === "none" || !sw) continue;
    const m = inv.multiply(el.getScreenCTM()), e = el.getBBox();
    const hx = sw / 2 * Math.hypot(m.a, m.b), hy = sw / 2 * Math.hypot(m.c, m.d);
    for (const [px, py] of [[e.x, e.y], [e.x + e.width, e.y], [e.x, e.y + e.height], [e.x + e.width, e.y + e.height]]) {
      const q = new DOMPoint(px, py).matrixTransform(m);
      x0 = Math.min(x0, q.x - hx); x1 = Math.max(x1, q.x + hx); y0 = Math.min(y0, q.y - hy); y1 = Math.max(y1, q.y + hy);
    }
  }
  return [x0, y0, x1 - x0, y1 - y0];
}
async function image(svg) {
  const img = new Image();
  img.src = "data:image/svg+xml;charset=utf-8," + encodeURIComponent(svg);
  await img.decode();
  return img;
}
// the painted pixels (alpha > 0) around box, drawn at up to 4 px per output px, and the size of one pixel in units;
// grows the window until nothing touches its edge
async function paintBox(body, defs, box, scale) {
  let [x, y, w, h] = box;
  for (let n = 0; n < 5; n++) {
    const pad = Math.max(w, h) * 0.25 + 40 / scale, R = [x - pad, y - pad, w + 2 * pad, h + 2 * pad];
    const rs = Math.min(4 * scale, Math.sqrt(1.6e7 / (R[2] * R[3])));
    const cw = Math.ceil(R[2] * rs), ch = Math.ceil(R[3] * rs), sx = cw / R[2], sy = ch / R[3];
    const img = await image(`<svg xmlns="${NS}" viewBox="${R.join(" ")}" width="${cw}" height="${ch}" preserveAspectRatio="none">${defs ? `<defs>${defs}</defs>` : ""}${body}</svg>`);
    const c = document.createElement("canvas"); c.width = cw; c.height = ch;
    const g = c.getContext("2d", { willReadFrequently: true }); g.drawImage(img, 0, 0, cw, ch);
    const a = g.getImageData(0, 0, cw, ch).data;
    let x0 = cw, y0 = ch, x1 = -1, y1 = -1;
    for (let j = 0; j < ch; j++) {
      const row = j * cw * 4; let any = false;
      for (let i = 0; i < cw; i++) if (a[row + i * 4 + 3]) { any = true; if (i < x0) x0 = i; if (i > x1) x1 = i; }
      if (any) { if (j < y0) y0 = j; y1 = j; }
    }
    if (x1 < 0) return null;
    if (x0 > 0 && y0 > 0 && x1 < cw - 1 && y1 < ch - 1)
      return { box: [R[0] + x0 / sx, R[1] + y0 / sy, (x1 + 1 - x0) / sx, (y1 + 1 - y0) / sy], px: Math.max(1 / sx, 1 / sy) };
    [x, y, w, h] = R;
  }
  throw new Error("ink keeps running past the window");
}
// the frame: the geometry box, widened on a side only where the painted pixels run more than one pixel past it
// (a shadow or anything the geometry does not see; a fill's own antialiasing stays within one pixel)
function frameOf(G, P) {
  if (!P) return G;
  const [gx0, gy0, gx1, gy1] = [G[0], G[1], G[0] + G[2], G[1] + G[3]], b = P.box, t = 1.01 * P.px;
  const x0 = b[0] < gx0 - t ? b[0] : gx0, y0 = b[1] < gy0 - t ? b[1] : gy0;
  const x1 = b[0] + b[2] > gx1 + t ? b[0] + b[2] : gx1, y1 = b[1] + b[3] > gy1 + t ? b[1] + b[3] : gy1;
  return [x0, y0, x1 - x0, y1 - y0];
}
const outward = ([x, y, w, h]) => { const x0 = Math.floor(x * 100) / 100, y0 = Math.floor(y * 100) / 100;
  return [x0, y0, r2(Math.ceil((x + w) * 100) / 100 - x0), r2(Math.ceil((y + h) * 100) / 100 - y0)]; };

/* ---------- the figures ---------- */
const FIG = new Map();
const fig = (id, d) => FIG.set(id, d);
const K = 70 / L.wordmark().vb[3];    // logo figures: the wordmark 70 px tall

fig("logo/wordmark-light", { ground: C.paper, caption: "The wordmark: ink strokes, the vermilion pin, on light grounds.",
  build: async () => ({ body: L.wordmark().body, scale: K }) });
fig("logo/wordmark-dark", { ground: C.ink, caption: "On the ink ground: cream strokes, the pin stays vermilion.",
  build: async () => ({ body: L.wordmark({ ink: C.cream }).body, scale: K }) });
fig("logo/wordmark-ver", { ground: C.ver, caption: "On the vermilion ground: strokes and pin both light.",
  build: async () => ({ body: L.wordmark({ ink: C.sky, pin: C.sky }).body, scale: K }) });
fig("logo/rim", { ground: C.paper, caption: "림, the Korean mark, with its own pin.",
  build: async () => ({ body: L.rim().body, scale: K }) });
function lockup(ink, pin) {   // the BI's lockup: wordmark, a divider, 림
  const a = L.wordmark({ ink, pin }), b = L.rim({ ink, pin }), gap = 300, ox = a.vb[0] + a.vb[2] + 2 * gap - b.vb[0];
  const div = `<rect x="${f(a.vb[0] + a.vb[2] + gap - 6)}" y="${f(b.vb[1])}" width="12" height="${f(b.vb[3])}" fill="${ink}" opacity=".25"/>`;
  return `${a.body}${div}<g transform="translate(${f(ox)} 0)">${b.body}</g>`;
}
fig("logo/lockup", { ground: C.paper, caption: "Lockup: the wordmark and 림.", build: async () => ({ body: lockup(C.ink, C.ver), scale: K }) });

fig("logo/construction", { ground: C.paper,
  build: async () => {
    const t = L.wordmark(), [x0, y0, w] = t.vb, red = C.ver, S = M.stems, dx = M.dotX, r = L.r, cy = L.CY, s = L.s;
    const lab = (str, x, y, fill, o = {}) => T(str, { w: 500, size: 40, x, y, fill, halo: C.paper, haloW: 12, ...o });
    const hl = async (y, l) => `<line class="guide" x1="${x0 - 420}" x2="${x0 + w + 120}" y1="${y}" y2="${y}" stroke="${C.ink}" stroke-width="3" opacity=".35"/>` + await lab(l, x0 - 420, y - 14, C.ink, { opacity: .7 });
    // stem axes: l and i run to the top (the ascender, the pin); the others stop above the x-height, so the labels
    // of the pin gap and the pin keep clear of them
    const vl = (x, i) => `<line class="guide" x1="${x}" x2="${x}" y1="${i < 2 ? y0 - 80 : -F.xh - 20}" y2="60" stroke="${red}" stroke-width="2.5" stroke-dasharray="12 12" opacity=".6"/>`;
    const tick = `class="guide" stroke="${red}" stroke-width="4"`;
    const dimH = async (xa, xb, y, l) => `<g ${tick}><line x1="${xa}" x2="${xb}" y1="${y}" y2="${y}"/><line x1="${xa}" x2="${xa}" y1="${y - 18}" y2="${y + 18}"/><line x1="${xb}" x2="${xb}" y1="${y - 18}" y2="${y + 18}"/></g>` + await lab(l, (xa + xb) / 2, y + 58, red, { anchor: "middle" });
    const dimV = async (ya, yb, x, l, anchor = "start", ddx = 28, ty = (ya + yb) / 2 + 14) => `<g ${tick}><line x1="${x}" x2="${x}" y1="${ya}" y2="${yb}"/><line x1="${x - 18}" x2="${x + 18}" y1="${ya}" y2="${ya}"/><line x1="${x - 18}" x2="${x + 18}" y1="${yb}" y2="${yb}"/></g>` + await lab(l, x + ddx, ty, red, { anchor });
    const pinTop = -(cy - r), gap = -F.xh - (cy + r);
    let g = await hl(-F.asc, f(pinTop) === F.asc ? `ascender ${F.asc} = pin top` : `ascender ${F.asc}`);
    if (f(pinTop) !== F.asc) g += await hl(-pinTop, `pin top ${f(pinTop)}`);
    g += await hl(cy, `pin centre ${f(-cy)}`) + await hl(-F.xh, `x-height ${F.xh}`) + await hl(0, "baseline 0") + S.map(vl).join("");
    const y1 = 110, y2 = 210;
    let d = await dimH(S[0] - s / 2, S[0] + s / 2, y1, `s ${f(s)}`) + await dimH(S[1] + s / 2, S[2] - s / 2, y1, `${f(S[2] - S[1] - s)}`)
      + await dimH(S[2] + s / 2, S[3] - s / 2, y1, `counter ${f(S[3] - S[2] - s)}`) + await dimH(S[4] + s / 2, S[5] - s / 2, y1, `${f(S[5] - S[4] - s)}`)
      + await dimH(S[2], S[3], y2, `stem pitch ${f(S[3] - S[2])}`);
    d += await dimV(-F.asc, -F.xh, S[0] - s / 2 - 60, `${f(F.asc - F.xh)}`, "end", -28)
      + await dimV(cy + r, -F.xh, dx + r + 40, `gap ${f(gap)} = ${f(gap / s)}s`, "start", 28, cy + r + 8)
      // 2r: its label left of the line and in the upper half of the pin, between the ascender and the pin-centre lines
      + await dimV(cy - r, cy + r, dx + r + 420, `2r ${f(2 * r)}`, "end", -28, cy - r / 2 + 14) + await dimV(-F.xh, 0, x0 + w + 60, `x-height ${F.xh}`);
    return { body: g + t.body + d, scale: 0.42,
      caption: `Construction, in font units (em ${F.upm}): the stroke s = ${f(s)} sets every measure.`, meta: { upm: F.upm, s } };
  } });

const LABEL_PX = 13;   // a label drawn at logo scale: this many px tall at 1x (the smallest text of any figure is 11 px)
fig("logo/clearspace", { ground: C.paper, caption: "Clear space: half the x-height on every side of the wordmark's box.",
  build: async () => {
    const t = L.wordmark(), [x, y, w, h] = t.vb, m = F.xh / 2, size = LABEL_PX / K;
    // the label sits in the band above the box, centred on its height (cap height ~ 0.7 em)
    return { scale: K, body: `<rect class="guide" x="${f(x - m)}" y="${f(y - m)}" width="${f(w + 2 * m)}" height="${f(h + 2 * m)}" fill="none" stroke="${C.ver}" stroke-dasharray="30 20" stroke-width="7"/><rect class="guide" x="${f(x)}" y="${f(y)}" width="${f(w)}" height="${f(h)}" fill="none" stroke="${C.ink}" stroke-width="4" opacity=".4"/>${t.body}`
      + await T(`${f(m)} = x-height / 2`, { w: 500, size, x: x - m + 12 / K, y: y - m / 2 + 0.35 * size, fill: C.ver }),
      meta: { clear_space: m } };
  } });

for (const h of [12, 16, 24]) fig(`logo/minsize-${h}`, { ground: C.paper, png1x: true,
  build: async () => {
    const gd = L.gdFor(h), t = L.wordmark({ gd }), k = h / t.vb[3], white = r2(gd * L.s * k);
    return { body: t.body, scale: k, meta: { h, gd, white_px: white },
      caption: `The wordmark ${h} px tall; the pin gap opens to ${gd}s, leaving ${white} px of white under the pin.` };
  } });

const K44 = 44 / L.wordmark().vb[3];   // the don'ts: the wordmark 44 px tall
const dont = (id, caption, build) => fig(`logo/misuse-${id}`, { ground: C.paper, caption, build: async () => ({ scale: K44, ...await build() }) });
dont("pin-ink", "Don't set the pin in ink: the pin disappears.", async () => ({ body: L.wordmark({ pin: C.ink }).body }));
dont("pin-colour", "Don't give the pin another colour: vermilion only.", async () => ({ body: L.wordmark({ pin: C.blue }).body }));
dont("stroke-ver", "Don't set the strokes in vermilion: it is for the pin only.", async () => ({ body: L.wordmark({ ink: C.ver }).body }));
dont("stretch", "Don't stretch or squash it.", async () => ({ body: `<g transform="scale(1.5 1)">${L.wordmark().body}</g>` }));
dont("round-feet", "Don't round the feet (Quicksand as it is): stems standing on the baseline end flat.", async () => ({ body: LIMN_make({ feet: "round" }).wordmark().body }));
dont("tracking", "Don't space the letters out.", async () => ({ body: L.wordmark({ track: 170 }).body }));
dont("typed", "Don't type the name, with a capital L, in another typeface.", async () => ({ body: await T("Limn", { font: "ref:Poppins-Bold", size: 40 / K44, fill: C.ink, sample: true }) }));
dont("effects", "Don't add shadows or effects.", async () => {
  const k = K44;   // the BI's drop-shadow(3px 4px 3px rgba(0,0,0,.35)) at 44 px
  return { defs: `<filter id="sh" filterUnits="userSpaceOnUse" x="-2000" y="-2000" width="8000" height="4000"><feDropShadow dx="${f(3 / k)}" dy="${f(4 / k)}" stdDeviation="${f(3 / k)}" flood-color="#000" flood-opacity=".35"/></filter>`,
    body: `<g filter="url(#sh)">${L.wordmark().body}</g>` };
});
dont("busy-ground", "Don't place it on a busy, low-contrast ground.", async () => {
  const t = L.wordmark(), [x, y, w, h] = t.vb, k = K44, px = 14 / k, py = 10 / k;
  return { defs: `<linearGradient id="bg" x1="0" y1="0" x2="1" y2="1"><stop offset="0" stop-color="#8ec5fc"/><stop offset="1" stop-color="#e0c3fc"/></linearGradient>`,
    body: `<rect x="${f(x - px)}" y="${f(y - py)}" width="${f(w + 2 * px)}" height="${f(h + 2 * py)}" rx="${f(6 / k)}" fill="url(#bg)"/>${t.body}` };
});
dont("raised-pin", "Don't float the pin higher: the pin top sits on the ascender.", async () => ({ body: L.wordmark({ gd: 1.3, full: true }).body }));

/* ---------- icon ---------- */
function boxIn(root, el) {    // el's box in root's user units
  const b = el.getBBox(), m = root.getScreenCTM().inverse().multiply(el.getScreenCTM());
  const a = new DOMPoint(b.x, b.y).matrixTransform(m), c = new DOMPoint(b.x + b.width, b.y + b.height).matrixTransform(m);
  return [a.x, a.y, c.x, c.y];
}
fig("icon/grid", { ground: C.paper,
  build: async () => {
    const ic = L.icon(1024, { vector: true, flat: true });
    host.innerHTML = ic;
    const root = host.firstElementChild, [bodyEl] = root.querySelectorAll("path"), cv = root.viewBox.baseVal;
    const stemEl = root.querySelector(`path[fill="${C.ink}"]`), pinEl = root.querySelector("circle");
    const bd = boxIn(root, bodyEl), st = boxIn(root, stemEl), pn = boxIn(root, pinEl), N = cv.width, mid = cv.x + N / 2;
    const red = C.ver, tick = `class="guide" stroke="${red}" stroke-width="3"`;
    const lab = (s, x, y, o = {}) => T(s, { w: 500, size: 30, x, y, fill: red, ...o });
    const bar = (xa, ya, xb, yb, h) => `<g ${tick}><line x1="${f(xa)}" x2="${f(xb)}" y1="${f(ya)}" y2="${f(yb)}"/>` + (h ? `<line x1="${f(xa - 14)}" x2="${f(xa + 14)}" y1="${f(ya)}" y2="${f(ya)}"/><line x1="${f(xb - 14)}" x2="${f(xb + 14)}" y1="${f(yb)}" y2="${f(yb)}"/>` : `<line x1="${f(xa)}" x2="${f(xa)}" y1="${f(ya - 14)}" y2="${f(ya + 14)}"/><line x1="${f(xb)}" x2="${f(xb)}" y1="${f(yb - 14)}" y2="${f(yb + 14)}"/>`) + "</g>";
    // outside the canvas: labels right of their lines; inside the body: labels left of the i, clear of the
    // centre lines (the i's axis and the canvas middle)
    const inside = { halo: C.bone, haloW: 10, anchor: "end" };
    let grid = "";
    for (let v = 0; v <= N; v += 64) grid += `M${v} 0V${N}M0 ${v}H${N}`;
    let g = `<path class="guide" d="${grid}" fill="none" stroke="${C.ink}" stroke-width="2" opacity=".08"/><rect class="guide" x="0" y="0" width="${N}" height="${N}" fill="none" stroke="${C.ink}" stroke-width="3" opacity=".35"/>`
      + ic + `<rect class="guide" x="${f(bd[0])}" y="${f(bd[1])}" width="${f(bd[2] - bd[0])}" height="${f(bd[3] - bd[1])}" fill="none" stroke="${red}" stroke-width="3" stroke-dasharray="16 12" opacity=".7"/>`
      + `<path class="guide" d="M${mid} 0V${N}M0 ${mid}H${N}" stroke="${red}" stroke-width="2" opacity=".35"/>`;
    // measures as the labels show them (one decimal)
    const sw = f(st[2] - st[0]), ih = f(st[3] - pn[1]), pd = f(pn[2] - pn[0]), gp = f(st[1] - pn[3]), body = f(bd[3] - bd[1]);
    g += bar(N + 330, 0, N + 330, N, true) + await lab(`canvas ${f(N)}`, N + 354, mid + 11)
      + bar(N + 90, bd[1], N + 90, bd[3], true) + await lab(`body ${f(body)}`, N + 114, mid + 11)
      + bar(pn[2] + 150, pn[1], pn[2] + 150, st[3], true) + await lab(`i ${f(ih)}`, pn[2] + 126, mid - 24, inside)
      + bar(st[0], st[3] + 44, st[2], st[3] + 44, false) + await lab(`stem ${f(sw)}`, st[0] - 24, st[3] + 55, inside)
      + bar(pn[0], pn[1] - 34, pn[2], pn[1] - 34, false) + await lab(`pin ${f(pd)}`, pn[0] - 24, pn[1] - 23, inside)
      + `<g ${tick}><line x1="${f(pn[0] - 40)}" x2="${f(pn[0] - 40)}" y1="${f(pn[3])}" y2="${f(st[1])}"/></g>` + await lab(`gap ${f(gp)}`, pn[0] - 56, (pn[3] + st[1]) / 2 + 11, inside);
    return { body: g, scale: 0.5, meta: { canvas: N, body, stem: sw, i: ih, pin: pd, gap: gp },
      caption: `The app icon on the Apple grid: a ${f(N)} canvas, the ${body} squircle, the i ${ih} tall, centred.` };
  } });

// the optical tiers of the vector icon: px ranges with the same stem (in s) and pin gap, read off LIMN.iconSpec
function iconTiers(maxPx) {
  const out = [];
  for (let px = 1; px <= maxPx; px++) {
    const sp = L.iconSpec(px), stem = r2(sp.w / L.s), last = out[out.length - 1];
    if (last && last.stem_s === stem && last.gd === sp.gd) last.to = px; else out.push({ from: px, to: px, stem_s: stem, gd: sp.gd });
  }
  return out;
}
const and = xs => xs.length < 2 ? `${xs.join("")}` : `${xs.slice(0, -1).join(", ")} and ${xs[xs.length - 1]}`;
const RAMP = [256, 128, 64, 40, 32, 24, 20, 16];
fig("icon/ramp", { ground: C.paper, dpr: true,
  build: async () => {
    let g = "", y = 0;
    for (const [th, name] of [["light", "Bone"], ["dark", "Ink"]]) {
      let x = 64; const base = y + RAMP[0];
      g += await T(name, { w: 500, size: 12, x: 0, y: base - RAMP[0] / 2 + 4, fill: C.muted });
      for (const px of RAMP) {
        g += place(L.icon(px, { theme: th, dpr: DPR }), x, base - px) + await T(`${px}`, { size: 11, x: x + px / 2, y: base + 20, anchor: "middle", fill: C.muted });
        x += px + 28;
      }
      y = base + 48;
    }
    const tiers = iconTiers(RAMP[0]), pixel = Object.keys(L.ICON_PX).map(Number);
    const range = (t, i) => i === 0 ? `up to ${t.to} px` : i === tiers.length - 1 ? `${t.from} px and up` : `${t.from}–${t.to} px`;
    return { body: g, scale: 1, meta: { sizes: RAMP, tiers, pixel },
      caption: `Sizes ${and(RAMP)} px. Stem and pin gap by size: ${tiers.map((t, i) => `${range(t, i)} ${t.stem_s}s and ${t.gd}s`).join("; ")}. ${and(pixel)} px are pixel drawings.` };
  } });

function pixelDrawing(svg, n, z, grid) {   // an n-pixel drawing drawn z times, with its pixel grid
  let d = ""; for (let i = 0; i <= n; i++) d += `M${i} 0V${n}M0 ${i}H${n}`;
  return `<g transform="scale(${z})"><g shape-rendering="crispEdges">${inner(svg)}</g><path class="guide" d="${d}" fill="none" stroke="${grid}" stroke-width="${r2(1 / z)}" opacity=".16"/></g>`;
}
const PX_SIDE = 256;   // each pixel drawing is drawn this many px wide
for (const n of Object.keys(L.ICON_PX).map(Number)) fig(`icon/px-${n}`, { ground: C.paper, png1x: true,
  build: async () => {
    const P = L.ICON_PX[n], [, bw] = P.body, [, sw, st, sb] = P.stem, [, qy, rows] = P.pin;
    return { body: pixelDrawing(L.icon(n, { dpr: 1 }), n, PX_SIDE / n, C.ink), scale: 1,
      meta: { body: bw, stem: [sw, sb - st], pin: [rows[0].length, rows.length], gap: st - (qy + rows.length), round_top: P.stem.length > 4 },
      caption: `The ${n} px icon, drawn pixel by pixel; the grid is the device pixel.` };
  } });

const FAV = Object.keys(L.FAVICON_PX).map(Number), FAV_SIDE = 128;   // favicon drawings, each drawn this many px wide
for (const [key, dark] of [["light", false], ["dark", true]]) fig(`icon/favicon-${key}`, {
  ground: dark ? "#35363a" : "#ffffff", png1x: true, dpr: true,
  build: async () => {
    const bg = dark ? "#35363a" : "#ffffff", fg = dark ? "#b9bcc2" : C.muted, pad = 24;
    let g = "", x = pad;
    for (const n of FAV) {
      const z = FAV_SIDE / n;
      g += place(pixelDrawing(L.favicon(n, { dpr: 1 }), n, z, dark ? "#ffffff" : C.ink), x, pad)
        + await T(`${n} px × ${z}`, { size: 11, x: x + FAV_SIDE / 2, y: pad + FAV_SIDE + 22, anchor: "middle", fill: fg });
      x += FAV_SIDE + 32;
    }
    x += 8;
    let y = pad + 22;
    for (const n of FAV) {   // at their own size, one above the other
      g += place(L.favicon(n, { dpr: DPR }), x, y) + await T(`${n} px`, { size: 11, x: x + n + 10, y: y + n / 2 + 4, fill: fg });
      y += n + 34;
    }
    const W = x + FAV[FAV.length - 1] + 48 + pad, H = pad + FAV_SIDE + 22 + pad;
    return { body: `<rect x="0" y="0" width="${W}" height="${H}" rx="12" fill="${bg}"/>` + g, scale: 1, meta: { sizes: FAV },
      caption: `The browser favicon on a ${key} tab: the same ink drawing on light and dark tabs, ${and(FAV)} px.` };
  } });

const TOUCH = 180;   // the home-screen icon (tools/build_icons.py TOUCH)
fig("icon/touch-180", { ground: null, png1x: true,
  build: async () => ({ body: L.icon(TOUCH, { bleed: true }), scale: 1, meta: { px: TOUCH },
    caption: `The ${TOUCH} px home-screen icon: the body fills the square (iOS rounds it).` }) });

/* ---------- color: the public tokens (sky is "On vermilion", the strokes and pin on the vermilion ground) ---------- */
const SWATCH = D.tokens;
fig("color/swatches", { ground: C.paper,
  build: async () => {
    let g = "", x = 0;
    for (const { key, name, use } of SWATCH) {
      g += `<rect x="${x + 0.5}" y="0.5" width="167" height="111" rx="6" fill="${C[key]}" stroke="${C.ink}" stroke-opacity=".08"/>`
        + await T(name, { w: 600, size: 15, x, y: 140 }) + await T(C[key], { size: 12, x, y: 162, fill: C.muted }) + await T(use, { size: 12, x, y: 180, fill: C.muted });
      x += 168 + 20;
    }
    return { body: g, scale: 1, meta: { tokens: SWATCH.map(t => t.key), count: SWATCH.length }, caption: `The ${SWATCH.length} colour tokens.` };
  } });

/* ---------- type (live: the PNG is Chromium with @font-face) ---------- */
const typefig = (id, caption, build, extra = {}) => fig(`type/${id}`, { ground: C.paper, live: true, caption, build, ...extra });
typefig("specimen-hero", "Development font specimen; input version recorded in the manifest. The 1.000 download excludes Hangul.", async () => {
  let g = "", y = 0;
  for (const [s, w, size, gap] of [["Limn Sans", 700, 120, 0], ["Pin it. Fix it. Done.", 400, 44, 70], ["다람쥐 헌 쳇바퀴에 타고파", 400, 44, 62], ["Aa Bb Gg Rr 0123456789 ?!&@", 300, 28, 50]]) {
    y += gap || size; g += await T(s, { w, size, x: 0, y, sample: true });
  }
  return { body: g, scale: 1 };
});
typefig("weights-ladder", "", async () => {
  let g = "", y = 0;
  for (const W of D.weights) {
    y += 56;
    g += await T(`${W.w}`, { w: 500, size: 13, x: 0, y: y - 4, fill: C.muted });
    const t = await tx(`Limn Sans ${W.name}`, { w: W.w, size: 40, x: 64, y, sample: true });
    g += t.svg + await T(`S ${W.S}`, { w: 500, size: 13, x: t.x1 + 24, y: y - 4, fill: C.muted });
  }
  const ws = D.weights.map(W => W.w);
  return { body: g, scale: 1, meta: { count: ws.length, from: ws[0], to: ws[ws.length - 1], upm: D.upm },
    caption: `${ws.length} weights, ${ws[0]} to ${ws[ws.length - 1]}; S is the stroke of each weight in font units (em ${D.upm}).` };
});
typefig("latin-hangul", "Experimental Latin/Hangul pairing, outside the 1.000 download: Hangul derived from NanumSquareRound, fitted to each weight.", async () => {
  let g = "", y = 0;
  for (const w of [300, 400, 700]) {
    y += 52;
    g += await T(`${w}`, { w: 500, size: 13, x: 0, y: y - 6, fill: C.muted });
    const a = await tx("Every pin points to one line.", { w, size: 32, x: 64, y, sample: true });
    g += a.svg + await T("핀 하나가 원문 한 줄을 가리킵니다.", { w, size: 32, x: a.x1 + 28, y, sample: true });
  }
  return { body: g, scale: 1 };
});
const GRID = [
  ["Latin", "ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz"],
  ["Figures", "0123456789"],
  ["Punctuation", ".,:;!?¡¿'\"‘’“”‹›«»()[]{}-–—‐/\\|&@#%‰*…·•§¶†‡_"],
  ["Accents", "ÀÁÂÃÄÅÆÇÈÉÊËÌÍÎÏÑÒÓÔÕÖØŒÙÚÛÜÝŸÞßàáâãäåæçèéêëìíîïñòóôõöøœùúûüýÿþðłŁšŠžŽčČřŘ"],
  ["Greek", "ΑΒΓΔΕΖΗΘΙΚΛΜΝΞΟΠΡΣΤΥΦΧΨΩαβγδεζηθικλμνξοπρσςτυφχψω"],
  ["Symbols", "+−×÷=≠≈≤≥±¬∞√∑∏∫∂µΩ°′″€£¥₩$¢¤©®™№←↑→↓↔○●□■△▲☆★♪℃㎡①②③"],
  ["Hangul", "가나다라마바사아자차카타파하림한글원고핀줄ㄱㄴㄷㄹㅁㅂㅅㅇㅈㅊㅋㅌㅍㅎㅏㅑㅓㅕㅗㅛㅜㅠㅡㅣ"],
];
const CMAP = new Set(D.cmap);
for (const W of D.weights) typefig(`glyph-grid-${W.w}`, "", async () => {
  const cw = 60, chh = 76, cols = 16;
  let g = "", y = 0;
  for (const [name, chars] of GRID) {
    const list = [...chars].filter(c => CMAP.has(c.codePointAt(0)));
    if (!list.length) continue;
    g += await T(name, { w: 500, size: 12, x: 0, y: y + 14, fill: C.muted });
    y += 24;
    for (let i = 0; i < list.length; i++) {
      const cx = (i % cols) * cw, cy = y + Math.floor(i / cols) * chh;
      g += `<rect class="guide" x="${cx + 0.5}" y="${cy + 0.5}" width="${cw}" height="${chh}" fill="none" stroke="${C.ink}" stroke-opacity=".12"/>`
        + await T(list[i], { w: W.w, size: 40, x: cx + cw / 2 + 0.5, y: cy + 52, anchor: "middle", sample: true });
    }
    y += Math.ceil(list.length / cols) * chh + 22;
  }
  return { body: g, scale: 1, meta: { w: W.w, total: D.coverage.total },
    caption: `Characters at ${W.w} ${W.name}: a sample of each set (${D.coverage.total} characters in all).` };
});
/* each row a setting of the feature; its label says on or off, and "(default)" only where the font sets the sample
   the same with no features asked for (HarfBuzz's glyph run compared) */
const FEAT = {
  kern: { text: "AVATAR Type, WAVE", rows: [{ kern: false }, { kern: true }] },
  tnum: { column: ["1,111.11", "7,980.40", "1,017.71"], rows: [{ pnum: true }, { tnum: true }] },
  pnum: { text: "In 2011, 1,114 of 7,481 notes", rows: [{ tnum: true }, { pnum: true }] },
  zero: { text: "0O 1000 R2D0", rows: [{ zero: false }, { zero: true }] },
  ss01: { text: "agate, ginger, a gag", rows: [{ ss01: false }, { ss01: true }] },
};
async function featLabel(texts, feat, size) {
  const same = (await Promise.all(texts.map(async t => (await shape(t, "LS400", size, {})).g === (await shape(t, "LS400", size, feat)).g))).every(Boolean);
  return Object.entries(feat).map(([k, v]) => `${k} ${v ? "on" : "off"}`).join(", ") + (same ? " (default)" : "");
}
for (const tag of D.features) {
  if (!FEAT[tag]) throw new Error(`no sample for the font's feature ${tag}`);
  typefig(`features-${tag}`, "", async () => {
    const S = FEAT[tag]; let g = "";
    if (S.column) {   // two columns, right-aligned: only tabular figures line up
      let x = 0;
      for (const feat of S.rows) {
        g += await T(await featLabel(S.column, feat, 44), { w: 500, size: 13, x, y: 0, fill: C.muted });
        for (const [i, v] of S.column.entries()) g += await T(v, { size: 44, feat, x: x + 250, y: 60 + i * 56, anchor: "end", sample: true });
        x += 330;
      }
    } else {
      let y = 0;
      for (const feat of S.rows) {
        g += await T(await featLabel([S.text], feat, 48), { w: 500, size: 13, x: 0, y: y, fill: C.muted });
        g += await T(S.text, { size: 48, feat, x: 0, y: y + 58, sample: true });
        y += 100;
      }
    }
    return { body: g, scale: 1, caption: `OpenType ${tag}.` };
  });
}
const BODY = D.weights.find(W => W.w === 400) || D.weights[Math.floor(D.weights.length / 2)];   // the text weight
const WATERFALL = [64, 48, 36, 28, 24, 20, 16, 14, 12], SMALL = [12, 13, 14, 15, 16];
typefig("waterfall", "", async () => {
  let g = "", y = 0;
  for (const size of WATERFALL) {
    y += Math.max(size * 1.25, 26);
    g += await T(`${size}`, { w: 500, size: 12, x: 0, y, fill: C.muted }) + await T("Sphinx of black quartz, judge my vow.", { w: BODY.w, size, x: 44, y, sample: true });
  }
  return { body: g, scale: 1, meta: { sizes: WATERFALL, w: BODY.w },
    caption: `Limn Sans ${BODY.name} from ${WATERFALL[0]} to ${WATERFALL[WATERFALL.length - 1]} px.` };
});
typefig("sizes-12-16", "", async () => {
  let g = "", y = 0;
  for (const size of SMALL) {
    y += 26;
    g += await T(`${size} px`, { w: 500, size: 11, x: 0, y, fill: C.muted }) + await T("Pin it, fix it, done. 핀을 꽂고 고칩니다. 0123456789", { w: BODY.w, size, x: 52, y, sample: true });
  }
  return { body: g, scale: 1, meta: { sizes: SMALL, w: BODY.w },
    caption: `Small sizes, ${SMALL[0]} to ${SMALL[SMALL.length - 1]} px, ${BODY.name}: the PNGs are Chromium's hinted rendering of the font files.` };
}, { png1x: true });

/* ---------- motion: the curve, its handles, the time ---------- */
const nf = v => `${+(+v).toFixed(2)}`;
async function curve(title, lines, P) {
  const B = 200, X = t => r2(t * B), Y = p => r2(B - p * B), [x1, y1, x2, y2] = P;
  let g = `<rect class="guide" x="0" y="0" width="${B}" height="${B}" fill="none" stroke="${C.ink}" stroke-opacity=".18"/>`
    + `<path class="guide" d="M0 ${B}L${B} 0" stroke="${C.ink}" stroke-opacity=".12" stroke-dasharray="4 4"/>`
    + `<path d="M${X(0)} ${Y(0)}L${X(x1)} ${Y(y1)}M${X(1)} ${Y(1)}L${X(x2)} ${Y(y2)}" stroke="${C.ver}" stroke-width="1.5"/>`
    + `<path d="M${X(0)} ${Y(0)}C${X(x1)} ${Y(y1)} ${X(x2)} ${Y(y2)} ${X(1)} ${Y(1)}" fill="none" stroke="${C.ink}" stroke-width="3" stroke-linecap="round"/>`
    + `<circle cx="${X(x1)}" cy="${Y(y1)}" r="5" fill="${C.ver}"/><circle cx="${X(x2)}" cy="${Y(y2)}" r="5" fill="${C.ver}"/>`
    + `<circle cx="${X(0)}" cy="${Y(0)}" r="3.5" fill="${C.ink}"/><circle cx="${X(1)}" cy="${Y(1)}" r="3.5" fill="${C.ink}"/>`
    + await T("time", { size: 11, x: B, y: B + 16, anchor: "end", fill: C.muted });
  let y = B + 44;
  g += await T(title, { w: 600, size: 15, x: 0, y });
  for (const l of lines) { y += 20; g += await T(l, { size: 12, x: 0, y, fill: C.muted }); }
  return { body: g, scale: 1 };
}
const bez = P => `cubic-bezier(${P.map(nf).join(", ")})`;
const MO = D.motion;
fig("motion/drop", { ground: C.paper, caption: "Pin drop: when a pin is saved, and the logo on the first screen. Once.",
  build: () => curve("Pin drop", [`${nf(MO.drop.duration_s)} s`, bez(MO.drop.curve)], MO.drop.curve) });
fig("motion/write", { ground: C.paper, caption: "Write: while a PDF builds, each letter is wiped in from the left, the pin last.",
  build: () => curve("Write", [`${nf(MO.write.duration_s)} s per letter`, bez(MO.write.curve)], MO.write.curve) });
fig("motion/ripple", { ground: C.paper, caption: "Ripple: a new pin arrives; the ring spreads once, the pin drops as in pin drop.",
  build: () => curve("Ripple", [`ring ${nf(MO.ripple.duration_s)} s`, bez(MO.ripple.curve)], MO.ripple.curve) });
fig("motion/light", { ground: C.paper, caption: "Light: while searching, a light sweeps the word and gathers into the dot.",
  build: () => curve("Light", [`sweep ${nf(MO.light.sweep_s)} s · gather ${nf(MO.light.gather_s)} s`, bez(MO.light.curve)], MO.light.curve) });

/* ---------- use ---------- */
fig("use/tab", { ground: null, dpr: true, caption: "The favicon in a browser tab strip, light and dark.",
  build: async () => {
    const W = 560, tw = 240;
    let g = "", y = 0;
    for (const th of [
      { strip: "#dee1e6", tab: "#ffffff", fg: "#1f1f1f", dim: "#45474a", pill: "#f1f3f4" },
      { strip: "#1f2023", tab: "#35363a", fg: "#f1f1f1", dim: "#b9bcc2", pill: "#28292c" }]) {
      g += `<path d="M0 ${y + 10}Q0 ${y} 10 ${y}H${W - 10}Q${W} ${y} ${W} ${y + 10}V${y + 82}H0Z" fill="${th.strip}"/>`
        + `<path d="M8 ${y + 42}V${y + 16}Q8 ${y + 8} 16 ${y + 8}H${8 + tw - 8}Q${8 + tw} ${y + 8} ${8 + tw} ${y + 16}V${y + 42}Z" fill="${th.tab}"/>`
        + place(L.favicon(16, { dpr: DPR }), 20, y + 17) + await T(D.label, { size: 12.5, x: 44, y: y + 29.5, fill: th.fg })
        + await T("New Tab", { size: 12.5, x: 8 + tw + 18, y: y + 29.5, fill: th.dim })
        + `<rect x="0" y="${y + 42}" width="${W}" height="40" fill="${th.tab}"/><rect x="72" y="${y + 48}" width="${W - 96}" height="28" rx="14" fill="${th.pill}"/>`;
      y += 82 + 16;
    }
    return { body: g, scale: 1 };
  } });
fig("use/dock", { ground: null, dpr: true, caption: "The app icon in a Dock, on a light and a dark wallpaper.",
  build: async () => {
    const W = 720, H = 150, n = 58, gap = 9;
    const ph = c => `<svg width="${n}" height="${n}" viewBox="0 0 1024 1024"><path d="${L.SQ}" fill="${c}"/></svg>`;
    let g = "", y = 0;
    const defs = `<linearGradient id="wl" x1="0" y1="0" x2="1" y2="1"><stop offset="0" stop-color="#f0d9c9"/><stop offset=".55" stop-color="#d7d3e8"/><stop offset="1" stop-color="#c4d8e7"/></linearGradient>`
      + `<linearGradient id="wd" x1=".33" y1="0" x2=".67" y2="1"><stop offset="0" stop-color="#1b2338"/><stop offset=".55" stop-color="#2b2540"/><stop offset="1" stop-color="#10151f"/></linearGradient>`;
    for (const [th, grad, label, bar, line, dot, lc] of [
      ["light", "wl", "Light wallpaper", "rgba(255,255,255,.32)", "rgba(255,255,255,.5)", "rgba(0,0,0,.55)", "rgba(0,0,0,.55)"],
      ["dark", "wd", "Dark wallpaper", "rgba(40,44,60,.45)", "rgba(255,255,255,.14)", "rgba(255,255,255,.7)", "rgba(255,255,255,.6)"]]) {
      const slots = [ph("#e8e8ea"), ph("#3a7bd5"), ph("#8e8e93"), L.icon(n, { theme: th, dpr: DPR }), ph("#34c759"), ph("#ff9f0a")];
      const bw = slots.length * n + (slots.length - 1) * gap + 20, bx = (W - bw) / 2, by = y + H - 16 - (n + 18);
      g += `<rect x="0" y="${y}" width="${W}" height="${H}" rx="14" fill="url(#${grad})"/>` + await T(label, { w: 600, size: 12, x: 22, y: y + 28, fill: lc })
        + `<rect x="${bx}" y="${by}" width="${bw}" height="${n + 18}" rx="20" fill="${bar}" stroke="${line}"/>`;
      slots.forEach((s, i) => { g += place(s, bx + 10 + i * (n + gap), by + 8); });
      g += `<circle cx="${bx + 10 + 3 * (n + gap) + n / 2}" cy="${by + n + 13}" r="2" fill="${dot}"/>`;
      y += H + 16;
    }
    return { defs, body: g, scale: 1 };
  } });

/* ---------- entry points (Python) ---------- */
async function build(id, o = {}) {
  const def = FIG.get(id); if (!def) throw new Error(`no figure ${id}`);
  LIVE = !!o.live; DPR = o.dpr || 1; RUNS = []; SEED = 1;
  const g = await def.build();
  let frame = o.frame;
  if (!frame) { const G = geomBox(g.body, g.defs); frame = outward(frameOf(G, await paintBox(g.body, g.defs, G, g.scale))); }
  const W = r2(frame[2] * g.scale), H = r2(frame[3] * g.scale);
  const svg = `<svg xmlns="${NS}" viewBox="${frame.join(" ")}" width="${W}" height="${H}">${g.defs ? `<defs>${g.defs}</defs>` : ""}${g.body}</svg>`;
  const caption = g.caption || def.caption || "";
  if (/\d/.test(def.caption || "") && !g.caption) throw new Error(`${id}: a caption with numbers must be built from the data`);
  return { svg, w: W, h: H, frame, scale: g.scale, texts: [...new Set(RUNS.map(r => r[0]))],
    min_text_px: RUNS.length ? r2(Math.min(...RUNS.map(r => r[1])) * g.scale) : null,
    ground: def.ground ?? null, caption, meta: g.meta || null, live: !!def.live, png1x: !!def.png1x, dpr_drawn: !!def.dpr };
}
window.FIG_ids = () => [...FIG.keys()];
window.FIG_build = build;
window.FIG_png = async (id, o) => {    // canvas raster of the figure drawn for o.dpr, in the frame of the 1x SVG
  const r = await build(id, { dpr: o.dpr, frame: o.frame });
  const img = await image(r.svg), c = document.createElement("canvas");
  c.width = Math.ceil(r.w * o.dpr - 1e-6); c.height = Math.ceil(r.h * o.dpr - 1e-6);
  c.getContext("2d").drawImage(img, 0, 0, r.w * o.dpr, r.h * o.dpr);
  return c.toDataURL("image/png");
};
window.FIG_stage = async (id, o) => {  // the live figure on the page, @font-face loaded; each run's width vs HarfBuzz's
  const r = await build(id, { dpr: o.dpr, frame: o.frame, live: true });
  const st = document.getElementById("stage"); st.innerHTML = r.svg;
  await Promise.all(D.faces.map(fc => document.fonts.load(`16px ${fc}`)));
  await document.fonts.ready;
  const miss = D.faces.filter(fc => !document.fonts.check(`16px ${fc}`));
  if (miss.length) throw new Error(`@font-face not loaded: ${miss}`);
  const dx = [...st.querySelectorAll("text")].map(t => [Math.abs(t.getComputedTextLength() - +t.dataset.adv), t.textContent, t.getAttribute("font-family")]);
  const worst = dx.reduce((a, b) => (b[0] > a[0] ? b : a), [0, "", ""]);
  return { w: r.w, h: r.h, runs: dx.length, max_dx: worst[0], worst: worst.slice(1) };
};
window.FIG_unstage = () => { document.getElementById("stage").innerHTML = ""; };
window.FIG_facts = () => {
  const pairs = [["ink", "paper", "text", 4.5], ["ver", "paper", "graphic (the pin)", 3], ["cream", "ink", "text", 4.5],
    ["ver", "ink", "graphic (the pin)", 3], ["ink", "bone", "icon stroke", 3], ["sky", "ver", "graphic", 3]];
  const px = n => { const P = L.ICON_PX[n], [, bw] = P.body, [, sw, st, sb] = P.stem, [, qy, rows] = P.pin;
    return { body: bw, stem: [sw, sb - st], pin: [rows[0].length, rows.length], gap: st - (qy + rows.length), round_top: P.stem.length > 4 }; };
  const fav = n => { const P = L.FAVICON_PX[n], [, bw] = P.body, [, sw, st, sb] = P.stem, [, qy, rows] = P.pin;
    return { body: bw, stem: [sw, sb - st], pin: [rows[0].length, rows.length], gap: st - (qy + rows.length) }; };
  return {
    colors: Object.fromEntries(D.tokens.map(t => [t.key, C[t.key]])),
    color_tokens: D.tokens.map(t => ({ ...t, hex: C[t.key] })),
    colors_other: { muted: C.muted },
    contrast: pairs.map(([fg, bg, use, need]) => { const ratio = +L.contrast(C[fg], C[bg]).toFixed(2); return { fg, bg, ratio, use, need, pass: ratio >= need }; }),
    logo: { s: L.s, xh: L.XH, xo: L.XO, asc: L.ASC, desc: L.DESC, cap: L.CAP, pin_r: L.r, pin_cy: L.CY, pin_top: f(-(L.CY - L.r)),
      gd: L.P.gd, gap: f(-L.XH - (L.CY + L.r)), clear_space: F.xh / 2, logo_kern: L.LOGO_KERN, stems: M.stems,
      min_gd: Object.fromEntries([12, 16, 18, 24, 32, 48].map(h => [h, L.gdFor(h)])) },
    icon: { px: Object.fromEntries(Object.keys(L.ICON_PX).map(n => [n, px(n)])), favicon: Object.fromEntries(Object.keys(L.FAVICON_PX).map(n => [n, fav(n)])),
      tiers: iconTiers(1024) },
  };
};
})();
"""


def page_html(files, data):
    faces = "\n".join(f'@font-face{{font-family:"LS{f["w"]}";src:url("{f["woff2"]}") format("woff2")}}' for f in files["files"])
    return PAGE % {"faces": faces, "data": json.dumps(data, ensure_ascii=False)}


def router(html):
    def route(r):
        path = r.request.url[len(ORIGIN):].split("?")[0]
        if path in ("", "index.html"):
            return r.fulfill(status=200, content_type="text/html; charset=utf-8", body=html)
        if path == "figures.js":
            return r.fulfill(status=200, content_type="text/javascript; charset=utf-8", body=FIGURES_JS)
        p = (SITE / path).resolve()
        if SITE in p.parents and p.is_file():
            ct = {".js": "text/javascript; charset=utf-8", ".woff2": "font/woff2", ".css": "text/css"}.get(p.suffix, "application/octet-stream")
            return r.fulfill(status=200, content_type=ct, body=p.read_bytes())
        return r.fulfill(status=404, body="")
    return route


def png_bytes(data_url_or_bytes):
    """a PNG as Pillow writes it: no text chunks, no metadata"""
    raw = data_url_or_bytes
    if isinstance(raw, str):
        raw = base64.b64decode(raw.split(",", 1)[1])
    im = Image.open(io.BytesIO(raw))
    im.load()
    b = io.BytesIO()
    im.convert("RGBA").save(b, format="PNG", optimize=True)
    return b.getvalue()


# ---------------------------------------------------------------- the app screens: a throwaway Limn instance

SAMPLE_TEX = r"""\documentclass[11pt]{article}
\usepackage[letterpaper,margin=1.1in]{geometry}
\usepackage{amsmath}
\usepackage{booktabs}
\setlength{\parindent}{0pt}
\setlength{\parskip}{0.6\baselineskip}
\title{Sample paper}
\author{A. Author \and B. Author}
\date{}
\begin{document}
\maketitle

\begin{abstract}
This sample paper shows how a manuscript reads in a review tool. It has a short introduction, one method with a single equation, a small table of results and a conclusion. Every sentence here is placeholder text, written so that a reader can point at a sentence, an equation or a table cell and leave a note on it.
\end{abstract}

\section{Introduction}
Reviewing a draft is a conversation about places in a document. A reader marks a spot, writes what should change, and the writer finds the same spot in the source. When the two sides share a precise address for each spot, the conversation gets shorter and fewer notes are lost between versions.

This paper uses a simple example to describe such an address. We count how long it takes to resolve a note, from the moment it is written to the moment the change is confirmed, and we compare two ways of pointing at the text.

\section{Method}
Each note $n$ has a position $p_n$ in the rendered page and a line range $[a_n, b_n]$ in the source. We treat the time to resolve a note as the sum of the time to locate it and the time to edit it,
\begin{equation}
  T_n = T_n^{\mathrm{locate}} + T_n^{\mathrm{edit}},
  \label{eq:time}
\end{equation}
and we estimate both parts from a log of review sessions. The locate time depends on how far the address is from the text it names, so a note that carries its own line range should need almost none.

We ran twelve review sessions on three short documents. In half of the sessions the notes carried only a page number; in the other half they carried the page and the source line range.

\section{Results}
Table~\ref{tab:results} lists the median times. Notes with a line range were located in a fraction of the time, while the edit time stayed about the same.

\begin{table}[h]
  \centering
  \begin{tabular}{lrrr}
    \toprule
    Address & Notes & Locate (s) & Edit (s) \\
    \midrule
    Page only & 96 & 41 & 64 \\
    Page and lines & 104 & 6 & 61 \\
    \bottomrule
  \end{tabular}
  \caption{Median time per note in each part of Eq.~\eqref{eq:time}.}
  \label{tab:results}
\end{table}

\section{Conclusion}
A shared address for each spot in a document removes most of the time spent looking for it. The example is small, but the same measure applies to any draft that is written in one form and read in another.

\end{document}
"""
# the pins on the sample: each a phrase that starts a paragraph on page 1, and each paragraph one source line, so the
# pin names one line and its number badge falls in the left margin (the sample sets paragraphs flush left), not on a
# word; the note; fix or question
SAMPLE_PINS = (("Reviewing a draft is a conversation about places", "Say who the readers are here: co-authors, or referees?", "fix"),
               ("This paper uses a simple example", "Does address mean the line range here?", "question"),
               ("We ran twelve review sessions", "Give the number of reviewers as well as the sessions.", "fix"))
SAMPLE_GIT_DATE = "2026-01-01T09:00:00+0000"  # the sample's one commit, dated so its hash is the same on every run
TMP_PREFIX = "limn-figures-"
# run in the server's process before exec: on Linux the server gets SIGTERM when the export dies, even by SIGKILL;
# if the export is already gone it does not start at all
PDEATH = """import ctypes, os, signal, sys
if sys.platform.startswith("linux"):
    ctypes.CDLL(None, use_errno=True).prctl(1, int(signal.SIGTERM))  # PR_SET_PDEATHSIG
if os.getppid() != int(os.environ.pop("FIGURES_PARENT")):
    sys.exit("the export that started this server is gone")
os.execv(sys.executable, [sys.executable] + sys.argv[1:])
"""


def free_port():
    """a port the OS picks for 127.0.0.1 (its ephemeral range, above the fixed ports long-running instances use)"""
    s = socket.socket()
    s.bind(("127.0.0.1", 0))
    port = s.getsockname()[1]
    s.close()
    return port


NO_PROXY = urllib.request.build_opener(urllib.request.ProxyHandler({}))  # 127.0.0.1 never goes through http_proxy


def api(base, path, body=None):
    data = None if body is None else json.dumps(body).encode()
    rq = urllib.request.Request(base + path, data=data, method="GET" if body is None else "POST",
                                headers={"Content-Type": "application/json"} if body is not None else {})
    with NO_PROXY.open(rq, timeout=30) as r:
        return json.load(r)


def pdf_words(pdf, page):
    """the words of a page: (x0, y0, x1, y1, text), points, y down (pdftotext -bbox)"""
    xml = subprocess.run(["pdftotext", "-bbox", "-f", str(page), "-l", str(page), str(pdf), "-"],
                         capture_output=True, text=True, check=True, timeout=60).stdout
    return [(float(a), float(b), float(c), float(d), w) for a, b, c, d, w in
            re.findall(r'<word xMin="([\d.]+)" yMin="([\d.]+)" xMax="([\d.]+)" yMax="([\d.]+)">([^<]*)</word>', xml)]


def phrase_box(words, phrase):
    """the box (points, y down) of the words of phrase in a row on one line"""
    want = phrase.split()
    for i in range(len(words) - len(want) + 1):
        run = words[i:i + len(want)]
        if [w[4] for w in run] == want and max(w[1] for w in run) - min(w[1] for w in run) < 2:
            return min(w[0] for w in run) - 1, min(w[1] for w in run) - 1, max(w[2] for w in run) + 1, max(w[3] for w in run) + 1
    raise RuntimeError(f"phrase not on the page: {phrase!r}")


def contrast(a, b):
    x, y = lum(a), lum(b)
    return (max(x, y) + 0.05) / (min(x, y) + 0.05)


def chip_accent(py, colors):
    """the demo's accent: the first of the brand's vermilion and ink that keeps CHIP_TEXT_CONTRAST under the label
    chip's text, which Limn sets on the accent (--brand-foreground of its viewer tokens)"""
    css = subprocess.run([py, "-c", "import limn, pathlib; print((pathlib.Path(limn.__file__).parent / 'viewer' / 'css' / 'tokens.css').read_text())"],
                         capture_output=True, text=True, check=True, timeout=60).stdout
    fg = re.search(r"--brand-foreground:\s*(#[0-9a-fA-F]{6})", css).group(1)
    for key in ("ver", "ink"):
        r = contrast(colors[key], fg)
        if r >= CHIP_TEXT_CONTRAST:
            return {"accent": colors[key], "token": key, "chip_text": fg, "chip_contrast": round(r, 2),
                    "tried": {k: round(contrast(colors[k], fg), 2) for k in ("ver", "ink")}}
    raise RuntimeError(f"neither vermilion nor ink keeps {CHIP_TEXT_CONTRAST}:1 under the chip text {fg}")


def clear_stale():
    """temporary folders of earlier runs that died without cleaning up (SIGKILL): each names its owner's PID"""
    for d in Path(tempfile.gettempdir()).glob(TMP_PREFIX + "*"):
        try:
            pid = int((d / "owner").read_text())
        except (OSError, ValueError):
            continue
        if pid == os.getpid():
            continue
        try:
            os.kill(pid, 0)
        except ProcessLookupError:
            shutil.rmtree(d, ignore_errors=True)
        except PermissionError:
            pass


def stop_group(proc):
    """SIGTERM the server's process group (its own session: only what this export started), SIGKILL after 15 s"""
    try:
        os.killpg(proc.pid, signal.SIGTERM)
    except ProcessLookupError:
        return
    try:
        proc.wait(timeout=15)
    except subprocess.TimeoutExpired:
        os.killpg(proc.pid, signal.SIGKILL)
        proc.wait(timeout=5)


BADGES_JS = """() => {
  const pg = document.querySelector('.pg canvas.vb').getBoundingClientRect();
  return { page: [pg.x, pg.y, pg.width, pg.height],
           badges: [...document.querySelectorAll('.mark b')].map(b => { const r = b.getBoundingClientRect(); return [r.x, r.y, r.width, r.height, b.textContent]; }) };
}"""


def app_screens(out, browser, limn_from, colors):
    """use/app-light.png and use/app-dark.png: the Limn app on the sample manuscript, English interface, the sample
    pins. The instance is Limn from limn_from in uv's cache (not an installed limn), with HOME, XDG folders,
    manuscript and state in one temporary folder, bound to 127.0.0.1 on a free port. Whatever ends the export
    (an error, SIGTERM, SIGHUP, Ctrl-C) stops the server's process group and removes the folder; if the export is
    killed outright, the server stops on its own (PR_SET_PDEATHSIG) and the next run removes the folder.
    Checked on the page before each capture: no page errors, no forbidden string, the label shown, the build line
    names the sample's commit, and no pin badge covers a word of the PDF."""
    clear_stale()
    tmp = proc = log = None
    shots = {}
    try:
        py = subprocess.run(["uv", "tool", "run", "--from", limn_from, "python", "-c", "import sys, limn; print(sys.executable)"],
                            capture_output=True, text=True, timeout=900, check=True).stdout.strip().splitlines()[-1]
        acc = chip_accent(py, colors)
        tmp = Path(tempfile.mkdtemp(prefix=TMP_PREFIX))
        (tmp / "owner").write_text(str(os.getpid()))
        ms, state, home = tmp / "manuscript", tmp / "state", tmp / "home"
        for d in (ms, state, home):
            d.mkdir()
        (ms / "main.tex").write_text(SAMPLE_TEX, encoding="utf-8")
        env = {k: v for k, v in os.environ.items() if not k.startswith(("LIMN_", "XDG_", "GIT_"))}
        env.update(HOME=str(home), XDG_CONFIG_HOME=str(home / ".config"), XDG_DATA_HOME=str(home / ".local/share"),
                   XDG_STATE_HOME=str(home / ".local/state"), XDG_CACHE_HOME=str(home / ".cache"))
        # the sample is a repository with one commit, so the viewer's build line names a commit instead of "-"
        genv = dict(env, GIT_CONFIG_NOSYSTEM="1", GIT_AUTHOR_DATE=SAMPLE_GIT_DATE, GIT_COMMITTER_DATE=SAMPLE_GIT_DATE)
        for args in (["init", "-q"], ["add", "main.tex"],
                     ["-c", "user.name=A. Author", "-c", "user.email=author@example.com", "-c", "commit.gpgsign=false", "commit", "-q", "-m", LABEL]):
            subprocess.run(["git", "-C", str(ms), *args], env=genv, check=True, capture_output=True, timeout=60)
        head = subprocess.run(["git", "-C", str(ms), "rev-parse", "--short", "HEAD"], env=genv, capture_output=True, text=True, check=True).stdout.strip()
        port = free_port()
        base = f"http://127.0.0.1:{port}"
        log = open(tmp / "server.log", "wb")
        proc = subprocess.Popen([py, "-c", PDEATH, "-m", "limn", "serve", "--manuscript", str(ms), "--main", "main.tex",
                                 "--port", str(port), "--bind", "127.0.0.1", "--state-dir", str(state), "--auth", "local",
                                 "--local-user", "author", "--label", LABEL, "--accent", acc["accent"]],
                                env=dict(env, FIGURES_PARENT=str(os.getpid())), stdout=log, stderr=subprocess.STDOUT,
                                start_new_session=True)
        (tmp / "server.pid").write_text(str(proc.pid))
        meta, t0 = None, time.time()
        while time.time() - t0 < 240:
            if proc.poll() is not None:
                raise RuntimeError("the demo server exited: " + (tmp / "server.log").read_text(errors="replace")[-800:])
            try:
                meta = api(base, "/api/meta")
                if (meta.get("last_build") or {}).get("state") == "ok" and not meta.get("building"):
                    break
            except OSError:
                pass
            time.sleep(0.5)
        else:
            raise RuntimeError("the demo PDF did not build in 240 s")
        pw, ph = meta["pages"][0]["pt_w"], meta["pages"][0]["pt_h"]
        words = pdf_words(state / "build" / "main.pdf", 1)
        pins = []
        for phrase, note, kind in SAMPLE_PINS:
            x0, y0, x1, y1 = phrase_box(words, phrase)
            pk = api(base, "/api/pick", {"page": 1, "x0": x0, "y0": y0, "x1": x1, "y1": y1,
                                         "frac": [x0 / pw, y0 / ph, (x1 - x0) / pw, (y1 - y0) / ph]})
            if pk.get("error"):
                raise RuntimeError(f"pick failed for {phrase!r}: {pk['error']}")
            if pk["lo"] != pk["hi"]:
                raise RuntimeError(f"the sample pin {phrase!r} names lines {pk['lo']}-{pk['hi']}, not one line")
            pin = {k: pk[k] for k in ("file", "name", "page", "lo", "hi", "raw_lo", "raw_hi", "kind", "via", "score", "frac", "quote", "pdf_build") if k in pk}
            pin.update(note=note, kind_req=kind, scope=pk.get("default_level"))
            api(base, "/api/pin", pin)
            pins.append({"line": pk["lo"], "kind": kind, "note": note})
        for theme in ("light", "dark"):
            ctx = browser.new_context(viewport={"width": APP_VIEW[0], "height": APP_VIEW[1]}, device_scale_factor=2)
            ctx.add_init_script("localStorage.setItem('pinPrefs', JSON.stringify({theme: %s, coach: {mouse: 1, touch: 1, sel: 1, side: 1}}));"
                                "localStorage.setItem('limnLang', 'en');" % json.dumps(theme))
            pg = ctx.new_page()
            errs = []
            pg.on("pageerror", lambda e: errs.append(str(e)))
            pg.goto(base + "/?lang=en", wait_until="networkidle")
            pg.wait_for_function("() => document.querySelectorAll('.pg canvas.vb').length > 0 && document.querySelectorAll('.mark b').length >= %d" % len(SAMPLE_PINS), timeout=60000)
            pg.wait_for_timeout(2500)
            seen = pg.evaluate("() => document.title + '\\n' + document.body.innerText")
            bad = [w for w in FORBIDDEN if w.lower() in seen.lower()] + ([LABEL] if LABEL not in seen else [])
            if " · - · " in seen or head not in seen:
                bad.append(f"the build line does not name the sample's commit {head}")
            B = pg.evaluate(BADGES_JS)
            px, py0, pwid = B["page"][0], B["page"][1], B["page"][2]
            k = pwid / pw   # CSS px per point on page 1
            for bx, by, bw, bh, label in B["badges"]:
                for x0, y0, x1, y1, w in words:
                    wx0, wy0, wx1, wy1 = px + x0 * k, py0 + y0 * k, px + x1 * k, py0 + y1 * k
                    if min(bx + bw, wx1) - max(bx, wx0) > 0.5 and min(by + bh, wy1) - max(by, wy0) > 0.5:
                        bad.append(f"pin badge {label} covers the word {w!r}")
            if errs or bad:
                raise RuntimeError(f"app screen {theme}: page errors {errs}, checks {bad}")
            shots[theme] = png_bytes(pg.screenshot())
            ctx.close()
    finally:
        # a second signal must not cut the clean-up short
        held = {s: signal.signal(s, signal.SIG_IGN) for s in (signal.SIGTERM, signal.SIGHUP, signal.SIGINT)}
        try:
            if proc is not None:
                stop_group(proc)
            if log is not None:
                log.close()
            if tmp is not None:
                shutil.rmtree(tmp, ignore_errors=True)
        finally:
            for s, h in held.items():
                signal.signal(s, h)
    entries = []
    for theme, data in shots.items():
        name = f"use/app-{theme}.png"
        (out / name).write_bytes(data)
        entries.append({"id": f"use/app-{theme}", "file": name, "w": APP_VIEW[0], "h": APP_VIEW[1], "scale": 2,
                        "png": {"2x": name}, "ground": None,
                        "caption": f"The Limn app ({theme} theme) on a sample manuscript: {len(pins)} pins, the PDF and the pin list.",
                        "texts": [LABEL] + [p["note"] for p in pins]})
    demo = {"limn": limn_from.rsplit("@", 1)[-1], "label": LABEL, "viewport": list(APP_VIEW), "scale": 2,
            "pin_count": len(pins), "pins": pins, "head": head, "badges_clear": True, **acc,
            "accent_rule": f"the first of ver, ink that keeps {CHIP_TEXT_CONTRAST}:1 under the label chip's text"}
    return entries, demo


# ---------------------------------------------------------------- main

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default=str(SITE / "figures"))
    ap.add_argument("--only", help="figure ids starting with this (a partial run; no manifest)")
    ap.add_argument("--no-app", action="store_true", help="skip the app screens (the manifest then lacks them)")
    ap.add_argument("--limn", default=LIMN_FROM, help="uv tool run --from source of Limn for the app screens")
    a = ap.parse_args()
    # SIGTERM / SIGHUP end the run the way an error does, so every finally runs (the demo server is stopped and its
    # folder removed); Ctrl-C already does. make figures execs each step, so a signal to make reaches this process.
    def on_signal(n, _frame):
        raise SystemExit(128 + n)
    for s in (signal.SIGTERM, signal.SIGHUP):
        signal.signal(s, on_signal)
    out = Path(a.out).resolve()
    # only a figures folder is cleared: one this tool wrote (it has manifest.json, or only its group folders)
    if out.exists() and any(p.name not in GROUPS + ("manifest.json",) for p in out.iterdir()):
        sys.exit(f"export_figures: {out} holds other files; give an empty folder or one this tool wrote")
    out.mkdir(parents=True, exist_ok=True)
    (out / "manifest.json").unlink(missing_ok=True)   # a partial run has none either: the old one would not describe it
    if not a.only:
        for g in GROUPS:
            shutil.rmtree(out / g, ignore_errors=True)
    for g in GROUPS:
        (out / g).mkdir(exist_ok=True)

    play = load_js(SITE / "limn-font-play.js", "window.LIMN_PLAY=")
    files = load_js(SITE / "fonts" / "fonts.js", "window.LIMN_FONT_FILES=")
    load_js(SITE / "limn-font.js", "window.LIMN_FONT=")  # present (the brand drawing)
    ttfs = {str(f["w"]): TTFont(SITE / f["ttf"]) for f in files["files"]}
    cmaps = {w: set(t.getBestCmap()) for w, t in ttfs.items()}
    cmap = set.intersection(*cmaps.values())
    if any(c != cmap for c in cmaps.values()):
        sys.exit("export_figures: the weights' cmaps differ - coverage would depend on the weight")
    feats = sorted(set.union(*(set(font_features(t)) for t in ttfs.values())))
    weights = weights_of(play, files)
    cov = coverage(cmap)
    mo = motion(SITE / "limn-pages.css")
    data = {"weights": [{"w": int(w), **v} for w, v in weights.items()], "cmap": sorted(cmap), "coverage": cov,
            "features": feats, "motion": mo, "faces": [f"LS{f['w']}" for f in files["files"]], "label": LABEL,
            "tokens": list(TOKENS), "upm": files["upm"]}
    shaper = Shaper(files)
    figures, fontface = [], {"runs": 0, "max_dx_px": 0.0, "figures": 0}
    with sync_playwright() as p:
        br = p.chromium.launch(channel="chromium")
        pages = {}
        for dpr in (1, 2):
            ctx = br.new_context(device_scale_factor=dpr, viewport={"width": 1600, "height": 1200})
            ctx.route(ORIGIN + "**", router(page_html(files, data)))
            pg = ctx.new_page()
            errs = []
            pg.on("pageerror", lambda e, errs=errs: errs.append(str(e)))
            pg.on("console", lambda m, errs=errs: m.type == "error" and errs.append(m.text))
            pg.expose_function("limnShape", shaper.shape)
            pg.goto(ORIGIN)
            if errs:
                sys.exit("export_figures: page errors: " + "; ".join(errs))
            pages[dpr] = pg
        p1 = pages[1]
        facts = p1.evaluate("() => FIG_facts()")
        ids = [i for i in p1.evaluate("() => FIG_ids()") if not a.only or i.startswith(a.only)]
        for fid in ids:
            r = p1.evaluate("(id) => FIG_build(id)", fid)
            svg_name = fid + ".svg"
            (out / svg_name).write_text(r["svg"] + "\n", encoding="utf-8")
            entry = {"id": fid, "file": svg_name, "w": r["w"], "h": r["h"], "frame": r["frame"], "scale": r["scale"],
                     "png": {}, "ground": r["ground"], "caption": r["caption"], "texts": r["texts"], "min_text_px": r["min_text_px"],
                     "live": r["live"], "dpr_drawn": r["dpr_drawn"]}
            if r["meta"]:
                entry["meta"] = r["meta"]
            for k in ((1, 2) if r["png1x"] else (2,)):
                name = f"{fid}@{k}x.png"
                if r["live"]:
                    pg = pages[k]
                    cw, ch = math.ceil(r["w"] * k - 1e-6) / k, math.ceil(r["h"] * k - 1e-6) / k  # as FIG_png: whole device px
                    pg.set_viewport_size({"width": math.ceil(cw) + 2, "height": math.ceil(ch) + 2})
                    st = pg.evaluate("([id, f, d]) => FIG_stage(id, {frame: f, dpr: d})", [fid, r["frame"], k])
                    shot = pg.screenshot(clip={"x": 0, "y": 0, "width": cw, "height": ch}, omit_background=True)
                    pg.evaluate("() => FIG_unstage()")
                    fontface["runs"] += st["runs"] if k == 2 else 0
                    fontface["max_dx_px"] = round(max(fontface["max_dx_px"], st["max_dx"]), 3)
                    if st["max_dx"] > 0.5:
                        print(f"  FAIL {fid} @{k}x: {st['worst']} set by @font-face is {st['max_dx']:.2f} px off HarfBuzz")
                    data_png = png_bytes(shot)
                else:
                    data_png = png_bytes(p1.evaluate("([id, f, d]) => FIG_png(id, {frame: f, dpr: d})", [fid, r["frame"], k]))
                (out / name).write_bytes(data_png)
                with Image.open(io.BytesIO(data_png)) as im:
                    entry["png"][f"{k}x"] = name
                    entry.setdefault("png_px", {})[f"{k}x"] = list(im.size)
            if r["live"]:
                fontface["figures"] += 1
            figures.append(entry)
            print(f"  {fid:28s} {r['w']:>8} x {r['h']:<8} {' '.join(entry['png'])}")
        demo = None
        if not a.no_app and (not a.only or "use/app-".startswith(a.only) or a.only.startswith("use/app-")):
            ents, demo = app_screens(out, br, a.limn, facts["colors"])
            for e in ents:
                with Image.open(out / e["file"]) as im:
                    e["png_px"] = {"2x": list(im.size)}
                print(f"  {e['id']:28s} {e['w']:>8} x {e['h']:<8} 2x")
            figures += ents
        br.close()
    if fontface["max_dx_px"] > 0.5:
        sys.exit(f"export_figures: a run set by @font-face is {fontface['max_dx_px']} px off HarfBuzz's width")
    if a.only:
        print(f"{len(figures)} figures -> {out} (partial: no manifest)")
        return
    dirty = bool(git("status", "--porcelain", "--", "tools", "limn-brand.js", "limn-pages.css"))
    manifest = {
        "build": git("rev-parse", "HEAD"), "dirty": dirty,
        "fonts": {"family": files["family"], "version": files["version"], "rev": files["rev"], "upm": files["upm"],
                  "files": [{"w": f["w"], "name": f["name"], "woff2": Path(f["woff2"]).name, "ttf": Path(f["ttf"]).name} for f in files["files"]]},
        "weights": weights, "coverage": cov, "features": feats,
        "colors": facts["colors"], "color_tokens": facts["color_tokens"], "colors_other": facts["colors_other"],
        "contrast": facts["contrast"],
        "logo": facts["logo"], "icon": facts["icon"], "motion": mo, "fontface": fontface, "demo": demo,
        "figures": figures,
    }
    (out / "manifest.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    print(f"{len(figures)} figures, manifest.json -> {out}" + (" (tools changed since the commit)" if dirty else ""))


if __name__ == "__main__":
    main()
