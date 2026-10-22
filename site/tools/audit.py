"""Glyph audit of every weight and text cut (make check). Exits 1 on any failure: every line it prints is a fault
to fix, not a known exception.

  uv run --no-project --with skia-pathops --with fonttools --with shapely python3 tools/audit.py [--only GATE,...] [--json PATH]
      [--data name=path,...]     (--json writes the failures and the per-glyph geometry there; nothing is written otherwise)

Data: limn-font-play.js and limn-font-play-opt<px>.js (the Latin, Greek and symbol glyphs, pins drawn by the engine's
pinsOf) and limn-hangul-<w>.js (Hangul, the file checks below). Every glyph is read as the engine draws it: the
outline (nonzero) with its pins as ink circles, y up.

Gates (S = the weight's stem):

  data        a glyph outside the font files' line box (970 / -330), a glyph missing from one weight that others have, a proof character missing, an empty drawing, a zero box, an advance <= 0; ink more than 0.6 S left of
              the origin or past the advance inside the x-height band (the body of every letter: marks above it and
              descender hooks below it overhang by design, and the collision gate checks them); the pin count of a
              glyph against 700; a glyph whose height, pins included, steps more than x1.25 / x0.8 between
              neighbouring weights, unless the pin steps as much (• is 1.7 pins across) or two stems do (⁼)
  topology    the number of ink pieces or of counters of a glyph changes between neighbouring weights (a counter that
              closes, a new pinhole, a piece that comes loose). TOPO_ALLOW lists the glyphs whose change is the design
  counter     a counter (white enclosed by ink) whose largest inscribed circle is narrower than 0.3 S
  mono        the ink of a glyph (outline + pins) falls from one weight to the next heavier one (by more than 0.2 %)
  spike       ink narrower than 1.5 units reaching more than 6 units out (a zero-width spike or a sliver), white
              narrower than 1.5 units reaching more than 6 units in (a crack), or a piece of ink smaller than
              (0.3 S)^2 that is not a pin (a speck); dust under 1 unit² is left to the font files, which drop it
  kerncover   a glyph the build did not measure for kerning (the data's "kcover", written by build_font.py: every
              glyph must be kerned by the parent, by the clearance passes or through its kerning class)
  accent      the accents' stroke (the macron's thickness) outside 0.83-0.92 S
  collision   two neighbours in tools/audit_pairs.txt (real strings, and the proof sentences) set with the engine's
              kerning come closer than 0.1 S (ink to ink, pins included); no kerning across a Latin|Greek boundary,
              as browsers split script runs
  hangul      the Hangul data: KS X 1001 coverage, empty glyphs, boxes, advances

Scope (in_scope below): Korean and English, their punctuation, numeric super/subscripts and signs, Currency Symbols
(U+20A0–20CF), Letterlike Symbols (U+2100–214F), Number Forms (U+2150–218F), Arrows (U+2190–21FF), Mathematical
Operators (U+2200–22FF), Miscellaneous Technical (U+2300–23FF), and the supported supplemental symbols
⟨⟩⟵⟶⟷✓✔✗✘. Greek, extended Latin and alphabetic modifier/subscript letters (including ₑ) remain informational.
A collision fails only when both glyphs of the pair are in scope. What it finds on the other glyphs
is printed as one "info" line per gate (the count and a few examples) and written to --json under "info", not "fails".
"""
import glob
import json
import math
import os
import pathlib
import re
import sys
import unicodedata
from concurrent.futures import ProcessPoolExecutor

import pathops
from fontTools.pens.transformPen import TransformPen
from fontTools.svgLib.path import parse_path
from shapely import affinity, maximum_inscribed_circle
from shapely.geometry import MultiPolygon, Polygon
from shapely.ops import unary_union

D = pathlib.Path(__file__).resolve().parent.parent   # site/
TOOLS = D / "tools"

# glyphs whose ink pieces or counters change between neighbouring weights by design (the counter gate still holds every
# counter they keep to 0.3 S, so a step is a white that closes cleanly, never a speck)
TOPO_ALLOW = {
    "₩": "the bar at 0.56 CAP (the Hangul parent's ₩) passes over W's middle crotch while the crotch rises above it (100-300) "
         "and under it from 400, where the crotch sits lower",
    "￦": "₩'s drawing",
    "₦": "N's crotches fill in as it gets heavier: its two corner whites are their own counters while they are 0.4 S wide, and "
         "from where they would be specks each runs on into the white between the bars (sym_numeric.py)",
    "₱": "two bars while the bowl has room for three whites of 0.4 S, one bar from where it has not (sym_numeric.py)",
}
COUNTER_MIN = 0.3        # S
MONO_TOL = 0.002
SPIKE_R, SPIKE_LEN = 0.75, 6.0
SPECK = 0.3              # S: a piece of ink smaller than (SPECK S)^2
ACCENT = (0.83, 0.92)    # S
COLLIDE = 0.1            # S
LINE = (970, -330)       # the font files' line box (build_ttf.py LINE_ASC, LINE_DESC): every glyph inside it


# Korean and English are proofed (README Status); the rest is included, not yet proofed — dartworklabs/limn-sans#20
def in_scope(ch: str) -> bool:
    """Classify one Unicode character under the Korean/English and research-symbol quality policy.

    The caller supplies exactly one character. Alphabetic modifier/subscript letters stay deferred,
    even when adjacent numeric signs are required; this preserves the documented ₑ exception.
    """
    o = ord(ch)
    if 0x20 <= o <= 0x7E: return True                                   # Basic Latin (English)
    if 0xA0 <= o <= 0xBF or o in (0xD7, 0xF7): return True             # Latin-1 punctuation and signs, × ÷
    if 0x2010 <= o <= 0x205E: return True                               # general punctuation
    if ch in "⁰¹²³⁴⁵⁶⁷⁸⁹⁺⁻⁼⁽⁾₀₁₂₃₄₅₆₇₈₉₊₋₌₍₎": return True     # numeric super/subscripts and signs, no letters
    if 0x20A0 <= o <= 0x20CF: return True                               # Currency Symbols
    if 0x2100 <= o <= 0x23FF: return True                               # Letterlike, Number Forms, Arrows, Math, Technical
    if ch in "⟨⟩⟵⟶⟷✓✔✗✘": return True                               # supplemental glyphs explicitly built by sym_math
    if 0x2460 <= o <= 0x24FF or 0x25A0 <= o <= 0x25FF or 0x2600 <= o <= 0x26FF: return True  # ①… shapes ★ ♥ ☎
    if 0x3000 <= o <= 0x303F or 0x3130 <= o <= 0x318F or 0x3380 <= o <= 0x33FF: return True  # CJK symbols, jamo, ㎏
    if 0xAC00 <= o <= 0xD7A3 or 0xFF00 <= o <= 0xFFEF: return True     # Hangul syllables, full/halfwidth forms
    return False


def load(f):
    t = open(f, encoding="utf-8").read()
    i = t.rindex("]=") + 2 if "LIMN_PLAY_OPT[" in t else t.index("=") + 1
    return json.loads(t[i:t.rindex(";")])


# ---------------------------------------------------------------- engine geometry (limn-brand.js LIMN_playset)
def pins_of(W, ch, g):
    """pinsOf with the default rule (fit): [(x, y up, r)]."""
    if ch == "림":
        if "pinx" not in g: return []
        return [(g["pinx"], -g["piny"], g["pinr"])] if g.get("pinr") else []
    d = W.get("dots", {}).get(ch)
    if not d: return []
    r, gap, os_ = W["pin"]["r"], W["pin"]["gap"], W["xo"] - W["xh"]
    out = []
    for k, x, y, r0 in d["pins"]:
        nx = x + (r - r0) if d["only"] else x
        cy = W["xh"] + gap + r if k == "i" else r - os_ if k == "base" else W["xo"] - r if k == "top" else y
        out.append((nx, cy, r))
    return out


def adv_of(W, ch, g):
    d = W.get("dots", {}).get(ch)
    return d["adv0"] + 2 * (W["pin"]["r"] - d["pins"][0][3]) if d and d["only"] else g["adv"]


def kern_of(K, KC, a, b):
    v = K.get(a + b)
    if v is not None: return v
    l = (KC.get(a) or [None, None])[0] or a
    r = (KC.get(b) or [None, None])[1] or b
    return K.get(l + r, 0) if l + r != a + b else 0


def script_of(ch):
    """Latin | Greek | Hangul | None (common: figures, punctuation, symbols take the run they are in)."""
    if "가" <= ch <= "힣" or "ㄱ" <= ch <= "ㆎ" or "ᄀ" <= ch <= "ᇿ": return "Hang"
    if not unicodedata.category(ch).startswith("L"): return None
    n = unicodedata.name(ch, "")
    if n.startswith("GREEK"): return "Grek"
    if n.startswith("LATIN") or n.startswith("MODIFIER LETTER") or ch.isascii(): return "Latn"
    return None                                            # µ ℕ ℏ …: common


def _circle(pen, cx, cy, r):
    k = 0.5522847 * r
    pen.moveTo((cx + r, cy))
    pen.curveTo((cx + r, cy + k), (cx + k, cy + r), (cx, cy + r))
    pen.curveTo((cx - k, cy + r), (cx - r, cy + k), (cx - r, cy))
    pen.curveTo((cx - r, cy - k), (cx - k, cy - r), (cx, cy - r))
    pen.curveTo((cx + k, cy - r), (cx + r, cy - k), (cx + r, cy))
    pen.closePath()


def ink_path(d, pins):
    p = pathops.Path()
    if d:
        parse_path(d, TransformPen(p.getPen(), (1, 0, 0, -1, 0, 0)))
    if pins:
        c = pathops.Path(); cp = c.getPen()
        for x, y, r in pins: _circle(cp, x, y, r)
        return pathops.op(p, c, pathops.PathOp.UNION, fix_winding=True) if d else pathops.simplify(c, fix_winding=True)
    return pathops.simplify(p, fix_winding=True)


def flatten(c, steps=12):
    pts, cur = [], None
    for verb, a in c.segments:
        if verb == "moveTo":
            cur = a[0]; pts.append(cur)
        elif verb == "lineTo":
            cur = a[0]; pts.append(cur)
        elif verb == "qCurveTo":
            if a[-1] is None:
                ctrl = list(a[:-1]); mid = ((ctrl[-1][0] + ctrl[0][0]) / 2, (ctrl[-1][1] + ctrl[0][1]) / 2)
                cur = mid; pts.append(mid); a = tuple(ctrl) + (mid,)
            ctrl = list(a[:-1]); end = a[-1]; p0 = cur
            for i, q in enumerate(ctrl):
                e = end if i == len(ctrl) - 1 else ((q[0] + ctrl[i + 1][0]) / 2, (q[1] + ctrl[i + 1][1]) / 2)
                for k in range(1, steps + 1):
                    t = k / steps
                    pts.append(((1 - t) ** 2 * p0[0] + 2 * (1 - t) * t * q[0] + t * t * e[0], (1 - t) ** 2 * p0[1] + 2 * (1 - t) * t * q[1] + t * t * e[1]))
                p0 = e
            cur = end
        elif verb == "curveTo":
            c1, c2, e = a; p0 = cur
            for k in range(1, steps + 1):
                t = k / steps; u = 1 - t
                pts.append((u ** 3 * p0[0] + 3 * u * u * t * c1[0] + 3 * u * t * t * c2[0] + t ** 3 * e[0],
                            u ** 3 * p0[1] + 3 * u * u * t * c1[1] + 3 * u * t * t * c2[1] + t ** 3 * e[1]))
            cur = e
    return pts


def geometry(p):
    """(shapely MultiPolygon, [outer polygons], [hole polygons with the ink inside them removed]) of a simplified path."""
    cs = [c for c in p.contours]
    if not cs: return None, [], []
    big = max(cs, key=lambda c: abs(c.area))
    outer, holes = [], []
    for c in cs:
        pts = flatten(c)
        if len(pts) < 3: continue
        poly = Polygon(pts).buffer(0)
        if poly.is_empty: continue
        (outer if c.clockwise == big.clockwise else holes).append(poly)
    ink = Polygon()                    # the simplified contours do not overlap: even-odd = the XOR of all of them
    for q in outer + holes:
        ink = ink.symmetric_difference(q)
    whites = [h.difference(ink) for h in holes]
    return ink, outer, whites


def reversals(p):
    """Zero-width spikes: the outline turns straight back (more than 175 degrees) on two arms longer than 2 units
    (shapely's cleaning would drop them, so they are read off the contours themselves)."""
    out = []
    for c in p.contours:
        pts = flatten(c, 8)
        pts = [q for i, q in enumerate(pts) if i == 0 or math.dist(q, pts[i - 1]) > 1e-6]
        m = len(pts)
        for i in range(m):
            a, b, e = pts[i - 1], pts[i], pts[(i + 1) % m]
            u, v = (b[0] - a[0], b[1] - a[1]), (e[0] - b[0], e[1] - b[1])
            lu, lv = math.hypot(*u), math.hypot(*v)
            if min(lu, lv) > 2 and (u[0] * v[0] + u[1] * v[1]) / (lu * lv) < -0.9962:
                out.append((round(min(lu, lv), 1), [round(b[0]), round(b[1])]))
    return out


def measure(args):
    """Per glyph of one weight of one data set: topology, ink, counters, spikes, specks."""
    name, w, W, chars = args
    S = W["s"]; out = {}
    for ch in chars:
        g = W["glyphs"][ch]
        pins = pins_of(W, ch, g)
        if not g.get("d") and not pins: continue
        try:
            p = ink_path(g.get("d"), pins)
        except pathops.PathOpsError as e:
            out[ch] = {"err": repr(e)}; continue
        ink, outer, whites = geometry(p)
        if ink is None: continue
        rev = reversals(p)
        # dust under 1 unit² is not counted: the font files drop it (build_ttf._clean_path)
        pieces = [q for q in getattr(ink, "geoms", [ink]) if q.geom_type == "Polygon" and q.area >= 1.0]
        n_out = len(pieces); n_hole = sum(1 for q in pieces for r in q.interiors if Polygon(r).area >= 1.0)
        mic = []
        for wh in whites:
            if wh.is_empty or wh.area < 1.0: continue
            mic.append(2 * maximum_inscribed_circle(wh, 0.05).length)
        # spikes (ink narrower than 2 SPIKE_R reaching out) and cracks (white narrower than 2 SPIKE_R reaching in)
        spikes = [("spike", L, b) for L, b in rev]
        opened = ink.buffer(-SPIKE_R, join_style="mitre").buffer(SPIKE_R, join_style="round")
        closed = ink.buffer(SPIKE_R, join_style="round").buffer(-SPIKE_R, join_style="mitre")
        for kind, geo in (("spike", ink.difference(opened)), ("crack", closed.difference(ink))):
            for q in (getattr(geo, "geoms", [geo]) if not geo.is_empty else []):
                b = q.bounds; L = math.hypot(b[2] - b[0], b[3] - b[1])
                if q.area < 0.5 or q.area / max(L, 1e-9) < 0.05: continue      # the buffers' own rounding along an edge
                if L > SPIKE_LEN: spikes.append((kind, round(L, 1), [round(v) for v in b]))
        pin_c = [(x, y) for x, y, _ in pins]
        specks = [round(q.area) for q in pieces if q.area < (SPECK * S) ** 2
                  and not any(q.contains(Polygon([(x - .5, y - .5), (x + .5, y - .5), (x + .5, y + .5), (x - .5, y + .5)])) for x, y in pin_c)]
        out[ch] = {"topo": (n_out, n_hole), "ink": ink.area, "mic": mic, "spikes": spikes, "specks": specks}
    return name, w, out


# ---------------------------------------------------------------- collisions on real strings
def proof_corpus(scope="full"):
    """Read the real proof sentences; a release audit excludes only Hangul, without fake fixtures."""
    html = (D / "proof.html").read_text(encoding="utf-8")
    lines = re.findall(r'"([^"]*)"', html.split("const G=[")[1].split("];")[0])
    if scope == "latin-symbols":
        from build_ttf import is_hangul
        return ["".join(c if not is_hangul(ord(c)) else " " for c in line) for line in lines]
    if scope != "full":
        raise ValueError("audit scope must be full or latin-symbols")
    return lines


def pair_corpus(scope="full"):
    """Read real neighboring pairs, excluding Hangul runs only in the explicit release scope."""
    lines = [l.rstrip("\n") for l in open(TOOLS / "audit_pairs.txt", encoding="utf-8") if l.strip() and not l.startswith("#")]
    lines += proof_corpus(scope)
    if scope == "latin-symbols":
        from build_ttf import is_hangul
        lines = ["".join(c if not is_hangul(ord(c)) else " " for c in line) for line in lines]
    pairs = set()
    for l in lines:
        for word in re.split(r"[      　]+", l):
            cs = [c for c in word if c not in "­​"]
            for a, b in zip(cs, cs[1:]):
                pairs.add(a + b)
    return sorted(pairs)


def collide(args):
    name, w, W, pairs = args
    S = W["s"]; K, KC = W["kern"], W["kcls"]; geo = {}; hits = []

    def g_of(ch):
        if ch not in geo:
            g = W["glyphs"].get(ch)
            geo[ch] = None
            if g and (g.get("d") or pins_of(W, ch, g)):
                ink = geometry(ink_path(g.get("d"), pins_of(W, ch, g)))[0]
                geo[ch] = ink
        return geo[ch]
    for pr in pairs:
        a, b = pr
        A, B = g_of(a), g_of(b)
        if A is None or B is None: continue
        sa, sb = script_of(a), script_of(b)
        k = 0 if (sa and sb and sa != sb) else kern_of(K, KC, a, b)
        dx = adv_of(W, a, W["glyphs"][a]) + k
        d = A.distance(affinity.translate(B, dx, 0))
        if d < COLLIDE * S:
            hits.append((pr, round(d / S, 3)))
    return name, w, hits


def main():
    """Audit real engine records under full development or explicit non-Hangul release scope."""
    only = None; jpath = None
    args = sys.argv[1:]
    if "--only" in args: only = set(args[args.index("--only") + 1].split(","))
    if "--json" in args: jpath = args[args.index("--json") + 1]
    scope = args[args.index("--scope") + 1] if "--scope" in args else "full"
    if scope not in ("full", "latin-symbols"):
        raise ValueError("--scope must be full or latin-symbols")
    on = lambda g: (only is None or g in only) and (scope == "full" or g != "hangul")
    if "--data" in args:                  # --data name=path[,name=path...]: other data files (a scratch build)
        sets = {kv.split("=")[0]: load(kv.split("=", 1)[1]) for kv in args[args.index("--data") + 1].split(",")}
    else:
        sets = {"play": load(D / "limn-font-play.js")}
        for f in sorted(glob.glob(str(D / "limn-font-play-opt*.js"))):
            sets["opt" + re.search(r"opt(\d+)", f).group(1)] = load(f)
    corpus = "".join(proof_corpus(scope))
    fails, info, geo_out = {}, {}, {}

    def fail(gate, item, chars=None):
        """A finding about the glyph(s) `chars` (None: about the data as a whole): a failure when they are all in scope,
        an info line otherwise."""
        (fails if chars is None or all(in_scope(c) for c in chars) else info).setdefault(gate, []).append(item)

    def fail_list(gate, head, chars, tail=""):
        """A finding that lists glyphs ("missing ...", "lacks ..."): the in-scope ones fail, the rest is info."""
        a = "".join(c for c in chars if in_scope(c)); b = "".join(c for c in chars if not in_scope(c))
        if a: fails.setdefault(gate, []).append(f"{head}{a}{tail}")
        if b: info.setdefault(gate, []).append(f"{head}{b}{tail}")
    HG = {}
    if scope == "latin-symbols":
        from build_ttf import SPACE_PROVENANCE_IN, load_js, release_data, space_provenance
        if "--symbols" not in args:
            raise ValueError("release audit requires --symbols directory with explicit U+3000 authority")
        directory = pathlib.Path(args[args.index("--symbols") + 1])
        for w in range(100, 1000, 100):
            HG[str(w)] = load_js(directory / f"limn-hangul-{w}.js", f"window.LIMN_HANGUL[{w}]=")
            if "spaces" not in HG[str(w)]:
                if SPACE_PROVENANCE_IN is None:
                    raise ValueError("release audit requires LIMN_TTF_SPACE_PROVENANCE_IN")
                authority = space_provenance(SPACE_PROVENANCE_IN)
                HG[str(w)] = {**HG[str(w)], "spaces": {"\u3000": authority[str(w)]["advance"]}}
        for name, Wset in sets.items():
            if set(Wset) != {str(w) for w in range(100, 1000, 100)}:
                raise ValueError(f"{name}: release audit requires all nine weights")
            for w in Wset:
                Wset[w], HG[w] = release_data(Wset[w], HG[w])
    else:
        for f in sorted(glob.glob(str(D / "limn-hangul-*.js"))):
            t = open(f, encoding="utf-8").read(); HG[re.search(r"hangul-(\d+)", f).group(1)] = json.loads(t[t.index("]=") + 2:t.rindex(";")])

    # ---- data
    if on("data"):
        for name, Wset in sets.items():
            ws = sorted(Wset, key=int)
            for w in ws:
                F = Wset[w]; g = F["glyphs"]; s = F["s"]; hg = HG.get(w, {}).get("glyphs", {})
                miss = sorted({c for c in corpus if c.strip() and c not in g and c not in hg and c not in F.get("spaces", {})})
                if miss: fail_list("data", f"{name}:{w} missing ", miss)
                for ch, v in g.items():
                    if ch == " ": continue
                    d = v.get("d", ""); pins = pins_of(F, ch, v)
                    if not d and not pins: fail("data", f"{name}:{w}:{ch} empty", ch); continue
                    if v["adv"] <= 0 and not (v["adv"] == 0 and unicodedata.category(ch) == "Mn"):   # combining marks: zero width
                        fail("data", f"{name}:{w}:{ch} adv {v['adv']}", ch)
                    if not d: continue
                    b = v.get("box")
                    if not b or b[2] - b[0] <= 0 or b[3] - b[1] <= 0: fail("data", f"{name}:{w}:{ch} zero box", ch); continue
                    ys = [-b[1], -b[3]] + [q for x, y, r in pins for q in (y + r, y - r)]
                    if name == "play" and (max(ys) > LINE[0] or min(ys) < LINE[1]):          # the files are built from play
                        fail("data", f"{name}:{w}:{ch} ink {min(ys):.0f}..{max(ys):.0f} outside the line box {LINE[1]}..{LINE[0]}", ch)
                    # the x-height band, from the drawing
                    p = ink_path(d, [])
                    band = pathops.Path(); bp = band.getPen()
                    bp.moveTo((-1e4, 0)); bp.lineTo((1e4, 0)); bp.lineTo((1e4, F["xh"])); bp.lineTo((-1e4, F["xh"])); bp.closePath()
                    body = pathops.op(p, band, pathops.PathOp.INTERSECTION)
                    if list(body.contours) and unicodedata.category(ch) != "Mn":
                        x0, _, x1, _ = body.bounds; adv = adv_of(F, ch, v)
                        if x0 < -0.6 * s: fail("data", f"{name}:{w}:{ch} ink {x0:.0f} left of the origin", ch)
                        if x1 > adv + 0.6 * s: fail("data", f"{name}:{w}:{ch} ink {x1 - adv:.0f} past the advance", ch)
                for ch, sp in F.get("dots", {}).items():
                    r7 = Wset["700"].get("dots", {}).get(ch)
                    if r7 and len(sp["pins"]) != len(r7["pins"]): fail("data", f"{name}:{w}:{ch} pin count {len(sp['pins'])} vs 700 {len(r7['pins'])}", ch)
            every = set().union(*(set(Wset[w]["glyphs"]) for w in ws))
            for w in ws:                   # one glyph set at every weight (₤ once dropped out of one weight unnoticed)
                gone = every - set(Wset[w]["glyphs"])
                if gone: fail_list("data", f"{name}:{w} lacks ", sorted(gone), " (in other weights)")
            for a, b in zip(ws, ws[1:]):
                for ch, ga in Wset[a]["glyphs"].items():
                    gb = Wset[b]["glyphs"].get(ch)
                    if not gb or not ga.get("d") or not gb.get("d"): continue
                    ya = [ga["box"][1], ga["box"][3]] + [q for x, y, r in pins_of(Wset[a], ch, ga) for q in (-y - r, -y + r)]
                    yb = [gb["box"][1], gb["box"][3]] + [q for x, y, r in pins_of(Wset[b], ch, gb) for q in (-y - r, -y + r)]
                    ha, hb = max(ya) - min(ya), max(yb) - min(yb)
                    # a glyph drawn to the pin (•) may follow the pin's step; a small one made of stacked strokes (⁼) may
                    # grow by two stems' step
                    pk = Wset[b]["pin"]["r"] / Wset[a]["pin"]["r"]
                    grow = max(0.25 * ha, (pk * 1.02 - 1) * ha, 2 * (Wset[b]["s"] - Wset[a]["s"]))
                    if ha > 50 and not (min(0.8, pk / 1.02) * ha <= hb <= ha + grow):
                        fail("data", f"{name}:{a}->{b}:{ch} height x{hb / ha:.2f}", ch)

    # ---- geometry gates
    geo_gates = {"topology", "counter", "mono", "spike"}
    if only is None or only & geo_gates:
        tasks = []
        for name, Wset in sets.items():
            for w, F in Wset.items():
                chars = [c for c in F["glyphs"] if c not in (" ", "림")]
                tasks.append((name, w, F, chars))
        R = {}
        with ProcessPoolExecutor(min(len(tasks), int(os.environ.get("LIMN_JOBS", os.cpu_count() or 8)))) as ex:
            for name, w, out in ex.map(measure, tasks):
                R.setdefault(name, {})[w] = out
        for name, byw in R.items():
            ws = sorted(byw, key=int)
            S = {w: sets[name][w]["s"] for w in ws}
            for w in ws:
                for ch, m in byw[w].items():
                    if "err" in m: fail("spike", f"{name}:{w}:{ch} pathops {m['err']}", ch); continue
                    if on("counter"):
                        for v in m["mic"]:
                            if v < COUNTER_MIN * S[w]: fail("counter", f"{name}:{w}:{ch} {v / S[w]:.2f} S", ch)
                    if on("spike"):
                        for kind, L, b in m["spikes"]: fail("spike", f"{name}:{w}:{ch} {kind} {L:.0f} u at {b}", ch)
                        for a_ in m["specks"]: fail("spike", f"{name}:{w}:{ch} speck {a_} u2", ch)
            for a, b in zip(ws, ws[1:]):
                for ch, ma in byw[a].items():
                    mb = byw[b].get(ch)
                    if not mb or "err" in ma or "err" in mb: continue
                    if on("topology") and ma["topo"] != mb["topo"] and ch not in TOPO_ALLOW:
                        fail("topology", f"{name}:{a}->{b}:{ch} pieces/counters {ma['topo']} -> {mb['topo']}", ch)
                    if on("mono") and mb["ink"] < ma["ink"] * (1 - MONO_TOL):
                        fail("mono", f"{name}:{a}->{b}:{ch} ink {ma['ink']:.0f} -> {mb['ink']:.0f} ({100 * (mb['ink'] / ma['ink'] - 1):+.1f} %)", ch)
        geo_out.update(R)

    # ---- kerning coverage, accents
    for name, Wset in sets.items():
        for w, F in sorted(Wset.items(), key=lambda kv: int(kv[0])):
            if on("kerncover"):
                kc = F.get("kcover")
                if kc is None: fail("kerncover", f"{name}:{w} no kcover in the data (build_font.py)")
                elif kc: fail_list("kerncover", f"{name}:{w} not measured: ", kc)
            if on("accent"):
                g = F["glyphs"].get("¯")
                if g and g.get("d"):
                    b = g["box"]; k = (b[3] - b[1]) / F["s"]
                    if not ACCENT[0] <= k <= ACCENT[1]: fail("accent", f"{name}:{w} macron {b[3] - b[1]:.1f} = {k:.2f} S", "¯")

    # ---- collisions
    if on("collision"):
        pairs = pair_corpus(scope)
        tasks = [(name, w, F, pairs) for name, Wset in sets.items() for w, F in Wset.items()]
        with ProcessPoolExecutor(min(len(tasks), int(os.environ.get("LIMN_JOBS", os.cpu_count() or 8)))) as ex:
            for name, w, hits in ex.map(collide, tasks):
                for pr, d in hits: fail("collision", f"{name}:{w}:{pr} {d:.2f} S", pr)

    # ---- the default build: S on the HALF curve, and the white between the pins of “ at 400 = 0.13 XH
    if on("curve") and "play" in sets and os.environ.get("LIMN_WCURVE", "HALF").upper() == "HALF":
        import weights as WT
        for i, w in enumerate(range(100, 1000, 100)):
            F = sets["play"].get(str(w))
            if F is None: fail("curve", f"play:{w} missing"); continue
            if abs(F["s"] - WT.STEM_TABLES["HALF"][i]) > 0.51:          # the data keeps S in whole units
                fail("curve", f"play:{w} S {F['s']}, HALF {WT.STEM_TABLES['HALF'][i]}")
        F = sets["play"].get("400")
        if F and os.environ.get("LIMN_QUOTE_WHITE", "0.13") == "0.13":
            # “ is two equal drops, the second moved right by the pitch: white = pitch - 2 x the pin radius
            xs = []
            for c in ink_path(F["glyphs"]["“"]["d"], ()).contours:
                q = pathops.Path(); c.draw(q.getPen()); xs.append(q.bounds[0])
            white = sorted(xs)[1] - sorted(xs)[0] - 2 * F["pin"]["r"] if len(xs) == 2 else None
            want = 0.13 * F["xh"]
            if white is None or abs(white - want) > 1:
                fail("curve", f"play:400 “ white {white if white is None else round(white, 1)} u, want {want:.1f} ± 1")

    # ---- Hangul
    if on("hangul"):
        KS = {bytes([a, b]).decode("euc-kr") for a in range(0xB0, 0xC9) for b in range(0xA1, 0xFF)}
        for w, Hd in HG.items():
            g = Hd["glyphs"]
            if KS - set(g): fail("hangul", f"{w} missing KS X 1001 {''.join(sorted(KS - set(g))[:20])}")
            for ch, v in g.items():
                b = v["box"]
                if not v.get("d"): fail("hangul", f"{w}:{ch} empty")
                elif b[2] - b[0] <= 0 or b[3] - b[1] <= 0: fail("hangul", f"{w}:{ch} zero box")
                if v["adv"] <= 0: fail("hangul", f"{w}:{ch} adv<=0")
                if b[1] < -900 or b[3] > 250: fail("hangul", f"{w}:{ch} outside -900..250")
                if b[0] < -40 or b[2] > v["adv"] + 40: fail("hangul", f"{w}:{ch} ink past the advance")

    gates = ["data", "topology", "counter", "mono", "spike", "kerncover", "accent", "collision", "curve", "hangul"]
    for gname in gates:
        if not on(gname): continue
        v = fails.get(gname, [])
        print(f"{gname:10s} {'FAIL' if v else 'ok':4s} {len(v):5d}" + (": " + " | ".join(v[:12]) if v else ""))
        u = info.get(gname, [])
        if u:                             # out of scope: not a failure (in_scope)
            print(f"{gname:10s} info {len(u):5d} out of scope: " + " | ".join(x[:80] for x in u[:4]))
    print("audit scope:", scope, "(Hangul gate excluded)" if scope == "latin-symbols" else "")
    print("supplemental inputs:" if scope == "latin-symbols" else "hangul weights checked:", " ".join(sorted(HG, key=int)) or "none (make hangul)")
    if jpath:                             # --json PATH: every failure line, by gate, the out-of-scope findings (and the geometry per glyph)
        json.dump({"scope": scope, "fails": fails, "info": info, "geometry": geo_out}, open(jpath, "w"), ensure_ascii=False)
    sys.exit(1 if fails else 0)


if __name__ == "__main__":
    main()
