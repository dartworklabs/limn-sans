"""Build the limn typeface from Quicksand Bold.

limn inherits Quicksand's whole system (proportions, curves, figures, spacing, kerning) and changes
only what the brand rules require. Every change is listed in MODS and written into the output, so
the pages can show exactly where limn departs from its parent.

  uv run --no-project --with fonttools --with skia-pathops --with uharfbuzz python3 tools/build_font.py
  LIMN_WGHT=500 LIMN_PLAY_OUT=/tmp/w500.json ...   # one weight's playground data (tools/build_play.py)

Quicksand © The Quicksand Project Authors, SIL Open Font License 1.1 (tools/OFL-Quicksand.txt).
"Quicksand" is a Reserved Font Name, so the modified glyphs are published only as "limn".
"""
import sys as _sys, pathlib as _pl, time as _time; _sys.path.insert(0, str(_pl.Path(__file__).parent))
from ofl_header import header
_T0 = _time.time()
def _tick(what):
    if __import__("os").environ.get("LIMN_TIMING"): print(f"[{_time.time() - _T0:6.1f}s] {what}", file=_sys.stderr)
import json
import math
import os
import sys
from pathlib import Path as FSPath

import pathops
import uharfbuzz as hb
from fontTools.pens.svgPathPen import SVGPathPen
from fontTools.pens.transformPen import TransformPen
from fontTools.ttLib import TTFont
from fontTools.varLib.instancer import instantiateVariableFont

SRC = str(FSPath(__file__).resolve().parent / "Quicksand[wght].ttf")   # Google Fonts, OFL
WGHT = int(os.environ.get("LIMN_WGHT", 700))
PLAY_OUT = os.environ.get("LIMN_PLAY_OUT")   # set: write this weight's playground data there instead
OUT = FSPath(os.environ.get("LIMN_FONT_OUT") or FSPath(__file__).resolve().parent.parent / "limn-font.js")   # LIMN_FONT_OUT: option builds (m-width) never touch the live file

LOWER = "abcdefghijklmnopqrstuvwxyz"
UPPER = "ABCDEFGHIJKLMNOPQRSTUVWXYZ"
DIGITS = "0123456789"
PUNCT = ".,:;!?·-–—/'\"()&@#%+=*_[]{}\\|$<>^~`…¡¿‘’“”‚„×÷€£¥¢°©®™«»‹›•±§¶†‡‰¦¬µ¹²³½¼¾ºª¤₩№⁄"   # common symbols (proof B05: € was missing; sweep 2026-09-28: ¤ ₩ № ⁄)
CHARS = LOWER + UPPER + DIGITS + PUNCT
DOTTED = ".:;!?·ij"          # every round dot in these becomes the pin

from weights import instance as _weights_instance   # wght 100-900: Quicksand's own at 300-700, pen-offset outside
font = _weights_instance(SRC, WGHT)
gs = font.getGlyphSet()
cmap = font.getBestCmap()
hmtx = font["hmtx"].metrics
UPM = font["head"].unitsPerEm


# ---------------------------------------------------------------- geometry helpers
def gpath(ch, name=None):
    p = pathops.Path()
    gs[name or cmap[ord(ch)]].draw(p.getPen(glyphSet=gs))
    p.simplify()              # variable-font outlines overlap; merge them into clean contours
    return p


def bounds(p):
    return p.bounds  # (xmin, ymin, xmax, ymax)


def polylines(p, steps=24):
    """Flatten a path into closed polylines for slicing."""
    polys, cur, start = [], [], None
    for verb, pts in p.segments:
        if verb == "moveTo":
            cur = [pts[0]]; start = pts[0]
        elif verb == "lineTo":
            cur.append(pts[0])
        elif verb == "qCurveTo":
            if pts[-1] is None:     # closed contour made only of off-curve points
                ctrl = list(pts[:-1]); mid = ((ctrl[-1][0] + ctrl[0][0]) / 2, (ctrl[-1][1] + ctrl[0][1]) / 2)
                cur = [mid]; pts = tuple(ctrl) + (mid,)
            p0 = cur[-1]
            # a TrueType qCurve may carry implied on-curve points
            ctrl = list(pts[:-1]); end = pts[-1]
            segs = []
            for i, c in enumerate(ctrl):
                e = end if i == len(ctrl) - 1 else ((c[0] + ctrl[i + 1][0]) / 2, (c[1] + ctrl[i + 1][1]) / 2)
                segs.append((c, e))
            for c, e in segs:
                for k in range(1, steps + 1):
                    t = k / steps
                    cur.append(((1 - t) ** 2 * p0[0] + 2 * (1 - t) * t * c[0] + t * t * e[0],
                                (1 - t) ** 2 * p0[1] + 2 * (1 - t) * t * c[1] + t * t * e[1]))
                p0 = e
        elif verb == "curveTo":
            p0 = cur[-1]; c1, c2, e = pts
            for k in range(1, steps + 1):
                t = k / steps; u = 1 - t
                cur.append((u ** 3 * p0[0] + 3 * u * u * t * c1[0] + 3 * u * t * t * c2[0] + t ** 3 * e[0],
                            u ** 3 * p0[1] + 3 * u * u * t * c1[1] + 3 * u * t * t * c2[1] + t ** 3 * e[1]))
        elif verb in ("closePath", "endPath"):
            if cur: polys.append(cur)
            cur = []
    if cur: polys.append(cur)
    return polys


def slice_at(p, y):
    """Ink intervals of a simplified path on the horizontal line y (even-odd)."""
    xs = []
    for poly in polylines(p):
        n = len(poly)
        for i in range(n):
            (x0, y0), (x1, y1) = poly[i], poly[(i + 1) % n]
            if (y0 <= y < y1) or (y1 <= y < y0):
                xs.append(x0 + (y - y0) * (x1 - x0) / (y1 - y0))
    xs.sort()
    return [(xs[i], xs[i + 1]) for i in range(0, len(xs) - 1, 2)]


def rect(x0, y0, x1, y1):
    p = pathops.Path()
    p.moveTo(x0, y0); p.lineTo(x1, y0); p.lineTo(x1, y1); p.lineTo(x0, y1); p.close()
    return p


def circle(cx, cy, r, n=4):
    """A circle from four cubic quarters (k = 0.5523)."""
    k = 0.5522847 * r
    p = pathops.Path()
    p.moveTo(cx + r, cy)
    p.cubicTo(cx + r, cy + k, cx + k, cy + r, cx, cy + r)
    p.cubicTo(cx - k, cy + r, cx - r, cy + k, cx - r, cy)
    p.cubicTo(cx - r, cy - k, cx - k, cy - r, cx, cy - r)
    p.cubicTo(cx + k, cy - r, cx + r, cy - k, cx + r, cy)
    p.close()
    return p


def union(*ps):
    return pathops.op(ps[0], ps[1], pathops.PathOp.UNION) if len(ps) == 2 else union(union(ps[0], ps[1]), *ps[2:])


def diff(a, b):
    return pathops.op(a, b, pathops.PathOp.DIFFERENCE)


def inter(a, b):
    return pathops.op(a, b, pathops.PathOp.INTERSECTION)


def xform(p, a=1, b=0, c=0, d=1, e=0, f=0):
    return p.transform(a, b, c, d, e, f)


# ---------------------------------------------------------------- measured system
def _b(ch):
    return gpath(ch).bounds


# read from the font, so every weight gets its own (at 700: 535 · 545 · 740 · -200 · 700 · 120)
XH = round(_b("x")[3])          # flat x-height (top of x, i, u stems)
XO = round(_b("o")[3])          # round x-height (overshoot of n, o)
ASC = round(_b("l")[3])         # ascender (b d f h k l)
DESC = round(_b("p")[1])        # descender (p q g j y)
CAP = round(_b("H")[3])
S = round(_b("l")[2] - _b("l")[0])   # stem: l is 75..195
# The pin follows Quicksand's own dot across the weights (audit 2026-09-27): Quicksand grows its dot
# with the weight but slower than the stem (d/s 1.73 at 300 → 1.05 at 700) and keeps the white under
# it almost constant (68 → 65). limn scales both by fixed factors, set at the brand weight 700 so the
# pin is r 78.5 with a 48 gap there — which puts its top exactly on the ascender (the A rule).
def _i_dot():
    cs = sorted(gpath("i").contours, key=lambda c: c.bounds[3])
    d = cs[-1].bounds
    return (d[2] - d[0]) / 2, d[1] - XH          # Quicksand's dot radius, white above the x-height
Q_DOT_R, Q_GAP = _i_dot()
# The i stem's own top: Quicksand's round top rises over the flat x-height at the light weights (+5 at 100, +3.5 at
# 400, +0.7 at 700, 0 from 800). The engine places the pin from the x-height (XH + gap + r), so the white the eye
# sees between stem and pin is the gap less this rise (2026-09-29: 77 at 100 where 82 was meant).
def _i_top():
    cs = sorted(gpath("i").contours, key=lambda c: c.bounds[3])
    return cs[0].bounds[3]
I_OS = max(0.0, _i_top() - XH)
PIN_K, GAP_K = 78.5 / 63.0, 48.0 / 65.0          # limn pin ÷ Quicksand dot (r 63, gap 65), measured at 700
PIN_R = Q_DOT_R * PIN_K
GAP = Q_GAP * GAP_K                               # white between pin and i stem (0.4 s at 700)
# ==== lin 2026-09-27 · thin-end pin rule (LIMN_PIN_RULE) =================================================
# user 2026-09-27: "특수문자들 thin 쪽으로 갈 수록 ... 점이 붙은 문자들이나 나누기 기호 ... 비율이 이상". Below 700
# the pin followed Quicksand's dot, extrapolated past its axis: at 100 (s 18) it was 3.7 s across (0.13 XH),
# while the thin references draw their dots 2.0-2.6 s (0.08-0.11 XH: Inter, Lexend, M+ Rounded 1c Thin), and
# the white next to a pin stayed ~50 units at every weight, so ÷ ! ? ¨ closed up as the strokes thinned
# (the references open that white 1.4-2.5x from 700 to Thin; Quicksand's own ÷ 2.5x from 700 to 300).
# Both now follow straight lines in the stem and x-height, like the references' dots (d = a XH + b S), fixed
# by two anchors: the brand weight (s 120, XH 535: r 78.5, white 48 — unchanged) and the thin end (s 20,
# XH 510: diameter PIN_THIN x s, white GAP_THIN x the 700 white in XH units). Only below s 120; 700 and
# above keep the parent-dot rule. LIMN_PIN_RULE=parent gives the rule before.
PIN_RULE = os.environ.get("LIMN_PIN_RULE", "lin")
PIN_THIN = float(os.environ.get("LIMN_PIN_THIN", 2.5))     # pin diameter / stem at s 20 (refs 2.05-2.64)
GAP_THIN = float(os.environ.get("LIMN_GAP_THIN", 1.8))     # pin white / XH at s 20, over its 700 value (refs: ! 1.45x, ÷ ¨ 2.1x; 1.8 ~ their geometric mean)
if PIN_RULE == "lin" and S < 120:
    _s0, _x0, _s1, _x1 = 20.0, 510.0, 120.0, 535.0
    _pb = (2 * 78.5 - _x1 / _x0 * PIN_THIN * _s0) / (_s1 - _x1 / _x0 * _s0)       # d = _pa XH + _pb S
    _pa = (PIN_THIN * _s0 - _pb * _s0) / _x0
    _g1 = 48.0 / _x1 * (GAP_THIN - 1) / (_s1 / _x1 - _s0 / _x0)                  # GAP = XH (_g0 - _g1 S / XH)
    _g0 = 48.0 / _x1 + _g1 * _s1 / _x1
    PIN_R = (_pa * XH + _pb * S) / 2
    GAP = _g0 * XH - _g1 * S
# ==== /lin ==================================================================================================
# proof audit 2026-09-27 (C-05): text cut. The playground's optical size used to enlarge only the
# drawn pin (min 2.2 px) and lift it (gap min 1.25 px); nothing else knew — commas, quotes, … , ! ?
# and the kerning kept the small pin, so at 12-20 px the enlarged pin ran into the 1 of 1,024, into
# the stem of !, and the two pins of “ ” … merged. LIMN_OPT_PX builds the whole weight at a design
# size instead: pin and gap are held at the on-screen minimum there and everything downstream
# (punct.py, ! ?, pin kerning) is built around that pin.
# proof audit 2026-09-27 (C-08), options for the extreme-weight pin (default "follow" = unchanged):
#   LIMN_PIN_HI=taper  above 700 the pin and its gap shrink toward the heavy references (Inter, Nunito,
#                      Outfit, M+ Rounded Black: dot 1.0-1.1 s, gap 0.23-0.45 s): r 0.654 s -> 0.5 s and
#                      gap 0.4 s -> 0.25 s between s 120 and 200. Pin top 827 -> 798 at 900 (asc 740).
#   LIMN_PIN_LO=lift   below 700 the pin top rises from the cap height (s 18) to the ascender (s 120)
#                      instead of sinking with Quicksand's dot (623 at 100): gap opens, size unchanged.
PIN_HI, PIN_LO = os.environ.get("LIMN_PIN_HI", "follow"), os.environ.get("LIMN_PIN_LO", "follow")
if PIN_HI == "taper" and S > 120:
    _t = min(1.0, (S - 120) / 80)
    PIN_R = S * (0.654 + (0.5 - 0.654) * _t); GAP = S * (0.4 + (0.25 - 0.4) * _t)
if PIN_LO == "lift" and S < 120:
    _top = CAP + (ASC - CAP) * max(0.0, (S - 18) / (120 - 18))
    GAP = max(GAP, _top - XH - 2 * PIN_R)
OPT_PX = float(os.environ.get("LIMN_OPT_PX", 0) or 0)
if OPT_PX:
    _ppu = OPT_PX / UPM
    PIN_R = max(PIN_R, 1.1 / _ppu); GAP = max(GAP, 1.25 / _ppu)
# ==== poc 2026-09-30 · pin-size cap for the PoC page (QA visual S5, outlines S7), built only when asked =======
# LIMN_PIN_CAP=1.4 | 1.25: pin diameter <= that x the stem at every weight (none = the rules above, unchanged).
# Every pin and comma head takes it (punct, accents, greek read PIN_R); GAP and the i top rule stay as they are.
PIN_CAP = os.environ.get("LIMN_PIN_CAP", "none")
if PIN_CAP != "none":
    PIN_R = min(PIN_R, float(PIN_CAP) * S / 2)
# ==== /poc ==================================================================================================
PIN_CY = XH + GAP + PIN_R                         # i pin centre (y up); at 700 the pin top = ASC
# ---- wcons 2026-09-27 · one vertical rule at every weight ----------------------------------------------
# The rule at 700 is l top = pin top = ascender (740). Following Quicksand's dot, the pin top only met the
# ascender at 700 (623 at 100, 827 at 900) while l, b, d, h, k stayed on 740 — so i and l drifted apart
# and the pages, which fit each line to its ink, drew l shorter at 800-900. Now the pin top is on the
# ascender at every weight: the pin keeps Quicksand's dot size (PIN_K), and the white under it (I_GAP)
# takes what is left. Above 700 there is less room than the parent's dot wants, so the white may narrow
# from 0.4 s (700) to 0.2 s (at s 180) and the pin gives the rest (r 78.5 at 700 · 79.6 at 800 · 84.5 at
# 900). GAP (white between a pin and any other stroke: ! ? ÷ …) stays the parent-dot rule.
# LIMN_PIN_TOP=follow gives the earlier rule (pin follows the parent dot, top = XH + GAP + 2 R).
# 2026-09-29 (user: "폰트가 얇아지면 i의 점과 세로획 사이 간격이 벌어지는 버그 … 특히 얇은 폰트가 매우 어색"): with
# the top held on the ascender the white under the pin took all the room the smaller pin left — 180 at 100, 128 at
# 400 against GAP 82 · 67 (the white every other pin keeps: ! ? ÷ ¨), 9 s at 100. Quicksand keeps its i white
# nearly constant (68 at 300, 65 at 700) and lets the dot's top move with the weight, and so do Inter and Nunito
# (dot top 716 -> 781, 685 -> 756 from thin to black). Now the white under the i pin is the smaller of the two:
# the room up to the ascender and GAP. The brand drawing (s 120) and the heavy end keep the top on the ascender
# (their room is the smaller); the lighter weights keep GAP and their pin sits lower (top 647 at 100, 683 at 400).
# LIMN_PIN_TOP=asc restores the top on the ascender at every weight.
PIN_TOP = os.environ.get("LIMN_PIN_TOP", "gap")
I_GAP = GAP
if PIN_TOP in ("asc", "gap") and not OPT_PX and PIN_HI == "follow" and PIN_LO == "follow":
    _gmin = S * (0.4 - 0.2 * max(0.0, min(1.0, (S - 120) / 60)))
    PIN_R = min(PIN_R, (ASC - XH - _gmin) / 2)
    I_GAP = ASC - XH - 2 * PIN_R                      # from the x-height, the engine's reference
    if PIN_TOP == "gap":
        I_GAP = min(I_GAP, GAP + I_OS)                # GAP is the white above the stem's own top
    PIN_CY = XH + I_GAP + PIN_R
elif PIN_TOP in ("asc", "gap") and OPT_PX:
    # text cut: pin and white held at the screen minimum; the top stays on the ascender while it fits
    I_GAP = max(ASC - XH - 2 * PIN_R, 1.25 / _ppu)
    if PIN_TOP == "gap":
        I_GAP = max(min(I_GAP, GAP + I_OS), 1.25 / _ppu)
    PIN_CY = XH + I_GAP + PIN_R
# ---- /wcons ---------------------------------------------------------------------------------------------


def split_dot(p, above):
    """Remove round dot contours whose bottom lies above `above`; return (rest, dot centres)."""
    rest = pathops.Path(); dots = []
    for c in p.contours:
        xmin, ymin, xmax, ymax = c.bounds
        w, h = xmax - xmin, ymax - ymin
        if ymin > above and abs(w - h) < 0.25 * max(w, h) and w < max(1.4 * S, 160):
            dots.append(((xmin + xmax) / 2, (ymin + ymax) / 2, w / 2))
        else:
            rest.addPath(c)
    rest.simplify()
    return rest, dots


def flatten_feet(p):
    """Square every vertical stem end that stands on the baseline or hangs to the descender.
    A stem is recognised by a slice ≈ S wide that stays at the same x across 120 units; its round
    cap is filled out to a square corner. Diagonals, bowls and hooks do not pass the test."""
    added = []

    def stem_width(edge, x, foot):
        """Width of the stem that stands on a vertical edge, read higher up where it is alone
        (the narrowest reading — where a bowl joins, the slice is wider)."""
        ws = [b - a for y in range(int(foot + 150), int(foot + 460), 25) for a, b in slice_at(p, y)
              if 0.85 * S <= b - a <= 1.2 * S and abs((a if edge == "L" else b) - x) < 1.5]
        return min(ws) if ws else S

    def bottom(ca, cb, foot):
        """Lowest ink in the column [ca, cb] near the foot line (b's stem sinks with its bowl)."""
        for y in range(int(foot - 20), int(foot + 6)):
            if any(iv[1] > ca + 1 and iv[0] < cb - 1 for iv in slice_at(p, y + 0.5)):
                return y
        return None

    for foot in (0, DESC):
        # proof audit 2026-09-27 (C-02): above 700 the straight run of a stem under a bar (4 at 900:
        # bar from 175) or over a bowl joint (a b d) is shorter than 0.62 s + 60, so the probes hit the
        # bar and the foot stayed round. Same lines up to 700 (S <= 120), lower and closer above it.
        y1 = foot + min(0.62 * S, 0.52 * S + 12); y2 = y1 + 60 * min(1.0, 120 / S)
        up = slice_at(p, y2)
        boxes = []
        for a, b in slice_at(p, y1):
            if b - a < 0.85 * S:
                continue
            L = any(abs(iv[0] - a) < 1.5 for iv in up)      # vertical outer edges: same x on both lines
            R = any(abs(iv[1] - b) < 1.5 for iv in up)
            if L and R and b - a <= 1.2 * S:
                boxes.append((a, b, a, b))                    # a free-standing stem
                continue
            if L:
                w = stem_width("L", a, foot); boxes.append((a, a + w, a, a + w / 2))
            if R:
                w = stem_width("R", b, foot); boxes.append((b - w, b, b - w / 2, b))
        for a, b, ca, cb in boxes:
            # judge on the outer half of the stem, so a bowl or bar joining on the inside
            # (b, d, B, L) does not hide the end
            yb = bottom(ca, cb, foot)
            if yb is None or yb <= foot - 20:
                continue          # no end here, or the ink goes on below
            low = [iv for iv in slice_at(p, yb + 1.5) if iv[1] > ca + 1 and iv[0] < cb - 1]
            if not low or (low[0][0] <= ca + 3 and low[-1][1] >= cb - 3):
                continue          # already square
            # a joint is not an end: when another stroke meets the stem right at the foot (N's
            # diagonal, the bars of L E B D), the corner stays round as in Quicksand (user 2026-09-27:
            # "중간 연결 점은 전부 원형으로") — only a stem that ends by itself gets a flat foot
            mid = (ca + cb) / 2
            jv = next((iv for iv in slice_at(p, yb + 0.3 * S) if iv[0] <= mid <= iv[1]), None)
            # (C-02) a bar or diagonal is joined all the way down; a bowl (a b d q) leaves a V open
            # just above the end. At 800-900 the bowl's thick bottom closes that V by 0.3 s, so also
            # ask 0.1 s above the end: only a stroke joined there too is a joint.
            jv0 = next((iv for iv in slice_at(p, yb + 0.1 * S) if iv[0] <= mid <= iv[1]), None)
            if S <= 120 and jv and jv[1] - jv[0] > (b - a) + 6:
                continue
            # ---- wcons 2026-09-27: C-02 read N's round bottom joint (diagonal into stem) as a lone stem end at
            # 800-900 and squared it (N's lower right corner poked out, the user's "N 또한"). A bowl's V
            # (a b d q) shows as a second piece of ink right next to the stem 0.1 s above the end; a
            # diagonal's round joint shows as one piece alone. Only the V makes a foot.
            if S > 120 and jv and jv[1] - jv[0] > (b - a) + 6:
                if jv0 and jv0[1] - jv0[0] > (b - a) + 6:
                    continue
                row = slice_at(p, yb + 0.1 * S)
                if jv0 and not any(iv != jv0 and min(abs(iv[0] - jv0[1]), abs(jv0[0] - iv[1])) < 0.5 * S for iv in row):
                    continue
            # ---- /wcons
            # a bowl joining the stem low down (a b d q) leaves a small V between the bowl and the
            # stem's old round end; square the foot out to that V so no step remains
            if (ca, cb) != (a, b):
                mid = (a + b) / 2
                side = [], []
                for y in range(int(yb) + 2, int(y1) + 2):
                    iv = next((iv for iv in slice_at(p, y + 0.5) if iv[0] <= mid <= iv[1]), None)
                    if iv is None: break
                    if iv[1] - iv[0] > (b - a) + 30: break            # merged with the bowl
                    side[0].append(iv[0]); side[1].append(iv[1])
                if side[0]:
                    top = int(yb) + 2 + len(side[0])
                    if ca == a: b = max(b, max(side[1]))                  # stem on the left (b)
                    else: a = min(a, min(side[0]))                      # stem on the right (a d q)
                    p = union(p, rect(a, yb, b, top + 1))
            p = union(p, rect(a, yb, b, y1 + 1))
            if yb < foot:
                # Quicksand sinks b's stem end with its bowl (to -10); a flat foot stands exactly on
                # the line, like every other foot — trim the stem column back to it
                p = diff(p, rect(a - 1, yb - 2, b if ca == a else b + 1, foot))
                p = union(p, rect(a, foot, b, y1 + 1))
            added.append(round((a + b) / 2))
    return p, added


def smooth_seam(p, y0, y1):
    """wcons 2026-09-27: where a glyph was cut on a horizontal and its two parts moved together (the ?
    tail), the edges do not meet flush and leave a step (a square notch on the ? tail at 700, bigger
    steps at 800-900). Inside the band y0..y1 (+- a quarter stem) close and then open the outline with a
    radius of a quarter stem: the step fills and its corner rounds, like every other joint."""
    from weights import _soff as _so
    if S == 120 and not os.environ.get("LIMN_SEAM700"):
        return p            # the brand weight stays as it was (LIMN_SEAM700=1 smooths its ? too: 147 units², the tail notch)
    r = 0.25 * S; lo, hi = min(y0, y1) - r, max(y0, y1) + r
    q = _so(_so(p, r, r), -r, -r)
    q = _so(_so(q, -r, -r), r, r)
    band = rect(-1e4, lo, 1e4, hi)
    out = union(diff(p, band), inter(q, band)); out.simplify()
    if len(list(out.contours)) != len(list(p.contours)):
        return p            # the smoothing must not split or join anything (200: a thin tail came loose)
    return out


def stems_of(p, y=None):
    """x centres of vertical stems (slices ≈ S wide) on a line inside the x-height."""
    y = y or 0.28 * XH
    return [round((a + b) / 2, 1) for a, b in slice_at(p, y) if 0.85 * S <= b - a <= 1.15 * S]


# ---------------------------------------------------------------- build
MODS = []   # [char, what changed, why]
G = {}


def put(ch, p, adv=None, lsb_ref=None, pins=()):
    G[ch] = {"p": p, "adv": adv if adv is not None else hmtx[cmap[ord(ch)]][0], "pins": list(pins)}


for ch in CHARS:
    if ord(ch) not in cmap:
        print("missing", ch, file=sys.stderr); continue
    put(ch, gpath(ch))
ORIG = {ch: g["p"] for ch, g in G.items()}   # Quicksand as it is, for the side-by-side pages

# ---- wcons 2026-09-27 · u's stems reach the x-height ------------------------------------------------------
# Quicksand's u stops short of the x-height below 700 (499 against 510 at 300, 526 against 529 at 600),
# while i, x, v and the n built from it stand on it. Stretch u's upper half so both stem ends meet the
# x-height; the bowl is untouched. At 700 u already meets it (no change). The turned-over n then stands on
# the baseline by itself (N_LIFT below becomes 0).
_ub = bounds(G["u"]["p"])
if XH - _ub[3] > 0.5:
    from weights import _map as _wmap0, _piecewise as _wpiece0
    G["u"]["p"] = _wmap0(G["u"]["p"], _wpiece0([0.5 * XH, _ub[3]], [0.5 * XH, XH])); G["u"]["p"].simplify()
    MODS.append(["u", f"세로획 끝 +{XH - _ub[3]:.0f} → x높이", "Quicksand의 u는 700 아래에서 x높이에 못 미침 — 위 절반만 늘려 두 세로획 끝을 x높이에"])
# ---- /wcons ---------------------------------------------------------------------------------------------

# 1 · spurless n family — n is u turned over (Quicksand's own u, rotated 180°), so the arch flows
#     into both stems without a spur. m, h, r are built from that n.
u = G["u"]["p"]; ux0, uy0, ux1, uy1 = bounds(u)
n2 = xform(u, -1, 0, 0, -1, ux0 + ux1, XH)            # (x, y) -> (x0+x1-x, 535-y): stems stand on 0
n2.simplify()
# proof audit 2026-09-27 (C-01): below 700 Quicksand's u stems stop short of the x-height (486 at 100,
# 508 at 400, 535 = XH only at 700), so the turned u stood 12 ... 3 units above the baseline — n m r h
# floated, and at 100-400 flatten_feet never found their feet (round feet next to flat i l k). Stretch
# the stem part (baseline .. half the x-height) down onto the baseline; the arch above is untouched.
N_LIFT = bounds(n2)[1]
if N_LIFT > 0.5:
    from weights import _map as _wmap, _piecewise as _wpiece
    n2 = _wmap(n2, _wpiece([N_LIFT, 0.5 * XH], [0.0, 0.5 * XH])); n2.simplify()
nx0, _, nx1, _ = bounds(n2)
u_adv = G["u"]["adv"]; u_lsb = ux0; u_rsb = u_adv - ux1
put("n", n2, adv=u_adv)                               # mirrored: lsb/rsb swap, u's are equal-ish
ns = stems_of(n2); pitch = ns[1] - ns[0]
MODS.append(["n", "u를 180° 돌린 것", f"어깨(왼쪽 세로획 윗돌기) 없이 아치가 두 세로획으로 이어짐. 폭 {round(nx1-nx0)} (Quicksand n 466)"])

m2 = union(n2, xform(n2, e=pitch)); m2.simplify()
put("m", m2, adv=u_adv + pitch)
MODS.append(["m", "n 두 개를 세로획 하나 겹쳐 붙임", f"세로획 간격 {pitch:.0f} (Quicksand m 336과 같음). 가운데는 두 아치가 만나는 골짜기 하나"])

# n width (checklist S4, decided 2026-09-27): the turned-over u was the narrowest n of eight fonts
# (ink 0.854 × x-height, references ≥ 0.871), so o and m read wide beside it. Extrude the arch at its
# middle by NW; the stems and both round shoulders stay. m keeps two of the old n (its width is set
# by MK below) and r keeps the old arch, so only n and h widen.
NW = round(9 * S / 120, 1)
def widen_mid(p, dw):
    x0, _, x1, _ = bounds(p); cx = (x0 + x1) / 2
    out = union(inter(p, rect(-1e4, -1e4, cx, 1e4)), xform(inter(p, rect(cx, -1e4, 1e4, 1e4)), e=dw))
    strip = inter(p, rect(cx - 0.5, -1e4, cx + 0.5, 1e4))
    t = 0.0
    while t <= dw:
        out = union(out, xform(strip, e=t)); t += 0.5
    out.simplify(); return out
n_w = widen_mid(n2, NW)
put("n", n_w, adv=u_adv + NW)
MODS.append(["n h", f"아치 가운데 +{NW:g}", "u를 돌린 n은 참고 서체 8종보다 좁아(잉크 0.854 × x높이, 참고 ≥ 0.871) o와 m이 넓어 보임 — 두 세로획과 둥근 어깨는 그대로, 아치만 늘림. m·r은 늘리기 전 n에서 만듦"])

lq = G["l"]["p"]; lx0, _, lx1, _ = bounds(lq)
stem_l = xform(lq, e=ns[0] - (lx0 + lx1) / 2)
h2 = union(n_w, stem_l); h2.simplify()
put("h", h2, adv=u_adv + NW)
MODS.append(["h", "l 세로획 + 어깨 없는 n", "아치가 세로획 옆에서 곧바로 솟음"])

# r: the new n cut on a vertical through its arch, ended with a round cap like every other end
rq = G["r"]["p"]; rx0, _, rx1, _ = bounds(rq)
xc = ns[0] + 0.62 * pitch
ys =[y for y in range(int(XH * 0.5), XO + 2) if any(a <= xc <= b for a, b in slice_at(n2, y))]
y_in, y_out = min(ys), max(ys)
cap_r = (y_out - y_in) / 2
r2 = union(inter(n2, rect(nx0 - 5, -5, xc, XO + 20)), circle(xc, (y_in + y_out) / 2, cap_r))
r2.simplify()
r_adv = round(xc + cap_r + (G["r"]["adv"] - rx1))
put("r", r2, adv=r_adv)
# spacing audit (2026-09-27): the spurless n's left side is now a round shoulder, which reads 8 units
# wider than Quicksand's straight stem (area model calibrated on Quicksand's own nn = oo); take it back
LSB_FIX = -8
for ch in "nmr":
    G[ch]["p"] = xform(G[ch]["p"], e=LSB_FIX); G[ch]["adv"] += LSB_FIX
# m width (question 2026-09-27): m is two n's, so its counters equal n's and its ink is 1.74 × n —
# the widest m among 12 reference fonts (median ≈ 1.64). narrow(): scale across, then give the
# stems back their weight with a horizontal-only dilation, so only the counters shrink.
def narrow(p, k):
    x0 = bounds(p)[0]; q = xform(p, k, 0, 0, 1, x0 * (1 - k), 0); dl = S * (1 - k)
    n = max(2, math.ceil(dl / 2))
    parts = [xform(q, e=-dl / 2 + dl * i / n) for i in range(n + 1)]
    out = parts[0]
    for part in parts[1:]:
        out = union(out, part); out.simplify()
    out = xform(out, e=dl / 2); out.simplify()
    return out
MK = float(os.environ.get("LIMN_MK", 0.90))   # option C, decided 2026-09-27 (m-width.html)
if MK != 1.0:
    w0 = bounds(G["m"]["p"])[2] - bounds(G["m"]["p"])[0]
    G["m"]["p"] = narrow(G["m"]["p"], MK)
    G["m"]["adv"] = round(G["m"]["adv"] - (w0 - (bounds(G["m"]["p"])[2] - bounds(G["m"]["p"])[0])))
MODS.append(["n m r", "왼쪽 여백 −8", "어깨를 없애 왼쪽 윗모서리가 둥글어진 만큼 흰 공간이 넓어 보여, Quicksand의 nn·oo와 같은 면적 기준으로 되돌림"])
MODS.append(["r", "어깨 없는 n의 아치를 잘라 둥근 끝", f"Quicksand r의 윗돌기를 없애 n과 같은 어깨. 폭 {round(xc + cap_r - nx0)} (Quicksand r {round(rx1-rx0)})"])

OSH = XO - XH   # overshoot of round glyphs (10 at 700)
QDROP = None
DOTSPEC = {}   # per glyph: how each pin is anchored (i · base · top · mid), Quicksand's own dot radius
# 2 · pins — every round dot becomes the pin (one size, one colour). i and j: pin top on the
#     ascender, white GAP above the stem; so the stem keeps Quicksand's x-height.
for ch in DOTTED:
    if ch not in G: continue
    p = G[ch]["p"]
    rest, dots = split_dot(p, above=-1e9 if ch in ".:;!?·" else XH + 10)
    DOTSPEC[ch] = {"only": ch in ".:·", "adv0": G[ch]["adv"], "pins": [
        ["i" if ch in "ij" else "base" if cy - r0 < 20 else "mid" if ch == "·" else "top",
         round(cx, 1), round(cy if ch == "·" else cy + r0, 1), round(r0, 1)] for cx, cy, r0 in dots]}
    if ch in "ij":
        (cx, cy, r0), = dots
        pins = [(cx, PIN_CY)]
    else:
        pins = []
        for cx, cy, r0 in dots:
            # keep the dot's own edge that faces the line it sits on: bottom dots stand on the
            # baseline, upper dots keep their top, the middle dot keeps its centre
            if cy - r0 < 20: pins.append((cx, PIN_R - OSH))           # stands on the baseline, overshooting like o
            elif ch == "·": pins.append((cx, cy))
            else: pins.append((cx, XO - PIN_R))                      # upper dot of : ; tops at the round x-height, like o
        if ch in ".:·!":
            # where the pin is the widest part of the glyph, it keeps the dot's side bearings:
            # widen by the pin's extra size on both sides (for ! the stem moves with it)
            grow = PIN_R - dots[0][2]
            rest = pathops.Path() if ch != "!" else xform(rest, e=grow)
            pins = [(x + grow, y) for x, y in pins]
            G[ch]["adv"] += round(2 * grow)
            if ch == "!":
                DOTSPEC[ch].update(only=False, adv0=G[ch]["adv"])
                DOTSPEC[ch]["pins"] = [[k, x + round(grow, 1), y, r0] for k, x, y, r0 in DOTSPEC[ch]["pins"]]
                # checklist 2026-09-27: the stem ended 76 above the pin (i and ? keep GAP 48) and the
                # glyph read looser than Quicksand's. Run the stem down to GAP above the pin and take
                # the extra white out of both side bearings.
                yb = bounds(rest)[1]; need = 2 * PIN_R - OSH + GAP
                if yb > need + 1:
                    cut = yb + 0.6 * S
                    a_, b_ = [iv for iv in slice_at(rest, cut)][0]
                    low = inter(rest, rect(-1e4, -1e4, 1e4, cut)); up = inter(rest, rect(-1e4, cut, 1e4, 1e4))
                    rest = union(union(up, xform(low, f=need - yb)), rect(a_, cut - (yb - need) - 1, b_, cut + 1)); rest.simplify()
                tight = round(8 * S / 120)
                rest = xform(rest, e=-tight); pins = [(x - tight, y) for x, y in pins]; G[ch]["adv"] -= 2 * tight
                DOTSPEC[ch]["adv0"] = G[ch]["adv"]
                DOTSPEC[ch]["pins"] = [[k, x - tight, y, r0] for k, x, y, r0 in DOTSPEC[ch]["pins"]]
        if ch == "?":
            # the larger pin grew up into the hook's tail (white 22 < the i gap 48): shorten the
            # tail so the white between them is the same GAP as on i
            yb = bounds(rest)[1]; need = 2 * PIN_R + GAP - OSH; _seams = []
            if yb < need:
                cut = yb + 0.5 * S + 30
                low = inter(rest, rect(-1e4, -1e4, 1e4, cut)); up = inter(rest, rect(-1e4, cut, 1e4, 1e4))
                rest = union(up, xform(low, f=need - yb)); rest.simplify()
                _seams.append((cut, cut + need - yb))                          # wcons: smoothed below
            # Quicksand's ? rises to the ascender (740), above ! and the capitals (700): bring the
            # hook down to the cap height by taking the difference out of the tail's straight part
            drop = bounds(rest)[3] - CAP
            if drop > 1:
                yb = bounds(rest)[1]
                mid = [(a + b) / 2 for a, b in slice_at(rest, yb + 0.6 * S)][0]
                ytop = yb + 0.6 * S
                while True:
                    iv = [iv for iv in slice_at(rest, ytop + 2) if iv[0] <= mid <= iv[1]]
                    if not iv or iv[0][1] - iv[0][0] > 1.2 * S: break
                    ytop += 2
                cut = (yb + 0.5 * S + ytop) / 2
                low = inter(rest, rect(-1e4, -1e4, 1e4, cut)); up = inter(rest, rect(-1e4, cut, 1e4, 1e4))
                rest = union(xform(up, f=-drop), low); rest.simplify()
                _seams.append((cut - drop, cut))                               # wcons: smoothed below
                QDROP = (round(drop), round(ytop - yb))
            if _seams:              # wcons: one smoothing over both seams, after both cuts (no step where the parts met)
                rest = smooth_seam(rest, min(a for a, _ in _seams), max(b for _, b in _seams))
    G[ch]["p"] = rest
    G[ch]["pins"] = [(round(x, 1), round(y, 1)) for x, y in pins]
MODS.append(["i j", "점 → 핀", f"주색 원, 반지름 {PIN_R:.1f} ({PIN_R/S:.3f}s), 세로획 윗끝과의 흰 틈 {I_GAP - I_OS:.0f} ({(I_GAP - I_OS)/S:.2f}s). 핀 윗끝 {PIN_CY + PIN_R:.0f} — 흰 틈은 어센더까지 남는 자리와 다른 핀들의 흰 틈 규칙(GAP {GAP:.0f}) 중 작은 쪽: 브랜드·굵은 쪽은 윗끝 = 어센더 {ASC} = l 윗끝, 가는 쪽은 틈을 지키고 점이 내려옴. 크기는 Quicksand 점 × {PIN_K:.3f}(700 위에서는 흰 틈이 0.2s까지 좁아지고 남는 만큼만), 흰 틈은 어센더까지 남는 자리"])   # wcons
if PIN_RULE == "lin" and S < 120:   # ==== lin 2026-09-27 · thin-end pin rule (see PIN_THIN) ====
    MODS.append(["핀 (700 아래)", "얇은 굵기 규칙", f"핀 지름 = {_pa:.4f} XH + {_pb:.3f} s = {2 * PIN_R:.1f} ({2 * PIN_R / S:.2f}s, {2 * PIN_R / XH:.3f} XH), 핀 옆 흰 틈 = {_g0:.4f} XH − {_g1:.3f} s = {GAP:.1f} — 700(r 78.5 · 틈 48)과 s 20(지름 {PIN_THIN}s · 틈 700의 {GAP_THIN}배)을 잇는 직선. 참고 서체 Thin의 점 2.05~2.64s"])
MODS.append([". : ; ! ? ·", "점 → 핀", "같은 크기의 핀. 기준선 위 점은 기준선에 서고, 윗점은 윗선을 지킴. 핀이 가장 넓은 . : · !는 핀 기준 옆 여백"])
MODS.append(["?", "꼬리를 짧게 · 대문자 높이로", "커진 핀과 꼬리 사이 흰 틈(22)을 i와 같은 0.4s로. 어센더(740)까지 솟던 갈고리를 ! · 대문자와 같은 700으로"])
MODS.append(["핀 오버슈트", "o처럼 넘침", f"핀은 둥근 글자라 o처럼 기준선 아래·x높이 위로 {OSH}씩 넘친다 — 기준선의 핀(. ! ? ;)은 바닥 −{OSH}, 콜론·세미콜론의 윗핀은 윗끝 {XO}"])

# 2b · punctuation & symbols as one system (tools/punct.py)
from punct import apply_punct, punct_kern
PUNCT_OUT = apply_punct(G, dict(S=S, XH=XH, XO=XO, CAP=CAP, ASC=ASC, DESC=DESC, PIN_R=PIN_R, GAP=GAP, OSH=OSH, Q_DOT_R=Q_DOT_R, DOTSPEC=DOTSPEC, OPT_PX=OPT_PX, UPM=UPM,
                                     PIN_CY=PIN_CY))   # wcons: the i pin centre (pin top on the ascender at every weight)
DOTSPEC.update(PUNCT_OUT["dotspec"]); MODS.extend(PUNCT_OUT["mods"])
# ==== lin 2026-09-27 · ellipsis pitch at the thin end ======================================================
# punct.py sets the … pitch to 3 PIN_R (white = r). With the thin-end pin that pulls the dots together as the
# weight drops (white 0.05 XH at 100), while the references hold the pitch near constant in x-heights from
# Thin to Bold (Quicksand 0.39 -> 0.37, M+ Rounded 0.71 -> 0.67, Lexend 0.44 -> 0.46) and their Thin white is
# 0.25-0.60 XH. Below 700 the pitch is held at its 700 value in XH (3 x 78.5 / 535 = 0.44 XH); at 700 and
# above punct.py's 3 PIN_R stands. The glyph widens by the extra pitch; DOTSPEC follows.
ELL_K = 3 * 78.5 / 535.0
if PIN_RULE == "lin" and S < 120 and "…" in G and len(G["…"]["pins"]) == 3:
    _ps = G["…"]["pins"]; _p0 = _ps[1][0] - _ps[0][0]; _p1 = max(_p0, ELL_K * XH)
    if _p1 > _p0 + 0.05:
        G["…"]["pins"] = [(round(_ps[0][0] + i * _p1, 1), _ps[i][1]) for i in range(3)]
        G["…"]["adv"] = round(G["…"]["adv"] + 2 * (_p1 - _p0))
        if "…" in DOTSPEC:
            DOTSPEC["…"]["adv0"] = G["…"]["adv"]
            DOTSPEC["…"]["pins"] = [[k, round(_ps[0][0] + i * _p1, 1), y, r0] for i, (k, x, y, r0) in enumerate(DOTSPEC["…"]["pins"])]
        MODS.append(["…", "얇은 굵기: 점 간격", f"핀이 작아져도 점 간격은 700과 같은 {ELL_K:.2f} XH ({_p1:.0f}, 3 PIN_R {_p0:.0f} 대신) — 참고 서체처럼 Thin에서도 점 사이가 열림"])
# ==== /lin ==================================================================================================

# comma heads are ink (user 2026-09-27: "콤마에 빨간색을 넣지 마"): the comma and everything built from it
# (‚ „ ‘ ’ “ ” and the lower half of ;) take their round head into the outline — it is no longer a pin,
# so it never takes the pin colour. The upper dot of ; stays a pin, like the colon's.
INK_HEADS = {",": "all", "‚": "all", "„": "all", "‘": "all", "’": "all", "“": "all", "”": "all", ";": "base"}
# The head is filled with a disc 1 unit inside the pin wherever the tail already draws the pin's rim.
# punct.comma_tail A sweeps from the pin's own circle and cuts a hole of R - 2 for the pin layer, so a disc
# of R is a second copy of the tail's rim, a few hundredths off it (pins are rounded to 0.1; ‘ “ are
# turned), and skia's union of two near-copies of one circle is unreliable: at opt28 100 it kept the disc
# and dropped the tail (‘ 79 tall instead of 200, the left mark of “ and the mark of ģ too). R - 1 still
# covers the hole and shares no edge with the tail. Commas B and C draw no rim; their head is the pin.
from punct import OPT as PUNCT_OPT
HEAD_R = PIN_R - 1 if PUNCT_OPT["comma"] == "A" else PIN_R
for ch, which in INK_HEADS.items():
    if ch not in G or not G[ch]["pins"]: continue
    spec = DOTSPEC.get(ch, {}).get("pins")
    keep, keep_spec = [], []
    for i, (x, y) in enumerate(G[ch]["pins"]):
        kind = spec[i][0] if spec and i < len(spec) else None
        if which == "all" or (which == "base" and (kind == "base" or (kind is None and y < XH / 2))):
            G[ch]["p"] = union(G[ch]["p"], circle(x, y, HEAD_R)); G[ch]["p"].simplify()
        else:
            keep.append((x, y))
            if spec and i < len(spec): keep_spec.append(spec[i])
    G[ch]["pins"] = keep
    if ch in DOTSPEC:
        if keep_spec: DOTSPEC[ch]["pins"] = keep_spec
        else: del DOTSPEC[ch]
MODS.append([", ; ‚ „ ‘ ’ “ ”", "쉼표 머리는 먹색", "쉼표와 쉼표에서 나온 글자의 둥근 머리는 핀이 아니라 글자의 일부 — 핀 색을 켜도 빨갛게 되지 않음. ;의 윗점은 콜론처럼 핀"])

# proof audit 2026-09-27 (proof.html, three reviewers setting real text): data in tools/proof_fixes.json
PROOF = json.loads((FSPath(__file__).resolve().parent / "proof_fixes.json").read_text())
def _xmap(p, fx):
    out = pathops.Path(); pen = out.getPen()
    m = lambda pt: (fx(pt[0], pt[1]), pt[1])
    for verb, pts in p.segments:
        if verb == "moveTo": pen.moveTo(m(pts[0]))
        elif verb == "lineTo": pen.lineTo(m(pts[0]))
        elif verb == "qCurveTo": pen.qCurveTo(*[m(q) if q is not None else None for q in pts])
        elif verb == "curveTo": pen.curveTo(*[m(q) for q in pts])
        elif verb == "closePath": pen.closePath()
        elif verb == "endPath": pen.endPath()
    return out
# f (A · I01): the hook reached so far right that the i pin after it needed +14 — "fi" read "f i". Pull
# the part right of the stem and above the bar in by 11.6 % (hook end 432 -> 412 at 700); fi needs no kern.
_fx0 = max(b for a, b in slice_at(G["f"]["p"], 0.3 * XH)); _fy0 = XH + 0.2 * S
G["f"]["p"] = _xmap(G["f"]["p"], lambda x, y: _fx0 + (x - _fx0) * 0.884 if x > _fx0 and y > _fy0 else x); G["f"]["p"].simplify()
MODS.append(["f", "갈고리 −11.6 %", "갈고리 끝이 멀리 나가 뒤의 i 핀을 밀어냈음(fi +14, \"f i\"로 읽힘) — 세로획 오른쪽·가로획 위 부분만 세로획 쪽으로 당김"])
# − (B · B05): U+2212 was missing, so "20 − 5" lost its sign. It is +'s horizontal bar alone.
if "+" in G:
    _pp = G["+"]["p"]; _px0 = bounds(_pp)[0]
    _bar = bounds(inter(_pp, rect(_px0 + 0.3 * S, -1e4, _px0 + 0.3 * S + 1, 1e4)))
    put("−", inter(_pp, rect(-1e4, _bar[1] - 0.05, 1e4, _bar[3] + 0.05)), adv=G["+"]["adv"])
    MODS.append(["−", "Quicksand에 없는 글자", "빼기 기호 — +의 가로 막대만"])

# i side bearings (checklist S1/S5, decided 2026-09-27): Quicksand's i (side bearings 58) was the
# tightest and darkest letter in text (density 1.061, references ≤ 1.008). Open both sides by IW;
# the pin clearance kerning below is measured afterwards, so it follows.
IW = round(6 * S / 120)
G["i"]["p"] = xform(G["i"]["p"], e=IW); G["i"]["pins"] = [(x + IW, y) for x, y in G["i"]["pins"]]; G["i"]["adv"] += 2 * IW
DOTSPEC["i"]["pins"] = [[k, round(x + IW, 1), y, r0] for k, x, y, r0 in DOTSPEC["i"]["pins"]]
DOTSPEC["i"]["adv0"] = G["i"]["adv"]
MODS.append(["i", f"옆 여백 +{IW}", "문장에서 가장 좁고 진한 글자였음(농도 1.061, 참고 ≤ 1.008) — 양쪽을 열고 핀 커닝은 그 뒤에 잰다"])

# 3 · feet — stems that stand on the baseline or hang to the descender end flat
PREFEET = {ch: g["p"] for ch, g in G.items()}          # for the playground's "round feet"
FEET = {}
for ch, g in G.items():
    p, added = flatten_feet(g["p"])
    if added:
        g["p"] = p; FEET[ch] = added
MODS.append(["세로획 발", "밑끝 평평", "혼자 끝나는 세로획이 기준선에 서거나 디센더로 내려갈 때만 네모. 다른 획과 만나는 이음부(N의 오른쪽 아래, L·E·B·D의 모서리)와 윗끝·사선 끝·곡선 끝은 Quicksand 그대로 둥글게"])

# 3b · crotches — where two strokes meet at an acute angle (v w V W A M N X K 4 …), the ink between
#     them piles up into a dark knot (up to 1.38 s where a stem is 1 s; audit 2026-09-27: w, W pop
#     out in text). Deepen each acute crotch along its own two edges and round its bottom, so the
#     ink across the joint is at most TRAP_T — the joint reads as two strokes meeting, not a blot.
TRAP_T = float(os.environ.get("LIMN_TRAP_T", 0)) * S      # off: traps read as stencil cuts (tried 2026-09-27)
TRAP_ANGLE = 80        # only crotches narrower than this (degrees) — right-angle T joins are left alone
TRAP_RUN = 2.0 * S     # the strokes thin gradually over this length from the crotch
TRAP_R = 0.25 * S      # radius of the new, round crotch
TRAP_MAX = 0.6 * S     # never deeper than this
# only between two straight edges (diagonals), and only at a vertex: the ink across the joint ends
# within 2.5 s (a bowl joining a stem, or K's arms meeting its stem, is a stroke running on)


def _corners(p, lens=False):
    """Concave corners of a path: (point, unit dir back along the incoming edge, unit dir along the
    outgoing edge, white wedge angle in degrees). Directions come from the segment tangents."""
    out = []
    # ink side: pathops keeps one orientation for the whole glyph (holes run the other way), so the
    # biggest contour's sign tells on which side of travel the ink lies for every contour
    big = max(p.contours, key=lambda c: abs(c.area)) if list(p.contours) else None
    ink_left = big is not None and big.clockwise is False
    for c in p.contours:
        segs = [s for s in c.segments]
        pts = []            # (point, incoming tangent, outgoing tangent)
        cur = None; first = None; last_t = None
        items = []
        for verb, args in segs:
            if verb == "moveTo":
                cur = args[0]; first = cur; continue
            if verb in ("closePath", "endPath"):
                continue
            if verb == "lineTo":
                q = args[0]; items.append((cur, q, (q[0] - cur[0], q[1] - cur[1]), (q[0] - cur[0], q[1] - cur[1]), "L")); cur = q
            elif verb == "qCurveTo":
                if args[-1] is None: cur = None; items = []; break      # all off-curve circle: no corners
                ctrl = list(args[:-1]); q = args[-1]
                t0 = (ctrl[0][0] - cur[0], ctrl[0][1] - cur[1]); t1 = (q[0] - ctrl[-1][0], q[1] - ctrl[-1][1])
                items.append((cur, q, t0, t1, "C")); cur = q
            elif verb == "curveTo":
                c1, c2, q = args
                items.append((cur, q, (c1[0] - cur[0], c1[1] - cur[1]), (q[0] - c2[0], q[1] - c2[1]), "C")); cur = q
        if not items: continue
        if first is not None and cur is not None and (abs(cur[0] - first[0]) > 1e-6 or abs(cur[1] - first[1]) > 1e-6):
            items.append((cur, first, (first[0] - cur[0], first[1] - cur[1]), (first[0] - cur[0], first[1] - cur[1]), "L"))
        # orientation (y up): positive area = counter-clockwise
        area = sum(it[0][0] * it[1][1] - it[1][0] * it[0][1] for it in items) / 2
        n = len(items)
        for i in range(n):
            a0, P, _, tin, kin = items[i]
            _, b1, tout, _, kout = items[(i + 1) % n]
            if kin != "L" or kout != "L": continue      # only where two straight strokes meet
            li, lo = math.hypot(*tin), math.hypot(*tout)
            if li < 1e-6 or lo < 1e-6: continue
            di = (tin[0] / li, tin[1] / li); do = (tout[0] / lo, tout[1] / lo)
            cross = di[0] * do[1] - di[1] * do[0]
            turn = math.degrees(math.atan2(cross, di[0] * do[0] + di[1] * do[1]))
            # a concave corner (reflex on the ink side) turns away from the ink
            if (ink_left and turn < -1) or (not ink_left and turn > 1):
                alpha = 180 - abs(turn)                  # white wedge angle
                out.append((P, (-di[0], -di[1]), do, alpha) + ((math.dist(a0, P), math.dist(P, b1)) if lens else ()))   # wcons: + edge (chord) lengths
    return out


def _ray_exit(p, P, d, start=2.0):
    """Distance along the ray P + t d (t > start) to where it leaves the ink."""
    best = None
    for pl in polylines(p, steps=16):
        n = len(pl)
        for i in range(n):
            (x0, y0), (x1, y1) = pl[i], pl[(i + 1) % n]
            ex, ey = x1 - x0, y1 - y0
            den = d[0] * ey - d[1] * ex
            if abs(den) < 1e-9: continue
            t = ((x0 - P[0]) * ey - (y0 - P[1]) * ex) / den
            u = ((x0 - P[0]) * d[1] - (y0 - P[1]) * d[0]) / den
            if t > start and 0 <= u <= 1 and (best is None or t < best): best = t
    return best


def open_crotches(p):
    """Rounded ink trap: the V between two strokes is made deeper by thinning both strokes gradually
    over TRAP_RUN from the crotch, and its new bottom is filleted with radius TRAP_R — so the white
    reaches TRAP_T from the outer edge of the joint and the crotch reads round, not as a notch."""
    done = []
    for P, u1, u2, alpha in _corners(p):
        if alpha >= TRAP_ANGLE: continue
        bx, by = u1[0] + u2[0], u1[1] + u2[1]; L = math.hypot(bx, by)
        if L < 1e-6: continue
        b = (bx / L, by / L)                             # into the white wedge
        dn = (-b[0], -b[1])                              # into the ink
        tv = _ray_exit(p, P, dn)
        if tv is None or tv <= TRAP_T or tv > 2.5 * S: continue
        depth = min(tv - TRAP_T, TRAP_MAX)
        E1 = (P[0] + u1[0] * TRAP_RUN, P[1] + u1[1] * TRAP_RUN)
        E2 = (P[0] + u2[0] * TRAP_RUN, P[1] + u2[1] * TRAP_RUN)
        # the sharp apex of the deeper V sits below the wanted white bottom by the fillet's rise
        Cp = (P[0] + dn[0] * depth, P[1] + dn[1] * depth)
        for _ in range(3):
            a1 = math.atan2(E1[1] - Cp[1], E1[0] - Cp[0]); a2 = math.atan2(E2[1] - Cp[1], E2[0] - Cp[0])
            hh = abs((a1 - a2 + math.pi) % (2 * math.pi) - math.pi) / 2
            rise = TRAP_R * (1 / math.sin(hh) - 1)
            Cp = (P[0] + dn[0] * (depth + rise), P[1] + dn[1] * (depth + rise))
        kite = pathops.Path(); kite.moveTo(*E1); kite.lineTo(*Cp); kite.lineTo(*E2); kite.lineTo(*P); kite.close()
        # fillet: give back the ink between the new edges' tangent points and the apex, below the circle
        dZ = TRAP_R / math.sin(hh)
        Z = (Cp[0] + b[0] * dZ, Cp[1] + b[1] * dZ)
        def foot(E):
            ex, ey = E[0] - Cp[0], E[1] - Cp[1]; l = math.hypot(ex, ey); ex, ey = ex / l, ey / l
            t = (Z[0] - Cp[0]) * ex + (Z[1] - Cp[1]) * ey
            return (Cp[0] + ex * t, Cp[1] + ey * t)
        F1, F2 = foot(E1), foot(E2)
        tip = pathops.Path(); tip.moveTo(*F1); tip.lineTo(*Cp); tip.lineTo(*F2); tip.close()
        p = union(diff(p, kite), diff(tip, circle(Z[0], Z[1], TRAP_R)))
        done.append((P, round(alpha), round(tv), round(depth)))
    return p, done


# 3b' · fillets (user 2026-09-27: "연결점은 원형으로", "둥근 귀여운 느낌"): every inner corner where two
#      straight strokes meet at less than FILLET_ANGLE gets a small round fillet of radius FILLET·s,
#      the same way every outer end is round — adds a little ink into the crotch instead of cutting it
FILLET = float(os.environ.get("LIMN_FILLET", 0.25))   # on, decided 2026-09-27
FILLET_ANGLE = 120
FILLETS = {}


def _edge_dist(p, q):
    """wcons: distance from point q to the outline of p."""
    best = 1e9
    for pl in polylines(p, steps=12):
        for i in range(len(pl)):
            (x0, y0), (x1, y1) = pl[i], pl[(i + 1) % len(pl)]
            vx, vy = x1 - x0, y1 - y0; L2 = vx * vx + vy * vy or 1e-9
            t = max(0.0, min(1.0, ((q[0] - x0) * vx + (q[1] - y0) * vy) / L2))
            best = min(best, math.hypot(q[0] - x0 - t * vx, q[1] - y0 - t * vy))
    return best


def fillet_corners(p, rad):
    done = 0
    rad0 = rad
    for P, u1, u2, alpha, li, lo in _corners(p, lens=True):
        if alpha >= FILLET_ANGLE: continue
        half = math.radians(alpha / 2)
        bx, by = u1[0] + u2[0], u1[1] + u2[1]; L = math.hypot(bx, by)
        if L < 1e-6: continue
        b = (bx / L, by / L)
        # ---- wcons 2026-09-27 ----------------------------------------------------------------------------
        # (a) a fillet needs its two edges: on a stair of tiny edges (n's widened arch at 800 leaves 0.5-unit
        #     steps) each step got a 30-unit fillet triangle that hung into the counter as a spike.
        # (b) above 700 the dilation sharpens every inner corner (its radius shrinks by the pen), so the
        #     fillet grows toward 0.25 s again (45 at 900) — but only as far as the white allows: its
        #     depth along the bisector stays within 0.3 of the white in front of it (4 A ¼ keep their counters,
        #     where 700's 30 would close them).
        rad = rad0
        if S > 120:
            tw = _ray_exit(p, P, b)
            if tw:
                rad = min(FILLET * S, 0.3 * tw / (1 / math.sin(half) - 1 + 1e-9))
        if min(li, lo) < 3 or alpha < 20:    # a stair step or a sliver (A at 300: 8°, t 142), not a crotch
            continue
        # (c) both tangent points must land on the outline: where an edge turns within the fillet's
        #     reach (A's legs under the bar at 300, a short piece of a different slope), the triangle
        #     stood off the edge and left a tooth hanging along the leg.
        _t = rad / math.tan(half)
        if min(li, lo) < _t - 0.5 and max(_edge_dist(p, (P[0] + u1[0] * _t, P[1] + u1[1] * _t)),
                                                         _edge_dist(p, (P[0] + u2[0] * _t, P[1] + u2[1] * _t))) > max(4.0, 0.35 * _t):
            continue
        # ---- /wcons ------------------------------------------------------------------------------------------
        t = rad / math.tan(half); dz = rad / math.sin(half)
        F1 = (P[0] + u1[0] * t, P[1] + u1[1] * t); F2 = (P[0] + u2[0] * t, P[1] + u2[1] * t)
        Z = (P[0] + b[0] * dz, P[1] + b[1] * dz)
        tri = pathops.Path(); tri.moveTo(*P); tri.lineTo(*F1); tri.lineTo(*F2); tri.close()
        p = union(p, diff(tri, circle(Z[0], Z[1], rad))); done += 1
    return p, done


if FILLET > 0:
    for ch, g in G.items():
        if ch == "림": continue
        p, n = fillet_corners(g["p"], FILLET * min(S, 120))   # radius stops growing past 700: at 900 (s 200) 0.25 s filled the counters of 4 and A
        if n: g["p"] = p; FILLETS[ch] = n

TRAPS = {}
if TRAP_T > 0:
    for ch, g in G.items():
        if ch == "림": continue
        p, done = open_crotches(g["p"])
        if done:
            g["p"] = p; TRAPS[ch] = done
    MODS.append(["예각 이음부", "골을 둥글게 파고듦", f"두 획이 {TRAP_ANGLE}°보다 좁게 만나는 골을 제 획을 따라 더 깊게 파고 바닥을 둥글게 — 이음부를 가로지르는 먹이 {TRAP_T/S:.2f}s를 넘지 않게 ({len(TRAPS)}자)"])

# 3c · size outliers (audit 2026-09-27: w, W, Q pop out in running text)
#   W: its diagonals are thicker than every other diagonal (median 127 vs 118–120) and it is the
#      widest capital (1.61 × the median); w is the widest lowercase (1.55 ×).
#   Q: Quicksand's wavy tail adds 32 % more ink than O and widens it.
# narrow w and W until their diagonals weigh what v and V weigh (measured median stroke:
# W 127 → 118 at 0.92, V 120; w 121 → 114 at 0.94, v 118) — which also takes them in from the edge
WX = {"W": 0.92, "w": 0.94} if os.environ.get("LIMN_WX") is None else {c: float(os.environ["LIMN_WX"]) for c in "wW"}
for ch in "wW":
    if WX[ch] != 1.0:
        WXc = WX[ch]
        g = G[ch]; bx0, _, bx1, _ = bounds(g["p"])
        g["p"] = xform(g["p"], WXc, 0, 0, 1, bx0 * (1 - WXc), 0)
        g["adv"] = round(g["adv"] - (bx1 - bx0) * (1 - WXc))
MODS.append(["w W", "가로 0.94 · 0.92", "사선 굵기를 v·V에 맞춤(W 127→118, V 120) — 가장 넓고 무거워 문장에서 튀던 두 글자"])
# ==== Q (LIMN_QTAIL) — redesign 2026-09-27, atq.html =================================================
#   orig   Quicksand's wavy tail
#   short  the earlier straight tail (round pen S from the bowl's estimated centre line at 5 o'clock):
#          at 800-900 its round start bulged into the counter, its joins were sharp notches and the
#          round pen made it heavier than the bowl it leaves
#   1      a straight tail that crosses the bowl: it starts inside the counter on purpose (by 0.9 S, never
#          more than 0.4 of the counter), leaves the bowl at 5 o'clock and ends with its ink bottom
#          on the comma line −0.24 XH
#   2      a short tail attached to the bowl: the same line, cut by the counter so nothing enters it,
#          ink bottom −0.15 XH (the earlier depth)
#   3      a tail on the baseline: it leaves the bowl's bottom right and lies on the overshoot line,
#          reaching past the bowl — nothing below the baseline
# 1-3 are drawn with the family's pen (the O's own stem and hairline, tools/punct.py pen_line) and
# joined round (round_joins, the fillet radius). The counter is O's, measured, not an estimate.
QTAIL = os.environ.get("LIMN_QTAIL", "2")
QTAIL_INFO = ""
if QTAIL in ("1", "2", "3"):
    from punct import atq_contrast, pen_line, round_joins
    O = G["O"]["p"]; ox0, oy0, ox1, oy1 = bounds(O)
    cx, cy, rx, ry = (ox0 + ox1) / 2, (oy0 + oy1) / 2, (ox1 - ox0) / 2, (oy1 - oy0) / 2
    QSV, QSH = atq_contrast(O)
    outer = max(O.contours, key=lambda c: abs(c.area)); O_fill = pathops.Path(); O_fill.addPath(outer); O_fill.simplify()
    counter = diff(O_fill, O)
    cb = bounds(counter); crx, cry = (cb[2] - cb[0]) / 2, (cb[3] - cb[1]) / 2
    def _on(ax, ay, t):                                # point of an ellipse centred on O at angle t (deg)
        return (cx + ax * math.cos(math.radians(t)), cy + ay * math.sin(math.radians(t)))
    mid_x, mid_y = (rx + crx) / 2, (ry + cry) / 2        # the bowl's centre line (between outer and counter)
    FR_Q = float(os.environ.get("LIMN_FILLET", 0.25)) * min(S, 120)
    if QTAIL in ("1", "2"):
        th = -50; Pc = _on(mid_x, mid_y, th); ang = math.radians(-54)
        dx, dy = math.cos(ang), math.sin(ang)
        bot = (-0.24 if QTAIL == "1" else -0.15) * XH
        L_out = (bot + QSH / 2 - Pc[1]) / dy          # ink bottom = the pen's lower edge
        P2 = (Pc[0] + dx * L_out, Pc[1] + dy * L_out)
        if QTAIL == "1":
            Pi = _on(crx, cry, th)                     # counter edge on the same ray
            e = min(0.9 * S, 0.4 * min(crx, cry))      # how far the tail reaches into the counter: a full
                                                       # stroke's length, so it reads as a crossing, not a knob
            back = math.hypot(Pc[0] - Pi[0], Pc[1] - Pi[1]) + e - QSV / 2
            P1 = (Pc[0] - dx * max(0.0, back), Pc[1] - dy * max(0.0, back))
            tail = pen_line([P1, P2], QSV, QSH)
        else:
            tail = diff(pen_line([Pc, P2], QSV, QSH), counter)
        adv_q = G["O"]["adv"] + round(0.1 * S)
    else:
        th = -64; Pc = _on(mid_x, mid_y, th)
        P2 = (ox1 + 0.02 * rx, -OSH + QSH / 2)          # its round end past the bowl, standing on the overshoot line
        tail = diff(pen_line([Pc, P2], QSV, QSH), counter)
        adv_q = G["O"]["adv"] + round(max(0.0, P2[0] + QSV / 2 - ox1) * 0.7)
    Q = round_joins(union(O, tail), FR_Q); Q.simplify()
    # the closing may nudge O by a hair; keep O exactly and take only what the tail adds
    G["Q"]["p"] = union(O, diff(Q, O)); G["Q"]["p"].simplify()
    # skia's difference can fail where Q's outline runs on O's own (at S 62.1 it returned the filled disc: Q
    # became a black dot, 2026-09-28); then take the joined Q as it is, a hair off O
    if abs(abs(G["Q"]["p"].area) - abs(Q.area)) > 0.01 * abs(Q.area):
        G["Q"]["p"] = Q
    G["Q"]["adv"] = adv_q
    QTAIL_INFO = f"꼬리 {QTAIL}: 끝 {P2[0] - ox1:+.0f}, 먹 밑끝 {bounds(G['Q']['p'])[1]:.0f}"
    MODS.append(["Q", {"1": "몸통을 가로지르는 곧은 꼬리", "2": "몸통에 붙은 짧은 꼬리", "3": "기준선 위 꼬리"}[QTAIL],
                 "O 그대로 + O의 펜(세로 획·가로 획 대비)으로 그린 곧은 꼬리, 이음은 둥글게 — 굵어져도 속공간으로 튀어나오지 않음. " + QTAIL_INFO])
# ==== end Q =========================================================================================
if QTAIL == "short":
    O = G["O"]["p"]; ox0, oy0, ox1, oy1 = bounds(O)
    cx, cy, rx, ry = (ox0 + ox1) / 2, (oy0 + oy1) / 2, (ox1 - ox0) / 2, (oy1 - oy0) / 2
    # start on the bowl's own centre line at five o'clock, so the tail's round end hides inside the
    # stroke instead of sitting in the counter, and run outward and down past the baseline
    th, rcx, rcy = math.radians(-50), rx - S / 2, ry - S / 2
    P1 = (cx + rcx * math.cos(th), cy + rcy * math.sin(th)); ang = math.radians(-52)
    P2 = (P1[0] + math.cos(ang) * 0.5 * ry, P1[1] + math.sin(ang) * 0.5 * ry)
    tail = pathops.Path()
    tail.moveTo(*P1); tail.lineTo(*P2)
    tail.stroke(S, pathops.LineCap.ROUND_CAP, pathops.LineJoin.ROUND_JOIN, 4); tail.convertConicsToQuads(); tail.simplify()
    G["Q"]["p"] = union(O, tail); G["Q"]["p"].simplify()
    G["Q"]["adv"] = G["O"]["adv"] + round(0.1 * S)   # the tail reaches the next letter at the baseline (Qa 0.98 vs refs ≥ 1.02)
    MODS.append(["Q", "짧은 곧은 꼬리", "Quicksand의 물결 꼬리는 O보다 먹이 32% 많고 디센더 끝까지 내려가 튀었음 — O의 5시 방향 획에서 나오는 같은 굵기·둥근 끝의 짧은 사선 꼬리(먹 +9%)"])
# + and = share the maths axis (checklist S6: Quicksand's + sits 10 above =)
if "+" in G and "=" in G:
    _pb, _eb = bounds(G["+"]["p"]), bounds(G["="]["p"])
    _dy = (_eb[1] + _eb[3]) / 2 - (_pb[1] + _pb[3]) / 2
    if abs(_dy) > 1: G["+"]["p"] = xform(G["+"]["p"], f=_dy)

# 3d · symmetry (user 2026-09-27: "Z가 좌우 대칭이 안 맞는 불안한 느낌"). Quicksand draws several
#     symmetric letters slightly off (mirror IoU Y 0.91, x 0.92, v 0.93 …; Z's bottom bar runs
#     further right than its top bar runs left). Rebuild each from one half: mirror letters from the
#     heavier half (checklist 2026-09-27: "closer to the original area" is always a tie, since both
#     candidates differ from L+R by |L-R|, and float noise picked the lighter half — v lost 3.6% ink),
#     Z z from the bottom half turned 180°. w W joined after their 0.94/0.92 narrowing (IoU 0.98).
SYM_MIRROR, SYM_POINT = "vVwWxXYAMU", "Zz"
SYM = {}
for ch in SYM_MIRROR + SYM_POINT:
    p = G[ch]["p"]; x0, y0, x1, y1 = bounds(p); cx, cy = (x0 + x1) / 2, (y0 + y1) / 2; big = 1e4
    if ch in SYM_MIRROR:
        cands = []
        for keep in (rect(-big, -big, cx + 0.5, big), rect(cx - 0.5, -big, big, big)):
            h = inter(p, keep); q = union(h, xform(h, -1, 0, 0, 1, 2 * cx, 0)); q.simplify(); cands.append(q)
    else:
        h = inter(p, rect(-big, -big, big, cy + 0.5))
        q = union(h, xform(h, -1, 0, 0, -1, 2 * cx, 2 * cy)); q.simplify(); cands = [q]
    best = max(cands, key=lambda q: abs(q.area))
    G[ch]["p"] = best; SYM[ch] = round(abs(best.area) / abs(p.area), 3)
MODS.append(["v V w W x X Y A M U · Z z", "대칭으로", "좌우대칭 글자는 한쪽 반을 뒤집어 붙이고(먹이 많은 쪽 — 가벼운 반을 고르면 v가 3.6% 옅어짐), Z·z는 아래 반을 180° 돌려 — Quicksand의 작은 어긋남(대칭 일치율 0.91~0.96)을 없앰"])

# 4 · 림 — NanumSquareRound's own 림 at this weight, paired with the Latin exactly as the Hangul is (tools/hangul.py:
#     master, pen, scale, baseline, tracking), with its ㅣ turned into an i (user 2026-09-28): the pin's diameter
#     and the stem's width are the ㅣ's own width, the white between them 0.35 of it, the pin top on the ㅣ's top
#     and the stem down to the ㅣ's foot. The pin is not in the outline: the engine draws it (vermilion in the
#     logo, ink in text). This replaces the 림 constructed here before (2026-09-27).
import hangul as _hangul
_rp, _radv, (_rx, _ry, _rr), _rinfo = _hangul.rim(WGHT, latin_white=(I_GAP - I_OS) / (2 * PIN_R))
G["림"] = {"p": xform(_rp, 1, 0, 0, -1), "adv": round(_radv), "pins": [(round(_rx, 1), round(-_ry, 1))], "pinr": round(_rr, 2)}
_hp = _hangul.params(WGHT)
_hpen = f" 펜 {_hp['delta']:+.1f}" if _hp["delta"] else ""
MODS.append(["림", "나눔스퀘어라운드의 림", f"한글과 같은 짝({_hp['master']}{_hpen} · k {_hp['k']:.4f} · dy {_hp['dy']:+.1f}), ㅣ를 i로: 핀 지름 = 줄기 = ㅣ 굵기 {_rinfo['w']:.0f}, 틈 {_rinfo['gap']:.0f}(브랜드 0.35 × 굵기, 가는 쪽은 라틴 i처럼 점 지름에 비례), 줄기 윗끝 고정, 줄기 끝 = ㅣ 끝"])
import greek; greek.build(globals())   # Greek (tools/greek.py): shapes from the final letters now; spacing, tonos, kcls after accents.build

# ==== spacing · Tracy classes (2026-09-27, tools/spacing.json, spacing.html) =============================
# Every side of a-z and A-Z is set from its shape class: side = ratio x o's side (O for capitals), both read as
# the nearest ink inside the x-height (cap-height) band. o and O keep Quicksand's sides and are the unit, so
# the system follows the family's own spacing at every weight. This replaces what accumulated before it
# (n m r left -8, i +6, the proof audit's 14 side-bearing deltas): those were fitted with an area model that
# counted open white (s c e apertures) wrongly and were scaled as fixed deltas, which Quicksand's own
# masters do not follow (its s left is 0.62 o at 700 but 0.87 o at 400, so +12 at 700 became a 58-unit s
# at 400 — the loose s the user saw). The code above still runs; this block measures after it and sets the
# final sides.
SPC = json.loads((FSPath(__file__).resolve().parent / "spacing.json").read_text())
_obb = bounds(G["o"]["p"]); _sbk = (_obb[0] + G["o"]["adv"] - _obb[2]) / 80.0   # o's sides / 80 (also used by pkern below)
SPC_K = 1 + SPC["contrast"] * max(-1.0, min(1.0, (S - 120) / 60))   # straight:round contrast grows with the weight


def _near(p, side, y0, y1, adv):
    """nearest ink to the left edge (side L) or to the advance (side R) on scanlines y0+1, y0+3, ... < y1"""
    polys = polylines(p, steps=16); best = None
    for y in range(int(y0) + 1, int(y1), 2):
        xs = []
        for poly in polys:
            n = len(poly)
            for i in range(n):
                (xa, ya), (xb, yb) = poly[i], poly[(i + 1) % n]
                if (ya <= y < yb) or (yb <= y < ya):
                    xs.append(xa + (y - ya) * (xb - xa) / (yb - ya))
        if not xs: continue
        v = min(xs) if side == "L" else adv - max(xs)
        best = v if best is None else min(best, v)
    return best


def _shift(ch, dl, dr):
    G[ch]["p"] = xform(G[ch]["p"], e=dl); G[ch]["pins"] = [(x + dl, y) for x, y in G[ch]["pins"]]; G[ch]["adv"] += dl + dr
    if ch in PREFEET: PREFEET[ch] = xform(PREFEET[ch], e=dl)
    if ch in FEET: FEET[ch] = [round(x + dl) for x in FEET[ch]]
    if ch in DOTSPEC:
        DOTSPEC[ch]["pins"] = [[k, round(x + dl, 1), y, r0] for k, x, y, r0 in DOTSPEC[ch]["pins"]]; DOTSPEC[ch]["adv0"] = G[ch]["adv"]


SPACING = {}                                # side -> [class, before, after] (units, this weight)
for _grp, _top in (("lc", XH), ("uc", CAP)):
    _spec = SPC[_grp]; _a = _spec["anchor"]
    _unit = (_near(G[_a]["p"], "L", 0, _top, G[_a]["adv"]) + _near(G[_a]["p"], "R", 0, _top, G[_a]["adv"])) / 2
    if _grp == "lc": _unit_lc = _unit
    _d = {}
    for _cls, (_r, _sides, _why) in _spec["classes"].items():
        if isinstance(_r, list):             # [at 700, at 400]: a side whose parent shape changes with the weight
            _r = _r[1] + (_r[0] - _r[1]) * max(0.0, min(1.0, (S - 60) / 60))
        _rr = _r if _cls == "round" else _r * SPC_K
        for _s in _sides.split():
            _ch, _sd = _s[:-1], _s[-1]
            if _ch not in G or _ch == _a: continue
            _cur = _near(G[_ch]["p"], _sd, 0, _top, G[_ch]["adv"])
            _d.setdefault(_ch, [0, 0])[0 if _sd == "L" else 1] = round(_rr * _unit - _cur)
            SPACING[_s] = [_cls, round(_cur, 1), round(_rr * _unit, 1)]
    for _ch, (_dl, _dr) in _d.items():
        _shift(_ch, _dl, _dr)
SPC_UNIT = round(_sbk * SPC_K, 3)          # kern exceptions scale like the spacing
if os.environ.get("LIMN_SPACING_OUT"):     # the table as built at this weight, for spacing.html
    FSPath(os.environ["LIMN_SPACING_OUT"]).write_text(json.dumps({"w": WGHT, "k": SPC_K, "unit": SPC_UNIT, "sides": SPACING}))
# the earlier spacing notes are superseded by the classes (their code still runs; the classes set the result)
MODS[:] = [m for m in MODS if not (m[0] in ("n m r", "i") and "여백" in m[1])]
MODS.append(["a–z A–Z", "옆 여백 = 모양 부류 × o의 옆 여백",
             f"Walter Tracy의 방법: 곧은 줄기 {SPC['lc']['classes']['straight'][0]:.2f}, 아치(n u) {SPC['lc']['classes']['arch'][0]:.2f}, "
             f"둥근 획 1.00(o), s {SPACING['sL'][2] / _unit_lc:.2f}·{SPACING['sR'][2] / _unit_lc:.2f}(이 굵기) … "
             f"대문자 곧은 줄기 {SPC['uc']['classes']['straight'][0]:.2f} × O. 전문 서체 14종의 간격에 맞춘 값, 굵을수록 곧은 쪽이 조금 더 넓음(× {SPC_K:.3f}) — spacing.html"])
# ==== /spacing =====================================================================================

# tabular figures (decided 2026-09-27): limn's UI counts lines and pins, so the figures are tabular by
# default — every figure on one width TN (widest figure ink + 0.4 s, 601 at 700), ink centred. The
# proportional widths stay in "pnum" for the playground; figures do not kern.
# proof audit 2026-09-27 (C-04): "+ 0.4 s" is 48 at 700 but 7 at 100 (00 ink 6 apart — figures touch
# at 12-16 px) and 80 at 900 (figures looser than letters). Keep 48 at 700 and scale it with the
# family's own spacing instead of the stem: o's side bearings (80 at 700, 110 at 100, 56 at 900).
_ob = bounds(G["o"]["p"]); O_SB = _ob[0] + G["o"]["adv"] - _ob[2]
TN_WHITE = 0.4 * 120 * O_SB / 80.0
# (B01, B02): centred in a tabular cell the parent's 1 left 158 of white on each side ("1 1 8", ". 12"),
# and the cell was as wide as 4, the widest figure. The tabular 1 gets a round-ended foot bar
# (0.571 cap long, one stem thick) and 4 is narrowed to 0.95 with its stems kept; the proportional 1
# keeps the parent's shape (pglyph, used when figures are proportional).
PGLYPH = {"1": {"p": G["1"]["p"], "adv": G["1"]["adv"]}}
_c1 = FEET["1"][0] if FEET.get("1") else (lambda iv: (iv[0] + iv[1]) / 2)(max(slice_at(G["1"]["p"], 0.3 * CAP), key=lambda iv: iv[1] - iv[0]))
_L1 = 0.571 * CAP; _foot = pathops.Path(); _foot.moveTo(_c1 - _L1 / 2 + S / 2, S / 2); _foot.lineTo(_c1 + _L1 / 2 - S / 2, S / 2)
_foot.stroke(S, pathops.LineCap.ROUND_CAP, pathops.LineJoin.ROUND_JOIN, 4); _foot.convertConicsToQuads()
if os.environ.get("LIMN_ONE_FOOT") == "1":   # off (user 2026-09-27: "없는 게 더 이뻐보이는데"); the footed 1 stays an option
    G["1"]["p"] = union(G["1"]["p"], _foot); G["1"]["p"].simplify()
_4b = bounds(G["4"]["p"]); G["4"]["p"] = narrow(G["4"]["p"], 0.95); _4n = bounds(G["4"]["p"])
G["4"]["adv"] -= round((_4b[2] - _4b[0]) - (_4n[2] - _4n[0])); PREFEET["4"] = narrow(PREFEET["4"], 0.95)
if FEET.get("4"): FEET["4"] = [round(_4b[0] + (x - _4b[0]) * (_4n[2] - _4n[0]) / (_4b[2] - _4b[0])) for x in FEET["4"]]
TN = round(max(bounds(G[d]["p"])[2] - bounds(G[d]["p"])[0] for d in DIGITS) + TN_WHITE)
PNUM = {}
for d in DIGITS:
    x0, _, x1, _ = bounds(G[d]["p"]); dx = round((TN - (x1 - x0)) / 2 - x0, 1)
    PNUM[d] = [G[d]["adv"], dx]
    G[d]["p"] = xform(G[d]["p"], e=dx); G[d]["pins"] = [(x + dx, y) for x, y in G[d]["pins"]]; G[d]["adv"] = TN
    PREFEET[d] = xform(PREFEET[d], e=dx)
    if d in FEET: FEET[d] = [round(x + dx) for x in FEET[d]]
MODS.append(["0–9", f"고정폭 {TN}", "줄 번호·핀 개수처럼 자릿수가 바뀌는 숫자가 흔들리지 않게 모든 숫자를 한 폭에, 잉크를 가운데로. 비례 폭은 조절 패널의 '비례'로"])

# ---- SYM hook 2026-09-27 (tools/punct.py apply_sym_late): superiors, fractions, © ® ™ °, € ¥ ¢ are built
#      from the final letters and figures, so they come after feet, fillets, symmetry and the tabular figures
from punct import apply_sym_late
MODS.extend(apply_sym_late(G))
from punct import apply_sym_new          # sweep 2026-09-28: ¤ ₩ № ′ ″ ⁄ ‒ on the same classes
MODS.extend(apply_sym_new(G))
from sym_numeric import apply_sym_numeric; MODS.extend(apply_sym_numeric(G, globals()))   # 2026-09-29: superiors, inferiors, fractions, Roman numerals, letterlike, currency
# ---- /SYM hook

# 3e · accented letters (tools/accents.py): limn's final base letters + marks drawn to the limn rules
import accents
# ==== lin 2026-09-27 · stroke fallback for accents.py ====================================================
# accents.cedilla() starts its arc on the stem's own end point, so the polyline carries a zero-length step;
# skia's simplify then fails for some anchors (Ţ at curve A 900, S 153) and the glyph is left out. Only when
# simplify fails: drop near-duplicate points and stroke again. A build that never fails is unchanged.
_acc_stroke = accents._stroke
def _acc_stroke_safe(segs, w):
    try:
        return _acc_stroke(segs, w)
    except pathops.PathOpsError:
        def _dedup(s):
            if s[0] == "c": return s
            out = [s[0]]
            for q in s[1:]:
                if math.hypot(q[0] - out[-1][0], q[1] - out[-1][1]) > 0.01: out.append(q)
            return out
        segs = [_dedup(s) for s in segs]
        for e in (0.0, 0.011, -0.023, 0.037, 0.29):          # then a hair's shift, taken back out
            mv = lambda q: (q[0] + e, q[1] + 0.7 * e)
            try:
                p = _acc_stroke([s if s[0] == "c" else [mv(q) for q in s] for s in segs], w)
                return p.transform(1, 0, 0, 1, -e, -0.7 * e) if e else p
            except pathops.PathOpsError:
                continue
        raise
accents._stroke = _acc_stroke_safe
# ==== /lin ==================================================================================================
accents.build(globals())
# maths, arrows, punctuation, keyboard (tools/sym_math.py): built from the final letters and punctuation, before the
# kerning, so the clearance passes (punct_kern, accents.kern) measure them like every other glyph
import sym_math; MODS.extend(sym_math.build(globals()))
_tick("glyphs built")

# ---------------------------------------------------------------- kerning (Quicksand GPOS, via HarfBuzz)
blob = hb.Blob.from_file_path(SRC)
hbf = hb.Font(hb.Face(blob)); hbf.set_variations({"wght": WGHT})


def adv_of(text, kern=True):
    buf = hb.Buffer(); buf.add_str(text); buf.guess_segment_properties()
    hb.shape(hbf, buf, {"kern": kern, "liga": False, "calt": False})
    return sum(p.x_advance for p in buf.glyph_positions)


KERN = {}
ks = [c for c in LOWER + UPPER + DIGITS + ".,:;!?-/'\"()" if c in G]
single = {c: adv_of(c) for c in ks}
for a in ks:
    for b in ks:
        v = adv_of(a + b) - single[a] - single[b]
        if v: KERN[a + b] = v

# checklist audit 2026-09-27 (S3): Quicksand's kerning was made for its spurred n and v-shaped y.
# Deltas measured at 700 against the parent's pair white and six OFL references, applied at every
# weight: overhangs over the spurless shoulder close up, period/comma after diagonals and r get
# kerned, y is kerned as the u it is, and r v · r w · f ) stop over-opening.
# sweep 2026-09-28: rn rm rr rv rw left this table for spacing.json "set". Scaled with the stem (S / 120), the
# r|stem -30 grew 7x from 100 to 900 while the white it closes shrinks: rn read toward m at 800-900 (-18 % / -20 % of
# the letter white, area measure) and was right only at 100. rv rw carried Quicksand's constant +50 against a delta
# that scaled, so rv stood +19 % open at 100 and +2 % at 900.
KERN_FIX = {"fn": -25, "fm": -25, "fr": -25, "Yn": -17, "Ym": -17, "Yr": -17,
            "Vn": -17, "Vm": -17, "Vr": -17, "vn": -16, "vm": -16, "vr": -16, "wn": -10, "wm": -10, "wr": -10,
            "Pn": -12, "Pm": -12, "Pr": -12,
            "r.": 30, "r,": -60, "T.": 15, "T,": -85, "V.": -80, "V,": -80, "W.": -55, "W,": -55, "Y.": -55,
            "Y,": -55, "v.": -75, "v,": -75, "w.": -60, "w,": -60, "F.": -45, "F,": -45,
            "Ty": -90, "Ay": 15, "Ky": 8, "Ly": 17, "Xy": 14, "yA": 15, "yT": -20, "yX": 10,
            "f)": 40}
for pr, dv in KERN_FIX.items():
    v = KERN.get(pr, 0) + round(dv * S / 120)          # measured at 700; 400 needed about half (proof A · I15)
    if v: KERN[pr] = v
    else: KERN.pop(pr, None)
import punct as _punct; _punct.ST["parent_kerned"] = set(ks)
_punct.ST["classed"] = {c for c, (a, b) in accents.ST["cls"].items() if a and b}   # ß Þ ẞ: the parent's own pairs, measured too
_tick("parent kerning"); punct_kern(KERN, G); _tick("punct_kern")                     # tools/punct.py: , ; take . : pairs; rebuilt glyphs keep GAP white
# ==== sweep 2026-09-28 · j kerns at least as its dotless ȷ ============================================
# j is ȷ with a pin (accents.py builds ȷ from j's own outline), and a pin only ever needs more room. punct_kern
# measured the rebuilt ( [ { ¿ ¡ … against both, but held each pair to the parent's own white where the parent had
# the pair: Quicksand sets (j with the hook under the parenthesis, so (j kept 0 while (ȷ, which the parent lacks,
# was opened to GAP (+60 … +68). At 700-900 the dilated hook ran into ( [ { (overlap 0.04-0.10 S). So every pair of
# ȷ is a floor for the same pair of j, on both sides; ĵ has its own pairs (punct_kern measures it as a new glyph)
# and kerns as j where it has none (kcls).
JFLOOR = {}
for _pr, _v in list(KERN.items()):
    if len(_pr) != 2 or "ȷ" not in _pr: continue
    _jp = _pr.replace("ȷ", "j")
    if _v > KERN.get(_jp, 0):
        JFLOOR[_jp] = [KERN.get(_jp, 0), _v]; KERN[_jp] = _v
# ==== /sweep
for pr, dv in PROOF["kern"].items():     # proof audit: 152 pairs set by running text, deltas at 700
    if pr[0] in G and pr[1] in G:
        v = KERN.get(pr, 0) + round(dv * S / 120)
        if v: KERN[pr] = v
        else: KERN.pop(pr, None)
# ==== spacing · kerning exceptions (tools/spacing.json "kern") — pairs still uneven after the classes =====
for pr, dv in SPC["kern"].items():
    if pr[0] in G and pr[1] in G:
        v = KERN.get(pr, 0) + round(dv * SPC_UNIT)
        if v: KERN[pr] = v
        else: KERN.pop(pr, None)
# ==== /spacing =====================================================================================
# ==== small-glyphs 2026-09-28 · held pairs (tools/spacing.json "hold") ===============================
# The exceptions above are deltas on Quicksand's kerning, which was made for Quicksand's own sides. Where
# that kerning moves across the weights unlike the classes, no fixed delta can follow it: Quicksand kerns
# LT -100 at 700 but -59 at 400, so after the classes LT stood 4.4 O-sides apart at 400 against 3.6 at 700
# (HH: 3.7 and 3.9) and read open in LATTE, SALT, HALT. A held pair is kerned to the white it has at 700
# instead — the nearest ink-to-ink white across the pair, scaled with the spacing unit like every other
# exception — so 700 stays as it is by construction and the other weights keep its proportion.
def _pair_white(a, b, k):
    """Nearest horizontal white between the inks of a and b set with kerning k (rows 2 units apart,
    where both have ink; pins are not counted)."""
    pa, pb = polylines(G[a]["p"], steps=16), polylines(G[b]["p"], steps=16)

    def xs_at(polys, y):
        xs = []
        for poly in polys:
            for i in range(len(poly)):
                (x0, y0), (x1, y1) = poly[i], poly[(i + 1) % len(poly)]
                if (y0 <= y < y1) or (y1 <= y < y0):
                    xs.append(x0 + (y - y0) * (x1 - x0) / (y1 - y0))
        return xs
    ba, bb = bounds(G[a]["p"]), bounds(G[b]["p"]); dx = G[a]["adv"] + k; best = None
    for y in range(int(max(ba[1], bb[1])) + 1, int(min(ba[3], bb[3])), 2):
        xa, xb = xs_at(pa, y), xs_at(pb, y)
        if xa and xb:
            v = min(xb) + dx - max(xa)
            best = v if best is None else min(best, v)
    return best


HOLD = {}                                   # pair -> [kerning before, after]
for pr, white in SPC.get("hold", {}).items():
    if pr.startswith("_") or pr[0] not in G or pr[1] not in G: continue
    k0 = KERN.get(pr, 0); w0 = _pair_white(pr[0], pr[1], k0)
    if w0 is None: continue
    v = k0 + round(white * SPC_UNIT - w0)
    if v: KERN[pr] = v
    else: KERN.pop(pr, None)
    HOLD[pr] = [k0, v]
if HOLD:
    MODS.append([" ".join(HOLD), "짝의 흰 폭을 700에 고정", "Quicksand의 커닝이 굵기에 따라 부류 옆 여백과 다르게 움직이는 짝(LT: 700 −100, 400 −59)은 700에서의 잉크 사이 흰 폭을 옆 여백 단위로 모든 굵기에 — "
                 + ", ".join(f"{pr} {a}→{b}" for pr, (a, b) in HOLD.items())])
# ==== /small-glyphs ================================================================================
# ==== sweep 2026-09-28 · pairs set outright (tools/spacing.json "set") ================================
# A pair's kerning is the value at 700 times the spacing unit, whatever the parent, KERN_FIX and the exceptions
# gave: for pairs whose parent kerning is constant across the weights (Quicksand's g|round -20, du +16, rv rw +50)
# or whose fix scaled with the stem (r|stem), neither follows the white, which the spacing unit does (Eref / unit
# is 143-148 from 100 to 900 on the sweep's area measure). Measured before: gd gq gc go -8 % … -12 %, du +8 … +12 %,
# rv +19 % (100) … +2 % (900), rn rm rr -1 % (100) … -20 % (900) of the letter white off their group's median.
SETK = {}
for pr, v in SPC.get("set", {}).items():
    if pr.startswith("_") or pr[0] not in G or pr[1] not in G: continue
    k0, k1 = KERN.get(pr, 0), round(v * SPC_UNIT)
    if k1: KERN[pr] = k1
    else: KERN.pop(pr, None)
    SETK[pr] = [k0, k1]
if SETK:
    MODS.append([" ".join(SETK), "짝 커닝을 흰 폭 단위로", "부모 커닝이 굵기에 상관없이 같거나(g|둥근 −20, du +16, rv rw +50) 획 굵기로 늘던(r|줄기 −30 × S/120) 짝은 700 값 × 옆 여백 단위로 새로 — "
                 + ", ".join(f"{pr} {a}→{b}" for pr, (a, b) in SETK.items())])
# ==== sweep 2026-09-28 · bars in line (tools/spacing.json "bars") =====================================
# Where two bars meet end to end at one height — r's arm and the bars of f t z at the x-height, T F E Z L and T Z at
# the cap height and on the baseline — nothing but the kerning keeps the two apart, and the dilated bars of 800-900
# came within 0.10-0.16 S (rt rf TT ff ft FT): read at text sizes they fuse into one stroke. Such a pair keeps its
# inks at least clear x S apart (exact outline distance, GEOS); a closer pair opens by the shortfall. At the light
# weights the bars end well apart and nothing changes.
BARS = SPC.get("bars", {})
BAR_CLEAR = BARS.get("clear", 0) * S
BAROPEN = {}
if BAR_CLEAR > 0:
    from shapely import affinity as _saff
    _bgeo = {}

    def _bink(ch):
        if ch not in _bgeo: _bgeo[ch] = _hangul.to_geom(G[ch]["p"])
        return _bgeo[ch]
    for _grp in ("lc", "uc"):
        for _a in BARS[_grp]["right"].split():
            for _b in BARS[_grp]["left"].split():
                if _a not in G or _b not in G: continue
                k0 = k = KERN.get(_a + _b, 0)
                for _ in range(6):
                    d = _bink(_a).distance(_saff.translate(_bink(_b), G[_a]["adv"] + k))
                    if d >= BAR_CLEAR - 0.05: break
                    k += max(1, math.ceil(BAR_CLEAR - d))
                if k != k0:
                    KERN[_a + _b] = k; BAROPEN[_a + _b] = [k0, k]
if BAROPEN:
    MODS.append([" ".join(BAROPEN), "나란한 막대", f"같은 높이에서 끝과 끝이 만나는 막대(r의 팔·f t z의 막대, T F E Z L·T Z) 짝은 잉크 사이 {BARS['clear']:g} S({BAR_CLEAR:.0f}) 이상 — "
                 + ", ".join(f"{pr} {a}→{b}" for pr, (a, b) in BAROPEN.items())])
# ==== /sweep ========================================================================================
PKERN = {pr: round(v * S / 120) for pr, v in PROOF["pkern"].items()}   # proportional figures only (B03)
MODS.append([f"{len(PROOF['kern'])}쌍", "커닝 보정(교정쇄)", "문장으로 써 보고 잰 값: 대시·괄호·마침표 짝 — 700에서 잰 차이를 획 굵기에 비례해 모든 굵기에. 글자끼리의 짝은 옆 여백 체계와 그 예외 커닝(spacing.json)으로 옮김"])   # spacing 2026-09-27
MODS.append([f"{len(SPC['kern'])}쌍", "예외 커닝(옆 여백 체계 뒤)", "부류 옆 여백으로 고르게 되지 않는 짝만 — f의 걸침(ff ft fo), r·T·V·Y·L·A의 열린 쪽 등. 700에서 잰 값을 o의 옆 여백 비례로 모든 굵기에"])   # spacing 2026-09-27
for pr in [k for k in KERN if k[0] in DIGITS or k[1] in DIGITS]:
    del KERN[pr]                                       # tabular figures do not kern
# ... except against the quotes and primes after them (5' 12" 5′ 11″): the quotes stand on the i pin's line, low enough
# for a figure's top to meet them, and a figure's side is its tabular cell (−40 to −67 units against the references at
# every weight). FIG_QUOTE at 700, by the spacing unit, like the other exceptions
FIG_QUOTE = {"'": 43, '"': 43, "’": 43, "”": 43, "′": 45, "″": 45}
for _d in DIGITS:
    for _q, _v in FIG_QUOTE.items():
        if _q in G: KERN[_d + _q] = round(_v * SPC_UNIT)
MODS.append(["0–9 + ' \" ’ ” ′ ″", "숫자 뒤 따옴표", "고정폭 숫자는 커닝하지 않지만, 숫자 뒤의 따옴표·프라임은 숫자 윗부분과 같은 높이에 서므로 700에서 +43(′ ″ +45)을 옆 여백 단위로 — 5' 12\" 5′ 11″"])
# ¹⁄₂: the fraction slash sets a superior figure before it and an inferior one after it as ½ does — the fraction's white
# WS between each figure and the slash (its own side bearings left ¹⁄₂ 44-88 units wider than ½)
from punct import sym_white as _sw, ST as _PST2
import geom as _geom
from shapely import affinity as _aff
if "⁄" in G:
    _WS = _sw(_PST2["M"]); _sl = _geom.shape(G["⁄"]["p"]); FRACK = {}
    for _a in "⁰¹²³⁴⁵⁶⁷⁸⁹₀₁₂₃₄₅₆₇₈₉":
        if _a not in G: continue
        _g = _geom.shape(G[_a]["p"]); _left = _a in "⁰¹²³⁴⁵⁶⁷⁸⁹"
        _pr = _a + "⁄" if _left else "⁄" + _a
        _k = KERN.get(_pr, 0)
        for _ in range(6):
            _d = (_g.distance(_aff.translate(_sl, G[_a]["adv"] + _k, 0)) if _left
                  else _sl.distance(_aff.translate(_g, G["⁄"]["adv"] + _k, 0)))
            if abs(_d - _WS) < 0.5: break
            _k += round((_WS - _d) / 0.9)
        if _k: KERN[_pr] = _k; FRACK[_pr] = _k
    MODS.append(["¹⁄₂", "분수 빗금 짜기", f"⁄ 앞의 위첨자 숫자, 뒤의 아래첨자 숫자는 ½처럼 빗금과 흰 틈 WS {_WS:.0f} — " + ", ".join(f"{k} {v}" for k, v in list(FRACK.items())[:4]) + " …"])
MODS.append(["rn fr Yn … · r. V, T, … · Ty", "커닝 보정", f"어깨 없는 n 위로 튀어나온 글자는 좁히고, 사선·r 뒤 마침표·쉼표에 커닝을 넣고, u 모양 y를 u처럼 커닝 — {len(KERN_FIX)}쌍, 참고 서체 6종 범위 안으로"])

# pin clearance (audit 2026-09-27): the pin is larger and higher than Quicksand's dot, and the
# kerning was made for the small dot. Wherever i or j meets another glyph — on either side — the
# white between the pin and the neighbour's ink must be at least PIN_CLEAR; add the shortfall to
# the pair's kerning. Distances are measured on the real outlines, not boxes.
PIN_CLEAR = 65
_poly = {}


def _segs(ch):
    if ch not in _poly:
        _poly[ch] = [(pl[i], pl[(i + 1) % len(pl)]) for pl in polylines(G[ch]["p"], steps=12) for i in range(len(pl))]
    return _poly[ch]


def _dist(px, py, ch, dx):
    best = 1e9
    for (x0, y0), (x1, y1) in _segs(ch):
        x0 += dx; x1 += dx
        vx, vy = x1 - x0, y1 - y0; L2 = vx * vx + vy * vy or 1e-9
        t = max(0.0, min(1.0, ((px - x0) * vx + (py - y0) * vy) / L2))
        best = min(best, math.hypot(px - x0 - t * vx, py - y0 - t * vy))
    return best


PINKERN = {}
kp = [c for c in LOWER + UPPER + DIGITS + ".,:;!?-/'\"()&" if c in G and list(G[c]["p"].contours)]
for a in "ij":
    for b in kp:
        for L, Rt in ((a, b), (b, a)):
            k = KERN.get(L + Rt, 0); xr = G[L]["adv"] + k
            d = min((_dist(x, y, Rt, xr) if L in "ij" else 1e9) for x, y in G[L]["pins"]) if L in "ij" else 1e9
            if Rt in "ij":
                d = min(d, min(_dist(x + xr, y, L, 0) for x, y in G[Rt]["pins"]))
            d -= PIN_R
            if d < PIN_CLEAR and (L + Rt) not in PINKERN:
                PINKERN[L + Rt] = round(PIN_CLEAR - d)
                KERN[L + Rt] = k + PINKERN[L + Rt]
# two pins side by side (ii ij ji jj): the pins are wider than the stems under them, so keep at
# least the white that stands between the two stems of "ii" — the row of pins keeps the stems' rhythm
PIN_PAIR = 0.82 * (G["i"]["adv"] - S)   # proof A · I07: the full stem white made ii ij ji jj read "i i"
for L in "ij":
    for Rt in "ij":
        k = KERN.get(L + Rt, 0); xr = G[L]["adv"] + k
        d = min(math.hypot(x2 + xr - x1, y2 - y1) for x1, y1 in G[L]["pins"] for x2, y2 in G[Rt]["pins"]) - 2 * PIN_R
        if d < PIN_PAIR:
            PINKERN[L + Rt] = PINKERN.get(L + Rt, 0) + round(PIN_PAIR - d); KERN[L + Rt] = k + round(PIN_PAIR - d)
_tick("pin kerning"); accents.kern(globals()); _tick("accents.kern")                 # tools/accents.py: é takes e's pairs, marks keep clear of neighbours
MODS.append(["i j 옆", "핀 커닝", f"핀과 이웃 글자 윤곽 사이 흰 폭이 {PIN_CLEAR}(0.54s)보다 좁은 쌍, 핀이 나란한 쌍(ii·ij·ji)은 두 세로획 사이 흰 폭({PIN_PAIR:.0f})보다 좁은 만큼 커닝을 벌림 — {len(PINKERN)}쌍, 실제 윤곽 거리로 양쪽 모두"])
if JFLOOR:
    MODS.append(["j ĵ", "ȷ의 커닝이 하한", "j는 ȷ에 핀을 더한 것이라 ȷ의 짝보다 좁게 짜이지 않음 — ( [ { ¿ 와 j의 갈고리가 700~900에서 겹치던 것(부모의 (j 흰 폭을 따르느라 0) 해소: "
                 + ", ".join(f"{pr} {a}→{b}" for pr, (a, b) in JFLOOR.items())])

# ==== sweep 2026-09-28 · aliases and spaces ========================================================
# ‐ ‑ (U+2010 U+2011) are the hyphen, ― (U+2015) the em dash, ￦ (U+FFE6) the won sign: the same drawing, and they
# kern through their class (kcls below), so they are added after all the kerning and take none of their own.
from punct import SYM_ALIAS
for _a, _b in SYM_ALIAS.items():
    if _b in G and _a not in G:
        G[_a] = {"p": pathops.Path(G[_b]["p"]), "adv": G[_b]["adv"], "pins": list(G[_b]["pins"])}
_als = {}
for _a, _b in SYM_ALIAS.items():
    if _a in G: _als.setdefault(_b, []).append(_a)
for _pr, _v in list(KERN.items()):          # the base's pairs, written out so the class compaction below drops them
    if len(_pr) != 2 or not (_pr[0] in _als or _pr[1] in _als): continue
    for _A in [_pr[0]] + _als.get(_pr[0], []):
        for _B in [_pr[1]] + _als.get(_pr[1], []):
            if _A + _B not in KERN: KERN[_A + _B] = _v
# typographic spaces and zero-width marks (the engine and the font files set them from this table; U+3000, one
# Hangul syllable wide, comes from the Hangul data): no-break = the word space; thin and narrow no-break = the
# parent's thin space (Quicksand 205, 1/5 em); en, em; soft hyphen and ZWSP take no room.
_thin = hmtx[cmap[0x2009]][0] if 0x2009 in cmap else round(UPM / 5)
SPACES = {"\u00a0": hmtx["space"][0], "\u2009": _thin, "\u202f": _thin, "\u2002": UPM // 2, "\u2003": UPM,
          "\u00ad": 0, "\u200b": 0}
# ==== /sweep ========================================================================================

# ---------------------------------------------------------------- variant for the l-height decision
# "compact": the earlier rule (l top = pin centre, gap 0.4s) kept by shortening the ascenders; the
# descenders stay (Quicksand's hooks cannot be shortened by moving outlines) — shown only on the
# comparison page, where it reproduces the v2 imbalance (b d f shorter than p q).
def retract(p, cut, dy):
    big = 1e4
    if dy > 0:   # pull the part above `cut` down
        return union(inter(p, rect(-big, -big, big, cut)), xform(inter(p, rect(-big, cut, big, big)), f=-dy))
    return union(inter(p, rect(-big, cut, big, big)), xform(inter(p, rect(-big, -big, big, cut)), f=-dy))


A_C = XH + GAP + PIN_R                  # 661.5: l top = pin centre
dyA, dyD = ASC - A_C, (-DESC) - (A_C - XH)
VAR = {}
for ch in "abcdefghijklmnopqrstuvwxyz.":
    p = G[ch]["p"]
    b = bounds(p) if p.contours else (0, 0, 0, 0)
    if b[3] > CAP: p = retract(p, 610, dyA)          # b d f h k l (t at 650 stays); descenders unchanged
    pins = [(x, A_C if ch in "ij" else y) for x, y in G[ch]["pins"]]
    VAR[ch] = {"p": p, "adv": G[ch]["adv"], "pins": pins}

# ---------------------------------------------------------------- output (y down, baseline 0)
def d_of(p):
    pen = SVGPathPen(None, ntos=lambda v: ("%.1f" % v).rstrip("0").rstrip("."))
    p.draw(TransformPen(pen, (1, 0, 0, -1, 0, 0)))
    return pen.getCommands()


def box(p, pins=(), pr=None):
    """Ink box (y down) including pins (radius pr, default the pin)."""
    pr = PIN_R if pr is None else pr
    b = list(bounds(p)) if list(p.contours) else [1e9, 1e9, -1e9, -1e9]
    for x, y in pins:
        b = [min(b[0], x - pr), min(b[1], y - pr), max(b[2], x + pr), max(b[3], y + pr)]
    return [round(b[0], 1), round(-b[3], 1), round(b[2], 1), round(-b[1], 1)]


# ---- wcons 2026-09-27 · one clean outline per glyph ----------------------------------------------------------
# A transform after the last boolean op can leave overlapping pieces in the output (n h at 300: four
# overlapping contours drawn as one shape). Merge them; glyphs that are already clean are left untouched.
# Specks under one square unit (a self-touching point in Quicksand's ¹ ¼ ½ at 600 left a hole of area 0)
# are dropped.
for ch, g in G.items():
    _q = pathops.Path(g["p"]); _q.simplify()
    _cs = [c for c in _q.contours if abs(c.area) >= 1.0]
    if len(_cs) != len(list(_q.contours)):
        _q = pathops.Path()
        for c in _cs: _q.addPath(c)
    if len(list(_q.contours)) != len(list(g["p"].contours)):
        g["p"] = _q
# ---- /wcons ---------------------------------------------------------------------------------------------

# pinholes (audit 2026-09-27): a boolean step can leave a counter smaller than a tenth-stem square — the
# cedilla's hook at 600 kept a hole of 47 units². At any size that reads as a broken glyph, not as
# white, so such tiny contours are dropped before output.
PINHOLE = (0.1 * S) ** 2                 # 144 at 700; real small counters (the 4 of ¼, ®) are 600+
PINHOLES = {}
for ch, g in G.items():
    cs = list(g["p"].contours)
    small = [c for c in cs if abs(c.area) < PINHOLE]
    if small and len(small) < len(cs):
        q = pathops.Path(); qp = q.getPen()
        for c in cs:
            if abs(c.area) >= PINHOLE: c.draw(qp)
        g["p"] = q; PINHOLES[ch] = [round(abs(c.area)) for c in small]
if PINHOLES: print("pinholes dropped:", PINHOLES)
# ---- outline hygiene (tools/geom.py): a spike or a crack left by the boolean steps (a bar's join at 600-900, a
# cedilla's) goes, and every counter keeps COUNTER_MIN of white: a narrower one (the 4 of ¼ ⁴ at 900, the R of ®) is
# opened by thinning the ink round it, by at most 0.12 s. The wordmark's letters have neither and are never touched.
import geom
COUNTER_MIN = 0.35 * S
HYGIENE = {}
for ch, g in G.items():
    if ch == "림" or not list(g["p"].contours): continue
    q = geom.despike(g["p"])
    q = geom.open_counters(q, COUNTER_MIN, 0.12 * S)
    if q is not g["p"]:
        HYGIENE[ch] = round(abs(q.area) - abs(g["p"].area), 1); g["p"] = q
if HYGIENE: print("outline hygiene:", HYGIENE, file=sys.stderr)
_tick("hygiene")
CHANGED = set("nmhrij.:;!?·wWQ") | set(FEET) | set(SYM)
CHANGED |= PUNCT_OUT["changed"]
glyphs = {}
for ch, g in G.items():
    glyphs[ch] = {"d": d_of(g["p"]), "adv": g["adv"], "box": box(g["p"], g["pins"], g.get("pinr")), **({"pinr": g["pinr"]} if "pinr" in g else {}),
                  "pins": [[x, -y] for x, y in g["pins"]], "stems": stems_of(g["p"]) if ch in "ilmnhu" else []}
    if ch in CHANGED and ch in ORIG:
        glyphs[ch]["orig"] = {"d": d_of(ORIG[ch]), "adv": hmtx[cmap[ord(ch)]][0]}
for ch in "lu":                       # unchanged parents shown next to their children
    glyphs[ch]["orig"] = {"d": d_of(ORIG[ch]), "adv": hmtx[cmap[ord(ch)]][0]}

# kerning classes (accents): é kerns as e, so a pair is written only where it differs from its base pair —
# the renderer falls back to the base pair (kcls). Writing every accented pair out took the data from
# ~0.7 k to ~17 k pairs per weight (1.5 MB -> 7.2 MB for the playground).
KCLS = {ch: [c[0], c[1]] for ch, c in accents.ST["cls"].items()}
KCLS.update({_a: [_b, _b] for _a, _b in SYM_ALIAS.items() if _a in G})   # sweep 2026-09-28: aliases kern as their glyph
def _kbase(pr):
    l = (KCLS.get(pr[0]) or [None, None])[0] or pr[0]; r = (KCLS.get(pr[1]) or [None, None])[1] or pr[1]
    return l + r
KOUT = {}
for pr, v in KERN.items():
    bp = _kbase(pr) if len(pr) == 2 else pr
    if bp != pr and KERN.get(bp, 0) == v: continue
    KOUT[pr] = v
_L, _R = {}, {}
for ch, (kl, kr) in KCLS.items():
    if kl: _L.setdefault(kl, []).append(ch)
    if kr: _R.setdefault(kr, []).append(ch)
for pr, v in list(KERN.items()):            # accented pairs that are 0 while their base pair is not
    if len(pr) != 2 or not v: continue
    for A in [pr[0]] + _L.get(pr[0], []):
        for B in [pr[1]] + _R.get(pr[1], []):
            if A + B != pr and A + B not in KERN and _kbase(A + B) == pr: KOUT[A + B] = 0
_bad = [pr for pr, v in KERN.items() if len(pr) == 2 and KOUT.get(pr, KOUT.get(_kbase(pr), 0) if pr not in KOUT else KOUT[pr]) != v]
assert not _bad, ("kern compaction mismatch", _bad[:10])
# kerning coverage (tools/audit.py kerncover): every glyph is kerned by the parent's GPOS (ks), measured against every
# neighbour by a clearance pass (punct_kern's rebuilt set, accents.kern's marks), or kerns through its class, whose base
# is itself covered. KCOVER lists what is none of these; the audit fails the build on any.
from punct import ST as _PST
_cov = set(ks) | set(_PST.get("kern_measured", ())) | set(accents.ST["marks"])
for _ in range(3):
    _cov |= {ch for ch, (kl, kr) in KCLS.items() if (kl or ch) in _cov and (kr or ch) in _cov}
import unicodedata as _ud
KCOVER = sorted(ch for ch, g in G.items() if ch != "림" and (list(g["p"].contours) or g["pins"]) and ch not in _cov
                and _ud.category(ch) != "Mn")                          # combining marks (zero width) do not kern
data = {
    "name": "limn", "parent": "Quicksand Bold (wght 700) — SIL OFL 1.1, © The Quicksand Project Authors",
    "upm": UPM, "xh": XH, "xo": XO, "asc": ASC, "desc": DESC, "cap": CAP, "s": S,
    "pin": {"r": round(PIN_R, 2), "gap": round(I_GAP, 2), "dotgap": round(GAP, 2), "cy": -round(PIN_CY, 2)},   # wcons: gap = the i pin white
    "space": hmtx["space"][0], "spaces": SPACES, "glyphs": glyphs, "kern": KOUT, "kcls": KCLS, "kcover": KCOVER, "pinkern": PINKERN, "mods": MODS, "feet": FEET,
    "tn": TN, "pnum": PNUM, "pkern": PKERN, "pglyph": {ch: {"d": d_of(v["p"]), "adv": v["adv"], "box": box(v["p"])} for ch, v in PGLYPH.items()},
    "variants": {"compact": {"asc": round(A_C, 1), "desc": DESC,
                             "glyphs": {ch: {"d": d_of(v["p"]), "adv": v["adv"], "box": box(v["p"], v["pins"]), "pins": [[x, -y] for x, y in v["pins"]]}
                                        for ch, v in VAR.items()}}},
}
if PLAY_OUT:
    def gd(p):
        return {"d": d_of(p), "box": box(p)}
    play = {
        "w": WGHT, "pin": {"r": round(PIN_R, 2), "gap": round(I_GAP, 2), "dotgap": round(GAP, 2), "qr": round(Q_DOT_R, 2), "qgap": round(Q_GAP, 2)}, "xh": XH, "xo": XO, "asc": ASC, "desc": DESC, "cap": CAP, "s": S, "space": hmtx["space"][0], "spaces": SPACES,
        "glyphs": {ch: {"d": d_of(g["p"]), "adv": g["adv"], "box": box(g["p"]), "stems": stems_of(g["p"]) if ch in "ilmnhu" else [],
                        **({"pinx": g["pins"][0][0], "piny": -g["pins"][0][1], "pinr": g.get("pinr")} if ch == "림" else {})}
                   for ch, g in G.items()},
        "nofeet": {ch: gd(PREFEET[ch]) for ch in FEET},                       # feet left round
        "spur": {ch: {**gd(ORIG[ch]), "adv": hmtx[cmap[ord(ch)]][0]} for ch in "nmhr"},   # Quicksand's own n family
        "spurfeet": {ch: gd(flatten_feet(ORIG[ch])[0]) for ch in "nmhr"},
        "dots": DOTSPEC, "kern": KOUT, "kcls": KCLS, "kcover": KCOVER, "tn": TN, "pnum": PNUM, "pkern": PKERN,
        "pglyph": {ch: {"d": d_of(v["p"]), "adv": v["adv"], "box": box(v["p"])} for ch, v in PGLYPH.items()},
        # Quicksand's own alternates, for the playground: ss01 a·g (double-storey) and the slashed zero
        "alt": {ch: {"d": d_of(q), "box": box(q), "adv": TN if ch == "0" else hmtx[nm][0]}
                for ch, nm in (("a", "a.ss01"), ("g", "g.ss01"), ("0", "zero.zero"))
                for q0 in [flatten_feet(gpath(None, nm))[0]]
                for q in [xform(q0, e=(TN - (bounds(q0)[2] - bounds(q0)[0])) / 2 - bounds(q0)[0]) if ch == "0" else q0]},
    }
    FSPath(PLAY_OUT).write_text(json.dumps(play, ensure_ascii=True, separators=(",", ":")))
    print("play", WGHT, "S", S, "XH", XH, "ASC", ASC, "->", PLAY_OUT)
    sys.exit(0)
OUT.write_text(header("build_font.py") + "window.LIMN_FONT=" + json.dumps(data, ensure_ascii=True, separators=(",", ":")) + ";\n")
print("wrote", OUT, OUT.stat().st_size, "bytes;", len(glyphs), "glyphs;", len(KERN), "kern pairs")
print("pin r", round(PIN_R, 2), "n stems", ns, "pitch", pitch, "r xc", round(xc), "cap_r", round(cap_r))
print("feet:", {k: v for k, v in FEET.items()})
print("sym:", SYM, "? drop/tail:", QDROP)
print("traps:", {k: [(a, t, d) for _, a, t, d in v] for k, v in TRAPS.items()})
