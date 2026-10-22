"""limn accented letters: Latin-1 Supplement, Latin Extended-A and the rest of Google Fonts' GF Latin Core.

Hooked into build_font.py in two places, both reading the build's own namespace (globals()):

  accents.build(globals())   after the base letters are final (feet, fillets, symmetry, side bearings,
                             figures) and before the kerning: adds the glyphs, their pins and DOTSPEC
  accents.kern(globals())    after the kerning is final (Quicksand GPOS + limn fixes + pin clearance):
                             joins ĳ Ĳ ŉ, maps every base pair onto its accented letters, then opens any
                             pair where a mark comes too close to the neighbour

Every accented letter is limn's own base letter (spurless n, the proof side bearings, the symmetric
v w x y z …) plus a mark drawn to limn's rules; nothing is copied from Quicksand's composites except
where a letter has no limn base (ß ẞ Þ þ ĸ Æ æ Œ Ŋ), which takes the parent's shape and then limn's
feet and fillets; ð is drawn on limn's o (see eth()). Bars and slashes (Đ đ Ħ ħ Ŧ ŧ Ł ł Ø ø) are straight round-ended strokes on limn's own
stems: the bars in the currency bars' LIGHT pen and at least the parent's bar length (U+0335), đ ħ in the
ascender above the round x-height with the stem's end showing above the bar, Đ Ŧ at H's bar, Ħ between H's
bar and the cap height, ŧ at half the x-height; the slashes in the parent's bar weight, ł Ł through the stem
at half its height rising 32°, Ø ø corner to corner of the bowl. All sizes are read from the glyphs at build
time, so the module follows whatever weights.py and build_font.py make of the base letters.

The rules (numbers at 700, UPM 1000; s = stem 120, GAP 48, pin r 78.5):

  pins        every dot-like mark is the pin — one size (PIN_R), the size the renderers draw.
              ¨ = two pins, ˙ = one pin, ŀ Ŀ = the middle-dot pin. Two pins keep GAP white between them
              (centres 2 r + GAP = 205 apart, the parent's 199). ï keeps both pins (the diaeresis is
              meaning, not decoration); İ gets a pin.
  mark line   lowercase: every mark stands on XH + GAP = the bottom of the i pin; the pins are the i
              pin (DOTSPEC kind "i", top on the ascender). Round letters (o e a) overshoot into that white
              by OSH, as they do under the x-height line.
              capitals and ascenders (ĺ ĥ): marks stand on top + 0.75 GAP (36) and use the flatter cap
              forms; cap pins are DOTSPEC kind "mid" at that line + r.
              macron and tilde are centred on the pin centre line instead (XH + GAP + r = 661.5).
  strokes     acute grave circumflex caron breve macron tilde double-acute cedilla ogonek: one
              monoline stroke with round ends and round joins. Stroke = ACC_K = 0.87 of the stem at every
              weight (17 at 100, 93 at 700, 119 at 900): a step lighter than the letters, as marks are in the
              references, and following the weight axis with them (the parent's macron ran from 1.6 s at 100
              to 0.68 s at 900). The skeleton is fixed in font units up to 700, as in the parent:
                acute/grave  length 140, 50° (caps 37°); the lower end stands on the optical centre
                circumflex/caron  two arms 138 long at 37° (caps 30°)
                breve  half-ellipse 250 × 84 deep (caps 66)
                macron  255 (caps 265)       tilde  one sine period 308 × 81 (caps 64)
                double acute  two strokes 110 long at 50° (caps 40°), lower ends 180 apart
              (medians of Quicksand, Nunito, M PLUS Rounded 1c, Fredoka at 700-800)
  ring        an annulus as wide as the parent's ring (U+030A at this weight), the marks' stroke, but never more
              than 0.34 of its width, so its counter stays open at 600-900; it stands on the mark line (Å too:
              apart from the apex, like Nunito, Fredoka). Like every mark above it stays under TOP_MAX (955; the
              line box tops at 970): over a capital it shrinks with the strokes' skeleton there (Å Ů 500-900)
  hook        ̉ : a small ? of the marks' stroke; its start keeps a quarter stroke of white from its foot where it
              would only touch it (capitals at 200), or runs into it (capitals from 300)
  below       cedilla: a stub from inside the letter's bottom, turning into a round hook (to −153);
              ogonek: a hook hanging from the right end of the letter's bottom (to −160);
              comma below (ș ț ķ ļ ņ ŗ Ș Ț Ķ Ļ Ņ Ŗ Ģ): limn's own comma, head top GAP under the baseline, and
              never under BOT_MIN (-315, 15 inside the line box as TOP_MAX is): from 700 it rises into that white,
              down to 0.75 GAP, then shortens (900);
              ģ: limn's own turned comma ‘ standing on the mark line
  ď ľ ť Ľ     limn's own ’ at its quote height, GAP of white from the stem (ť: lifted clear of the bar, over
              the x-height, where it hangs over the next letter: ť keeps t's advance)
  centre      optical centre = centre of the ink in the top quarter of the x-height under the mark (the
              stem for i j l h, the arch for n, the apex for A); a and g: the bowl (counter centre).
              Bottom marks: centre of the ink in the bottom fifth.
  i j         the dotless stem; the mark replaces the pin
  spacing     every accented letter keeps its base letter's advance, and its kerning: é takes e's pairs
              (ď ľ ť take ’'s on their right, ĳ i|j, œ o|e …), each pair from the nearest base pair (one side
              through its class before both: Ύδ is Yδ, not Y|o). Then the mark is measured against every
              neighbour on the real outlines; a pair whose mark comes closer than PIN_CLEAR (pins) or
              1.25 GAP (strokes) is opened by the shortfall.
"""
import math
import unicodedata

import pathops

TOP = {0x300: "grave", 0x301: "acute", 0x302: "circumflex", 0x303: "tilde", 0x304: "macron", 0x306: "breve",
       0x307: "dot", 0x308: "dieresis", 0x309: "hook", 0x30A: "ring", 0x30B: "hungarumlaut", 0x30C: "caron"}
BOTTOM = {0x326: "commabelow", 0x327: "cedilla", 0x328: "ogonek"}
LATVIAN = "ģķļņŗĢĶĻŅŖ"          # U+0327 in Unicode, drawn as a comma (ģ: turned comma above), as in the parent
APOS = "ďľťĽ"                   # caron drawn as the apostrophe
# skeletons at every weight (font units): see the module docstring
SHAPE = {
    "lc": {"acute": (140, 50), "circ": (138, 37), "breve": (125, 84), "macron": 255, "tilde": (308, 81), "hung": (110, 50, 90), "hook": (112, 84)},
    "uc": {"acute": (140, 37), "circ": (138, 30), "breve": (125, 66), "macron": 265, "tilde": (308, 64), "hung": (110, 40, 90), "hook": (96, 78)},
}
CAP_GAP_K = 0.75                # capitals and ascenders: marks sit lower (0.75 GAP)
ACC_K = 0.87                    # the marks' stroke, x the stem
TOP_MAX = 955                   # no mark above this (the font files' line box tops at 970)
BOT_MIN = -315                  # no mark below this (the line box bottoms at -330), the same 15 units inside it
CLEAR_K = 1.25                  # stroke marks keep 1.25 GAP from a neighbour (pins: PIN_CLEAR)

LATIN1 = "".join(chr(c) for c in range(0xC0, 0x100) if c not in (0xD7, 0xF7))
EXTA = "".join(chr(c) for c in range(0x100, 0x180))
EXTRA = "ȘșȚțȷẀẁẂẃẄẅẞỲỳǰ"         # rest of GF Latin Core's letters, and ǰ
# Vietnamese (GF Latin Vietnamese): the horned ơ ư Ơ Ư and every precomposed letter of U+1EA0-1EF9 — one or two marks
# above (a second beside ˆ or over ˘ ˆ), the horn, the dot below (see viet() in build)
VIET = "ƠơƯư" + "".join(chr(c) for c in range(0x1EA0, 0x1EFA))
SPACING = "¨´¯¸ˆˇ˘˙˚˛˜˝"          # spacing marks (GF Latin Core)
# combining marks (U+0300-036F): the marks the accented letters are built from, as zero-width glyphs whose ink stands
# over (under) the letter before them — text in NFD shows them when a font has no precomposed letter for the pair
COMBINING = {0x300: "grave", 0x301: "acute", 0x302: "circumflex", 0x303: "tilde", 0x304: "macron", 0x305: "overline",
             0x306: "breve", 0x307: "dot", 0x308: "dieresis", 0x30A: "ring", 0x30B: "hungarumlaut", 0x30C: "caron",
             0x309: "hook", 0x312: "turnedcomma", 0x31B: "horn", 0x323: "dotbelow", 0x326: "commabelow", 0x327: "cedilla",
             0x328: "ogonek", 0x335: "shortstroke"}
TARGET = LATIN1 + EXTA + EXTRA

# glyphs with no limn base: the parent's shape, then limn's feet and fillets
PARENT = "ßẞÞþĸÆæŒŊ"
# bars and slashes drawn on limn's base letter (see graft() in build): ch -> base
GRAFT = {"Đ": "D", "Ð": "D", "đ": "d", "Ħ": "H", "ħ": "h", "Ŧ": "T", "ŧ": "t", "Ł": "L", "ł": "l", "Ø": "O", "ø": "o"}
# kerning classes for letters that are not base + mark: (class on the left of a pair = its right side,
# class on the right of a pair = its left side); None = the parent's own kerning (HarfBuzz)
KCLASS = {"ı": ("i", "i"), "ȷ": ("j", "j"), "ĳ": ("j", "i"), "Ĳ": ("J", "I"), "ŉ": ("n", "’"), "ŀ": (None, "l"),
          "Ŀ": ("L", "L"), "æ": ("e", "a"), "œ": ("e", "o"), "Æ": ("E", "A"), "Œ": ("E", "O"), "ð": ("o", "o"),
          "þ": ("p", "p"), "ĸ": ("k", "k"), "ŋ": ("n", "n"), "Ŋ": ("N", "N"), "ſ": ("f", "l"), "ß": (None, None),
          "ẞ": (None, None), "Þ": (None, None)}
for _c, _b in GRAFT.items():
    KCLASS[_c] = (_b, _b)
for _c in APOS:
    KCLASS[_c] = ("’", unicodedata.normalize("NFD", _c)[0])

ST = {"marks": {}, "clear": {}, "nopin": set(), "cls": {}, "new": [], "log": {}, "fail": {}, "combining": set()}


def _stroke(segs, w):
    """segs: list of point lists (open polylines) or ("c", p0, c1, c2, p3) cubics; round caps and joins."""
    out = pathops.Path()
    for s in segs:
        p = pathops.Path()
        if s[0] == "c":
            _, p0, c1, c2, p3 = s
            p.moveTo(*p0); p.cubicTo(*c1, *c2, *p3)
        else:
            p.moveTo(*s[0])
            for q in s[1:]: p.lineTo(*q)
        p.stroke(w, pathops.LineCap.ROUND_CAP, pathops.LineJoin.ROUND_JOIN, 4)
        p.convertConicsToQuads()
        out.addPath(p)
    out.simplify()
    return out


def _empty(p):
    return not list(p.contours)


def _bez(p0, c1, c2, p3, t):
    u = 1 - t
    return (u ** 3 * p0[0] + 3 * u * u * t * c1[0] + 3 * u * t * t * c2[0] + t ** 3 * p3[0],
            u ** 3 * p0[1] + 3 * u * u * t * c1[1] + 3 * u * t * t * c2[1] + t ** 3 * p3[1])


def build(ns):
    G, S, XH, XO, CAP, ASC = ns["G"], ns["S"], ns["XH"], ns["XO"], ns["CAP"], ns["ASC"]
    PIN_R, GAP, OSH, DOTSPEC, MODS = ns["PIN_R"], ns["GAP"], ns["OSH"], ns["DOTSPEC"], ns["MODS"]
    Q_DOT_R, Q_GAP = ns["Q_DOT_R"], ns["Q_GAP"]
    gpath, bounds, slice_at, rect, circle = ns["gpath"], ns["bounds"], ns["slice_at"], ns["rect"], ns["circle"]
    union, diff, inter, xform = ns["union"], ns["diff"], ns["inter"], ns["xform"]
    cmap, hmtx, gs = ns["cmap"], ns["hmtx"], ns["gs"]
    FEET, PREFEET = ns["FEET"], ns["PREFEET"]
    FILLET = ns.get("FILLET", 0)

    MW = ACC_K * S                                                  # the marks' stroke
    ring = sorted(gpath(None, "uni030A").contours, key=lambda c: -abs(c.area))
    (a0, b0, a1, b1) = ring[0].bounds
    R_OUT = (a1 - a0 + b1 - b0) / 4                                 # the parent's ring, outer radius
    R_IN = R_OUT - min(MW, 0.34 * 2 * R_OUT)
    GAP_UC = CAP_GAP_K * GAP
    # the skeleton is the parent's up to 700; where the stroke is heavier (800-900) it grows by half the stem's
    # gain, so ˆ ˇ ˘ ¸ ˛ keep a counter (× 1.07 at 800, × 1.14 at 900)
    from weights import stem as _stem
    K = max(1.0, 0.5 + 0.5 * S / _stem(700))
    ST["K"] = K
    PAIR = PIN_R + GAP / 2                                          # half the distance between two pins
    ST.update(MW=MW, GAP=GAP, PIN_R=PIN_R, CLEAR_STROKE=CLEAR_K * GAP)

    def fillet(p):
        if FILLET > 0 and "fillet_corners" in ns:
            p, _ = ns["fillet_corners"](p, FILLET * min(S, 120))
        return p

    def band_x(p, y0, y1, n=7):
        xs = []
        for k in range(n):
            for a, b in slice_at(p, y0 + (y1 - y0) * (k + 0.5) / n):
                xs += [a, b]
        return (min(xs), max(xs)) if xs else None

    def counter_x(p):
        cs = list(p.contours)
        if len(cs) < 2: return None
        outer = max(cs, key=lambda c: abs(c.area))
        holes = [c for c in cs if c.clockwise != outer.clockwise]
        if not holes: return None
        h = max(holes, key=lambda c: abs(c.area)).bounds
        return (h[0] + h[2]) / 2

    def top_anchor(base, p):
        if base in "ag":
            cx = counter_x(p)
            if cx is not None: return cx
        top = bounds(p)[3]
        x0, x1 = band_x(p, top - 0.25 * XH, top - 1)
        return (x0 + x1) / 2

    def bottom_anchor(p):
        x0, x1 = band_x(p, 1, 0.2 * XH)
        return (x0 + x1) / 2

    def line_of(base, p):
        """(form, mark line, pin centre, pin kind) for marks above this base."""
        if base.isupper():
            return "uc", CAP + GAP_UC, CAP + GAP_UC + PIN_R, "mid"
        top = bounds(p)[3]
        if top > (XO + CAP) / 2:                                    # ascender (ĺ ĥ)
            return "uc", top + GAP_UC, top + GAP_UC + PIN_R, "mid"
        return "lc", XH + GAP, XH + GAP + PIN_R, "i"

    def pin_spec(kind, x, cy):
        # DOTSPEC as build_font writes it: kind "i" keeps Quicksand's own dot top (the renderer derives the
        # pin centre from the weight's gap); "mid" is the pin centre itself
        y = XH + Q_GAP + 2 * Q_DOT_R if kind == "i" else cy
        return [kind, round(x, 1), round(y, 1), round(Q_DOT_R, 1)]

    def comma_head(ch, top=True):
        p = G[ch]["p"]; b = bounds(p)
        y = b[3] - 0.3 * PIN_R if top else b[1] + 0.3 * PIN_R
        iv = max(slice_at(p, y), key=lambda iv: iv[1] - iv[0])
        return p, b, (iv[0] + iv[1]) / 2

    def comma_below(x):
        """limn's comma under the baseline, its head's centre at x: the head top GAP under the baseline. The comma grows
        with the weight and reached -333 at 900, past the line box: like the marks above (TOP_MAX), it stays over BOT_MIN —
        it rises into that white, down to the capitals' mark white (CAP_GAP_K GAP), then shortens about its head top."""
        q, qb, hx = comma_head(",", top=True)
        h = qb[3] - qb[1]; top_ = -GAP
        if top_ - h < BOT_MIN:
            top_ = min(-CAP_GAP_K * GAP, BOT_MIN + h)
        m = xform(q, e=x - hx, f=top_ - qb[3])
        if top_ - h < BOT_MIN:
            k = (top_ - BOT_MIN) / h
            m = xform(m, 1, 0, 0, k, 0, top_ * (1 - k))
        return m

    def mark_above(name, form, ax, ml, pc, K=K, K0=K):
        """K scales the strokes' length, K0 the room between two strokes (˝ keeps it when its strokes shorten)."""
        sh = SHAPE[form]; hw = MW / 2; y = ml + hw
        if name in ("acute", "grave"):
            L, a = sh["acute"]; L *= K; sg = 1 if name == "acute" else -1
            return _stroke([[(ax, y), (ax + sg * L * math.cos(math.radians(a)), y + L * math.sin(math.radians(a)))]], MW), []
        if name in ("circumflex", "caron"):
            L, a = sh["circ"]; L *= K; dx, dy = L * math.cos(math.radians(a)), L * math.sin(math.radians(a))
            pts = [(ax - dx, y), (ax, y + dy), (ax + dx, y)] if name == "circumflex" else [(ax - dx, y + dy), (ax, y), (ax + dx, y + dy)]
            return _stroke([pts], MW), []
        if name == "breve":
            a, d = sh["breve"]; a, d = a * K, d * K; k = 0.5522847
            cy = y + d
            return _stroke([("c", (ax - a, cy), (ax - a, cy - k * d), (ax - k * a, y), (ax, y)),
                            ("c", (ax, y), (ax + k * a, y), (ax + a, cy - k * d), (ax + a, cy))], MW), []
        if name == "macron":
            L = sh["macron"] * K
            return _stroke([[(ax - L / 2, pc), (ax + L / 2, pc)]], MW), []
        if name == "tilde":
            w, A = sh["tilde"]; w, A = w * K, A * K
            pts = [(ax - w / 2 + w * t / 32, pc + A / 2 * math.sin(2 * math.pi * t / 32)) for t in range(33)]
            return _stroke([pts], MW), []
        if name == "hungarumlaut":
            L, a, dx = sh["hung"]; L, dx = L * K, dx * K0
            ex, ey = L * math.cos(math.radians(a)), L * math.sin(math.radians(a))
            return _stroke([[(ax - dx, y), (ax - dx + ex, y + ey)], [(ax + dx, y), (ax + dx + ex, y + ey)]], MW), []
        if name == "hook":
            # ̉ : a small question-mark hook — out to the upper left, over the top and back down to a short foot
            # over the centre (the parent's hook above, drawn with the marks' stroke)
            H, W = sh["hook"]; H, W = max(H * K, (1.9 if form == "uc" else 2.4) * MW), max(W * K, (1.7 if form == "uc" else 2.0) * MW); top = y + H - MW   # (it keeps white inside its
            # curl at 700-900, where the stroke is as heavy as the parent's hook is tall)
            foot = ("c", (ax + 0.46 * W, y + 0.60 * (H - MW)), (ax + 0.42 * W, y + 0.30 * (H - MW)), (ax, y + 0.36 * (H - MW)), (ax, y))

            def hook(e):
                return _stroke([("c", (ax - 0.45 * W - e, y + 0.62 * (H - MW)), (ax - 0.40 * W - e, top + 0.08 * H), (ax + 0.50 * W, top + 0.08 * H), (ax + 0.46 * W, y + 0.60 * (H - MW))),
                                foot], MW)
            m = hook(0.0)
            # the start's round end either keeps white from the foot or runs into it (capitals from 300, where the curl is
            # one drop of ink). Where it only touches it (capitals at 200: the skeleton is 78 wide, the stroke 45, the end
            # 1.00 stroke from the foot's centreline) the white between them is a crack 10 units long; there the start moves
            # out to the left until a quarter stroke of white stands between them
            import geom as _geom
            if any(k == "crack" for k, _ in _geom.spikes(m)):
                s0 = (ax - 0.45 * W, y + 0.62 * (H - MW))
                fp = [_bez(*foot[1:], i / 64) for i in range(65)]
                e = 0.0
                while e < W and min(math.dist((s0[0] - e, s0[1]), q) for q in fp) < 1.25 * MW:
                    e += 1.0
                if e:
                    m = hook(e)
            return m, []
        if name == "ring":
            # its size is the parent's ring, so the shortening that keeps a mark under TOP_MAX (K below ST["K"], accented())
            # shrinks it with the strokes: over a capital it reached 960 at 700 and 976 at 900, past the line box (970)
            f = min(1.0, K / ST["K"]); ro = R_OUT * f; ri = ro - min(MW, 0.34 * 2 * ro)
            return diff(circle(ax, ml + ro, ro), circle(ax, ml + ro, ri)), []
        if name == "dot":
            return pathops.Path(), [(ax, pc)]
        if name == "dieresis":
            return pathops.Path(), [(ax - PAIR, pc), (ax + PAIR, pc)]
        raise KeyError(name)

    def cedilla(ax, y_top):
        y1, rc = -25 * K, 42.0 * K
        cy = y1 - rc
        arc = [(ax + rc * math.cos(math.radians(t)), cy + rc * math.sin(math.radians(t))) for t in range(90, -151, -10)]
        return _stroke([[(ax, y_top), (ax, y1)] + arc], MW)

    def ogonek(p):
        y = MW / 2
        ivs = slice_at(p, y)
        xs = max(iv[1] for iv in ivs) - MW / 2
        return _stroke([("c", (xs, y), (xs - 95 * K, y - 50 * K), (xs - 75 * K, y - 160 * K), (xs + 45 * K, y - 160 * K))], MW)

    def put(ch, p, adv, pins=(), spec_pins=None, mark=None, base=None, clear=None):
        G[ch] = {"p": p, "adv": adv, "pins": [(round(x, 1), round(y, 1)) for x, y in pins]}
        if spec_pins:
            DOTSPEC[ch] = {"only": False, "adv0": adv, "pins": spec_pins}
        if mark is not None:
            m = pathops.Path(); m.addPath(mark)
            for x, y in pins: m.addPath(circle(x, y, PIN_R))
            if not _empty(m):
                ST["marks"][ch] = m
                ST["clear"][ch] = clear if clear is not None else (ns.get("PIN_CLEAR", 65) if pins else CLEAR_K * GAP)
        if base is not None and base in FEET:
            FEET[ch] = list(FEET[base])
            PREFEET[ch] = union(PREFEET[base], mark) if mark is not None and not _empty(mark) else PREFEET[base]
        ST["new"].append(ch)

    def accented(ch):
        dec = unicodedata.normalize("NFD", ch)
        base, marks = dec[0], [ord(c) for c in dec[1:]]
        if len(marks) != 1: raise ValueError("not base + one mark")
        mk = marks[0]
        if ch == "ģ":
            mk = 0x312                                              # turned comma above (U+0312), as in the parent
        stem_only = base in "ij"
        keep_pin = False
        bp = G[base]["p"]; adv = G[base]["adv"]; pins = []
        if stem_only and mk in TOP:
            ST["nopin"].add(ch)                                     # the mark replaces the pin
        elif base in "ij":
            keep_pin = True                                         # į keeps its pin
            pins = list(G[base]["pins"])
        spec = [list(e) for e in DOTSPEC[base]["pins"]] if keep_pin and base in DOTSPEC else []
        if ch in APOS:
            q = G["’"]["p"]; qb = bounds(q)
            dy = 0
            if base == "t":
                dy = (XH + GAP) - qb[1]                             # clear of the bar, like the parent
            q = xform(q, f=dy); qb = bounds(q)
            ys = [qb[1] + (qb[3] - qb[1]) * k / 12 for k in range(13)]
            ys = [y for y in ys if base != "t" or y > XH + GAP]
            gaps = []
            for y in ys:
                qa = slice_at(q, y); ba = slice_at(bp, y)
                if qa and ba: gaps.append(min(iv[0] for iv in qa) - max(iv[1] for iv in ba))
            dx = GAP - min(gaps) if gaps else bounds(bp)[2] + GAP - qb[0]
            m = xform(q, e=dx)
            radv = G["’"]["adv"] - bounds(G["’"]["p"])[2]
            # ť: the mark stands over the x-height, so it hangs over the next letter (the advance stays t's; the pairs
            # where it meets an ascender are opened below, in kern()); ď ľ Ľ: beside the stem, it widens the letter
            if base != "t":
                adv = max(adv, round(bounds(m)[2] + radv))
            put(ch, union(bp, m), adv, mark=m, base=base)
            return
        if mk in TOP or mk == 0x312:
            form, ml, pc, kind = line_of(base, bp)
            ax = top_anchor(base, bp)
            if ch == "ģ":
                q, qb, hx = comma_head("‘", top=False)
                m = xform(q, e=ax - hx, f=ml - qb[1]); mp = []
            else:
                m, mp = mark_above(TOP[mk], form, ax, ml, pc)
                # over an ascender (ĥ ĺ) the heavier weights' larger skeleton would leave the line box (970): it
                # shortens until the mark's top is TOP_MAX
                kk = K
                while not _empty(m) and bounds(m)[3] > TOP_MAX and kk > 0.6:
                    kk -= 0.02; m, mp = mark_above(TOP[mk], form, ax, ml, pc, kk)
            p = bp if _empty(m) else union(bp, m)
            spec += [pin_spec(kind, x, y) for x, y in mp]
            put(ch, p, adv, pins + mp, spec, mark=m, base=base)
            return
        if mk in BOTTOM:
            name = "commabelow" if ch in LATVIAN else BOTTOM[mk]
            if name == "commabelow":
                m = comma_below(bottom_anchor(bp))
            elif name == "cedilla":
                m = cedilla(bottom_anchor(bp), 0.5 * S)
            else:
                m = ogonek(bp)
            put(ch, union(bp, m), adv, pins, spec, mark=m, base=base)
            return
        raise ValueError("mark U+%04X" % mk)

    def stem_centres(p, y):
        return [(a + b) / 2 for a, b in slice_at(p, y) if 0.75 * S <= b - a <= 1.3 * S]

    # bars and slashes: one straight stroke with round ends on limn's own stems — as limn's Q tail replaced the parent's
    # wavy one. Slashes (Ł ł Ø ø) keep the parent's bar (U+0335) thickness; the bars (Đ Ð Ħ ħ Ŧ ŧ đ) are the
    # currency bars' LIGHT pen (€ ¥ ₩), lighter than the stems as they grow heavier, so bar and stem never knot:
    #   length   the parent's bar length, and at least a round cap and 0.45 s of straight bar past each side of
    #            the stem (at 800-900 the parent's bar ended in a nub on each side)
    #   đ ħ      in the ascender over the bowl or arch: the bar's top at least 0.8 s under the stem's top (its round
    #            end and a piece of straight stem show above it), its bottom 0.3 s over the round x-height; where the
    #            ascender has no room for both (800-900) the bar draws lighter, down to 0.45 s, and the margins share
    #            what is left
    #   Ħ        between H's bar and the cap height by the same rule (0.4 s of white above H's bar)
    _bb = gpath(None, "uni0335").bounds
    BAR_T, BAR_W = _bb[3] - _bb[1], _bb[2] - _bb[0]
    from punct import sym_pens, ST as _PST
    LIGHT_H = sym_pens(_PST["M"])["SUP"][1]
    ST.update(BAR_T=BAR_T, BAR_W=BAR_W, LIGHT_H=LIGHT_H)

    def h_bar_y():
        """Centre and top of limn H's crossbar."""
        hp = G["H"]["p"]; hb = bounds(hp); xm = (hb[0] + hb[2]) / 2
        ys = [y for y in range(int(0.2 * CAP), int(0.8 * CAP)) if any(a <= xm <= b for a, b in slice_at(hp, y + 0.5))]
        return (min(ys) + max(ys) + 1) / 2, max(ys) + 1

    def in_band(lo, hi, top_k, bot_k):
        """(centre, thickness) of a bar between lo and hi: top_k s of room above it, bot_k s below, thickness LIGHT
        or what the room leaves (never under 0.45 s; then the margins shrink in proportion)."""
        T = min(LIGHT_H, hi - lo - (top_k + bot_k) * S)
        if T >= 0.45 * S:
            a, b = lo + bot_k * S + T / 2, hi - top_k * S - T / 2
            return min(max((lo + hi) / 2, a), b), T
        T = 0.45 * S; f = (hi - lo - T) / ((top_k + bot_k) * S)
        return lo + bot_k * S * f + T / 2, T

    def graft(ch, base):
        lb = G[base]["p"]; b0 = bounds(lb); T = BAR_T
        if ch in "Øø":
            # corner to corner of the bowl, 5 % in from the sides, 2 % beyond top and bottom (parent: 4-6 %, 1-3 %)
            w, h = b0[2] - b0[0], b0[3] - b0[1]
            lo, hi = (b0[0] + 0.05 * w, b0[1] - 0.02 * h), (b0[2] - 0.05 * w, b0[3] + 0.02 * h)
            L = math.hypot(hi[0] - lo[0], hi[1] - lo[1]); ux, uy = (hi[0] - lo[0]) / L, (hi[1] - lo[1]) / L
            a, b = (lo[0] + ux * T / 2, lo[1] + uy * T / 2), (hi[0] - ux * T / 2, hi[1] - uy * T / 2)
        elif ch in "Łł":
            # through the stem at half its height, rising 32°, 1.13 bar lengths end to end (parent ł)
            yc = (CAP if ch == "Ł" else ASC) / 2
            xc = stem_centres(lb, yc)[0]
            half = (1.13 * BAR_W - T) / 2; ang = math.radians(32)
            a, b = (xc - half * math.cos(ang), yc - half * math.sin(ang)), (xc + half * math.cos(ang), yc + half * math.sin(ang))
        else:
            T = LIGHT_H
            if ch in "ĐÐŦ":
                yc = h_bar_y()[0]                                   # where H's bar is
            elif ch == "ŧ":
                yc = XH / 2
            elif ch == "Ħ":
                yc, T = in_band(h_bar_y()[1], CAP, 0.8, 0.4)
            else:                                                   # đ ħ: in the ascender above the bowl
                yc, T = in_band(XO, bounds(lb)[3], 0.8, 0.3)
            ys = 0.3 * CAP if base.isupper() else (0.3 * XH if base == "t" else (XH + ASC) / 2)
            sc = stem_centres(lb, ys)
            ext = max((BAR_W - S) / 2, T / 2 + 0.45 * S)            # past each side of the stem, ink
            if ch == "Ħ":
                a, b = (b0[0] - ext + T / 2, yc), (b0[2] + ext - T / 2, yc)
            else:
                xc = sc[0]
                a, b = (xc - S / 2 - ext + T / 2, yc), (xc + S / 2 + ext - T / 2, yc)
        m = _stroke([[a, b]], T)
        # bars meet the stem square on and get limn's round fillet; a 32° slash would grow a web, so not
        p = union(lb, m) if ch in "ŁłØø" else fillet(union(lb, m))
        # the advance grows by what the parent adds (Đ vs D); ink past the side bearings is left to kern()
        adv = G[base]["adv"] + hmtx[cmap[ord(ch)]][0] - hmtx[cmap[ord(base)]][0]
        put(ch, p, adv, mark=m, base=base)


    def parent(ch):
        p = gpath(ch)
        pre = p
        p, added = ns["flatten_feet"](p)
        p = fillet(p)
        put(ch, p, hmtx[cmap[ord(ch)]][0])
        if added:
            FEET[ch] = added; PREFEET[ch] = pre

    def eth():
        """ð on limn's o: the ascender leaves the bowl's right side upright, rises to the ascender and turns left to a
        round end over the bowl (the parent's skeleton), in o's pen; the bar crosses it rising 18° in the LIGHT pen,
        0.45 s of bar and a round end past the stroke on each side, its low end 0.3 s over the round x-height; the
        crossing is not closed round (a slanted crossing grows a web, as Ł's). The parent's ð, dilated past 700, knotted
        its bar into the ascender (1.9 S of ink at 900)."""
        from punct import atq_contrast, pen_line, bez_pts
        o = G["o"]["p"]; ox0, oy0, ox1, oy1 = bounds(o); w = ox1 - ox0; ocy = (oy0 + oy1) / 2
        SV, SH = atq_contrast(o)
        A = ASC - SH / 2
        P0 = (ox1 - SV / 2, ocy); P3 = (ox0 + 0.34 * w, A - 0.03 * w)
        asc = bez_pts(P0, (ox1 - SV / 2, ocy + 0.62 * (A - ocy)), (ox0 + 0.78 * w, A), P3, 40)
        stroke = pen_line(asc, SV, SH)
        T = LIGHT_H; ang = math.radians(18); ca, sa = math.cos(ang), math.sin(ang)
        half = SV / 2 + 0.45 * S + T / 2                           # centre to each end: the stroke, 0.45 s, the cap
        yb = XO + 0.3 * S + T / 2 + half * sa
        xb = next((x for x, y in asc if y >= yb), asc[-1][0])
        bar_ = pen_line([(xb - half * ca, yb - half * sa), (xb + half * ca, yb + half * sa)], T / (LIGHT_H / sym_pens(_PST["M"])["SUP"][0]), T)
        p = union(union(o, stroke), bar_)
        right = max(bounds(p)[2], ox1); o_rsb = G["o"]["adv"] - ox1
        adv = round(right + o_rsb - 0.5 * max(0.0, right - ox1))
        put("ð", p, adv, mark=bar_)

    def special(ch):
        if ch == "ð":
            eth(); return
        if ch in PARENT:
            parent(ch); return
        if ch in GRAFT:
            graft(ch, GRAFT[ch]); return
        if ch == "ı":
            put(ch, G["i"]["p"], G["i"]["adv"], base="i"); ST["nopin"].add(ch); return
        if ch == "ȷ":
            put(ch, G["j"]["p"], G["j"]["adv"], base="j"); ST["nopin"].add(ch); return
        if ch == "œ":
            qo, qe, qoe = gpath("o"), gpath("e"), gpath("œ")
            dx = bounds(qoe)[2] - bounds(qe)[2]
            put(ch, union(G["o"]["p"], xform(G["e"]["p"], e=dx + bounds(G["e"]["p"])[0] - bounds(qe)[0])), hmtx[cmap[ord(ch)]][0])
            return
        if ch == "ŋ":
            q = gpath("ŋ"); n = G["n"]["p"]
            sq, sl = stem_centres(q, 0.3 * XH), stem_centres(n, 0.3 * XH)
            dx = sl[-1] - sq[-1]
            hook = inter(q, rect(sq[-1] - S, -1e4, 1e4, 0.15 * S))
            put(ch, union(n, xform(hook, e=dx)), G["n"]["adv"], base="n")
            if ch in FEET:                                          # the right stem runs on into the hook
                FEET[ch] = [x for x in FEET[ch] if abs(x - sl[-1]) > S]
                PREFEET[ch] = union(PREFEET[ch], xform(hook, e=dx))
            return
        if ch == "ſ":
            f = G["f"]["p"]
            a, b = max(slice_at(f, 0.3 * XH), key=lambda iv: iv[1] - iv[0])
            # the bar is the only part of f that reaches left of the stem (the hook goes right)
            rows = [y for y in range(int(0.5 * XH), int(XH + S)) if any(iv[0] < a - 0.2 * S for iv in slice_at(f, y + 0.5))]
            y1 = max(rows) + 3
            # below the hook only the stem stays (the bar and its fillets go); the hook's end is kept whole
            hook = [y for y in range(int(y1), int(ASC)) if any(iv[0] > b + 1 for iv in slice_at(f, y + 0.5))]
            cut = min(y1 + 0.5 * S, (min(hook) - 1) if hook else 1e9)
            p = union(inter(f, rect(-1e4, cut, 1e4, 1e4)), inter(f, rect(a, -1e4, b, cut + 1)))
            fb = bounds(G["f"]["p"]); pb = bounds(p); lsb = bounds(G["l"]["p"])[0]
            p = xform(p, e=lsb - pb[0])
            put(ch, p, round(lsb + (pb[2] - pb[0]) + (G["f"]["adv"] - fb[2])))
            return
        if ch in "ŀĿ":
            base = "l" if ch == "ŀ" else "L"
            bp = G[base]["p"]; bb = bounds(bp)
            cy = G["·"]["pins"][0][1] if G.get("·", {}).get("pins") else XH / 2
            if ch == "Ŀ":
                qa, qc = gpath(None, "periodcentered").bounds, gpath(None, "periodcentered.case").bounds
                cy += (qc[1] + qc[3]) / 2 - (qa[1] + qa[3]) / 2
                sx = max(iv[1] for iv in slice_at(bp, cy) if iv[1] - iv[0] < 1.3 * S)
            else:
                sx = bb[2]
            x = sx + GAP + PIN_R
            adv = max(G[base]["adv"], round(x + PIN_R + bb[0]))
            put(ch, bp, adv, [(x, cy)], [["mid", round(x, 1), round(cy, 1), round(Q_DOT_R, 1)]], mark=pathops.Path(), base=base)
            return
        raise KeyError(ch)

    for ch in TARGET:
        if ch in G or ord(ch) not in cmap and ch not in "ſǰ":
            continue
        try:
            if ch in PARENT or ch in GRAFT or ch in "ıȷœŋſŀĿð":
                special(ch)
            elif ch in "ĳĲŉ":
                continue                                            # joined in kern(), once the pair kerning is known
            else:
                accented(ch)
        except Exception as e:                                      # report, never break the build
            ST["fail"][ch] = repr(e)

    # ---- Vietnamese: the horn, the dot below, and two marks above
    #   horn       one stroke of the marks' pen from the top right of the bowl (o) or the right stem's top (u U), rising
    #              to the right to a round end 0.30 x-height (capitals 0.22 CAP) over it, as far out as the parent's horn
    #   dot below  the pin, GAP_UC under the baseline under the letter's bottom centre; beside a descender (ỵ) it hangs
    #              halfway down the tail and moves right until GAP clears it
    #   two above  ˆ with ´ ` ̉: the second mark stands beside the right arm's end, half the ˆ up (the Vietnamese form);
    #              ˆ with ˜ and ˘ with anything: the second over the first; either way max(0.35 GAP, 0.25 s) of white
    #              between them. Every stack stays under TOP_MAX, the marks shortening, then each pressed down onto its
    #              own line; over a horned letter the marks keep GAP / 2 from the horn
    def horn_of(base, bp):
        """The horn's stroke; it starts at the centre of the letter's topmost stroke (so it joins it at every weight)."""
        b = bounds(bp); up = base.isupper(); h = (0.22 * CAP) if up else (0.30 * XH)
        if base in "oO":
            x0 = b[2] - 0.30 * (b[2] - b[0])
        else:
            x0 = max((a + c) / 2 for a, c in slice_at(bp, b[3] - 0.5 * S - 2))    # the right stem's centre
        col = inter(bp, rect(x0 - 0.5, -1e4, x0 + 0.5, 1e4))
        lo_, hi_ = max(((c.bounds[1], c.bounds[3]) for c in col.contours), key=lambda r: r[1])
        y0 = (lo_ + hi_) / 2 if base in "oO" else hi_ - 0.5 * S
        top = hi_ if base in "oO" else b[3]
        x1 = b[2] + 0.16 * (b[2] - b[0]) - MW / 2; y1 = top + h - MW / 2
        return _stroke([("c", (x0, y0), (x1, y0), (x1, 0.5 * (y0 + y1)), (x1 - 0.1 * MW, y1))], MW)

    import geom as _geom

    def dist(a, b):
        return _geom.shape(a).distance(_geom.shape(b))

    def squeeze(m, y0, fy):
        return m if fy >= 1 else xform(m, 1, 0, 0, fy, 0, y0 * (1 - fy))

    def two_above(names, form, ax, ml, pc, kk, fy=1.0):
        """One or two marks above; fy presses each mark down onto its own line (so a stack never closes up)."""
        m1 = squeeze(mark_above(names[0], form, ax, ml, pc, kk)[0], ml, fy)
        if len(names) == 1: return m1
        b1 = bounds(m1); white = max(0.35 * GAP, 0.25 * S)
        if names[0] == "circumflex" and names[1] in ("acute", "grave", "hook"):
            # beside the right arm, half the ˆ up; it keeps `white` from the ˆ at every weight
            L, a = SHAPE[form]["circ"]; dx = L * kk * math.cos(math.radians(a))
            y2 = ml + 0.5 * (b1[3] - b1[1]); x2 = ax + dx + 0.35 * MW
            m2 = squeeze(mark_above(names[1], form, x2, y2, pc, kk)[0], y2, fy)
            e = 0.0
            while dist(m1, xform(m2, e=e, f=0.6 * e)) < white and e < 2 * S:
                e += 2
            m2 = xform(m2, e=e, f=0.6 * e)
        else:
            ml2 = b1[3] + white
            m2 = squeeze(mark_above(names[1], form, ax, ml2, ml2 + (pc - ml), kk)[0], ml2, fy)
        return union(m1, m2)

    def viet(ch):
        dec = unicodedata.normalize("NFD", ch); base = dec[0]; mks = [ord(c) for c in dec[1:]]
        if base not in G: raise KeyError(base)
        bp0 = G[base]["p"]; bp = bp0; adv = G[base]["adv"]; pins, spec = [], []; marks = pathops.Path()
        above = [TOP[m] for m in mks if m in TOP]
        if base in "ij" and above:
            ST["nopin"].add(ch)                                 # the mark replaces the pin
        elif base in "ij":
            pins = list(G[base]["pins"]); spec = [list(e) for e in DOTSPEC.get(base, {}).get("pins", [])]
        if 0x31B in mks:
            hm = horn_of(base, bp0); bp = union(bp, hm); marks = union(marks, hm)
            adv = max(adv, round(bounds(hm)[2] + 0.5 * (G[base]["adv"] - bounds(bp0)[2])))
        if above:
            form, ml, pc, kind = line_of(base, bp0)
            ax = top_anchor(base, bp0)
            kk = K; fy = 1.0; m = two_above(above, form, ax, ml, pc, kk)
            while bounds(m)[3] > TOP_MAX and kk > 0.6:
                kk -= 0.02; m = two_above(above, form, ax, ml, pc, kk)
            while bounds(m)[3] > TOP_MAX and fy > 0.35:            # still over (capitals with two marks at 800-900): each
                # mark presses down onto its own line
                fy -= 0.02; m = two_above(above, form, ax, ml, pc, kk, fy)
            if 0x31B in mks:                                        # a mark over a horned letter keeps GAP from the horn
                while dist(m, hm) < 0.5 * GAP and ax > bounds(bp0)[0]:
                    ax -= 2; m = two_above(above, form, ax, ml, pc, kk, fy)
            bp = union(bp, m); marks = union(marks, m)
        if 0x323 in mks:
            ax = bottom_anchor(bp0); cy = -GAP_UC - PIN_R
            desc = inter(bp0, rect(-1e4, -1e4, 1e4, -0.1 * XH))
            if not _empty(desc):                                # ỵ: beside the tail, halfway down it (not a period)
                cy = 0.45 * ns["DESC"]
                while any(math.dist((ax, cy), q) < PIN_R + GAP for c in desc.contours for q in [pt for _, seg in c.segments for pt in seg if pt is not None]):
                    ax += 2
            pins.append((ax, cy)); spec.append(["mid", round(ax, 1), round(cy, 1), round(Q_DOT_R, 1)])
        put(ch, bp, adv, pins, spec or None, mark=marks, base=base)

    for ch in VIET:
        if ch in G: continue
        try:
            viet(ch)
        except Exception as e:
            ST["fail"][ch] = repr(e)

    # spacing marks: the lowercase mark, centred in the parent's side bearings
    for ch in SPACING:
        if ch in G or ord(ch) not in cmap: continue
        try:
            nm = cmap[ord(ch)]
            qb = gpath(None, nm).bounds; qadv = hmtx[nm][0]; sb = max(0.0, (qadv - (qb[2] - qb[0])) / 2)
            name = {"¨": "dieresis", "´": "acute", "¯": "macron", "ˆ": "circumflex", "ˇ": "caron", "˘": "breve",
                    "˙": "dot", "˚": "ring", "˜": "tilde", "˝": "hungarumlaut"}.get(ch)
            if name:
                m, mp = mark_above(name, "lc", 0.0, XH + GAP, XH + GAP + PIN_R)
            elif ch == "¸":
                m, mp = cedilla(0.0, 0.0), []
            else:
                m, mp = ogonek(rect(-0.5 * MW, 0, 0.5 * MW, MW)), []
            whole = pathops.Path(); whole.addPath(m)
            for x, y in mp: whole.addPath(circle(x, y, PIN_R))
            wb = bounds(whole); dx = sb - wb[0]
            m = xform(m, e=dx); mp = [(x + dx, y) for x, y in mp]
            put(ch, m, round(sb * 2 + wb[2] - wb[0]), mp, [pin_spec("i", x, y) for x, y in mp] or None)
        except Exception as e:
            ST["fail"][ch] = repr(e)

    # combining marks: the lowercase mark centred over an o-wide letter before the origin (advance 0), cedilla and comma
    # below under its middle, ogonek at its right; U+0305 is a macron across the whole letter, U+0335 a bar through it
    wo = G["o"]["adv"]; axc = -wo / 2
    for cp, name in COMBINING.items():
        ch = chr(cp)
        if ch in G: continue
        try:
            mp = []
            if name in ("overline",):
                m = _stroke([[(-wo + MW / 2, XH + GAP + PIN_R), (-MW / 2, XH + GAP + PIN_R)]], MW)
            elif name == "shortstroke":
                m = _stroke([[(axc - BAR_W / 2 + MW / 2, XH / 2), (axc + BAR_W / 2 - MW / 2, XH / 2)]], ST.get("LIGHT_H", MW))
            elif name == "turnedcomma":
                q, qb, hx = comma_head("‘", top=False)
                m = xform(q, e=axc - hx, f=XH + GAP - qb[1])
            elif name == "commabelow":
                m = comma_below(axc)
            elif name == "cedilla":
                m = cedilla(axc, 0.5 * S)
            elif name == "horn":
                m = xform(horn_of("o", G["o"]["p"]), e=-G["o"]["adv"])
            elif name == "dotbelow":
                m = pathops.Path(); mp = [(axc, -GAP_UC - PIN_R)]
            elif name == "ogonek":
                m = ogonek(rect(-0.2 * wo - MW, 0, -0.2 * wo, MW))
            else:
                m, mp = mark_above(name, "lc", axc, XH + GAP, XH + GAP + PIN_R)
            put(ch, m, 0, mp, [pin_spec("i" if y > 0 else "mid", x, y) for x, y in mp] or None)
            ST["combining"].add(ch)
        except Exception as e:
            ST["fail"][ch] = repr(e)

    ST["cls"] = {}
    for ch in ST["new"]:
        if ch in KCLASS:
            ST["cls"][ch] = KCLASS[ch]
        elif ch not in SPACING and ch not in ST["combining"]:
            b = unicodedata.normalize("NFD", ch)[0]
            ST["cls"][ch] = (b, b)
    n_new = len([c for c in ST["new"] if c not in SPACING and c not in ST["combining"]])
    MODS.append(["À–ÿ Ā–ž …", "악센트 글자 %d자 + 부호 %d자 + 결합 부호 %d자" % (n_new, len([c for c in ST["new"] if c in SPACING]), len(ST["combining"])),
                 f"limn 기본 글자 + limn 규칙의 부호(tools/accents.py). 점 부호는 핀(r {PIN_R:.1f}, 두 핀 사이 흰 틈 {GAP:.0f}), 획 부호는 줄기 × {ACC_K} = {MW:.0f}의 둥근 끝 단선(모든 굵기에서 같은 비), 고리는 그 굵기로 부모 고리의 폭에(폭의 0.34까지). 소문자 부호는 i 핀 아랫선(x높이 + {GAP:.0f})에, 대문자·어센더 부호는 +{GAP_UC:.0f}에 서고 더 눕힘"])
    MODS.append(["ı ȷ ì í î ï …", "점 없는 줄기", "i·j의 부호는 핀을 대신함. ï는 두 핀(분음 부호는 뜻을 가름). į는 핀과 오고넥을 함께"])
    MODS.append(["ß Þ þ ð ĸ Æ æ Œ Ŋ · Đ Ħ Ŧ Ł Ø", "부모 모양 + limn 규칙", "limn 기본 글자가 없는 글자는 Quicksand의 모양에 limn의 평평한 발·둥근 이음을, 막대(Đ Ħ Ŧ đ ħ ŧ)는 화폐 막대와 같은 LIGHT 펜으로 부모 막대(U+0335) 길이 이상(줄기 밖으로 둥근 끝 + 0.45 s), đ ħ는 줄기 끝이 막대 위로 0.8 s 드러나게, 빗금(Ł Ø)은 부모 막대 굵기로 곧게 새로 그어 limn 줄기에 얹음(Q 꼬리처럼 물결 대신 직선)"])
    return ST


def kern(ns):
    """Map base pairs onto the accented letters and open pairs whose mark comes too close."""
    G, KERN, PINKERN, MODS = ns["G"], ns["KERN"], ns.get("PINKERN", {}), ns["MODS"]
    union, xform, bounds, circle = ns["union"], ns["xform"], ns["bounds"], ns["circle"]
    PIN_R, PIN_CLEAR = ns["PIN_R"], ns.get("PIN_CLEAR", 65)
    DOTSPEC, DIGITS = ns["DOTSPEC"], ns["DIGITS"]
    cmap = ns["cmap"]

    # ĳ Ĳ ŉ: the two letters as kerned
    for ch, (a, b) in (("ĳ", ("i", "j")), ("Ĳ", ("I", "J")), ("ŉ", ("’", "n"))):
        if ch in G or ord(ch) not in cmap or a not in G or b not in G: continue
        dx = G[a]["adv"] + KERN.get(a + b, 0)
        pins = list(G[a]["pins"]) + [(x + dx, y) for x, y in G[b]["pins"]]
        spec = [list(e) for e in DOTSPEC.get(a, {}).get("pins", [])] + [[k, round(x + dx, 1), y, r] for k, x, y, r in DOTSPEC.get(b, {}).get("pins", [])]
        G[ch] = {"p": union(G[a]["p"], xform(G[b]["p"], e=dx)), "adv": round(dx + G[b]["adv"]), "pins": pins}
        if spec: DOTSPEC[ch] = {"only": False, "adv0": G[ch]["adv"], "pins": spec}
        ST["new"].append(ch); ST["cls"][ch] = KCLASS[ch]

    cls = ST["cls"]
    base_keys = list(KERN.items())
    lefts, rights = {}, {}
    for ch, (kl, kr) in cls.items():
        if kl: lefts.setdefault(kl, []).append(ch)
        if kr: rights.setdefault(kr, []).append(ch)
    nopin = ST["nopin"]
    added = 0
    # a pair takes the base pair nearest to it: one side through its class before both. Ύ δ is Υ|δ's pair (Yδ, set by
    # spacing.json) and not Y|o's, which the class of δ (o) also reaches: in the order the pairs were made (Yo is the
    # parent's, Yδ came later) Ύδ took Yo's -41, and at 900 Ύ's arm ran into δ's neck (0.07 S)
    via = {}                                                # mapped pair -> the sides it took through a class
    for pr, v in base_keys:
        if len(pr) != 2: continue
        x, y = pr
        Ls = [x] + lefts.get(x, []); Rs = [y] + rights.get(y, [])
        if len(Ls) == 1 and len(Rs) == 1: continue
        pk = PINKERN.get(pr, 0)
        for A in Ls:
            for B in Rs:
                if A == x and B == y: continue
                n = (A != x) + (B != y)
                if (A + B) in KERN and ((A + B) not in via or via[A + B] <= n): continue
                vv = v - (pk if (A in nopin and x in "ij") or (B in nopin and y in "ij") else 0)
                if vv or (A + B) in via:                    # (a nearer 0 replaces a farther pair too)
                    if (A + B) not in via: added += 1
                    KERN[A + B] = vv; via[A + B] = n

    # the parent's own kerning for letters with no limn class
    par = [ch for ch, (kl, kr) in cls.items() if kl is None or kr is None]
    if par and "adv_of" in ns:
        adv_of, single, ks = ns["adv_of"], ns["single"], ns["ks"]
        for ch in par:
            kl, kr = cls[ch]
            s0 = adv_of(ch)
            for o in ks:
                if kl is None:
                    v = adv_of(ch + o) - s0 - single[o]
                    if v and (ch + o) not in KERN: KERN[ch + o] = v; added += 1
                if kr is None:
                    v = adv_of(o + ch) - single[o] - s0
                    if v and (o + ch) not in KERN: KERN[o + ch] = v; added += 1

    # ---- mark clearance on the outlines: row profiles every 4 units
    Y0, STEP, NR = -480, 4, 420
    INF = float("inf")
    polylines = ns["polylines"]

    def raster(p):
        lo, hi = [INF] * NR, [-INF] * NR
        for pl in polylines(p, steps=8):
            n = len(pl)
            for i in range(n):
                (x0, y0), (x1, y1) = pl[i], pl[(i + 1) % n]
                if y0 == y1: continue
                if y0 > y1: x0, y0, x1, y1 = x1, y1, x0, y0
                j0 = max(0, math.ceil((y0 - Y0) / STEP)); j1 = min(NR - 1, math.floor((y1 - Y0) / STEP))
                for j in range(j0, j1 + 1):
                    yy = Y0 + j * STEP
                    xx = x0 + (yy - y0) * (x1 - x0) / (y1 - y0)
                    if xx < lo[j]: lo[j] = xx
                    if xx > hi[j]: hi[j] = xx
        rows = [j for j in range(NR) if lo[j] < INF]
        return lo, hi, rows, (max(hi[j] for j in rows) if rows else -INF)

    def full_path(ch):
        p = pathops.Path(); p.addPath(G[ch]["p"])
        for x, y in G[ch]["pins"]: p.addPath(circle(x, y, PIN_R))
        return p

    # every glyph is a neighbour, the figures too: they do not kern among themselves, but a mark over the next letter
    # (ΐ ϊ ĩ …) must clear a figure as it clears a letter
    NB = [c for c in G if c != "림" and c not in "¨´¯¸ˆˇ˘˙˚˛˜˝" and c not in ST["combining"] and (list(G[c]["p"].contours) or G[c]["pins"])]
    FULL = {c: raster(full_path(c)) for c in NB}
    MARK = {}
    for ch, m in ST["marks"].items():
        if ch in G: MARK[ch] = (raster(m), ST["clear"][ch])
    for ch in "ij":                         # the i/j pin, so a pinless neighbour (í ı) still keeps it clear
        if ch in G and G[ch]["pins"]:
            pp = pathops.Path()
            for x, y in G[ch]["pins"]: pp.addPath(circle(x, y, PIN_R))
            MARK[ch] = (raster(pp), PIN_CLEAR)

    def need(Lr, Rr, shift, C):
        """How much the pair must open so the right edge of Lr keeps C from the left edge of Rr."""
        _, Lhi, Lrows, Lmax = Lr; Rlo, _, Rrows, _ = Rr
        if not Lrows or not Rrows: return 0.0
        w = int(C / STEP) + 1
        a, b = max(0, Lrows[0] - w), min(NR, Lrows[-1] + w + 1)
        mr = min(Rlo[a:b])
        if mr == INF or mr + shift - Lmax >= C: return 0.0
        best = 0.0
        for i in Lrows:
            xl = Lhi[i]
            for j in range(max(0, i - w + 1), min(NR, i + w)):
                xr = Rlo[j]
                if xr == INF: continue
                dy = (j - i) * STEP
                r = math.sqrt(max(0.0, C * C - dy * dy)) - (xr + shift - xl)
                if r > best: best = r
        return best

    newset = set(ST["new"]) & set(G)
    opened = {}
    pairs = set()
    for A in MARK:
        if A not in newset and A not in "ij": continue
        for N in NB:
            if A in "ij" and N not in newset: continue          # base i/j pairs are build_font's
            pairs.add((A, N)); pairs.add((N, A))
    for L, R in pairs:
        if L not in G or R not in G: continue
        shift = G[L]["adv"] + KERN.get(L + R, 0)
        d = 0.0
        if L in MARK and R in FULL:
            (mr, C) = MARK[L]; d = max(d, need(mr, FULL[R], shift, C))
        if R in MARK and L in FULL:
            (mr, C) = MARK[R]
            d = max(d, need(FULL[L], mr, shift, C))     # R's mark (left edge) against L's right edge
        if d >= 1:
            opened[L + R] = math.ceil(d)
            KERN[L + R] = KERN.get(L + R, 0) + math.ceil(d)
    for k in [k for k, v in KERN.items() if v == 0]:
        del KERN[k]
    ST["log"] = {"mapped": added, "opened": len(opened), "opened_pairs": opened}
    import os, sys, json
    if os.environ.get("LIMN_ACC_DEBUG"):
        with open(os.environ["LIMN_ACC_DEBUG"], "w") as fh:
            json.dump({"opened": opened, "fail": ST["fail"], "new": ST["new"]}, fh, ensure_ascii=False)
    print(f"accents: {len(set(ST['new']) & set(G))} glyphs, {added} mapped pairs, {len(opened)} opened for marks"
          + (f", FAILED {ST['fail']}" if ST["fail"] else ""), file=sys.stderr)
    MODS.append(["악센트 커닝", "기본 글자의 짝 + 부호 여백", f"é는 e의 짝을 물려받음(ď ľ ť의 오른쪽은 ’, ĳ는 i|j, œ는 o|e) — {added}쌍. 부호가 이웃 윤곽에 핀은 {PIN_CLEAR}, 획은 {CLEAR_K * ST['GAP']:.0f}보다 가까운 {len(opened)}쌍은 모자란 만큼 벌림"])
    return ST
