"""Check the figures make figures wrote (tools/export_figures.py) against the build data, and scan them for what the
public file must never show.

  uv run --no-project --with playwright --with fonttools --with brotli --with pillow python3 tools/check_figures.py OUT

Checks, exit 1 on any failure:
  manifest  OUT/manifest.json exists and has every section
  weights   every weight of limn-font-play.js: S, x-height, overshoot, cap, ascender, descender, pin radius, gap and
            top, quote pin, equal to the data; each TTF's OS/2 weight class, x-height and cap height agree; the
            weights ladder shows each S
  coverage  counted again from every TTF's cmap (one cmap for all weights, and each .woff2 the same as its .ttf)
  features  the GSUB/GPOS feature tags of the font files, each with its type/features-<tag> figure
  colors    the six public tokens (ink, ver, paper, bone, cream, and sky as On vermilion) = LIMN.COLOR, the swatches
            show them all; contrast recomputed here (WCAG 2.x relative luminance), pass = ratio >= need; every
            colour in an SVG is LIMN.COLOR's or a named scenery colour, and a logo mark's pin circles its pin colour
  logo      the construction numbers against limn-font.js and LIMN, and drawn in the construction and clear-space
            labels; the optical pin gap of each minimum size
  icon      the pixel-drawing table against LIMN.ICON_PX and LIMN.FAVICON_PX; the optical tiers against iconSpec
  motion    the durations and curves read again from limn-pages.css
  captions  every number in a caption is a number of the data (none spelled out); the ones that restate a rule
            (tiers, pixel sizes, weight count and range, em, canvas and body, white under the pin) recomputed here
  text      no text in a figure below 11 px at 1x
  labels    no guide (dimension, grid, keyline, axis) shows inside a label's glyph box, and no two labels overlap
  demo      each sample pin names one line, no badge covered a word, the build line names a commit, the accent is
            vermilion or ink, whichever keeps 4.5:1 under the label chip's text (vermilion first)
  figures   every required id listed once and no file under OUT outside the manifest; its SVG parses, width, height
            and viewBox = the manifest's; each PNG has the pixel size recorded (2x = twice w and h), its ink reaches
            the edges, and a PNG rasterised from its SVG is that SVG
  frames    each SVG drawn in Chromium with its viewBox opened on every side: no ink outside the frame (nothing
            cropped: overshoot, bezier handles, halos, shadows), and ink within 1.5 px of every edge (the frame is
            the ink bounds, not a loose box)
  public    every file under OUT (SVG text, manifest, PNG text chunks) holds none of FORBIDDEN and no token-like
            string (Limn, GitHub, OpenAI-style, Figma, bearer); PNGs carry no text chunks
Needs the build data (make play, make font, make fonts) and Playwright's Chromium.
"""
import base64
import json
import math
import os
import re
import struct
import sys
import unicodedata
import xml.etree.ElementTree as ET  # parses the SVGs export_figures.py wrote, never outside input
import zlib
from pathlib import Path

from fontTools.ttLib import TTFont
from PIL import Image
from playwright.sync_api import sync_playwright

SITE = Path(__file__).resolve().parent.parent
ORIGIN = "http://limn.check/"

# never in anything that may go public (the portfolio spec's public-safety rules); matched case-insensitively.
# Only the generic shapes live here. The deployment's own private names - internal hostnames, project code names -
# go in tools/private-strings.txt, which is not committed: a public checkout must not carry the very strings this
# list exists to keep out. One per line there; blank lines and lines starting with # are ignored. Reading no names
# at all - the file missing, empty, or only comments - is a failure of the public check, not a quiet pass with
# four patterns; LIMN_PRIVATE_STRINGS=none accepts that scan deliberately (a clone with nothing of its own to hide).
FORBIDDEN_GENERIC = ("/home/", "~/", "/tmp/", "@gmail.com")
PRIVATE_STRINGS = SITE / "tools" / "private-strings.txt"
PRIVATE_STRINGS_WAIVED = os.environ.get("LIMN_PRIVATE_STRINGS") == "none"


def private_strings(path=PRIVATE_STRINGS):
    if not path.exists():
        return ()
    return tuple(s.strip() for s in path.read_text().splitlines() if s.strip() and not s.lstrip().startswith("#"))


PRIVATE = private_strings()
FORBIDDEN = FORBIDDEN_GENERIC + PRIVATE
TOKEN_RES = (re.compile(rb"limn_[A-Za-z0-9_-]{16,}"), re.compile(rb"gh[pousr]_[A-Za-z0-9]{20,}"),
             re.compile(rb"sk-[A-Za-z0-9_-]{20,}"), re.compile(rb"Bearer\s+[A-Za-z0-9._-]{12,}"),
             re.compile(rb"figd_[A-Za-z0-9_-]{20,}"))
TOKEN_KEYS = ("ink", "ver", "paper", "bone", "cream", "sky")   # the public colour tokens (sky: "On vermilion")
# colours the figures may use besides LIMN.COLOR: the scenery of the tab, Dock and favicon grounds (Chrome's tab
# greys, macOS placeholder app colours and wallpapers), the busy ground and the shadow of the don'ts
SCENERY = {"#ffffff", "#000", "#000000", "#35363a", "#b9bcc2", "#dee1e6", "#1f1f1f", "#45474a", "#f1f3f4", "#1f2023",
           "#f1f1f1", "#28292c", "#e8e8ea", "#3a7bd5", "#8e8e93", "#34c759", "#ff9f0a", "#f0d9c9", "#d7d3e8", "#c4d8e7",
           "#1b2338", "#2b2540", "#10151f", "#8ec5fc", "#e0c3fc"}
NUMBER_WORDS = re.compile(r"\b(zero|one|two|three|four|five|six|seven|eight|nine|ten|eleven|twelve|thirteen|fourteen|"
                          r"fifteen|sixteen|seventeen|eighteen|nineteen|twenty)\b", re.I)
MIN_TEXT_PX = 11   # no text in a figure smaller than this at 1x
SECTIONS = ("build", "fonts", "weights", "coverage", "features", "colors", "contrast", "logo", "icon", "motion", "figures")
FIXED_IDS = (["logo/" + i for i in ("wordmark-light", "wordmark-dark", "wordmark-ver", "lockup", "rim", "construction",
                                    "clearspace", "minsize-12", "minsize-16", "minsize-24")]
             + ["icon/" + i for i in ("grid", "ramp", "px-16", "px-20", "px-24", "px-32", "favicon-light", "favicon-dark", "touch-180")]
             + ["color/swatches"]
             + ["type/" + i for i in ("specimen-hero", "weights-ladder", "latin-hangul", "waterfall", "sizes-12-16")]
             + ["motion/" + i for i in ("drop", "write", "ripple", "light")]
             + ["use/" + i for i in ("app-light", "app-dark", "tab", "dock")])
SVG_NS = "{http://www.w3.org/2000/svg}"
KEYWORD_CURVES = {"linear": [0, 0, 1, 1], "ease": [0.25, 0.1, 0.25, 1], "ease-in": [0.42, 0, 1, 1],
                  "ease-out": [0, 0, 0.58, 1], "ease-in-out": [0.42, 0, 0.58, 1]}
OVER_PX, LOOSE_PX, PNG_EDGE_PX = 0.6, 1.5, 3

fails = []


def fail(msg):
    fails.append(msg)


def load_js(path, marker):
    if not path.exists():
        sys.exit(f"check_figures: {path.name} missing - run make play font fonts first")
    t = path.read_text(encoding="utf-8")
    i = t.index(marker) + len(marker)
    return json.loads(t[i:t.rindex(";")])


def js(v):
    """a number as JavaScript prints it (20, 39.5)"""
    return str(int(v)) if float(v).is_integer() else repr(float(v))


def f1(v):
    """limn-brand.js f(): one decimal, as JavaScript prints it"""
    return js(round(v + 0.0, 1))


def near(a, b, tol=1e-6):
    return isinstance(a, (int, float)) and isinstance(b, (int, float)) and abs(a - b) <= tol


# ---------------------------------------------------------------- data

def check_weights(M, play, files):
    names = {str(f["w"]): f["name"] for f in files["files"]}
    if sorted(M["weights"], key=int) != sorted(play, key=int):
        fail(f"weights: manifest {sorted(M['weights'], key=int)} vs data {sorted(play, key=int)}")
    for w, W in play.items():
        m = M["weights"].get(w, {})
        p = W["pin"]
        want = {"name": names.get(w), "S": W["s"], "xh": W["xh"], "xo": W["xo"], "cap": W["cap"], "asc": W["asc"],
                "desc": W["desc"], "pin_r": p["r"], "pin_gap": p["gap"], "pin_top": W["xh"] + p["gap"] + 2 * p["r"],
                "quote_r": p["qr"], "quote_gap": p["qgap"]}
        for k, v in want.items():
            if not (m.get(k) == v or near(m.get(k), v, 0.006)):
                fail(f"weights {w} {k}: manifest {m.get(k)!r}, data {v!r}")
    for f in files["files"]:
        w = str(f["w"])
        os2 = TTFont(SITE / f["ttf"])["OS/2"]
        if os2.usWeightClass != f["w"]:
            fail(f"{f['ttf']}: usWeightClass {os2.usWeightClass}")
        if w in play and (os2.sxHeight != round(play[w]["xh"]) or os2.sCapHeight != round(play[w]["cap"])):
            fail(f"{f['ttf']}: OS/2 x-height {os2.sxHeight} / cap {os2.sCapHeight} vs data {play[w]['xh']} / {play[w]['cap']}")


def char_class(cp):
    ch = chr(cp)
    name, cat = unicodedata.name(ch, ""), unicodedata.category(ch)
    if 0xAC00 <= cp <= 0xD7A3:
        return "hangul"
    if 0x1100 <= cp <= 0x11FF or 0x3130 <= cp <= 0x318F or 0xA960 <= cp <= 0xA97F or 0xD7B0 <= cp <= 0xD7FF:
        return "jamo"
    for prefix, k in (("LATIN ", "latin"), ("GREEK ", "greek"), ("COPTIC ", "greek"), ("CYRILLIC ", "cyrillic")):
        if name.startswith(prefix):
            return k
    if cat == "Nd":
        return "digits"
    if cat[0] == "P":
        return "punctuation"
    if cat[0] == "Z" or cat == "Cf":
        return "spaces"
    return "symbols"


def check_coverage(M, files):
    cmaps, feats = {}, set()
    for f in files["files"]:
        tt = TTFont(SITE / f["ttf"])
        cmaps[f["w"]] = set(tt.getBestCmap())
        if set(TTFont(SITE / f["woff2"]).getBestCmap()) != cmaps[f["w"]]:
            fail(f"{f['woff2']}: cmap differs from {f['ttf']}")
        for t in ("GSUB", "GPOS"):
            if t in tt and tt[t].table.FeatureList:
                feats |= {fr.FeatureTag for fr in tt[t].table.FeatureList.FeatureRecord}
    cm = next(iter(cmaps.values()))
    if any(c != cm for c in cmaps.values()):
        fail("coverage: the weights' cmaps differ")
    want = {"total": len(cm)}
    for cp in cm:
        k = char_class(cp)
        want[k] = want.get(k, 0) + 1
    got = M["coverage"]
    for k in set(want) | set(got):
        if got.get(k, 0) != want.get(k, 0):
            fail(f"coverage {k}: manifest {got.get(k)}, cmap {want.get(k, 0)}")
    if sum(v for k, v in got.items() if k != "total") != got.get("total"):
        fail("coverage: the classes do not add up to the total")
    if M["features"] != sorted(feats):
        fail(f"features: manifest {M['features']}, font files {sorted(feats)}")
    return sorted(feats)


def lum(h):
    c = [int(h[i:i + 2], 16) / 255 for i in (1, 3, 5)]
    c = [v / 12.92 if v <= 0.04045 else ((v + 0.055) / 1.055) ** 2.4 for v in c]
    return 0.2126 * c[0] + 0.7152 * c[1] + 0.0722 * c[2]


def check_colors(M, B, figs):
    C = B["COLOR"]
    if sorted(M["colors"]) != sorted(TOKEN_KEYS):
        fail(f"colors: manifest tokens {sorted(M['colors'])}, want {sorted(TOKEN_KEYS)}")
    for k in TOKEN_KEYS:
        if M["colors"].get(k) != C.get(k):
            fail(f"colors {k}: manifest {M['colors'].get(k)}, LIMN.COLOR {C.get(k)}")
    toks = M.get("color_tokens", [])
    if [t["key"] for t in toks] != list(M["colors"]) or any(t["hex"] != C.get(t["key"]) for t in toks):
        fail(f"color_tokens {[(t['key'], t['hex']) for t in toks]} do not match colors")
    if not any(t["key"] == "sky" and t["name"] == "On vermilion" for t in toks):
        fail("color_tokens: sky is not the public token On vermilion")
    sw = figs.get("color/swatches", {}).get("meta", {})
    if sw.get("tokens") != list(M["colors"]) or sw.get("count") != len(M["colors"]):
        fail(f"color/swatches shows {sw.get('tokens')}, the tokens are {list(M['colors'])}")
    for k, v in M.get("colors_other", {}).items():
        if C.get(k) != v:
            fail(f"colors_other {k}: manifest {v}, LIMN.COLOR {C.get(k)}")
    for c in M["contrast"]:
        a, b = lum(C[c["fg"]]), lum(C[c["bg"]])
        r = (max(a, b) + 0.05) / (min(a, b) + 0.05)
        if abs(r - c["ratio"]) > 0.006:
            fail(f"contrast {c['fg']}/{c['bg']}: manifest {c['ratio']}, computed {r:.3f}")
        if c["pass"] != (r >= c["need"]) or c["need"] not in (3, 4.5):
            fail(f"contrast {c['fg']}/{c['bg']}: pass {c['pass']} for {r:.2f} against {c['need']}")


def check_logo(M, font, B, figs):
    L, p = M["logo"], font["pin"]
    want = {"s": font["s"], "xh": font["xh"], "xo": font["xo"], "asc": font["asc"], "desc": font["desc"], "cap": font["cap"],
            "pin_r": p["r"], "pin_cy": p["cy"], "gap": p["gap"], "clear_space": font["xh"] / 2, "gd": B["gd"],
            "logo_kern": B["LOGO_KERN"]}
    for k, v in want.items():
        if not (L.get(k) == v or near(L.get(k), v, 0.051)):
            fail(f"logo {k}: manifest {L.get(k)!r}, data {v!r}")
    if not near(L.get("pin_top"), font["xh"] + p["gap"] + 2 * p["r"], 0.051):
        fail(f"logo pin_top {L.get('pin_top')} != x-height + gap + 2r")
    if not near(B["gd"] * font["s"], p["gap"], 0.051):
        fail(f"logo: gd {B['gd']} x s {font['s']} is not the font's pin gap {p['gap']}")
    for h, g in L.get("min_gd", {}).items():
        # limn-brand.js gdFor: solved on the height with the raised pin, rounded up
        want = 1.25 * (font["asc"] - B["gd"] * font["s"]) / (font["s"] * (int(h) - 1.25))
        want = round(B["gd"], 2) if want <= B["gd"] else math.ceil(want * 100) / 100
        if not near(g, want, 0.0051):
            fail(f"logo min_gd {h}: {g}")
    cons = set(figs.get("logo/construction", {}).get("texts", []))
    gap = p["gap"]
    for t in (f"x-height {js(font['xh'])}", f"s {f1(font['s'])}", f"2r {f1(2 * p['r'])}", f"pin centre {f1(-p['cy'])}",
              f"gap {f1(gap)} = {f1(gap / font['s'])}s", f"{f1(font['asc'] - font['xh'])}", "baseline 0"):
        if t not in cons:
            fail(f"logo/construction does not show {t!r}")
    if not any(t.startswith(f"ascender {js(font['asc'])}") for t in cons):
        fail("logo/construction does not show the ascender")
    if f"{f1(font['xh'] / 2)} = x-height / 2" not in figs.get("logo/clearspace", {}).get("texts", []):
        fail("logo/clearspace does not show half the x-height")


def px_facts(P, favicon=False):
    _, bw, _ = P["body"]
    _, sw, st, sb = P["stem"][:4]
    _, qy, rows = P["pin"]
    d = {"body": bw, "stem": [sw, sb - st], "pin": [len(rows[0]), len(rows)], "gap": st - (qy + len(rows))}
    if not favicon:
        d["round_top"] = len(P["stem"]) > 4
    return d


def check_icon(M, B, figs):
    for n, P in B["ICON_PX"].items():
        want = px_facts(P)
        if M["icon"]["px"].get(n) != want:
            fail(f"icon px {n}: manifest {M['icon']['px'].get(n)}, ICON_PX {want}")
        meta = figs.get(f"icon/px-{n}", {}).get("meta")
        if meta is not None and meta != want:
            fail(f"icon/px-{n} meta {meta} vs ICON_PX {want}")
    for n, P in B["FAVICON_PX"].items():
        if M["icon"]["favicon"].get(n) != px_facts(P, True):
            fail(f"icon favicon {n}: manifest {M['icon']['favicon'].get(n)}, FAVICON_PX {px_facts(P, True)}")


def numbers_in(v, out, skip=("caption", "texts")):
    """every number of a manifest value: numeric values, and dict keys that are numbers"""
    if isinstance(v, bool):
        return out
    if isinstance(v, (int, float)):
        out.add(round(float(v), 6))
    elif isinstance(v, dict):
        for k, x in v.items():
            if re.fullmatch(r"-?\d+(\.\d+)?", str(k)):
                out.add(round(float(k), 6))
            if k not in skip:
                numbers_in(x, out, skip)
    elif isinstance(v, list):
        for x in v:
            numbers_in(x, out, skip)
    return out


def check_captions(M, figs, B, play, font):
    """a caption's numbers are the data's: each is a number of the manifest (its data sections and the figure's own
    entry), never a number word; and the ones that restate a rule are recomputed from the data here"""
    pool = numbers_in({k: v for k, v in M.items() if k != "figures"}, set())
    for e in figs.values():
        cap = e.get("caption", "")
        tag = e["id"][len("type/features-"):] if e["id"].startswith("type/features-") else None
        if NUMBER_WORDS.search(cap.replace(f" {tag}.", ".") if tag else cap):   # an OpenType tag (zero) is a name
            fail(f"{e['id']} caption spells a number: {cap!r}")
        own = numbers_in(e, set(pool))
        for n in re.findall(r"(?<![\w.])\d+(?:\.\d+)?", cap):
            if round(float(n), 6) not in own:
                fail(f"{e['id']} caption has {n}, which is not in the data: {cap!r}")

    def says(fid, *vals):
        cap = figs.get(fid, {}).get("caption", "")
        got = {round(float(n), 6) for n in re.findall(r"(?<![\w.])\d+(?:\.\d+)?", cap)}
        for v in vals:
            if round(float(v), 6) not in got:
                fail(f"{fid} caption does not say {js(v)}: {cap!r}")
    ws = sorted(int(w) for w in play)
    says("type/weights-ladder", len(ws), ws[0], ws[-1], font["upm"])
    says("logo/construction", font["upm"], font["s"])
    says("icon/grid", B["canvas"], B["body"])
    says("icon/ramp", *[int(n) for n in B["ICON_PX"]], *[v for t in B["tiers"] for v in (t["stem_s"], t["gd"])])
    ramp = figs.get("icon/ramp", {}).get("meta", {})
    if ramp.get("tiers") != B["ramp_tiers"] or ramp.get("pixel") != [int(n) for n in B["ICON_PX"]]:
        fail(f"icon/ramp tiers {ramp.get('tiers')} / pixel {ramp.get('pixel')} vs LIMN {B['ramp_tiers']} / {list(B['ICON_PX'])}")
    if M["icon"].get("tiers") != B["tiers"]:
        fail(f"icon tiers {M['icon'].get('tiers')} vs LIMN.iconSpec {B['tiers']}")
    for k in ("light", "dark"):
        says(f"icon/favicon-{k}", *[int(n) for n in B["FAVICON_PX"]])
    says("color/swatches", len(TOKEN_KEYS))
    for fid, e in figs.items():
        if fid.startswith("logo/minsize-"):
            h, gd = e["meta"]["h"], e["meta"]["gd"]
            top = max(font["asc"], font["xh"] + gd * font["s"] + 2 * font["pin"]["r"])   # the wordmark's height, pin top on top
            if not near(e["meta"]["white_px"], round(gd * font["s"] * h / top, 2), 0.011):
                fail(f"{fid}: white under the pin {e['meta']['white_px']} px, the data give {gd * font['s'] * h / top:.2f}")
            says(fid, h, gd, e["meta"]["white_px"])
    if M.get("demo"):
        for k in ("light", "dark"):
            says(f"use/app-{k}", len(M["demo"]["pins"]))


def check_text_size(figs):
    for e in figs.values():
        if e.get("min_text_px") is not None and e["min_text_px"] < MIN_TEXT_PX - 1e-9:
            fail(f"{e['id']}: text {e['min_text_px']} px at 1x, below {MIN_TEXT_PX} px")


def check_demo(M, B):
    d = M.get("demo") or {}
    pins = d.get("pins", [])
    if not pins or d.get("pin_count") != len(pins) or any(not isinstance(p.get("line"), int) for p in pins):
        fail(f"demo pins {pins}: each must name one line")
    if d.get("badges_clear") is not True:
        fail("demo: a pin badge covered a word")
    if not d.get("head") or d["head"] == "-":
        fail(f"demo: the build line names no commit ({d.get('head')!r})")
    if d.get("accent") not in (B["COLOR"]["ver"], B["COLOR"]["ink"]):
        fail(f"demo accent {d.get('accent')} is neither vermilion nor ink")
    elif d.get("chip_text"):
        if lum_ratio(d["accent"], d["chip_text"]) < 4.5:
            fail(f"demo accent {d['accent']} under chip text {d['chip_text']} is below 4.5:1")
        if d["accent"] != B["COLOR"]["ver"] and lum_ratio(B["COLOR"]["ver"], d["chip_text"]) >= 4.5:
            fail("demo accent: vermilion would have kept 4.5:1, so it should have been the accent")


def lum_ratio(p, q):
    a, b = lum(p), lum(q)
    return (max(a, b) + 0.05) / (min(a, b) + 0.05)


HEX = re.compile(r'(?:fill|stroke|stop-color|flood-color)="(#[0-9a-fA-F]{3,6})"')


def check_svg_colours(out, figs, B):
    """every colour in an SVG is LIMN.COLOR's or a named scenery colour; in the logo marks the pin circles are the
    pin colour of that mark (vermilion; sky on the vermilion ground)"""
    brand = {v.lower() for v in B["COLOR"].values()}
    for e in figs.values():
        if not e["file"].endswith(".svg"):
            continue
        text = (out / e["file"]).read_text(encoding="utf-8")
        odd = sorted({c.lower() for c in HEX.findall(text)} - brand - SCENERY)
        if odd:
            fail(f"{e['file']}: colours outside LIMN.COLOR and the scenery list: {odd}")
        fid = e["id"]
        if fid in ("logo/wordmark-light", "logo/wordmark-dark", "logo/wordmark-ver", "logo/rim", "logo/lockup") or fid.startswith("logo/minsize-"):
            pin = B["COLOR"]["sky"] if fid == "logo/wordmark-ver" else B["COLOR"]["ver"]
            circles = re.findall(r'<circle [^>]*fill="(#[0-9a-fA-F]{3,6})"', text)
            if not circles or any(c.lower() != pin for c in circles):
                fail(f"{e['file']}: pin circles {circles}, want {pin}")


def check_motion(M, figs):
    css = re.sub(r"/\*.*?\*/", "", (SITE / "limn-pages.css").read_text(encoding="utf-8"), flags=re.S)

    def anim(sel):
        m = re.search(re.escape(sel) + r"\{[^}]*animation:([\w-]+) ([\d.]+)s ([\w-]+(?:\([^)]*\))?)", css)
        curve = m.group(3)
        pts = [float(x) for x in curve[13:-1].split(",")] if curve.startswith("cubic-bezier") else KEYWORD_CURVES[curve]
        return m.group(1), float(m.group(2)), pts

    def frames(name):
        body = re.search(r"@keyframes " + name + r"\{(.*?)\}\}", css).group(1) + "}"
        out = []
        for sel, decl in re.findall(r"([\d.%,]+)\{([^}]*)\}", body):
            for o in sel.split(","):
                out.append((float(o.rstrip("%")), dict(d.split(":", 1) for d in decl.split(";") if ":" in d)))
        return sorted(out, key=lambda t: t[0])

    got = M["motion"]
    for key, sel in (("drop", ".w .pt"), ("write", ".w .gl")):
        _, dur, pts = anim(sel)
        if not near(got[key]["duration_s"], dur) or got[key]["curve"] != pts:
            fail(f"motion {key}: manifest {got[key]}, css {dur} s {pts}")
    name, cycle, pts = anim(".ic-ring")
    ks = frames(name)
    shows = min(o for o, p in ks if float(p.get("opacity", 0)) > 0)
    last = [p["transform"] for o, p in ks if "transform" in p][-1]
    grown = min(o for o, p in ks if p.get("transform") == last)
    if not near(got["ripple"]["duration_s"], round(cycle * (grown - shows) / 100, 3)) or got["ripple"]["curve"] != pts:
        fail(f"motion ripple: manifest {got['ripple']}, css {cycle} s x {shows}-{grown} %")
    name, cycle, pts = anim(".lm-light")
    ts = [(o, p["transform"]) for o, p in frames(name) if "transform" in p]
    sc = [re.search(r"scale\(([^)]*)\)", t).group(1) for _, t in ts]
    i = next(i for i in range(len(ts) - 1) if sc[i] != sc[i + 1])
    sweep, gather = cycle * (ts[1][0] - ts[0][0]) / 100, cycle * (ts[i + 1][0] - ts[i][0]) / 100
    if not (near(got["light"]["sweep_s"], round(sweep, 3)) and near(got["light"]["gather_s"], round(gather, 3)) and got["light"]["curve"] == pts):
        fail(f"motion light: manifest {got['light']}, css sweep {sweep} gather {gather}")
    for key, t in (("drop", f"{js(round(got['drop']['duration_s'], 2))} s"), ("ripple", f"ring {js(round(got['ripple']['duration_s'], 2))} s")):
        if t not in figs.get(f"motion/{key}", {}).get("texts", []):
            fail(f"motion/{key} does not show {t!r}")


# ---------------------------------------------------------------- files

def png_chunks(data):
    """(type, data) of every chunk"""
    if data[:8] != b"\x89PNG\r\n\x1a\n":
        raise ValueError("not a PNG")
    i, out = 8, []
    while i < len(data):
        n = struct.unpack(">I", data[i:i + 4])[0]
        out.append((data[i + 4:i + 8].decode("latin-1"), data[i + 8:i + 8 + n]))
        i += 12 + n
    return out


def scan(name, blob):
    low = blob.lower()
    for w in FORBIDDEN:
        if w.lower().encode() in low:
            fail(f"public: {name} contains {w!r}")
    for r in TOKEN_RES:
        m = r.search(blob)
        if m:
            fail(f"public: {name} contains a token-like string {m.group(0)[:12]!r}...")


def check_public(out):
    # the scan is only as wide as its list: say so loudly rather than pass on the four generic patterns alone
    if not PRIVATE and not PRIVATE_STRINGS_WAIVED:
        where = PRIVATE_STRINGS.relative_to(SITE.parent)
        how = "is missing" if not PRIVATE_STRINGS.exists() else "names nothing"
        fail(f"public: {where} {how}, so only {len(FORBIDDEN_GENERIC)} generic patterns were checked. Put this "
             "deployment's own hostnames and code names there (one per line, not committed), or set "
             "LIMN_PRIVATE_STRINGS=none to accept a generic-only scan.")
    for p in sorted(out.rglob("*")):
        if not p.is_file():
            continue
        rel = p.relative_to(out).as_posix()
        data = p.read_bytes()
        if p.suffix == ".png":
            try:
                chunks = png_chunks(data)
            except ValueError as e:
                fail(f"{rel}: {e}")
                continue
            for t, d in chunks:
                if t in ("tEXt", "zTXt", "iTXt", "eXIf", "iCCP"):
                    fail(f"public: {rel} carries a {t} chunk")
                if t in ("zTXt", "iTXt", "iCCP"):
                    try:
                        d = d + zlib.decompress(d[d.index(b"\0") + 2:])
                    except (ValueError, zlib.error):
                        pass
                if t not in ("IDAT",):
                    scan(f"{rel} {t}", d)
            scan(rel + " (name)", rel.encode())
        else:
            scan(rel, data)


def check_files(M, out, weights, feats):
    figs = {}
    for e in M["figures"]:
        if e["id"] in figs:
            fail(f"figures: {e['id']} listed twice")
        figs[e["id"]] = e
    want = FIXED_IDS + [f"type/glyph-grid-{w}" for w in sorted(weights, key=int)] + [f"type/features-{t}" for t in feats]
    for i in want:
        if i not in figs:
            fail(f"figures: {i} missing")
    if not any(i.startswith("logo/misuse-") for i in figs):
        fail("figures: no logo/misuse-* figure")
    listed = set()
    for e in figs.values():
        listed.add(e["file"])
        listed |= set(e.get("png", {}).values())
    for p in out.rglob("*"):
        rel = p.relative_to(out).as_posix()
        if p.is_file() and rel != "manifest.json" and rel not in listed:
            fail(f"figures: {rel} is not in the manifest (a stale file?)")
    for e in figs.values():
        f = out / e["file"]
        if not f.exists():
            fail(f"{e['file']}: missing")
            continue
        if f.suffix == ".svg":
            try:
                root = ET.fromstring(f.read_text(encoding="utf-8"))
            except ET.ParseError as x:
                fail(f"{e['file']}: not XML ({x})")
                continue
            if root.tag != SVG_NS + "svg":
                fail(f"{e['file']}: root is {root.tag}")
            if not (near(float(root.get("width")), e["w"], 0.006) and near(float(root.get("height")), e["h"], 0.006)):
                fail(f"{e['file']}: {root.get('width')} x {root.get('height')}, manifest {e['w']} x {e['h']}")
            vb = [float(v) for v in root.get("viewBox").split()]
            if e.get("frame") and any(not near(a, b, 0.006) for a, b in zip(vb, e["frame"])):
                fail(f"{e['file']}: viewBox {vb}, manifest frame {e['frame']}")
            if vb[2] <= 0 or vb[3] <= 0:
                fail(f"{e['file']}: empty viewBox")
        for k, name in e.get("png", {}).items():
            pf = out / name
            if not pf.exists():
                fail(f"{name}: missing")
                continue
            with Image.open(pf) as im:
                im.load()
                s = int(k[:-1])
                if list(im.size) != e.get("png_px", {}).get(k):
                    fail(f"{name}: {im.size}, manifest {e.get('png_px', {}).get(k)}")
                if abs(im.size[0] - e["w"] * s) > 1 or abs(im.size[1] - e["h"] * s) > 1:
                    fail(f"{name}: {im.size} is not {k} of {e['w']} x {e['h']}")
                bb = im.convert("RGBA").getchannel("A").getbbox()
                if not bb:
                    fail(f"{name}: empty")
                elif not e["id"].startswith("use/app-") and (bb[0] > PNG_EDGE_PX or bb[1] > PNG_EDGE_PX
                                                             or im.size[0] - bb[2] > PNG_EDGE_PX or im.size[1] - bb[3] > PNG_EDGE_PX):
                    fail(f"{name}: ink {bb} does not reach the edges of {im.size}")
    return figs


FRAME_JS = """
async ([svg]) => {
  const doc = new DOMParser().parseFromString(svg, "image/svg+xml"), root = doc.documentElement;
  const [x, y, w, h] = root.getAttribute("viewBox").trim().split(/[\\s,]+/).map(Number);
  const k = +root.getAttribute("width") / w;                       // output px per unit
  const pad = Math.max(w, h) * 0.1 + 12 / k, R = [x - pad, y - pad, w + 2 * pad, h + 2 * pad];
  const s = Math.min(2, Math.sqrt(1.6e7 / (R[2] * k * R[3] * k)));   // raster px per output px
  const cw = Math.ceil(R[2] * k * s), ch = Math.ceil(R[3] * k * s);
  root.setAttribute("viewBox", R.join(" ")); root.setAttribute("width", cw); root.setAttribute("height", ch);
  root.setAttribute("preserveAspectRatio", "none");
  const img = new Image();
  img.src = "data:image/svg+xml;charset=utf-8," + encodeURIComponent(new XMLSerializer().serializeToString(root));
  await img.decode();
  const c = document.createElement("canvas"); c.width = cw; c.height = ch;
  const g = c.getContext("2d", { willReadFrequently: true }); g.drawImage(img, 0, 0, cw, ch);
  const a = g.getImageData(0, 0, cw, ch).data;
  let x0 = cw, y0 = ch, x1 = -1, y1 = -1;
  for (let j = 0; j < ch; j++) { const row = j * cw * 4; let any = false;
    for (let i = 0; i < cw; i++) if (a[row + i * 4 + 3]) { any = true; if (i < x0) x0 = i; if (i > x1) x1 = i; }
    if (any) { if (j < y0) y0 = j; y1 = j; } }
  if (x1 < 0) return null;
  const ux = cw / R[2], uy = ch / R[3];                           // raster px per unit
  const ink = [R[0] + x0 / ux, R[1] + y0 / uy, R[0] + (x1 + 1) / ux, R[1] + (y1 + 1) / uy];
  // output px: how far the ink runs past each edge (left, top, right, bottom), and how far inside it stops
  const past = [(x - ink[0]) * k, (y - ink[1]) * k, (ink[2] - x - w) * k, (ink[3] - y - h) * k];
  return { past, touches: [x0 === 0, y0 === 0, x1 === cw - 1, y1 === ch - 1] };
}
"""


def check_frames(out, figs, pg):
    for e in figs.values():
        if not e["file"].endswith(".svg") or not (out / e["file"]).exists():
            continue
        r = pg.evaluate(FRAME_JS, [(out / e["file"]).read_text(encoding="utf-8")])
        if r is None:
            fail(f"{e['file']}: draws nothing")
            continue
        sides = ("left", "top", "right", "bottom")
        if any(r["touches"]):
            fail(f"{e['file']}: ink runs to the edge of the opened window ({[s for s, t in zip(sides, r['touches']) if t]})")
        for side, v in zip(sides, r["past"]):
            if v > OVER_PX:
                fail(f"{e['file']}: ink {v:.2f} px outside the frame on the {side} (cropped)")
            elif v < -LOOSE_PX:
                fail(f"{e['file']}: the frame is {-v:.2f} px loose on the {side} (not the ink bounds)")


RENDER_JS = """
const draw = async (root, cw, ch, drop) => {
  const r = root.cloneNode(true);
  if (drop) r.querySelectorAll(drop).forEach(e => e.remove());
  r.setAttribute("width", cw); r.setAttribute("height", ch); r.setAttribute("preserveAspectRatio", "none");
  const img = new Image();
  img.src = "data:image/svg+xml;charset=utf-8," + encodeURIComponent(new XMLSerializer().serializeToString(r));
  await img.decode();
  const c = document.createElement("canvas"); c.width = cw; c.height = ch;
  const g = c.getContext("2d", { willReadFrequently: true }); g.drawImage(img, 0, 0, cw, ch);
  return g.getImageData(0, 0, cw, ch).data;
};
"""

# labels (data-label; their halos share class "label") against guides (class "guide"): the figure drawn without its
# labels, and without labels and guides; any pixel that differs inside a label's glyph box is a guide showing there.
# Also every pair of label boxes that overlap.
LABELS_JS = "async ([svg]) => {" + RENDER_JS + """
  const root = new DOMParser().parseFromString(svg, "image/svg+xml").documentElement;
  if (!root.querySelector("[data-label]")) return { labels: 0, hits: [], overlaps: [] };
  const host = document.createElement("div"); host.style.cssText = "position:absolute;left:0;top:0";
  document.body.appendChild(host);
  const live = document.importNode(root, true); host.appendChild(live);
  const inv = live.getScreenCTM().inverse();
  const boxOf = el => { const b = el.getBBox(), m = inv.multiply(el.getScreenCTM());
    const q = [[b.x, b.y], [b.x + b.width, b.y], [b.x, b.y + b.height], [b.x + b.width, b.y + b.height]].map(([x, y]) => new DOMPoint(x, y).matrixTransform(m));
    return [Math.min(...q.map(p => p.x)), Math.min(...q.map(p => p.y)), Math.max(...q.map(p => p.x)), Math.max(...q.map(p => p.y))]; };
  const L = [...live.querySelectorAll("[data-label]")].map(el => ({ text: el.getAttribute("data-label"), box: boxOf(el) }));
  host.remove();
  const [x, y, w, h] = root.getAttribute("viewBox").trim().split(/[\\s,]+/).map(Number);
  const k = +root.getAttribute("width") / w, s = Math.min(2, Math.sqrt(1.6e7 / (w * k * h * k)));
  const cw = Math.ceil(w * k * s), ch = Math.ceil(h * k * s), ux = cw / w, uy = ch / h;
  const A = await draw(root, cw, ch, ".label"), B = await draw(root, cw, ch, ".label, .guide");
  const hits = [];
  for (const l of L) {
    const [b0, b1, b2, b3] = l.box; let n = 0;
    for (let j = Math.max(0, Math.floor((b1 - y) * uy)); j < Math.min(ch, Math.ceil((b3 - y) * uy)); j++)
      for (let i = Math.max(0, Math.floor((b0 - x) * ux)); i < Math.min(cw, Math.ceil((b2 - x) * ux)); i++) {
        const px = x + (i + .5) / ux, py = y + (j + .5) / uy;
        if (px < b0 || px > b2 || py < b1 || py > b3) continue;
        const p = (j * cw + i) * 4;
        if ([0, 1, 2, 3].some(c => Math.abs(A[p + c] - B[p + c]) > 8)) n++;
      }
    if (n) hits.push([l.text, n]);
  }
  const overlaps = [];
  for (let a = 0; a < L.length; a++) for (let b = a + 1; b < L.length; b++) {
    const p = L[a].box, q = L[b].box;
    if (Math.min(p[2], q[2]) > Math.max(p[0], q[0]) && Math.min(p[3], q[3]) > Math.max(p[1], q[1])) overlaps.push([L[a].text, L[b].text]);
  }
  return { labels: L.length, hits, overlaps };
}"""

# the PNG against its SVG drawn again as a PNG is made (the SVG at dpr times its size, on whole device pixels): the
# share of pixels that differ by more than 32 in a channel
PNG_JS = """async ([svg, png, dpr, cw, ch]) => {
  const pixels = async (src, w, h) => { const img = new Image(); img.src = src; await img.decode();
    const c = document.createElement("canvas"); c.width = cw; c.height = ch;
    const g = c.getContext("2d", { willReadFrequently: true }); g.drawImage(img, 0, 0, w, h);
    return g.getImageData(0, 0, cw, ch).data; };
  const root = new DOMParser().parseFromString(svg, "image/svg+xml").documentElement;
  const W = +root.getAttribute("width"), H = +root.getAttribute("height");
  const A = await pixels("data:image/svg+xml;charset=utf-8," + encodeURIComponent(svg), W * dpr, H * dpr);
  const B = await pixels(png, cw, ch);
  let n = 0;
  for (let p = 0; p < A.length; p += 4) if ([0, 1, 2, 3].some(c => Math.abs(A[p + c] - B[p + c]) > 32)) n++;
  return n / (cw * ch);
}"""


def check_labels(out, figs, pg):
    for e in figs.values():
        if not e["file"].endswith(".svg"):
            continue
        r = pg.evaluate(LABELS_JS, [(out / e["file"]).read_text(encoding="utf-8")])
        for text, n in r["hits"]:
            fail(f"{e['file']}: a guide runs through the label {text!r} ({n} px)")
        for a, b in r["overlaps"]:
            fail(f"{e['file']}: the labels {a!r} and {b!r} overlap")


def check_png_match(out, figs, pg):
    """a PNG rasterised from its SVG (not live text, not a device-pixel drawing) must be that SVG"""
    for e in figs.values():
        if not e["file"].endswith(".svg") or e.get("live") or e.get("dpr_drawn"):
            continue
        svg = (out / e["file"]).read_text(encoding="utf-8")
        for k, name in e.get("png", {}).items():
            data = (out / name).read_bytes()
            with Image.open(out / name) as im:
                cw, ch = im.size
            share = pg.evaluate(PNG_JS, [svg, "data:image/png;base64," + base64.b64encode(data).decode(), int(k[:-1]), cw, ch])
            if share > 0.001:
                fail(f"{name}: {share:.2%} of its pixels differ from {e['file']}")


def brand_values(pg, ramp_max):
    """LIMN's values, and a few measured here: the icon's canvas and body, and its optical tiers scanned from
    iconSpec px by px (to 1024, and to the ramp's largest size)"""
    return pg.evaluate("""(rampMax) => {
      const L = LIMN, tiers = max => { const out = [];
        for (let px = 1; px <= max; px++) { const sp = L.iconSpec(px), stem = +(sp.w / L.s).toFixed(2), t = out[out.length - 1];
          if (t && t.stem_s === stem && t.gd === sp.gd) t.to = px; else out.push({from: px, to: px, stem_s: stem, gd: sp.gd}); }
        return out; };
      const NS = 'http://www.w3.org/2000/svg', s = document.createElementNS(NS, 'svg');
      document.body.appendChild(s); s.innerHTML = L.icon(1024, {vector: true, flat: true});
      const ic = s.firstElementChild, body = ic.querySelector('path').getBBox();
      const out = {COLOR: L.COLOR, gd: L.P.gd, LOGO_KERN: L.LOGO_KERN, ICON_PX: L.ICON_PX, FAVICON_PX: L.FAVICON_PX,
        tiers: tiers(1024), ramp_tiers: tiers(rampMax), canvas: ic.viewBox.baseVal.width, body: +body.height.toFixed(2)};
      s.remove(); return out; }""", ramp_max)


def main():
    if len(sys.argv) != 2:
        sys.exit("usage: check_figures.py OUT")
    out = Path(sys.argv[1])
    man = out / "manifest.json"
    if not man.exists():
        print(f"FAIL manifest missing: {man}")
        sys.exit(1)
    M = json.loads(man.read_text(encoding="utf-8"))
    missing = [s for s in SECTIONS if s not in M]
    if missing:
        print(f"FAIL manifest lacks {missing}")
        sys.exit(1)
    if not re.fullmatch(r"[0-9a-f]{40}", M["build"]):
        fail(f"build {M['build']!r} is not a commit")
    play = load_js(SITE / "limn-font-play.js", "window.LIMN_PLAY=")
    font = load_js(SITE / "limn-font.js", "window.LIMN_FONT=")
    files = load_js(SITE / "fonts" / "fonts.js", "window.LIMN_FONT_FILES=")
    if (M["fonts"].get("version"), M["fonts"].get("rev")) != (files["version"], files["rev"]):
        fail(f"fonts: manifest {M['fonts'].get('version')} {M['fonts'].get('rev')}, fonts.js {files['version']} {files['rev']}")
    check_weights(M, play, files)
    feats = check_coverage(M, files)
    figs = check_files(M, out, play, feats)
    ladder = set(figs.get("type/weights-ladder", {}).get("texts", []))
    for w, W in play.items():
        if f"S {js(W['s'])}" not in ladder:
            fail(f"type/weights-ladder does not show S {js(W['s'])} for {w}")
    with sync_playwright() as p:
        br = p.chromium.launch(channel="chromium")
        pg = br.new_page()
        html = '<!doctype html><meta charset="utf-8"><body><script src="limn-font.js"></script><script src="limn-brand.js"></script></body>'

        def route(r):
            path = r.request.url[len(ORIGIN):].split("?")[0]
            if path in ("", "index.html"):
                return r.fulfill(status=200, content_type="text/html", body=html)
            f = SITE / path
            return r.fulfill(status=200, content_type="text/javascript", body=f.read_bytes()) if f.is_file() else r.fulfill(status=404, body="")
        pg.route(ORIGIN + "**", route)
        pg.goto(ORIGIN)
        B = brand_values(pg, max(figs.get("icon/ramp", {}).get("meta", {}).get("sizes", [1])))
        check_colors(M, B, figs)
        check_logo(M, font, B, figs)
        check_icon(M, B, figs)
        check_motion(M, figs)
        check_captions(M, figs, B, play, font)
        check_text_size(figs)
        check_demo(M, B)
        check_svg_colours(out, figs, B)
        check_frames(out, figs, pg)
        check_labels(out, figs, pg)
        check_png_match(out, figs, pg)
        br.close()
    check_public(out)
    for m in fails:
        print("FAIL", m)
    n_png = sum(len(e.get("png", {})) for e in figs.values())
    print(f"{len(figs)} figures ({n_png} PNGs) in {out}: " + (f"{len(fails)} failures" if fails else "PASS"))
    sys.exit(1 if fails else 0)


if __name__ == "__main__":
    main()
