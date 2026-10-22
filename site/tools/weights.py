"""limn weights 100-900 from Quicksand, whose wght axis only runs 300-700.

  from weights import instance
  font = instance(SRC, WGHT)      # a TTFont, as instantiateVariableFont(TTFont(SRC), {"wght": WGHT}) gives

300-700 is Quicksand's own instance, untouched (only a dot that is not round enough for the pin rule
is made round; that happens below 400, where Quicksand's period is an oval). Outside the axis the
nearest master (300 or 700) is eroded or dilated with an elliptical pen:

  stem S(w)       300-700: Quicksand's own, 0.2 w - 20 (40 ... 120)
                  below 300: every 100 thins by Quicksand's own 300->400 ratio 1.5 (27 at 200, 18 at 100)
                  above 700: leaves 700 with Quicksand's slope and bends up to 180 at 900 (145 at 800):
                  paragraph colour then darkens in even steps 500 -> 900 (wcons 2026-09-27)
  contrast H/S    Quicksand's own o (.95 at 300, .92 at 700); 1.00 at 100, .75 at 900 like the references
  x-height        Quicksand's own inside the axis, 510 + 0.0625 (w - 300); held at the nearest master's
                  outside it (510 below 300, 535 above 700) — every vertical metric outside the axis is
                  the master's, so ascender, cap height, x-height and the pin top (= ascender, build_font)
                  stay one set of lines from 700 to 900 (wcons 2026-09-27)
  zones           baseline, x-height, cap height, ascender and descender are held by a piecewise-linear
                  vertical map through the moved flat edges (overshoots ride along)
  spacing         every glyph's side bearings follow Quicksand's own per-glyph 300->700 trend, linear in S
  thinnest        below the axis a part Quicksand draws thin (the tails of } £) keeps about 0.8 S (_min_stroke)
  width           a glyph Quicksand narrows as it gets heavier (C Æ Œ Q) keeps narrowing past the axis: its ink width
                  follows that trend, not the pen (_follow_width)
  counters        when dilating, a small counter closes by at most 0.55 x its inradius (A 4 e stay open);
                  the pen never makes a new one: a notch whose mouth it closes is filled (ð, fill_new_counters)
  dots, tails     dots and comma tails follow Quicksand's own per-glyph trend, not the pen; a dot the pin
                  rule would miss (oval) is made round; ! ? keep white above their dot; above 700 the ?
                  hook is squeezed to the cap height and clear of the pin (build_font's cut needs a tail)

metrics(w) gives the targets. Measured and chosen in /tmp/limn-work/weights (weights.html).
"""
from functools import lru_cache

import pathops
from fontTools.pens.cu2quPen import Cu2QuPen
from fontTools.pens.ttGlyphPen import TTGlyphPen
from fontTools.ttLib import TTFont
from fontTools.varLib.instancer import instantiateVariableFont

LO, HI = 300, 700                      # Quicksand's axis
# stem bend above 700 (proof audit 2026-09-27, C-10 option): 0.001 gives S 150 / 200 at 800 / 900;
# 0.0005 gives 145 / 180 (even paragraph-colour steps, 900 lighter than M+ Rounded Black)
# wcons 2026-09-27 (user: "600 이후 너무 익스포넨셜하게 증가"): 0.0005 is the default now
STEM_K2 = float(__import__("os").environ.get("LIMN_STEM_K2", 0.0005))
STEM_B1 = float(__import__("os").environ.get("LIMN_STEM_B1", 0.2))     # slope leaving 700 (Quicksand's own 0.2)
# wcons 2026-09-27: "hold" keeps the x-height (and its overshoot) of the nearest master outside the axis;
# "trend" is the earlier extrapolation (547.5 at 900), which left no room for the pin under the ascender
XH_OUT = __import__("os").environ.get("LIMN_XH_OUT", "hold")
DOTTED = ".:;!?·ij"                    # the glyphs whose round dots become pins (build_font.py)
LOWER = "abcdefghijklmnopqrstuvwxyz"
CAP, ASC, DESC = 700, 740, -200


# ------------------------------------------------------------------ the curves
# ==== lin 2026-09-27 · linear weight curve (LIMN_WCURVE) ==============================================
# user 2026-09-27: "300~700까지 굵어지는 그 굵기 증가(선형)가 그대로 800, 900으로 이어지면 좋겠음 ... S/x 의
# 비율이 선형으로 커졌으면 좋겠음 ... 100에서 900까지 선형으로". The stem-to-x-height ratio r = S / XH is one
# straight line in the weight; S follows from r and the x-height that goes with S (Quicksand's own inside
# its axis, the nearest master's outside: XH_OUT "hold"). Inside the axis every limn weight is the
# Quicksand instance whose stem is S (wght_q = 5 (S + 20)): limn 400 on curve A = Quicksand 441.8. Only a
# stem outside 40-120 is eroded / dilated from the nearest master.
#   A (default)  through (100, 20 / 510) and (700, 120 / 535): S 20 35.7 51.8 68.4 85.2 102.4 120 136.5 153.0
#   B            through (700, 120 / 535) and (900, 145 / 535) (900 = the old 800): S 43.0 ... 120 132.5 145
#   C            through (100, 18 / 510) and (900, 145 / 535): 700 moves to S 113 (reference only)
#   Q            the curve before (1.5x per 100 below 300, bend above 700: 18 27 40 ... 120 145 180)
#   D (default, 2026-09-28)  through (100, 20 / 510) and (900, A's 800 / 535): the user dropped A's 900 ("900은 쓰지
#                말고 800을 900으로 맞춰서 그 사이를 더 상세히 쪼개자"), so the nine weights share A's 100 ... 800 range
#                in equal steps: S 20 33.8 47.8 62.1 76.7 91.6 106.8 122.1 136.5. Quicksand Bold (S 120, the
#                brand drawing: limn-font.js, the wordmark, the logo 림) is no longer a family weight; it is
#                built on A (Makefile font) and sits 2 % under D's 800.
#   2026-10-01   the default is HALF (user decision after the PoC: 400 halfway between D and the grey of Inter /
#                Pretendard 400, even steps up to 155 at 900; STEM_TABLES below). D and the others stay selectable.
WCURVE = __import__("os").environ.get("LIMN_WCURVE", "HALF").upper()
CURVES = {"A": ((100, 20 / 510), (700, 120 / 535)),
          "B": ((700, 120 / 535), (900, 145 / 535)),
          "C": ((100, 18 / 510), (900, 145 / 535))}
# ---- weight-curve tables (PoC 2026-09-30, QA visual S2 S4) -----------------------------------------------
# Text grey = ink / (advance x 0.7 em) of the QA's Latin line; grey(S) measured on D's weights and on 900 probes
# (S 145 0.405 · 150 0.413 · 155 0.422; from S 160 the Hangul ㅣ of 림 merges into ㅁ, so 155 is the ceiling here).
# LIMN_WCURVE=D900     D at 100-800; 900 at S LIMN_S900 (145: the 800 -> 900 step = the mean of D's, 0.042)
# LIMN_WCURVE=ALIGNED  400 at the grey of Inter / Pretendard 400 (0.2815), even steps up to 155 (0.028 a step)
# LIMN_WCURVE=HALF     400 halfway between D's and ALIGNED's (0.2425, about D's 500), even steps up to 155 (0.036)
# LIMN_WCURVE=TABLE    S from LIMN_WSTEMS="s100,s200,...,s900"
# S is given at 100 ... 900 and runs straight between. HALF is the default; the brand drawing (A) is untouched.
STEM_TABLES = {"ALIGNED": (60.0, 69.8, 79.8, 90.0, 100.8, 111.8, 123.4, 139.1, 155.0),
               "HALF": (39.5, 51.2, 63.2, 75.9, 88.9, 102.6, 116.8, 134.7, 155.0)}
if __import__("os").environ.get("LIMN_WSTEMS"):
    STEM_TABLES["TABLE"] = tuple(float(v) for v in __import__("os").environ["LIMN_WSTEMS"].split(","))
S900 = float(__import__("os").environ.get("LIMN_S900", 145))
# ==== /poc ==================================================================================================


def qs_stem(wq):
    """Quicksand's own l stem at its wght wq (40 at 300 ... 120 at 700)."""
    return 0.2 * wq - 20


def qs_wght(S):
    """The Quicksand wght whose stem is S (unclamped)."""
    return 5.0 * (S + 20)


def _stem_q(w):
    """The curve before lin (LIMN_WCURVE=Q)."""
    if w < LO:
        return 40 * 1.5 ** ((w - LO) / 100)
    if w <= HI:
        return 0.2 * w - 20
    return 120 + STEM_B1 * (w - HI) + STEM_K2 * (w - HI) ** 2


def _wz(S):
    """The Quicksand wght whose vertical metrics go with stem S (held at the master outside the axis)."""
    wq = qs_wght(S)
    return min(HI, max(LO, wq)) if XH_OUT == "hold" else wq


def xh_of(S):
    return 510 + 0.0625 * (_wz(S) - LO)


def ratio(w, curve=None):
    """S / XH on a linear curve."""
    (w0, r0), (w1, r1) = CURVES[curve or WCURVE]
    return r0 + (r1 - r0) * (w - w0) / (w1 - w0)


def stem(w, curve=None):
    curve = (curve or WCURVE).upper()
    if curve == "Q":
        return _stem_q(w)
    if curve in STEM_TABLES or curve == "D900":        # poc 2026-09-30, see STEM_TABLES
        return _stem_table(w, curve)
    r = ratio(w, curve)
    # S = r XH(S): XH(S) is flat below 40 and above 120 (hold) and 497.5 + 0.3125 S between
    a, b = 510 - 0.0625 * LO + 0.0625 * 5 * 20, 0.0625 * 5
    if XH_OUT == "hold":
        if r * 510 <= qs_stem(LO):
            return round(r * 510, 9)
        if r * 535 >= qs_stem(HI):
            return round(r * 535, 9)
    return round(a * r / (1 - b * r), 9)        # rounded: 700 on A and B is exactly 120 (Quicksand 700)


CURVES["D"] = ((100, 20 / 510), (900, stem(800, "A") / 535))      # the default curve, defined on A


def _stem_table(w, curve):                  # poc 2026-09-30, see STEM_TABLES
    if curve == "D900":
        return stem(w, "D") if w <= 800 else stem(800, "D") + (S900 - stem(800, "D")) * (w - 800) / 100
    t = STEM_TABLES[curve]
    i = min(7, max(0, int((w - 100) // 100)))
    return t[i] + (t[i + 1] - t[i]) * (w - 100 - 100 * i) / 100
# ==== /poc ==================================================================================================


def _q_contrast(wq):
    return (38 + 0.18 * (wq - LO)) / qs_stem(wq)          # Quicksand's o: horizontal / vertical


def contrast_of(S):
    """H / S for a stem S: Quicksand's own inside the axis; outside, the ramp the old curve had at the same
    stem (1.00 at S 17.8, .75 at S 180), so the contrast belongs to the stroke weight, not to the name."""
    if qs_stem(LO) <= S <= qs_stem(HI):
        return _q_contrast(qs_wght(S))
    if S < qs_stem(LO):
        w = LO + 100 * __import__("math").log(S / 40) / __import__("math").log(1.5)    # old curve's weight
        return min(1.0, _q_contrast(LO) + (1.0 - _q_contrast(LO)) * (LO - w) / 200)
    d = (-STEM_B1 + (STEM_B1 ** 2 + 4 * STEM_K2 * (S - 120)) ** 0.5) / (2 * STEM_K2) if STEM_K2 else (S - 120) / STEM_B1
    return max(0.75, _q_contrast(HI) + (0.75 - _q_contrast(HI)) * d / 200)


def contrast(w):
    return contrast_of(stem(w))


def metrics_of(S, w=None):
    """Targets for a stem S (the same dict for a limn weight and for the Quicksand master it maps to)."""
    wz = _wz(S)
    xh = 510 + 0.0625 * (wz - LO)
    return {"w": w, "S": S, "H": S * contrast_of(S), "XH": xh, "wq": qs_wght(S),
            "XO": xh + max(3.0, 5 + 0.0125 * (wz - LO)), "CAP": CAP, "ASC": ASC, "DESC": DESC}


def metrics(w):
    return metrics_of(stem(w), w)
# ==== /lin ==============================================================================================


# ------------------------------------------------------------------ path helpers
def _path(gs, name):
    p = pathops.Path()
    gs[name].draw(p.getPen(glyphSet=gs))
    p.simplify()
    return p


def _map(p, fy):
    out = pathops.Path(); pen = out.getPen()
    m = lambda pt: (pt[0], fy(pt[1]))
    for verb, pts in p.segments:
        if verb == "moveTo": pen.moveTo(m(pts[0]))
        elif verb == "lineTo": pen.lineTo(m(pts[0]))
        elif verb == "qCurveTo": pen.qCurveTo(*[m(q) if q is not None else None for q in pts])
        elif verb == "curveTo": pen.curveTo(*[m(q) for q in pts])
        elif verb == "closePath": pen.closePath()
        elif verb == "endPath": pen.endPath()
    return out


def _piecewise(src, dst):
    ks = sorted(zip(src, dst))
    def f(y):
        if y <= ks[0][0]: return ks[0][1] + (y - ks[0][0])
        if y >= ks[-1][0]: return ks[-1][1] + (y - ks[-1][0])
        for (a, A), (b, B) in zip(ks, ks[1:]):
            if a <= y <= b:
                return A + (y - a) * (B - A) / (b - a)
        return y
    return f


def offset(p, rx, ry):
    """Dilate (> 0) or erode (< 0) by an ellipse with semi-axes rx, ry of the same sign: a round pen
    in a space squeezed vertically by ry / rx."""
    if abs(rx) < 1e-3:
        return pathops.Path(p)
    k = ry / rx
    q = _map(p, lambda y: y / k)
    s = pathops.Path(q)
    s.stroke(2 * abs(rx), pathops.LineCap.ROUND_CAP, pathops.LineJoin.ROUND_JOIN, 4)
    s.convertConicsToQuads()
    q = pathops.op(q, s, pathops.PathOp.UNION if rx > 0 else pathops.PathOp.DIFFERENCE)
    q.simplify()
    return _map(q, lambda y: y * k)


# proof audit 2026-09-27 (C-07): with 0.55 the 900 counters of 4 A e % stayed at 0.23-0.34 s (a pinhole
# in 4 at 12-16 px). A small counter now closes by at most COUNTER_KEEP_SMALL x its inradius; counters
# with an inradius past rx / 0.55 (73 at 900: B R o a d ...) still close by the full pen, so they keep
# the stems' weight; a linear ramp over the last 20 % joins the two (no jump between glyphs).
COUNTER_KEEP = 0.55                     # the old share; its threshold (rx / 0.55) is where the ramp ends
COUNTER_KEEP_SMALL = float(__import__("os").environ.get("LIMN_COUNTER_KEEP_SMALL", 0.2))


def _inradius(c):
    """Half the thickness of a contour's thickest part (erode until nothing is left)."""
    q = pathops.Path(); q.addPath(c); q.simplify()
    # proof audit 2026-09-27 (C-12): search only up to half the contour's narrow side. From 300 the pen was
    # far wider than a small round counter (% rings, r 63) and skia's stroker left its centre uncovered,
    # so the % rings read as huge (299) and closed by the full pen at 900 (hole 0.24 s).
    x0, y0, x1, y1 = q.bounds
    lo, hi = 0.0, min(x1 - x0, y1 - y0) / 2 + 1
    for _ in range(9):
        mid = (lo + hi) / 2
        if list(offset(q, -mid, -mid).contours): lo = mid
        else: hi = mid
    return lo


def grow(p, rx, ry):
    """offset(), but when dilating, a small counter (A 4 e a at 800-900) shrinks by at most
    COUNTER_KEEP x its inradius instead of by the full pen: the white stays open and the ink
    around it grows less than the stems. Big counters (o n) are untouched."""
    out = offset(p, rx, ry)
    if rx <= 0:
        return out
    cs = list(p.contours)
    if len(cs) < 2:
        return fill_new_counters(out, p)[0]          # small-glyphs 2026-09-28 (see fill_new_counters)
    big = max(cs, key=lambda c: abs(c.area))
    for c in cs:
        if c.clockwise == big.clockwise:
            continue
        ir = _inradius(c); big_at = rx / COUNTER_KEEP
        s = min(1.0, COUNTER_KEEP_SMALL * ir / rx)
        s += (1.0 - s) * max(0.0, min(1.0, (ir - 0.8 * big_at) / (0.2 * big_at)))
        if s >= 0.999:
            continue
        hole = pathops.Path(); hole.addPath(c); hole.simplify()
        hole = offset(hole, -s * rx, -s * ry)
        if list(hole.contours):
            out = pathops.op(out, hole, pathops.PathOp.DIFFERENCE)
    return fill_new_counters(out, p)[0]              # small-glyphs 2026-09-28 (see fill_new_counters)


# ------------------------------------------------------------------ wcons 2026-09-27: symbols and separate parts
# (1) Symbols follow their own stroke trend. Quicksand thickens ® © ™ ¹ ² ³ ½ % … far less than its stems
#     from 300 to 700 (® 0.25 of the stem's growth, © 0.56, ™ 0.76, % 0.78; stroke = 2 area / outline
#     length against l's). The full stem pen overweighted them at 800-900 and closed ® and ©. Letters
#     and figures keep the stem pen exactly (the S rule); other glyphs take their own share, eased in
#     between 0.8 and 0.9 so no glyph jumps.
# (2) Separate parts keep their white. When dilating, two parts that were apart at the master (the rings
#     and slash of %, the plus and bar of ±, T and M of ™, R in the ring of ®) are grown one by one; where
#     the white between them would fall below the master's x sqrt(S_master / S): a part nested in the
#     other's counter (® ©) shrinks about its centre; a stroke end pointing straight at the other part
#     (± plus stem) is shortened and its new end rounded; otherwise (side by side: % ‰ ¼ ½ ¾ ™) the part
#     farther from the glyph's middle moves sideways, and the glyph widens with it (grow_parts).
LETTERS = "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789"


def _flat(c, steps=8):
    pts = []; cur = None; first = None
    for verb, a in c.segments:
        if verb == "moveTo":
            cur = a[0]; first = cur; pts.append(cur)
        elif verb == "lineTo":
            e = a[0]; n = max(1, int(((e[0] - cur[0]) ** 2 + (e[1] - cur[1]) ** 2) ** 0.5 / 8))
            pts.extend((cur[0] + (e[0] - cur[0]) * k / n, cur[1] + (e[1] - cur[1]) * k / n) for k in range(1, n + 1))
            cur = e
        elif verb == "qCurveTo":
            if a[-1] is None:
                ctrl = list(a[:-1]); mid = ((ctrl[-1][0] + ctrl[0][0]) / 2, (ctrl[-1][1] + ctrl[0][1]) / 2)
                cur = mid; pts.append(mid); a = tuple(ctrl) + (mid,)
            ctrl = list(a[:-1]); end = a[-1]; p0 = cur
            for i, q in enumerate(ctrl):
                e = end if i == len(ctrl) - 1 else ((q[0] + ctrl[i + 1][0]) / 2, (q[1] + ctrl[i + 1][1]) / 2)
                for k in range(1, steps + 1):
                    t = k / steps
                    pts.append(((1 - t) ** 2 * p0[0] + 2 * (1 - t) * t * q[0] + t * t * e[0],
                                (1 - t) ** 2 * p0[1] + 2 * (1 - t) * t * q[1] + t * t * e[1]))
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


def _stroke(p):
    per = 0.0
    for c in p.contours:
        q = _flat(c)
        per += sum(((q[i][0] - q[i - 1][0]) ** 2 + (q[i][1] - q[i - 1][1]) ** 2) ** 0.5 for i in range(len(q)))
    return 2 * abs(p.area) / per if per else 0.0


@lru_cache(maxsize=None)
def _pen_k(src):
    """Per glyph name: the share of the stem pen it takes (1 for letters and figures)."""
    f3, f7 = _qs(src, LO), _qs(src, HI)
    g3, g7 = f3.getGlyphSet(), f7.getGlyphSet()
    by = _class(f3); ln = f3.getBestCmap()[ord("l")]
    tl = _stroke(_path(g7, ln)) - _stroke(_path(g3, ln))
    out = {}
    for n in f3.getGlyphOrder():
        ch = by.get(n, "")
        if (ch and ch in LETTERS) or n.split(".")[0] in LETTERS or n.startswith("zero"):
            continue
        p3, p7 = _path(g3, n), _path(g7, n)
        if not list(p3.contours) or not list(p7.contours):
            continue
        k = (_stroke(p7) - _stroke(p3)) / tl
        k = max(0.25, min(1.0, k))
        if k < 0.9:
            out[n] = k if k <= 0.8 else k + (1.0 - k) * (k - 0.8) / 0.1
    return out


def _sop(a, b, how):
    """pathops.op that retries with a tiny shift of b when skia gives up on a degenerate pair."""
    for e in (0.0, 0.011, -0.023, 0.037):
        try:
            return pathops.op(a, b.transform(1, 0, 0, 1, e, 0.7 * e) if e else b, how)
        except pathops.PathOpsError:
            continue
    return pathops.Path(a) if how != pathops.PathOp.INTERSECTION else pathops.Path()


def _soff(p, rx, ry):
    """offset() that retries with a tiny shift when skia gives up; the shift is taken back out."""
    for e in (0.0, 0.011, -0.023, 0.037):
        try:
            q = offset(p.transform(1, 0, 0, 1, e, 0.7 * e) if e else p, rx, ry)
            return q.transform(1, 0, 0, 1, -e, -0.7 * e) if e else q
        except pathops.PathOpsError:
            continue
    return pathops.Path(p)


def _components(p):
    """Outer contours with their own holes, as separate paths (nesting by containment)."""
    cs = list(p.contours)
    if len(cs) < 2:
        return [p]
    fill = []
    for c in cs:
        q = pathops.Path(); q.addPath(c); q.simplify(); fill.append(q)
    n = len(cs)
    inside = [[False] * n for _ in range(n)]
    for i in range(n):
        for j in range(n):
            if i != j and abs(fill[i].area) < abs(fill[j].area):
                x = _sop(fill[i], fill[j], pathops.PathOp.INTERSECTION)
                inside[i][j] = abs(x.area) > 0.98 * abs(fill[i].area)
    depth = [sum(inside[i]) for i in range(n)]
    comps = []
    for i in range(n):
        if depth[i] % 2: continue
        q = pathops.Path(); q.addPath(cs[i])
        for h in range(n):
            if depth[h] == depth[i] + 1 and inside[h][i]:
                q.addPath(cs[h])
        q.simplify(); comps.append(q)
    return comps


def _nearest(A, B):
    """Closest points of two parts' outlines: (distance, point on A, its polyline, index, same for B)."""
    pa = [(q, i, pl) for c in A.contours for pl in [_flat(c)] for i, q in enumerate(pl)]
    pb = [(q, i, pl) for c in B.contours for pl in [_flat(c)] for i, q in enumerate(pl)]
    best = None
    for qa, ia, pla in pa:
        for qb, ib, plb in pb:
            d = (qa[0] - qb[0]) ** 2 + (qa[1] - qb[1]) ** 2
            if best is None or d < best[0]:
                best = (d, qa, pla, ia, qb, plb, ib)
    return best[0] ** 0.5, best[1:4], best[4:7]


def _convexity(pl, i, ink_left, reach):
    """Signed curvature at pl[i], positive where the outline bulges out of the ink."""
    n = len(pl)
    def walk(step):
        j = i; s = 0.0
        while s < reach:
            k = (j + step) % n
            s += ((pl[k][0] - pl[j][0]) ** 2 + (pl[k][1] - pl[j][1]) ** 2) ** 0.5; j = k
            if j == i: break
        return pl[j]
    a, b, c = walk(-1), pl[i], walk(1)
    cr = (b[0] - a[0]) * (c[1] - a[1]) - (b[1] - a[1]) * (c[0] - a[0])
    la = ((b[0] - a[0]) ** 2 + (b[1] - a[1]) ** 2) ** 0.5; lb = ((c[0] - b[0]) ** 2 + (c[1] - b[1]) ** 2) ** 0.5
    lc = ((c[0] - a[0]) ** 2 + (c[1] - a[1]) ** 2) ** 0.5
    k = 2 * cr / (la * lb * lc + 1e-9)
    return k if ink_left else -k


def _near_axis(pl, i, reach):
    """Direction a stroke runs out at pl[i]: from the centre of the outline points within `reach` to pl[i]."""
    q = pl[i]; pts = [p for p in pl if (p[0] - q[0]) ** 2 + (p[1] - q[1]) ** 2 < reach * reach]
    cx = sum(p[0] for p in pts) / len(pts); cy = sum(p[1] for p in pts) / len(pts)
    L = ((q[0] - cx) ** 2 + (q[1] - cy) ** 2) ** 0.5 or 1.0
    return (q[0] - cx) / L, (q[1] - cy) / L


def _cx(p):
    b = p.bounds
    return (b[0] + b[2]) / 2


def _shorten(A, other, target, ry, rx):
    """Cut part A back so it keeps `target` white from `other`; round the new end (0.4 of A's stroke)."""
    A2 = _sop(A, _soff(other, target, target * ry / rx), pathops.PathOp.DIFFERENCE)
    rho = 0.4 * _stroke(A)
    gone = _sop(A, A2, pathops.PathOp.DIFFERENCE)
    if list(A2.contours) and list(gone.contours):
        opened = _soff(_soff(A2, -rho, -rho), rho, rho)
        bits = _sop(A2, opened, pathops.PathOp.DIFFERENCE)
        zone = _soff(gone, rho + 2, rho + 2)
        A2 = _sop(A2, _sop(bits, zone, pathops.PathOp.INTERSECTION), pathops.PathOp.DIFFERENCE)
    return A2


def grow_parts(p, rx, ry, S0, S1):
    """grow(), part by part, keeping the white between separate parts (see above).
    For a pair that would come closer than the master's white x sqrt(S0 / S1):
      nested (R in the ring of ®, C in ©)       the inner part shrinks about its own centre
      a stroke end pointing at the other part    that stroke is shortened, its end rounded (± plus, ™ T)
      otherwise (side by side: % ‰ ¼ ½ ¾)        the part farther from the glyph's middle moves sideways,
                                                 with everything beyond it (the glyph widens)"""
    if rx <= 0:
        return grow(p, rx, ry)
    comps = _components(p)
    if len(comps) < 2:
        return grow(p, rx, ry)
    big = max(p.contours, key=lambda c: abs(c.area))
    ink_left = big.clockwise is False
    grown = [grow(c, rx, ry) for c in comps]
    keep = (S0 / S1) ** 0.5
    gx = _cx(p)
    for _pass in range(4):
        for i in range(len(comps)):
            for j in range(i + 1, len(comps)):
                w0, (qa, pla, ia), (qb, plb, ib) = _nearest(comps[i], comps[j])
                if w0 > S0:                 # only parts set tight (white under a stem) can run together
                    continue
                target = w0 * keep
                if not list(grown[i].contours) or not list(grown[j].contours):
                    continue
                touch = list(_sop(grown[i], grown[j], pathops.PathOp.INTERSECTION).contours)
                w1 = 0.0 if touch else _nearest(grown[i], grown[j])[0]
                if w1 >= target - 0.5:
                    continue
                bi, bj = comps[i].bounds, comps[j].bounds
                in_a = bi[0] >= bj[0] and bi[2] <= bj[2] and bi[1] >= bj[1] and bi[3] <= bj[3]
                in_b = bj[0] >= bi[0] and bj[2] <= bi[2] and bj[1] >= bi[1] and bj[3] <= bi[3]
                L = ((qb[0] - qa[0]) ** 2 + (qb[1] - qa[1]) ** 2) ** 0.5 or 1.0
                d = ((qb[0] - qa[0]) / L, (qb[1] - qa[1]) / L)          # from part i towards part j
                sa, sb = _stroke(comps[i]), _stroke(comps[j])
                ka = _convexity(pla, ia, ink_left, 0.25 * S0); kb = _convexity(plb, ib, ink_left, 0.25 * S0)
                ax_a = _near_axis(pla, ia, 1.5 * sa); ax_b = _near_axis(plb, ib, 1.5 * sb)
                end_a = ka * 0.7 * sa > 1 and ax_a[0] * d[0] + ax_a[1] * d[1] > 0.8
                end_b = kb * 0.7 * sb > 1 and -(ax_b[0] * d[0] + ax_b[1] * d[1]) > 0.8
                if in_a or in_b:
                    inner, outer = (i, j) if in_a else (j, i)
                    A = grown[inner]; b_ = A.bounds; c = ((b_[0] + b_[2]) / 2, (b_[1] + b_[3]) / 2)
                    lo_, hi_ = 0.6, 1.0
                    for _ in range(10):
                        f = (lo_ + hi_) / 2
                        B = A.transform(f, 0, 0, f, c[0] * (1 - f), c[1] * (1 - f))
                        if list(_sop(B, _soff(grown[outer], target, target), pathops.PathOp.INTERSECTION).contours):
                            hi_ = f
                        else:
                            lo_ = f
                    grown[inner] = A.transform(lo_, 0, 0, lo_, c[0] * (1 - lo_), c[1] * (1 - lo_))
                elif end_a or end_b:
                    cut, other = (i, j) if end_a else (j, i)
                    _s = _shorten(grown[cut], grown[other], target, ry, rx)
                    if list(_s.contours) and abs(_s.area) > 0.5 * abs(grown[cut].area):
                        grown[cut] = _s
                else:
                    mv, st = (i, j) if abs(_cx(comps[i]) - gx) > abs(_cx(comps[j]) - gx) else (j, i)
                    sgn = 1.0 if _cx(comps[mv]) > _cx(comps[st]) else -1.0
                    dx = sgn * (target - w1) / max(abs(d[0]), 0.5)
                    c0 = _cx(comps[mv])
                    for k_ in range(len(comps)):
                        if (_cx(comps[k_]) - c0) * sgn >= -0.5:
                            grown[k_] = grown[k_].transform(1, 0, 0, 1, dx, 0)
    out = grown[0]
    for q in grown[1:]:
        out = _sop(out, q, pathops.PathOp.UNION)
    return out


# ------------------------------------------------------------------ small-glyphs 2026-09-28: no new counters
# The pen may close the mouth of a narrow notch and shut the white behind it in. ð at 800-900: the
# channel between its crossbar and the bowl top (open to the left, a hairline at 700) closed at its mouth
# and left a sliver of white inside (1340 units² at 800, 360 at 900) — a third contour and a pinhole at
# text sizes. Dilation only ever takes white away, so any white that is enclosed after it but was not a
# counter at the master (it lies entirely in what was outside) is such a closed notch: it is filled, as
# the notch fills with ink everywhere else along it. Counters of the master, however far they shrink or
# split, are kept (grow() already holds them open). It runs inside grow(), on each part before
# grow_parts() moves any part, so a kept counter always lies over its own master counter.
def fill_new_counters(out, master):
    """Fill every hole of `out` that does not overlap a hole of `master` (same coordinates)."""
    cs = list(out.contours)
    if len(cs) < 2:
        return out, []
    big = max(cs, key=lambda c: abs(c.area))
    mcs = list(master.contours)
    mbig = max(mcs, key=lambda c: abs(c.area)) if mcs else None
    old = pathops.Path()
    for c in mcs:
        if c.clockwise != mbig.clockwise:
            h = pathops.Path(); h.addPath(c); h.simplify()
            old = _sop(old, h, pathops.PathOp.UNION) if list(old.contours) else h
    filled = []
    for c in cs:
        if c.clockwise == big.clockwise:
            continue
        h = pathops.Path(); h.addPath(c); h.simplify()
        if list(old.contours) and abs(_sop(h, old, pathops.PathOp.INTERSECTION).area) > 0.5:
            continue                                  # (part of) a counter the master already had
        filled.append(abs(h.area))
        out = _sop(out, h, pathops.PathOp.UNION)
    if filled:
        out.simplify()
    return out, filled


# ------------------------------------------------------------------ width outside the axis
# The pen widens a glyph as it dilates and narrows it as it erodes. Quicksand does the same for almost every glyph, but
# draws a few narrower as they get heavier (C Æ Œ Q: C's ink 575 at 300, 559 at 700), and there the pen turns the trend
# round at the axis ends: C was narrower at 800 than at 900, and at 100 than at 200. Those glyphs follow their own
# 300 -> 700 ink-width trend instead: grown with a pen widened across, then compressed across about the ink's middle
# to the trend's width, so the stems still come out at S.
def _follow_width(p, master, t, dS, ry, S0, S1, zmap):
    """p grown from master; returns p, or the glyph at its own trend width where the parent narrows it with weight."""
    if not t or t[LO][0] is None or not list(p.contours):
        return p
    (l3, r3, a3), (l7, r7, a7) = t[LO], t[HI]
    w3, w7 = a3 - l3 - r3, a7 - l7 - r7
    if w7 >= w3:
        return p
    b0 = master.bounds; W0 = b0[2] - b0[0]
    Wt = W0 + (w7 - w3) / 80 * dS
    if Wt <= S1 * 1.5:
        return p
    rx = (W0 * S1 - Wt * S0) / (2 * (Wt - S1))           # k (W0 + 2 rx) = Wt and k (S0 + 2 rx) = S1
    q = _map(grow_parts(master, rx, ry, S0, S1), zmap); q.simplify()
    b = q.bounds; kx = Wt / (b[2] - b[0]); cx = (b[0] + b[2]) / 2
    return q.transform(kx, 0, 0, 1, cx * (1 - kx), 0)


# ------------------------------------------------------------------ the thinnest stroke below the axis
# Eroding takes the same pen off every stroke, so a part that Quicksand already draws thin (the tapering tails of } and
# £) goes down to a hairline at 100-200. Such a part grows back by up to 0.25 S a side, never past the master's own
# outline, so no stroke is much thinner than 0.8 S.
def _min_stroke(p, limit, S1):
    t = 0.4 * S1
    opened = _soff(_soff(p, -t, -t), t, t)
    thin = _sop(p, opened, pathops.PathOp.DIFFERENCE)
    parts = pathops.Path()
    for c in thin.contours:
        if abs(c.area) > (0.3 * S1) ** 2:
            parts.addPath(c)
    if not list(parts.contours):
        return p
    parts.simplify()
    grown = _sop(_soff(parts, 0.25 * S1, 0.25 * S1), limit, pathops.PathOp.INTERSECTION)
    out = _sop(p, grown, pathops.PathOp.UNION); out.simplify()
    if len(list(out.contours)) != len(list(p.contours)):
        return p                                   # never a new piece or a new hole (g at 200: a speck by its ear)
    return out


def _circle(cx, cy, r):
    k = 0.5522847 * r
    p = pathops.Path()
    p.moveTo(cx + r, cy)
    p.cubicTo(cx + r, cy + k, cx + k, cy + r, cx, cy + r)
    p.cubicTo(cx - k, cy + r, cx - r, cy + k, cx - r, cy)
    p.cubicTo(cx - r, cy - k, cx - k, cy - r, cx, cy - r)
    p.cubicTo(cx + k, cy - r, cx + r, cy - k, cx + r, cy)
    p.close()
    return p


def round_dots(p, S):
    """A dot the pin rule cannot find (|w - h| >= 0.25 max, the test in build_font.split_dot) becomes a
    circle as wide as the dot, standing where it stood (on the baseline, or on its own centre)."""
    cs = list(p.contours)
    if not cs: return p, 0
    big = max(cs, key=lambda c: abs(c.area))
    out = pathops.Path(); n = 0
    for c in cs:
        x0, y0, x1, y1 = c.bounds; w, h = x1 - x0, y1 - y0
        dot = (c.clockwise == big.clockwise and w < max(1.4 * S, 160) and h < 1.6 * w
               and abs(c.area) > 0.7 * w * h and len(cs) <= 3)
        if dot and abs(w - h) >= 0.25 * max(w, h):
            r = w / 2
            out.addPath(_circle((x0 + x1) / 2, y0 + r if y0 < 20 else (y0 + y1) / 2, r)); n += 1
        else:
            out.addPath(c)
    out.simplify()
    return out, n


# ------------------------------------------------------------------ Quicksand and its spacing trend
@lru_cache(maxsize=None)
def _qs(src, w):
    return instantiateVariableFont(TTFont(src), {"wght": w})


@lru_cache(maxsize=None)
def _trend(src):
    """Per glyph at 300 and 700: (lsb, rsb, advance) of the ink (None for empty glyphs)."""
    t = {}
    for w in (LO, HI):
        f = _qs(src, w); gs = f.getGlyphSet(); hm = f["hmtx"].metrics
        for n in f.getGlyphOrder():
            p = _path(gs, n); adv = hm[n][0]
            b = p.bounds if list(p.contours) else None
            t.setdefault(n, {})[w] = (b[0] if b else None, adv - b[2] if b else None, adv)
    return t


def _split(p):
    """(rest, dots, tail): the round dots of a dotted glyph (fill > 0.8, not taller than 1.6 x wide),
    and the comma tail of , ; (the lowest non-dot contour)."""
    rest = pathops.Path(); dots = []; other = []
    cs = list(p.contours)
    big = max(cs, key=lambda c: abs(c.area)) if cs else None
    for c in cs:
        x0, y0, x1, y1 = c.bounds; w, h = x1 - x0, y1 - y0
        if c.clockwise == big.clockwise and w < 160 and h < 1.6 * w and abs(c.area) > 0.8 * w * h:
            dots.append(c)
        else:
            other.append(c)
    for c in other: rest.addPath(c)
    rest.simplify()
    dots.sort(key=lambda c: (round(c.bounds[1] + c.bounds[3]), c.bounds[0]))
    return rest, dots


@lru_cache(maxsize=None)
def _dot_trend(src):
    """Per dotted glyph at 300 and 700: [(cx, cy, w, h)] of its dots, and the height of a comma tail.
    Dots and tails follow the parent's own growth (the i dot grows 0.36 per unit of stem, a pen would
    give 0.5; the comma lengthens 1.1 per unit), not the pen."""
    t = {}
    for w in (LO, HI):
        f = _qs(src, w); gs = f.getGlyphSet(); cm = f.getBestCmap()
        for ch in DOTTED + ",":
            n = cm.get(ord(ch))
            if not n: continue
            rest, dots = _split(_path(gs, n))
            bb = [c.bounds for c in dots]
            tail = rest.bounds[3] - rest.bounds[1] if ch in ",;" and list(rest.contours) else None
            t.setdefault(n, {})[w] = ([((b[0] + b[2]) / 2, (b[1] + b[3]) / 2, b[2] - b[0], b[3] - b[1]) for b in bb], tail)
    return t


def _lin(a, b, dS, base):
    """Quicksand's value at the base master, moved along its own 300 -> 700 slope by dS."""
    return (a if base == LO else b) + (b - a) / 80 * dS


def _rebuild_dotted(src, name, ch, p_base, rx, ry, zmap, dS, base, S, m=None):
    """Dotted glyphs: the pen works on the rest only; dots are rescaled and moved along Quicksand's
    own trend; a comma tail keeps the parent's length trend; the white above a dot never closes."""
    rest, dots = _split(p_base)
    tr = _dot_trend(src).get(name)
    tail_w = rest.bounds[2] - rest.bounds[0] if list(rest.contours) else 1.0
    if list(rest.contours):
        rest = _map(offset(rest, rx, ry), zmap); rest.simplify()
    if ch in ",;" and tr and tr[LO][1] and list(rest.contours):
        x0, y0, x1, y1 = rest.bounds
        # at least 1.36 x its width: a Black comma as wide as Quicksand's trend makes it would read as
        # a round dot to build_font's pin rule (|w - h| < 0.25 h) and turn into a pin
        f = 0.0
        if base == HI:                                # 251/189 = 1.33 at 700, eased to 1.36 by 800
            f0 = tr[HI][1] / tail_w
            f = f0 + (1.36 - f0) * min(1.0, dS / 30)
        k = max(_lin(tr[LO][1], tr[HI][1], dS, base), f * (x1 - x0)) / (y1 - y0)
        rest = rest.transform(1, 0, 0, k, 0, y1 * (1 - k))          # the tail keeps its top
    dps = []
    follow = tr and len(tr[LO][0]) == len(dots) == len(tr[HI][0])
    for i, c in enumerate(dots):
        q = pathops.Path(); q.addPath(c)
        if follow:
            cx, cy, w, h = (_lin(a, b, dS, base) for a, b in zip(tr[LO][0][i], tr[HI][0][i]))
            x0, y0, x1, y1 = c.bounds; sx, sy = w / (x1 - x0), h / (y1 - y0)
            q = q.transform(sx, 0, 0, sy, cx - sx * (x0 + x1) / 2, cy - sy * (y0 + y1) / 2)
        else:
            q = _map(offset(q, rx, ry), zmap)
        x0, y0, x1, y1 = q.bounds; w, h = x1 - x0, y1 - y0
        if abs(w - h) >= 0.25 * max(w, h):             # the pin rule only finds round dots
            q = _circle((x0 + x1) / 2, y0 + w / 2 if y0 < 20 else (y0 + y1) / 2, w / 2)
        dps.append(q)
    # ! ? : the dot under the stroke keeps at least 0.2 s of white, or build_font cannot find it.
    # Lift the stroke's lower end (as build_font does for ?'s tail).
    if ch in "!?" and dps and list(rest.contours):
        yb = rest.bounds[1]; need = max(q.bounds[3] for q in dps) + 0.2 * S
        if yb < need:
            cut = yb + 0.5 * S + 30; big = 1e4
            low = pathops.op(rest, _rect(-big, -big, big, cut), pathops.PathOp.INTERSECTION)
            up = pathops.op(rest, _rect(-big, cut, big, big), pathops.PathOp.INTERSECTION)
            rest = pathops.op(up, low.transform(1, 0, 0, 1, 0, need - yb), pathops.PathOp.UNION)
    # ? above 700: build_font brings the hook from the ascender down to the cap height by cutting the
    # tail's straight part, which a Black ? no longer has (pin + gap + hook fill the cap height).
    # Bring it down here instead, by squeezing the hook, eased in over the first 30 units of stem
    # so the build's own cut takes the rest just past 700.
    # Its tail must also clear the pin build_font will put under it (pin r = 1.246 x the i dot's
    # radius, white = 0.738 x the i dot's own gap — build_font's PIN_K, GAP_K), or the build cuts the
    # tail through the hook's lower arm.
    if ch == "?" and base == HI and list(rest.contours) and m is not None:
        yb, top = rest.bounds[1], rest.bounds[3]
        e = min(1.0, dS / 30)
        it = _dot_trend(src).get("i")
        need = yb
        if it:
            cx, cy, w, h = (_lin(a, b, dS, base) for a, b in zip(it[LO][0][0], it[HI][0][0]))
            need = 2 * (78.5 / 63.0) * (w / 2) + (48.0 / 65.0) * (cy - h / 2 - m["XH"]) - (m["XO"] - m["XH"])
        nb = yb + max(0.0, need - yb) * e; nt = top - max(0.0, top - CAP) * e
        if nb > yb + 0.5 or nt < top - 0.5:
            k = (nt - nb) / (top - yb)
            rest = rest.transform(1, 0, 0, k, 0, nb - k * yb)
    out = pathops.Path(rest)
    for q in dps: out.addPath(q)
    out.simplify()
    return out


def _rect(x0, y0, x1, y1):
    p = pathops.Path()
    p.moveTo(x0, y0); p.lineTo(x1, y0); p.lineTo(x1, y1); p.lineTo(x0, y1); p.close()
    return p


def _write(font, name, p, adv):
    pen = TTGlyphPen(None)
    p.draw(Cu2QuPen(pen, max_err=0.25, reverse_direction=False))
    # keep the coordinates fractional: build_font reads the outlines through pathops and never compiles
    # this font, and rounding each short arc of a round join to the unit grid makes little kinks
    g = pen.glyph(round=lambda v: round(v, 2))
    font["glyf"][name] = g
    g.recalcBounds(font["glyf"])
    font["hmtx"][name] = (max(0, int(round(adv))), int(g.xMin) if g.numberOfContours else 0)


def _class(font):
    cm = font.getBestCmap()
    by = {}
    for u, n in cm.items():
        by.setdefault(n, chr(u))
    return by


# ------------------------------------------------------------------ the one entry point
def instance(src, wght):
    """Quicksand-derived TTFont at any wght 100-900 (outlines, advances, side bearings in hmtx)."""
    w = float(wght)
    if not 100 <= w <= 900:
        raise ValueError(f"wght {wght} outside 100-900")
    m = metrics(w)
    wq = round(m["wq"], 6)                   # lin: the Quicksand instance whose stem is S (limn 700 = 700)
    if LO <= wq <= HI:
        font = instantiateVariableFont(TTFont(src), {"wght": wq})    # Quicksand's own outlines
        _fix_dots(font, m["S"])
        return font
    base = LO if wq < LO else HI
    mb = metrics_of(qs_stem(base), base)     # lin: the master's own targets
    font = instantiateVariableFont(TTFont(src), {"wght": base})
    gs = font.getGlyphSet()
    chars = _class(font)
    rx = (m["S"] - mb["S"]) / 2
    # horizontal edges move out by ry and the zone map then scales the x-height band by
    # XH / (XH_base + 2 ry): pick ry so o's horizontal lands on H(w) after both
    ry = (m["H"] * mb["XH"] / m["XH"] - mb["H"]) / (1 - m["H"] / m["XH"]) / 2
    dS = m["S"] - mb["S"]
    trend = _trend(src)
    # proof audit 2026-09-27 (C-03): past 700 the straight-line trend runs the small side bearings of
    # diagonal and round-ended letters below zero (A -15, x -10, W -3, ( ) 0 at 900: AA xx KW () touch).
    # Above the axis no side bearing shrinks faster than n's do (x 0.89 at 800, 0.70 at 900).
    n_name = font.getBestCmap().get(ord("n"))
    SB_K = 1.0
    if base == HI and n_name in trend:
        (nl3, nr3, _), (nl7, nr7, _) = trend[n_name][LO], trend[n_name][HI]
        SB_K = (nl7 + nr7 + (nl7 - nl3 + nr7 - nr3) / 80 * dS) / (nl7 + nr7)
    new = {}
    kpen = _pen_k(src)                                     # wcons: symbols follow their own stroke trend
    tt = _path(gs, font.getBestCmap()[ord("t")]).bounds[3]  # wcons: the t height is a zone too (650)
    for name in font.getGlyphOrder():
        p = _path(gs, name)
        ch = chars.get(name, "")
        lower = ch in LOWER or name.split(".")[0] in LOWER
        if list(p.contours):
            top = "XH" if lower else "CAP"
            if lower:      # wcons: + the t height, held like the other lines (t 645 at 100, 655 at 900 before)
                zmap = _piecewise([mb["DESC"] - ry, -ry, mb[top] + ry, tt + ry, mb["ASC"] + ry], [m["DESC"], 0, m[top], tt, m["ASC"]])
            else:
                zmap = _piecewise([mb["DESC"] - ry, -ry, mb[top] + ry, mb["ASC"] + ry], [m["DESC"], 0, m[top], m["ASC"]])
            if ch and ch in DOTTED + ",":
                p = _rebuild_dotted(src, name, ch, p, rx, ry, zmap, dS, base, m["S"], m)
            else:
                k = kpen.get(name, 1.0)
                p0 = p
                p = _map(grow_parts(p0, rx * k, ry * k, mb["S"], m["S"]), zmap); p.simplify()
                if k == 1.0:
                    p = _follow_width(p, p0, trend.get(name), dS, ry, mb["S"], m["S"], zmap)
                if base == LO:
                    p = _min_stroke(p, _map(p0, zmap), m["S"])
        t = trend.get(name)
        if t and t[LO][0] is not None and list(p.contours):
            (l3, r3, _), (l7, r7, _) = t[LO], t[HI]
            lb, rb, _ = t[base]
            lsb = lb + (l7 - l3) / 80 * dS; rsb = rb + (r7 - r3) / 80 * dS
            if SB_K < 1.0:
                lsb = max(lsb, lb * SB_K) if lb > 0 else lsb
                rsb = max(rsb, rb * SB_K) if rb > 0 else rsb
            if base == LO:          # below the axis a side bearing under zero goes no further under than the master's (£ at 100)
                lsb, rsb = max(lsb, min(0.0, lb)), max(rsb, min(0.0, rb))
            x0, _, x1, _ = p.bounds
            p = p.transform(1, 0, 0, 1, lsb - x0, 0)
            adv = lsb + (x1 - x0) + rsb
        elif t:
            adv = t[base][2] + (t[HI][2] - t[LO][2]) / 80 * dS
        else:
            adv = font["hmtx"][name][0]
        new[name] = (p, adv)
    for name, (p, adv) in new.items():       # after every read, since composites draw their parts
        _write(font, name, p, adv)
    return font


def _fix_dots(font, S):
    gs = font.getGlyphSet(); cm = font.getBestCmap(); fixes = {}
    for ch in DOTTED:
        name = cm.get(ord(ch))
        if not name: continue
        p, n = round_dots(_path(gs, name), S)
        if n: fixes[name] = (p, font["hmtx"][name][0])
    for name, (p, adv) in fixes.items():
        _write(font, name, p, adv)
