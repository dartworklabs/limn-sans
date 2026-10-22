"""limn maths operators, arrows, general punctuation and keyboard symbols (sym-math 2026-09-29).

Called once by build_font.py, right after accents.build and before the kerning (the letters, figures and every
glyph punct.py builds are final there, and the clearance passes then measure these glyphs too):

    import sym_math; MODS.extend(sym_math.build(globals()))

Every glyph is built on the classes of tools/punct.py, so it holds at every weight 100-900 and in the text cuts:

  axis     AX, the parent hyphen's centre (308 at 700). Every operator, every horizontal arrow's shaft and every
           mark "on the axis" (⋯ ∶ ⁃ ‣ ⁕) is centred on it.
  PW       the + square, 0.9 XH. An operator's ink is PW tall; its advance is op_cell (punct.py): the ink centred in
           max(ink, PW) + 2 OP_SB, OP_SB the parent = sign's side bearing — one width for + − = × ÷ ≠ ≤ ≈ ≡ ∈ ⊂ …
  T        the bar pen (the stem S, round): operators, arrows, keyboard symbols. Letter-like maths (∑ ∏ ∫ ∂ ∆ ∇)
           take the family's pen (the stem S, o's contrast) and the side bearings of the letter they resemble.
  whites   gap_eq, the = sign's white (max(0.75 S, 0.16 PW)), between any two parallel strokes: ≡ ≈ ≃ ≅ ⇒ ‖ ∥.
  slash    a negation slash (≠ ≢ ∉ ∄) runs at the slope of / (20° from vertical); ≠'s ink is PW tall like + 's, the
           others reach 0.18 PW past what they cross (≠'s overhang at 700). The slash of a ring (∅ ⊘) runs corner
           to corner, as Ø's does (accents.py).
  rings    a ring with something inside (⊕ ⊖ ⊗ ⊘ ⊙ ∅ ∮) takes the DENSE pen, like ¤: 1.1 PW across, on the axis.
           ◌ is the one ring off the axis: © 's ring (O's height, the LIGHT pen) with the stroke cut into 12 dots,
           so a shaper's placeholder stands in the band a capital stands in and a mark clears its ink.
  arrows   shaft on the axis (vertical arrows stand on the baseline and reach the cap height; ↕ ⇕ ⇞ ⇟ span
           the bracket band like |), head = two arms at 45° to the shaft, h = PW/2 − T/2 to each side, so a head is
           exactly PW across — the + 's square. → is 1.5 PW of ink, ↔ 2 PW, the long arrows 0.8 PW longer.
           ⇐ ⇒ ⇔ ⇑ ⇓ ⇕: two shafts gap_eq apart, the same head.
  pins     every dot is the pin (PIN_R), placed by the pin rule (DOTSPEC kinds base / top / mid).
  heavy    ✔ ✘: the pen T + 0.14 PW at every weight (a fixed step heavier than ✓ ✗).
"""
import math

import pathops

import punct as P
from punct import ST, _circle, _diff, _empty, _inter, _xf, bez_pts, ell_pts, line, op_cell, pen_line, sym_pens, sym_white

GROUPS = {
    "maths": "≠≤≥≈≃≅≡≢∼∝∞√∑∏∫∬∮∂∆∇∅∈∉∋∩∪⊂⊃⊆⊇∀∃∄∧∨∠⊥∓∗∘∙⋅∕∖∣∥∴∵∶≐≒≪≫⊕⊖⊗⊘⊙⋯⊤⊢∌≔≝⋮⋱⟨⟩⌈⌉⌊⌋ℕℤℚℝℂℏ",
    "arrows": "→←↑↓↔↕↖↗↘↙↩↪↰↱↳↴↵↺↻⇐⇒⇔⇑⇓⇕⇞⇟⇤⇥⇧⇪⟵⟶⟷↦",
    "punct": "‖‗‛‟‣․‥‧‱‴‵‶‷‸‼‽‾‿⁀⁁⁂⁃⁅⁆⁇⁈⁉⁎⁑⁕⁐⁓⁗◦◌",
    "tech": "⌃⌅⌘⌥⌦⌫⌧⏎⏏⎋⎇✓✔✗✘⚠",
}
SLASH = math.tan(math.radians(P.PRIME_SLANT))       # / \ ′: 20° from vertical
INFO = {}                                            # numbers for the report


def _union(*ps):
    """punct._union, checked pair by pair: skia's union can drop a piece or fill a counter (⊕ at 900 lost a third of its
    ring, then a counter). A union of a and b has the area |a| + |b| - |a ∩ b| and the box of both; a result that
    misses either is redone a hair apart (the shift, 0.01-0.03 unit, is left in: far under a rounding step)."""
    ps = [q for q in ps if not _empty(q)]
    if not ps:
        return pathops.Path()
    out = ps[0]
    for q in ps[1:]:
        out = _union2(out, q)
    return out


def _union2(a, b):
    want = [min(a.bounds[0], b.bounds[0]), min(a.bounds[1], b.bounds[1]), max(a.bounds[2], b.bounds[2]), max(a.bounds[3], b.bounds[3])]
    for e in (0.0, 0.011, -0.017, 0.029):
        bb = _xf(b, e=e, f=0.7 * e) if e else b
        try:
            u = pathops.op(a, bb, pathops.PathOp.UNION)
            i = pathops.op(a, bb, pathops.PathOp.INTERSECTION)
        except pathops.PathOpsError:
            continue
        exp = abs(a.area) + abs(bb.area) - abs(i.area)
        if abs(abs(u.area) - exp) <= 0.002 * exp + 1 and all(abs(x - y) < 0.5 for x, y in zip(u.bounds, want)):
            return u
    raise RuntimeError("sym_math: union failed")


def round_joins(p, r):
    """punct.round_joins, checked: the closing is two skia strokes and boolean ops, which can drop a piece as the
    union does. A closing only ever adds ink inside the outline, so a result that is smaller or narrower is retried
    a hair off, and otherwise the joins stay as the pen drew them."""
    b0, a0 = p.bounds, abs(p.area)
    for rr in (r, 0.93 * r, 1.07 * r):
        for e in (0.0, 0.013, -0.021, 0.034):              # and a hair off, taken back (∆ ∇ at 800 failed every radius)
            pp = _xf(p, e=e, f=0.7 * e) if e else p
            q = P.round_joins(pp, rr)
            if q is pp and rr >= 0.5: continue             # punct.round_joins hands its input back when skia fails
            if e: q = _xf(q, e=-e, f=-0.7 * e)
            b1 = q.bounds if not _empty(q) else (0, 0, 0, 0)
            if abs(q.area) >= a0 - 1 and all(abs(u - v) < 1.5 for u, v in zip(b0, b1)):
                return q
    return p


def _rot(p, deg, cx=0.0, cy=0.0):
    c, s = math.cos(math.radians(deg)), math.sin(math.radians(deg))
    return _xf(p, c, s, -s, c, cx - c * cx + s * cy, cy - s * cx - c * cy)


def _mirror(g):
    """g mirrored left to right inside its own advance."""
    a = g["adv"]
    return {"p": _xf(g["p"], -1, 0, 0, 1, a, 0), "adv": a, "pins": [(a - x, y) for x, y in g["pins"]],
            **({"kinds": list(g["kinds"])} if "kinds" in g else {})}


def _flip(p, cy):
    return _xf(p, 1, 0, 0, -1, 0, 2 * cy)


def _box(p, pins=(), r=0.0):
    b = list(p.bounds) if not _empty(p) else [1e9, 1e9, -1e9, -1e9]
    for x, y in pins:
        b = [min(b[0], x - r), min(b[1], y - r), max(b[2], x + r), max(b[3], y + r)]
    return b


def _fill_poly(pts, w):
    """A filled polygon whose corners are round: the polygon itself and its outline stroked with a round pen w
    (the corner radius is w / 2; the ink reaches w / 2 past the points)."""
    q = pathops.Path(); q.moveTo(*pts[0])
    for pt in pts[1:]:
        q.lineTo(*pt)
    q.close()
    return _union(q, line(list(pts) + [pts[0], pts[1]], w))


def _seg_dist(p, a, b):
    vx, vy = b[0] - a[0], b[1] - a[1]; L2 = vx * vx + vy * vy or 1e-9
    t = max(0.0, min(1.0, ((p[0] - a[0]) * vx + (p[1] - a[1]) * vy) / L2))
    return math.hypot(p[0] - a[0] - t * vx, p[1] - a[1] - t * vy)


def _poly_dist(pts, a, b):
    return min(_seg_dist(q, a, b) for q in pts)


def build(ns):
    G, DOTSPEC = ns["G"], ns["DOTSPEC"]
    M = ST["M"]
    S, XH, XO, CAP, ASC, DESC, OSH, AX, T, GAP, R = (M[k] for k in ("S", "XH", "XO", "CAP", "ASC", "DESC", "OSH", "AX", "T", "GAP", "PIN_R"))
    BB, BT, FR, QR, BASE_CY, YB = M["BB"], M["BT"], M["FR"], M["QR"], M["BASE_CY"], M["YB"]
    SV, SH = M["PEN"]
    pens = sym_pens(M); DV, DH = pens["DENSE"]; LV, LH = pens["SUP"]
    PW = 0.9 * XH; h = PW / 2 - T / 2
    gap_eq = max(0.75 * S, 0.16 * PW); dq = (T + gap_eq) / 2; p3 = T + gap_eq
    OV = (PW - (2 * T + gap_eq)) / 2                 # how far ≠'s slash reaches past the = bars (ink)
    OVN = 0.18 * PW                                  # the other negations (≢ ∉ ∄): past what they cross, ≠'s at 700
    HV = T + 0.14 * PW                               # the heavy pen (✔ ✘)
    TOPC = XO - R                                    # the colon's upper pin centre
    new = {}

    def L(pts, w=T):
        return line(pts, w)

    def rj(p, k=0.5):
        return round_joins(p, k * FR)

    def op(p, pins=(), kinds=None, wmin=None, sb=None):
        """the operator cell (punct.op_cell); pins (x, y) with their DOTSPEC kinds (default mid)"""
        g = op_cell(M, p, pins, wmin, sb)
        g["kinds"] = kinds or ["mid"] * len(pins)
        return g

    def sb_of(ch):
        g = G[ch]; b = g["p"].bounds
        return (b[0] + g["adv"] - b[2]) / 2

    def cell_sb(p, sb, pins=(), kinds=None, r=None):
        b = _box(p, pins, R if r is None else r)
        adv = round(b[2] - b[0] + 2 * sb); dx = sb - b[0]
        return {"p": _xf(p, e=dx), "adv": adv, "pins": [(x + dx, y) for x, y in pins], "kinds": kinds or ["mid"] * len(pins)}

    def copy(ch):
        g = G[ch]
        spec = DOTSPEC.get(ch)
        return {"p": pathops.Path(g["p"]), "adv": g["adv"], "pins": list(g["pins"]),
                "kinds": [e[0] for e in spec["pins"]] if spec and len(spec["pins"]) == len(g["pins"]) else ["mid"] * len(g["pins"])}

    def slash(yc, half, w=T, x=0.0):
        """a negation slash through (x, yc) at the slope of /, its centreline `half` above and below"""
        return L([(x - half * SLASH, yc - half), (x + half * SLASH, yc + half)], w)

    # =============================================================== maths: the axis class (T pen, PW, op cell)
    eq = _union(L([(-h, AX + dq), (h, AX + dq)]), L([(-h, AX - dq), (h, AX - dq)]))
    three = _union(*[L([(-h, AX + k * p3), (h, AX + k * p3)]) for k in (-1, 0, 1)])
    tilde = G["~"]["p"]; tb = tilde.bounds; tilde = _xf(tilde, e=-(tb[0] + tb[2]) / 2, f=AX - (tb[1] + tb[3]) / 2)
    bar = lambda y, a=-h, b=h: L([(a, y), (b, y)])
    new["≠"] = op(_union(eq, slash(AX, PW / 2 - T / 2)))
    new["≡"] = op(three)
    new["≢"] = op(_union(three, slash(AX, p3 + OVN)))
    new["≈"] = op(_union(_xf(tilde, f=dq), _xf(tilde, f=-dq)))
    new["≃"] = op(_union(_xf(tilde, f=dq), bar(AX - dq)))
    new["≅"] = op(_union(_xf(tilde, f=p3), bar(AX), bar(AX - p3)))
    new["∼"] = op(pathops.Path(tilde))
    # ≤ ≥ : < 's chevron over a bar, together PW tall like < ; the chevron gives up one bar and the = white
    cw = 0.84 * PW - T
    hc = max((PW - 2 * T - gap_eq) / 2, 0.62 * h)       # at 700-900 the chevron keeps 0.62 of < 's height (the pair grows past PW)
    le = _union(L([(cw / 2, AX + dq + hc), (-cw / 2, AX + dq), (cw / 2, AX + dq - hc)]), bar(AX - h, -cw / 2, cw / 2))
    new["≤"] = op(rj(le)); new["≥"] = _mirror(new["≤"])
    # ≐ ≒ : = with pins GAP off the bars (÷'s rule)
    pin_off = dq + T / 2 + GAP + R
    new["≐"] = op(eq, [(0, AX + pin_off)])
    xe = h + T / 2 - R
    new["≒"] = op(eq, [(-xe, AX + pin_off), (xe, AX - pin_off)])
    # ∓ : ± turned
    pm = G["±"]; b = pm["p"].bounds
    new["∓"] = {"p": _xf(pm["p"], -1, 0, 0, -1, pm["adv"], b[1] + b[3]), "adv": pm["adv"], "pins": []}
    # ∗ : limn's * on the axis
    st = G["*"]["p"]; b = st.bounds
    new["∗"] = op(_xf(st, f=AX - (b[1] + b[3]) / 2))
    # ∘ ◦ : a ring as large as • (1.7 pins across), the LIGHT pen
    Dr = max(2 * 1.7 * R, 0.3 * XH)                        # (never under 0.3 XH: the light pin made it a speck at 100-400)
    ring_s = pen_line(ell_pts(0, AX, (Dr - LV) / 2, (Dr - LH) / 2, 0, 360, 72), LV, LH)
    new["∘"] = op(ring_s)
    new["◦"] = cell_sb(pathops.Path(ring_s), sb_of("•"))
    # ∙ ⋅ : the middle dot (a pin on the axis)
    new["∙"] = copy("·"); new["⋅"] = copy("·")
    # ∕ ∖ ∣ : the slash, backslash and bar of the bracket band
    new["∕"] = copy("/"); new["∖"] = copy("\\"); new["∣"] = copy("|")
    # ∥ (and ‖ below): two | the = white apart
    vb = L([(0, BB + S / 2), (0, BT - S / 2)], S)
    par = _union(vb, _xf(vb, e=S + gap_eq))
    new["∥"] = cell_sb(par, sb_of("|"))
    # ∧ ∨ : a chevron PW tall, 0.84 PW wide (< turned upright)
    wedge = L([(-cw / 2, AX - h), (0, AX + h), (cw / 2, AX - h)])
    new["∧"] = op(rj(wedge)); new["∨"] = op(rj(_flip(wedge, AX)))
    # ⊂ ⊃ : a half circle and two straight arms in the PW square; ∩ ∪ the same turned upright, 0.84 PW wide
    rr = h

    def cup(y0, y1, rad, w=cw):
        """⊂'s centreline: arms from the right (x = w/2) to the half circle of radius rad centred at y0..y1's middle"""
        yc = (y0 + y1) / 2; xc = -w / 2 + rad
        return [(w / 2, yc + rad)] + ell_pts(xc, yc, rad, rad, 90, 270, 36) + [(w / 2, yc - rad)]
    ws = PW - T
    sub = L(cup(AX - h, AX + h, rr, ws))
    new["⊂"] = op(sub); new["⊃"] = _mirror(new["⊂"])
    cap_u = L(cup(AX - cw / 2, AX + cw / 2, cw / 2, ws))
    new["∪"] = op(_rot(cap_u, 90, 0, AX)); new["∩"] = op(_rot(cap_u, -90, 0, AX))
    # ⊆ ⊇ : ⊂ over a bar, together PW tall (as ≤)
    sube = _union(L(cup(AX + dq - hc, AX + dq + hc, hc, ws)), bar(AX - h, -ws / 2, ws / 2))
    new["⊆"] = op(rj(sube)); new["⊇"] = _mirror(new["⊆"])
    # ∈ ∉ ∋ : ⊂ with its middle bar. Three strokes stacked in PW leave (PW - 3 T) / 2 between them: 66 at 700, 39 at 800,
    # 8 at 900 (∉'s slash shut them into specks, then into one blot). The two pockets keep WHITE_K S (0.4 S, the white a
    # mark leaves in a sign, tools/sym_numeric.py): the pen lightens where they would be narrower, as three stacked
    # strokes do (℮ & #), down to DENSE, and the sign grows past PW where DENSE is not light enough (as ≤ ⊆ do)
    te, he = T, h
    if he - te < 0.4 * S:
        te = max(DV, min(T, (PW - 2 * 0.4 * S) / 3))
        he = max((PW - te) / 2, te + 0.4 * S)
    if (te, he) == (T, h):
        el = rj(_union(sub, L([(-ws / 2, AX), (ws / 2, AX)])))
    else:
        wse = PW - te
        el = rj(_union(L(cup(AX - he, AX + he, he, wse), te), L([(-wse / 2, AX), (wse / 2, AX)], te)))
    INFO["∈"] = (round(te, 1), round(he - te, 1))
    new["∈"] = op(el); new["∋"] = _mirror(new["∈"])
    new["∉"] = op(_union(el, slash(AX, he + OVN, te, 0.5 * he)))   # through the arms, where the pockets it closes are widest
    # ⊥ ⊤ ⊢ : a bar and a stem in the PW square, joined round
    new["⊥"] = op(round_joins(_union(bar(AX - h), L([(0, AX - h), (0, AX + h)])), FR))
    new["⊤"] = op(round_joins(_union(bar(AX + h), L([(0, AX + h), (0, AX - h)])), FR))
    new["⊢"] = op(round_joins(_union(L([(-h, AX - h), (-h, AX + h)]), bar(AX)), FR))
    # ∠ : a bar on the square's floor and a leg rising 60° from its left end
    ang = math.radians(60)
    new["∠"] = op(rj(L([(-h + 2 * h / math.tan(ang), AX + h), (-h, AX - h), (h, AX - h)])))
    # ≪ ≫ : two < chevrons, the « » white between their legs
    th0 = math.atan2(h, cw)
    pitch_ll = (0.12 * CAP + 0.05 * S + T) / math.sin(th0)
    chev = lambda x0: L([(x0 + cw / 2, AX + h), (x0 - cw / 2, AX), (x0 + cw / 2, AX - h)])
    new["≪"] = op(rj(_union(chev(0), chev(pitch_ll)))); new["≫"] = _mirror(new["≪"])
    # ∴ ∵ ∶ ⋯ : pins; ∴ ∵ on the colon's two lines, a triangle whose base is its height
    ht = TOPC - BASE_CY
    sb_ell = (G["…"]["pins"][0][0] - R + G["…"]["adv"] - G["…"]["pins"][-1][0] - R) / 2
    new["∴"] = cell_sb(pathops.Path(), sb_ell, [(-ht / 2, BASE_CY), (ht / 2, BASE_CY), (0, TOPC)], ["base", "base", "top"])
    new["∵"] = cell_sb(pathops.Path(), sb_ell, [(-ht / 2, TOPC), (ht / 2, TOPC), (0, BASE_CY)], ["top", "top", "base"])
    off = T / 2 + GAP + R                                # ÷'s dots without the bar
    new["∶"] = cell_sb(pathops.Path(), sb_ell, [(0, AX + off), (0, AX - off)])
    e3 = G["…"]
    new["⋯"] = {"p": pathops.Path(), "adv": e3["adv"], "pins": [(x, AX) for x, _ in e3["pins"]], "kinds": ["mid"] * 3}
    # ⊕ ⊖ ⊗ ⊘ ⊙ ∅ : a ring 1.1 PW across on the axis, the DENSE pen; what is inside runs to the ring
    Dc = 1.1 * PW; ra, rb = (Dc - DV) / 2, (Dc - DH) / 2
    ringc = pen_line(ell_pts(0, AX, ra, rb, 0, 360, 96), DV, DH)
    dpen = lambda pts: pen_line(pts, DV, DH)
    c45 = math.cos(math.radians(45))
    new["⊕"] = op(rj(_union(ringc, dpen([(-ra, AX), (ra, AX)]), dpen([(0, AX - rb), (0, AX + rb)]))))
    new["⊖"] = op(rj(_union(ringc, dpen([(-ra, AX), (ra, AX)]))))
    new["⊗"] = op(rj(_union(ringc, dpen([(-ra * c45, AX - rb * c45), (ra * c45, AX + rb * c45)]), dpen([(-ra * c45, AX + rb * c45), (ra * c45, AX - rb * c45)]))))
    new["⊘"] = op(rj(_union(ringc, dpen([(-ra * c45, AX - rb * c45), (ra * c45, AX + rb * c45)]))))
    new["⊙"] = op(ringc, [(0, AX)])
    ext = 0.08 * PW                                       # ∅: the slash reaches past the ring, corner to corner
    new["∅"] = op(rj(_union(ringc, dpen([(-(ra + ext) * c45, AX - (rb + ext) * c45), ((ra + ext) * c45, AX + (rb + ext) * c45)]))))
    # ◌ : the dotted circle a shaper puts under a combining mark that was typed without a base. It is © 's ring
    # (punct.py circled: O's own height and both overshoots, the LIGHT pen) with the stroke cut into DC_N dots —
    # Unicode's reference count — whose centres run on that ring's own centreline, so ◌ and © read as one
    # diameter and one weight. Each dot is the LIGHT pen set down once (LV by LH, o's contrast), the pen of
    # ° ∘ ◦ and the rings of © ®.
    #   not the pin  every other dot in the family is the pin, but the pin is a period: DC_N pins on a ring this
    #                size leave 7 units between neighbours at 400 and overlap from 500 up (41 deep at 700), and
    #                pinsOf draws every pin at the weight's one radius, so it cannot be scaled down for this
    #                glyph. A dot under the pin has to be drawn, and LIGHT is the family's size for a small mark.
    #   the band     on the axis (1.1 PW, as ⊙) the ring would top 12-17 units under the lowercase mark floor
    #                XH + GAP — a quarter of the white o leaves its own accent. On O's band the exporter anchors
    #                the mark over the ink instead (tools/mark_attachment.py: yMax above (XO + CAP) / 2), the
    #                rule it uses for a capital, so ◌́ sits like Á and the dots stay clear.
    DC_N = 12
    Dd = M["O_T"] - M["O_B"]                              # O's height with both overshoots: © 's ring across
    cyd = (M["O_T"] + M["O_B"]) / 2                       # and its centre, as © takes it
    kd = LH / LV                                          # the pen's contrast: a dot is LV across, LH tall
    ad, bd = (Dd - LV) / 2, (Dd - LH) / 2                 # the ring's centreline, where the dots sit
    dot = lambda x, y: _xf(_circle(x, y / kd, LV / 2), d=kd)
    ang = lambda i: math.radians(90 + 360 * i / DC_N)     # a dot at the top, four on the axes (DC_N is 12)
    new["◌"] = cell_sb(_union(*[dot(ad * math.cos(ang(i)), cyd + bd * math.sin(ang(i))) for i in range(DC_N)]),
                       sb_of("O"))                        # O's side bearings: the family's round capital
    INFO["◌"] = (DC_N, round(Dd), round(2 * ad * math.sin(math.pi / DC_N) - LV, 1))   # dots, across, white between

    # ∞ ∝ : two lobes on the axis (1.5 XH by 0.74 XH of ink), the family's pen at the bar's weight
    kc = SH / SV; TV, TH = T, T * kc
    Winf, Hinf = 1.5 * XH, 0.74 * XH
    ca = (Winf - TV) / 2                                  # centre to the far end of a lobe (centreline)
    a_l = 0.56 * ca; c_l = ca - a_l; b_l = (Hinf - TH) / 2
    th = math.radians(48); k1, k2 = 0.55 * c_l / math.cos(th), 0.45 * c_l
    Cc = (0.0, AX)

    def seg(p0, d0, p3_, d3):
        return bez_pts(p0, (p0[0] + d0[0], p0[1] + d0[1]), (p3_[0] - d3[0], p3_[1] - d3[1]), p3_, 20)
    up_r, dn_r = (k1 * math.cos(th), k1 * math.sin(th)), (k1 * math.cos(th), -k1 * math.sin(th))
    Tr, Br, Tl, Bl = (c_l, AX + b_l), (c_l, AX - b_l), (-c_l, AX + b_l), (-c_l, AX - b_l)
    s1 = seg(Cc, up_r, Tr, (k2, 0))
    arc_r = ell_pts(c_l, AX, a_l, b_l, 90, -90, 40)
    s2 = seg(Br, (-k2, 0), Cc, (-dn_r[0], -dn_r[1]))
    s3 = seg(Cc, (-up_r[0], up_r[1]), Tl, (-k2, 0))
    arc_l = ell_pts(-c_l, AX, a_l, b_l, 90, 270, 40)
    s4 = seg(Bl, (k2, 0), Cc, up_r)
    inf = pen_line(P._chain(s1, arc_r, s2, s3, arc_l, s4), TV, TH)
    new["∞"] = op(rj(inf))
    xe_p = c_l + 0.15 * a_l                               # ∝ : the left lobe, its arms end over the right lobe's tops
    Eu, El = (xe_p, AX + b_l), (xe_p, AX - b_l)
    prop = pen_line(P._chain(seg(El, (-k2, 0), Cc, (-dn_r[0], -dn_r[1])), s3, arc_l, s4, seg(Cc, up_r, Eu, (k2, 0))), TV, TH)
    new["∝"] = op(rj(prop))
    INFO["inf"] = (Winf, Hinf)

    # √ : a short tick into the V on the baseline, the long stroke to the cap height (T pen)
    Wr = 1.02 * XH - T
    new["√"] = op(rj(L([(0, 0.46 * CAP), (0.30 * Wr, T / 2), (Wr, CAP - T / 2)])))

    # =============================================================== maths: letter-like (the family's pen)
    fp = lambda pts: pen_line(pts, SV, SH)
    # ∑ : Z's width, cap height, bars and a diagonal pair meeting at 0.52 of the width
    Zb = G["Z"]["p"].bounds; Wz = Zb[2] - Zb[0]
    xl, xr = SV / 2, Wz - SV / 2
    sig = fp([(xr, CAP - SH / 2), (xl, CAP - SH / 2), (xl + 0.52 * (xr - xl), CAP / 2), (xl, SH / 2), (xr, SH / 2)])
    new["∑"] = cell_sb(round_joins(sig, FR), sb_of("Z"))
    # ∏ : H's width, a bar on the cap height over two stems with flat feet (the family's feet)
    Hb = G["H"]["p"].bounds; Wh = Hb[2] - Hb[0]
    pi = fp([(SV / 2, SH / 2), (SV / 2, CAP - SH / 2), (Wh - SV / 2, CAP - SH / 2), (Wh - SV / 2, SH / 2)])
    pi, _ = ns["flatten_feet"](round_joins(pi, FR))
    new["∏"] = cell_sb(pi, sb_of("H"))
    # ∆ ∇ : A's width and height, a triangle with round corners
    Ab = G["A"]["p"].bounds; Wa, top_a = Ab[2] - Ab[0], Ab[3]
    # the pen's own ring round the triangle's centreline: the polygon grown and shrunk by half the pen (a closed polyline
    # stroked through its start twice lost its round corners at 800, and with them ink)
    from weights import offset as _woff
    cl = pathops.Path(); cl.moveTo(SV / 2, SH / 2); cl.lineTo(Wa / 2, top_a - SH / 2); cl.lineTo(Wa - SV / 2, SH / 2); cl.close()
    tri = _diff(_woff(cl, SV / 2, SH / 2), _woff(cl, -SV / 2, -SH / 2))
    tri = round_joins(tri, FR)
    new["∆"] = cell_sb(tri, sb_of("A"))
    new["∇"] = cell_sb(_xf(tri, 1, 0, 0, -1, 0, top_a + Ab[1]), sb_of("A"))
    # ∀ : A turned; ∃ : E mirrored; ∄ : ∃ with the negation slash
    ga = G["A"]; b = ga["p"].bounds
    new["∀"] = {"p": _xf(ga["p"], -1, 0, 0, -1, ga["adv"], b[1] + b[3]), "adv": ga["adv"], "pins": []}
    new["∃"] = _mirror({"p": G["E"]["p"], "adv": G["E"]["adv"], "pins": []})
    eb = new["∃"]["p"].bounds
    new["∄"] = {"p": _union(new["∃"]["p"], slash(CAP / 2, CAP / 2 + OVN - S / 2, S, eb[0] + 0.4 * (eb[2] - eb[0]))), "adv": new["∃"]["adv"], "pins": []}
    # ∂ : a bowl of o's contrast (0.62 of the cap height, 0.88 of o's width) whose right side runs on up into a
    #     hook that turns left at the cap height (round end)
    ob = G["o"]["p"].bounds; Wo = ob[2] - ob[0]
    bw, bh = 0.88 * Wo, 0.64 * CAP + OSH
    bxa, bya = (bw - SV) / 2, (bh - SH) / 2
    bcx, bcy = bw / 2, -OSH + bh / 2
    bowl = ell_pts(bcx, bcy, bxa, bya, 0, 360, 72)
    P0 = (bcx + bxa, bcy); P3 = (bcx - 0.30 * bxa, CAP + OSH - SH / 2)
    hook = bez_pts(P0, (P0[0], bcy + 0.62 * (P3[1] - bcy)), (bcx + 0.55 * bxa, P3[1]), P3, 28)
    hook += [(P3[0] - 0.12 * bxa, P3[1] - 0.04 * bxa)]
    new["∂"] = cell_sb(round_joins(_union(pen_line(bowl, SV, SH), pen_line(hook, SV, SH)), FR), sb_of("o"))
    # ∫ ∬ ∮ : descender to ascender; a straight stem leaning like / at a third of its slope, hooks of o's pen
    y_hi, y_lo = ASC - SH / 2, DESC + SH / 2
    r_h = 0.17 * XH
    lean = SLASH / 3
    ytop, ybot = y_hi - r_h, y_lo + r_h
    xs_t, xs_b = lean * (ytop - AX), lean * (ybot - AX)
    hook_t = ell_pts(xs_t + r_h, ytop, r_h, r_h, 180, 20, 24)
    lower = [(xs_b - (x - xs_t), ybot - (y - ytop)) for x, y in hook_t]   # the upper hook turned about the stem's foot
    int_c = list(reversed(hook_t)) + lower
    integ = pen_line(int_c, SV, SH)
    # the integrals' hooks reach over their neighbours, so their side bearing is a fifth of the parent's = (∫f read
    # 84-95 units open at 700 on OP_SB)
    SB_INT = 0.2 * (M["OP_SB"] - 0.7 * M["O_SIDE"])
    new["∫"] = op(integ, wmin=0, sb=SB_INT)
    ib = integ.bounds
    hook_r = max(x for x, _ in hook_t) + SV / 2 - xs_t          # the upper hook's reach right of the stem
    pitch_i = hook_r + gap_eq + SV / 2
    new["∬"] = op(_union(integ, _xf(integ, e=pitch_i)), wmin=0, sb=SB_INT)
    Do = max(0.5 * XH, S + 2 * DV + gap_eq)                 # ∮ : the ring leaves half the = white each side of the stem
    ring_o = pen_line(ell_pts((xs_t + xs_b) / 2, (ytop + ybot) / 2, (Do - DV) / 2, (Do - DH) / 2, 0, 360, 72), DV, DH)
    new["∮"] = op(rj(_union(integ, ring_o)), wmin=0, sb=SB_INT)
    INFO["int"] = (ib[3] - ib[1], r_h)

    # =============================================================== arrows
    LA = 1.5 * PW                                          # → : ink length

    def head(tip, u, hh=h, w=T):
        ux, uy = u; nx, ny = -uy, ux
        return L([(tip[0] - ux * hh + nx * hh, tip[1] - uy * hh + ny * hh), tip,
                  (tip[0] - ux * hh - nx * hh, tip[1] - uy * hh - ny * hh)], w)

    def harrow(Lk, fwd=True, back=False, double=False):
        """a horizontal arrow of ink length Lk centred on (0, 0), pointing +x (heads at +x if fwd, at -x if back)"""
        x1, x0 = Lk / 2 - T / 2, -Lk / 2 + T / 2
        parts = []
        if fwd: parts.append(head((x1, 0), (1, 0)))
        if back: parts.append(head((x0, 0), (-1, 0)))
        if not double:
            parts.append(L([(x0, 0), (x1, 0)]))
        else:
            for yy in (dq, -dq):
                a = x0 + (dq if back else 0); b_ = x1 - (dq if fwd else 0)
                parts.append(L([(a, yy), (b_, yy)]))
        return rj(_union(*parts))

    def on_axis(p, deg=0):
        return _xf(_rot(p, deg), f=AX)

    def standing(p, deg):
        """rotated, then set on the baseline"""
        q = _rot(p, deg); b = q.bounds
        return _xf(q, f=-b[1])

    for ch, fwd, back, dbl, Lk in (("→", 1, 0, 0, LA), ("←", 0, 1, 0, LA), ("↔", 1, 1, 0, 2 * PW),
                                   ("⟶", 1, 0, 0, LA + 0.8 * PW), ("⟵", 0, 1, 0, LA + 0.8 * PW), ("⟷", 1, 1, 0, 2.8 * PW),
                                   ("⇒", 1, 0, 1, LA), ("⇐", 0, 1, 1, LA), ("⇔", 1, 1, 1, 2 * PW)):
        new[ch] = op(on_axis(harrow(Lk, fwd, back, dbl)))
    for ch, fwd, back, dbl, Lk, deg in (("↑", 1, 0, 0, CAP, 90), ("↓", 1, 0, 0, CAP, -90), ("⇑", 1, 0, 1, CAP, 90), ("⇓", 1, 0, 1, CAP, -90)):
        new[ch] = op(standing(harrow(Lk, fwd, back, dbl), deg))
    for ch, dbl in (("↕", 0), ("⇕", 1)):
        q = _rot(harrow(BT - BB, 1, 1, dbl), 90)
        new[ch] = op(_xf(q, f=(BT + BB) / 2))
    for ch, deg in (("↗", 45), ("↖", 135), ("↙", -135), ("↘", -45)):
        new[ch] = op(on_axis(harrow(LA, 1, 0, 0), deg))
    # ⇤ ⇥ : ← / → with a bar PW tall at the tip, the = white between
    for ch, back in (("⇥", 0), ("⇤", 1)):
        a = harrow(LA, not back, back)
        xb = (LA / 2 + gap_eq + T / 2) * (-1 if back else 1)
        new[ch] = op(on_axis(_union(a, L([(xb, -h), (xb, h)]))))
    # ⇞ ⇟ : ↕'s length (the bracket band: a cap-height ↑ has no room for two bars under its head at 700-900) with two
    #       bars across the shaft (0.5 h to each side), the = white apart; the upper one keeps 0.8 of the = white from
    #       the head's arms, the lower one a stem's length of shaft under it
    LB = BT - BB; lb = 0.5 * h; x0a, x1a = -LB / 2 + T / 2, LB / 2 - T / 2
    x_hi = x1a - lb - (T + 0.8 * gap_eq) * math.sqrt(2); x_lo = x0a + T + 0.5 * gap_eq
    pb = max(min(p3, x_hi - x_lo), T + 0.35 * gap_eq)
    xc_b = min(x_hi - pb / 2, (x0a + x1a - h) / 2)
    for ch, deg in (("⇞", 90), ("⇟", -90)):
        bars = [L([(xc_b + s_ * pb / 2, -lb), (xc_b + s_ * pb / 2, lb)]) for s_ in (-1, 1)]
        new[ch] = op(_xf(_rot(rj(_union(harrow(LB, 1), *bars)), deg), f=(BT + BB) / 2))
    # ↰ ↱ ↳ ↴ ↵ ⏎ : one turn, round corner; the head's arm touches the cap height or the baseline
    Wt = 1.2 * PW
    yc_up = CAP - h - T / 2
    xs, xt = Wt - T / 2, T / 2                             # stem x, tip x
    new["↰"] = op(round_joins(_union(L([(xs, T / 2), (xs, yc_up), (xt, yc_up)]), head((xt, yc_up), (-1, 0))), FR))
    new["↱"] = _mirror(new["↰"])
    yc_dn = h + T / 2
    new["↳"] = op(round_joins(_union(L([(xt, CAP - T / 2), (xt, yc_dn), (xs, yc_dn)]), head((xs, yc_dn), (1, 0))), FR))
    new["↵"] = _mirror(new["↳"])
    new["⏎"] = _mirror(new["↳"])
    new["↴"] = op(round_joins(_union(L([(xt - h, CAP - T / 2), (Wt - T / 2 - h, CAP - T / 2), (Wt - T / 2 - h, T / 2)]),
                                     head((Wt - T / 2 - h, T / 2), (0, -1))), FR))
    # ↩ ↪ : the arrow on the lower line, its tail turning up round a half circle and back
    r_k = 0.36 * PW
    y0 = -r_k
    xa, xc_ = -LA / 2 + T / 2, LA / 2 - T / 2 - r_k
    hk = [(xa + 0.55 * LA, y0 + 2 * r_k), (xc_, y0 + 2 * r_k)] + ell_pts(xc_, y0 + r_k, r_k, r_k, 90, -90, 30) + [(xa, y0)]
    q = rj(_union(L(hk), head((xa, y0), (-1, 0))))
    b = q.bounds
    new["↩"] = op(_xf(q, f=AX - (b[1] + b[3]) / 2)); new["↪"] = _mirror(new["↩"])
    # ↺ ↻ : three quarters of a circle (baseline to the cap height) from its left end round the bottom to the top,
    #       where the head points on. On a curve the head is set along the chord of the arc it covers, not the
    #       tangent: the arc then runs down the middle of the head as a straight shaft does (along the tangent the
    #       inner arm ran into the arc — the V between them closed)
    rc = (CAP - T) / 2; ycc = CAP / 2
    arc = ell_pts(0, ycc, rc, rc, 180, 450, 90)
    hh_c = 0.8 * h; phi = hh_c / rc
    tip = (0, ycc + rc)
    ux, uy = -rc * math.sin(phi), rc * (1 - math.cos(phi)); ul = math.hypot(ux, uy)
    circ = round_joins(_union(L(arc), head(tip, (ux / ul, uy / ul), hh_c)), 0.5 * FR)
    new["↺"] = op(circ); new["↻"] = _mirror(new["↺"])
    INFO["circ"] = math.degrees(math.atan2(uy, -ux))

    # ⇧ ⇪ : the outline arrow (keyboard: baseline to the cap height), head wings at 45°
    def up_outline(y0_, y1_):
        w2 = (y1_ - y0_ - T) * 0.52; apex = (0, y1_ - T / 2); yw = apex[1] - w2
        w1 = 0.46 * w2
        pts = [(-w1, y0_ + T / 2), (-w1, yw), (-w2, yw), apex, (w2, yw), (w1, yw), (w1, y0_ + T / 2), (-w1, y0_ + T / 2), (-w1, yw)]
        return round_joins(L(pts), 0.5 * FR), w1
    sh_, w1 = up_outline(0, CAP)
    new["⇧"] = op(sh_)
    new["⇪"] = op(_union(sh_, L([(-w1, -gap_eq - T / 2), (w1, -gap_eq - T / 2)])))   # ⇧ over a bar under the baseline

    # =============================================================== keyboard (baseline to the cap height, T pen)
    kb0, kb1 = T / 2, CAP - T / 2
    # ⌃ : the arrow head alone, its top on the cap height; ⌅ : the same under a bar on the cap height
    new["⌃"] = op(head((0, kb1), (0, 1)))
    new["⌅"] = op(_union(L([(-h, kb1), (h, kb1)]), head((0, kb1 - p3), (0, 1))))
    # ⌘ : four 270° loops joined by the four sides of a square; loops 0.8 of the square's half side. Four strokes stack
    #     in the cap height (loop, side, side, loop), so a loop's counter is 2 rl - T: 63 at 700, 39 at 800, 13 at 900
    #     (shut). The loops and the square keep WHITE_K S (0.4 S) of white: the loops grow, up to the square's size, and
    #     where four pens and three such whites need more than the cap height the sign grows (as ≤ ∈ grow past PW), up to
    #     the ascender; past that the pen lightens (a lighter pen in the cap height made ⌘ lighter at 900 than at 800)
    wk, cmin = T, 0.4 * S
    sq = (CAP - wk) / 2 / 2.6; rl = 0.8 * sq; cyk = CAP / 2
    if 2 * rl - wk < cmin:
        Hk = min(ASC, max(CAP, 4 * T + 3 * cmin))
        wk = min(T, max(DV, (Hk - 3 * cmin) / 4))
        hk = (Hk - wk) / 2
        rl = max(0.8 * hk / 2.6, (wk + cmin) / 2); sq = hk - 2 * rl; cyk = Hk / 2
    INFO["⌘"] = (round(wk, 1), round(2 * rl - wk, 1), round(2 * sq - wk, 1), round(2 * cyk))
    cs = []
    corners = [(1, 1, 180, -90), (-1, 1, -90, -360), (-1, -1, 0, -270), (1, -1, 90, -180)]
    for sx, sy, a0, a1 in corners:
        cs += ell_pts(sx * (sq + rl), cyk + sy * (sq + rl), rl, rl, a0, a1, 40)
    cs.append(cs[0])
    new["⌘"] = op(round_joins(L(cs, wk), 0.5 * FR))
    # ⌥ ⎇ : ‾\_ with a separate bar on the top right; ⎇ is ⌥ turned over
    Wk = 1.1 * CAP - T
    xa_, xb_ = 0.28 * Wk, 0.70 * Wk
    opt = _union(L([(0, kb1), (xa_, kb1), (xb_, kb0), (Wk, kb0)]), L([(xb_ - 0.04 * Wk, kb1), (Wk, kb1)]))
    new["⌥"] = op(round_joins(opt, 0.5 * FR)); new["⎇"] = op(_flip(new["⌥"]["p"], CAP / 2))
    # ⌫ ⌦ ⌧ : a key outline (⌫ ⌦ pointed, ⌧ square) with a × inside, 0.6 of the = white clear of the outline
    Hk = CAP - T
    wk = 1.4 * CAP - T
    pt = 0.5 * Hk                                          # the point's depth (45°)
    dele = [(wk, kb0), (pt, kb0), (0, CAP / 2), (pt, kb1), (wk, kb1), (wk, kb0), (pt, kb0)]
    xcx, xr_ = (pt + wk) / 2, CAP / 2 - 1.5 * T - 0.6 * gap_eq
    xx = _union(L([(xcx - xr_, CAP / 2 - xr_), (xcx + xr_, CAP / 2 + xr_)]), L([(xcx - xr_, CAP / 2 + xr_), (xcx + xr_, CAP / 2 - xr_)]))
    new["⌫"] = op(round_joins(_union(L(dele), xx), 0.5 * FR)); new["⌦"] = _mirror(new["⌫"])
    wq = 1.2 * CAP - T
    box_ = [(0, kb0), (0, kb1), (wq, kb1), (wq, kb0), (0, kb0), (0, kb1)]
    xx2 = _union(L([(wq / 2 - xr_, CAP / 2 - xr_), (wq / 2 + xr_, CAP / 2 + xr_)]), L([(wq / 2 - xr_, CAP / 2 + xr_), (wq / 2 + xr_, CAP / 2 - xr_)]))
    new["⌧"] = op(round_joins(_union(L(box_), xx2), 0.5 * FR))
    # ⏏ : a filled triangle over a filled bar, the = white between; ‣ ⚠ below use the same filled shapes
    wej = 1.3 * PW - T
    ybar = T / 2
    tri_b = T + gap_eq + T / 2
    new["⏏"] = op(_union(_fill_poly([(-wej / 2, tri_b), (wej / 2, tri_b), (0, min(kb1, tri_b + 0.55 * wej))], T), L([(-wej / 2, ybar), (wej / 2, ybar)], T)))
    # ⎋ : a circle open at the upper left, an arrow ↖ from its centre out through the gap
    rc2 = (CAP - T) / 2; cy2 = CAP / 2
    tip2 = (-0.78 * rc2 * c45 * 1.28, cy2 + 0.78 * rc2 * c45 * 1.28)
    hh2 = 0.62 * h
    arm_h = (tip2[0] + hh2 * math.sqrt(2), tip2[1]); arm_v = (tip2[0], tip2[1] - hh2 * math.sqrt(2))
    a_s, a_e = 90.0, 180.0 - 360.0
    ring_pts = lambda s_, e_: ell_pts(0, cy2, rc2, rc2, s_, e_, 90)
    while _poly_dist(ring_pts(a_s, a_s + 1), tip2, arm_h) < T + GAP and a_s > 0:
        a_s -= 2
    while _poly_dist(ring_pts(a_e + 360, a_e + 361), tip2, arm_v) < T + GAP and a_e > -270:
        a_e += 2
    esc = _union(L(ring_pts(a_s, a_e)), L([(0, cy2), tip2]), L([arm_h, tip2, arm_v]))
    new["⎋"] = op(round_joins(esc, 0.5 * FR))
    # ✓ ✔ ✗ ✘ : in the PW square on the axis (✓ 1.3 PW wide); the heavy ones with the heavy pen
    def check(w):
        Wc = 1.3 * PW - w; hc_ = (PW - w) / 2
        return round_joins(L([(-Wc / 2, AX + 0.05 * hc_), (-Wc / 2 + 0.36 * Wc, AX - hc_), (Wc / 2, AX + hc_)], w), 0.5 * FR)

    def cross(w):
        e_ = (PW - w) / 2
        return round_joins(_union(L([(-e_, AX + e_), (e_ * 0.96, AX - e_)], w), L([(-e_ * 0.96, AX - e_), (e_, AX + e_ * 1.04)], w)), 0.5 * FR)
    new["✓"] = op(check(T)); new["✔"] = op(check(HV)); new["✗"] = op(cross(T)); new["✘"] = op(cross(HV))
    # ⚠ : a filled triangle (1.2 as wide as tall, round corners T/2) with a white ! of limn's stem and pin cut out of it,
    #     a margin of 0.75 T all round; the triangle grows with the pen (1.12 CAP + 0.8 T tall), so the sign gains weight as its white ! does; the ! is
    # limn's stem, never narrower than 0.05 of the triangle (at 100-200 the stem alone read as a hairline)
    Hw = 1.12 * CAP + 0.8 * T; Ww = 1.2 * Hw; m = 0.75 * T; SK = max(S, 0.05 * Hw)
    trip = [(-Ww / 2 + T / 2, T / 2), (Ww / 2 - T / 2, T / 2), (0, Hw - T / 2)]
    solid = _fill_poly(trip, T)
    sa = math.sin(math.atan2(Ww / 2, Hw))
    yp = m + R
    yt_ = Hw - (SK / 2 + m) / sa
    stem = L([(0, yp + R + GAP + SK / 2), (0, yt_)], SK)
    new["⚠"] = op(_diff(solid, _union(stem, _circle(0, yp, R))))
    INFO["warn"] = (yt_ - (yp + R + GAP)) / S

    # =============================================================== general punctuation
    new["‖"] = cell_sb(pathops.Path(par), sb_of("|"))
    # ‗ : _ doubled about its own centre, the = white scaled to _'s bar
    u = G["_"]["p"]; ub = u.bounds; tu = ub[3] - ub[1]; gu = gap_eq * tu / T
    new["‗"] = {"p": _union(_xf(u, f=(tu + gu) / 2), _xf(u, f=-(tu + gu) / 2)), "adv": G["_"]["adv"], "pins": []}
    # ‾ : _ reflected through the axis; ‿ ⁀ : an arc at _ and at ‾
    new["‾"] = {"p": _flip(u, AX), "adv": G["_"]["adv"], "pins": []}
    # (ties are small marks: the LIGHT pen; as wide as ⁓, 1.3 PW, and 0.2 PW + half a pen deep, so at 800-900 they
    #  stay arcs, not beans)
    yu = (ub[1] + ub[3]) / 2; dtie = 0.2 * PW + 0.5 * LV; wtie = (1.3 * PW - LV) / 2
    lpen = lambda pts: pen_line(pts, LV, LH)
    tie = lpen(ell_pts(0, yu + dtie, wtie, dtie, 180, 360, 40))
    new["‿"] = cell_sb(tie, sb_of("_")); new["⁀"] = cell_sb(_flip(tie, AX), sb_of("_"))
    g_cl = 0.5 * PW                                         # ⁐ : ⁀ over ‿, their ends 0.5 PW apart about the axis
    new["⁐"] = cell_sb(_union(lpen(ell_pts(0, AX + g_cl / 2, wtie, dtie, 0, 180, 40)),
                              lpen(ell_pts(0, AX - g_cl / 2, wtie, dtie, 180, 360, 40))), sb_of("_"))
    # ‛ ‟ : ’ ” mirrored (reversed nine)
    new["‛"] = _mirror(copy("’")); new["‟"] = _mirror(copy("”"))
    # ‣ : a filled triangle pointing right on the axis, 1.25 × • (never under 0.45 XH); ⁃ : a bar T as long as • is wide
    Db = 2 * 1.7 * R
    Dt = max(1.25 * Db, 0.45 * XH)                                     # a triangle reads smaller than a disc of its height
    wc_ = min(T, 0.3 * Dt); tr_h = Dt - wc_; tr_w = 0.87 * tr_h        # corners: a round pen of 0.3 of its size
    new["‣"] = cell_sb(_fill_poly([(-tr_w / 2, AX - tr_h / 2), (tr_w / 2, AX), (-tr_w / 2, AX + tr_h / 2)], wc_), sb_of("•"))
    new["⁃"] = cell_sb(L([(-(Db - T) / 2, AX), ((Db - T) / 2, AX)]), sb_of("•"))
    # ․ ‥ ‧ : the period, two pins of … , the middle dot
    new["․"] = copy(".")
    new["‥"] = {"p": pathops.Path(), "adv": round(e3["adv"] - (e3["pins"][1][0] - e3["pins"][0][0])), "pins": e3["pins"][:2],
               "kinds": [e[0] for e in DOTSPEC["…"]["pins"][:2]]}
    new["‧"] = copy("·")
    # ‱ : ‰ with one more small ring, at the pitch of its last two
    pm_ = G["‰"]["p"]; cs_ = list(pm_.contours)
    rings = sorted([c for c in cs_ if c.bounds[3] < CAP * 0.6], key=lambda c: -c.bounds[2])
    if len(rings) >= 3:
        last = rings[0]; lb = last.bounds
        ring_last = [c for c in rings if c.bounds[0] >= lb[0] - 0.5 and c.bounds[2] <= lb[2] + 0.5]
        prev = [c for c in rings if c not in ring_last]
        pitch_r = lb[0] - max(prev, key=lambda c: c.bounds[2]).bounds[0]
        cp = pathops.Path(); pen_ = cp.getPen()
        for c in ring_last:                                   # the ring and its counter in one path, so the counter stays white
            c.draw(pen_)
        q = _union(pathops.Path(pm_), _xf(cp, e=pitch_r))
        new["‱"] = {"p": q, "adv": round(G["‰"]["adv"] + pitch_r), "pins": []}
    # ′ ″ ‴ ⁗ and the reversed ones: the prime repeated at the pitch of ″
    pr = G["′"]["p"]; dp = 1.5 * S
    for ch, n in (("‴", 3), ("⁗", 4)):
        new[ch] = {"p": _union(*[_xf(pr, e=i * dp) for i in range(n)]), "adv": round(G["′"]["adv"] + (n - 1) * dp), "pins": []}
    new["‵"] = _mirror(copy("′")); new["‶"] = _mirror(copy("″")); new["‷"] = _mirror(new["‴"])
    # ‸ : a caret of ^ 's pen hanging under the baseline, GAP below it, 0.42 XH tall (at least 2.2 stems: at 900 the
    #     legs were shorter than the pen) and 0.67 XH wide (Inter's)
    hw_c = (0.67 * XH - S) / 2; ya_c = -GAP - S / 2; hc_c = min(max(0.42 * XH, 2.2 * S), ya_c + S / 2 + 320)   # (inside the -330 line)
    new["‸"] = cell_sb(L([(-hw_c, ya_c - hc_c + S), (0, ya_c), (hw_c, ya_c - hc_c + S)], S), sb_of("^"))
    # ⁁ : a long stroke rising right from under the baseline and a short leg from its middle down to the right
    lh = PW - T
    a0_, a1_ = (-0.30 * lh, YB - 0.2 * XH), (0.30 * lh, YB - 0.2 * XH + lh)
    mid_ = ((a0_[0] + a1_[0]) / 2, (a0_[1] + a1_[1]) / 2)
    new["⁁"] = cell_sb(rj(_union(L([a0_, a1_]), L([mid_, (mid_[0] + (mid_[1] - a0_[1]) * 0.6, a0_[1])]))), sb_of("^"))
    # * family: ⁎ is * lowered so its ink stands on the comma line; ⁑ two * stacked on the cap height and
    #           the baseline; ⁂ three * at 0.6 in a triangle; ⁕ eight arms of * 's pen on the axis
    sb_ = st.bounds
    new["⁎"] = {"p": _xf(st, f=YB - sb_[1]), "adv": G["*"]["adv"], "pins": []}
    new["⁑"] = {"p": _union(st, _xf(st, f=-sb_[1])), "adv": G["*"]["adv"], "pins": []}
    from weights import grow as _wgrow
    k_s = 0.6
    small = _xf(st, k_s, 0, 0, k_s, 0, 0)
    try:
        small = _wgrow(small, 0.15 * S * (1 - k_s), 0.15 * S * (1 - k_s))
    except pathops.PathOpsError:
        pass
    smb = small.bounds; sw = smb[2] - smb[0]; shh = smb[3] - smb[1]
    wsm = sym_white(M) * 0.6
    tri3 = [(-(sw + wsm) / 2, 0), ((sw + wsm) / 2, 0), (0, shh + wsm * 0.6)]
    ast = _union(*[_xf(small, e=x - (smb[0] + smb[2]) / 2, f=y - smb[1]) for x, y in tri3])
    ab_ = ast.bounds
    new["⁂"] = cell_sb(_xf(ast, f=CAP / 2 + 0.05 * CAP - (ab_[1] + ab_[3]) / 2), sb_of("*"))
    aw = 0.75 * S if S <= 120 else 90 + 0.45 * (S - 120)
    # eight arms 0.76 XH across; the white between two arm ends is at least 0.35 of an arm, and where 0.76 XH leaves less
    # (from 600 up) the flower grows rather than its arms thinning, so it gains weight at every step
    rf = max((0.76 * XH - aw) / 2, 1.35 * aw / (2 * math.sin(math.radians(22.5))))
    new["⁕"] = cell_sb(_union(*[L([(0, AX), (rf * math.cos(math.radians(22.5 + 45 * i)), AX + rf * math.sin(math.radians(22.5 + 45 * i)))], aw) for i in range(8)]), sb_of("*"))
    # ⁓ : ~ drawn 1.3 PW long
    a_w = (1.3 * PW - T) / 2; b_w = 0.08 * PW + 0.1 * T
    new["⁓"] = cell_sb(L([(-a_w + 2 * a_w * i / 60, AX + b_w * math.sin(math.pi * (-1 + 2 * i / 60) + math.pi)) for i in range(61)]), sb_of("–"))
    # ⁅ ⁆ : [ ] with a quill: a stroke of the top arm's own thickness from the stem to half the arm's length, on the axis
    lb_ = G["["]["p"]; bb = lb_.bounds
    stem_l, stem_r = min((iv for iv in P.slice_ivs(lb_, AX)), key=lambda iv: iv[0])
    arm_x = max(b for a, b in P.slice_ivs(lb_, bb[3] - 2))
    xm = (stem_r + arm_x) / 2
    ta = _inter(lb_, P._rect(xm - 0.5, AX, xm + 0.5, 1e4)).bounds; ta = ta[3] - ta[1]
    quill = line([((stem_l + stem_r) / 2, AX), (stem_r + 0.5 * (arm_x - stem_r) - ta / 2, AX)], ta)
    new["⁅"] = {"p": round_joins(_union(lb_, quill), FR), "adv": G["["]["adv"], "pins": []}
    new["⁆"] = _mirror(new["⁅"])
    # ‼ ⁇ ⁈ ⁉ ‽ : ! and ? set together with one side bearing of white between them (half of "!!" typed)
    def pair(a, b):
        ga_, gb_ = copy(a), copy(b)
        ba_ = _box(ga_["p"], ga_["pins"], R); bb_ = _box(gb_["p"], gb_["pins"], R)
        white = ((ga_["adv"] - ba_[2]) + bb_[0]) / 2
        dx = ba_[2] + white - bb_[0]
        return {"p": _union(ga_["p"], _xf(gb_["p"], e=dx)) if not _empty(gb_["p"]) else ga_["p"], "adv": round(dx + gb_["adv"]),
                "pins": ga_["pins"] + [(x + dx, y) for x, y in gb_["pins"]], "kinds": ga_["kinds"] + gb_["kinds"]}
    new["‼"] = pair("!", "!"); new["⁇"] = pair("?", "?"); new["⁈"] = pair("?", "!"); new["⁉"] = pair("!", "?")
    q_ = copy("?"); qx = q_["pins"][0][0]; ex_ = G["!"]
    stem_ex = _xf(ex_["p"], e=qx - ex_["pins"][0][0])
    new["‽"] = {"p": round_joins(_union(q_["p"], stem_ex), 0.5 * FR), "adv": q_["adv"], "pins": q_["pins"], "kinds": q_["kinds"]}

    # =============================================================== maths coverage (2026-09-30)
    # ↦ : → with a bar PW tall across its tail
    x0t = -LA / 2 + T / 2
    new["↦"] = op(on_axis(rj(_union(harrow(LA, 1, 0, 0), L([(x0t, -h), (x0t, h)])))))
    # ⟨ ⟩ : a chevron over the bracket band (the stem's pen S), the apex on the axis, as wide as ( is
    bw_ = G["("]["p"].bounds; wch = max(0.30 * (BT - BB), (bw_[2] - bw_[0]) + 0.3 * S)
    ang_b = L([(wch - S / 2, BT - S / 2), (S / 2, AX), (wch - S / 2, BB + S / 2)], S)
    new["⟨"] = cell_sb(rj(ang_b), sb_of("("))
    new["⟩"] = _mirror(new["⟨"])
    # ⌈ ⌉ ⌊ ⌋ : limn's [ with one arm: the other end of its stem is round, like every free end
    lbr = G["["]["p"]; lbb = lbr.bounds
    s_l, s_r = min(P.slice_ivs(lbr, AX), key=lambda iv: iv[0]); s_c = (s_l + s_r) / 2; s_w = s_r - s_l
    upper = _inter(lbr, P._rect(-1e4, AX, 1e4, 1e4))
    column = _union(_inter(lbr, P._rect(s_l - 1, lbb[1] + s_w / 2, s_r + 1, AX + 1)), _circle(s_c, lbb[1] + s_w / 2, s_w / 2))
    ceil_l = {"p": _union(upper, column), "adv": G["["]["adv"], "pins": []}
    new["⌈"] = ceil_l; new["⌉"] = _mirror(ceil_l)
    floor_l = {"p": _flip(ceil_l["p"], (lbb[1] + lbb[3]) / 2), "adv": G["["]["adv"], "pins": []}
    new["⌊"] = floor_l; new["⌋"] = _mirror(floor_l)
    # ∌ : ∋ with the negation slash (∉ mirrored)
    new["∌"] = _mirror(new["∉"])
    # ≔ : the colon's two pins before = , each pin on a bar's line, GAP between a pin and the bar it leads
    xb0 = R + GAP
    dp = max(dq, R + GAP / 2)                             # the pins never closer than GAP (the text cuts' larger pin)
    new["≔"] = op(_union(L([(xb0 + T / 2, AX + dq), (xb0 + 2 * h + T / 2, AX + dq)]), L([(xb0 + T / 2, AX - dq), (xb0 + 2 * h + T / 2, AX - dq)])),
                  [(0, AX + dp), (0, AX - dp)])
    # ≝ : = under the letters d e f at the superior scale (0.40), reweighed to the LIGHT pen, the = sign's white between
    from punct import _reweigh
    from fontTools.pens.roundingPen import RoundingPen
    kd = 0.40; word = pathops.Path(); x_ink = None
    for c in "def":
        q, _ = _reweigh(M, _xf(G[c]["p"], kd, 0, 0, kd, 0, 0), kd, (LV, LH))
        qg = pathops.Path(); q.draw(RoundingPen(qg.getPen(), roundFunc=lambda v: round(v * 10) / 10)); qg.simplify()
        qg = round_joins(qg, 0.9)                          # the scaled letter's own slits (f's hook at 900) close
        gb = qg.bounds
        # set by their scaled side bearings, and never closer than half the LIGHT pen (the pen of 800-900 joined d e f)
        if x_ink is None:
            qg = _xf(qg, e=-gb[0])
        else:
            gap_l = max(kd * (sb_prev + (G[c]["p"].bounds[0])), 0.5 * LV)
            qg = _xf(qg, e=x_ink + gap_l - gb[0])
        word = _union(word, qg); x_ink = qg.bounds[2]
        sb_prev = G[c]["adv"] - G[c]["p"].bounds[2]
    wb = word.bounds
    # the = sign's white under the word, unless that takes it over TOP_MAX (accents.py: the line box tops at 970; the word
    # reached 974 at 900): then the white narrows, down to WS (the white inside small marks), and past that the word shrinks
    from accents import TOP_MAX
    y0 = AX + dq + T / 2; wh = wb[3] - wb[1]
    white = max(min(gap_eq, TOP_MAX - y0 - wh), min(gap_eq, sym_white(M)))
    word = _xf(word, e=-(wb[0] + wb[2]) / 2, f=y0 + white - wb[1])
    if y0 + white + wh > TOP_MAX:
        k = (TOP_MAX - y0 - white) / wh
        word = _xf(word, k, 0, 0, k, 0, (y0 + white) * (1 - k))
    INFO["≝"] = round(white, 1)
    new["≝"] = op(_union(eq, word))
    # ⋮ ⋱ : three pins at the pitch of … , upright and falling
    pe = e3["pins"][1][0] - e3["pins"][0][0]
    new["⋮"] = cell_sb(pathops.Path(), sb_ell, [(0, AX + pe), (0, AX), (0, AX - pe)])
    pd = pe / math.sqrt(2)
    new["⋱"] = cell_sb(pathops.Path(), sb_ell, [(-pd, AX + pd), (0, AX), (pd, AX - pd)])
    # ℕ ℤ ℚ ℝ ℂ : the double-struck capitals — limn's letter with one LIGHT stroke more inside it, parallel to its main
    #   stroke and WS from it (N R: beside the left stem, into the diagonal or the bowl's top; C Q: inside the bowl's left
    #   side, from arc to arc; Z: along the diagonal, from the bottom bar up to where the letter ends), joined round
    WSd = sym_white(M)

    def col_hits(p, x, y0, up=True):
        """The first ink above (below) y0 on the vertical line x."""
        runs = sorted((c.bounds[1], c.bounds[3]) for c in _inter(p, P._rect(x - 0.5, -1e4, x + 0.5, 1e4)).contours)
        if up:
            return next((a for a, b in runs if a >= y0), None)
        return next((b for a, b in reversed(runs) if b <= y0), None)

    def struck(letter, kind):
        lp = G[letter]["p"]; lb = lp.bounds
        if kind == "stem":                     # N R: beside the left stem
            a_, b_ = P.slice_ivs(lp, 0.2 * CAP)[0]
            x = b_ + WSd + LV / 2
            y_top = col_hits(lp, x, 0.2 * CAP) or CAP
            q = pen_line([(x, LH / 2), (x, y_top + LH / 2)], LV, LH)
        elif kind == "bowl":                   # C Q: inside the bowl's left side
            a_, b_ = P.slice_ivs(lp, (lb[1] + lb[3]) / 2)[0]
            x = b_ + WSd + LV / 2; ym = (lb[1] + lb[3]) / 2
            yh, yl = col_hits(lp, x, ym), col_hits(lp, x, ym, up=False)
            q = pen_line([(x, yl - LH / 2), (x, yh + LH / 2)], LV, LH)
        else:                                  # Z: along the diagonal, on its right
            ivs = lambda y: [iv for iv in P.slice_ivs(lp, y) if iv[1] - iv[0] < 3 * S]
            y1, y2 = 0.3 * CAP, 0.6 * CAP
            (c1a, c1b), (c2a, c2b) = ivs(y1)[0], ivs(y2)[0]
            slope = ((c2a + c2b) / 2 - (c1a + c1b) / 2) / (y2 - y1)
            off = (c1b - c1a) / 2 + (WSd + LV / 2) * math.hypot(1, slope)
            xat = lambda y: (c1a + c1b) / 2 + slope * (y - y1) + off
            y_end = y1
            while y_end < CAP and xat(y_end + 2) < lb[2] - LV / 2:
                y_end += 2
            q = pen_line([(xat(LH / 2), LH / 2), (xat(y_end), y_end)], LV, LH)
        return {"p": round_joins(_union(lp, q), 0.5 * FR), "adv": G[letter]["adv"], "pins": []}
    for ch, (letter, kind) in {"ℕ": ("N", "stem"), "ℝ": ("R", "stem"), "ℂ": ("C", "bowl"), "ℚ": ("Q", "bowl"), "ℤ": ("Z", "diag")}.items():
        if letter in G:
            new[ch] = struck(letter, kind)
    # ℏ : h with the bar of ħ slanted 20 degrees (rising to the right) through its stem
    if "ħ" in G:
        import accents as _acc
        bm = _acc.ST["marks"].get("ħ")
        if bm is not None and not _empty(bm):
            bb_ = bm.bounds; cxb, cyb = (bb_[0] + bb_[2]) / 2, (bb_[1] + bb_[3]) / 2
            tb = bb_[3] - bb_[1]; hl_ = (bb_[2] - bb_[0] - tb) / 2
            c20, s20 = math.cos(math.radians(20)), math.sin(math.radians(20))
            sl = line([(cxb - hl_ * c20, cyb - hl_ * s20), (cxb + hl_ * c20, cyb + hl_ * s20)], tb)
            new["ℏ"] = {"p": _union(G["h"]["p"], sl), "adv": G["ħ"]["adv"], "pins": []}

    # arrows and keyboard marks fill their cell edge to edge: they take the wider side bearing (OP_SB_WIDE; on OP_SB →
    # read 45-77 units and ⌘C 55-67 tighter than the references at 700)
    for ch in GROUPS["arrows"] + GROUPS["tech"]:
        g = new.get(ch)
        if not g: continue
        dx = (M["OP_SB_WIDE"] - M["OP_SB"])
        g["p"] = _xf(g["p"], e=dx); g["pins"] = [(x + dx, y) for x, y in g["pins"]]; g["adv"] = g["adv"] + 2 * dx
    # =============================================================== into G and DOTSPEC
    for ch, g in new.items():
        pins = [(round(x, 1), round(y, 1)) for x, y in g.get("pins", [])]
        kinds = g.get("kinds") or ["mid"] * len(pins)
        p = pathops.Path(g["p"]); p.simplify()
        G[ch] = {"p": p, "adv": int(round(g["adv"])), "pins": pins}
        if pins:
            ys = {"base": round(2 * QR, 1), "top": XO}
            DOTSPEC[ch] = {"only": False, "adv0": G[ch]["adv"],
                           "pins": [[k, x, ys.get(k, y), round(QR, 1)] for (x, y), k in zip(pins, kinds)]}
        ST["changed"].add(ch)
    f0 = lambda v: f"{v:.0f}"
    return [
        [GROUPS["maths"][:24], "수학 연산자 · 축 부류", f"축 {f0(AX)}, 잉크 PW {f0(PW)} 정사각, T 펜 {f0(T)}, 한 폭(op_cell: 잉크를 max(잉크, PW) + 양옆 = 의 옆 여백 {f0(M['OP_SB'])}), 나란한 획 사이 = 의 흰 틈 {f0(gap_eq)}. "
         f"부정 빗금은 / 기울기(20°)로 = 보다 {f0(OV)} 더, 고리(⊕ ⊖ ⊗ ⊘ ⊙ ∅ ∮)는 DENSE 펜 1.1 PW, 고리의 빗금은 Ø처럼 모서리에서 모서리로"],
        [GROUPS["maths"][24:], "수학 · 글자 꼴", f"∑ = Z 폭, ∏ = H 폭(평평한 발), ∆ ∇ = A 폭·높이, ∂ = o 대비의 속 0.64 CAP + 갈고리, ∫ = 디센더~어센더(고리 {f0(r_h)}), ∀ = A 돌림, ∃ = E 뒤집음 — 가족의 펜, 닮은 글자의 옆 여백. "
         f"∞ ∝ 1.5 × 0.74 XH, ∴ ∵ ∶ ⋯ ≐ ≒ ⊙ 의 점은 핀"],
        [GROUPS["arrows"], "화살표", f"축지름은 수학 축, 머리는 축지름과 45°인 두 팔로 PW({f0(PW)}) 폭, T 펜. → 1.5 PW, ↔ 2 PW, 긴 화살표 +0.8 PW, 세로 화살표는 기준선~대문자 높이, ↕ ⇕ ⇞ ⇟ 는 괄호 띠. "
         f"⇒ 류는 두 축지름 = 의 흰 틈, 둥근 화살표 ↺ ↻ 는 머리를 접선이 아니라 호의 현 방향으로({INFO['circ']:.0f}° 기울임, 안쪽 팔이 호와 붙지 않게)"],
        [GROUPS["punct"], "일반 구두점", "‖ = | 둘(= 의 흰 틈), ‗ ‾ ‿ ⁀ ⁐ 는 _ 에서(‾ 는 축에 대칭), ‛ ‟ 는 ’ ” 뒤집음, ‣ ⁃ 는 • 폭, ․ ‥ ‧ 는 핀, ‱ 는 ‰ + 고리, ‴ ⁗ ‵ ‶ ‷ 는 ′ 반복, "
         "‼ ⁇ ⁈ ⁉ 는 ! ? 를 옆 여백 하나 사이로, ‽ 는 ? + ! 의 줄기, ⁎ ⁑ ⁂ ⁕ 는 * 에서, ⁅ ⁆ 는 [ ] + 팔 반, ◦ 는 • 크기 고리(LIGHT 펜), "
         f"◌ 는 © 고리(O 높이 {INFO['◌'][1]}, LIGHT 펜)를 점 {INFO['◌'][0]}개로 끊은 것 — 점은 LIGHT 펜을 한 번 찍은 것, 점 사이 흰 틈 {INFO['◌'][2]:.0f}"],
        ["↦ ⟨ ⟩ ⌈ ⌉ ⌊ ⌋ ∌ ≔ ≝ ⋮ ⋱ ℕ ℤ ℚ ℝ ℂ ℏ", "수학 · 괄호와 글자꼴", "↦ = → + 꼬리 막대(PW), ⟨ ⟩ = 괄호 띠의 꺾쇠(S 펜, 꼭지는 축), ⌈ ⌉ ⌊ ⌋ = limn의 [ 에서 팔 하나(다른 끝은 둥글게), "
         "∌ = ∉ 뒤집음, ≔ = 콜론의 두 핀 + =, ≝ = = 위 def(0.40, LIGHT 펜), ⋮ ⋱ = … 간격의 핀 셋, ℕ ℤ ℚ ℝ ℂ = limn 글자 + 안쪽에 나란한 LIGHT 획(WS 띄움), ℏ = h + ħ의 막대를 20° 기울여"],
        [GROUPS["tech"], "키보드·확인", f"키 기호는 기준선~대문자 높이, T 펜, 둥근 이음. ⌃ 는 화살표 머리, ⌘ 는 270° 고리 넷, ⎇ = ⌥ 뒤집음, ⏎ = ↵. ✓ ✗ 는 PW 칸, ✔ ✘ 는 펜 T + 0.14 PW. "
         f"⚠ 는 채운 삼각형(1.12 CAP + 0.8 T, 펜과 함께 커짐)에서 limn의 줄기(삼각형의 0.05 이상)·핀 크기 ! 를 빼냄(줄기 {INFO['warn']:.1f} S)"],
    ]
