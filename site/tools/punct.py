"""limn punctuation and symbols — one system, built from the brand metrics.

Called by build_font.py right after the pin stage:

    PUNCT_OUT = apply_punct(G, m)        # m: S XH XO CAP ASC DESC PIN_R GAP OSH (+ Q_DOT_R)
    ...
    punct_kern(KERN, G)                  # after KERN_FIX, before the pin clearance pass

Everything below is a rule on the metrics (y up, font units), so it holds at every weight:

  AX     maths axis = centre of the parent's own hyphen (306.5 at 700 = 0.573 XH; references 0.54–0.63).
         - – — · + − = < > × ÷ ~ and the brackets' centre all sit on it.
  T      bar weight = the stem S (the parent's hyphen is 119 against 120 at 700; past the parent's axis its hyphen is
         extrapolated apart from the stem, 26 against 20 at 100). Every dash, operator bar and arrow uses it.
  pin    every dot-like element is the pin (PIN_R), with GAP white to any stroke next to it.
  ends   every free stroke end is round (round caps); the only flat ends stay the feet in build_font.
  QT QB  quote band: top = the i pin top (= ASC at 700), bottom = QT − comma height (465 at 700 =
         0.87 XH; refs 0.76–1.00). Every quote, curly or straight, fills this band.

Options (environment, defaults = recommendation):
  LIMN_COMMA  A (tapered tail tangent to the pin) | B (straight round-capped stroke) | C (monoline hook)
  LIMN_EXCL   cap (! top on the cap height) | asc (i turned exactly: top on the ascender)
  LIMN_AT     1 | 2 | 3 (see the "@ &" block below; A, B = the earlier @, kept for comparison)
  LIMN_AMP    1 | 2 | 3 (see the "@ &" block below; orig = Quicksand's own &)
  LIMN_QUOTE  wedge (' " are ink wedges) | pin (' " are a pin with a straight tail)
  LIMN_PUNCT_DUMP=path   also write every option's glyphs as JSON (for punct.html)
"""
import json
import math
import os

import pathops

OPT = {
    "comma": os.environ.get("LIMN_COMMA", "A"),
    "excl": os.environ.get("LIMN_EXCL", "cap"),
    "at": os.environ.get("LIMN_AT", "1"),        # @ & redesign 2026-09-27 (atq.html): default = recommendation
    "amp": os.environ.get("LIMN_AMP", "A"),     # SYM 2026-09-27 (symbols.html): A; 1 = the earlier &
    "quote": os.environ.get("LIMN_QUOTE", "wedge"),
}
ST = {}          # module state shared by apply_punct and punct_kern
KERN_LOG = []    # what punct_kern did, for the report


# ---------------------------------------------------------------- geometry
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


def _rect(x0, y0, x1, y1):
    p = pathops.Path()
    p.moveTo(x0, y0); p.lineTo(x1, y0); p.lineTo(x1, y1); p.lineTo(x0, y1); p.close()
    return p


def _op(a, b, op):
    return pathops.op(a, b, op)


def _union(*ps):
    out = ps[0]
    for q in ps[1:]:
        out = _op(out, q, pathops.PathOp.UNION)
    return out


def _diff(a, b):
    return _op(a, b, pathops.PathOp.DIFFERENCE)


def _inter(a, b):
    return _op(a, b, pathops.PathOp.INTERSECTION)


def _xf(p, a=1, b=0, c=0, d=1, e=0, f=0):
    return p.transform(a, b, c, d, e, f)


def _empty(p):
    return not list(p.contours)


def _stroked(p, w):
    p.stroke(w, pathops.LineCap.ROUND_CAP, pathops.LineJoin.ROUND_JOIN, 4)
    p.convertConicsToQuads()
    p.simplify()
    return p


def line(pts, w):
    """Monoline stroke through points, round caps and joins."""
    p = pathops.Path(); p.moveTo(*pts[0])
    for q in pts[1:]:
        p.lineTo(*q)
    return _stroked(p, w)


def bez(p0, c1, c2, p3, t):
    u = 1 - t
    return (u ** 3 * p0[0] + 3 * u * u * t * c1[0] + 3 * u * t * t * c2[0] + t ** 3 * p3[0],
            u ** 3 * p0[1] + 3 * u * u * t * c1[1] + 3 * u * t * t * c2[1] + t ** 3 * p3[1])


def curve(p0, c1, c2, p3, w):
    p = pathops.Path(); p.moveTo(*p0); p.cubicTo(*c1, *c2, *p3)
    return _stroked(p, w)


def arc_pts(cx, cy, r, a0, a1, n=48):
    """Points on a circle from angle a0 to a1 (degrees, counter-clockwise when a1 > a0)."""
    return [(cx + r * math.cos(math.radians(a0 + (a1 - a0) * i / n)), cy + r * math.sin(math.radians(a0 + (a1 - a0) * i / n)))
            for i in range(n + 1)]


def hull2(c0, r0, c1, r1):
    """Two circles and the band tangent to both (a tapered stroke with round ends)."""
    dx, dy = c1[0] - c0[0], c1[1] - c0[1]; d = math.hypot(dx, dy)
    if d <= abs(r0 - r1) + 1e-6:
        return _circle(*(c0 if r0 >= r1 else c1), max(r0, r1))
    ux, uy = dx / d, dy / d; nx, ny = -uy, ux
    s = (r0 - r1) / d; c = math.sqrt(max(0.0, 1 - s * s))
    q = pathops.Path()
    pts = []
    for sign in (1, -1):
        vx, vy = nx * c * sign + ux * s, ny * c * sign + uy * s
        pts.append(((c0[0] + r0 * vx, c0[1] + r0 * vy), (c1[0] + r1 * vx, c1[1] + r1 * vy)))
    (a0, a1), (b0, b1) = pts
    q.moveTo(*a0); q.lineTo(*a1); q.lineTo(*b1); q.lineTo(*b0); q.close()
    out = _union(q, _circle(*c0, r0), _circle(*c1, r1)); out.simplify()
    return out


def sweep(pts, radii):
    """A tapered stroke: the round-ended band through points with a radius at each point."""
    out = hull2(pts[0], radii[0], pts[1], radii[1])
    for i in range(1, len(pts) - 1):
        out = _union(out, hull2(pts[i], radii[i], pts[i + 1], radii[i + 1]))
    out.simplify()
    return out


def rot180(p, cx, cy):
    return _xf(p, -1, 0, 0, -1, 2 * cx, 2 * cy)


# ================================================================ @ & Q redesign (2026-09-27, atq.html)
# The three glyphs are drawn as monoline strokes on centrelines set by the metrics, so they hold at
# every weight. Three rules shared with the rest of limn:
#   pen    the family's own pen: as wide as the stem, as tall as the o's horizontal stroke (Quicksand's
#          contrast, 0.92 at 700, 1.00 at 100, 0.75 at 900) — a round pen would draw the horizontals
#          of @ & Q heavier than every o and O next to them at 800-900
#   joins  every joint and crossing is round: a morphological closing of radius FILLET·min(S, 120),
#          the radius build_font gives its straight-corner fillets
#   ends   every free end is the pen's round cap
def atq_contrast(p):
    """(vertical stroke, horizontal stroke) of a round letter: its left side at mid-height, its top."""
    x0, y0, x1, y1 = p.bounds; my, mx = (y0 + y1) / 2, (x0 + x1) / 2
    side = sorted((c.bounds for c in _inter(p, _rect(-1e4, my - 0.5, 1e4, my + 0.5)).contours), key=lambda b: b[0])
    cap_ = sorted((c.bounds for c in _inter(p, _rect(mx - 0.5, -1e4, mx + 0.5, 1e4)).contours), key=lambda b: -b[3])
    return side[0][2] - side[0][0], cap_[0][3] - cap_[0][1]


def pen_line(pts, SV, SH):
    """Monoline stroke through points with an elliptical pen SV wide and SH tall (round caps and joins)."""
    k = SH / SV
    p = pathops.Path(); p.moveTo(pts[0][0], pts[0][1] / k)
    for x, y in pts[1:]:
        p.lineTo(x, y / k)
    return _xf(_stroked(p, SV), d=k)


def _band(p, r):
    q = pathops.Path(p); q.stroke(2 * r, pathops.LineCap.ROUND_CAP, pathops.LineJoin.ROUND_JOIN, 4)
    q.convertConicsToQuads()
    return q


def round_joins(p, r):
    """Closing of radius r: every concave corner (joint, crossing) becomes a fillet of radius r; convex
    outlines are unchanged. Whites narrower than 2r would close, so r stays under the glyph's whites."""
    if r < 0.5:
        return p
    try:
        dil = _union(p, _band(p, r))
        out = _diff(dil, _band(dil, r)); out.simplify()
        return out
    except pathops.PathOpsError:
        return p


def bez_pts(p0, c1, c2, p3, n=24):
    return [bez(p0, c1, c2, p3, i / n) for i in range(n + 1)]


def ell_pts(cx, cy, a, b, t0, t1, n=48):
    """Points on an ellipse (degrees, counter-clockwise when t1 > t0)."""
    return [(cx + a * math.cos(math.radians(t0 + (t1 - t0) * i / n)), cy + b * math.sin(math.radians(t0 + (t1 - t0) * i / n)))
            for i in range(n + 1)]


def ell_tan(a, b, t):
    """Unit counter-clockwise tangent of an ellipse at angle t (degrees)."""
    vx, vy = -a * math.sin(math.radians(t)), b * math.cos(math.radians(t)); L = math.hypot(vx, vy)
    return vx / L, vy / L


def _chain(*parts):
    out = []
    for q in parts:
        out += q if not out else q[1:]
    return out


def _clear(p_end, pts, need):
    return min(math.hypot(p_end[0] - x, p_end[1] - y) for x, y in pts) >= need


def amp_glyph(M, G, kind):
    """& on the metrics. Height: O's own (CAP + overshoot down to −overshoot); width a share of O's.
      1  et-ligature: a closed upper loop, the stroke crosses itself at the neck and runs as a diagonal
         to a round tail on the baseline; the bowl rises on the right to a round arm end.
      2  open et (the parent's skeleton): the upper hook stays open (round end at two o'clock); one
         smooth stroke runs from it over the top, down the left into the bowl and up to the arm end;
         the diagonal parts from the hook's left side and crosses the arm to the round tail.
      3  Et, simplified: an epsilon whose waist runs on as the bar of a t; a short upright crosses the
         bar. No self-crossing.
    Above 700 the pen is lightened to 0.84 at 900 and the glyph widened by 0.4 (S − 120). The arm end
    drops (to 0.36 of the height at most) where it would come closer than GAP to the upper loop."""
    S, XH, CAP, OSH, GAP = M["S"], M["XH"], M["CAP"], M["OSH"], M["GAP"]
    SV, SH = M["PEN"]
    # above 700 the & draws a little lighter (0.84 of the pen at 900) and a little wider, as every
    # reference does (& stroke 0.81-0.93 s): four strokes stacked in the cap height leave no counter
    # at the full pen
    f = 1 - 0.16 * min(1.0, max(0.0, (S - 120) / 80))
    SV, SH = SV * f, SH * f
    Wo = M["O_W"]
    Wd = {"1": 0.93, "2": 0.95, "3": 0.90}[kind] * Wo + 0.4 * max(0.0, S - 120)
    xl, xr = SV / 2, Wd - SV / 2; w = xr - xl
    yb, yt = M["O_B"] + SH / 2, M["O_T"] - SH / 2; Hc = yt - yb          # O's own top and bottom (overshoots)
    strokes, info = [], ""
    if kind in "12":
        # upper loop: an ellipse on the top line, never narrower than one pen + 0.7 S of counter
        if kind == "1":
            ua = max(0.21 * w, 0.5 * SV + 0.44 * S); ub = max(0.21 * Hc, 0.5 * SH + 0.40 * S)
            ux, uy = xl + 0.08 * w + ua, yt - ub
        else:   # the open hook is larger: its counter is closed by the diagonal, not by its own bottom
            ua = max(0.25 * w, 0.5 * SV + 0.5 * S); ub = max(0.30 * Hc, 0.5 * SH + 0.5 * S)
            ux, uy = xl + 0.06 * w + ua, yt - ub
        L = lambda t: (ux + ua * math.cos(math.radians(t)), uy + ub * math.sin(math.radians(t)))
        # bowl: from the left, round the bottom, up the right to the arm end at half the height; it is
        # narrower than the glyph, so the tail runs out past it (the parent's proportions)
        # the arm ends at half the height, lower if needed to keep GAP (plus the round-join radius, so
        # the closing does not bridge it) from the loop above it
        loop_pts = ell_pts(ux, uy, ua, ub, -90, 90, 36)
        ya = yb + 0.50 * Hc; xa = xl + 0.84 * w
        while ya > yb + 0.36 * Hc and not _clear((xa, ya), loop_pts, SV + GAP + 2 * M["FR"]):
            ya -= 2
        A = (xa, ya); B = (xl + 0.42 * w, yb); Lf = (xl, yb + 0.28 * Hc)
        E = (xr, yb)                                          # tail end: its round cap on the overshoot line
        bowl = _chain(bez_pts(A, (A[0] + 0.02 * w, ya - 0.30 * Hc), (B[0] + 0.30 * w, yb), B),
                      bez_pts(B, (B[0] - 0.24 * w, yb), (xl, Lf[1] - 0.16 * Hc), Lf))

        def diag_to_E(t):
            P = L(t); tv = ell_tan(ua, ub, t); d = math.hypot(E[0] - P[0], E[1] - P[1])
            c35, s35 = math.cos(math.radians(35)), math.sin(math.radians(35))
            return bez_pts(P, (P[0] + tv[0] * 0.30 * d, P[1] + tv[1] * 0.30 * d), (E[0] - 0.30 * d * c35, E[1] + 0.30 * d * s35), E, 32)
        if kind == "1":
            t_in, t_out = -35, 236
            P_in = L(t_in); ti = ell_tan(ua, ub, t_in); d_in = math.hypot(P_in[0] - Lf[0], P_in[1] - Lf[1])
            rise = bez_pts(Lf, (xl, Lf[1] + 0.16 * Hc), (P_in[0] - ti[0] * 0.45 * d_in, P_in[1] - ti[1] * 0.45 * d_in), P_in)
            loop = ell_pts(ux, uy, ua, ub, t_in, t_out, 60)
            strokes.append(_chain(bowl, rise, loop, diag_to_E(t_out)))
            info = "닫힌 위 고리 · 목에서 교차 · 둥근 꼬리"
        else:
            # the parent's skeleton: the hook (round end at two o'clock) runs over the top and down its
            # left side straight on into the diagonal and the tail; the bowl branches off the hook's left
            # side, heading down and out to the left, round the bottom and up to the arm
            t_out, t_branch = 244, 204
            strokes.append(_chain(ell_pts(ux, uy, ua, ub, 16, t_out, 60), diag_to_E(t_out)))
            # leaving along the hook's own tangent, so its outer side runs on without an elbow
            J = L(t_branch); tj = ell_tan(ua, ub, t_branch); d = math.hypot(J[0] - Lf[0], J[1] - Lf[1])
            down = bez_pts(J, (J[0] + tj[0] * 0.12 * d, J[1] + tj[1] * 0.12 * d), (xl, Lf[1] + 0.30 * d), Lf)
            strokes.append(_chain(down, list(reversed(bowl))))
            info = "열린 위 갈고리(부모의 뼈대) · 몸통이 갈고리 왼쪽에서 갈라짐 · 사선이 팔과 교차"
    else:
        # epsilon + t: the waist runs on as the t's bar; a short upright crosses it. The upright keeps
        # SV + GAP (centre to centre) from both ends of the epsilon — at heavy weights the glyph widens
        # for it instead of the upright shrinking to a knob
        yw = yb + 0.50 * Hc
        au = max(0.24 * w, 0.5 * SV + 0.3 * S); hu = (yt - yw) / 2
        al = max(0.31 * w, 0.5 * SV + 0.36 * S); hl = (yw - yb) / 2
        cu, cl = (xl + au, yw + hu), (xl + al, yb + hl)
        tu, tl = 38, 324
        upper = ell_pts(*cu, au, hu, tu, 270, 50)                 # from the top end round to the waist
        lower = ell_pts(*cl, al, hl, 90, tl, 50)                  # from the bar round to the bottom end
        h1 = 0.24 * Hc
        need = SV + GAP + 2 * M["FR"]
        ends = [upper[0], lower[-1]]
        xs = xl + 0.62 * w
        while not all(_clear((xs, yw + s_ * h1), ends, need) and _clear((xs, yw), ends, need) for s_ in (1, -1)):
            xs += 2
        bar_end = (xs + max(0.16 * w, 0.5 * SV + 0.25 * S), yw)
        strokes += [upper + [bar_end], lower, [(xs, yw + h1), (xs, yw - h1)]]
        info = f"ε + t · 폭 {(bar_end[0] + SV / 2) / Wo:.2f} O"
    p = _union(*[pen_line(s_, SV, SH) for s_ in strokes])
    # crossings here are acute (the diagonal over the arm): the full fillet radius piles ink into their
    # wedges (thickest point 1.55 × O at 700), so & takes half of it (1.3 ×, the references 1.04-1.32)
    p = round_joins(p, 0.5 * M["FR"])
    return p, info


# ================================================================ SYM · symbol classes (2026-09-27, symbols.html)
# Every non-letter glyph belongs to one metric class (table in symbols.html). The class sets its band
# (bottom and top line), its width relation and its pen; the glyphs below are built on those rules, so
# they hold at every weight 100-900.
#
#   pens   S      the stem: brackets, | / \ ¦, ! ?, ^ and the figures (a letter's own weight)
#          T      the bar: the stem S: dashes, the maths operators and the arrows
#          DENSE  a glyph that stacks three or more strokes across the cap height or pairs strokes side by
#                 side (& # « » ‹ ›) draws one step lighter (references 0.82-0.94 S at bold): 0.85 S at
#                 700, back towards S where the counters are wide (0.93 S at 400, 0.98 S at 100), 0.77 S
#                 at 900
#          LIGHT  (key "SUP") the small class: superior and fraction figures, ° ª º ™, the rings and
#                 letters of © ®, the bars of € ¥ ¢: 0.72 S at 700 (references 0.63-0.79 S), 0.86 S at
#                 400, 0.96 S at 100 — at the light end a mark lighter than the already thin stem read
#                 as a hairline ghost next to the letters —, 0.67 S at 900
#   whites WS = 0.06 CAP + 0.35 S inside small marks (¦ and fractions); « » 0.12 CAP + 0.05 S; the = sign
#          max(0.75 S, 0.16 PW)
#   every pen is the family's elliptical pen (o's contrast) with round ends; joints round (FR).
def sym_pens(M):
    S = M["S"]; k = M["PEN"][1] / M["PEN"][0]
    t_hi = min(1.0, max(0.0, (S - 120) / 80))
    dense = S * (1 - 0.15 * min(1.0, S / 120) - 0.11 * t_hi)
    sup = S * (1 - 0.28 * min(1.0, S / 120) - 0.06 * t_hi)     # 0.72 S at 700, 0.86 at 400, 0.96 at 100, 0.67 at 900
    return {"DENSE": (dense, dense * k), "SUP": (sup, sup * k), "k": k}


# & shape constants (shares of the glyph's centreline width w / height Hc): bowl's left extreme and
# bottom point, the diagonal's two handles and end angle, the loop's entry and exit angles
AMP_P = {"lf": 0.36, "bx": 0.42, "c1": 0.45, "c2": 0.30, "ang": 38, "tin": -38, "tout": 232}


def sym_white(M):
    """WS, the white inside a small mark: between the two chevrons of « », the two halves of ¦, a
    fraction's figures and its slash. 0.06 CAP + 0.35 S: 84 at 700, 48 at 100, 105 at 900 — a share of
    the stem alone (0.7 S) left 13 units at 100, and « ¦ ½ closed up at the light weights."""
    return 0.06 * M["CAP"] + 0.35 * M["S"]


def amp_sym(M, G, kind):
    """& on the cap-figure class: O's height (overshoots), 0.90 of O's width, the DENSE pen.
    The earlier & (LIMN_AMP 1) read squashed: its upper loop was 0.53 of the width with a counter of
    0.16 W (references 0.18-0.38, median 0.27), its bowl was a flat oval whose left side peaked at 0.28
    of the height, and the full pen closed both. Here the loop is sized from its counter, the bowl
    from the 8's lower bowl, and the pen is the dense-class pen.
      A  et, closed loop: the loop (outer 0.60 W, 0.46 H, counter >= 0.24 W) sits on the cap line; the
         stroke leaves its lower left as the diagonal to a round tail on the baseline and comes back
         in at its lower right from the bowl — an X at the neck, as in 8's waist (0.52 H).
      B  open hook (the parent's own skeleton): the loop stays open at two o'clock with a round end;
         the bowl branches off its left side.
      C  as A, with a straight arm: the bowl ends on its bottom right and a straight stroke rises from
         there at 70 degrees to 0.55 H — no curl beside the loop."""
    S, CAP, OSH, GAP = M["S"], M["CAP"], M["OSH"], M["GAP"]
    SV, SH = sym_pens(M)["DENSE"]
    Wo = M["O_W"]
    Wd = 0.90 * Wo + 0.3 * max(0.0, S - 120)
    xl, xr = SV / 2, Wd - SV / 2; w = xr - xl
    yb, yt = M["O_B"] + SH / 2, M["O_T"] - SH / 2; Hc = yt - yb; Ht = M["O_T"] - M["O_B"]
    # loop: outer 0.60 W wide (never a counter under 0.24 W), 0.46 of the height, left edge at 0.08 W
    LW = max(0.60 * Wd, 2 * SV + 0.24 * Wd) if kind != "B" else max(0.64 * Wd, 2 * SV + 0.30 * Wd)
    LH = (0.46 if kind != "B" else 0.52) * Ht
    ua, ub = (LW - SV) / 2, (LH - SH) / 2
    ux, uy = 0.08 * Wd + LW / 2, yt - ub
    L = lambda t: (ux + ua * math.cos(math.radians(t)), uy + ub * math.sin(math.radians(t)))
    loop_pts = ell_pts(ux, uy, ua, ub, -90, 90, 36)
    E = (xr, yb)                                             # tail end, round cap on the overshoot line
    # bowl: the 8's lower bowl — left extreme at 0.32 of the height, bottom point at 0.44 W
    Lf = (xl, yb + AMP_P["lf"] * Hc); B = (xl + AMP_P["bx"] * w, yb)
    need = SV + GAP + 2 * M["FR"]
    strokes = []
    if kind in "AB":
        ya = yb + 0.50 * Hc; xa = xl + 0.86 * w
        while ya > yb + 0.36 * Hc and not _clear((xa, ya), loop_pts, need):
            ya -= 2
        A = (xa, ya)
        arm = bez_pts(A, (A[0] + 0.01 * w, ya - 0.30 * Hc), (B[0] + 0.32 * w, yb), B)
    else:
        # straight arm: bowl bottom -> a point on the right at 0.14 H, then straight up at 70 degrees
        B2 = (xl + 0.76 * w, yb + 0.16 * Hc)
        ya = yb + 0.55 * Hc
        cot = 1 / math.tan(math.radians(70))
        while ya > yb + 0.36 * Hc and not _clear((B2[0] + (ya - B2[1]) * cot, ya), loop_pts, need):
            ya -= 2
        A = (B2[0] + (ya - B2[1]) * cot, ya)
        dl = 0.14 * Hc                                      # the arm runs on into the bowl without a corner
        arm = _chain([A, B2], bez_pts(B2, (B2[0] - dl * cot, B2[1] - dl), (B[0] + 0.24 * w, yb), B))
    bowl = _chain(arm, bez_pts(B, (B[0] - 0.26 * w, yb), (xl, Lf[1] - 0.20 * Hc), Lf))

    def diag_to_E(t):
        P = L(t); tv = ell_tan(ua, ub, t); d = math.hypot(E[0] - P[0], E[1] - P[1])
        c, s = math.cos(math.radians(AMP_P["ang"])), math.sin(math.radians(AMP_P["ang"]))
        return bez_pts(P, (P[0] + tv[0] * AMP_P["c1"] * d, P[1] + tv[1] * AMP_P["c1"] * d), (E[0] - AMP_P["c2"] * d * c, E[1] + AMP_P["c2"] * d * s), E, 32)
    if kind in "AC":
        t_in, t_out = AMP_P["tin"], AMP_P["tout"]
        P_in = L(t_in); ti = ell_tan(ua, ub, t_in); d_in = math.hypot(P_in[0] - Lf[0], P_in[1] - Lf[1])
        rise = bez_pts(Lf, (xl, Lf[1] + 0.20 * Hc), (P_in[0] - ti[0] * 0.42 * d_in, P_in[1] - ti[1] * 0.42 * d_in), P_in)
        strokes.append(_chain(bowl, rise, ell_pts(ux, uy, ua, ub, t_in, t_out, 60), diag_to_E(t_out)))
        info = "닫힌 고리 · 목에서 X" + (" · 곧은 팔" if kind == "C" else " · 둥근 팔")
    else:
        t_out, t_br = 244, 204
        strokes.append(_chain(ell_pts(ux, uy, ua, ub, 18, t_out, 60), diag_to_E(t_out)))
        J = L(t_br); tj = ell_tan(ua, ub, t_br); d = math.hypot(J[0] - Lf[0], J[1] - Lf[1])
        down = bez_pts(J, (J[0] + tj[0] * 0.12 * d, J[1] + tj[1] * 0.12 * d), (xl, Lf[1] + 0.30 * d), Lf)
        strokes.append(_chain(down, list(reversed(bowl))))
        info = "열린 갈고리(부모의 뼈대)"
    p = _union(*[pen_line(s_, SV, SH) for s_ in strokes])
    p = round_joins(p, 0.5 * M["FR"])
    # the numbers for the class table: loop counter width and the pen, in W and S
    return p, info + f" · 고리 속 {(LW - 2 * SV) / Wd:.2f} W · 펜 {SV / S:.2f} S · 폭 {Wd / CAP:.2f} CAP"


def sym_early(M, G, place, PW, h, gap_eq):
    """Axis class (± ¬ < > ~ « » ‹ › •), bracket band (¦) and descending class († ‡ § ¶), and #.
    Runs inside apply_punct after the maths block; `place` recentres on the parent's side bearings."""
    S, XH, CAP, OSH, AX, T, GAP = M["S"], M["XH"], M["CAP"], M["OSH"], M["AX"], M["T"], M["GAP"]
    BB, BT = M["BB"], M["BT"]
    DV, DH = sym_pens(M)["DENSE"]
    FR = M["FR"]
    WS = sym_white(M)
    out = {}
    # ---- axis class: every operator in the PW square on AX, bar pen T (round) ------------------------
    # < > : apex on the axis, open end 0.84 PW wide (ink), PW tall — the + 's square
    hh = (PW - T) / 2; cw = 0.84 * PW - T
    for ch, sgn in (("<", 1), (">", -1)):
        if ch in G:
            pts = [(sgn * cw / 2, AX + hh), (-sgn * cw / 2, AX), (sgn * cw / 2, AX - hh)]
            out[ch] = op_cell(M, line(pts, T))
    # ~ : one sine period across PW, amplitude 0.08 PW, on the axis
    if "~" in G:
        a = (PW - T) / 2; b = 0.08 * PW + 0.1 * T
        pts = [(-a + 2 * a * i / 40, AX + b * math.sin(math.pi * (-1 + 2 * i / 40) + math.pi)) for i in range(41)]
        out["~"] = op_cell(M, line(pts, T))
    # ± : the + itself, lifted onto a bar that stands on the baseline (gap = the = sign's white)
    if "±" in G:
        hv = min(h, (CAP - 2 * T - gap_eq) / 2)             # the + as long as it fits under the cap height (900: shorter)
        yb_ = T / 2; yp = T + gap_eq + T / 2 + hv
        out["±"] = op_cell(M, _union(line([(-hv, yp), (hv, yp)], T), line([(0, yp - hv), (0, yp + hv)], T), line([(-h, yb_), (h, yb_)], T)))
    # ¬ : the = sign's upper bar, turning down at the right to the lower bar's level
    if "¬" in G:
        dq = (T + gap_eq) / 2
        out["¬"] = op_cell(M, line([(-h, AX + dq), (h, AX + dq), (h, AX - dq)], T))
    # « » ‹ › : chevrons on the axis, 0.88 PW tall, the dense pen; « » two of them WS apart
    th = (0.88 * PW - DH) / 2; cwg = 0.87 * th
    ang = math.atan2(th, cwg)
    pitch = (0.12 * CAP + 0.05 * S + DV) / math.sin(ang)  # white between the two: 0.12 CAP + 0.05 S (84-93 at every weight)
    def chev(sgn, x0):
        return pen_line([(x0 + sgn * cwg, AX + th), (x0, AX), (x0 + sgn * cwg, AX - th)], DV, DH)
    for ch, sgn, n in (("‹", 1, 1), ("›", -1, 1), ("«", 1, 2), ("»", -1, 2)):
        if ch in G:
            out[ch] = place(ch, round_joins(_union(*[chev(sgn, i * pitch) for i in range(n)]), 0.5 * FR))
    # • : a disc on the axis, 1.7 pins across (267 = 0.38 CAP at 700; references 0.36) — it follows the
    #     pin, so at 100 it is the weight's own dot scaled up, not a 0.3 CAP blot among hairlines
    if "•" in G:
        out["•"] = place("•", _circle(0, AX, 1.7 * M["PIN_R"]))
    # ---- bracket band: ¦ is | with a white of WS centred on the axis ------------------------------------
    if "¦" in G:
        gw = WS
        out["¦"] = place("¦", _union(line([(0, BB + S / 2), (0, AX - gw / 2 - S / 2)], S), line([(0, AX + gw / 2 + S / 2), (0, BT - S / 2)], S)))
    # ---- descending class: top on the cap height, bottom on the bracket bottom BB ---------------------
    # † ‡ : a stem S over the whole band, bars T 0.56 CAP long at 0.70 CAP (‡: and its mirror)
    ybar = 0.70 * CAP; bl = (0.56 * CAP - T) / 2
    stem = line([(0, BB + S / 2), (0, CAP - S / 2)], S)
    if "†" in G:
        out["†"] = place("†", round_joins(_union(stem, line([(-bl, ybar), (bl, ybar)], T)), FR))
    if "‡" in G:
        out["‡"] = place("‡", round_joins(_union(stem, line([(-bl, ybar), (bl, ybar)], T), line([(-bl, CAP + BB - ybar), (bl, CAP + BB - ybar)], T)), FR))
    from weights import _map as _wmap, _piecewise as _wpw
    # ¶ : drawn with the pen like every other stroke — two stems S over the band, the bowl a half
    #     ellipse on the left from the cap height down to 0.40 CAP, its counter 0.24 CAP − S wide and never under
    #     0.65 S (from 600 up the bowl widens with the pen, so it stays open: the parent filled its bowl solid).
    if "¶" in G:
        SV_, SH_ = M["PEN"]
        x1 = 1.5 * SV_ + max(0.24 * CAP - SV_, 0.65 * S)       # the left stem's centre; stem white 0.10 CAP + 0.3 S
        x2 = x1 + SV_ + 0.10 * CAP + 0.3 * S; yl = 0.40 * CAP
        a_ = x1 - SV_ / 2; b_ = (CAP - yl) / 2 - SH_ / 2; cyb = (CAP + yl) / 2
        bowl = ell_pts(x1, cyb, a_, b_, 90, 270, 48)
        top = [(x2, BB + SH_ / 2), (x2, CAP - SH_ / 2), (x1, CAP - SH_ / 2)]
        q = _union(pen_line(top + bowl[1:], SV_, SH_), pen_line([(x1, CAP - SH_ / 2), (x1, BB + SH_ / 2)], SV_, SH_))
        out["¶"] = place("¶", round_joins(q, FR))
    # § : the parent's, stretched onto the band (a round form: CAP + OSH at the top)
    if "§" in G:
        p = G["§"]["p"]; y0, y1 = p.bounds[1], p.bounds[3]
        q = _wmap(p, _wpw([y0, y1], [BB, CAP + OSH])); q.simplify()
        out["§"] = {"p": q, "adv": G["§"]["adv"], "pins": []}
    # ---- # : cap-figure class, dense pen; verticals 0.32 CAP apart leaning 10°, bars 0.33 CAP apart ---
    if "#" in G:
        sl = math.tan(math.radians(10)); dv = 0.16 * CAP; hl = 0.32 * CAP
        vs = [pen_line([(x - sl * (CAP / 2 - DH / 2), DH / 2), (x + sl * (CAP / 2 - DH / 2), CAP - DH / 2)], DV, DH) for x in (-dv, dv)]
        bs = [pen_line([(-hl, y), (hl, y)], DV, DH) for y in (0.5 * CAP - 0.165 * CAP, 0.5 * CAP + 0.165 * CAP)]
        out["#"] = place("#", round_joins(_union(*vs, *bs), 0.5 * FR))
    return out


# ---- SYM late: built from limn's final letters and figures (build_font calls this after the tabular
#      figures, before the accents; see the hook there) ---------------------------------------------
K_SUP = 0.58        # superior figures and letters: 0.58 of their full size, top on the cap height
K_REG = 0.64        # ® : its ring 0.64 of O's height (a superior mark like ™, ring a little larger)


def _reweigh(M, p, k, pen):
    """p already scaled by k: dilate or erode so its stems are pen = (vertical, horizontal)."""
    from weights import offset as _woff, grow as _wgrow
    S = M["S"]; kc = M["PEN"][1] / M["PEN"][0]
    rx = (pen[0] - k * S) / 2; ry = (pen[1] - k * S * kc) / 2
    if abs(rx) < 0.25:
        return p, 0.0
    if rx * ry <= 0:
        ry = rx * kc
    try:
        return (_wgrow(p, rx, ry) if rx > 0 else _woff(p, rx, ry)), ry
    except pathops.PathOpsError:
        return p, 0.0


def _gap_to(a, b, white):
    """True when a and b keep at least `white` apart (b dilated by white does not meet a)."""
    return _empty(_inter(a, _dilate(b, white)))


def _slide(fixed, moving, white, lo, hi, towards=+1):
    """Largest shift (towards = +1, moving to the right) or smallest (-1) that keeps `white`."""
    for _ in range(14):
        mid = (lo + hi) / 2
        ok = _gap_to(_xf(moving, e=mid), fixed, white)
        if (ok and towards > 0) or (not ok and towards < 0):
            lo = mid
        else:
            hi = mid
    return lo if towards > 0 else hi


def apply_sym_late(G):
    """Superior class (¹ ² ³ ª º ° ™ ®), fractions (½ ¼ ¾), © and the currency built on letters
    (€ ¥ ¢). Returns the MODS rows; the glyphs go into G and into the changed set."""
    M = ST["M"]; B = ST["before"]
    S, XH, XO, CAP, OSH, AX, T, GAP = (M[k] for k in ("S", "XH", "XO", "CAP", "OSH", "AX", "T", "GAP"))
    P = sym_pens(M); SUP, DENSE, kc = P["SUP"], P["DENSE"], P["k"]; LIGHT = SUP   # LIGHT: the superior pen, also the currency bars
    FR = M["FR"]; Ht = M["O_T"] - M["O_B"]
    gap_eq = max(0.75 * S, 0.16 * 0.9 * XH)               # the = sign's white (as in apply_punct)
    out, info = {}, {}

    def place(ch, p):
        """Side bearings: the parent glyph's mean side bearing (as recentre_x)."""
        src = B.get(ch) or G[ch]
        x0, _, x1, _ = src["p"].bounds; sb = (x0 + src["adv"] - x1) / 2
        b = p.bounds
        return {"p": _xf(p, e=sb - b[0]), "adv": round(b[2] - b[0] + 2 * sb), "pins": []}

    def sup(src_ch, line_from, line_to, k=K_SUP, pen=SUP):
        """src glyph scaled by k about `line_from`, which lands on `line_to` after the reweigh."""
        p = _xf(G[src_ch]["p"], k, 0, 0, k, 0, 0)
        p, ry = _reweigh(M, p, k, pen)
        dy = line_to - k * line_from - (ry if line_to > 0 else -ry)
        return _xf(p, f=dy)

    # ---- superiors: figures and letters at K_SUP, top on the cap height, the SUP pen --------------------
    for ch, d in (("¹", "1"), ("²", "2"), ("³", "3")):
        if ch in G:
            out[ch] = place(ch, sup(d, CAP, CAP))
    for ch, l in (("ª", "a"), ("º", "o")):
        if ch in G:
            out[ch] = place(ch, sup(l, XH, CAP))
    # ° : a ring as tall as the superior o (K_SUP of o's height), its top where º's top is
    if "°" in G:
        D = K_SUP * (XO + OSH); cy = CAP + K_SUP * OSH - D / 2
        ring = pen_line(ell_pts(0, cy, (D - SUP[0]) / 2, (D - SUP[1]) / 2, 0, 360, 72), *SUP)
        out["°"] = place("°", ring)
    # ™ : T and M at K_SUP, the SUP pen, set with their own white scaled by K_SUP
    if "™" in G:
        t_ = sup("T", CAP, CAP); m_ = sup("M", CAP, CAP)
        w0 = (G["T"]["adv"] - G["T"]["p"].bounds[2]) + G["M"]["p"].bounds[0]
        white = max(0.6 * SUP[0], K_SUP * w0)
        m_ = _xf(m_, e=t_.bounds[2] + white - m_.bounds[0])
        out["™"] = place("™", _union(t_, m_))

    # ---- circled marks: a ring and a letter at `share` of the ring (© 0.46, ® 0.42), one pen for both -----
    def circled(letter, D, cy, pen, share=0.46):
        ring = pen_line(ell_pts(0, cy, (D - pen[0]) / 2, (D - pen[1]) / 2, 0, 360, 96), *pen)
        k = share * D / CAP
        q = _xf(G[letter]["p"], k, 0, 0, k, 0, 0)
        q, _ = _reweigh(M, q, k, pen)
        b = q.bounds
        q = _xf(q, e=-(b[0] + b[2]) / 2 + 0.02 * D, f=cy - (b[1] + b[3]) / 2)
        return _union(ring, q)
    if "©" in G:       # full size: O's own height and overshoots
        out["©"] = place("©", circled("C", Ht, (M["O_T"] + M["O_B"]) / 2, SUP))
    if "®" in G:       # superior mark like ™: ring K_REG of O's height, top on the cap height (+ overshoot)
        # the R keeps a counter: the pen is at most 0.14 of the ring. Where the LIGHT pen is heavier than that (600 and
        # up) the ring grows by the fourth root of the excess, so the mark keeps gaining weight with the letters
        D0 = K_REG * Ht; D = D0 * max(1.0, SUP[0] / (0.14 * D0)) ** 0.25; pr = min(SUP[0], 0.14 * D)
        out["®"] = place("®", circled("R", D, CAP + K_REG * OSH - D / 2, (pr, pr * kc), 0.42))

    # ---- fractions: superior numerator, denominator on the baseline, slash from baseline to cap -------
    ang = math.radians(24)
    run = (CAP - SUP[1]) * math.tan(ang)
    slash = pen_line([(0, SUP[1] / 2), (run, CAP - SUP[1] / 2)], *SUP)
    white = sym_white(M)
    for ch, n, d in (("½", "1", "2"), ("¼", "1", "4"), ("¾", "3", "4")):
        if ch not in G: continue
        num = sup(n, CAP, CAP)
        den = sup(d, 0, 0)
        nb, db = num.bounds, den.bounds
        num = _xf(num, e=-nb[2]); den = _xf(den, e=-db[0])           # num ends at x 0, den starts at x 0
        xn = _slide(slash, num, white, -run - 2 * S, run + S, +1)
        xd = _slide(slash, den, white, -run, 2 * run + 2 * S, -1)
        out[ch] = place(ch, _union(_xf(num, e=xn), slash, _xf(den, e=xd)))

    # ---- currency on letters: the letter at its own weight, the bars with the dense pen -----------------
    # € : C with the = sign's two bars (their spacing), centred on C's middle, from 0.10 W left of C to
    #     0.62 W into it
    if "€" in G:
        c = G["C"]["p"]; b = c.bounds; Cw = b[2] - b[0]; ym = (b[1] + b[3]) / 2; dq = (LIGHT[1] + gap_eq) / 2
        bars = [pen_line([(b[0] - 0.10 * Cw + LIGHT[0] / 2, y), (b[0] + 0.62 * Cw, y)], *LIGHT) for y in (ym - dq, ym + dq)]
        out["€"] = place("€", round_joins(_union(c, *bars), 0.5 * FR))
    # ¥ : Y with the same two bars, the upper one on the fork
    if "¥" in G:
        y_ = G["Y"]["p"]; b = y_.bounds; cx = (b[0] + b[2]) / 2; Yw = b[2] - b[0]
        fy = b[3]
        while fy > b[1] + S and len(slice_ivs(y_, fy)) > 1:
            fy -= 2
        dq = LIGHT[1] + gap_eq
        hl = 0.30 * Yw
        bars = [pen_line([(cx - hl, y), (cx + hl, y)], *LIGHT) for y in (fy - LIGHT[1] / 2, fy - LIGHT[1] / 2 - dq)]
        out["¥"] = place("¥", round_joins(_union(y_, *bars), 0.5 * FR))
        info["¥"] = fy
    # ¢ : c with a vertical bar through its middle, 0.13 CAP beyond the baseline and the round x-height
    if "¢" in G:
        c = G["c"]["p"]; b = c.bounds; cx = (b[0] + b[2]) / 2 + 0.02 * (b[2] - b[0]); e = 0.13 * CAP
        bar = pen_line([(cx, -e + LIGHT[1] / 2), (cx, XO + e - LIGHT[1] / 2)], *LIGHT)
        out["¢"] = place("¢", round_joins(_union(c, bar), 0.5 * FR))

    for ch, g in out.items():
        G[ch] = g
        ST["changed"].add(ch)
    f0 = lambda v: f"{v:.0f}"
    return [
        ["¹ ² ³ ª º ° ™", "위첨자 부류", f"limn의 숫자·글자를 {K_SUP}배로, 윗끝 = 대문자 높이 {CAP}, 펜 LIGHT {SUP[0]:.0f}({SUP[0] / S:.2f} S). ° 는 위첨자 o 높이의 고리"],
        ["½ ¼ ¾", "분수", f"분자 = 위첨자, 분모 = 같은 크기로 기준선에, 빗금은 기준선~대문자 높이 24°, 펜 LIGHT, 흰 틈 WS {f0(white)}"],
        ["© ®", "고리 글자", f"고리 + C(0.46)·R(0.42), 고리와 글자 한 펜. © 는 O 높이, ® 는 ™처럼 위첨자(고리 {K_REG} O, 펜 ≤ 0.14 × 고리)"],
        ["€ ¥ ¢", "글자 + 막대", f"limn의 C·Y·c 그대로 + LIGHT 펜({SUP[0] / S:.2f} S) 막대. € ¥ 막대 간격 = 등호의 흰 틈 {f0(gap_eq)}"],
        ["& # « » ‹ ›", "DENSE 펜", f"획이 셋 이상 겹치거나 나란한 글자는 {DENSE[0] / S:.2f} S. & 는 대문자·숫자 부류(O 높이·O 폭 0.90), # 은 폭 0.79 CAP·10° 기울기, « » 는 축 위 0.88 PW"],
        ["± ¬ < > ~ • ¦ † ‡ § ¶", "부류 규칙으로", "수학 축 PW 정사각·T 펜(± 는 + 를 기준선 막대 위로), • 1.7 핀, ¦ 는 WS만큼 끊은 |, † ‡ § ¶ 는 대문자 높이~괄호 아랫선"],
    ]


# ---- sweep 2026-09-28: symbols the sweep found missing (tofu), each on a class above. build_font calls this right
#      after apply_sym_late (the figures, W N º ' " / are final by then); the pure aliases (‐ ‑ = -, ― = —, ￦ = ₩)
#      are added by build_font after the kerning, as copies kerned through their class.
SYM_ALIAS = {"‐": "-", "‑": "-", "―": "—", "￦": "₩"}
PRIME_SLANT = 20        # degrees from vertical: the slant of / and \ (bracket band)


def apply_sym_new(G):
    """¤ (maths axis), ₩ (currency on a letter), № (letter + superior), ′ ″ (the straight quotes on the slant of /),
    ⁄ (the fractions' slash), ‒ (figure dash: a dash as wide as a tabular figure). Returns the MODS rows."""
    M = ST["M"]; B = ST["before"]
    S, XH, CAP, AX, T = (M[k] for k in ("S", "XH", "CAP", "AX", "T"))
    P = sym_pens(M); SUP, DENSE = P["SUP"], P["DENSE"]; LIGHT = SUP
    FR = M["FR"]; PW = 0.9 * XH
    gap_eq = max(0.75 * S, 0.16 * PW)
    out = {}

    def place(ch, p):
        """Side bearings: the parent glyph's mean side bearing (as apply_sym_late)."""
        src = B.get(ch) or G[ch]
        x0, _, x1, _ = src["p"].bounds; sb = (x0 + src["adv"] - x1) / 2
        b = p.bounds
        return {"p": _xf(p, e=sb - b[0]), "adv": round(b[2] - b[0] + 2 * sb), "pins": []}

    # ¤ : axis class — ink in the PW square on the axis like + and ×; a ring 0.62 PW across and four spokes at 45°
    #     to the square's corners, the DENSE pen (five strokes meet: the pen of & # « »), joins round
    if "¤" in G:
        DV, DH = DENSE; D = max(0.62 * PW, 2 * DV + 0.30 * PW)          # the counter never under 0.30 PW (800-900)
        a, b = (D - DV) / 2, (D - DH) / 2
        ring = pen_line(ell_pts(0, AX, a, b, 0, 360, 96), DV, DH)
        c45 = math.cos(math.radians(45))
        sx, sy = PW / 2 - DV / 2, PW / 2 - DH / 2
        spokes = [pen_line([(i * a * c45, AX + j * b * c45), (i * sx, AX + j * sy)], DV, DH) for i in (-1, 1) for j in (-1, 1)]
        out["¤"] = place("¤", round_joins(_union(ring, *spokes), 0.5 * FR))
    # ₩ : currency on a letter (€ ¥): limn's W at its own weight and one LIGHT bar reaching 0.04 W past its ink. One bar,
    #     as the rounded parents draw it (Quicksand, NanumSquareRound, M+ Rounded, Varela Round), across the W at
    #     NanumSquareRound's own height, 0.56 CAP (the Hangul parent's ₩, all four masters). The bar was first laid on
    #     the highest row cut three ways; with limn's middle apex that row is near the cap height, and the bar read
    #     as a lid on a W, not as ₩ (2026-09-29, checked against Pretendard, Noto Sans KR, Inter and NanumSquareRound).
    if "₩" in G:
        w_ = G["W"]["p"]; b = w_.bounds; Ww = b[2] - b[0]
        yb = 0.56 * CAP
        ext = 0.04 * Ww
        bar = pen_line([(b[0] - ext + LIGHT[0] / 2, yb), (b[2] + ext - LIGHT[0] / 2, yb)], *LIGHT)
        out["₩"] = place("₩", round_joins(_union(w_, bar), 0.5 * FR))
    # № : limn's N and its superior o (º, the superior class), set with ™'s white; under the o a LIGHT bar as wide as
    #     its ink, the = sign's white at the superior scale below it (every reference underlines the o of №: without
    #     it N + º reads N°); N's left side, º's right side
    if "№" in G and "º" in G:
        n_, o_ = G["N"]["p"], G["º"]["p"]; nb, ob = n_.bounds, o_.bounds
        w0 = (G["N"]["adv"] - nb[2]) + G["o"]["p"].bounds[0]
        white = max(0.6 * SUP[0], K_SUP * w0)
        yb = ob[1] - K_SUP * gap_eq - LIGHT[1] / 2
        o_ = _union(o_, pen_line([(ob[0] + LIGHT[0] / 2, yb), (ob[2] - LIGHT[0] / 2, yb)], *LIGHT))
        q = _union(n_, _xf(o_, e=nb[2] + white - ob[0]))
        out["№"] = {"p": q, "adv": round(q.bounds[2] + (G["º"]["adv"] - ob[2])), "pins": []}
    # ′ ″ : the prime is the straight quote's wedge (quote band QT..QB, S tapering to 0.7 S) slanted like / (20°),
    #       sheared about the band's middle so it keeps the band; the quote's own side bearings
    t = math.tan(math.radians(PRIME_SLANT))
    for ch, src in (("′", "'"), ("″", "\"")):
        if src not in G or G[src]["pins"]: continue          # the wedge quotes (LIMN_QUOTE=wedge) only
        q = G[src]["p"]; b = q.bounds; yc = (b[1] + b[3]) / 2; sb = (b[0] + G[src]["adv"] - b[2]) / 2
        p = _xf(q, 1, 0, t, 1, -t * yc, 0); pb = p.bounds
        out[ch] = {"p": _xf(p, e=sb - pb[0]), "adv": round(pb[2] - pb[0] + 2 * sb), "pins": []}
    # ⁄ : the slash of ½ ¼ ¾ — baseline to cap height at 24°, the LIGHT pen
    if "⁄" in G:
        run = (CAP - SUP[1]) * math.tan(math.radians(24))
        out["⁄"] = place("⁄", pen_line([(0, SUP[1] / 2), (run, CAP - SUP[1] / 2)], *SUP))
    # ‒ : figure dash — a bar of the hyphen's weight T on the axis, as long as the widest figure's ink, centred in the
    #     tabular width (555‒1234 keeps the columns of the figures)
    if "0" in G:
        TN = G["0"]["adv"]
        fw = max(G[d]["p"].bounds[2] - G[d]["p"].bounds[0] for d in "0123456789")
        L = fw - T
        out["‒"] = {"p": line([(TN / 2 - L / 2, AX), (TN / 2 + L / 2, AX)], T), "adv": TN, "pins": []}

    for ch, g in out.items():
        G[ch] = g
        ST["changed"].add(ch)
    f0 = lambda v: f"{v:.0f}"
    return [
        ["¤", "수학 축 부류", f"PW({f0(PW)}) 정사각에 고리(0.62 PW, 속공간 ≥ 0.30 PW) + 45° 살 넷, DENSE 펜({DENSE[0] / S:.2f} S), 이음 둥글게"],
        ["₩ ￦", "글자 + 막대", "limn의 W 그대로 + LIGHT 막대 하나(둥근 부모들처럼), 높이는 한글 부모 나눔스퀘어라운드의 ₩와 같은 0.56 CAP, 잉크 밖으로 0.04 W. ￦는 ₩와 같은 글자"],
        ["№", "글자 + 위첨자", "limn의 N + º(위첨자 o) + o 밑 LIGHT 막대(흰 틈 = 등호의 틈 × 0.58), 사이 흰 틈은 ™의 규칙"],
        ["′ ″", "곧은 따옴표를 / 기울기로", f"쐐기 ' \" 를 따옴표 띠 가운데를 축으로 {PRIME_SLANT}° 기울임(/ \\ 와 같은 각), 옆 여백은 따옴표 그대로"],
        ["⁄", "분수 빗금", "½ ¼ ¾ 의 빗금 그대로: 기준선~대문자 높이 24°, LIGHT 펜"],
        ["‒ ‐ ‑ ―", "대시", "‒ = 줄기 굵기 T의 막대, 가장 넓은 숫자 잉크만큼, 고정폭 숫자 폭 가운데(축 위). ‐ ‑ = 하이픈, ― = em 대시(같은 글자, 같은 커닝 부류)"],
    ]


def slice_ivs(p, y):
    """Ink intervals of p on the line y (via an intersection with a thin band)."""
    band = _inter(p, _rect(-1e4, y - 0.5, 1e4, y + 0.5))
    ivs = sorted((c.bounds[0], c.bounds[2]) for c in band.contours)
    return ivs


def at_glyph(M, G, kind):
    """@ on the metrics. The ring is one size up to 700 (top on O's top, bottom −0.25 XH: 1.21 cap
    heights; the references keep theirs at 1.23-1.25 at every weight) and grows a little downwards above
    it; the stroke is 0.85 S, held under Ro/3.2 so the a keeps a counter at 900 (0.68 S there — the
    references lighten their @ the same way, 0.58-0.85 S). The earlier @ sized its ring from the stroke
    and the gap, so it grew from 0.92 to 1.35 cap heights between 100 and 900.
      1  a built like limn's a (round bowl, stem on its right), ring a circle; the stem's foot curls
         right in a tight U and runs up into the ring, which goes round and stops with a round end
         GAP under the curl.
      2  limn's own a (Quicksand's a, scaled by W/S so its stems are the ring's weight), ring a circle
         drawn apart, open at the lower right beside the a's foot, both ends round.
      3  as 1, the ring an O-proportioned oval.
    In all three the a is as large as fits with `white` to the ring, set a little to the lower left of
    the ring's centre so its stem's top (the tight corner) clears the ring."""
    S, XH, XO, CAP, OSH, GAP = M["S"], M["XH"], M["XO"], M["CAP"], M["OSH"], M["GAP"]
    k = M["PEN"][1] / M["PEN"][0]
    # above 700 the ring grows a little downwards (1.21 -> 1.24 cap heights at 900, the references'
    # 1.23-1.25), so the a keeps a counter
    top_o, bot_o = M["O_T"], -0.25 * XH - 0.3 * max(0.0, S - 120)
    cy = (top_o + bot_o) / 2; Ro = (top_o - bot_o) / 2
    rho = M["O_W"] / (M["O_H"]) if kind == "3" else 1.0
    cx = 0.0
    sh = 0.07
    # the a (a round bowl, half sizes hx hy, with its stem's top at the top-right corner) must sit inside
    # the ring's counter less `white`. The corner is the tight point, so the a moves off-centre toward
    # the lower left by `sh` of its size: that frees the corner, and the bowl's round side has room

    def room(W):
        WH = W * k; white = max(GAP, 0.4 * W)
        Rcy = Ro - WH / 2; Rcx = (Ro * rho) - W / 2
        return WH, white, Rcx, Rcy, Rcx - W / 2 - white, Rcy - WH / 2 - white

    def fits(hx, hy):
        dx, dy = -sh * hx, -sh * hy
        pts = [(hx, hy)] + [(hx * math.cos(math.radians(t)), hy * math.sin(math.radians(t))) for t in range(0, 360, 15)]
        return all(((x + dx) / Rix) ** 2 + ((y + dy) / Riy) ** 2 <= 1 for x, y in pts)

    def a_size(W):
        ha = 0.42 * XH + 0.2 * W                               # a's outer half-height, as large as fits
        while not fits(0.94 * ha, ha):
            ha -= 1
        return ha
    W = min(0.85 * S, Ro / 3.2)
    WH, white, Rcx, Rcy, Rix, Riy = room(W)
    # small-glyphs 2026-09-28: the a keeps a counter at least as wide as the white between it and the ring.
    # In the text cuts that white is held at 1.25 px (GAP), which at 12 px is 104 units: at 900 (stroke
    # 130) the a that still fitted was 300 wide, its counter 40, and the round-join closing below (r 30)
    # shut it — the @ read as a blot in a ring (800: counter 79). Where the counter would be narrower,
    # the whole @ — ring and a, one pen — is drawn lighter until it is not (the references lighten their
    # @ to 0.58-0.85 S anyway): 0.79 S at 800 and 0.72 S at 900 in the 12 px cut (counters 108, 107),
    # 0.84 S at 900 in the 16 px cut. Nothing changes where the a already has the room (every weight at
    # its own size, every cut at 100-700).
    if kind in "13":
        while 2 * (0.94 * a_size(W) - W) < white and W > 0.5 * S:
            W -= 1
            WH, white, Rcx, Rcy, Rix, Riy = room(W)
    R = lambda t: (cx + Rcx * math.cos(math.radians(t)), cy + Rcy * math.sin(math.radians(t)))
    strokes = []; a_ink = None
    if kind in "13":
        ha = a_size(W)
        hb = 0.94 * ha
        bx, by = hb - W / 2, ha - WH / 2
        ax, ay = cx - sh * hb, cy - sh * ha                  # the bowl's centre, off the ring's
        bowl = ell_pts(ax, ay, bx, by, 0, 360, 72)
        xs = ax + bx; y_top = ay + by; y1 = ay - 0.45 * by
        # the foot curls right in a tight U and meets the ring at the same height, running up it
        t0 = -math.degrees(math.asin(min(0.95, (cy - y1) / Rcy)))
        P0 = R(t0); t0v = ell_tan(Rcx, Rcy, t0); d = P0[0] - xs
        curl = bez_pts((xs, y1), (xs, y1 - 0.62 * d), (P0[0] - t0v[0] * 0.62 * d, P0[1] - t0v[1] * 0.62 * d), P0)
        stem = [(xs, y_top), (xs, y1)]
        hook = _chain(stem, curl)
        need = W + GAP
        end = t0 + 300
        while end < t0 + 350 and _clear(R(end + 2), hook + bowl, need):
            end += 2
        ring = ell_pts(cx, cy, Rcx, Rcy, t0, end, 120)
        strokes += [bowl, _chain(hook, ring)]
        info = f"고리 {'원' if kind == '1' else 'O 비율 타원'} · 끝 {end - 360:.0f}°"
    else:
        # limn's own a scaled by W/S, so its stems are the ring's weight exactly (contrast kept)
        a0 = G["a"]["p"]; ab = a0.bounds
        sa = W / S
        gr = lambda s_: max(0.0, (W - S * s_) / 2)
        while not fits(sa * (ab[2] - ab[0]) / 2 + gr(sa), sa * (ab[3] - ab[1]) / 2 + gr(sa)):
            sa -= 0.005
        a1 = _xf(a0, sa, 0, 0, sa, 0, 0)
        grow = (W - S * sa) / 2                               # scaled down further: give the stems back their weight
        if grow > 0.5:
            a1 = _union(a1, _band(a1, grow)); a1.simplify()
        b1 = a1.bounds
        hx, hy = (b1[2] - b1[0]) / 2, (b1[3] - b1[1]) / 2   # centred off the ring's centre like the built a
        a_ink = _xf(a1, e=cx - sh * hx - (b1[0] + b1[2]) / 2, f=cy - sh * hy - (b1[1] + b1[3]) / 2)
        pts = [pt for c in a_ink.contours for _, seg in c.segments for pt in seg if pt is not None]
        # ring: open at the lower right, beside the a's foot; the two round ends keep `white` apart
        thc = -40
        half = math.degrees(math.asin(min(0.99, (W + white) / (2 * Rcx))))
        s0, e0 = thc + half, thc + 360 - half
        while s0 < 10 and not _clear(R(s0), pts, W / 2 + GAP):
            s0 += 2
        while e0 > 230 and not _clear(R(e0), pts, W / 2 + GAP):
            e0 -= 2
        strokes.append(ell_pts(cx, cy, Rcx, Rcy, s0, e0, 120))
        info = f"limn의 a ×{sa:.2f} · 고리 원, 열림 {e0 - 360:.0f}° ~ {s0:.0f}°"
    p = _union(*[pen_line(s_, W, WH) for s_ in strokes])
    if a_ink is not None:
        p = _union(p, a_ink)
    p = round_joins(p, min(M["FR"], 0.3 * white))
    return p, info + f", 굵기 {W / S:.2f} S"


# ---------------------------------------------------------------- the system
def _metrics(G, m):
    M = dict(m)
    S = M["S"]
    hb = G["-"]["p"].bounds
    M["AX"] = (hb[1] + hb[3]) / 2                       # maths axis: the parent's hyphen centre
    M["T"] = S                                          # bar weight: the stem (the parent's hyphen is S at 700)
    M.setdefault("PIN_CY", M["XH"] + M["GAP"] + M["PIN_R"])   # i pin centre (build_font passes it: top on the ascender)
    M["BASE_CY"] = M["PIN_R"] - M["OSH"]                 # baseline pin centre (overshoots like o)
    M["YB"] = -0.24 * M["XH"]                            # comma ink bottom (refs 0.50–0.74 of the descender)
    M["COMMA_H"] = 2 * M["PIN_R"] - M["OSH"] - M["YB"]   # comma ink height
    M["QT"] = M["PIN_CY"] + M["PIN_R"]                  # quote top: the i pin top (= ASC at 700)
    M["QB"] = M["QT"] - M["COMMA_H"]                    # quote line (bottom of every quote)
    M["QR"] = M.get("Q_DOT_R", M["PIN_R"] / 1.246)       # Quicksand's own dot radius, for DOTSPEC
    ob = G["("]["p"].bounds
    M["BH"] = ob[3] - ob[1]                              # bracket height: the parent's parenthesis
    M["BT"], M["BB"] = M["AX"] + M["BH"] / 2, M["AX"] - M["BH"] / 2
    eb = G["="]["p"].bounds
    ob = G["o"]["p"].bounds
    M["O_SIDE"] = (ob[0] + G["o"]["adv"] - ob[2]) / 2       # o's side bearing: the unit of limn's spacing
    # operator side bearing: the parent's = (50 at every weight) + 0.7 of o's side, so an operator's white moves with
    # the spacing of the letters (+ = ≠ × read tight in a = b at every weight, by 25-35 at 700); arrows and keyboard
    # marks, whose ink fills the cell edge to edge, take OP_SB_WIDE
    M["OP_SB"] = (eb[0] + G["="]["adv"] - eb[2]) / 2 + 0.7 * M["O_SIDE"]
    M["OP_SB_WIDE"] = M["OP_SB"] + 0.47 * M["O_SIDE"]
    return M


def op_cell(M, p, pins=(), wmin=None, sb=None):
    """Axis class, one advance (sym-math 2026-09-29): every maths operator's ink (pins included) is centred in
    max(ink, PW) + 2 OP_SB (see _metrics). The parent gave + ± 32-34 and < > 40 against the 50 of = ÷ ~ ¬ at 700, so
    + and = stood 35 units apart in width with the same ink; Inter and Pretendard set every operator on one advance, and
    a column of sums lines up only that way. Wider ink (∞ ≪ arrows) keeps 2 OP_SB; sb overrides OP_SB."""
    PW = 0.9 * M["XH"] if wmin is None else wmin
    R = M["PIN_R"]
    b = list(p.bounds) if not _empty(p) else [1e9, 1e9, -1e9, -1e9]
    for x, y in pins:
        b = [min(b[0], x - R), min(b[1], y - R), max(b[2], x + R), max(b[3], y + R)]
    adv = round(max(b[2] - b[0], PW) + 2 * (M["OP_SB"] if sb is None else sb))
    dx = (adv - (b[0] + b[2])) / 2
    return {"p": _xf(p, e=dx), "adv": adv, "pins": [(x + dx, y) for x, y in pins]}


def atq_metrics(M, G):
    """@ & Q redesign: the family's pen (o's contrast), O's box, the round-join radius."""
    S = M["S"]
    sv, sh = atq_contrast(G["o"]["p"])
    M["PEN"] = (S, S * sh / sv)
    Ob = G["O"]["p"].bounds
    M["O_W"], M["O_H"] = Ob[2] - Ob[0], Ob[3] - Ob[1]
    M["O_T"], M["O_B"] = Ob[3], Ob[1]
    M["FR"] = float(os.environ.get("LIMN_FILLET", 0.25)) * min(S, 120)
    return M


def comma_tail(M, px, kind):
    """Ink of a comma whose pin is centred (px, BASE_CY); the pin itself is drawn by the pin layer."""
    S, R, YB, cy = M["S"], M["PIN_R"], M["YB"], M["BASE_CY"]
    if kind == "A":
        # tadpole: a tapered tail whose right edge runs on from the pin's right side, bending left
        # the circles of the sweep never pass the pin's right side, so the tail's outer edge leaves
        # the pin tangentially at three o'clock and runs down into the tip
        rt = 0.24 * S
        # proof audit 2026-09-27 (C-06): below 700 the pin is 1-2 s wide and the tail's tip (0.48 s)
        # and body fell under the stem — at 100-300 the tail vanished at text sizes and , read as .
        # (1,024 as 1.024). The tip grows with the same pin/stroke ratio, up to a full stem (0.5 s).
        q = R / (0.654 * S)
        if q > 1.01:
            rt = min(0.5 * S, rt * q)
        if M.get("OPT_PX"):
            # (C-05, below) before the tip is placed, and the tail as long as the pin is held: the pin keeps its screen
            # size while its overshoot grows with the weight, so the tail's bottom goes down with it (-0.3 % of ink a step)
            rt = max(rt, 0.367 * R); YB = YB - M["OSH"]
        tip = (px - 0.55 * R, YB + rt)
        P0, C1, C2 = (px, cy), (px + 0.25 * R, cy - 0.75 * R), (px + 0.05 * R, tip[1] + 0.45 * R)
        n = 28
        pts = [bez(P0, C1, C2, tip, i / n) for i in range(n + 1)]
        # the taper's speed follows the pin/stroke ratio: 1.1 at 700 (R = 0.654 S); at light weights the
        # pin is 1-2 S wide, and a tail that stayed that wide read heavier than every stroke around it
        k = 1.1 * max(1.0, R / (0.654 * S)) ** 2
        if M.get("OPT_PX"):
            # (C-05) text cut: the comma is the 700 comma scaled to the pin (tip 0.24 s at 700 = 0.367 R,
            # taper 1.1), so at 12-20 px it still reads as a comma and not as a period
            rt = max(rt, 0.367 * R); k = 1.1
        rad = [rt + (R - rt) * (1 - i / n) ** k for i in range(n + 1)]
        ink = sweep(pts, rad)
    elif kind == "B":
        # a straight round-capped stroke leaving the pin down and to the left (25° from vertical)
        w = 0.8 * S; ang = math.radians(-115)
        L = (cy - (YB + w / 2)) / -math.sin(ang)
        ink = line([(px, cy), (px + L * math.cos(ang), cy + L * math.sin(ang))], w)
    else:
        # monoline hook: the stroke follows the pin's right edge down, then swings left under it
        w = 0.72 * S
        P0 = (px + R - w / 2, cy)
        P3 = (px - 0.45 * R, YB + w / 2)
        ink = curve(P0, (P0[0], cy - 0.75 * R), (px + 0.35 * R, P3[1] - 0.05 * R), P3, w)
    return _diff(ink, _circle(px, cy, R - 2))    # the pin covers the start of the tail


def build_comma(M, kind, adv, px):
    return {"p": comma_tail(M, px, kind), "adv": adv, "pins": [(px, M["BASE_CY"])]}


def apply_punct(G, m):
    """Rebuild the punctuation and symbols in G (see the module docstring). Returns
    {"dotspec": {...}, "mods": [...], "changed": set} for build_font to merge."""
    M = _metrics(G, m)
    ST["M"] = M
    ST["before"] = {ch: {"p": pathops.Path(g["p"]), "adv": g["adv"], "pins": list(g["pins"])} for ch, g in G.items()}
    S, XH, XO, CAP, ASC, R, GAP, OSH, AX, T = (M[k] for k in ("S", "XH", "XO", "CAP", "ASC", "PIN_R", "GAP", "OSH", "AX", "T"))
    QR = M["QR"]
    AW = 0.85 * S                                    # @ stroke (see at_sign)
    dots, mods, changed, out = {}, [], set(), {}

    def ink_bounds(ch):
        return G[ch]["p"].bounds

    def recentre_x(ch, p, keep_sb=True):
        """Place p so its side bearings equal the parent glyph's mean side bearing; returns (p, adv)."""
        x0, _, x1, _ = G[ch]["p"].bounds; sb = (x0 + G[ch]["adv"] - x1) / 2
        b = p.bounds
        return _xf(p, e=sb - b[0]), round(b[2] - b[0] + 2 * sb)

    # ---- period / comma / semicolon / quotes -------------------------------------------------
    per = G["."]; px_per = per["pins"][0][0]; adv_per = per["adv"]
    col = G[":"]; px_col = col["pins"][0][0]; adv_col = col["adv"]
    commas = {k: build_comma(M, k, adv_per, px_per) for k in "ABC"}
    # the period's DOTSPEC entry gives Quicksand's own dot for the playground's "original dots" view
    per_dot = [["base", round(px_per, 1), round(2 * QR, 1), round(QR, 1)]]

    def semicolon(k):
        c = comma_tail(M, px_col, k)
        return {"p": c, "adv": adv_col, "pins": [(px_col, XO - R), (px_col, M["BASE_CY"])]}

    def quote_right(k):
        """’ = the comma lifted so its pin is the i pin (top on the ascender at 700)."""
        c = commas[k]; dy = M["PIN_CY"] - M["BASE_CY"]
        return {"p": _xf(c["p"], f=dy), "adv": c["adv"], "pins": [(px_per, M["PIN_CY"])]}

    def quote_left(k):
        """‘ = ’ turned 180° inside the same band (pin at the bottom on the quote line)."""
        q = quote_right(k); b = _union(q["p"], _circle(px_per, M["PIN_CY"], R)).bounds
        cx, cy = (b[0] + b[2]) / 2, (b[1] + b[3]) / 2
        return {"p": rot180(q["p"], cx, cy), "adv": q["adv"], "pins": [(2 * cx - px_per, 2 * cy - M["PIN_CY"])]}

    def double(g, pitch):
        """Two marks side by side, `pitch` apart; the pair keeps the single mark's side bearings."""
        p = _union(g["p"], _xf(g["p"], e=pitch)) if not _empty(g["p"]) else g["p"]
        return {"p": p, "adv": round(g["adv"] + pitch), "pins": [*g["pins"], *[(x + pitch, y) for x, y in g["pins"]]]}

    DPITCH = 2 * R + 0.45 * S                      # “ ” „ : white between the two pins 0.45 s
    # and at least 0.13 XH (QA visual S5, user decision 2026-10-01: 0.45 s left the heavy quotes shut and the light
    # ones wide); the " wedges' white too. LIMN_QUOTE_WHITE=k changes k, LIMN_QUOTE_WHITE=none keeps 0.45 s only.
    _qw = os.environ.get("LIMN_QUOTE_WHITE", "0.13")
    QW = None if _qw.lower() == "none" else float(_qw) * XH
    if QW is not None:
        DPITCH = 2 * R + max(0.45 * S, QW)
    if M.get("OPT_PX"):                            # (C-05) text cut: that white is never under 1.25 px
        DPITCH = max(DPITCH, 2 * R + 1.25 * M["UPM"] / M["OPT_PX"])

    variants = {}
    for k in "ABC":
        variants[f"comma{k}"] = {",": commas[k], ";": semicolon(k), "’": quote_right(k), "‘": quote_left(k),
                                 "‚": commas[k], "“": double(quote_left(k), DPITCH), "”": double(quote_right(k), DPITCH),
                                 "„": double(commas[k], DPITCH)}

    # straight quotes: wedge (ink) or pin with a straight tail
    def wedge(cx):
        return hull2((cx, M["QT"] - S / 2), S / 2, (cx, M["QB"] + 0.35 * S), 0.35 * S)

    def pin_drop(cx):
        cyp = M["PIN_CY"]
        ink = _diff(hull2((cx, cyp), R, (cx, M["QB"] + 0.3 * S), 0.3 * S), _circle(cx, cyp, R - 2))
        return ink, [(cx, cyp)]

    qb1 = G["'"]["p"].bounds; qb2 = G["\""]["p"].bounds
    for kind in ("wedge", "pin"):
        v = {}
        if kind == "wedge":
            p1 = wedge(0); p2 = _union(wedge(0), wedge(1.5 * S if QW is None else S + max(0.5 * S, QW))); pins1 = pins2 = []
        else:
            p1, pins1 = pin_drop(0); a, _ = pin_drop(0); b, _ = pin_drop(DPITCH)
            p2, pins2 = _union(a, b), [(0, M["PIN_CY"]), (DPITCH, M["PIN_CY"])]
        for ch, p, pins, qb in (("'", p1, pins1, qb1), ("\"", p2, pins2, qb2)):
            full = _union(p, *[_circle(x, y, R) for x, y in pins]) if pins else p
            fb = full.bounds; sb = (qb[0] + G[ch]["adv"] - qb[2]) / 2
            dx = sb - fb[0]
            v[ch] = {"p": _xf(p, e=dx), "adv": round(fb[2] - fb[0] + 2 * sb), "pins": [(x + dx, y) for x, y in pins]}
        variants[f"quote_{kind}"] = v

    # ---- ! and ¡ : i turned 180° -----------------------------------------------------------
    ex = G["!"]; epx = ex["pins"][0][0]
    for kind, top in (("cap", CAP), ("asc", ASC)):
        y0 = M["BASE_CY"] + R + GAP                 # white GAP above the pin, as under the i pin
        stem = line([(epx, y0 + S / 2), (epx, top - S / 2)], S)
        g = {"p": stem, "adv": ex["adv"], "pins": [(epx, M["BASE_CY"])]}
        # ¡ is ! turned: the pin tops at the round x-height like the upper pin of : ;
        # rot180 about y=0 maps [pin bottom, top] to [-top, -(pin bottom)]; lift so the pin top is XO
        pin_bottom = M["BASE_CY"] - R
        lift = XO + pin_bottom                       # -(pin bottom) + lift = XO
        inv = _xf(rot180(stem, epx, 0), f=lift)
        variants[f"excl_{kind}"] = {"!": g, "¡": {"p": inv, "adv": ex["adv"], "pins": [(epx, -M["BASE_CY"] + lift)]}}

    # ¿ is the (already pinned) ? turned 180°, pin top on the round x-height
    q = G["?"]; qpx, qpy = q["pins"][0]
    pin_bottom = qpy - R; lift = XO + pin_bottom
    cxq = q["adv"] / 2
    inv_q = {"p": _xf(rot180(q["p"], cxq, 0), f=lift), "adv": q["adv"], "pins": [(2 * cxq - qpx, -qpy + lift)]}

    # ---- @ ---------------------------------------------------------------------------------
    def at_sign(kind):
        # The a: an o-like bowl 0.8 XH across, centred on the x-height middle, its stem on the bowl's
        # right side rising to the bowl top. The ring runs round the same middle; the a slides left
        # by d, and the ring is the smallest that keeps GAP white both from the stem's top end (upper
        # right) and from the bowl (left). Stroke AW = 0.85 S: three strokes stacked across the glyph
        # (ring · bowl · counter · bowl · ring) read darker than one stem at S (refs: ring 0.58–1.04 s,
        # median 0.69), so the whole @ is drawn one step lighter — still one weight throughout.
        W = AW
        rb = 0.4 * XH; cy = XH / 2; cx = 0.0
        best = None
        for d in range(0, int(rb)):
            xs_ = rb - W / 2 - d
            need = max(math.hypot(xs_, rb - W / 2) + W + GAP, rb + d + GAP + W / 2)
            if best is None or need < best[0]: best = (need, d)
        Rc, d = best                                  # ring centreline radius, a's shift
        bowl = _diff(_circle(cx - d, cy, rb), _circle(cx - d, cy, rb - W))
        xs = cx - d + rb - W / 2                      # a's stem: the bowl's right side
        top = (xs, cy + rb - W / 2)
        if kind == "A":
            # one stroke: stem down to the centre line, a U turn, up into the ring, round the ring
            rho = (cx + Rc - xs) / 2
            u = [(xs + rho - rho * math.cos(math.radians(a)), cy - rho * math.sin(math.radians(a))) for a in range(0, 181, 6)]
            centre = [top] + u
            a_part = line(centre, W)
            start = 0
        else:
            # two strokes: the a stands whole (stem to the bowl's bottom, round ends) and the ring is
            # open at three o'clock — it starts there with a round end instead of joining the stem
            foot = (xs, cy - rb + W / 2)
            centre = [top, foot]
            a_part = line(centre, W)
            start = 0
        # ring: counter-clockwise from 3 o'clock; stop where its round end keeps GAP from the a
        def clear(a):
            ex_, ey_ = cx + Rc * math.cos(math.radians(a)), cy + Rc * math.sin(math.radians(a))
            pts = centre if len(centre) > 2 else [(centre[0][0], centre[0][1] + (centre[1][1] - centre[0][1]) * i / 20) for i in range(21)]
            return min(math.hypot(ex_ - x, ey_ - y) for x, y in pts) - W >= GAP
        end = 180
        while end < 358 and clear(end + 2):
            end += 2
        if kind == "B":
            # B's ring must not close on itself: open it between -70° and -20°, facing the a's foot
            start, end = -20, min(end, 290)
        ring = line(arc_pts(cx, cy, Rc, start, end, 90), W)
        p = _union(bowl, a_part, ring)
        info = f"고리 {start}° → {end - 360:.0f}°, 굵기 0.85 S"
        p.simplify()
        pa, adv = recentre_x("@", p)
        return {"p": pa, "adv": adv}, info

    at = {k: at_sign(k) for k in "AB"}
    for k in "AB":
        variants[f"at{k}"] = {"@": at[k][0]}

    # ==== @ & redesign (2026-09-27, atq.html) — LIMN_AT 1|2|3, LIMN_AMP 1|2|3|orig ==============
    atq_metrics(M, G)
    amp = {}
    for k in "123":
        p, info = at_glyph(M, G, k)
        pa, adv = recentre_x("@", p)
        at[k] = ({"p": pa, "adv": adv}, info); variants[f"at{k}"] = {"@": at[k][0]}
        p, info = amp_glyph(M, G, k)
        pa, adv = recentre_x("&", p)
        amp[k] = ({"p": pa, "adv": adv}, info); variants[f"amp{k}"] = {"&": amp[k][0]}
    for k in "ABC":                                  # SYM: & on the cap-figure class (amp_sym)
        p, info = amp_sym(M, G, k)
        pa, adv = recentre_x("&", p)
        amp[k] = ({"p": pa, "adv": adv}, info); variants[f"amp{k}"] = {"&": amp[k][0]}
    ST["amp"] = amp
    # ==== end @ & redesign =====================================================================

    # ---- chosen options into G ---------------------------------------------------------------
    chosen = {}
    chosen.update(variants[f"comma{OPT['comma']}"])
    chosen.update(variants[f"quote_{OPT['quote']}"])
    chosen.update(variants[f"excl_{OPT['excl']}"])
    chosen["@"] = variants[f"at{OPT['at']}"]["@"]
    if OPT["amp"] in amp:
        chosen["&"] = variants[f"amp{OPT['amp']}"]["&"]
    if "¿" in G:
        chosen["¿"] = inv_q

    # ---- ellipsis: three pins, 3 PIN_R apart -------------------------------------------------
    if "…" in G:
        lsb = px_per - R
        pitch = 3 * R
        chosen["…"] = {"p": pathops.Path(), "adv": round(adv_per + 2 * pitch), "pins": [(px_per + i * pitch, M["BASE_CY"]) for i in range(3)]}

    # ---- middle dot on the axis: Quicksand centres it on its hyphen at 600–700 but 4–9 units low at
    #      400–500; move the pin to AX and patch its DOTSPEC entry in place (only its y changes)
    ST["mid_dot_off"] = round(G["·"]["pins"][0][1] - AX, 1)
    if abs(ST["mid_dot_off"]) > 0.05:
        md = G["·"]; chosen["·"] = {"p": md["p"], "adv": md["adv"], "pins": [(md["pins"][0][0], AX)]}
        ds = m.get("DOTSPEC", {}).get("·")
        if ds: ds["pins"] = [[k, x, round(AX, 1), r0] for k, x, _, r0 in ds["pins"]]

    # ---- brackets: centre on the maths axis, the parent's own height ----------------------------
    for ch in "()[]{}":
        b = G[ch]["p"].bounds; dy = AX - (b[1] + b[3]) / 2
        chosen[ch] = {"p": _xf(G[ch]["p"], f=dy), "adv": G[ch]["adv"], "pins": []}

    # ---- | / \ : one stroke of weight S across the bracket span --------------------------------
    BT, BB = M["BT"], M["BB"]
    for ch in "|/\\":
        if ch not in G: continue
        if ch == "|":
            p = line([(0, BB + S / 2), (0, BT - S / 2)], S)
        else:
            run = (BT - BB - S) * math.tan(math.radians(20))       # 20° from vertical (refs 15–26, median 20)
            a, b = (0, BB + S / 2), (run, BT - S / 2)
            if ch == "\\": a, b = (run, BB + S / 2), (0, BT - S / 2)
            p = line([a, b], S)
        pa, adv = recentre_x(ch, p)
        chosen[ch] = {"p": pa, "adv": adv, "pins": []}

    # ---- dashes: one bar of weight T on the axis, the parent's lengths; the en dash 1.6 × the hyphen (refs 1.64) ------
    hy = G["-"]["p"].bounds; hl = hy[2] - hy[0]
    for ch in "-–—":
        if ch not in G: continue
        b = G[ch]["p"].bounds; L = max(1.6 * hl, b[2] - b[0]) if ch == "–" else b[2] - b[0]
        sb = (b[0] + G[ch]["adv"] - b[2]) / 2
        chosen[ch] = {"p": line([(sb + T / 2, AX), (sb + L - T / 2, AX)], T), "adv": round(L + 2 * sb), "pins": []}

    # ---- maths: + = × ÷ one size (0.9 XH), bar weight T, on the axis ----------------------------
    PW = 0.9 * XH
    def place(ch, p):
        pa, adv = recentre_x(ch, p)
        return {"p": pa, "adv": adv, "pins": []}
    h = PW / 2 - T / 2
    opc = lambda ch, p: op_cell(M, p)                     # sym-math: one advance for the operators (op_cell)
    chosen["+"] = opc("+", _union(line([(-h, AX), (h, AX)], T), line([(0, AX - h), (0, AX + h)], T)))
    gap_eq = max(0.75 * S, 0.16 * PW)                     # SYM: never under 0.16 PW (0.75 s left 13 units at 100: = read as one bar)
    dq = (T + gap_eq) / 2
    chosen["="] = opc("=", _union(line([(-h, AX + dq), (h, AX + dq)], T), line([(-h, AX - dq), (h, AX - dq)], T)))
    if "×" in G:
        xw = 0.92 * PW; e = (xw - T) / 2
        chosen["×"] = opc("×", _union(line([(-e, AX - e), (e, AX + e)], T), line([(-e, AX + e), (e, AX - e)], T)))
    if "÷" in G:
        off = T / 2 + GAP + R
        bar = line([(-h, AX), (h, AX)], T)
        g = opc("÷", _union(bar, _circle(0, AX + off, R), _circle(0, AX - off, R)))
        bx = g["p"].bounds; cxd = (bx[0] + bx[2]) / 2
        g["p"] = _xf(bar, e=cxd); g["pins"] = [(cxd, AX + off), (cxd, AX - off)]
        chosen["÷"] = g
    for ch in "<>~":
        if ch not in G: continue
        b = G[ch]["p"].bounds
        chosen[ch] = {"p": _xf(G[ch]["p"], f=AX - (b[1] + b[3]) / 2), "adv": G[ch]["adv"], "pins": []}

    # ---- ^ : a chevron of weight S, apex on the cap height, legs to 0.6 XH, 0.8 XH wide -------------
    if "^" in G:
        hw = (0.8 * XH - S) / 2 + 0.75 * max(0.0, S - 120)   # wcons: above 700 the legs spread so the V stays open
        chosen["^"] = place("^", line([(-hw, 0.6 * XH + S / 2), (0, CAP - S / 2), (hw, 0.6 * XH + S / 2)], S))

    # ---- * : five round-capped arms, weight 0.75 S (six S arms fuse at this size), top on CAP -----
    if "*" in G:
        ah = 0.5 * CAP; w = 0.75 * S; rr = ah / 2 - w / 2
        if S > 120:   # wcons: above 700 the arms fused into a blob (tips 126 apart, arms 135 at 900): arms thicken
            ah += 0.5 * (S - 120); w = 90 + 0.45 * (S - 120); rr = ah / 2 - w / 2   # slower, the star grows a little
        # a five-point star's top arm reaches rr above the centre, the lower two only rr·cos36 below
        cyA = CAP - w / 2 - rr
        arms = [line([(0, cyA), (rr * math.sin(math.radians(72 * i)), cyA + rr * math.cos(math.radians(72 * i)))], w) for i in range(5)]
        chosen["*"] = place("*", _union(*arms))

    # ==== SYM early: axis, bracket band and descending classes (2026-09-27, symbols.html) ==========
    chosen.update(sym_early(M, G, place, PW, h, gap_eq))
    # ==== end SYM early =========================================================================

    # ---- write into G ------------------------------------------------------------------------
    for ch, g in chosen.items():
        if ch not in G and ch not in "…":
            continue
        G[ch] = {"p": g["p"], "adv": g["adv"], "pins": [(round(x, 1), round(y, 1)) for x, y in g.get("pins", [])]}
        changed.add(ch)

    # ---- DOTSPEC (playground re-draws pins from it) -------------------------------------------
    def spec(ch, entries, only=False):
        if ch in G:
            dots[ch] = {"only": only, "adv0": G[ch]["adv"], "pins": entries}
    for ch in ",‚":
        spec(ch, [["base", G[ch]["pins"][0][0], round(2 * QR, 1), round(QR, 1)]])
    spec("„", [["base", x, round(2 * QR, 1), round(QR, 1)] for x, _ in G["„"]["pins"]] if "„" in G else [])
    spec(";", [["top", G[";"]["pins"][0][0], XO, round(QR, 1)], ["base", G[";"]["pins"][1][0], round(2 * QR, 1), round(QR, 1)]])
    spec("!", [["base", G["!"]["pins"][0][0], round(2 * QR, 1), round(QR, 1)]])
    spec("¡", [["top", G["¡"]["pins"][0][0], XO, round(QR, 1)]])
    spec("¿", [["top", G["¿"]["pins"][0][0], XO, round(QR, 1)]])
    spec("…", [["base", x, round(2 * QR, 1), round(QR, 1)] for x, _ in G["…"]["pins"]])
    for ch in "’‘“”'\"÷":
        if ch in G and G[ch]["pins"]:
            spec(ch, [["mid", x, y, round(QR, 1)] for x, y in G[ch]["pins"]])

    # ---- report lines ------------------------------------------------------------------------
    f0 = lambda v: f"{v:.0f}"
    mods += [
        ["축", "수학 축 하나", f"- – — · + = < > × ÷ ~ 와 괄호 중심을 부모 하이픈 중심 {f0(AX)}({AX/XH:.3f} XH)에 — 참고 서체 0.54~0.63"],
        [", ; ’ ‘ “ ” ‚ „", "쉼표 = 핀 + 꼬리", f"쉼표 머리는 마침표 핀 그대로(같은 자리·같은 폭), 꼬리 끝 {f0(M['YB'])}(−0.24 XH). 따옴표 ’는 쉼표를 들어 핀을 i 핀 자리에, ‘는 그걸 180° 돌림 — 모든 따옴표 아랫선 {f0(M['QB'])}"],
        ["' \"", "쐐기" if OPT["quote"] == "wedge" else "핀+곧은 꼬리", f"윗끝 QT {f0(M["QT"])}(i 핀 윗끝 — 곡선 따옴표와 같은 띠), 아랫끝 따옴표선 {f0(M['QB'])}, 폭 S→0.7S, \" 두 획 사이 0.5 S"],
        ["! ¡", "i를 180° 돌림", f"i 세로획 그대로 S 한 굵기, 둥근 윗끝, 핀과 틈 GAP {f0(GAP)}, 윗끝 {'CAP ' + str(CAP) if OPT['excl'] == 'cap' else 'ASC ' + str(ASC)}. ¡는 !를 뒤집어 핀 윗끝 {XO}"],
        ["@", "바로 선 @", f"고리는 모든 굵기에서 한 크기(윗끝 O 윗끝, 밑끝 −0.25 XH), a는 limn의 a 구성, 가족의 펜(o의 대비)·둥근 이음 — {at[OPT['at']][1]}"],
        *([["&", "닫힌 고리 &", f"O 높이, 가족의 펜(o의 대비)·둥근 끝·둥근 이음 — {amp[OPT['amp']][1]}"]] if OPT["amp"] in amp else []),
        ["( ) [ ] { } | / \\", "괄호 띠", f"괄호는 높이 그대로 중심만 축으로(윗끝 {f0(M['BT'])}, 아랫끝 {f0(M['BB'])}). | / \\ 는 같은 띠를 S 굵기 한 획으로, / \\ 기울기 20°"],
        ["+ = × ÷", "한 크기", f"잉크 {f0(PW)}(0.9 XH) 정사각, 막대 굵기 T = 줄기 {f0(T)}. = 사이 흰 틈 0.75 S, ÷의 점은 핀(막대와 GAP)"],
        ["+ − = × ÷ ± < > ~ ¬", "한 폭", f"연산자는 모두 한 폭 {round(PW + 2 * M['OP_SB'])}: 잉크를 PW 칸 가운데에, 양옆 여백 {M['OP_SB']:.0f} = 부모 = 의 옆 여백 + o 옆 여백 × 0.7(글자 간격과 함께 움직임). 부모의 +는 ± 32~34, < > 40, = ÷ ~ ¬ 50 이라 잉크가 같아도 폭이 다르고, Inter·Pretendard는 한 폭. 화살표·키보드 기호는 o 옆 여백 × 0.47을 더"],
        ["– …", "길이 · 간격", f"- – — 는 T 굵기의 둥근 막대 하나(부모의 길이), en 대시 = 하이픈 × 1.6 (참고 1.64), … = 핀 셋, 간격 3 PIN_R"],
        ["* ^", "다시 그림", "* 다섯 팔 0.75 S(S로는 가운데가 뭉침), 윗끝 CAP · ^ S 굵기 꺾쇠, 꼭지 CAP, 다리 0.6 XH"],
    ]
    ST.update(changed=changed, adv_per=adv_per, adv_col=adv_col)
    if os.environ.get("LIMN_PUNCT_DUMP"):
        _dump(variants, inv_q, M, at)
    return {"dotspec": dots, "mods": mods, "changed": changed}


# ---------------------------------------------------------------- kerning
def _dilate(p, d):
    q = pathops.Path(p)
    q.stroke(2 * d, pathops.LineCap.ROUND_CAP, pathops.LineJoin.ROUND_JOIN, 4)
    q.convertConicsToQuads()
    try:
        return _union(p, q)
    except pathops.PathOpsError:        # (C-05) rare numeric failure on big text-cut pins: retry with a
        for dd in (d + 0.5, d - 0.5):   # hair-different pen, else hand back both (nonzero fill = union)
            q = pathops.Path(p); q.stroke(2 * dd, pathops.LineCap.ROUND_CAP, pathops.LineJoin.ROUND_JOIN, 4); q.convertConicsToQuads()
            try:
                return _union(p, q)
            except pathops.PathOpsError:
                pass
        # 2026-09-29: the hand-back below is unusable where the stroker itself made a bad contour (every later
        # intersection with it failed: ₺ ₾ Ş Ţ at the 12 px cut, ₕ ₙ K at 200); the outline with its points on a
        # coarser grid (under half a unit off, far below the 4-unit clearance steps) strokes cleanly
        from fontTools.pens.roundingPen import RoundingPen
        for g in (0.25, 1.0):
            pg = pathops.Path(); p.draw(RoundingPen(pg.getPen(), roundFunc=lambda v, g=g: round(v / g) * g))
            q = pathops.Path(pg); q.stroke(2 * d, pathops.LineCap.ROUND_CAP, pathops.LineJoin.ROUND_JOIN, 4); q.convertConicsToQuads()
            try:
                return _union(pg, q)
            except pathops.PathOpsError:
                pass
        out = pathops.Path(p); out.addPath(q)
        return out


def _with_pins(G, ch, R):
    p = pathops.Path(G[ch]["p"])
    for x, y in G[ch]["pins"]:
        p = _union(p, _circle(x, y, R))
    return p


def punct_kern(KERN, G):
    """Kerning for the rebuilt glyphs:
      1. , and ; are the period and colon with a tail: they take the period's / colon's pairs.
      2. every pair that has a rebuilt glyph, or a glyph the parent does not kern, on one side keeps at least GAP
         white between the inks (0.6 S next to a superior); a pair closer than that is opened just enough and logged."""
    M = ST["M"]; R, GAP = M["PIN_R"], M["GAP"]
    for k in [k for k in KERN if "," in k or ";" in k]:
        KERN_LOG.append(("drop", k, KERN.pop(k)))
    for k, v in list(KERN.items()):
        for src, dst in ((".", ","), (":", ";")):
            if src in k and k.count(src) == 1:
                nk = k.replace(src, dst)
                if all(c in G for c in nk):
                    KERN[nk] = v; KERN_LOG.append(("copy", nk, v))
    # a superior (T² f² V²) keeps more: the pen of 800-900 brought it within GAP of an overhanging letter
    SUPER = set("¹²³⁰⁴⁵⁶⁷⁸⁹⁺⁻⁼⁽⁾ⁿⁱ")
    import unicodedata
    chars = [c for c in G if c != "림" and unicodedata.category(c) != "Mn"]     # combining marks do not kern
    ink = {c: _with_pins(G, c, R) for c in chars}
    box = {c: ink[c].bounds for c in chars if not _empty(ink[c])}
    B = ST["before"]
    old_ink = {c: _with_pins(B, c, R) for c in B if c in chars}
    from shapely import affinity as _aff
    import geom as _geom
    shp = {}

    def shape_of(p):
        k = id(p)
        if k not in shp: shp[k] = (p, _geom.shape(p))           # (keep p alive: the id stays its own)
        return shp[k][1]

    def clearance(Lp, Rp, dx, clr):
        """White between two inks set dx apart, in 4-unit steps up to clr (the ink distance, rounded down to a step)."""
        d = shape_of(Lp).distance(_aff.translate(shape_of(Rp), dx, 0))
        return min(4 * int(clr / 4 + 0.999), 4 * int(d / 4)) if d < clr else 4 * int(clr / 4 + 0.999)

    # every glyph not kerned by the parent is measured against every neighbour (build_font's kerning coverage)
    todo = set(ST["changed"]) | {c for c in chars if c not in ST.get("parent_kerned", set()) and c not in ST.get("classed", set())}
    ST["kern_measured"] = todo
    # a screen before the exact test: row profiles 2 units apart (the left glyph's right edge dilated by clr, the right
    # glyph's left edge); a pair whose profiles stay 3 units clear of each other is clear of clr
    import numpy as np
    from weights import _flat
    Y0, STEP, NR = -700.0, 2.0, 1000
    INF = 1e9

    def profile(p):
        lo, hi = np.full(NR, INF), np.full(NR, -INF)
        for c in p.contours:
            pl = _flat(c, 8); n = len(pl)
            for i in range(n):
                (x0, y0), (x1, y1) = pl[i], pl[(i + 1) % n]
                if y0 == y1: continue
                if y0 > y1: x0, y0, x1, y1 = x1, y1, x0, y0
                j0 = max(0, int(np.ceil((y0 - Y0) / STEP))); j1 = min(NR - 1, int(np.floor((y1 - Y0) / STEP)))
                if j1 < j0: continue
                ys = Y0 + STEP * np.arange(j0, j1 + 1); xs = x0 + (ys - y0) * (x1 - x0) / (y1 - y0)
                lo[j0:j1 + 1] = np.minimum(lo[j0:j1 + 1], xs); hi[j0:j1 + 1] = np.maximum(hi[j0:j1 + 1], xs)
        return lo, hi
    prof = {c: profile(ink[c]) for c in box}
    env = {}

    def envelope(c, clr):
        if (c, clr) not in env:
            hi = prof[c][1]; e = hi.copy(); w = int(clr / STEP)
            for k in range(1, w + 1):
                dxk = (clr * clr - (k * STEP) ** 2) ** 0.5
                e[k:] = np.maximum(e[k:], hi[:-k] + dxk); e[:-k] = np.maximum(e[:-k], hi[k:] + dxk)
            env[(c, clr)] = e
        return env[(c, clr)]

    def clear_by_profile(L, Rt, dx, clr):
        lo = prof[Rt][0]; e = envelope(L, clr)
        m = (lo < INF / 2) & (e > -INF / 2)
        return not m.any() or float(np.min(lo[m] + dx - e[m])) > 3.0
    NCHK = [0, 0, 0]
    for a in todo:
        if a not in box: continue
        for b in chars:
            for L, Rt in ((a, b), (b, a)):
                if L not in box or Rt not in box: continue
                pair = L + Rt
                clr = max(GAP, 0.6 * M["S"]) if (L in SUPER or Rt in SUPER) else GAP
                k0 = KERN.get(pair, 0); k = k0
                NCHK[0] += 1
                if box[Rt][0] + G[L]["adv"] + k - box[L][2] >= clr: continue      # the boxes are clr apart: so are the inks
                NCHK[1] += 1
                if clear_by_profile(L, Rt, G[L]["adv"] + k, clr): continue
                NCHK[2] += 1
                if shape_of(ink[L]).distance(_aff.translate(shape_of(ink[Rt]), G[L]["adv"] + k, 0)) >= clr: continue
                # closer than clr: open only to what the parent pair had (never above clr) — the
                # parent's own tight pairs, such as () or f', are its design, not a clash
                want = clr
                if L in old_ink and Rt in old_ink and not _empty(old_ink[L]) and not _empty(old_ink[Rt]) and clr == GAP:
                    want = min(clr, clearance(old_ink[L], old_ink[Rt], B[L]["adv"] + k0, clr))
                while k < k0 + 300 and clearance(ink[L], ink[Rt], G[L]["adv"] + k, clr) < want:
                    k += 4
                if k != k0:
                    KERN[pair] = k; KERN_LOG.append(("open", pair, k0, k))
    if os.environ.get("LIMN_TIMING"):
        import sys
        print("punct_kern pairs: all / box / profile:", NCHK[:3], "todo", len(todo), file=sys.stderr)
    if os.environ.get("LIMN_PUNCT_LOG"):
        import sys
        for e in KERN_LOG:
            print("punct kern", *e, file=sys.stderr)
        print("punct mid-dot vs axis", ST.get("mid_dot_off"), file=sys.stderr)
    return KERN_LOG


# ---------------------------------------------------------------- page data
def _d(p):
    from fontTools.pens.svgPathPen import SVGPathPen
    from fontTools.pens.transformPen import TransformPen
    pen = SVGPathPen(None, ntos=lambda v: ("%.1f" % v).rstrip("0").rstrip("."))
    p.draw(TransformPen(pen, (1, 0, 0, -1, 0, 0)))
    return pen.getCommands()


def _dump(variants, inv_q, M, at):
    out = {"opt": OPT, "m": {k: round(v, 2) for k, v in M.items() if isinstance(v, (int, float))},
           "at_info": {k: at[k][1] for k in at}, "variants": {}}
    # SYM: the class numbers for symbols.html (pens, whites, the & variants' notes)
    pens = sym_pens(M)
    out["sym"] = {"DENSE": [round(v, 1) for v in pens["DENSE"]], "LIGHT": [round(v, 1) for v in pens["SUP"]],
                  "PEN": [round(v, 1) for v in M["PEN"]], "WS": round(sym_white(M), 1), "K_SUP": K_SUP, "K_REG": K_REG,
                  "PW": round(0.9 * M["XH"], 1), "GAP_EQ": round(max(0.75 * M["S"], 0.16 * 0.9 * M["XH"]), 1),
                  "amp_info": {k: v[1] for k, v in ST.get("amp", {}).items()}}
    for vk, glyphs in variants.items():
        out["variants"][vk] = {ch: {"d": _d(g["p"]), "adv": g["adv"], "pins": [[round(x, 1), round(-y, 1)] for x, y in g.get("pins", [])]}
                               for ch, g in glyphs.items()}
    with open(os.environ["LIMN_PUNCT_DUMP"], "w") as fh:
        json.dump(out, fh, ensure_ascii=True, separators=(",", ":"))
