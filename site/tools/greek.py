"""limn Greek: the monotonic Greek alphabet (U+0370-03FF) on limn's own letters, pens and rules.

Quicksand has no Greek, so nothing here is copied from a parent: every letter is limn's.

  greek.build(globals())     build_font.py, right after 림: the Latin letters are final there (spurless n,
                             feet, fillets, symmetry, Q) except their side bearings. Builds the shapes and
                             hooks late() onto accents.build.
  late(ns)                   after accents.build (side bearings, figures and the accented Latin are done):
                             copies, side bearings, tonos and dialytika, aliases, kerning classes, bars
  twins(ns)                  just before accents.kern: a copy (Υ = Y) takes its twin's final pairs
  The kerning itself is the Latin pipeline's: punct_kern and the bars rule measure the Greek glyphs too, then
  accents.kern gives each letter its class's pairs (kcls), drops the pin clearance where the letter has no
  pin (ι ί), and opens pairs where a mark (tonos, dialytika pins) comes close.

Rules (numbers at 700 on curve D, UPM 1000: s 107, x-height 531, ascender 740, descender -200, cap 700):

  same form   Α Β Ε Ζ Η Ι Κ Μ Ν Ο Ρ Τ Υ Χ ο ν ϲ Ϲ ϳ Ϳ are limn's A B E Z H I K M N O P T Y X o v c C j J:
              the same outline, advance and kerning (pair by pair, twins()). µ (U+00B5) is μ (it was
              Quicksand's µ, which stops short of the x-height and the descender); ; (U+037E) is ;, · (U+0387) ·.
  from parts  a Greek letter whose parts are in a Latin letter is cut from it:
                ι  t's stem and hook, the stem ending round at the x-height (the dotless i's top)
                τ  ι under a bar in t's thickness, 0.9 o long, the stem at 0.45 of it (t's own bar is short)
                κ  k with its stem ending at the x-height
                η  n, the right stem down to the descender       μ  u, the left stem down to the descender
                υ  u's left half and its mirror (both arms end round at the x-height)
                ω  two υ bowls sharing the middle arm, which ends round at 0.58 x-height; narrowed
                   like m (MK)
                α  o and one straight stroke leaning 0.22 that replaces the bowl's right side: its top
                   stands above the shoulder, its foot runs out past the bowl (Inter, Comfortaa)
                ρ  o and a stem from its middle down
                σ  o and a bar on its top, reaching 0.12 o past the bowl
                π  two stems n's pitch apart under a bar in t's thickness, 0.75 of t's overhang past them
                θ  o drawn up to the ascender (straight sides) and a bar across (e's bar)
                γ  v and a stem from its vertex to the descender
                Γ  F without its middle bar      Π  Γ and its mirror, H wide      Λ  V turned
                Δ  Λ and a bar on the baseline   Σ  Z's lower half and its mirror, the vertex round
                Θ  O and a free bar (0.6 of the counter), the rounded kin's Θ (M+ Rounded, Comfortaa)
  pen         the rest is drawn with the family's pen (punct.pen_line: o's stem wide, o's hairline tall;
              O's for capitals), round ends, joints closed round (the fillet radius, smaller where a white of the
              letter is narrower than twice it: ε at 900; the closing checked as sym_math's), as limn drew
              @ & Q: β δ ε ζ ξ ς λ φ ϕ χ ψ Ξ Φ Ψ Ω and the symbol forms ϑ ϖ ϱ ϰ. φ is the loop form of the references (U+03C6 in Inter,
              Pretendard, M+ Rounded): a stem, a D on its right, an open half-ellipse on its left whose top
              keeps max(GAP, 2.5 FR) from the stem; ϕ (U+03D5, maths) the closed ellipse with the stroke
              through, descender to ascender. ς ζ ξ share one tail: from the bowl's bottom round, no further
              than 0.8 of the letter, hooking back left on the descender. ϵ is c with e's bar
  proportions from Inter, Pretendard, M+ Rounded 1c and Comfortaa (ink width / o, heights / x-height):
              ascender letters (β δ ζ θ λ ξ) reach limn's ascender, descenders limn's descender; ψ's
              stem rises to the cap height (M+ Rounded, Comfortaa 1.32 x-height); φ's stem ends in the
              bowl (Inter, Pretendard, M+ Rounded)
  feet        limn's rule, by flatten_feet: a stem that ends alone on the baseline or the descender is
              flat (η μ ρ φ ψ β γ π Π Γ Φ Ψ), every other end round; fillets by fillet_corners
  spacing     Tracy classes of tools/spacing.json (side = class ratio x o's side, O's for capitals),
              assigned per side in SIDES; ι's hooked side is its own ratio (IOTA_R). Bars in line: π σ τ
              (x-height) and Γ Ξ Σ (cap height, baseline) join the "bars" rule's lists, so ππ ΓΤ ... keep
              0.2 s of white like TT rt
  tonos       limn's acute (accents.py: the parent's macron weight, 140 long, round ends) standing up
              at 65 degrees (acute 50): the references' tonos is 0.7-0.8 as wide as their acute. Lower
              case: on the mark line (x-height + GAP) over the letter's optical centre, like é.
              Capitals: left of the letter, its top at the cap height + 0.75 GAP; the letter moves right
              until 1.25 GAP of white stands between them (Ά keeps A's width: the tonos sits in the
              leg's open corner), and the tonos hangs into the side bearing (its ink starts on the origin). Dialytika = two pins (ï); ΐ ΰ: the tonos between two pins, each pin
              GAP clear of it.
"""
import math
import sys

import pathops

import accents
from punct import atq_contrast, bez_pts, ell_pts, pen_line
from sym_math import round_joins as round_joins_checked


def _holes(p):
    """The number of counters of an outline (contours turning against the largest, on a simplified copy)."""
    q = pathops.Path(p); q.simplify()
    cs = list(q.contours)
    if len(cs) < 2:
        return 0
    big = max(cs, key=lambda c: abs(c.area))
    return sum(1 for c in cs if c.clockwise != big.clockwise)

# ---------------------------------------------------------------- what the alphabet is made of
COPY = {"Α": "A", "Β": "B", "Ε": "E", "Ζ": "Z", "Η": "H", "Ι": "I", "Κ": "K", "Μ": "M", "Ν": "N", "Ο": "O",
        "Ρ": "P", "Τ": "T", "Υ": "Y", "Χ": "X", "ο": "o", "ν": "v", "ϲ": "c", "Ϲ": "C",   # ϲ Ϲ: lunate sigma
        "Ϳ": "J"}                                                  # Ϳ: the capital yot (ϳ = j), so both cases map
LOWER = "αβγδεζηθικλμνξοπρσςτυφχψω"
UPPER = "ΑΒΓΔΕΖΗΘΙΚΛΜΝΞΟΠΡΣΤΥΦΧΨΩ"
TONOS_LC = {"ά": "α", "έ": "ε", "ή": "η", "ί": "ι", "ό": "ο", "ύ": "υ", "ώ": "ω"}
TONOS_UC = {"Ά": "Α", "Έ": "Ε", "Ή": "Η", "Ί": "Ι", "Ό": "Ο", "Ύ": "Υ", "Ώ": "Ω"}
DIALYTIKA = {"ϊ": "ι", "ϋ": "υ", "Ϊ": "Ι", "Ϋ": "Υ"}
DIAL_TONOS = {"ΐ": "ι", "ΰ": "υ"}
ALIAS = {";": ";", "·": "·", "µ": "μ", "ϳ": "j"}          # Greek question mark, ano teleia, micro sign, yot

# Tracy class of every side (tools/spacing.json "lc" / "uc"); a Latin side name ("t L") takes that side's class
SIDES = {
    "α": ("round", "ι R"), "β": ("straight", "round"), "γ": ("v", "v"), "δ": ("round", "round"),
    "ε": ("round", "c R"), "ζ": ("round", "c R"), "η": ("arch", "arch"), "θ": ("round", "round"),
    "ι": ("straight", "ι R"), "κ": ("straight", "k R"), "λ": ("v", "v"), "μ": ("arch", "arch"),
    "ξ": ("round", "c R"), "π": ("t L", "t L"), "ρ": ("straight", "round"), "σ": ("round", "t R"),
    "ς": ("round", "c R"), "τ": ("t L", "t R"), "υ": ("arch", "arch"), "φ": ("round", "round"),
    "χ": ("x", "x"), "ψ": ("arch", "arch"), "ω": ("arch", "arch"), "ϕ": ("round", "round"), "ϵ": ("round", "c R"),
    "Γ": ("straight", "F R"), "Δ": ("A", "A"), "Θ": ("round", "round"), "Λ": ("A", "A"),
    "Ξ": ("E R", "E R"), "Π": ("straight", "straight"), "Σ": ("Z", "Z"), "Φ": ("round", "round"),
    "Ψ": ("U", "U"), "Ω": ("round", "round"),
    "ϑ": ("round", "round"), "ϖ": ("t L", "t L"), "ϱ": ("round", "round"), "ϰ": ("x", "x"),
}
# ι's right side is a stem with t's hook at the foot: the white above the hook reads as the letter's own,
# as under r's arm (0.20-0.30). The references set it close: Inter and Pretendard 0.0-0.1 x o's side,
# Comfortaa 0.7, M+ Rounded 1.4.
IOTA_R = 0.35
# kerning classes: (class on the left of a pair = this letter's right side, class on its right = its left side)
KCLS = {"α": ("a", "o"), "β": ("b", "b"), "γ": ("v", "v"), "δ": ("o", "o"), "ε": ("c", "c"), "ζ": ("c", "c"),
        "η": ("n", "n"), "θ": ("o", "o"), "ι": ("i", "i"), "κ": ("k", "k"), "λ": ("x", "x"), "μ": ("u", "u"),
        "ξ": ("c", "c"), "π": ("t", "t"), "ρ": ("p", "p"), "σ": ("o", "o"), "ς": ("c", "c"), "τ": ("t", "t"),
        "υ": ("u", "u"), "φ": ("o", "o"), "χ": ("x", "x"), "ψ": ("u", "u"), "ω": ("u", "u"), "ϕ": ("o", "o"), "ϵ": ("e", "c"),
        "Γ": ("F", "F"), "Δ": ("A", "A"), "Θ": ("O", "O"), "Λ": ("A", "A"), "Ξ": ("E", "Z"), "Π": ("H", "H"),
        "Σ": ("Z", "Z"), "Φ": ("O", "O"), "Ψ": ("U", "U"), "Ω": ("O", "O"),
        "ϑ": ("o", "o"), "ϖ": ("t", "t"), "ϱ": ("o", "o"), "ϰ": ("x", "x")}
TONOS_ANGLE = 65                 # degrees; accents.py's acute is 50 (caps 37)
OMEGA_MID = 0.58                 # ω: top of the middle arm / x-height
ALPHA_K = 0.22                   # α: lean of the right stroke (dx / dy)
PI_OV = 0.75                     # π: the bar past the legs, x t's bar left of its stem
GAMMA_LC = -35                   # Γ + lowercase: kerning at 700 on top of F's (by the spacing unit)
ST = {"shapes": {}, "feet": {}, "prefeet": {}, "fail": {}}


def _fail(ch, e):
    ST["fail"][ch] = repr(e)


# ---------------------------------------------------------------- build (right after 림)
def build(ns):
    G, S, XH, XO, ASC, DESC, CAP = ns["G"], ns["S"], ns["XH"], ns["XO"], ns["ASC"], ns["DESC"], ns["CAP"]
    bounds, slice_at, rect, circle = ns["bounds"], ns["slice_at"], ns["rect"], ns["circle"]
    union, diff, inter, xform = ns["union"], ns["diff"], ns["inter"], ns["xform"]
    FILLET = ns.get("FILLET", 0.25)
    FR = FILLET * min(S, 120)                                      # the fillet radius; joints close with it
    OSH, GAP = ns["OSH"], ns["GAP"]

    o = pathops.Path(G["o"]["p"]); ox0, oy0, ox1, oy1 = bounds(o)
    ow, ocx, ocy = ox1 - ox0, (ox0 + ox1) / 2, (oy0 + oy1) / 2
    SV, SH = atq_contrast(o)                                       # o's stem and hairline: the lowercase pen
    bot_c, top_c = oy0 + SH / 2, oy1 - SH / 2                     # o's centre line, bottom and top
    rx_o, ry_o = (ow - SV) / 2, (oy1 - oy0 - SH) / 2
    O = pathops.Path(G["O"]["p"]); Ob = bounds(O)
    Ow, Ocx = Ob[2] - Ob[0], (Ob[0] + Ob[2]) / 2
    SVc, SHc = atq_contrast(O)                                     # O's: the capital pen
    OSHc = Ob[3] - CAP

    def pen(pts, cap=False):
        return pen_line(pts, SVc, SHc) if cap else pen_line(pts, SV, SH)

    def close(p, r=FR):
        """The joints closed round with radius r, by sym_math's checked closing: skia's strokes can mis-wind a band and
        hand back a filled counter with the bowl cut off (ϑ at 400: 1 contour, 70..740), which the check retries a hair
        off. The radius stays under the letter's whites (round_joins: a white narrower than 2 r closes): where the pen
        leaves less than that between two strokes (ε's upper aperture at 900, 47 units against 2 FR = 60), a closing that
        would shut it into a new counter runs with a smaller radius."""
        n0 = _holes(p)
        q = round_joins_checked(p, r)
        while _holes(q) > n0 and r > 1.0:
            r *= 0.8
            q = round_joins_checked(p, r)
        q.simplify()
        return q

    def P(ch):
        return pathops.Path(G[ch]["p"])

    def stem_at(p, y, which=0, lo=0.75, hi=1.35):
        ivs = [iv for iv in slice_at(p, y) if lo * S <= iv[1] - iv[0] <= hi * S]
        return ivs[which]

    def mirror(p, x):
        return xform(p, -1, 0, 0, 1, 2 * x, 0)

    def rounded_stem(xa, xb, y0, y1, top=True, bottom=True):
        """A vertical stem from y0 to y1 with round (semicircle) ends; flatten_feet squares the ones that
        stand on a line."""
        w = xb - xa; r = w / 2; xc = (xa + xb) / 2
        a, b = (y0 + r) if bottom else y0, (y1 - r) if top else y1
        p = rect(xa, a, xb, b)
        if top: p = union(p, circle(xc, b, r))
        if bottom: p = union(p, circle(xc, a, r))
        return p

    def fill_slivers(p, k=0.15):
        """Fill every hole smaller than k x the largest one (the counter)."""
        cs = list(p.contours)
        if len(cs) < 3: return p
        outer = max(cs, key=lambda c: abs(c.area))
        holes = [c for c in cs if c.clockwise != outer.clockwise]
        big = max(abs(c.area) for c in holes)
        q = pathops.Path(); pen_ = q.getPen()
        for c in cs:
            if c in holes and abs(c.area) < k * big: continue
            c.draw(pen_)
        q.simplify(); return q

    def y_extrude(p, cy, dh):
        """Split at y = cy and move the upper part up by dh; the sides are filled straight (vertical there)."""
        lo = inter(p, rect(-1e4, -1e4, 1e4, cy)); up = xform(inter(p, rect(-1e4, cy, 1e4, 1e4)), f=dh)
        out = union(lo, up)
        for c in inter(p, rect(-1e4, cy - 0.25, 1e4, cy + 0.25)).contours:
            b = c.bounds; out = union(out, rect(b[0], cy - 0.5, b[2], cy + dh + 0.5))
        out.simplify(); return out

    def bar_rows(p, x, y0, y1):
        """Vertical runs of ink on the line x between y0 and y1: [(bottom, top), ...]."""
        runs = []
        for c in inter(p, rect(x - 0.25, y0, x + 0.25, y1)).contours:
            b = c.bounds; runs.append((b[1], b[3]))
        return sorted(runs)

    shapes = ST["shapes"]

    def put(ch, fn):
        try:
            p = fn(); p.simplify()
            shapes[ch] = p
        except Exception as e:                                    # report, never break the build
            _fail(ch, e)

    # -- t: stem, bar and hook (ι τ α π)
    t = P("t"); tb = bounds(t)
    ta, tbx = stem_at(t, 0.5 * XH); tw = tbx - ta; tc = (ta + tbx) / 2
    y_f = 0.5 * XH                                                 # top of t's plain stem (under the bar and its fillets)
    while y_f < XH and any(iv[0] <= tc <= iv[1] and iv[1] - iv[0] <= tw + 0.6 for iv in slice_at(t, y_f + 1)):
        y_f += 1
    t_runs = bar_rows(t, tb[0] + 0.5 * tw, 0.5 * XH, tb[3])       # t's bar, read at its left end
    T_BAR = t_runs[-1][1] - t_runs[-1][0]; T_TOP = t_runs[-1][1]
    T_OV = ta - min(iv[0] for iv in slice_at(t, T_TOP - T_BAR / 2))   # the bar left of the stem

    def iota():
        low = inter(t, rect(-1e4, -1e4, 1e4, y_f - 2))
        return union(low, rounded_stem(ta, tbx, y_f - 3, XH, bottom=False))
    put("ι", iota)

    def tau():
        # ι under a bar in t's thickness, 0.9 o long, the stem at 0.45 of it (t's own bar is too short for τ)
        io = shapes["ι"]; ia, ib = stem_at(io, 0.5 * XH); W = 0.9 * ow
        x0 = (ia + ib) / 2 - 0.45 * W; y = XH - T_BAR / 2
        return union(io, pen_line([(x0 + SV / 2, y), (x0 + W - SV / 2, y)], SV, T_BAR))
    put("τ", tau)

    def kappa():
        k = P("k"); ka, kb = stem_at(k, 0.9 * XH); kc = (ka + kb) / 2; kw = kb - ka
        y = XH                                                     # top of the arm's joint on the stem
        while y > 0.3 * XH and all(not (iv[0] <= kc <= iv[1]) or iv[1] - iv[0] <= kw + 0.6 for iv in slice_at(k, y)):
            y -= 1
        yc = min(y + 3, XH - kw / 2 - 1)
        return union(diff(k, rect(ka - 1, yc, kb + 1, 1e4)), rounded_stem(ka, kb, yc - 1, XH, bottom=False))
    put("κ", kappa)

    def eta():
        n = P("n"); ra, rb = stem_at(n, 0.3 * XH, -1)
        return union(n, rounded_stem(ra, rb, DESC, 0.3 * XH, top=False))
    put("η", eta)

    u = P("u"); ub = bounds(u)
    ula, ulb = stem_at(u, 0.6 * XH, 0); ura, urb = stem_at(u, 0.6 * XH, -1)
    uw = ulb - ula; ulc = (ula + ulb) / 2
    uxm = (ulc + (ura + urb) / 2) / 2                              # the bowl's middle
    uhalf = inter(u, rect(-1e4, -1e4, uxm, 1e4))

    put("μ", lambda: union(u, rounded_stem(ula, ulb, DESC, 0.6 * XH, top=False)))
    put("υ", lambda: union(uhalf, mirror(uhalf, uxm)))

    def omega():
        xr = 2 * uxm - ulc                                         # the right arm of υ = the middle arm of ω
        ytop = OMEGA_MID * XH
        right = inter(mirror(uhalf, uxm), rect(-1e4, -1e4, 1e4, ytop - uw / 2))
        bowl = union(uhalf, right, circle(xr, ytop - uw / 2, uw / 2))
        w = union(bowl, mirror(bowl, xr)); w.simplify()
        mk = ns.get("MK", 0.90)
        return ns["narrow"](w, mk) if mk != 1.0 and "narrow" in ns else w
    put("ω", omega)

    def alpha():
        # o and one straight stroke that is the bowl's right side at mid-height and leans ALPHA_K: its top
        # stands above the right shoulder, its foot runs out past the bowl (Inter, Comfortaa)
        # the stroke takes the place of the bowl's right side: o is kept left of the stroke's centre line
        xm = ox1 - SV / 2; r = S / 2
        top = (xm - ALPHA_K * (XH - r - ocy), XH - r); foot = (xm + ALPHA_K * (ocy - r), r)
        dx, dy = foot[0] - top[0], foot[1] - top[1]; L = math.hypot(dx, dy); ux, uy = dx / L, dy / L
        R = 1e4; ex, ey = top[0] - ux * R, top[1] - uy * R; fx, fy = foot[0] + ux * R, foot[1] + uy * R
        left = pathops.Path(); left.moveTo(ex, ey); left.lineTo(fx, fy); left.lineTo(fx - R, fy); left.lineTo(ex - R, ey); left.close()
        # where the bowl curves away from the stroke above mid-height a sliver of white is shut in between
        # them (a slit at the light weights): it is filled, so the bowl runs into the stroke
        return fill_slivers(close(union(inter(o, left), pen_line([top, foot], S, S))))
    put("α", alpha)

    def rho():
        p = union(o, rect(ox0, DESC + SV / 2, ox0 + SV, ocy), circle(ox0 + SV / 2, DESC + SV / 2, SV / 2))
        return close(p)
    put("ρ", rho)

    def sigma():
        y = oy1 - SH / 2; xe = ox0 + 1.12 * ow - SV / 2
        return close(union(o, pen([(ocx, y), (xe, y)])))
    put("σ", sigma)

    def phi():
        # the loop form, as Inter, Pretendard and M+ Rounded draw U+03C6: a stem from the descender to the
        # bowl's top, a half-ellipse on its right (a D, its top-left corner the pen's round end) and an open one
        # on its left whose top end keeps max(GAP, 2.5 FR) of white from the stem; 1.3 o wide, o's height
        W = 1.30 * ow; xs = W / 2; a = (W - SV) / 2
        white = max(GAP, 2.5 * FR)
        t0 = math.degrees(math.acos(max(-0.95, -(S / 2 + white + SV / 2) / a)))
        right = pen(ell_pts(xs, ocy, a, ry_o, 90, -90, 48))
        left = pen(ell_pts(xs, ocy, a, ry_o, t0, 270, 40))
        return close(union(right, left, rounded_stem(xs - S / 2, xs + S / 2, DESC, top_c, top=False)))
    put("φ", phi)

    def phi_symbol():
        # ϕ (U+03D5, the phi of maths): the closed form, an ellipse 1.25 o wide in o's height, with the stroke
        # through from the descender to the ascender
        W = 1.25 * ow; xc = W / 2
        bowl = pen(ell_pts(xc, ocy, (W - SV) / 2, ry_o, 0, 360, 96))
        return close(union(bowl, rounded_stem(xc - S / 2, xc + S / 2, DESC, ASC)))
    put("ϕ", phi_symbol)

    def lunate_epsilon():
        # ϵ (U+03F5): c and a bar across its middle in e's bar weight, to 0.72 of the letter
        c = P("c"); cb = bounds(c); y = (cb[1] + cb[3]) / 2
        return close(union(c, pen_line([(cb[0] + SV / 2, y), (cb[0] + 0.72 * (cb[2] - cb[0]) - SV / 2, y)], SV, E_BAR)))

    e = P("e"); eb = bounds(e)
    e_runs = bar_rows(e, (eb[0] + eb[2]) / 2, 0.25 * XH, 0.75 * XH)
    E_BAR = max(b - a for a, b in e_runs) if e_runs else SH

    def theta():
        dh = ASC - XH
        bowl = y_extrude(o, ocy, dh)
        yc = (oy0 + oy1 + dh) / 2
        bar = rect(ox0 + SV / 2, yc - E_BAR / 2, ox1 - SV / 2, yc + E_BAR / 2)
        return ns["fillet_corners"](union(bowl, bar), FR)[0] if "fillet_corners" in ns else union(bowl, bar)
    put("θ", theta)
    put("ϵ", lunate_epsilon)

    def gamma():
        v = P("v"); vb = bounds(v)
        yc = 1.0                                                   # the crotch: lowest line where the arms are apart
        while yc < XH and len(slice_at(v, yc)) < 2:
            yc += 1
        low = slice_at(v, 0.5 * yc)
        vc = (low[0][0] + low[-1][1]) / 2
        return close(union(v, rounded_stem(vc - S / 2, vc + S / 2, DESC, max(yc - 2, 0.5 * S), top=False)))
    put("γ", gamma)

    def pi():
        n = P("n"); nst = [(a + b) / 2 for a, b in slice_at(n, 0.3 * XH) if 0.75 * S <= b - a <= 1.35 * S]
        pitch = nst[-1] - nst[0]
        ov = PI_OV * T_OV                                          # the bar past the legs, 3/4 of t's (1.14 o)
        x0 = ov + S / 2; x1 = x0 + pitch; yc = XH - T_BAR / 2
        bar = pen_line([(x0 - S / 2 - ov + SV / 2, yc), (x1 + S / 2 + ov - SV / 2, yc)], SV, T_BAR)
        legs = union(rounded_stem(x0 - S / 2, x0 + S / 2, 0, yc, top=False), rounded_stem(x1 - S / 2, x1 + S / 2, 0, yc, top=False))
        return union(bar, legs)
    put("π", pi)

    def chi():
        x = P("x"); xb = bounds(x); w = 1.18 * (xb[2] - xb[0])       # the ink of x, wider for the taller cross (1.0 o)
        r = S / 2
        a, b = (0 + r, XH - r), (w - r, DESC + r)
        c, d = (w - r, XH - r), (0 + r, DESC + r)
        return union(pen_line([a, b], S, S), pen_line([c, d], S, S))
    put("χ", chi)

    def lam():
        v = P("v"); vb = bounds(v); w = vb[2] - vb[0]; r = S / 2
        top = (0.06 * w + r, ASC - r); foot_r = (w - r, r)
        yj = 0.55 * XH
        tj = (yj - foot_r[1]) / (top[1] - foot_r[1])
        J = (foot_r[0] + (top[0] - foot_r[0]) * tj, yj)
        return union(pen_line([top, foot_r], S, S), pen_line([J, (r, r)], S, S))
    put("λ", lam)

    # ---- pen letters (lowercase): β δ ε ζ ξ ς ψ

    def tail(x_start, w, x0=0.0):
        """The tail of ς ζ ξ: from the bottom of the bowl (heading right) round, no further than 0.8 of the
        letter, and down, hooking back left on the descender (Inter, M+ Rounded, Comfortaa)."""
        R = x0 + 0.80 * w - SV / 2; E = (x0 + 0.54 * w, DESC + SH / 2)
        return bez_pts((x_start, bot_c), (R, bot_c), (R, E[1] + 0.40 * (bot_c - E[1])), E, 32)

    def final_sigma():
        c = P("c"); cb = bounds(c)
        up = inter(c, rect(-1e4, ocy, 1e4, 1e4))
        cx = cb[0] + ow / 2
        arc = ell_pts(cx, ocy, rx_o, ry_o, 180, 270, 24)
        return close(union(up, pen(arc[:-1] + tail(cx, ow, cb[0]))))
    put("ς", final_sigma)

    def epsilon():
        w = 0.96 * ow; xl = SV / 2
        al = (w - SV) / 2; au = 0.86 * al
        yw = bot_c + 0.56 * (top_c - bot_c)                        # waist (centre line): the lower bowl is the larger
        bl, bu = (yw - bot_c) / 2, (top_c - yw) / 2
        cl = (xl + al, yw - bl); cu = (xl + (al - au) * 0.35 + au, yw + bu)
        upper = ell_pts(cu[0], cu[1], au, bu, 38, 270, 40)
        lower = ell_pts(cl[0], cl[1], al, bl, 90, 322, 40)
        tip = (cl[0] + 0.12 * al, yw)
        return close(pen(upper + [tip, (cl[0], yw)] + lower))
    put("ε", epsilon)

    def zeta():
        w = 0.88 * ow; T = ASC - SH / 2
        bar = [(0.18 * w, T), (w - SV / 2, T)]
        # from the bar's end down to the left (vertical at 0.32 x-height), then round into the bottom (horizontal)
        xl, yl = SV / 2, 0.32 * XH; P0 = (w - SV / 2, T)
        down = bez_pts(P0, (P0[0] - 0.55 * w, T - 0.45 * (T - yl)), (xl, yl + 0.30 * (T - yl)), (xl, yl), 40)
        bottom = bez_pts((xl, yl), (xl, yl - 0.55 * (yl - bot_c)), (xl + 0.45 * (0.5 * w - xl), bot_c), (0.50 * w, bot_c), 24)
        return close(pen(bar + down[1:] + bottom[1:] + tail(0.50 * w, w)[1:]))
    put("ζ", zeta)

    def xi():
        w = 0.88 * ow; T = ASC - SH / 2
        yw = 0.92 * XH                                             # waist, as in the references (0.9-1.0 x-height)
        xb = 0.30 * w; xl = SV / 2
        # one stroke: the bar leftwards, round its left end into the small upper bowl, back right to the waist
        # (a tip, as in ε), the large lower bowl, the tail
        bar = [(w - SV / 2, T), (xb, T)]
        upper = bez_pts((xb, T), (xb - 0.40 * w, T), (xl + 0.10 * w, yw), (0.52 * w, yw), 32)
        tip = (0.64 * w, yw)
        lower = bez_pts((0.52 * w, yw), (xl - 0.17 * w, yw), (xl - 0.17 * w, bot_c), (0.50 * w, bot_c), 40)
        return close(pen(bar + upper[1:] + [tip] + lower + tail(0.50 * w, w)[1:]))
    put("ξ", xi)

    def beta():
        w = 0.96 * ow; xs = S / 2
        top_i, bot_i = ASC + OSH, -OSH
        tc_, bc_ = top_i - SH / 2, bot_i + SH / 2
        # waist: the upper counter 0.8 of the lower (tall enough to stay open at 900)
        yw = (tc_ - SH + 0.8 * (bc_ + SH)) / 1.8
        # the waist's tip keeps GAP of white from the stem, and more than the joints' closing can bridge (2 FR),
        # so the two counters stay one at every weight; where the upper bowl is too narrow for that (800-900)
        # it widens until its bottom is the tip
        tip = (xs + S / 2 + max(GAP, 2.5 * FR) + SV / 2, yw)
        al = (w - SV) / 2; au = max(0.84 * al, tip[0] - xs)
        bu, bl = (tc_ - yw) / 2, (yw - bc_) / 2
        cu, cl = (xs + au, yw + bu), (xs + al, yw - bl)
        upper = ell_pts(cu[0], cu[1], au, bu, 180, -90, 48)        # up the left, over the top, round to the waist
        # from the waist round the right to the stem. Where the upper bowl is the wider (900: its bottom is the tip, 29
        # units right of the lower bowl's top), the lower bowl starts under the tip, not at its own top: running back
        # left to that top took the waist's ink 30 units nearer the stem than the tip (white 45 instead of 75) and the
        # closing shut the two counters apart
        t1 = 90.0
        if tip[0] > cl[0] + 0.5:
            t1 = math.degrees(math.acos(min(1.0, (tip[0] - cl[0]) / al)))
        lower = ell_pts(cl[0], cl[1], al, bl, t1, -180, 48)
        p = pen(upper + [tip] + lower)
        return close(union(p, rounded_stem(xs - S / 2, xs + S / 2, DESC, cu[1], top=False)))
    put("β", beta)

    def delta():
        w = ow; T = ASC - SH / 2
        neck = bez_pts((ocx, top_c), (ox0 + 0.02 * w, top_c + 0.35 * (T - top_c)), (ox0 + 0.08 * w, T), (ox0 + 0.42 * w, T), 32)
        top = neck + [(ox0 + 0.80 * w, T)]
        return close(union(o, pen(top)))
    put("δ", delta)

    def psi():
        w = 1.2 * ow; a = (w - SV) / 2; cx = w / 2
        yb = bot_c; b = min(0.9 * a, 0.62 * XH)                     # the cup's bottom on the baseline, arms straight above
        cup = [(cx - a, XH - SV / 2)] + ell_pts(cx, yb + b, a, b, 180, 360, 48) + [(cx + a, XH - SV / 2)]
        stem = rounded_stem(cx - S / 2, cx + S / 2, DESC, CAP)
        return close(union(pen(cup), stem))
    put("ψ", psi)

    # ---- capitals
    def Gamma():
        F = P("F"); fa, fb = stem_at(F, 0.3 * CAP)
        return union(inter(F, rect(-1e4, -1e4, fb + 0.05, 1e4)), inter(F, rect(-1e4, 0.75 * CAP, 1e4, 1e4)))
    put("Γ", Gamma)

    def Pi():
        g = shapes["Γ"]; H = P("H"); hb = bounds(H); gb = bounds(g)
        g = xform(g, e=hb[0] - gb[0]); xm = (hb[0] + hb[2]) / 2
        half = inter(g, rect(-1e4, -1e4, xm + 0.25, 1e4))
        return union(half, mirror(half, xm))
    put("Π", Pi)

    def Lambda():
        V = P("V"); vb = bounds(V)
        return xform(V, -1, 0, 0, -1, vb[0] + vb[2], vb[1] + vb[3])
    put("Λ", Lambda)

    E = P("E"); Eb = bounds(E)
    _ea, _eb = stem_at(E, 0.3 * CAP)
    E_runs = bar_rows(E, _eb + 0.6 * S + FR, -1, CAP + 1)           # E's three bars, read past the joint's fillet
    E_T = min(b - a for a, b in E_runs) if E_runs else SHc
    E_MID = sorted(E_runs, key=lambda r: abs((r[0] + r[1]) / 2 - CAP / 2))[0] if E_runs else (CAP / 2 - E_T / 2, CAP / 2 + E_T / 2)

    def Delta():
        L = shapes["Λ"]
        feet = slice_at(L, 1.0)
        xl, xr = (feet[0][0] + feet[0][1]) / 2, (feet[-1][0] + feet[-1][1]) / 2
        bar = pen_line([(xl, E_T / 2), (xr, E_T / 2)], SVc, E_T)
        return union(L, bar)
    put("Δ", Delta)

    def Sigma():
        Z = P("Z"); zb = bounds(Z); cx, cy = (zb[0] + zb[2]) / 2, (zb[1] + zb[3]) / 2
        lo = inter(Z, rect(-1e4, -1e4, 1e4, cy))
        # the diagonal's direction and thickness, read on the lower half
        y1, y2 = 0.3 * CAP, 0.45 * CAP
        i1 = [iv for iv in slice_at(Z, y1) if iv[1] - iv[0] < 3 * S]; i2 = [iv for iv in slice_at(Z, y2) if iv[1] - iv[0] < 3 * S]
        c1, c2 = (i1[0][0] + i1[0][1]) / 2, (i2[0][0] + i2[0][1]) / 2
        wh = i2[0][1] - i2[0][0]
        dx, dy = c2 - c1, y2 - y1; L = math.hypot(dx, dy); d = (dx / L, dy / L)
        wp = wh * abs(d[1])                                        # perpendicular thickness
        V = (cx, cy)
        def past(dd):                                              # the half-plane beyond the vertex along dd
            n = (-dd[1], dd[0]); R = 1e4
            q = pathops.Path(); pts = [(V[0] + n[0] * R, V[1] + n[1] * R), (V[0] + n[0] * R + dd[0] * R, V[1] + n[1] * R + dd[1] * R),
                                       (V[0] - n[0] * R + dd[0] * R, V[1] - n[1] * R + dd[1] * R), (V[0] - n[0] * R, V[1] - n[1] * R)]
            q.moveTo(*pts[0]); [q.lineTo(*pt) for pt in pts[1:]]; q.close(); return q
        up = xform(lo, 1, 0, 0, -1, 0, 2 * cy)
        dup = (d[0], -d[1])
        s = union(diff(lo, past(d)), diff(up, past(dup)), circle(V[0], V[1], wp / 2))
        return s
    put("Σ", Sigma)

    def Theta():
        cb = [c.bounds for c in diff(max_fill(O), O).contours]
        cb = max(cb, key=lambda b: (b[2] - b[0]) * (b[3] - b[1]))
        cw = cb[2] - cb[0]; L = 0.6 * cw; y = (Ob[1] + Ob[3]) / 2
        bar = pen_line([(Ocx - L / 2 + SVc / 2, y), (Ocx + L / 2 - SVc / 2, y)], SVc, E_T)
        return union(O, bar)

    def max_fill(p):
        outer = max(p.contours, key=lambda c: abs(c.area)); q = pathops.Path(); q.addPath(outer); q.simplify(); return q
    put("Θ", Theta)

    def Xi():
        w = 1.08 * (Eb[2] - Eb[0]); r = SVc / 2
        top = [(r, CAP - E_T / 2), (w - r, CAP - E_T / 2)]
        bot = [(r, E_T / 2), (w - r, E_T / 2)]
        ym = (E_MID[0] + E_MID[1]) / 2; m = 0.70 * w
        mid = [((w - m) / 2 + r, ym), ((w + m) / 2 - r, ym)]
        return union(pen_line(top, SVc, E_T), pen_line(bot, SVc, E_T), pen_line(mid, SVc, E_T))
    put("Ξ", Xi)

    I = P("I"); Ia, Ib = stem_at(I, 0.5 * CAP); Iw = Ib - Ia

    def Phi():
        W = 1.10 * Ow; H = 0.84 * CAP; cx = W / 2
        a, b = (W - SVc) / 2, (H - SHc) / 2
        bowl = pen(ell_pts(cx, CAP / 2, a, b, 0, 360, 96), cap=True)
        return close(union(bowl, rounded_stem(cx - Iw / 2, cx + Iw / 2, 0, CAP)))
    put("Φ", Phi)

    def Psi():
        W = 0.97 * Ow; cx = W / 2; a = (W - SVc) / 2
        yb = 0.28 * CAP + SHc / 2; b = 0.85 * a
        cup = [(cx - a, CAP - SVc / 2)] + ell_pts(cx, yb + b, a, b, 180, 360, 48) + [(cx + a, CAP - SVc / 2)]
        return close(union(pen(cup, cap=True), rounded_stem(cx - Iw / 2, cx + Iw / 2, 0, CAP)))
    put("Ψ", Psi)

    def Omega():
        W = 0.95 * Ow; cx = W / 2; a = (W - SVc) / 2
        top_i = CAP + OSHc; cyb = 0.56 * CAP; b = top_i - SHc / 2 - cyb
        # the bowl runs round to 205 degrees each side, then bends smoothly into a short upright leg that
        # stands on the baseline and turns out into a foot (O's pen throughout)
        arc = ell_pts(cx, cyb, a, b, 205, -25, 64)
        yl = SHc / 2; xl = cx - 0.55 * a; y1 = 0.12 * CAP
        A = arc[0]; ta = (-0.423 * a, 0.906 * b); tl = math.hypot(*ta); ta = (ta[0] / tl, ta[1] / tl)
        h = 0.40 * (A[1] - y1)
        legL = bez_pts((xl, y1), (xl, y1 + h), (A[0] - ta[0] * h, A[1] - ta[1] * h), A, 20)
        legR = [(2 * cx - x, y) for x, y in reversed(legL)]
        pts = [(cx - a, yl), (xl, yl)] + legL + arc[1:-1] + legR + [(2 * cx - xl, yl), (cx + a, yl)]
        return close(pen_line(pts, SVc, SHc))
    put("Ω", Omega)

    # ---- symbol variants (U+03D1 03D6 03F1 03F0: the forms maths and physics set apart)
    def theta_sym():
        # ϑ: a u-like bowl open at the top left, its right side rising to the ascender, over the top and down the left of
        # the loop to 0.62 x-height, then straight out to the right through the right side (Inter, Pretendard)
        w = 1.02 * ow; xl, xr = SV / 2, w - SV / 2; T = ASC - SH / 2; yx = 0.62 * XH
        # the bowl's left arm ends at 0.5 x-height and the loop comes down right of it, so the two never close a second
        # counter as the pen grows
        ax_ = (xr - xl) / 2; bowl = ell_pts((xl + xr) / 2, 0.5 * XH, ax_, 0.5 * XH - SH / 2, 180, 360, 40)
        start = bowl
        rise = bez_pts((xr, 0.5 * XH), (xr, 0.5 * XH + 0.55 * (T - 0.5 * XH)), (xr - 0.10 * w, T), (xl + 0.66 * (xr - xl), T), 24)
        down = bez_pts(rise[-1], (xl + 0.34 * (xr - xl), T), (xl + 0.32 * (xr - xl), yx + 0.20 * (T - yx)), (xl + 0.48 * (xr - xl), yx), 24)
        tail = [(xr + 0.10 * w, yx)]
        return close(pen(start + rise[1:] + down[1:] + tail))
    put("ϑ", theta_sym)

    def pi_sym():
        # ϖ: ω under a bar in t's thickness that reaches past it as π's does
        om = shapes["ω"]; b = bounds(om); ov = PI_OV * T_OV; yc = XH - T_BAR / 2
        bar = pen_line([(b[0] - ov + SV / 2, yc), (b[2] + ov - SV / 2, yc)], SV, T_BAR)
        return close(union(inter(om, rect(-1e4, -1e4, 1e4, XH - T_BAR)), bar))
    put("ϖ", pi_sym)

    def rho_sym():
        # ϱ: o with its left side running down past the baseline and turning right on the descender (a round end)
        E = (ox0 + 0.62 * ow, DESC + SH / 2)
        tail = bez_pts((ox0 + SV / 2, ocy), (ox0 + SV / 2, 0.15 * XH), (ox0 + SV / 2 + 0.05 * ow, E[1] + 0.10 * (ocy - E[1])), (ox0 + 0.30 * ow, E[1]), 24) + [E]
        return close(union(o, pen(tail)))
    put("ϱ", rho_sym)

    def kappa_sym():
        # ϰ: two strokes crossing in the x-height, each ending in a hook — the top left curls in, the bottom right curls up
        x = P("x"); xb = bounds(x); w = 1.05 * (xb[2] - xb[0]); xl, xr = SV / 2, w - SV / 2
        a = bez_pts((xl, 0.70 * XH), (xl, XH - SH / 2), (xl + 0.16 * w, XH - SH / 2), (xl + 0.30 * w, 0.78 * XH), 16) + \
            bez_pts((xl + 0.30 * w, 0.78 * XH), (xl + 0.50 * w, 0.45 * XH), (xr - 0.18 * w, SH / 2), (xr, 0.26 * XH), 20)[1:]
        b = [(xr - 0.02 * w, XH - SV / 2), (xl + 0.04 * w, SV / 2)]
        return close(union(pen(a), pen_line(b, S, S)))
    put("ϰ", kappa_sym)

    # feet and fillets: limn's rules on every constructed letter (copies keep their parent's)
    ff, fc = ns["flatten_feet"], ns.get("fillet_corners")
    for ch, p in list(shapes.items()):
        try:
            pre = p
            p, added = ff(p)
            if fc and FILLET > 0:
                p, _ = fc(p, FR)
            p.simplify()
            shapes[ch] = p
            if added:
                ST["feet"][ch] = added; ST["prefeet"][ch] = pre
        except Exception as ex:
            _fail(ch, ex)

    ST["m"] = dict(SV=SV, SH=SH, SVc=SVc, SHc=SHc, FR=FR, T_BAR=T_BAR, E_BAR=E_BAR, E_T=E_T)
    # the late step runs right after accents.build (side bearings and accented Latin are final there)
    if not getattr(accents.build, "_greek", False):
        _orig = accents.build

        def build_then_greek(ns2):
            st = _orig(ns2)
            late(ns2)
            return st
        build_then_greek._greek = True
        accents.build = build_then_greek
        _orig_kern = accents.kern

        def twins_then_kern(ns2):
            twins(ns2)
            return _orig_kern(ns2)
        accents.kern = twins_then_kern


# ---------------------------------------------------------------- twins (before accents.kern)
def twins(ns):
    """A letter drawn as another (Υ = Y, ; = ;, µ = μ) kerns exactly as it: the pair steps between accents.build
    and accents.kern (the punctuation clearance, the bars) measured the copy as a glyph of its own, and the
    Latin twin then got the kerning fixes of its own (Y. -55, TT ...), so the copy's pairs are replaced by the
    twin's, on either side and with each other."""
    KERN = ns["KERN"]; G = ns["G"]
    tw = {g: b for g, b in list(COPY.items()) + list(ALIAS.items()) if g in G and b in G}
    for k in [k for k in KERN if len(k) == 2 and (k[0] in tw or k[1] in tw)]:
        del KERN[k]
    inv = {}
    for g, b in tw.items():
        inv.setdefault(b, []).append(g)
    for k, v in list(KERN.items()):
        if len(k) != 2 or not (k[0] in inv or k[1] in inv): continue
        for A in [k[0]] + inv.get(k[0], []):
            for B in [k[1]] + inv.get(k[1], []):
                if A + B != k: KERN[A + B] = v
    PK = ns.get("PINKERN", {})                                    # and the pin clearance inside those pairs, so
    for k, v in list(PK.items()):                                 # accents.kern takes it out again for ı í …
        if len(k) != 2 or not (k[0] in inv or k[1] in inv): continue
        for A in [k[0]] + inv.get(k[0], []):
            for B in [k[1]] + inv.get(k[1], []):
                if A + B != k: PK[A + B] = v
    ST["twins"] = len(tw)
    # Γ before a lowercase letter: its arm hangs over the x-height as T's does, but Γ kerns as F, whose pairs were made for
    # F's middle bar (Γα Γε read open, most at 100-400): GAMMA_LC at 700 on top of that, by the spacing unit, for every
    # lowercase letter that stays under the arm (the ascenders β δ ζ θ λ ξ do not; a tonos is cleared by accents.kern)
    if "Γ" in G:
        cls = accents.ST["cls"]; u = ns["SPC_UNIT"]
        for x in LOWER + "".join(TONOS_LC) + "".join(k for k in DIALYTIKA if k.islower()) + "".join(DIAL_TONOS):
            if x not in G or x in "βδζθλξ": continue
            v = KERN.get("Γ" + x)
            if v is None:
                l = (cls.get("Γ") or (None, None))[0] or "Γ"; r = (cls.get(x) or (None, None))[1] or x
                v = KERN.get(l + r, 0)
            KERN["Γ" + x] = v + round(GAMMA_LC * u)


# ---------------------------------------------------------------- late (after accents.build)
def late(ns):
    G, S, XH, CAP, DOTSPEC, MODS = ns["G"], ns["S"], ns["XH"], ns["CAP"], ns["DOTSPEC"], ns["MODS"]
    FEET, PREFEET = ns["FEET"], ns["PREFEET"]
    bounds, slice_at, rect, circle = ns["bounds"], ns["slice_at"], ns["rect"], ns["circle"]
    union, diff, inter, xform = ns["union"], ns["diff"], ns["inter"], ns["xform"]
    PIN_R, GAP, I_GAP, Q_DOT_R, Q_GAP = ns["PIN_R"], ns["GAP"], ns.get("I_GAP", ns["GAP"]), ns["Q_DOT_R"], ns["Q_GAP"]
    near, SPC, SPC_K = ns["_near"], ns["SPC"], ns["SPC_K"]
    AST = accents.ST
    new = []

    def add(ch, p, adv, pins=(), spec=None, base=None, mark=None, clear=None):
        G[ch] = {"p": p, "adv": adv, "pins": [(round(x, 1), round(y, 1)) for x, y in pins]}
        if spec:
            DOTSPEC[ch] = {"only": False, "adv0": adv, "pins": spec}
        if base is not None and base in FEET:
            FEET[ch] = list(FEET[base]); pf = PREFEET.get(base, p)
            PREFEET[ch] = union(pf, mark) if mark is not None and list(mark.contours) else pf
        if mark is not None:
            m = pathops.Path(); m.addPath(mark)
            for x, y in pins: m.addPath(circle(x, y, PIN_R))
            if list(m.contours):
                AST["marks"][ch] = m
                AST["clear"][ch] = clear if clear is not None else (ns.get("PIN_CLEAR", 65) if pins and not list(mark.contours) else accents.CLEAR_K * GAP)
        new.append(ch)

    # 1 · the same form: limn's own glyph
    for g, lat in COPY.items():
        if lat in G:
            add(g, pathops.Path(G[lat]["p"]), G[lat]["adv"], G[lat]["pins"], base=lat)

    # 2 · constructed letters, set by their side classes (the Latin's method, tools/spacing.json)
    def unit(grp):
        a = SPC[grp]["anchor"]; top = XH if grp == "lc" else CAP
        return (near(G[a]["p"], "L", 0, top, G[a]["adv"]) + near(G[a]["p"], "R", 0, top, G[a]["adv"])) / 2
    UNIT = {"lc": unit("lc"), "uc": unit("uc")}

    def ratio(grp, cls):
        if cls == "ι R":
            r = IOTA_R
        else:
            classes = SPC[grp]["classes"]
            if cls in classes:
                r = classes[cls][0]
            else:                                                  # a Latin side name, e.g. "t L"
                side = cls.replace(" ", "")
                r = next(v[0] for v in classes.values() if side in v[1].split())
                cls = next(k for k, v in classes.items() if side in v[1].split())
            if isinstance(r, list):
                r = r[1] + (r[0] - r[1]) * max(0.0, min(1.0, (S - 60) / 60))
        return r if cls == "round" else r * SPC_K

    sides = {}
    for ch, p in ST["shapes"].items():
        grp = "uc" if ch.isupper() else "lc"; top = XH if grp == "lc" else CAP
        b = bounds(p); p = xform(p, e=-b[0]); adv = b[2] - b[0]
        cl, cr = SIDES[ch]
        L = ratio(grp, cl) * UNIT[grp]; R = ratio(grp, cr) * UNIT[grp]
        curL = near(p, "L", 0, top, adv); curR = near(p, "R", 0, top, adv)
        dl = L - curL; dr = R - curR
        p = xform(p, e=dl); adv = round(adv + dl + dr)
        pre = ST["prefeet"].get(ch)
        add(ch, p, adv)
        if ch in ST["feet"]:
            FEET[ch] = [round(x - b[0] + dl) for x in ST["feet"][ch]]
            PREFEET[ch] = xform(pre, e=-b[0] + dl)
        sides[ch] = (round(dl + 0), round(L), round(R))
    # µ is μ: one drawing (U+00B5 was Quicksand's, short of the x-height and the descender)
    if "μ" in G:
        G["µ"] = {"p": pathops.Path(G["μ"]["p"]), "adv": G["μ"]["adv"], "pins": []}
        if "μ" in FEET: FEET["µ"] = list(FEET["μ"]); PREFEET["µ"] = PREFEET["μ"]

    # 3 · tonos and dialytika (accents.py's stroke, pins and mark lines)
    MW, K = AST["MW"], AST["K"]
    LEN = accents.SHAPE["lc"]["acute"][0] * K
    ca, sa = math.cos(math.radians(TONOS_ANGLE)), math.sin(math.radians(TONOS_ANGLE))
    GAP_UC = accents.CAP_GAP_K * GAP
    PAIR = PIN_R + GAP / 2
    CLEAR = accents.CLEAR_K * GAP

    def tonos_at(x, y_low):
        """The tonos stroke whose lower end's ink bottom stands on y_low, lower end at x."""
        y = y_low + MW / 2
        return accents._stroke([[(x, y), (x + LEN * ca, y + LEN * sa)]], MW)

    def band_x(p, y0, y1, n=7):
        xs = []
        for k in range(n):
            for a, b in slice_at(p, y0 + (y1 - y0) * (k + 0.5) / n):
                xs += [a, b]
        return (min(xs), max(xs)) if xs else None

    def anchor(base, p):
        if base == "α":                                            # the bowl, like a
            cs = list(p.contours); outer = max(cs, key=lambda c: abs(c.area))
            holes = [c.bounds for c in cs if c.clockwise != outer.clockwise]
            if holes:
                h = max(holes, key=lambda b: (b[2] - b[0]) * (b[3] - b[1])); return (h[0] + h[2]) / 2
        top = bounds(p)[3]
        x0, x1 = band_x(p, top - 0.25 * XH, top - 1)
        return (x0 + x1) / 2

    def pin_spec(kind, x, cy):
        y = XH + Q_GAP + 2 * Q_DOT_R if kind == "i" else cy
        return [kind, round(x, 1), round(y, 1), round(Q_DOT_R, 1)]

    import hangul as _hg
    def dist(a, b):
        return _hg.to_geom(a).distance(_hg.to_geom(b))

    ml_lc, pc_lc = XH + GAP, XH + GAP + PIN_R
    for ch, base in TONOS_LC.items():
        if base not in G: continue
        try:
            bp = G[base]["p"]; ax = anchor(base, bp)
            m = tonos_at(ax, ml_lc)
            add(ch, union(bp, m), G[base]["adv"], base=base, mark=m)
        except Exception as ex:
            _fail(ch, ex)
    for ch, base in DIALYTIKA.items():
        if base not in G: continue
        try:
            bp = G[base]["p"]; ax = anchor(base, bp)
            if ch.isupper():
                pc = CAP + GAP_UC + PIN_R; kind = "mid"
            else:
                pc, kind = pc_lc, "i"
            pins = [(ax - PAIR, pc), (ax + PAIR, pc)]
            add(ch, pathops.Path(bp), G[base]["adv"], pins, [pin_spec(kind, x, y) for x, y in pins], base=base, mark=pathops.Path())
        except Exception as ex:
            _fail(ch, ex)
    for ch, base in DIAL_TONOS.items():
        if base not in G: continue
        try:
            bp = G[base]["p"]; ax = anchor(base, bp)
            m = tonos_at(ax - LEN * ca / 2, ml_lc)                 # the stroke's middle over the centre
            cy_eng = XH + I_GAP + PIN_R                            # where the renderers draw an "i" pin
            pins = []
            for sgn in (-1, 1):
                x = ax + sgn * PAIR
                while dist(m, circle(x, cy_eng, PIN_R)) < GAP:
                    x += sgn * 2
                pins.append((x, pc_lc))
            add(ch, union(bp, m), G[base]["adv"], pins, [pin_spec("i", x, y) for x, y in pins], base=base, mark=m)
        except Exception as ex:
            _fail(ch, ex)
    for ch, base in TONOS_UC.items():
        if base not in G: continue
        try:
            bp = G[base]["p"]; bb = bounds(bp)
            m = tonos_at(0, 0); mb = bounds(m)
            top = CAP + GAP_UC
            m = xform(m, e=bb[0] - mb[0], f=top - mb[3])
            dx = 0
            while dist(m, xform(bp, e=dx)) < CLEAR:
                dx += 2
            # the tonos hangs into the letter's left side bearing (its ink starts on the origin): it stands above the
            # neighbour's letter band, and accents.kern opens the pairs where it comes close
            ov = min(dx, bb[0])
            q = xform(union(xform(bp, e=dx), m), e=-ov)
            add(ch, q, round(G[base]["adv"] + dx - ov), base=None, mark=xform(m, e=-ov))
            if base in FEET:
                FEET[ch] = [x + dx - ov for x in FEET[base]]; PREFEET[ch] = xform(union(xform(PREFEET.get(base, bp), e=dx), m), e=-ov)
        except Exception as ex:
            _fail(ch, ex)

    # spacing marks: ΄ (tonos) ΅ (dialytika tonos), the width of limn's ´
    try:
        ac = G.get("´")
        if ac:
            ab = bounds(ac["p"]); sb = (ac["adv"] - (ab[2] - ab[0])) / 2
            m = tonos_at(0, ml_lc); mb = bounds(m); m = xform(m, e=sb - mb[0])
            add("΄", m, round(2 * sb + mb[2] - mb[0]))
            md = tonos_at(0, ml_lc); cxm = (bounds(md)[0] + bounds(md)[2]) / 2
            cy_eng = XH + I_GAP + PIN_R; pins = []
            for sgn in (-1, 1):
                x = cxm + sgn * PAIR
                while dist(md, circle(x, cy_eng, PIN_R)) < GAP:
                    x += sgn * 2
                pins.append((x, pc_lc))
            whole = pathops.Path(md)
            for x, y in pins: whole.addPath(circle(x, y, PIN_R))
            wb = bounds(whole); d0 = sb - wb[0]
            md = xform(md, e=d0); pins = [(x + d0, y) for x, y in pins]
            add("΅", md, round(2 * sb + wb[2] - wb[0]), pins, [pin_spec("i", x, y) for x, y in pins])
    except Exception as ex:
        _fail("΄΅", ex)

    # 4 · punctuation aliases: ; = ; and · = · (their pins and kerning too)
    for a, b in ALIAS.items():
        if b in G and a not in new and (a != "µ"):
            G[a] = {"p": pathops.Path(G[b]["p"]), "adv": G[b]["adv"], "pins": list(G[b]["pins"])}
            if b in DOTSPEC:
                DOTSPEC[a] = {k: (list(map(list, v)) if k == "pins" else v) for k, v in DOTSPEC[b].items()}
            new.append(a)

    # 5 · kerning classes, for accents.kern (it maps each class's pairs, drops i's pin clearance where the
    #     letter has no pin, and opens pairs where a mark comes close) and for the engine (kcls)
    cls = AST["cls"]
    for g, lat in COPY.items():
        if g in G: cls[g] = (lat, lat)
    for g, c in KCLS.items():
        if g in G: cls[g] = c
    for d in (TONOS_LC, TONOS_UC, DIALYTIKA, DIAL_TONOS):
        for ch, base in d.items():
            if ch in G: cls[ch] = cls.get(base, (base, base))
    for a, b in ALIAS.items():
        if a in G: cls[a] = (b, b) if a != "µ" else KCLS["μ"]
    if "µ" in G: new.append("µ")
    for ch in ("ι", "ί", "ϊ", "ΐ"):
        if ch in G: AST["nopin"].add(ch)
    # bars in line (tools/spacing.json "bars", applied by build_font after the kerning): π σ τ end in a bar at
    # the x-height on the right, π τ on the left; Γ Ξ Σ at the cap height (and Ξ Σ on the baseline), like F Z.
    # The rule's lists are extended here, in memory; the file keeps the Latin.
    # π σ τ ϖ's bar ends also meet ν's arms at the x-height, so ν joins the left list too (Greek|Latin pairs are not
    # kerned: browsers split the script runs)
    bars = SPC.get("bars")
    if bars:
        for grp, side, chars in (("lc", "right", "π σ τ ϖ"), ("lc", "left", "π τ ϖ ν"), ("uc", "right", "Γ Ξ Σ"), ("uc", "left", "Ξ Σ")):
            have = bars[grp][side].split()
            bars[grp][side] = " ".join(have + [c for c in chars.split() if c in G and c not in have])
    for ch in new:
        if ch not in AST["new"]: AST["new"].append(ch)
    ST["new"] = new; ST["sides"] = sides

    n_lc = len([c for c in new if c in LOWER]); n_uc = len([c for c in new if c in UPPER])
    MODS.append(["α–ω Α–Ω", f"그리스 문자 {len([c for c in new if c != 'µ'])}자",
                 "Quicksand에 없는 문자라 limn의 글자·펜·규칙으로(tools/greek.py): 모양이 같은 Α Β Ε Ζ Η Ι Κ Μ Ν Ο Ρ Τ Υ Χ ο ν ϲ Ϲ ϳ Ϳ는 limn 글자 그대로, "
                 "ι τ κ η μ υ ω α ρ σ π θ γ Γ Π Λ Δ Σ Θ ϖ는 limn 글자의 부분으로, β δ ε ζ ξ ς λ φ ϕ χ ψ Ξ Φ Ψ Ω와 기호 꼴 ϑ ϱ ϰ는 limn의 펜(o의 줄기 × 가는 획)으로 — φ는 참고 서체의 고리 모양, ϕ는 닫힌 모양. ϵ는 c에 e의 가로획. "
                 "발·이음·옆 여백(Tracy 부류)·커닝(라틴 짝 부류, 나란한 막대 0.2 s)은 라틴과 같은 규칙, 모양이 같은 글자는 커닝도 같음. µ는 μ와 한 글자"])
    MODS.append(["ά έ ή ί ό ύ ώ · Ά … · ϊ ϋ ΐ ΰ", "토노스·디알리티카",
                 f"토노스는 limn의 양음 부호 획을 {TONOS_ANGLE}°로 세운 것(참고 서체의 토노스는 양음 부호 폭의 0.7~0.8). 소문자는 é처럼 부호 선에, 대문자는 글자 왼쪽 "
                 f"대문자 높이 + {GAP_UC:.0f}에 두고 글자와 {CLEAR:.0f}(1.25 GAP) 띄움. 디알리티카는 핀 둘(ï처럼)"])
    if ST["fail"]:
        print("greek: FAILED", ST["fail"], file=sys.stderr)
    print(f"greek: {len(new)} glyphs ({n_lc} lower, {n_uc} upper)", file=sys.stderr)
