"""limn numeric, letterlike and currency symbols (2026-09-29) — superiors and inferiors, vulgar fractions, Roman
numerals, letterlike symbols and the currency signs, each built on a class of tools/punct.py.

build_font.py calls this once, right after apply_sym_new (the figures, letters, ° © ™ and the fraction slash are
final by then):

    from sym_numeric import apply_sym_numeric; MODS.extend(apply_sym_numeric(G, globals()))

The rules (y up, font units; K = K_SUP = 0.58; the pens are punct.sym_pens: LIGHT = the superior pen, DENSE, and the
family's own elliptical pen M["PEN"]):

  superior   ONE map for every superior figure, sign, bracket and letter (and the existing ¹ ² ³, the modifier letters
             ˣ ʲ ᵀ and the inferior ⱼ): limn's glyph scaled
             by K about its origin, reweighed to the LIGHT pen (punct._reweigh — a scaled glyph alone is 0.58 S, too
             light), then raised so a flat top on the cap height stays on the cap height, and the superiors lifted SUP_LIFT
             (0.11 CAP) over it. Everything therefore shares one superior baseline, BSUP = 0.42 CAP − 2 ry (0.40 CAP) + the lift: ⁿ ⁱ sit on it like the figures (Inter, Pretendard
             do the same), ª º keep their ordinal rule (top on the cap height). The advance is K × the glyph's own +
             the pen's growth, so the side bearings are K × the full-size ones — and the figures, tabular at full size,
             are tabular among themselves, but for ¹ ₁, which take the proportional 1 (the tabular cell's white made
             x₁ read wider than x₂). The signs and brackets ⁺ ⁻ ⁼ ⁽ ⁾ (and inferiors) add 0.25-0.35 S a side for
             their pen growth.
             ⁱ: the stem as above; its dot is the pin at the superior scale (K PIN_R + the pen growth), K × the i's own
             white above the stem (references: ⁱ white 0.45-0.57 of i's), drawn as ink (a mark, like ª º).
  inferior   (with ᵢ U+1D62) the superior drawing, moved down so its baseline is BSUB = −0.19 CAP (−133): Inter −0.20 · −0.21 CAP
             (₁ · ₀ at 400-700), Pretendard −0.17 · −0.19 CAP. Same widths.
  fraction   as ½ ¼ ¾: numerator superior, fraction slash (24°, LIGHT), denominator at the same size on the baseline,
             WS white to the slash; multi-figure parts (⅒) set with the proportional figure widths at that size.
             ℅ ℁ ℀: the letters at the same size, numerator top on the cap height (ª's rule), denominator on the baseline.
  Roman      Ⅰ–Ⅻ ⅰ–ⅻ: limn's letters set as a word — their own advances and the final kerning of their pairs (ii keeps
             the pin-pair white), pins kept as pins. Composed after the kerning (see _late), and they kern through
             the classes of their end letters (Ⅳ as I|V), like the accented letters. Ⅼ Ⅽ Ⅾ Ⅿ ⅼ ⅽ ⅾ ⅿ are the letters.
  letterlike ℉ ℃ = ° + F / C as set; ℗ = © with P; ℠ = ™ with S M; ℓ ℮ Ω drawn with the family pen (below);
             K Å (U+212A U+212B) = the letters K Å and Ω (U+2126) = the Greek Ω where tools/greek.py builds it (else
             drawn here): copies made in _late, kerning through the letter's class (Å also keeps its ring's clearance).
  currency   "currency on a letter" (€ ¥ ₩): limn's letter at its own weight + LIGHT bars at the = sign's spacing,
             strokes through a capital reach 0.13 CAP past it (¢'s rule). Marks that reach past the letter use up to
             0.65 of its side bearing (SB_KEEP) but come no closer to the edge than T's bar ends; beyond that the
             glyph widens. Every white a mark cuts out is kept at every weight (the audit counts contours against
             700), each at least WHITE_K = 0.4 S wide: ₱'s bars cut the bowl into three equal whites and draw lighter
             where those would close (the DENSE rule, 800-900), ₦'s bars move together and draw lighter where N's
             crotches would close its corner whites, ₭'s bar rises until the white under it is open, ₡ ₲ ₾ ₴ move or
             shorten a mark where a white would close. ₹ ₺ ₼ ₾ ₪ are drawn on the metrics (the family pen; ₪'s four
             side-by-side verticals take the DENSE pen, like # « »).
"""
import math
from pathlib import Path

import pathops

from punct import (ST, K_SUP, sym_pens, sym_white, _reweigh, _xf, _union, _diff, _inter, _rect, _circle,
                   pen_line, ell_pts, bez_pts, _chain, round_joins, _slide, slice_ivs)

SUB_DROP = 0.19     # inferior baseline, in CAP below the baseline
# superiors sit this much CAP over the cap height (2026-09-30, user chose "B" on review/sup/sup.html): with the top on
# the cap height x² y² 84m² read close to x2; Pretendard lifts its superiors 0.11 CAP, Inter 0.16 (then 1.2 floats off
# the line). Only the superiors move: inferiors, fraction numerators and ª º ™ keep their places.
SUP_LIFT = 0.11
EXT = 0.13          # strokes through a capital reach this much CAP past it (¢'s rule)
SB_KEEP = 0.35      # a mark may use the letter's side bearing down to this share of it
SUP_REF = (0.872, (0.749 - 0.872) / (107 - 62))   # superior stroke ÷ stroke: the references' median at 400, per unit of S

SUPS = {"⁰": "0", "¹": "1", "²": "2", "³": "3", "⁴": "4", "⁵": "5", "⁶": "6", "⁷": "7", "⁸": "8", "⁹": "9",
        "⁺": "+", "⁻": "−", "⁼": "=", "⁽": "(", "⁾": ")", "ⁿ": "n", "ⁱ": "i",
        "ˣ": "x", "ʲ": "j", "ᵀ": "T"}                          # modifier letters: eˣ, xʲ, Aᵀ
SUBS = {"₀": "0", "₁": "1", "₂": "2", "₃": "3", "₄": "4", "₅": "5", "₆": "6", "₇": "7", "₈": "8", "₉": "9",
        "₊": "+", "₋": "−", "₌": "=", "₍": "(", "₎": ")", "ₐ": "a", "ₑ": "e", "ₒ": "o", "ₓ": "x", "ₕ": "h", "ₖ": "k",
        "ₗ": "l", "ₘ": "m", "ₙ": "n", "ₚ": "p", "ₛ": "s", "ₜ": "t", "\u1d62": "i",   # ᵢ (a modifier letter: ∑ᵢ xᵢ)
        "ⱼ": "j"}
FRACS = {"⅓": ("1", "3"), "⅔": ("2", "3"), "⅕": ("1", "5"), "⅖": ("2", "5"), "⅗": ("3", "5"), "⅘": ("4", "5"),
         "⅙": ("1", "6"), "⅚": ("5", "6"), "⅐": ("1", "7"), "⅛": ("1", "8"), "⅜": ("3", "8"), "⅝": ("5", "8"),
         "⅞": ("7", "8"), "⅑": ("1", "9"), "⅒": ("1", "10"), "⅟": ("1", ""), "↉": ("0", "3"),
         "℀": ("a", "c"), "℁": ("a", "s"), "℅": ("c", "o")}
ROMAN = {"Ⅰ": "I", "Ⅱ": "II", "Ⅲ": "III", "Ⅳ": "IV", "Ⅴ": "V", "Ⅵ": "VI", "Ⅶ": "VII", "Ⅷ": "VIII", "Ⅸ": "IX",
         "Ⅹ": "X", "Ⅺ": "XI", "Ⅻ": "XII", "Ⅼ": "L", "Ⅽ": "C", "Ⅾ": "D", "Ⅿ": "M",
         "ⅰ": "i", "ⅱ": "ii", "ⅲ": "iii", "ⅳ": "iv", "ⅴ": "v", "ⅵ": "vi", "ⅶ": "vii", "ⅷ": "viii", "ⅸ": "ix",
         "ⅹ": "x", "ⅺ": "xi", "ⅻ": "xii", "ⅼ": "l", "ⅽ": "c", "ⅾ": "d", "ⅿ": "m"}
WORDS = {"₧": "Pts", "₨": "Rs"}                  # currency signs that are letters set as a word
ALIAS = {"\u212a": "K", "\u212b": "\u00c5"}                   # U+212A U+212B: copies of the letters (_late)
OMEGA, GREEK_OMEGA = "\u2126", "\u03a9"                  # U+2126 ohm sign, U+03A9 Greek capital omega
SUPF, SUBF = set("⁰¹²³⁴⁵⁶⁷⁸⁹"), set("₀₁₂₃₄₅₆₇₈₉")
LOG = {}


def _grid(p, g=0.1):
    """p with every point on the g grid (the data's precision), simplified. Outlines straight out of a scale and a
    reweigh carry points a hair apart that make skia's stroker fail when punct_kern dilates them (ₕ ₙ at 200)."""
    from fontTools.pens.roundingPen import RoundingPen
    q = pathops.Path()
    p.draw(RoundingPen(q.getPen(), roundFunc=lambda v: round(v / g) * g))
    q.simplify()
    return q


def _col_ivs(p, x):
    """Ink intervals of p on the vertical line x."""
    band = _inter(p, _rect(x - 0.5, -1e4, x + 0.5, 1e4))
    return sorted((c.bounds[1], c.bounds[3]) for c in band.contours)


def _poly(pts):
    q = pathops.Path(); q.moveTo(*pts[0])
    for pt in pts[1:]:
        q.lineTo(*pt)
    q.close()
    return q


def _erase_bar(p, y0, y1, d):
    """p without the horizontal bar between y0 and y1: the band y0 - d .. y1 + d is cut out and the strokes that cross
    it are drawn straight from the rows just below to just above (their intervals paired in order)."""
    lo, hi = y0 - d, y1 + d
    a, b = slice_ivs(p, lo), slice_ivs(p, hi)
    if not a or len(a) != len(b):
        return None
    out = _diff(p, _rect(-1e4, lo, 1e4, hi))
    for (a0, a1), (b0, b1) in zip(a, b):
        out = _union(out, _poly([(a0, lo - 0.6), (a1, lo - 0.6), (b1, hi + 0.6), (b0, hi + 0.6)]))
    out.simplify()
    return out


def _erased(p, y_lo, y_hi, wides, ds, count=None, name="?"):
    """(p without its bar, the bar's rows): the first bar width in wides that finds a bar and the first cut margin in ds
    that pairs the strokes above and below it. A glyph that finds none stops the build (₤ once dropped out of one weight
    unnoticed, at S 139, where the pairing failed)."""
    for wide in wides:
        rows = _bar_rows(p, y_lo, y_hi, wide, count)
        if not rows: continue
        for d in ds:
            er = _erase_bar(p, min(rows), max(rows), d)
            if er is not None:
                return er, rows
    raise RuntimeError(f"sym_numeric: {name}: no bar to take out")


def _bar_rows(p, y_lo, y_hi, wide, count=None):
    """Rows (2-unit steps) between y_lo and y_hi where a single interval is wider than `wide` (a bar)."""
    rows = []
    for y in range(int(y_lo), int(y_hi), 2):
        iv = slice_ivs(p, y + 0.5)
        if iv and max(b - a for a, b in iv) > wide and (count is None or len(iv) == count):
            rows.append(y + 0.5)
    return rows


WHITE_K = 0.4       # S: the narrowest counter a mark leaves in a letter (₦ ₭ …); the build's floor is build_font's COUNTER_MIN (0.35 S)


def _steps(a, b, n=6):
    """a down to b in n equal steps (a first)."""
    return [a + (b - a) * i / n for i in range(n + 1)] if a > b else [a]


def _keep_whites(cands, draw, n_holes, S, name):
    """The first candidate whose drawing has n_holes counters (a number, or one per candidate: [(c, n), ...]), each at
    least WHITE_K S wide (else the one whose narrowest counter is widest)."""
    from geom import counters
    best = None
    for c in cands:
        c, n = c if n_holes is None else (c, n_holes)
        p = draw(c); cs = counters(p)
        w = min((d for d, _ in cs), default=0.0) if len(cs) == n else -1.0
        if w >= WHITE_K * S:
            LOG[name] = c; return p
        if best is None or w > best[0]:
            best = (w, p, c)
    LOG[name] = ("widest", best[2], round(best[0] / S, 2))
    return best[1]


def apply_sym_numeric(G, ns):
    M = ST["M"]; B = ST["before"]
    S, XH, XO, CAP, OSH = (M[k] for k in ("S", "XH", "XO", "CAP", "OSH"))
    P = sym_pens(M); LIGHT, DENSE = P["SUP"], P["DENSE"]
    SV, SH = M["PEN"]; FR = M["FR"]
    K = K_SUP
    PW = 0.9 * XH
    gap_eq = max(0.75 * S, 0.16 * PW)             # the = sign's white
    dq = (LIGHT[1] + gap_eq) / 2                  # half the centre distance of two LIGHT bars at that white
    WS = sym_white(M)
    E = EXT * CAP
    # the superior pen: the references' median (Inter, Pretendard, Noto Sans KR; ¹ ÷ 1, ¹ ÷ H and ⁸ ÷ 8 strokes:
    # 0.872 at 400, 0.749 at 700), a line in S, at most the stem: 0.99 S at 100, 0.87 at 400, 0.75 at 700, 0.67 at 900
    # (LIGHT: 0.96 · 0.86 · 0.75 · 0.71)
    k_sup = min(1.0, SUP_REF[0] + SUP_REF[1] * (S - 62))
    SUPPEN = (k_sup * S, k_sup * S * LIGHT[1] / LIGHT[0])
    RX = (SUPPEN[0] - K * S) / 2
    PIN_R = ns["PIN_R"]
    out = {}

    def sides(ch):
        g = G[ch]; b = g["p"].bounds
        return b[0], g["adv"] - b[2]

    def mean_sb(ch):
        l, r = sides(ch); return (l + r) / 2

    def placed(p, lsb, rsb=None):
        b = p.bounds; rsb = lsb if rsb is None else rsb
        return {"p": _xf(p, e=lsb - b[0]), "adv": round(b[2] - b[0] + lsb + rsb), "pins": []}

    def on_box(lb, lsb, rsb, p):
        """A letter (ink box lb, side bearings lsb rsb) with marks: the letter keeps its place; a mark reaching past its
        ink uses up to 1 - SB_KEEP of the side bearing on that side, beyond that the glyph widens; a bar end never comes
        closer to the edge than T's bar ends (unless the letter itself does)."""
        b = p.bounds
        el, er = max(0.0, lb[0] - b[0]), max(0.0, b[2] - lb[2])
        nl = max(lsb - el, SB_KEEP * lsb, min(lsb, SB_T))
        nr = max(rsb - er, SB_KEEP * rsb, min(rsb, SB_T))
        return {"p": _xf(p, e=nl - b[0]), "adv": round(b[2] - b[0] + nl + nr), "pins": []}

    SB_T = mean_sb("T")

    def on_letter(letter, p):
        lb = G[letter]["p"].bounds
        return on_box(lb, *sides(letter), p)

    def bar(x0, x1, y, pen=LIGHT):
        """A horizontal bar whose ink runs from x0 to x1."""
        return pen_line([(x0 + pen[0] / 2, y), (x1 - pen[0] / 2, y)], *pen)

    # ================================================================ superiors and inferiors
    def superior(p, adv):
        """The one superior map: scale K, reweigh to LIGHT, a flat cap-height top stays on the cap height."""
        q = _xf(p, K, 0, 0, K, 0, 0)
        q, ry = _reweigh(M, q, K, SUPPEN)
        rx = RX if ry else 0.0
        return _xf(q, e=rx, f=CAP * (1 - K) - ry), K * adv + 2 * rx

    one, _ = superior(G["1"]["p"], G["1"]["adv"])
    BSUP = one.bounds[1]                          # the superior baseline (0.42 CAP - 2 ry)
    BSUB = -SUB_DROP * CAP
    DSUB = BSUB - BSUP

    def sup_glyph(src):
        if src == "1" and "1" in PNUM:            # ¹ ₁: the proportional 1 (the tabular cell's white made x₁ read x 1)
            adv1, dx1 = PNUM["1"]
            return superior(_xf(G["1"]["p"], e=-dx1), adv1)
        if src in "ij":                           # stem + the pin at the superior scale, as ink
            stem, adv = superior(G[src]["p"], G[src]["adv"])
            (px, py), = G[src]["pins"]
            white = py - PIN_R - G[src]["p"].bounds[3]           # the letter's own white, pin to the stem's top
            r = K * PIN_R + RX
            top = stem.bounds[3]
            return _union(stem, _circle(K * px + RX, top + K * white + r, r)), adv
        return superior(G[src]["p"], G[src]["adv"])

    # the signs and brackets grow by the pen (their ink is heavier than the scaled cell) and crowded their neighbours,
    # the more the heavier (0.6-0.87 of the references' white): SIGN_SB a side, 0.25 S up to 400, 0.35 S at 900
    sign_sb = S * (0.25 + 0.10 * max(0.0, min(1.0, (S - 62.1) / (136.5 - 62.1))))
    PNUM = ns.get("PNUM", {})
    SUPG = {}
    for ch, src in SUPS.items():
        if src in G:
            p, adv = sup_glyph(src)
            SUPG[src] = (p, adv)
            # = + − carry op_cell's white already (0.7 of o's side, scaled); the hook of ʲ stays right of the origin
            e = sign_sb if src in "()" else max(0.0, sign_sb - K * 0.7 * M["O_SIDE"]) if src in "=+−" else 0.0
            e = max(e, -p.bounds[0])
            out[ch] = {"p": _xf(p, e=e, f=SUP_LIFT * CAP), "adv": round(adv + 2 * e), "pins": []}
    for ch, src in SUBS.items():
        if src in G:
            p, adv = SUPG.get(src) or sup_glyph(src)
            SUPG[src] = (p, adv)
            e = sign_sb if src in "()" else max(0.0, sign_sb - K * 0.7 * M["O_SIDE"]) if src in "=+−" else 0.0
            e = max(e, -p.bounds[0])
            out[ch] = {"p": _xf(p, e=e, f=DSUB), "adv": round(adv + 2 * e), "pins": []}

    # ================================================================ fractions
    run = (CAP - LIGHT[1]) * math.tan(math.radians(24))
    slash = pen_line([(0, LIGHT[1] / 2), (run, CAP - LIGHT[1] / 2)], *LIGHT)
    PKERN0 = ns.get("PROOF", {}).get("pkern", {})

    def figures(s):
        """Full-size ink of a figure string set with the proportional widths (one figure: the glyph itself)."""
        if len(s) == 1:
            return G[s]["p"]
        q, x = pathops.Path(), 0.0
        for i, d in enumerate(s):
            adv, dx = PNUM.get(d, [G[d]["adv"], 0])
            if i:
                x += round(PKERN0.get(s[i - 1] + d, 0) * S / 120)
            q = _union(q, _xf(G[d]["p"], e=x - dx))
            x += adv
        return q

    def part(s, where):
        """Numerator ("num": top on the cap height) or denominator ("den": on the baseline) at the superior size."""
        if s.isdigit():
            q, _ = superior(figures(s), 0)
            return q if where == "num" else _xf(q, f=-BSUP)
        q = _xf(G[s]["p"], K, 0, 0, K, 0, 0)          # letters: ª's rule on top, the baseline below
        q, ry = _reweigh(M, q, K, SUPPEN)
        return _xf(q, f=CAP - K * XH - ry) if where == "num" else _xf(q, f=ry)

    src_half = B.get("½") or G["½"]
    hb = src_half["p"].bounds; sb_half = (hb[0] + src_half["adv"] - hb[2]) / 2
    for ch, (n, d) in FRACS.items():
        if not all(c in G for c in n + d):
            continue
        num = part(n, "num"); nb = num.bounds
        num = _xf(num, e=-nb[2])
        xn = _slide(slash, num, WS, -run - 2 * S, run + S, +1)
        parts = [_xf(num, e=xn), slash]
        if d:
            den = part(d, "den"); db = den.bounds
            den = _xf(den, e=-db[0])
            xd = _slide(slash, den, WS, -run, 2 * run + 2 * S, -1)
            parts.append(_xf(den, e=xd))
        out[ch] = placed(_union(*parts), sb_half)

    # ================================================================ letterlike
    # ℉ ℃ : the degree ring and the letter as set (the ring's own advance, no kerning)
    for ch, l in (("℉", "F"), ("℃", "C")):
        dg = G["°"]
        out[ch] = {"p": _union(dg["p"], _xf(G[l]["p"], e=dg["adv"])), "adv": round(dg["adv"] + G[l]["adv"]), "pins": []}

    # ℗ : ©'s rule — a ring of O's height and the letter at 0.46 of it, one LIGHT pen for both
    if "©" in G:
        Ht = M["O_T"] - M["O_B"]; cy = (M["O_T"] + M["O_B"]) / 2
        ring = pen_line(ell_pts(0, cy, (Ht - LIGHT[0]) / 2, (Ht - LIGHT[1]) / 2, 0, 360, 96), *LIGHT)
        k = 0.46 * Ht / CAP
        q, _ = _reweigh(M, _xf(G["P"]["p"], k, 0, 0, k, 0, 0), k, LIGHT)
        b = q.bounds
        q = _xf(q, e=-(b[0] + b[2]) / 2 + 0.02 * Ht, f=cy - (b[1] + b[3]) / 2)
        out["℗"] = placed(_union(ring, q), mean_sb("©"))
    # ℠ : ™'s rule with S and M
    if "™" in G:
        s_, _ = superior(G["S"]["p"], 0); m_, _ = superior(G["M"]["p"], 0)
        w0 = (G["S"]["adv"] - G["S"]["p"].bounds[2]) + G["M"]["p"].bounds[0]
        white = max(0.6 * LIGHT[0], K * w0)
        m_ = _xf(m_, e=s_.bounds[2] + white - m_.bounds[0])
        out["℠"] = placed(_union(s_, m_), mean_sb("™"))

    def parent_sb(ch, fallback):
        """Quicksand's own mean side bearing for a glyph it draws (ℓ ℮ Ω), else the fallback letter's."""
        cmap, hmtx = ns["cmap"], ns["hmtx"]
        if ord(ch) in cmap:
            b = ns["gpath"](ch).bounds; adv = hmtx[cmap[ord(ch)]][0]
            sb = (b[0] + adv - b[2]) / 2
            if sb > 0.3 * mean_sb(fallback):
                return sb
        return mean_sb(fallback)

    # ℓ : a looped l with the family pen, the ascender tall, 0.87 of n's ink wide: a lead-in from the left rises across
    #     the stem to the loop's right side, over the top and down the stem, which turns right into a tail
    ASC = M["ASC"]
    nb = G["n"]["p"].bounds
    w = max(0.87 * (nb[2] - nb[0]) - SV, (SV + 0.7 * S) / 0.62)    # the loop keeps 0.7 S of counter at 900
    xl = SV / 2; xr = xl + w
    xs = xl + 0.30 * w; xR = xs + max(0.44 * w, SV + 0.7 * S)
    yt = ASC - SH / 2; yl = 0.56 * ASC; yA = 0.30 * ASC
    la, lb = (xR - xs) / 2, yt - yl
    A = (xl, yA); R = (xR, yl)
    lead = bez_pts(A, (xl + 0.55 * (xR - xl), yA + 0.05 * (yl - yA)), (xR, yl - 0.55 * (yl - yA)), R)
    loop = ell_pts((xs + xR) / 2, yl, la, lb, 0, 180, 40)
    yb1 = 0.34 * XH; Bt = (xs + 0.48 * (xr - xs), SH / 2 - OSH); Z = (xr, 0.26 * XH)
    tail = _chain([(xs, yl), (xs, yb1)], bez_pts((xs, yb1), (xs, yb1 - 0.62 * (yb1 - Bt[1])), (Bt[0] - 0.40 * (Bt[0] - xs), Bt[1]), Bt),
                  bez_pts(Bt, (Bt[0] + 0.40 * (xr - Bt[0]), Bt[1]), (xr, Z[1] - 0.55 * (Z[1] - Bt[1])), Z))
    ell_l = round_joins(pen_line(_chain(lead, loop, tail), SV, SH), 0.5 * FR)
    out["ℓ"] = placed(ell_l, parent_sb("ℓ", "l"))

    # ℮ : o's box, 1.04 of o's width; a bar across the whole middle and the ring from its right end round to 318°;
    #     three strokes stacked in o's height (ring, bar, ring): the DENSE pen, as & # « »
    DV, DH = DENSE
    #     the ring's end keeps WHITE_K S from the bar's end and more than the round joins can bridge (2 FR): the aperture
    #     narrows as the pen grows (95 at 400, 63 at 700, 52 at 900, where the joins shut it into a second counter), so
    #     from 318° the ring ends earlier where it would be narrower
    from geom import shape as _shape
    ob = G["o"]["p"].bounds; We = 1.04 * (ob[2] - ob[0])
    a_, b_ = (We - DV) / 2, (ob[3] - ob[1] - DH) / 2; cx_, cy_ = We / 2, (ob[1] + ob[3]) / 2
    est_bar = _union(pen_line([(cx_ - a_, cy_), (cx_ + a_, cy_)], DV, DH), pen_line(ell_pts(cx_, cy_, a_, b_, 0, 15, 8), DV, DH))
    t_end = 318.0
    while t_end > 290 and _shape(pen_line(ell_pts(cx_, cy_, a_, b_, t_end - 25, t_end, 12), DV, DH)).distance(_shape(est_bar)) < max(WHITE_K * S, 2 * FR + 1):
        t_end -= 1.0
    LOG["℮"] = t_end
    est = _union(pen_line([(cx_ - a_, cy_), (cx_ + a_, cy_)], DV, DH), pen_line(ell_pts(cx_, cy_, a_, b_, 0, t_end, 72), DV, DH))
    out["℮"] = placed(round_joins(est, FR), parent_sb("℮", "o"))

    # Ω (U+2126): the Greek capital Ω where tools/greek.py builds it — copied in _late, after the kerning, and kerning as
    #     it; without it drawn here on O's box with the family pen: the bowl round from 240° to -60°, the legs turning down
    #     to the baseline and flat feet out to the bowl's width
    if (Path(__file__).resolve().parent / "greek.py").exists():
        LOG["Ω"] = "the Greek Ω (alias)"
    else:
        Wo = 0.94 * M["O_W"]; xl, xr = SV / 2, Wo - SV / 2
        yt = M["O_T"] - SH / 2; yb = SH / 2
        a_ = (xr - xl) / 2 * 0.96; cx_ = Wo / 2
        b_ = (yt - 0.26 * CAP) / (1 + math.sin(math.radians(60))); cy_ = yt - b_
        bowl = ell_pts(cx_, cy_, a_, b_, -60, 240, 90)
        strokes = [bowl]
        for side, t in ((1, -60), (-1, 240)):
            P0 = (cx_ + a_ * math.cos(math.radians(t)), cy_ + b_ * math.sin(math.radians(t)))
            xf_ = cx_ + side * 0.46 * a_
            leg = bez_pts(P0, (P0[0] - side * 0.10 * a_, P0[1] - 0.35 * (P0[1] - yb)), (xf_, yb + 0.30 * (P0[1] - yb)), (xf_, yb))
            foot = [(xf_, yb), (xr if side > 0 else xl, yb)]
            strokes.append(_chain(leg, foot))
        om = round_joins(_union(*[pen_line(s_, SV, SH) for s_ in strokes]), FR)
        out[OMEGA] = placed(om, parent_sb(OMEGA, "O"))
        LOG["Ω"] = "drawn here (no Greek Ω in this tree)"

    # ================================================================ currency on a letter
    def through(x, pen=LIGHT, slant=0.0, y0=-E, y1=CAP + E):
        """A stroke through a capital from y0 to y1 (ink), leaning `slant` degrees from vertical about the middle."""
        t = math.tan(math.radians(slant)); ym = CAP / 2
        a, b = (x + t * (y0 + pen[1] / 2 - ym), y0 + pen[1] / 2), (x + t * (y1 - pen[1] / 2 - ym), y1 - pen[1] / 2)
        return pen_line([a, b], *pen)

    def mid_x(p):
        b = p.bounds; return (b[0] + b[2]) / 2

    def stem_of(p, y):
        """The leftmost ink interval at height y (a capital's stem)."""
        return slice_ivs(p, y)[0]

    # ₡ : C with two strokes at the / slant (20°) through its middle, the = sign's white apart; the pair moves right where
    #     the left one would come closer than WS to the C's inner side (800-900: that white closed)
    c = G["C"]["p"]; cb = c.bounds; Cw = cb[2] - cb[0]; cx = mid_x(c) + 0.02 * Cw
    c_in = slice_ivs(c, CAP / 2)[0][1]                        # the C's inner left side at mid-height

    def colon_(a):
        g, th = a; pen = (th, th * LIGHT[1] / LIGHT[0])
        hx = (pen[0] + g) / 2 / math.cos(math.radians(20))
        cx2 = max(cx, c_in + WS + pen[0] / 2 + hx)
        return round_joins(_union(c, through(cx2 - hx, pen, slant=20), through(cx2 + hx, pen, slant=20)), 0.5 * FR)
    # the whites between the strokes and the C stay WHITE_K S: where they would close (S 150 and up) the strokes draw
    # lighter and closer, as ₦'s bars
    out["₡"] = on_letter("C", _keep_whites([(g, th) for th in _steps(LIGHT[0], 0.5 * S) for g in _steps(gap_eq, WHITE_K * S)],
                                           colon_, 2, S, "₡"))
    # ₵ : C with one upright stroke through its middle
    out["₵"] = on_letter("C", round_joins(_union(c, through(cx)), 0.5 * FR))
    # ₲ : G with one upright stroke through its middle — or through the left end of G's bar where that starts right of
    #     the middle (100-200), so the stroke always meets the bar
    g_ = G["G"]["p"]; gx = mid_x(g_) + 0.02 * (g_.bounds[2] - g_.bounds[0])
    gbar = [iv[-1][0] for y in range(int(0.25 * CAP), int(0.60 * CAP), 2) for iv in [slice_ivs(g_, y + 0.5)]
            if len(iv) >= 2 and iv[-1][1] - iv[-1][0] > 2.5 * S]
    if gbar:
        gx = max(gx, min(gbar) + LIGHT[0] / 2)
    out["₲"] = on_letter("G", round_joins(_union(g_, through(gx)), 0.5 * FR))
    # ₿ : B with two short strokes out of its top and bottom (not through it), the = sign's white apart, centred on
    #     the upper bowl's middle
    b_p = G["B"]["p"]; st = stem_of(b_p, 0.25 * CAP)
    bx = (st[0] + slice_ivs(b_p, 0.75 * CAP)[-1][1]) / 2
    ticks = []
    for x in (bx - (LIGHT[0] + gap_eq) / 2, bx + (LIGHT[0] + gap_eq) / 2):
        ticks += [pen_line([(x, CAP - SH / 2), (x, CAP + E - LIGHT[1] / 2)], *LIGHT), pen_line([(x, -E + LIGHT[1] / 2), (x, SH / 2)], *LIGHT)]
    out["₿"] = on_letter("B", round_joins(_union(b_p, *ticks), 0.5 * FR))
    # ₦ : N with two LIGHT bars across its middle, 0.08 W past both stems. The bars cut N's whites into four counters:
    #     two between the bars, and the two corners of N's crotches (above the upper bar at the top left, below the lower
    #     one at the bottom right). All four stay at least WHITE_K S wide at every weight: where the = sign's spacing and
    #     the LIGHT pen would close a corner (the crotches fill in as N gets heavier, 600-900) the bars move together
    #     (their white down to WHITE_K S) and then draw lighter (down to 0.5 S)
    n_ = G["N"]["p"]; nbx = n_.bounds; Nw = nbx[2] - nbx[0]

    def naira(g, th):
        pen = (LIGHT[0] * th / LIGHT[1], th); d_ = (th + g) / 2
        return round_joins(_union(n_, bar(nbx[0] - 0.08 * Nw, nbx[2] + 0.08 * Nw, CAP / 2 - d_, pen),
                                  bar(nbx[0] - 0.08 * Nw, nbx[2] + 0.08 * Nw, CAP / 2 + d_, pen)), 0.5 * FR)
    # where no spacing keeps the corners WHITE_K S wide (N's crotches fill in as it gets heavier: 700-900), each bar
    #     stops where it would shut a corner — the upper one at the left stem and again at the diagonal, the lower one at
    #     the diagonal and again at the right stem — so each corner white runs on into the white between the bars
    #     instead of closing into a speck or a knot; one of the audit's allowed topology steps
    def naira_open(g, th):
        pen = (LIGHT[0] * th / LIGHT[1], th); d_ = (th + g) / 2; x0, x1 = nbx[0] - 0.08 * Nw, nbx[2] + 0.08 * Nw
        yu, yl = CAP / 2 + d_, CAP / 2 - d_
        iu, il = slice_ivs(n_, yu), slice_ivs(n_, yl)
        if len(iu) < 3 or len(il) < 3:
            return naira(g, th)
        mid = lambda iv: (iv[0] + iv[1]) / 2
        parts = [bar(x0, mid(iu[0]) + pen[0] / 2, yu, pen), bar(mid(iu[1]) - pen[0] / 2, x1, yu, pen),
                 bar(x0, mid(il[1]) + pen[0] / 2, yl, pen), bar(mid(il[-1]) - pen[0] / 2, x1, yl, pen)]
        return round_joins(_union(n_, *parts), 0.5 * FR)
    two = [((g, th, 0), 4) for th in _steps(LIGHT[1], 0.5 * S) for g in _steps(gap_eq, WHITE_K * S)]
    out["₦"] = on_letter("N", _keep_whites(two + [((gap_eq, LIGHT[1], 1), 2)],
                                           lambda a: naira_open(a[0], a[1]) if a[2] else naira(a[0], a[1]), None, S, "₦"))
    # ₱ ₽ : P; ₱ two bars across the bowl, 0.10 W left of the stem to 0.04 W past the bowl;
    #       ₽ one bar under the bowl (the = sign's white below it), from 0.10 W left of the stem to 0.62 W
    p_ = G["P"]["p"]; pb = p_.bounds; Pw = pb[2] - pb[0]; pst = stem_of(p_, 0.2 * CAP)
    bowl_lo = _inter(p_, _rect(pst[1] + 2, -1e4, 1e4, 1e4)).bounds[1]
    pcol = _col_ivs(p_, pst[1] + 0.5 * (pb[2] - pst[1]))       # the bowl's two strokes, crossed at mid-bowl
    c0, c1 = pcol[0][1], pcol[-1][0]                           # the counter
    # the two bars cut the counter into three equal whites; four strokes stack across the bowl, so where the whites would
    # close (under 2 × the round-join radius + 0.1 S: 800-900) the bars draw lighter instead, the DENSE rule
    # and where two LIGHT bars cannot leave three whites of WHITE_K S (the bowl's counter shrinks as P gets heavier:
    # 700-900), one bar as heavy as the stem crosses the middle of the bowl instead (as heavy as the room leaves), so the
    # mark keeps its weight — an allowed topology step of the audit
    def peso(a):
        n, hb_ = a; pen_b = (hb_ / kc_, hb_)
        wh = (c1 - c0 - n * hb_) / (n + 1)
        ys_ = [c0 + wh * (i + 1) + hb_ * (i + 0.5) for i in range(n)]
        return round_joins(_union(p_, *[bar(pb[0] - 0.10 * Pw, pb[2] + 0.04 * Pw, y, pen_b) for y in ys_]), 0.5 * FR)
    kc_ = LIGHT[1] / LIGHT[0]
    wmin = max(FR + 0.1 * S, WHITE_K * S)
    h1 = min(SH, c1 - c0 - 2 * wmin)
    out["₱"] = on_letter("P", _keep_whites([((2, LIGHT[1]), 3)] + [((1, h1), 2)], peso, None, S, "₱"))
    out["₽"] = on_letter("P", round_joins(_union(p_, bar(pb[0] - 0.10 * Pw, pb[0] + 0.62 * Pw, bowl_lo - gap_eq - LIGHT[1] / 2)), 0.5 * FR))
    # ₣ : F with one bar across its stem, the = sign's white under the middle arm, 0.20 W either side of the stem
    f_ = G["F"]["p"]; fb = f_.bounds; Fw = fb[2] - fb[0]; fst = stem_of(f_, 0.2 * CAP)
    arm = [iv for iv in _col_ivs(f_, fst[1] + 0.5 * S) if iv[1] < 0.8 * CAP]
    if arm:
        yf = arm[0][0] - gap_eq - LIGHT[1] / 2; fc = (fst[0] + fst[1]) / 2
        out["₣"] = on_letter("F", round_joins(_union(f_, bar(fc - 0.20 * Fw - (fst[1] - fst[0]) / 2, fc + 0.20 * Fw + (fst[1] - fst[0]) / 2, yf)), 0.5 * FR))
    # ₭ : K with one bar across the stem and the arm just above the fork where limn's leg leaves the arm (the
    #     references' bar through the junction), the = sign's half white over the fork, from 0.09 W left of the stem to
    #     0.80 W (open white right of the arm). The white between stem and arm under it is one counter at every weight
    #     (at 800-900 the bar rises until it is); a bar on the fork or lower cut specks out of the crotches
    k_ = G["K"]["p"]; kb = k_.bounds; Kw = kb[2] - kb[0]
    ym = next((y + 0.5 for y in range(int(0.30 * CAP), int(0.80 * CAP), 2)
               if len(slice_ivs(k_, y + 0.5)) == 2 and len(slice_ivs(k_, y - 1.5)) == 3), 0.55 * CAP)
    yk = ym + LIGHT[1] / 2 + 0.5 * gap_eq
    kbar = lambda y: round_joins(_union(k_, bar(kb[0] - 0.09 * Kw, kb[0] + 0.80 * Kw, y)), 0.5 * FR)
    ys = [yk + 2 * i for i in range(int((0.80 * CAP - yk) / 2) + 1)]
    out["₭"] = on_letter("K", _keep_whites(ys, kbar, 1, S, "₭"))
    # ₮ : T with the = sign's two strokes across its stem at 0.40 CAP, rising 20° to the right, 0.44 W long
    t_ = G["T"]["p"]; tb = t_.bounds; Tw = tb[2] - tb[0]; tst = stem_of(t_, 0.2 * CAP); tc = (tst[0] + tst[1]) / 2
    L2 = 0.22 * Tw; sl = math.tan(math.radians(20))
    dqs = dq / math.cos(math.radians(20))
    slants = [pen_line([(tc - L2, y0 - L2 * sl), (tc + L2, y0 + L2 * sl)], *LIGHT) for y0 in (0.40 * CAP - dqs, 0.40 * CAP + dqs)]
    out["₮"] = on_letter("T", round_joins(_union(t_, *slants), 0.5 * FR))
    # ₸ : T with its top bar doubled: the bar copied the = sign's white below itself, the stem hanging from the lower one
    tby0 = _col_ivs(t_, tb[0] + 0.1 * Tw)[-1][0]            # bottom of the bar (at the left arm, clear of the stem)
    ttop = _inter(t_, _rect(-1e4, tby0, 1e4, 1e4)); thb = ttop.bounds
    tlow = _xf(ttop, f=-(thb[3] - thb[1]) - gap_eq)           # the copy, the = sign's white under the bar
    tstem = _inter(t_, _rect(-1e4, -1e4, 1e4, tlow.bounds[1] + 1))
    tenge = _union(ttop, tlow, tstem)
    out["₸"] = on_letter("T", round_joins(tenge, FR))
    # ₤ : £ with its bar taken out and the = sign's two LIGHT bars in its place (as € ¥)
    lp = G["£"]["p"]
    er, rows = _erased(lp, 0.2 * CAP, 0.7 * CAP, [2.2 * S, 1.9 * S, 1.6 * S], [0.25 * S, 0.35 * S, 0.15 * S, 0.45 * S, 0.55 * S], name="₤")
    xs_ = [x for y in rows for iv in slice_ivs(lp, y) for x in iv]
    y_ = (min(rows) + max(rows)) / 2
    out["₤"] = on_letter("£", round_joins(_union(er, bar(min(xs_), max(xs_), y_ - dq), bar(min(xs_), max(xs_), y_ + dq)), 0.5 * FR))
    # ₳ : A with its crossbar taken out and the = sign's two bars across, 0.06 W past the legs
    a_p = G["A"]["p"]; ab_ = a_p.bounds; Aw = ab_[2] - ab_[0]
    er, rows = _erased(a_p, 0.05 * CAP, 0.65 * CAP, [2.5 * S, 2.1 * S, 1.8 * S], [0.3 * S, 0.4 * S, 0.2 * S, 0.5 * S], 1, name="₳")
    y_ = (min(rows) + max(rows)) / 2 + 0.04 * CAP

    def austral(a):
        g, th, dy = a; pen = (LIGHT[0] * th / LIGHT[1], th); d_ = (th + g) / 2; yc = y_ - dy
        return round_joins(_union(er, bar(ab_[0] - 0.02 * Aw, ab_[2] + 0.02 * Aw, yc - d_, pen),
                                  bar(ab_[0] - 0.02 * Aw, ab_[2] + 0.02 * Aw, yc + d_, pen)), 0.5 * FR)
    # A's counter over the bars and the white between them stay WHITE_K S: where the apex fills in (S 150 and up) the bars
    # draw lighter and closer, then move down
    out["₳"] = on_letter("A", _keep_whites([(g, th, dy) for dy in (0.0, 0.03 * CAP, 0.06 * CAP) for th in _steps(LIGHT[1], 0.5 * S, 3)
                                            for g in _steps(gap_eq, WHITE_K * S, 3)], austral, 2, S, "₳"))
    # ₴ : S turned over left to right (the hryvnia's reversed S) and the = sign's two bars across its middle
    s_p = G["S"]["p"]; sbx = s_p.bounds
    rs = _xf(s_p, -1, 0, 0, 1, sbx[0] + sbx[2], 0); Sw = sbx[2] - sbx[0]; ysm = (sbx[1] + sbx[3]) / 2
    # where a bar would reach the turned S's terminal and close a white (900), its end on that side (the lower bar's
    # right, the upper bar's left: the terminals' corners) draws back until it keeps half the = sign's white
    # the bars cross the spine at a sharp angle, so their joins are not closed round (as Ł's slash is not): the closing
    # filled the wedges between bar and spine into a knot 2.1 S across at 700
    x0s, x1s = sbx[0] - 0.04 * Sw, sbx[2] + 0.04 * Sw
    cut = 0.0
    while cut < 0.4 * Sw:
        hr = _union(rs, bar(x0s, x1s - cut, ysm - dq), bar(x0s + cut, x1s, ysm + dq))
        if len(list(hr.contours)) == len(list(rs.contours)):
            break
        cut += 0.02 * Sw
    if cut:
        cut += 0.5 * gap_eq
        hr = _union(rs, bar(x0s, x1s - cut, ysm - dq), bar(x0s + cut, x1s, ysm + dq))
    ls_, rs_ = sides("S")
    hr = round_joins(hr, 3.0)                              # only the slits at the tips of the acute wedges (under 6 units)
    out["₴"] = on_box(sbx, rs_, ls_, hr)                    # turned over: the sides swap
    # ₥ : m with a stroke at the / slant through it, 0.13 CAP past the baseline and the round x-height
    m_p = G["m"]["p"]; mx = mid_x(m_p)
    out["₥"] = on_letter("m", round_joins(_union(m_p, through(mx, slant=20, y0=-E, y1=XO + E)), 0.5 * FR))

    # ================================================================ currency drawn on the metrics
    # ₹ : a headline on the cap height, the = sign's white under it a LIGHT bar, both 0.67 CAP wide; the bowl hangs from
    #     the headline's right half down to 0.40 CAP, runs back to the left and turns into the diagonal to the baseline
    Wr = 0.68 * CAP + 0.3 * max(0.0, S - 120); xl, xr = SV / 2, Wr - SV / 2; w = xr - xl
    yt = CAP - SH / 2; y2 = yt - SH / 2 - gap_eq - LIGHT[1] / 2; yb3 = 0.40 * CAP
    x0b = xl + 0.36 * w
    X = x0b + (xr - x0b) / 0.75                             # a cubic with both handles at X reaches xr
    bowl = bez_pts((x0b, yt), (X, yt), (X, yb3), (x0b, yb3))
    rupee = _union(pen_line([(xl, yt), (xr, yt)], SV, SH), bar(xl - SV / 2, xr + SV / 2, y2),
                   pen_line(_chain(bowl, [(x0b, yb3), (xl + 0.04 * w, yb3), (xr - 0.02 * w, SH / 2)]), SV, SH))
    out["₹"] = placed(round_joins(rupee, 0.5 * FR), mean_sb("T"))    # half the radius: the full one shut the bowl's white at 900
    # ₺ : a stem at 0.30 W from the cap height down, turning right along the baseline and up to a round end at 0.40 CAP;
    #     the = sign's two bars across the stem at 0.52 CAP, rising 20°, from the left edge to 0.66 W
    Wt = 0.70 * CAP + 0.3 * max(0.0, S - 120); xl, xr = SV / 2, Wt - SV / 2; w = xr - xl
    xs = xl + 0.30 * w; yb = SH / 2 - OSH
    Bt = (xs + 0.36 * w, yb)
    x0l, x1l = LIGHT[0] / 2, 0.66 * Wt - LIGHT[0] / 2; xm, L2 = (x0l + x1l) / 2, (x1l - x0l) / 2
    bars_l = [pen_line([(xm - L2, y0 - L2 * sl), (xm + L2, y0 + L2 * sl)], *LIGHT) for y0 in (0.52 * CAP - dqs, 0.52 * CAP + dqs)]

    def lira_bowl(ye):
        return pen_line(_chain([(xs, CAP - SV / 2), (xs, 0.32 * CAP)], bez_pts((xs, 0.32 * CAP), (xs, 0.10 * CAP), (Bt[0] - 0.24 * w, yb), Bt),
                               bez_pts(Bt, (Bt[0] + 0.30 * w, yb), (xr, 0.12 * CAP), (xr, ye))), SV, SH)
    # the bowl's round end keeps WHITE_K S from the lower bar and more than the joins can bridge (FR): the bar comes
    # down to it as the pen grows (102 at 400, 55 at 700, 16 at 900, where the joins shut a counter), so from 0.40 CAP
    # the end stands lower where it would be nearer
    from geom import shape as _shape
    ye = 0.40 * CAP
    end_of = lambda ye: _shape(_inter(lira_bowl(ye), _rect(xr - SV, 0.2 * CAP, 1e4, 1e4)))
    while ye > 0.26 * CAP and end_of(ye).distance(_shape(bars_l[0])) < max(WHITE_K * S, FR + 1):
        ye -= 0.005 * CAP
    LOG["₺"] = round(ye / CAP, 3)
    lira = _union(lira_bowl(ye), *bars_l)
    out["₺"] = placed(round_joins(lira, 0.5 * FR), sides("T")[0], sides("c")[1])
    # ₼ : an arch on the baseline 0.74 XH tall, 0.80 CAP wide, and a stem up its middle from 0.30 XH to the x-height
    Wm = 0.80 * CAP + 0.3 * max(0.0, S - 120); xl, xr = SV / 2, Wm - SV / 2
    ya = 0.74 * XH + OSH - SH / 2; ra = (xr - xl) / 2; ca = ya - ra * 0.92
    arch = _chain([(xl, SH / 2), (xl, ca)], ell_pts((xl + xr) / 2, ca, ra, ya - ca, 180, 0, 60), [(xr, ca), (xr, SH / 2)])
    manat = _union(pen_line(arch, SV, SH), pen_line([(Wm / 2, 0.30 * XH), (Wm / 2, XH - SV / 2)], SV, SH))
    out["₼"] = placed(round_joins(manat, FR), sides("n")[0], sides("n")[1])
    # ₾ : a base bar on the baseline 0.83 CAP wide; from its left end a stroke rises to 0.64 CAP, rounds over and down
    #     the right, ending level with the arc's centre (higher where that keeps the = sign's white over the bar); two LIGHT strokes (the = sign's white apart) from inside the arc
    #     up through its top to the cap height
    Wg = 0.83 * CAP + 0.3 * max(0.0, S - 120); xl, xr = SV / 2, Wg - SV / 2
    ya = 0.64 * CAP - SH / 2; xra = xr - 0.04 * (xr - xl); ra = (xra - xl) / 2; rb = min(ra, ya - 0.26 * CAP); cy = ya - rb
    t_end = max(-5.0, math.degrees(math.asin(max(-1.0, min(1.0, (1.5 * SH + gap_eq - cy) / rb)))))   # the end keeps the = white over the bar
    arc = _chain([(xl, SH / 2), (xl, cy)], ell_pts(xl + ra, cy, ra, rb, 180, t_end, 60))
    lari = [pen_line(arc, SV, SH), pen_line([(xl, SH / 2), (xr, SH / 2)], SV, SH)]
    for x in (xl + ra - (LIGHT[0] + gap_eq) / 2, xl + ra + (LIGHT[0] + gap_eq) / 2):
        lari.append(pen_line([(x, ya - 0.10 * CAP), (x, CAP - LIGHT[1] / 2)], *LIGHT))
    out["₾"] = placed(round_joins(_union(*lari), 0.5 * FR), sides("L")[0], sides("L")[1])
    # ₪ : two hooks turned 180° into each other on the x-height — a stem up the left, over the top and down at 2/3 of
    #     the width to 0.36 of the height, and its turned copy; four verticals side by side, so the DENSE pen and a
    #     white of 0.245 XH between them (Inter, Pretendard 1.17-1.44 XH wide at 400-700)
    DV, DH = DENSE; gw = 0.245 * XH
    Wn = 4 * DV + 3 * gw; xl, xr = DV / 2, Wn - DV / 2; yb, yt = DH / 2, XH - DH / 2
    xa = xl + 2 * (DV + gw); ye = yb + 0.36 * (yt - yb)
    hook = [(xl, yb), (xl, yt), (xa, yt), (xa, ye)]
    turned = [(xl + xr - x, yb + yt - y) for x, y in hook]
    out["₪"] = placed(round_joins(_union(pen_line(hook, DV, DH), pen_line(turned, DV, DH)), 0.5 * FR), sides("n")[0], sides("n")[1])

    # ================================================================ into G
    changed = ST["changed"]
    for ch, g in out.items():
        g["p"] = _grid(g["p"])
        G[ch] = g
        changed.add(ch)                           # punct_kern keeps GAP white to every neighbour
    _hook_late(ns)
    f0 = lambda v: f"{v:.0f}"
    LOG.update(BSUP=round(BSUP + SUP_LIFT * CAP, 1), BSUB=round(BSUB, 1), TNS=round(K * ns["TN"] + 2 * RX, 1))
    return [
        ["⁰–⁹ ⁺ ⁻ ⁼ ⁽ ⁾ ⁿ ⁱ ˣ ʲ ᵀ", "위첨자 부류 (한 규칙)", f"limn의 글자를 {K}배 + 위첨자 펜({SUPPEN[0] / S:.2f} S, 참고 서체 3종의 중앙값 — 400 0.87 · 700 0.75)으로 굵기 맞춤, 평평한 윗끝 = 대문자 높이 + {SUP_LIFT} CAP({f0(CAP * (1 + SUP_LIFT))}, Pretendard 높이), 모두 한 기준선 {f0(BSUP + SUP_LIFT * CAP)}. 폭 = {K} × 제 폭 + 펜이 불린 만큼 — 숫자는 고정폭 {f0(K * ns['TN'] + 2 * RX)}, ¹ ₁ 만 비례 1(고정폭 칸의 흰 폭이 x₁을 벌림). ⁽ ⁾ ⁺ ⁻ ⁼ 는 펜이 불린 만큼 양옆 0.25~0.35 S. ⁱ 의 점은 핀 × {K}, i 의 흰 틈 × {K}"],
        ["₀–₉ ₊ ₋ ₌ ₍ ₎ ₐ … ₜ ᵢ", "아래첨자", f"위첨자 그림 그대로, 기준선 {f0(BSUB)}(−{SUB_DROP} CAP: Inter −0.20~−0.21, Pretendard −0.17~−0.19)"],
        ["⅓ ⅔ ⅕ … ⅒ ⅟ ↉ ℅ ℁ ℀", "분수", f"½ 규칙: 분자 = 위첨자, 빗금 24°, 분모 = 같은 크기로 기준선, 흰 틈 WS {f0(WS)}. ⅒ 의 10 은 비례 숫자 폭. 글자 분수는 분자 윗끝 = CAP(ª 규칙)"],
        ["Ⅰ–Ⅻ ⅰ–ⅻ Ⅼ Ⅽ Ⅾ Ⅿ", "로마 숫자", "limn의 I V X L C D M · i v x l c d m 을 낱말처럼(제 폭 + 최종 커닝, ii 는 핀 짝 흰 틈), 핀은 핀 그대로. 커닝은 양 끝 글자의 부류로(Ⅳ = I|V)"],
        ["℉ ℃ ℗ ℠ ℓ ℮ Ω K Å", "글자꼴 기호", f"℉ ℃ = ° + F·C, ℗ = © 규칙(고리 + P 0.46), ℠ = ™ 규칙(S M), ℓ = 고리 l(가족 펜, n 폭 0.87), ℮ = o 상자에 가운데 막대, Ω = {LOG['Ω']}, K Å = 글자 그대로"],
        ["₡ ₵ ₲ ₿ ₦ ₱ ₽ ₣ ₭ ₮ ₸ ₤ ₳ ₴ ₥", "글자 + 막대", f"limn의 글자 + LIGHT 막대(등호의 흰 틈 {f0(gap_eq)}), 글자를 뚫는 획은 ±{EXT} CAP. 막대가 글자 밖으로 나가면 옆 여백을 {1 - SB_KEEP:.2f}까지 쓰되 T의 막대 끝보다 가장자리에 붙지 않음. 표시가 가둔 흰 공간은 모든 굵기에서 유지(₱ 는 고리 속을 셋으로 나누고 닫힐 굵기에서 막대를 가볍게 — DENSE 규칙, ₡ ₲ ₭ ₾ ₴ 는 표시를 옮기거나 줄임). ₤ ₳ 는 제 막대를 빼고 두 줄, ₴ 는 S를 좌우로 뒤집음, ₸ 는 T의 막대를 한 번 더"],
        ["₹ ₺ ₼ ₾ ₪ ₧ ₨ ₫", "치수로 그림", "₹ ₺ ₼ ₾ 는 가족 펜으로 새로(대문자 높이 안), ₪ 는 세로획 넷이 나란해 DENSE 펜, 흰 틈 0.245 XH. ₧ ₨ = Pts·Rs 를 낱말처럼, ₫ = đ + 밑줄(등호의 흰 틈)"],
    ]


# ---------------------------------------------------------------- after the kerning
def _hook_late(ns):
    """Roman numerals, ₧ ₨ (letters as a word) and ₫ (đ + a bar) need the final kerning or the accented letters, which
    build_font makes after this hook: they are composed at the start of accents.kern (run after all of build_font's
    kerning), so their kerning classes are in place when accents.kern maps the base pairs onto the class members."""
    import accents
    if getattr(accents.kern, "_sym_numeric", False):
        return
    kern0 = accents.kern

    def kern(ns2):
        _late(ns2)
        return kern0(ns2)
    kern._sym_numeric = True
    accents.kern = kern


def _late(ns):
    G, KERN, DOTSPEC = ns["G"], ns["KERN"], ns["DOTSPEC"]
    import accents
    cls = accents.ST["cls"]
    M = ST["M"]; S = M["S"]; LIGHT = sym_pens(M)["SUP"]
    gap_eq = max(0.75 * S, 0.16 * 0.9 * M["XH"])

    def word(s):
        p, pins, spec, x = pathops.Path(), [], [], 0.0
        for i, c in enumerate(s):
            if i:
                x += KERN.get(s[i - 1] + c, 0)
            p = _union(p, _xf(G[c]["p"], e=x))
            pins += [(round(px + x, 1), py) for px, py in G[c]["pins"]]
            spec += [[k, round(px + x, 1), y, r] for k, px, y, r in DOTSPEC.get(c, {}).get("pins", [])]
            x += G[c]["adv"]
        return p, round(x), pins, spec
    for ch, s in {**ROMAN, **WORDS}.items():
        if ch in G or not all(c in G for c in s):
            continue
        p, adv, pins, spec = word(s)
        G[ch] = {"p": p, "adv": adv, "pins": pins}
        if spec:
            DOTSPEC[ch] = {"only": False, "adv0": adv, "pins": spec}
        cls[ch] = (s[-1], s[0])                   # as a left glyph its right side is the last letter's
    # the superior and the inferior figures are tabular among themselves: like the full-size figures they do not kern
    # with each other (punct_kern opened ⁰⁰ to GAP, a white the superior cell keeps at K × the full-size one)
    for fig in (SUPF, SUBF):
        for k in [k for k in KERN if len(k) == 2 and k[0] in fig and k[1] in fig]:
            del KERN[k]
    # K Å Ω: copies of K Å and the Greek Ω, kerning through the letter's class (the letter itself where it has none: the
    # engine falls back one level only); Å's ring keeps its clearance to the neighbours (accents' marks)
    for a, b in {**ALIAS, OMEGA: GREEK_OMEGA}.items():
        if a in G or b not in G:
            continue
        G[a] = {"p": pathops.Path(G[b]["p"]), "adv": G[b]["adv"], "pins": list(G[b]["pins"])}
        cls[a] = cls.get(b, (b, b))
        if b in accents.ST["marks"]:
            accents.ST["marks"][a] = accents.ST["marks"][b]; accents.ST["clear"][a] = accents.ST["clear"][b]
            accents.ST["new"].append(a)
        for k in [k for k in KERN if len(k) == 2 and b in k]:
            KERN.setdefault(k.replace(b, a), KERN[k])
    # ₫ : đ with a LIGHT bar under the baseline, the = sign's white below it (as the bar under №'s o)
    if "đ" in G and "₫" not in G:
        d = G["đ"]; b = d["p"].bounds; y = -gap_eq - LIGHT[1] / 2
        under = pen_line([(b[0] + LIGHT[0] / 2, y), (b[2] - LIGHT[0] / 2, y)], *LIGHT)
        G["₫"] = {"p": round_joins(_union(d["p"], under), 0.5 * M["FR"]), "adv": d["adv"], "pins": list(d["pins"])}
        cls["₫"] = cls.get("đ", ("d", "d"))
        # its marks are đ's bar and the bar under it: accents.kern keeps them clear of the neighbours as it does đ's
        # (as d alone it touched ) ] ' " at 700-900)
        mk = pathops.Path(under)
        if "đ" in accents.ST["marks"]:
            mk = _union(mk, accents.ST["marks"]["đ"])
        accents.ST["marks"]["₫"] = mk; accents.ST["clear"]["₫"] = accents.ST["clear"].get("đ", accents.CLEAR_K * accents.ST["GAP"])
        if "₫" not in accents.ST["new"]: accents.ST["new"].append("₫")
