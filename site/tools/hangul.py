"""Hangul for Limn Sans: NanumSquareRound (NAVER, SIL OFL 1.1) set against limn's Latin at weights 100-900.

  from hangul import params, glyph, rim
  params(w)        the pairing at limn weight w (instance, pen, scale k, baseline dy, tracking)
  glyph(w, ch)     (pathops path in limn units, y down, baseline 0; advance)
  rim(w)           the brand 림: NanumSquareRound's own 림 at w with its ㅣ replaced by an i (pin drawn by the engine)

The parent is NanumSquareRound (L, R, B, EB, tools/hangul/, fetched by fetch_hangul.sh). "Nanum" is a
Reserved Font Name of NAVER's licence, so nothing derived from it carries that name.

Pairing rule (measured study /tmp/limn-audit/rim5, decided by the user 2026-09-28). All numbers are limn
units (UPM 1000); the frame is read on the proof Hangul (tools/hangul.py PROOFS, with repeats): the syllables'
top at the 10th percentile and bottom at the 90th, i.e. the deepest syllables.
  anchors    limn 700 = NanumSquareRound EB at k 0.916582, limn 400 = R at k 0.908515. These are the
             body-centre rule (body 1.16 cap, centre on cap/2) scaled up so the common open syllables reach
             NanumSquare Neo's size (+6 % at 700, +9 % at 400), then lowered by 20.
  frame      frame - V/2 = F(w): the ink frame (p10 top to p90 bottom) less half the vertical stroke V is one
             constant between the anchors (798.8 at 400, 798.9 at 700, linear between, held outside): the
             skeleton keeps its size and the ink grows around it, as in NanumSquareRound's own masters.
  centre     the frame's centre sits 350 above the baseline at every weight (cap / 2):
             dy = -350 - k c0, c0 the frame centre of the instance (y down).
  fit        2026-09-28: both anchors scaled by FIT 0.95 about the frame centre, the centre raised from 330 to
             350 — the open syllables on the Latin baseline, the final consonants dipping 54 (hangul-fit.html).
  stroke     V / S as at 400 (R) for 400 and below, as at 700 (EB) at 700, linear between, easing to 0.93
             at 900 (ratio()); then moved by a few percent so the proof syllables' ink runs on one quadratic in S
             across the master switches (smooth_targets(), release QA S12). NanumSquareRound's four masters are
             not point-compatible (가: 35 / 36 / 36 / 33 points), so they cannot be interpolated: each weight
             takes the master whose stroke is nearest and a round pen makes up the rest (GEOS through shapely,
             "the pen, release rules" below: clearance of GAP_MIN S between jamo and COUNTER_MIN S in counters
             at every weight, cusps filleted), and the result is fitted back to TrueType curves (fit_ring()).
  advance    one per glyph at every weight: R's advance x 400's scale + 400's tracking (advance()); every weight
             centres its ink in it. No extra white where Latin meets Hangul (BOUNDARY).
  coverage   all 11,172 syllables: the 8,693 NanumSquareRound leaves empty are composed from its drawn jamo
             (compose()); symbols from one master with a pen tied to the weight, the square units and ①-⑩ from
             Limn's own letters and figures (symbol_geom()).

  params() at build time (curve HALF, make hangul prints them): master per weight
  weight   100   200   300    400   500   600    700   800   900
  master   L     L     R      R     B     B      EB    EB    EB
"""
import math
import re
from functools import lru_cache
from pathlib import Path

import numpy as np
import pathops
from fontTools.cu2qu import curve_to_quadratic
from fontTools.pens.basePen import BasePen
from fontTools.pens.recordingPen import DecomposingRecordingPen
from fontTools.ttLib import TTFont

import weights as W
import hangul_cache as HC

HERE = Path(__file__).resolve().parent
FDIR = HERE / "hangul"
MASTERS = ("L", "R", "B", "EB")          # axis positions 0 1 2 3
WEIGHTS = tuple(range(100, 1000, 100))
CAP = 700
CENTRE = 350                             # frame centre above the baseline: cap / 2 (2026-09-28 fit, below)
# limn weight: (master, k). rim5's pairings (400 R 0.908515, 700 EB 0.916582) set the Hangul 20 below cap / 2 and
# read as hanging under the Latin (user 2026-09-28: "한글이 영어 대비 살짝 아래로 삐져나오잖아"). Six fits were set in
# mixed sentences (hangul-fit.html); the chosen one scales by 0.95 about the frame centre and raises it 20, so the
# open syllables (가 나 이) sit on the Latin baseline (-3 at 700) and only the final consonants dip (-54, was -95),
# with the centre on the capitals' centre (354 vs 350) and the body 1.16 cap. Putting the closed syllables on the
# baseline instead floats the open ones 47 above it, NanumSquareRound's two bottoms being 46 apart.
FIT = 0.95
PIN = {400: (1, 0.908515 * FIT), 700: (3, 0.916582 * FIT)}
# Hangul tracking (added to NanumSquareRound's advance x k, half on each side), measured by hangul_measure.py
# --refs where the references are, 400 and 700: in Pretendard, SUIT, Noto Sans KR and IBM Plex Sans KR the white
# between neighbouring syllables (mean over the rows where both have ink, the rim3/rim5 measure) is 2.40 (400) /
# 2.26 (700) x the white between their own Latin letters (medians; the four span 2.03-2.47). Giving limn's
# Hangul that proportion to limn's own letter white takes +1 at 400 and +9 at 700 (the earlier +32 came from
# six families' median 2.45, rim3 calib, whose row sampling also missed most pairs). Between the anchors the
# value runs straight, outside it is held; then the pen's change of the side bearings is given back (2 delta:
# eroding opens the syllables, dilating closes them), so every weight keeps its master's own spacing. The
# ratio is not extrapolated: fitted at 100 it asked -81 and ran the syllables into each other.
TRACK_ANCHOR = {400: 6, 700: 28}
# The anchors are stems, not weight names (2026-09-28, curve D): "400" is R at curve A's 400 stem (68.4), "700" is
# EB at Quicksand Bold's (120, the brand drawing). No family weight on D sits exactly on them; every weight is
# placed by its stem, so a given stem gets the same Hangul whatever the weight is called.
S_AT = {400: W.stem(400, "A"), 700: W.stem(700, "A")}
S_END = W.stem(900, "A")                 # RATIO_900 is reached at A's 900 stem (153)


def _x(S):
    return min(1.0, max(0.0, (S - S_AT[400]) / (S_AT[700] - S_AT[400])))   # re-measured after the 2026-09-28 fit (the smaller Hangul needs more white to keep the references' 2.40 / 2.26 ratio)
# Latin letter | Hangul syllable, either way: no extra white and no pair kerning. The nearest-approach measure
# puts limn at the references' proportion already (theirs 1.03 x the letter white at 400 and 700, limn 0.98-1.0);
# the row-mean measure would take 20-36 off, which by nearest approach set Latin against Hangul tighter than
# any reference.
BOUNDARY = 0


def track_of(w, delta):
    a, b = TRACK_ANCHOR[400], TRACK_ANCHOR[700]
    return round(a + _x(stem(w)) * (b - a) + 2 * delta)

# the proof text: the frame and the stroke are read on it (rim5's corpus: the proof sentences with repeats)
PROOFS = [
    "limn에 핀을 꽂아 두면 다시 읽힌다",
    "원고 PDF 3개 · 핀 12개 · Resolve all",
    "오늘의 manuscript를 pin it, fix it, done.",
    "리뷰어 코멘트 v0.3.12 — 2026년 9월 27일",
    "Limn 림 · 림 limn · 타이포그래피 Typography",
]
PARA = ("limn은 원고 PDF 위에 핀을 꽂아 두는 viewer다. 핀마다 comment와 page 번호가 남아서, "
        "다음 revision에서 바로 다시 찾는다. 모두 고치면 Resolve all 한 번으로 정리한다.")
VSET = "이니디리미비기지히"               # a vertical vowel stroke at mid height (mixlib.vstroke)
HSET = "으그느드르므브스"


def orient(p):
    """Wind every contour by its nesting depth (outer, hole, island …), so SVG's nonzero rule and the next
    boolean read the fill the same way. skia's simplify turned some ㅇ counters to their ring's direction (공
    at 100, 강 at 800), which filled them and misled every later operation."""
    cs = [c for c in p.contours if list(c.points)]
    out = pathops.Path(); out.fillType = pathops.FillType.WINDING
    for i, c in enumerate(cs):
        pt = c.points[0]; b = c.bounds
        depth = 0
        for j, d in enumerate(cs):
            if j == i: continue
            db = d.bounds
            if db[0] <= b[0] and db[1] <= b[1] and db[2] >= b[2] and db[3] >= b[3] and abs(d.area) > abs(c.area) and d.contains(pt):
                depth += 1
        q = pathops.Path(c)
        if q.clockwise != (depth % 2 == 1): q.reverse()
        out.addPath(q)
    return out


def tidy(p):
    """A raw outline (overlapping components) made clean: skia's simplify, then re-wound by nesting."""
    q = pathops.Path(p); q.simplify()
    return orient(q)


def is_syllable(ch):
    return 0xAC00 <= ord(ch) <= 0xD7A3


FRAME_TEXT = [ch for s in PROOFS + [PARA] for ch in s if is_syllable(ch)]


def ksx1001():
    """The 2,350 syllables of KS X 1001 (EUC-KR rows 0xB0-0xC8)."""
    out = []
    for hi in range(0xB0, 0xC9):
        for lo in range(0xA1, 0xFF):
            out.append(bytes([hi, lo]).decode("euc-kr"))
    return out


JAMO = [chr(u) for u in range(0x3131, 0x3164)]            # compatibility jamo ㄱ-ㅣ (51)
# Korean punctuation NanumSquareRound has and limn's Latin lacks
PUNCT = list("「」『』〈〉《》【】〔〕、。※〜")
# and the KS X 1001 typographic symbols Korean text sets every day (sweep 2026-09-28): the araea and katakana middle
# dots, the full-width tilde, the geometric bullets, the arrows, degrees Celsius, the square units and ①-⑩ — built per
# weight like every other NanumSquareRound glyph (master, pen, scale k, frame, tracking)
PUNCT += list("ㆍ・～○●□■△▲☆★℃㎡㎏㎝㎞①②③④⑤⑥⑦⑧⑨⑩")
# sym-math 2026-09-29: the arrows → ← ↑ ↓ left this list, the Latin draws them (tools/sym_math.py, with every other
# arrow); added the geometric and card symbols NanumSquareRound has (all four masters; ◊ ◦ ◯ ▪ ▫ ▢ ♦ ♫ ☀ ☼ ⚠ it lacks)
PUNCT += list("▶▷▼▽◀◁◆◇♠♡♥♣♪☎")


def syllables():
    """All 11,172 modern syllables U+AC00-D7A3 (release 2026-09-30; before it, KS X 1001's 2,350 only)."""
    return [chr(c) for c in range(0xAC00, 0xD7A4)]


def charset():
    ks = ksx1001(); seen = set(ks)
    return ks + [c for c in syllables() if c not in seen] + JAMO + PUNCT


# ------------------------------------------------------------------ NanumSquareRound
@lru_cache(maxsize=None)
def _masters():
    fs = []
    for m in MASTERS:
        p = FDIR / f"NanumSquareRound{m}.ttf"
        if not p.exists():
            raise FileNotFoundError(f"{p} missing: run make hangul-fonts (tools/fetch_hangul.sh)")
        f = TTFont(str(p), lazy=True)
        fs.append((f.getGlyphSet(), f.getBestCmap(), 1000 / f["head"].unitsPerEm))
    return fs


@lru_cache(maxsize=None)
def _rec(ch, m):
    """(pen ops, advance) of master m (0 L · 1 R · 2 B · 3 EB) in 1000 UPM, y up; None if missing. A syllable
    NanumSquareRound maps but leaves empty is composed from its drawn syllables' jamo (compose())."""
    gs, cm, u = _masters()[m]
    gn = cm.get(ord(ch))
    if gn is None:
        return None
    rp = DecomposingRecordingPen(gs); gs[gn].draw(rp)
    if not rp.value and is_syllable(ch):
        return compose(ch, m), gs[gn].width * u
    ops = [(op, tuple(None if q is None else (q[0] * u, q[1] * u) for q in v)) for op, v in rp.value]
    return ops, gs[gn].width * u


# ------------------------------------------------------------------ the syllables NanumSquareRound leaves empty
# NanumSquareRound maps all 11,172 syllables but draws 2,479 (KS X 1001's 2,350 and 129 more): the other 8,693 are
# empty glyphs (checked 2026-09-30 in all four masters; the release QA read the cmap). Each drawn syllable is a
# composite of three hand-set jamo drawn for it alone (1,294 distinct initials, 1,314 vowels), so the missing ones
# are composed here from them (the user chose all 11,172, 2026-09-30). For a syllable (L, V, T):
#   primary   the drawn syllable with the same vowel and a final of the same kind (none / single / double or
#             cluster: the vowel is drawn for it) that shares most with it: the same initial (8) and the same final
#             (8), an initial of the same kind (single / double, 1). Its vowel is taken as it is, and its initial
#             and final when they are the target's.
#   donors    an initial the primary lacks comes from the drawn syllable with the same initial and final presence
#             whose vowel is the same (8) or of the same kind (vertical / horizontal / both, 4), with a final of the
#             same kind (2); a final from the one with the same final whose vowel is the same (8) or of the same
#             kind (4). Each is fitted into the primary's own box for that jamo: centred, scaled to its size (the
#             two scales kept within COMPOSE_ASPECT of each other), and its strokes given back their weight by a
#             Minkowski sum (or difference) with a horizontal segment of (1 - sx) V0 and a vertical one of
#             (1 - sy) H0, so a scaled jamo keeps the master's stroke.
# The four masters share the plan (it is made from R's composites; their component names are the same) and fit
# with their own boxes and strokes.
COMPOSE_ASPECT = 0.08
SINGLE_T = {1, 4, 7, 8, 16, 17, 19, 21, 22, 23, 24, 25, 26, 27}      # ㄱ ㄴ ㄷ ㄹ ㅁ ㅂ ㅅ ㅇ ㅈ ㅊ ㅋ ㅌ ㅍ ㅎ
DOUBLE_L = {1, 4, 8, 10, 13}                                          # ㄲ ㄸ ㅃ ㅆ ㅉ


def _lvt(ch):
    s = ord(ch) - 0xAC00
    return s // 588, (s % 588) // 28, s % 28


def _tk(t):
    return 0 if t == 0 else 1 if t in SINGLE_T else 2


def _vk(v):
    return 0 if v in (0, 1, 2, 3, 4, 5, 6, 7, 20) else 1 if v in (8, 12, 13, 17, 18) else 2


@lru_cache(maxsize=None)
def _drawn():
    """{(L, V, T): {"L": name, "V": name, "T": name}} of the syllables NanumSquareRound R draws. The composites
    list their jamo in no fixed order (꺾 has its final second), so each is read by where it sits: the final is the
    one whose top is lowest, the initial of the other two the one further left and up (x - y smallest, y up)."""
    f = TTFont(str(FDIR / "NanumSquareRoundR.ttf"))
    cm, glyf = f.getBestCmap(), f["glyf"]
    out = {}
    for c in range(0xAC00, 0xD7A4):
        g = glyf[cm[c]]
        if g.numberOfContours == 0 or not g.isComposite():
            continue
        k = _lvt(chr(c)); cs = [cc.glyphName for cc in g.components]
        if len(cs) != (3 if k[2] else 2):                 # one component per jamo (none merge two, checked)
            continue
        bb = {}
        for n in cs:
            q = glyf[n]; q.recalcBounds(glyf); bb[n] = (q.xMin, q.yMin, q.xMax, q.yMax)
        roles = {}
        rest = list(cs)
        if k[2]:
            roles["T"] = min(rest, key=lambda n: bb[n][3]); rest.remove(roles["T"])
        roles["L"] = min(rest, key=lambda n: (bb[n][0] + bb[n][2]) / 2 - (bb[n][1] + bb[n][3]) / 2)
        rest.remove(roles["L"]); roles["V"] = rest[0]
        out[k] = roles
    return out


@lru_cache(maxsize=None)
def compose_plan(ch):
    """(primary (L, V, T), {role: donor (L, V, T)}) for an undrawn syllable: of the PLAN_TRY best-scoring primaries
    (and their donors), the one whose jamo, fitted in R, keep the most white between them (up to COMPOSE_GAP x
    V0; then the score decides). A donor initial with a bottom bar (ㅍ) put where the primary's was open (ㄱ) would
    meet the primary's vowel stem; another primary keeps them apart."""
    D = _drawn(); l, v, t = _lvt(ch)
    order = lambda ks, sc: sorted(ks, key=lambda k: (-sc(k), k))
    best = lambda ks, sc: order(ks, sc)[0] if ks else None
    # the vowel is drawn for its final's kind (none, single, double or cluster: a cluster's vowel stops higher), so
    # the primary has the same vowel and a final of the same kind, then as much else of the target as it can
    cands = order([k for k in D if k[1] == v and _tk(k[2]) == _tk(t)] or [k for k in D if k[1] == v and (k[2] > 0) == (t > 0)],
                  lambda k: 8 * (k[0] == l) + 8 * (k[2] == t) + ((k[0] in DOUBLE_L) == (l in DOUBLE_L)))[:PLAN_TRY]
    f = instance_facts(1); thr = COMPOSE_GAP * f["V0"]
    plans = []
    for rank, prim in enumerate(cands):
        parts = {"V": prim}
        if prim[0] == l:
            parts["L"] = prim
        else:
            # an initial is drawn for its vowel first (ㅙ ㅚ ㅞ pull it up and left), its final second
            parts["L"] = best([k for k in D if k[0] == l],
                              lambda k: 8 * (k[1] == v) + 4 * (_vk(k[1]) == _vk(v)) + 3 * ((k[2] > 0) == (t > 0))
                              + 2 * (_tk(k[2]) == _tk(t)) + (k[2] == t))
        if t:
            parts["T"] = prim if prim[2] == t else best(
                [k for k in D if k[2] == t],
                lambda k: 8 * (k[1] == v) + 4 * (_vk(k[1]) == _vk(v)) + 2 * (k[0] == l) + ((k[0] in DOUBLE_L) == (l in DOUBLE_L)))
        geo = {}
        for role, donor in parts.items():
            g = _cgeom(1, D[donor][role])
            if donor != prim:
                g = _fit_into(g, _cgeom(1, D[prim][role]).bounds, f["V0"], f["H0"])[0]
            geo[role] = g
        rs = list(geo)
        gap = min(geo[a].distance(geo[b]) - (geo[a].intersection(geo[b]).area if geo[a].intersects(geo[b]) else 0.0)
                  for i, a in enumerate(rs) for b in rs[i + 1:])
        plans.append((min(gap, thr), -rank, prim, parts))
        if gap >= thr:
            break
    _, _, prim, parts = max(plans, key=lambda x: (x[0], x[1]))
    return prim, parts


PLAN_TRY = 12


@lru_cache(maxsize=None)
def _cgeom(m, name):
    """A component of master m as shapely (1000 UPM, y up)."""
    gs, _, u = _masters()[m]
    rp = DecomposingRecordingPen(gs); gs[name].draw(rp)
    p = pathops.Path(); pen = p.getPen()
    for op, v in rp.value:
        getattr(pen, op)(*[None if q is None else (q[0] * u, q[1] * u) for q in v])
    return geom_of(tidy(p))


def _hseg(g, L, axis):
    """Minkowski sum (L > 0) or difference (L < 0) with a segment of length |L| along x (axis 0) or y (1)."""
    from shapely import affinity
    if abs(L) < 0.05:
        return g
    h = abs(L) / 2
    sh = (lambda q, d: affinity.translate(q, d, 0)) if axis == 0 else (lambda q, d: affinity.translate(q, 0, d))
    cs = [sh(g, -h), g, sh(g, h)]
    if L > 0:
        return _union(cs)
    return _inter(_inter(cs[0], cs[1]), cs[2])


def _fit_into(g, box, V0, H0):
    """g scaled and moved into box (x0, y0, x1, y1) as its donor jamo into the primary's, its strokes kept.
    -> (geometry, (sx, sy, ox, oy, tx, ty, Lx, Ly)): scale about (ox, oy), move by (tx, ty), Minkowski with segments
    Lx, Ly (for the hints, see compose_hints)."""
    from shapely import affinity
    x0, y0, x1, y1 = g.bounds; X0, Y0, X1, Y1 = box
    sx, sy = (X1 - X0) / max(x1 - x0, 1e-6), (Y1 - Y0) / max(y1 - y0, 1e-6)
    s = math.sqrt(sx * sy)
    sx = min(max(sx, s * (1 - COMPOSE_ASPECT)), s * (1 + COMPOSE_ASPECT))
    sy = min(max(sy, s * (1 - COMPOSE_ASPECT)), s * (1 + COMPOSE_ASPECT))
    ox, oy = (x0 + x1) / 2, (y0 + y1) / 2
    tx, ty = (X0 + X1) / 2 - ox, (Y0 + Y1) / 2 - oy
    q = affinity.translate(affinity.scale(g, sx, sy, origin=(ox, oy)), tx, ty)
    Lx, Ly = (1 - sx) * V0, (1 - sy) * H0
    # the strokes given back no further than leaves COMPOSE_WHITE x V0 in every white of the jamo (EB's ㄹ
    # channels are narrower than what a 15 % smaller ㄹ gives back)
    parts = _polys(q)
    lims = piece_limits(q, COMPOSE_WHITE * V0) if (Lx > 0 or Ly > 0) else [math.inf] * len(parts)
    out = []; fs = []
    for p_, lim in zip(parts, lims):                   # each piece as far as its own whites allow
        f = 1.0
        if (Lx > 0 or Ly > 0) and lim < max(Lx, Ly) / 2:
            f = max(0.0, lim) / (max(Lx, Ly) / 2)
        r_ = _hseg(_hseg(p_, Lx * f, 0), Ly * f, 1)
        if _topo(r_) != _topo(p_):
            r_, f = p_, 0.0
        out.append(r_); fs.append(f)
    r = _union(out)
    if _topo(r) != _topo(q):
        r = q; fs = [0.0]
    f = sum(fs) / len(fs) if fs else 0.0              # the hints move by the mean share
    return r, (sx, sy, ox, oy, tx, ty, Lx * f, Ly * f)


COMPOSE_WHITE = 0.35    # x the master's stroke


COMPOSE_GAP = 0.25      # x the master's stroke: least white between a fitted donor jamo and the others
COMPOSE_HOLE = 0.5      # x the stroke, squared: a hole smaller than this where two fitted jamo overlap is filled


def _hint_ops(ops):
    """Smooth on-curve points (explicit, and implied between two off-curves) of pen ops, with their tangents:
    [(x, y, tx, ty)] in the ops' own frame."""
    out = []
    contour = []                                  # list of (on-curve point, in-tangent, out-tangent)

    def flush():
        if len(contour) >= 2:
            n = len(contour)
            for i, (pt, tin, tout) in enumerate(contour):
                if tin is None: tin = contour[i - 1][2] if False else tin
                if tin is None or tout is None: continue
                a, b = _unit(np.asarray(tin)), _unit(np.asarray(tout))
                if (a * b).sum() > math.cos(math.radians(8)):
                    t = _unit(a + b); out.append((pt[0], pt[1], t[0], t[1]))
        contour.clear()
    segs = []
    cur = start = None
    for op, v in ops:
        if op == "moveTo":
            flush(); segs = []; cur = start = v[0]
        elif op == "lineTo":
            segs.append(("L", cur, v[0])); cur = v[0]
        elif op == "qCurveTo":
            ctrl = list(v[:-1]); end = v[-1]
            if end is None:                       # a contour of off-curve points only (TrueType ellipses)
                k = len(ctrl)
                mids = [((ctrl[i][0] + ctrl[(i + 1) % k][0]) / 2, (ctrl[i][1] + ctrl[(i + 1) % k][1]) / 2) for i in range(k)]
                segs = [("Q", mids[i - 1], ctrl[i], mids[i]) for i in range(k)]
                cur = start = mids[-1]
                continue
            p0 = cur
            for i, q in enumerate(ctrl):
                e = end if i == len(ctrl) - 1 else ((q[0] + ctrl[i + 1][0]) / 2, (q[1] + ctrl[i + 1][1]) / 2)
                segs.append(("Q", p0, q, e)); p0 = e
            cur = end
        elif op == "curveTo":
            segs.append(("C", cur, v[0], v[1], v[2])); cur = v[2]
        elif op in ("closePath", "endPath"):
            if cur is not None and start is not None and cur != start:
                segs.append(("L", cur, start))
            n = len(segs)
            for i in range(n):
                sg, nx = segs[i], segs[(i + 1) % n]
                tin = np.subtract(sg[-1], sg[-2]); tout = np.subtract(nx[2], nx[1])
                if np.hypot(*tin) < 1e-9 or np.hypot(*tout) < 1e-9: continue
                contour.append((sg[-1], tin, tout))
            flush(); segs = []; cur = start = None
    return out


def _hints_affine(hints, sx, sy, ox, oy, tx, ty):
    out = []
    for x, y, a, b in hints:
        t = _unit(np.array([a * sx, b * sy]))
        out.append((ox + (x - ox) * sx + tx, oy + (y - oy) * sy + ty, t[0], t[1]))
    return out


def _hints_normal_shift(hints, g, fx, fy):
    """Move each hint along its outward normal's signs: x by sign(nx) fx, y by sign(ny) fy (a Minkowski sum with a
    horizontal / vertical segment moves every edge that way); g tells outside from inside."""
    from shapely.geometry import Point
    from shapely.prepared import prep
    if not fx and not fy:
        return hints
    G = prep(g); out = []
    for x, y, a, b in hints:
        n = np.array([b, -a])
        if G.contains(Point(x + 1.5 * n[0], y + 1.5 * n[1])): n = -n
        out.append((x + np.sign(round(n[0], 6)) * fx, y + np.sign(round(n[1], 6)) * fy, a, b))
    return out


def _hints_offset(hints, g, d, hy=0.0):
    """Move each hint by d along its outward normal (a round pen of radius d; d < 0 erodes) and by the sign of its
    normal's y times hy / 2 (the vertical pen)."""
    from shapely.geometry import Point
    from shapely.prepared import prep
    G = prep(g); out = []
    for x, y, a, b in hints:
        n = np.array([b, -a])
        if G.contains(Point(x + 1.5 * n[0], y + 1.5 * n[1])): n = -n
        out.append((x + d * n[0], y + d * n[1] + (np.sign(round(n[1], 6)) * hy / 2 if hy else 0.0), a, b))
    return out


@lru_cache(maxsize=None)
def compose(ch, m):
    """Pen ops (1000 UPM, y up) of an undrawn syllable in master m (see above)."""
    from shapely.geometry.polygon import orient as sorient
    gs = [g for g, _ in _compose_parts(ch, m).values()]
    ops = []
    from shapely.geometry import Polygon
    lim = (COMPOSE_HOLE * instance_facts(m)["V0"]) ** 2
    polys = [Polygon(q.exterior, [r for r in q.interiors if Polygon(r).area >= lim]) for q in _polys(_union(gs))]
    for poly in polys:
        poly = sorient(poly, 1.0)
        for ring in [poly.exterior] + list(poly.interiors):
            cs = list(ring.coords)[:-1]
            ops.append(("moveTo", (cs[0],)))
            ops += [("lineTo", (q,)) for q in cs[1:]]
            ops.append(("closePath", ()))
    return ops



def has(ch):
    """Parent coverage only; workers construct and validate undrawn syllables."""
    return ord(ch) in _masters()[1][1]


def outline(ch, m, k=1.0, dx=0.0, dy=0.0):
    """Master m of NanumSquareRound, scaled by k and moved by (dx, dy); y down. -> (path, advance)."""
    ops, adv = _rec(ch, m)
    p = pathops.Path(); pen = p.getPen()
    for op, v in ops:
        getattr(pen, op)(*[None if q is None else (k * q[0] + dx, -k * q[1] + dy) for q in v])
    p = tidy(p)
    return p, k * adv


@lru_cache(maxsize=None)
def _compose_parts(ch, m):
    """{role: (geometry y up, hints y up)} of an undrawn syllable in master m: each donor fitted into the primary's
    box for its role; one that comes closer than COMPOSE_GAP x V0 to another jamo is fitted into a smaller box,
    in steps of 3 % up to 30 %, taken first from the side that faces the other jamo (an initial before ㅕ ㅔ gives
    way to their left bars), then from all sides; still too close, it is cut back to the gap."""
    D = _drawn(); prim, parts = compose_plan(ch)
    f = instance_facts(m)
    gap = COMPOSE_GAP * f["V0"]
    raw, res = {}, {}
    for role, donor in parts.items():
        g = _cgeom(m, D[donor][role]); h = _chints(m, D[donor][role])
        if donor == prim:
            res[role] = (g, h, None)
        else:
            q, T = _fit_into(g, _cgeom(m, D[prim][role]).bounds, f["V0"], f["H0"])
            raw[role] = (g, h); res[role] = (q, h, T)
    for role, (g, h) in raw.items():
        box = _cgeom(m, D[prim][role]).bounds
        others = _union([q for r, (q, _, _) in res.items() if r != role])
        q, _, T = res[role]
        if not others.is_empty and q.distance(others) < gap:
            ox_, oy_ = others.centroid.x, others.centroid.y
            cx, cy = (box[0] + box[2]) / 2, (box[1] + box[3]) / 2
            W_, H_ = box[2] - box[0], box[3] - box[1]
            sides = []
            near = _inter(others, _gbuf(q, gap))
            if not near.is_empty:
                ox_, oy_ = near.centroid.x, near.centroid.y
            sides.append("x+" if ox_ > cx else "x-")
            sides.append("y+" if oy_ > cy else "y-")
            done = False
            for step in range(1, 11):
                sh = 0.03 * step
                for side in sides + ["all"]:
                    x0, y0, x1, y1 = box
                    if side == "x+": x1 -= sh * W_
                    elif side == "x-": x0 += sh * W_
                    elif side == "y+": y1 -= sh * H_
                    elif side == "y-": y0 += sh * H_
                    else:
                        x0, y0, x1, y1 = cx - (cx - x0) * (1 - sh), cy - (cy - y0) * (1 - sh), cx + (x1 - cx) * (1 - sh), cy + (y1 - cy) * (1 - sh)
                    q2, T2 = _fit_into(g, (x0, y0, x1, y1), f["V0"], f["H0"])
                    if q2.distance(others) >= gap:
                        q, T = q2, T2; done = True
                        break
                if done:
                    break
            if not done:
                # still too close at 30 % smaller: one side gives up the ink within `gap` of the other — the
                # donor, or the jamo it meets (the primary's vowel stem reaching into a larger initial, 횎), whichever
                # keeps its pieces and holes, and of those the one that loses less
                qa = _diff(q, _gbuf(others, gap))
                ok_a = _topo(qa) == _topo(q)
                qb = {r: _diff(g2, _gbuf(q, gap)) for r, (g2, _, _) in res.items() if r != role}
                ok_b = all(_topo(qb[r]) == _topo(res[r][0]) for r in qb)
                loss_a = q.area - qa.area
                loss_b = sum(res[r][0].area - qb[r].area for r in qb)
                if ok_b and (not ok_a or loss_b < loss_a):
                    for r in qb:
                        res[r] = (qb[r], res[r][1], res[r][2])
                else:
                    ps = [c for c in _polys(qa) if c.area >= 0.25 * q.area]
                    if ps:
                        q = _union(ps)
        res[role] = (q, h, T)
    out = {}
    for role, (q, h, T) in res.items():
        if T is None:
            out[role] = (q, h); continue
        sx, sy, ox, oy, tx, ty, Lx, Ly = T
        hh = _hints_affine(h, sx, sy, ox, oy, tx, ty)
        out[role] = (q, _hints_normal_shift(hh, q, Lx / 2, Ly / 2))
    return out


@lru_cache(maxsize=None)
def _chints(m, name):
    gs, _, u = _masters()[m]
    rp = DecomposingRecordingPen(gs); gs[name].draw(rp)
    ops = [(op, tuple(None if q is None else (q[0] * u, q[1] * u) for q in v)) for op, v in rp.value]
    return tuple(_hint_ops(ops))


def parent_hints(ch, m):
    """Smooth on-curve points of master m's ch with their tangents, 1000 UPM, y up."""
    if is_syllable(ch):
        gs, cm, u = _masters()[m]
        rp = DecomposingRecordingPen(gs); gs[cm[ord(ch)]].draw(rp)
        if not rp.value:
            return [q for _, h in _compose_parts(ch, m).values() for q in h]
    return _hint_ops(_rec(ch, m)[0])


# ------------------------------------------------------------------ measures without a raster
def _rect(x0, y0, x1, y1):
    p = pathops.Path()
    p.moveTo(x0, y0); p.lineTo(x1, y0); p.lineTo(x1, y1); p.lineTo(x0, y1); p.close()
    return p


def runs_row(p, y, h=0.5):
    """Ink runs [(xa, xb)] on the row y (a thin band cut through the outline)."""
    x0, _, x1, _ = p.bounds
    q = pathops.op(p, _rect(x0 - 2, y - h / 2, x1 + 2, y + h / 2), pathops.PathOp.INTERSECTION)
    rs = sorted((c.bounds[0], c.bounds[2]) for c in q.contours)
    out = []
    for a, b in rs:
        if out and a <= out[-1][1] + 0.01: out[-1] = (out[-1][0], max(out[-1][1], b))
        else: out.append((a, b))
    return out


def runs_col(p, x, h=0.5):
    _, y0, _, y1 = p.bounds
    q = pathops.op(p, _rect(x - h / 2, y0 - 2, x + h / 2, y1 + 2), pathops.PathOp.INTERSECTION)
    rs = sorted((c.bounds[1], c.bounds[3]) for c in q.contours)
    out = []
    for a, b in rs:
        if out and a <= out[-1][1] + 0.01: out[-1] = (out[-1][0], max(out[-1][1], b))
        else: out.append((a, b))
    return out


def _pct(vals, q):
    """numpy.percentile, linear."""
    v = sorted(vals); n = len(v)
    x = (n - 1) * q / 100; i = int(math.floor(x)); f = x - i
    return v[i] + f * (v[min(i + 1, n - 1)] - v[i])


def _median(v):
    return _pct(v, 50)


def vstroke(get):
    """Median width of the vowel stem of 이 니 디 … at 0.4 / 0.5 / 0.6 of the glyph height (mixlib.vstroke)."""
    ws = []
    for ch in VSET:
        p = get(ch)
        x0, y0, x1, y1 = p.bounds
        for fr in (0.4, 0.5, 0.6):
            rr = runs_row(p, y0 + fr * (y1 - y0))
            if rr: ws.append(rr[-1][1] - rr[-1][0])
    return _median(ws)


def hstroke(get):
    hs = []
    for ch in HSET:
        p = get(ch)
        x0, y0, x1, y1 = p.bounds
        for fr in (0.45, 0.5, 0.55):
            rc = runs_col(p, x0 + fr * (x1 - x0))
            if rc: hs.append(rc[-1][1] - rc[-1][0])
    return _median(hs)


def frame(get):
    """(top p10, bottom p90, centre) of the proof syllables, y down."""
    tops, bots = [], []
    for ch in FRAME_TEXT:
        b = get(ch).bounds
        tops.append(b[1]); bots.append(b[3])
    t, b = _pct(tops, 10), _pct(bots, 90)
    return t, b, (t + b) / 2


@lru_cache(maxsize=None)
def instance_facts(m):
    """V0, frame (body), frame centre c0 and H0 of master m, unscaled."""
    cache = {}
    def get(ch):
        if ch not in cache: cache[ch] = outline(ch, m)[0]
        return cache[ch]
    top, bot, c0 = frame(get)
    return {"V0": vstroke(get), "H0": hstroke(get), "body": bot - top, "c0": c0}


# ------------------------------------------------------------------ the pairing
def stem(w):
    """The Latin stem S at weight w (weights.py). LIMN_KO_STEMS="s100,...,s900" (test hook): the Hangul built for
    another weight curve, S straight between the nine (the HALF curve takes 900 to 155, see the release notes)."""
    if _KO_STEMS:
        i = min(7, max(0, (int(w) - 100) // 100))
        return _KO_STEMS[i] + (_KO_STEMS[i + 1] - _KO_STEMS[i]) * (w - 100 - 100 * i) / 100
    return W.stem(w)


_KO_STEMS = tuple(float(v) for v in __import__("os").environ.get("LIMN_KO_STEMS", "").split(",") if v.strip())


@lru_cache(maxsize=None)
def _anchor(w):
    m, k = PIN[w]
    f = instance_facts(m)
    return {"m": m, "k": k, "F": k * (f["body"] - f["V0"] / 2), "ratio": k * f["V0"] / S_AT[w]}


def _between(w, key):
    a, b = _anchor(400)[key], _anchor(700)[key]
    return a + _x(stem(w)) * (b - a)


RATIO_900 = 0.93                         # V / S at 900 (the low end of the target band), see ratio()


def ratio(w):
    """V / S: 400's below 400, 700's at 700, linear between. Above 700 it eases to RATIO_900: a dilated EB
    darkens faster than limn's Latin (grey ratio 1.26 at 800 and 1.33 at 900 with 700's V / S, against the
    designed fonts' 1.10-1.17), so the stroke gives way within its band there."""
    S = stem(w)
    if S > S_AT[700]:
        a = _anchor(700)["ratio"]
        return a + (RATIO_900 - a) * (S - S_AT[700]) / (S_END - S_AT[700])
    return _between(w, "ratio")


def frame_target(w):
    """frame - V/2 for weight w. The ink frame (not the skeleton) is held at 700's at every weight, the way the
    Latin holds its baseline and cap height as ink edges: with the skeleton held, the open syllables floated up
    to 17 above the baseline at 100 and sank to -12 at 900 (2026-09-28 fit)."""
    return ink_frame() - ratio(w) * stem(w) / 2


@lru_cache(maxsize=None)
def ink_frame():
    m, k = PIN[700]
    return k * instance_facts(m)["body"]


_PRE = {}                                # params solved once by build_hangul.py and handed to its workers


def params(w):
    """The pairing at limn weight w: master m, pen delta (limn units, < 0 erodes), scale k, baseline dy, the vertical
    pen hx that holds the contrast, and the legacy tracking (400's sets the one advance, see advance())."""
    w = int(w)
    return _PRE[w] if w in _PRE else _params(w)


@lru_cache(maxsize=None)
def _params(w):
    S = stem(w); target = ratio(w) * S
    hit = [a for a in PIN if abs(S - S_AT[a]) < 1e-6]
    if hit:
        F = frame_target(w)
        m, k = PIN[hit[0]]; f = instance_facts(m)
        return {"w": w, "S": S, "m": m, "master": MASTERS[m], "delta": 0.0, "k": k, "dy": -CENTRE - k * f["c0"],
                "track": track_of(w, 0.0), "keep": 1.0, "V": target, "ratio": target / S, "frame": k * f["body"],
                "F": F, "S0": k * f["V0"], "H0": 0.0, "hx": 0.0, "hit": True}
    sm = smooth_targets() if SMOOTH_INK else {}
    P = solve_at(w, sm.get(str(w), target))
    P["V_rule"] = target
    return P


@lru_cache(maxsize=None)
def solve_at(w, target, master=None):
    """The pairing at weight w for a vertical stroke `target`: the nearest master at the frame rule (frame - V/2 =
    ink_frame - target/2; or `master`), its pen delta and scale, and the vertical pen hx that holds the contrast."""
    S = stem(w); F = ink_frame() - target / 2
    if master is None:
        m, k, delta = _nearest(F, target)
    else:
        m = master; k, delta = _solve(m, F, target)
    f = instance_facts(m)
    # horizontal strokes: hold Hangul's contrast at CONTRAST x the Latin's (see hx_of); the vertical pen that does
    # it grows the frame by hx, so the frame rule is solved again with the frame hx / 2 lower (same master)
    H0 = hx = 0.0
    if CONTRAST:
        P0 = {"S": S, "delta": delta, "hx": 0.0, "V": target, "H0": k * f["H0"] + 2 * delta}
        H0 = hstroke_g(lambda ch: pen_steps(fillet_cusps(geom_of(outline(ch, m, k)[0]), CUSP * k * f["V0"]), P0))
        hx = hx_of(w, target, H0)
        if hx:
            k, delta = _solve(m, F - hx / 2, target)
    dy = -CENTRE - k * f["c0"]
    return {"w": w, "S": S, "m": m, "master": MASTERS[m], "delta": delta, "k": k, "dy": dy, "track": track_of(w, delta),
            "keep": 1.0, "V": target, "ratio": target / S, "frame": k * f["body"] + 2 * delta + hx, "F": F,
            "S0": k * f["V0"], "H0": H0, "hx": hx}


@lru_cache(maxsize=None)
def parent_topo(ch, m):
    """(pieces, holes) of master m's ch."""
    return _topo(geom_of(outline(ch, m)[0]))


@lru_cache(maxsize=None)
def ref_topo(ch):
    """The pieces and holes a glyph keeps at every weight: those most of the four masters draw it with (R's on a
    tie; a composed syllable's donor can meet another jamo in one master and not in the others)."""
    import collections
    ts = [parent_topo(ch, m) for m in range(len(MASTERS))]
    c = collections.Counter(ts)
    top = max(c.values())
    return ts[1] if c[ts[1]] == top else next(t for t in ts if c[t] == top)


def master_for(ch, P):
    """P, or the pairing at P's weight and stroke with the nearest other master when P's master draws ch with other
    pieces or holes than ref_topo() (EB's ㄵ ㄽ touch, B's 겡 closes a counter, L's 걩 opens one): no weight then
    joins or splits what the rest keep apart (topology is the same at every weight)."""
    want = ref_topo(ch)
    if P.get("hit") or parent_topo(ch, P["m"]) == want:
        return P
    order = sorted(range(len(MASTERS)), key=lambda m: abs(_solve(m, P["F"], P["V"])[1]))
    for m in order:
        if parent_topo(ch, m) == want:
            Q = dict(solve_at(P["w"], P["V"], m)); Q["V_rule"] = P.get("V_rule", P["V"])
            return Q
    return P


# ------------------------------------------------------------------ one smooth weight rhythm (release QA S12)
# The stroke rule alone set the grey in a zigzag (Hangul / Latin grey 1.125 1.117 1.107 1.114 1.128 1.129 1.135
# 1.134 1.128 from 100 to 900, the syllables' ink step 1.14 1.07 1.04 1.13 1.00 1.09 0.88 0.66 of the mean): eroding
# the next master gives less ink than dilating the last at the same stem, so the ink fell back at each switch. Now
# the stroke rule gives each weight a first ink on the proof syllables (INK_TEXT); a quadratic in S through the
# nine is the target, and each weight's stroke is solved again (secant) to meet it. The stroke moves by at most
# SMOOTH_SPAN, the size, centre and contrast rules are untouched. Solved once by build_hangul.py (in parallel) and
# kept in tools/hangul/.params-cache.json; LIMN_KO_SMOOTH=0 turns it off.
SMOOTH_INK = __import__("os").environ.get("LIMN_KO_SMOOTH", "1") != "0"
INK_TEXT = sorted(set(FRAME_TEXT))
SMOOTH_VERSION = "ink-2026-09-30d"
SMOOTH_SPAN = 0.05       # the smoothed stroke stays within 5 % of the stroke rule
_SMOOTH_TARGETS = None   # resolved targets passed to pairing workers, also in a disk-cache-disabled build


def corpus_ink(w, P):
    """Mean ink of the proof syllables at pairing P (the pen's outline, before fitting)."""
    tot = 0.0
    for ch in INK_TEXT:
        tot += pen_geom(w, ch, P)[0].area
    return tot / len(INK_TEXT)


def _raw_ink(w):
    t = ratio(w) * stem(w)
    return w, t, corpus_ink(w, solve_at(w, t))


def _hit_ink(args):
    """The stroke whose ink meets the target (secant on the stroke), within SMOOTH_SPAN of the stroke rule: where the
    clearance holds the ink back (dense syllables at 800-900) the stroke is not pushed further to make it up."""
    w, want, t0 = args
    a, b = (1 - SMOOTH_SPAN) * t0, (1 + SMOOTH_SPAN) * t0
    fa, fb = corpus_ink(w, solve_at(w, a)) - want, corpus_ink(w, solve_at(w, b)) - want
    if fa > 0 or fb < 0:
        return w, (a if fa > 0 else b)
    for _ in range(10):
        c = b - fb * (b - a) / (fb - fa) if fb != fa else (a + b) / 2
        c = min(max(c, a + 0.05 * (b - a)), b - 0.05 * (b - a))
        fc = corpus_ink(w, solve_at(w, c)) - want
        if abs(fc) < 1e-4 * want:
            return w, c
        if fc < 0: a, fa = c, fc
        else: b, fb = c, fc
    return w, (a + b) / 2


def _smooth_key():
    """Automatically invalidate strokes when any actual producer, parent, dependency or rule input changes."""
    return HC.identity({"version": SMOOTH_VERSION, "inputs": HC.fingerprint(HERE, latin=False),
                        "stems": [stem(w) for w in WEIGHTS], "contrast": CONTRAST,
                        "gap": GAP_MIN, "counter": COUNTER_MIN, "clearance": CLEAR_PAD})


def _cache():
    """Read bounded smoothing records; LIMN_KO_CACHE=0 bypasses disk without changing smoothing."""
    p = FDIR / ".params-cache.json"
    C = HC.read_json(p) if HC.cache_enabled() else None
    return p, C if isinstance(C, dict) else {}


def _cached_targets():
    """Return complete finite nine-weight cached targets, or None for malformed/incompatible records."""
    if not HC.cache_enabled():
        return None
    _, C = _cache()
    entry = C.get(_smooth_key())
    if not isinstance(entry, dict) or set(entry) != {"targets", "raw_ink", "want_ink", "sha256"}:
        return None
    payload = {k: v for k, v in entry.items() if k != "sha256"}
    try:
        if HC.identity(payload) != entry["sha256"]:
            return None
        targets = entry.get("targets")
        if (not isinstance(targets, dict) or set(targets) != {str(w) for w in WEIGHTS}
                or not all(type(v) in (int, float) and math.isfinite(v) and v > 0 for v in targets.values())):
            return None
    except (ValueError, TypeError, OverflowError):
        return None
    return targets


def smooth_solve(mapper=map):
    """{str(w): stroke} for every family weight; mapper runs the per-weight solves (a Pool's map in the build)."""
    global _SMOOTH_TARGETS
    key = _smooth_key() if HC.cache_enabled() else None
    raw = list(mapper(_raw_ink, WEIGHTS))
    X = np.array([stem(w) for w, _, _ in raw]); Y = np.array([i for _, _, i in raw])
    c = np.polyfit(X, Y, 2)
    want = {w: float(np.polyval(c, stem(w))) for w, _, _ in raw}
    res = dict(mapper(_hit_ink, [(w, want[w], t) for w, t, _ in raw]))
    out = {str(w): res[w] for w in res}
    _SMOOTH_TARGETS = out
    if HC.cache_enabled():
        if _smooth_key() != key:
            raise RuntimeError("Hangul inputs changed during smoothing; retry with frozen inputs")
        path = FDIR / ".params-cache.json"
        try:
            with HC.key_lock(path.with_suffix(".lock")):
                _, C = _cache()
                C = dict(list(C.items())[-31:])
                entry = {"targets": out, "raw_ink": {str(w): i for w, _, i in raw},
                         "want_ink": {str(w): want[w] for w in want}}
                entry["sha256"] = HC.identity(entry)
                C[key] = entry
                try:
                    HC.atomic_json(path, C)
                except (ValueError, TypeError):
                    # Disposable history must not prevent publishing this valid solve (e.g. byte-limit overflow).
                    HC.atomic_json(path, {key: entry})
        except (OSError, ValueError, TypeError) as ex:
            print(f"smoothing cache unavailable: {ex}", flush=True)
    return out


@lru_cache(maxsize=None)
def smooth_targets():
    """Use resolved or valid cached strokes, otherwise solve the same smoothing rule cold."""
    if _SMOOTH_TARGETS is not None:
        return _SMOOTH_TARGETS
    targets = _cached_targets()
    if targets is not None:
        return targets
    return smooth_solve()


def _solve(m, F, target):
    """k and pen delta for master m holding frame - V / 2 = F and the stroke at target (the pen moves every edge
    by delta: k V0 + 2 delta = target and k B + delta = F)."""
    f = instance_facts(m); B = f["body"] - f["V0"] / 2
    k = (2 * F - target) / (2 * B - f["V0"])
    return k, F - k * B


def _nearest(F, target):
    """The master whose stroke is nearest the target at the frame rule: (m, k, delta) with the smallest |delta|."""
    best = None
    for m in range(len(MASTERS)):
        k, d = _solve(m, F, target)
        if best is None or abs(d) < abs(best[2]):
            best = (m, k, d)
    return best


def _runs_g(g, x=None, y=None):
    """Ink runs of a shapely outline along the row y or the column x: [(a, b)] sorted."""
    from shapely.geometry import LineString
    x0, y0, x1, y1 = g.bounds
    L = LineString([(x0 - 5, y), (x1 + 5, y)]) if y is not None else LineString([(x, y0 - 5), (x, y1 + 5)])
    q = g.intersection(L)
    segs = [s for s in getattr(q, "geoms", [q]) if s.geom_type == "LineString" and s.length > 0]
    k = 0 if y is not None else 1
    return sorted((s.bounds[k], s.bounds[k + 2]) for s in segs)


def vstroke_g(get):
    """vstroke() on shapely outlines: the vowel stem of 이 니 디 ... at 0.4 / 0.5 / 0.6 of the height, median."""
    ws = []
    for ch in VSET:
        g = get(ch); x0, y0, x1, y1 = g.bounds
        for fr in (0.4, 0.5, 0.6):
            rr = _runs_g(g, y=y0 + fr * (y1 - y0))
            if rr: ws.append(rr[-1][1] - rr[-1][0])
    return _median(ws)


def hstroke_g(get):
    hs = []
    for ch in HSET:
        g = get(ch); x0, y0, x1, y1 = g.bounds
        for fr in (0.45, 0.5, 0.55):
            rc = _runs_g(g, x=x0 + fr * (x1 - x0))
            if rc: hs.append(rc[-1][1] - rc[-1][0])
    return _median(hs)


# Horizontal-stroke contrast (2026-09-28). NanumSquareRound draws its horizontals about 0.85 of its verticals and
# Quicksand its crossbars about 0.96-1.09 of its stems, so limn's Hangul read lighter across than its Latin: its
# contrast (ㅡ / ㅣ) was 0.72-0.92 of the Latin's (H bar / l stem), 0.72 at 100. The Korean fonts designed with their
# own Latin keep theirs near 0.94 from 300 to 900 (Pretendard, SUIT, Noto Sans KR, IBM Plex Sans KR measured at
# every weight they have, /tmp/limn-refs900: medians 0.95 0.94 0.93 0.94 0.94 0.945 0.94 at 300-900) and near 1.0
# at the thin end (0.98 at 200, 1.01 at 100): Hangul horizontals a little lighter than the Latin's, never as light
# as limn's were. hx_of() gives the vertical pen (a vertical segment: horizontals thicken, verticals only
# lengthen) that puts limn's at contrast_target(w): CONTRAST from 300 up, rising straight to 1.0 at 100. The Latin bar contrast is the weight rule's (weights.contrast, Quicksand's o) x BAR_O: the H bar / l stem
# measured on the built Latin is 1.045-1.06 x that rule from 200 to 900 (1.10 at 100). The anchors (R at 68.4,
# EB at 120: the brand's 림) keep NanumSquareRound's own strokes. LIMN_KO_CONTRAST=0 turns it off. The grey this
# adds (Hangul paragraph ink / Latin: 1.10 at 400, 1.17 at 700, 1.18 at 900) stays at or under the references'
# medians at the same weights (1.12, 1.17, 1.22), which darken with weight as limn's does.
CONTRAST = float(__import__("os").environ.get("LIMN_KO_CONTRAST", 0.94))
BAR_O = 1.05


def contrast_target(w):
    """Hangul contrast / Latin contrast at weight w (the references' medians, see above)."""
    return CONTRAST + (1.0 - CONTRAST) * max(0.0, 300 - w) / 200


def hx_of(w, V, H0):
    """Vertical pen length for weight w: Hangul H = contrast_target x (Latin bar / stem) x V; under a unit, 0."""
    hx = contrast_target(w) * BAR_O * W.contrast(w) * V - H0
    return round(hx, 2) if abs(hx) >= 1.0 else 0.0


PEN_STEP = 3.0                           # the dilation grows in levels of at most 3 units of pen


def bop(a, b, how):
    """pathops boolean, retried with a tiny shift when skia gives up; only for simple shapes (림's stem)."""
    for e in (0.0, 0.011, -0.023, 0.037):
        try:
            r = pathops.op(a, b.transform(1, 0, 0, 1, e, 0.7 * e) if e else b, how)
            r.convertConicsToQuads()
            return orient(r)
        except pathops.PathOpsError:
            continue
    return pathops.Path(a)


# shapely helpers kept for build_font.py (to_geom: the Latin's own geometry checks) and the brand path.
FLAT = 8                                  # segments per quadratic when flattening (to_geom)


def to_geom(p):
    """pathops outline -> shapely (Multi)Polygon, filled by even-odd nesting of its contours."""
    import shapely
    from shapely.geometry import Polygon
    g = None
    for c in p.contours:
        pts = W._flat(c, steps=FLAT)
        if len(pts) < 3: continue
        ring = Polygon(pts).buffer(0)
        if ring.is_empty: continue
        g = ring if g is None else g.symmetric_difference(ring)
    return g if g is not None else Polygon()


def _area(p):
    """Filled area of an oriented outline (holes negative)."""
    cs = list(p.contours)
    if not cs: return 0.0
    big = max(cs, key=lambda c: abs(c.area))
    return sum(abs(c.area) * (1 if c.clockwise == big.clockwise else -1) for c in cs)


def _mindist(A, B):
    """Nearest distance between two outlines (flattened points); for the checks."""
    pa = [q for c in A.contours for q in W._flat(c, steps=8)]
    pb = [q for c in B.contours for q in W._flat(c, steps=8)]
    if not pa or not pb:
        return 1e9
    if True:
        a = np.asarray(pa); b = np.asarray(pb); best = 1e18
        for s in range(0, len(a), 256):
            best = min(best, float(((a[s:s + 256, None, :] - b[None, :, :]) ** 2).sum(-1).min()))
        return best ** 0.5
    return min((ax - bx) ** 2 + (ay - by) ** 2 for ax, ay in pa for bx, by in pb) ** 0.5



def clean(p, S):
    """Drop specks and pinholes smaller than a tenth-stem square (build_font's rule)."""
    lim = (0.1 * S) ** 2
    cs = list(p.contours)
    keep = [c for c in cs if abs(c.area) >= lim]
    if len(keep) == len(cs) or not keep:
        return p
    q = pathops.Path()
    for c in keep: q.addPath(c)
    return orient(q)


# ------------------------------------------------------------------ the pen, release rules (2026-09-30)
# The QA before the public release (outlines B1 B2 S11 S12, visual B1-B3) found the pen above wanting at the ends of
# the axis: every weight came out as short straight segments (GEOS flattens, nothing fitted curves back: ㅇ ○ faceted
# from 72 px, the files bloated), the capped dilation left slits and pinholes in the ㅅ ㅈ ㅊ crotch (its white
# wedge is narrow at the apex, so the cap kept it while the flanks grew around it), and at 700-900 it let jamo meet
# and ㅃ counters close. The pen below replaces it for every family weight (the brand's anchor weights still take
# NanumSquareRound's own outline unchanged, see glyph()):
#   1. the parent at the pairing's scale, flattened finely (G_FLAT), with its cusps filleted: NanumSquareRound draws
#      the ㅅ crotch as a cusp (both edges arrive nearly vertical), which a round pen turns into a spike (eroding) or
#      a slit (dilating). Every concave corner sharper than about 70 degrees takes a fillet of CUSP x the stroke.
#   2. eroding: part by part, as before. Dilating (and the vertical pen that holds the contrast, when it adds): the
#      ink grows level by level only into white that stays at least GAP_MIN x S wide after both sides have grown
#      (a white of width w gives each side (w - GAP_MIN S) / 2 at most), except the tips of a white that touch one
#      piece only and are small (the corners and crotches of a single stroke), which fill as a round pen fills them.
#   3. clearance: where the parent itself is closer than GAP_MIN x S (NanumSquareRound EB sets its dense syllables
#      tighter than that), both pieces are cut back symmetrically to it, and the cut corners rounded; a counter that
#      holds less than COUNTER_MIN x S is opened to it.
#   4. clean: GEOS make_valid, holes and pieces under (SPECK S)^2 dropped, zero-width spikes and slits closed.
#   5. curves: every ring is fitted with quadratic splines (corners kept, straight sides as lines and exactly
#      horizontal / vertical when within SNAP_DEG, on-curve points at the extrema), within FIT_TOL + QUAD_TOL of
#      the pen's outline; then rounded to units and checked again (valid, same pieces and holes, within 1.2).
G_FLAT = 2.0            # units: longest chord when the parent's curves are flattened for GEOS
G_ARC = 16              # segments per quarter circle in every GEOS buffer (chords stay under the fit's LINE_MIN)
GAP_MIN = 0.3           # x S: white between two pieces of a glyph (jamo, or the parts of one), every weight
COUNTER_MIN = 0.3       # x S: inscribed-circle diameter of the smallest counter
CLEAR_PAD = 3.0         # units added to both while building: fitting (1.0) and rounding (0.7) move each side
SPECK = 0.3             # (SPECK S)^2: holes and pieces smaller than this are dropped
CUSP = 0.2              # fillet radius at concave corners sharper than ~70 degrees, x the master's stroke (x k)
CUSP_AREA = 0.45        # a closing's added piece is a cusp when larger than this x r^2 (a 90-degree corner adds 0.21)
TIP_AREA = 1.6          # a narrow white of one piece fills as a round pen fills it when under this x T^2


def _polys(g):
    if g is None or g.is_empty:
        return []
    if g.geom_type == "Polygon":
        return [g]
    out = []
    for q in getattr(g, "geoms", []):
        out += _polys(q)
    return out


GRID = 0.001           # units: precision grid of the pen's booleans (GEOS snap-rounding: no zero-area slivers)


def _areal(g):
    """The polygons of a boolean's result (a GEOS overlay may add lines and points where edges touch)."""
    from shapely.geometry import MultiPolygon, Polygon
    ps = _polys(g)
    if not ps:
        return Polygon()
    return ps[0] if len(ps) == 1 else MultiPolygon(ps)


def _union(gs):
    import shapely
    gs = [_areal(g) for g in gs if g is not None and not g.is_empty]
    gs = [g for g in gs if not g.is_empty]
    if not gs:
        from shapely.geometry import Polygon
        return Polygon()
    return _areal(shapely.union_all(gs, grid_size=GRID))


def _diff(a, b):
    import shapely
    return _areal(shapely.difference(_areal(a), _areal(b), grid_size=GRID))


def _inter(a, b):
    import shapely
    return _areal(shapely.intersection(_areal(a), _areal(b), grid_size=GRID))


def _gbuf(g, d, join="round"):
    return g.buffer(d, quad_segs=G_ARC, join_style=join, cap_style="round", mitre_limit=4.0)


def _open(g, r):
    return _gbuf(_gbuf(g, -r), r)


def _flat_rings(p, step=G_FLAT):
    """pathops outline -> [[(x, y)]], every curve cut into chords of at most `step` units."""
    rings = []
    for c in p.contours:
        pts, cur = [], None
        for verb, a in c.segments:
            if verb == "moveTo":
                cur = a[0]; pts = [cur]
            elif verb == "lineTo":
                cur = a[0]; pts.append(cur)
            elif verb == "qCurveTo":
                ctrl = list(a[:-1]); end = a[-1]
                if end is None:                    # all off-curve: start at the implied midpoint
                    end = ((ctrl[-1][0] + ctrl[0][0]) / 2, (ctrl[-1][1] + ctrl[0][1]) / 2)
                    cur = end; pts.append(end)
                p0 = cur
                for i, q in enumerate(ctrl):
                    e = end if i == len(ctrl) - 1 else ((q[0] + ctrl[i + 1][0]) / 2, (q[1] + ctrl[i + 1][1]) / 2)
                    L = math.dist(p0, q) + math.dist(q, e)
                    n = max(2, math.ceil(L / step))
                    for k in range(1, n + 1):
                        t = k / n; u = 1 - t
                        pts.append((u * u * p0[0] + 2 * u * t * q[0] + t * t * e[0], u * u * p0[1] + 2 * u * t * q[1] + t * t * e[1]))
                    p0 = e
                cur = end
            elif verb == "curveTo":
                c1, c2, e = a; p0 = cur
                L = math.dist(p0, c1) + math.dist(c1, c2) + math.dist(c2, e)
                n = max(2, math.ceil(L / step))
                for k in range(1, n + 1):
                    t = k / n; u = 1 - t
                    pts.append((u ** 3 * p0[0] + 3 * u * u * t * c1[0] + 3 * u * t * t * c2[0] + t ** 3 * e[0],
                                u ** 3 * p0[1] + 3 * u * u * t * c1[1] + 3 * u * t * t * c2[1] + t ** 3 * e[1]))
                cur = e
        if len(pts) > 2 and pts[0] == pts[-1]:
            pts.pop()
        if len(pts) >= 3:
            rings.append(pts)
    return rings


def geom_of(p, step=G_FLAT):
    """pathops outline -> shapely (Multi)Polygon by even-odd nesting, curves flattened to `step`."""
    from shapely.geometry import Polygon
    g = None
    for pts in _flat_rings(p, step):
        ring = Polygon(pts).buffer(0)
        if ring.is_empty:
            continue
        g = ring if g is None else g.symmetric_difference(ring)
    return g if g is not None else Polygon()


def _cusps(g, L=3.0, turn=100.0):
    """Cusps of the ink: boundary vertices where the ring turns more than `turn` degrees within +-L units and the
    chord across that turn lies in the white (a white wedge narrower than 180 - turn degrees: the ㅅ crotch of
    NanumSquareRound measures 55-65 there, a square inner corner 90)."""
    from shapely.geometry import Point
    out = []
    for poly in _polys(g):
        for ring in [poly.exterior] + list(poly.interiors):
            P = np.asarray(ring.coords)[:-1]
            n = len(P)
            if n < 5: continue
            seg = np.hypot(*(np.roll(P, -1, 0) - P).T); s_ = np.concatenate([[0.0], np.cumsum(seg)]); tot = s_[-1]
            for i in range(n):
                a = _ring_at(P, s_, (s_[i] - L) % tot); b = _ring_at(P, s_, (s_[i] + L) % tot)
                u, v = P[i] - a, b - P[i]
                if np.hypot(*u) < 1e-6 or np.hypot(*v) < 1e-6: continue
                t = abs(math.degrees(math.atan2(u[0] * v[1] - u[1] * v[0], u[0] * v[0] + u[1] * v[1])))
                if t > turn and not g.contains(Point((a + b) / 2)):
                    out.append(Point(P[i]))
    return out


def _ring_at(P, s_, t):
    j = int(np.searchsorted(s_, t, side="right") - 1); j = min(max(j, 0), len(P) - 1)
    L = s_[j + 1] - s_[j]
    f = 0.0 if L <= 0 else (t - s_[j]) / L
    return P[j] + f * (P[(j + 1) % len(P)] - P[j])


def fillet_cusps(g, r):
    """Fill the cusps of the ink (the ㅅ ㅈ ㅊ crotch) with a fillet of radius r: the bits a closing of that piece
    adds at a cusp, nothing else (a closing alone would fill every channel and counter narrower than 2 r)."""
    if r <= 0:
        return g
    cusps = _cusps(g)
    if not cusps:
        return g
    parts = _polys(g)
    out = []
    for q in parts:
        cs = [c for c in cusps if q.distance(c) < 0.5]
        if not cs:
            out.append(q); continue
        c = _gbuf(_gbuf(q, r), -r)
        add = [a for a in _polys(_diff(c, q)) if any(a.distance(x) < 1.5 for x in cs)]
        keep = []
        for a in add:                       # never close or split a counter (ㅉ's small triangle has cusps)
            t = _union([q] + keep + [a])
            if _topo(t) == _topo(q):
                keep.append(a)
        out.append(_union([q] + keep) if keep else q)
    return _union(out)


def erode_parts(g, delta, keep=0.0):
    """A round pen of radius -delta eroding each part; a part thinner than the pen (the small ㅎ of ㄶ ㅀ at 100)
    takes the largest pen that keeps it whole, and (keep > 0) that leaves every stroke of it at least `keep` wide
    (NanumSquareRound draws the finals of its densest syllables, ㄽ ㄾ, thinner than the rest: the whole pen
    would leave hairlines)."""
    def fine(t, n0, area):
        if not (t.geom_type == "Polygon" and len(t.interiors) == n0):
            return False
        if keep <= 0:
            return True
        o = _open(t, keep / 2)
        return _topo(o) == (1, n0) and o.area >= KEEP_AREA * t.area
    out = []
    for part in _polys(g):
        n0 = len(part.interiors)
        q = _gbuf(part, delta)
        if not fine(q, n0, part.area):
            lo, hi = 0.0, -delta                    # the largest pen that keeps the part whole (bisection)
            for _ in range(10):
                mid = (lo + hi) / 2
                if fine(_gbuf(part, -mid), n0, part.area): lo = mid
                else: hi = mid
            q = _gbuf(part, -lo) if lo > 0 else part
        out.append(q)
    return _union(out)


KEEP_STROKE = 0.6       # x the stroke: the thinnest stroke an eroding pen leaves
KEEP_AREA = 0.9         # an opening of half the least stroke leaves this share of a part: no stroke thinner


def _msum(g, e, h):
    """Minkowski sum with a disc of radius e and a vertical segment of length h (copies every MSUM_STEP along it)."""
    from shapely import affinity
    q = _gbuf(g, e) if e > 0 else g
    if h > 0:
        n = max(2, math.ceil(h / MSUM_STEP))
        q = _union([affinity.translate(q, 0, -h / 2 + h * i / n) for i in range(n + 1)])
    return q


MSUM_STEP = 1.5         # units between the copies of a vertical Minkowski sum


def vshrink(g, h):
    """Minkowski difference with a vertical segment of length h: horizontals lose h, verticals h / 2 at each end."""
    from shapely import affinity
    if h <= 0:
        return g
    return affinity.translate(g, 0, -h / 2).intersection(g).intersection(affinity.translate(g, 0, h / 2))


AXIS_STEP = 1.5         # units: boundary sampling of the white's medial axis (Voronoi of the samples)
AXIS_KEEP = 2.5         # arc / chord above which two points of one outline face each other across a channel
CURV_L = 6.0            # units either side over which a boundary point's curvature is read
AXIS_SIMPLIFY = 1.5     # units: the medial axis is thinned to this before the band is drawn around it


def _samples(g):
    """Boundary samples of every outer outline (counters are held apart, see pen_steps), every AXIS_STEP units:
    (points, ring, piece, arc position, ring length, convexity = curvature where the ink turns outward, else 0)."""
    from shapely.geometry.polygon import orient as sorient
    pts, ring, piece, arc, L, conv = [], [], [], [], [], []
    for pi, poly in enumerate(_polys(g)):
        P = np.asarray(sorient(poly, 1.0).exterior.coords)
        seg = np.hypot(*np.diff(P, axis=0).T); tot = float(seg.sum())
        if tot <= 0: continue
        n = max(8, int(math.ceil(tot / AXIS_STEP)))
        t = np.linspace(0, tot, n, endpoint=False)
        cs = np.concatenate([[0.0], np.cumsum(seg)])
        j = np.clip(np.searchsorted(cs, t, side="right") - 1, 0, len(seg) - 1)
        f = ((t - cs[j]) / np.where(seg[j] > 0, seg[j], 1))[:, None]
        Q = P[j] + f * (P[j + 1] - P[j])
        k = max(1, int(round(CURV_L / (tot / n))))
        u = Q - np.roll(Q, k, 0); v = np.roll(Q, -k, 0) - Q
        turn = np.arctan2(u[:, 0] * v[:, 1] - u[:, 1] * v[:, 0], (u * v).sum(1))
        pts.append(Q); ring += [pi] * n; piece += [pi] * n; arc.append(t); L += [tot] * n
        conv.append(np.maximum(turn, 0) / (2 * k * tot / n))
    if not pts:
        return None
    return np.vstack(pts), np.array(ring), np.array(piece), np.concatenate(arc), np.array(L), np.concatenate(conv)


def clearance(g, e, wmin):
    """The white a round pen of radius e must leave around g, and the ink it must give up, as one region (shapely):
    discs of wmin / 2 along the medial axis of the white where it is narrower than wmin + 2 e (Voronoi of the
    boundary samples). Between two pieces the white after the pen is wmin exactly where it is short, placed so the
    flatter side keeps its growth and the rounder side (a stroke end, measured by convexity) gives up the ink: where
    the parent itself is closer than wmin, the ends are shortened, not the stems dented. Across a channel of one
    piece (ㄹ, ㅐ, ㅂ's notch: the boundary between the two nearest points longer than AXIS_KEEP x their distance)
    the band only stops the growth. The spurs into a corner or a crotch of one stroke (arc / chord 1.4-2.3 for
    60-90 degrees) hold nothing: they fill as a round pen fills them. -> (band, channel band)."""
    import shapely
    from scipy.spatial import Voronoi
    from shapely.geometry import LineString, MultiLineString, Polygon
    smp = _samples(g)
    if smp is None or len(smp[0]) < 8:
        return Polygon(), Polygon()
    X, ring, piece, arc, L, conv = smp
    vor = Voronoi(X)
    rp = vor.ridge_points; rv = np.array([v if len(v) == 2 else [-1, -1] for v in vor.ridge_vertices])
    ok = (rv >= 0).all(1)
    a, b = rp[:, 0], rp[:, 1]
    Vx = vor.vertices
    ch = np.hypot(*(X[a] - X[b]).T)
    ds = np.abs(arc[a] - arc[b]); ds = np.minimum(ds, L[a] - ds)
    other = ok & (piece[a] != piece[b])
    channel = ok & (ring[a] == ring[b]) & (ch > 0.5) & (ds > AXIS_KEEP * np.maximum(ch, 1e-9))
    reach = wmin / 2 + e + 1.0
    rA = np.hypot(*(Vx[np.maximum(rv[:, 0], 0)] - X[a]).T)
    rB = np.hypot(*(Vx[np.maximum(rv[:, 1], 0)] - X[a]).T)
    near = np.minimum(rA, rB) < reach
    # the rounder side's share of a cut (a stroke end against a stem: all of it; two like sides: half)
    ca, cb = conv[a], conv[b]
    wa = 0.5 + 0.5 * np.clip((ca - cb) / (ca + cb + CURV_EVEN), -1, 1)
    out = []
    for mask, shift in ((other & near, True), (channel & near, False)):
        idx = np.where(mask)[0]
        if not len(idx):
            out.append(Polygon()); continue
        # per Voronoi vertex: where the band's centre goes (averaged over the kept ridges that meet there)
        acc = {}
        for col in (0, 1):
            vv = rv[idx, col]
            C = Vx[vv]
            if shift:
                A, B = X[a[idx]], X[b[idx]]
                w = np.hypot(*(B - A).T); u = (B - A) / np.maximum(w, 1e-9)[:, None]
                r = np.hypot(*(C - A).T)
                slack = 2 * r - wmin                               # > 0: growth to share, < 0: ink to give up
                share = wa[idx]
                ga = np.where(slack >= 0, np.clip(slack * (1 - share), 0, e), slack * share)
                gb = np.where(slack >= 0, np.clip(slack - ga, 0, e), slack * (1 - share))
                ga = np.where(slack >= 0, np.clip(slack - gb, 0, e), ga)
                # the white after the pen runs from A + ga u to B - gb u (along the feet's line); its centre, moved
                # onto the ridge's own normal offset (C - its projection)
                mid = A + u * ((ga + w - gb) / 2)[:, None]
                proj = A + u * ((C - A) * u).sum(1)[:, None]
                C = mid + (C - proj)
            for k, v in enumerate(vv):
                acc.setdefault(int(v), []).append(C[k])
        segs = [(int(rv[i, 0]), int(rv[i, 1])) for i in idx]
        merged = shapely.line_merge(MultiLineString([(tuple(Vx[p]), tuple(Vx[q])) for p, q in segs]))
        key = {(round(float(Vx[v][0]), 6), round(float(Vx[v][1]), 6)): np.mean(cs, axis=0) for v, cs in acc.items()}
        lines = []
        for ln in getattr(merged, "geoms", [merged]):
            cs = [key.get((round(x, 6), round(y, 6)), (x, y)) for x, y in ln.coords]
            if len(cs) >= 2:
                lines.append(LineString(cs).simplify(AXIS_SIMPLIFY))
        band = MultiLineString(lines).buffer(wmin / 2, quad_segs=G_ARC) if lines else Polygon()
        out.append(band)
    return out[0], out[1]


CURV_EVEN = 0.004       # 1 / units: two sides whose curvatures differ by less than this share a cut evenly


def piece_limits(g, wmin):
    """For every piece of g (in _polys order), the largest pen it can take: half of what its nearest white beyond
    wmin leaves — the nearest other piece (the two share it) and the narrowest channel of its own outline (a white
    between two parts of one outline, AXIS_KEEP). One pen per piece: a stroke that faces a narrow white grows no
    more along its length than there, so no end swells past its middle."""
    import shapely
    from scipy.spatial import Voronoi
    from shapely.prepared import prep
    ps = _polys(g); n = len(ps)
    lim = [math.inf] * n
    for i in range(n):
        for j in range(i + 1, n):
            d = ps[i].distance(ps[j])
            if d < 4 * wmin:
                x = (d - wmin) / 2
                lim[i] = min(lim[i], x); lim[j] = min(lim[j], x)
    smp = _samples(g)
    if smp is not None and len(smp[0]) >= 8:
        X, ring, piece, arc, L, conv = smp
        vor = Voronoi(X)
        a, b = vor.ridge_points[:, 0], vor.ridge_points[:, 1]
        ch = np.hypot(*(X[a] - X[b]).T)
        ds = np.abs(arc[a] - arc[b]); ds = np.minimum(ds, L[a] - ds)
        cand = np.where((ring[a] == ring[b]) & (ch > 0.5) & (ds > AXIS_KEEP * ch) & (ch < 4 * wmin))[0]
        G = prep(g)
        for k in cand:
            mid = (X[a[k]] + X[b[k]]) / 2
            if G.contains(shapely.points(mid)):
                continue                                  # across a stroke, not a white
            i = piece[a[k]]
            lim[i] = min(lim[i], (ch[k] - wmin) / 2)
    return lim


def pen_steps(g, P, lighter=0.0, local=None):
    """The pen at weight P on the parent g (shapely, filleted): steps 2-4 of the section's head. lighter: that much
    less pen (units), for a glyph whose ink would otherwise not stay under the next weight's (build_hangul.py: a
    dense syllable the clearance holds back at the heavier weight is held back as much here). local: past the
    pen each piece takes whole, the rest of it too, held back only in bands along the whites it must keep (a dense
    syllable at 800-900 whose one pen per piece leaves it lighter than the weight below: build_hangul.py asks).
    None (the default): the local pen whenever its whites hold a piece back; False: one pen per piece only."""
    from shapely.geometry import Polygon, box as sbox
    S, V = P["S"], P["V"]
    wmin = GAP_MIN * S + CLEAR_PAD
    cmin = COUNTER_MIN * S + CLEAR_PAD
    d, hx = P["delta"] - lighter, P["hx"]
    base = g
    if d < 0:
        base = erode_parts(g, d, KEEP_STROKE * V)
        # eroding sharpens every round corner by -d: give the ends back their roundness (free ends are round),
        # with a radius under half the thinnest stroke (the horizontals, P["H0"] before the vertical pen)
        thin = min(V, P.get("H0") or V)
        base = _open_parts(base, min(-d, END_ROUND * thin))
    e, h = max(d, 0.0), max(hx, 0.0)
    x0, y0, x1, y1 = base.bounds
    white = _diff(sbox(x0 - 400, y0 - 400, x1 + 400, y1 + 400), base)
    held = False
    if e > 0 or h > 0:
        # one pen per piece, as large as its whites allow (piece_limits); the round pen and the vertical one
        # shrink together, so a piece keeps the weight's contrast
        grown = []
        for q, lim in zip(_polys(base), piece_limits(base, wmin)):
            f = 1.0 if lim >= e + h / 2 else max(0.0, lim) / (e + h / 2)
            held |= f < 1.0
            grown.append(_msum(q, e * f, h * f) if f > 0 else q)
        out = _union(grown)
        # A piece its whites hold back grows everywhere else (the local pen), not nowhere: held back as a whole,
        # the two halves of ㅉ (4 units apart in R, touching in EB) kept 쪽 at R's weight at 900, and the ink
        # order then held every weight under it (쪽 at 0.30 of its parent's ink against 가). 2026-10-01
        if local or (local is None and held):
            lband, lchan = clearance(base, e + h / 2, wmin)
            keep = _inter(_union([lband, lchan]), white)
            out = _union([out, _diff(_msum(base, e, h), keep)])
            out = _smooth_near(out, keep, BAND_OPEN * V, 0.0)
            if local is None:
                # growing round the bands' ends can narrow a white the parent had wide enough (헤 at 800: 37 of
                # 40 units): give that back too, measured on the grown outline
                tight, _ = clearance(out, 0.0, wmin)
                if not tight.is_empty:
                    out = _diff(out, tight)
        band, _ = clearance(base, 0.0, wmin)         # where the parent itself is closer than wmin
    else:
        out = base
        band, _ = clearance(base, 0.0, wmin)
    # counters: grow into one no further than leaves cmin across it (uniformly: the pen's corners), open one
    # that holds less than cmin to it
    for poly in _polys(base):
        for ring in poly.interiors:
            H = Polygon(ring)
            mic = 2 * _mic(H)
            if mic < cmin:
                out = _diff(out, _gbuf(H, (cmin - mic) / 2 + 0.2))
            elif e > 0 or h > 0:
                x = min(e + h / 2, (mic - cmin) / 2)
                out = _diff(out, _gbuf(H, -x) if x > 0 else H)
    if not band.is_empty:
        gone = _diff(_inter(out, band), white)          # parent ink the band takes
        n0 = len(_polys(out))
        out = _diff(out, band)
        if len(_polys(out)) > n0:
            # the band cut a stroke's tip off (a thin end close to another jamo): the tip goes with it
            ps = _polys(out)
            big = sorted(ps, key=lambda q: -q.area)
            keep = []
            for q in big:
                src = max(_polys(base), key=lambda b_: b_.intersection(q).area)
                sib = [x for x in keep if x.intersection(_gbuf(src, 1.0)).area > 0]
                if sib and q.area < TIP_DROP * src.area:
                    continue
                keep.append(q)
            out = _union(keep)
        if not gone.is_empty:
            out = _round_cut(out, gone, CUT_ROUND * V)
    if hx < 0:
        out = _vshrink_parts(out, -hx)
    out = tidy_geom(_fill_new_holes(out, base), S)
    if local is None and held:
        out = tidy_local(out)
        if _topo(out) != _topo(base):            # the local pen joined or lost a piece (훻 at 900): one pen per piece
            return pen_steps(g, P, lighter, False)
        return out
    return tidy_local(out) if local else out


def _fill_new_holes(g, base):
    """Fill every hole of g that is no counter of base (the pens close a narrow white notch into a pocket): no
    counter is made."""
    from shapely.geometry import Polygon
    old = [Polygon(r).representative_point() for p in _polys(base) for r in p.interiors]
    out = []
    changed = False
    for p in _polys(g):
        keep = []
        for r in p.interiors:
            H = Polygon(r)
            if any(H.contains(q) for q in old): keep.append(r)
            else: changed = True
        out.append(Polygon(p.exterior, keep))
    return _union(out) if changed else g


def _vshrink_parts(g, h):
    """vshrink() piece by piece; a piece whose pieces or holes it would change (a wall thinner than h between two
    counters) takes the largest h that keeps them."""
    out = []
    for p in _polys(g):
        t0 = _topo(p); hh = h
        for _ in range(10):
            q = vshrink(p, hh)
            if _topo(q) == t0:
                break
            hh *= 0.7
        else:
            q = p
        out.append(q)
    return _union(out)


def _open_parts(g, r):
    """An opening of radius r piece by piece, kept where it only rounds corners: the same holes, one piece, and at
    most END_LOSS of its ink gone (a stroke thinner than 2 r would go whole)."""
    out = []
    for p in _polys(g):
        q = _open(p, r)
        ok = _topo(q) == _topo(p) and q.area >= (1 - END_LOSS) * p.area
        out.append(q if ok else p)
    return _union(out)


END_LOSS = 0.03


def _smooth_near(g, zone, ro, rc):
    """Near the clearance bands, an opening of ro and a closing of rc: where the growth stops at a band its edge
    follows discs along the medial axis, and these round it off. rc stays under half the least white (GAP_MIN S),
    so no white closes; kept only where no piece or hole changes."""
    if zone.is_empty:
        return g
    Z = _gbuf(zone, 2 * max(ro, rc))
    sm = _open(g, ro)
    if rc > 0:
        sm = _gbuf(_gbuf(sm, rc), -rc)
    r = _union([_diff(g, Z), _inter(sm, Z)])
    return r if _topo(r) == _topo(g) else g


BAND_OPEN = 0.15        # x the stroke
BAND_CLOSE = 0.08       # x S (under GAP_MIN / 2)
END_ROUND = 0.45        # x the stroke: largest radius an eroded end gets back
CUT_ROUND = 0.3         # x the stroke: radius that rounds the ends a clearance cut leaves
TIP_DROP = 0.2          # a fragment the band cuts off a piece, under this share of it, is dropped
CAP_AREA = 0.6          # x its square: a corner an opening takes off is at most this (a square corner: 0.21)


def _mic(poly):
    from shapely import maximum_inscribed_circle
    try:
        return maximum_inscribed_circle(poly, tolerance=0.25).length
    except Exception:
        return 0.0


def _round_cut(q, gone, rho):
    """Round the ends a clearance cut leaves: of what an opening of rho would take off each piece (its corner caps),
    the caps that touch the cut; kept where that changes none of the piece's holes."""
    if rho <= 0 or gone.is_empty:
        return q
    zone = _gbuf(gone, 1.0)
    out = []
    for p in _polys(q):
        if p.distance(zone) > 0:
            out.append(p); continue
        caps = [c for c in _polys(_diff(p, _open(p, rho))) if c.intersects(zone) and c.area <= CAP_AREA * rho * rho]
        r = _diff(p, _union(caps)) if caps else p
        out.append(r if _topo(r) == _topo(p) else p)
    return _union(out)


def tidy_geom(g, S):
    """GEOS make_valid, then holes and pieces smaller than (SPECK S)^2 dropped and zero-width spikes and slits closed."""
    from shapely.geometry import Polygon
    from shapely.validation import make_valid
    if not g.is_valid:
        g = make_valid(g)
    lim = (SPECK * S) ** 2
    out = []
    for p in _polys(g):
        if p.area < lim:
            continue
        # a hole is a speck when small and thin: a round counter of COUNTER_MIN S across is smaller than lim
        holes = [h for h in p.interiors if Polygon(h).area >= lim or 2 * _mic(Polygon(h)) >= 0.5 * COUNTER_MIN * S]
        out.append(Polygon(p.exterior, holes))
    g = _union(out)
    # zero-width spikes and slits, and the unit-high steps the booleans leave, closed and opened away
    t = _topo(g)
    q = _gbuf(_gbuf(_gbuf(_gbuf(g, TIDY_R), -TIDY_R), -TIDY_R), TIDY_R)
    if not q.is_valid:
        q = make_valid(q)
    q = _union([p for p in _polys(q) if p.area >= lim])
    return q if _topo(q) == t else g


TIDY_R = 0.8            # units: closing and opening radius of tidy_geom (round: true corners move by 0.2)


LOCAL_CLOSE = 3.0       # units: the local band can leave long accidental slits that rounding turns into pockets
LOCAL_AREA = 0.02       # a repair may add at most 2 percent ink; pieces and genuine counters must stay unchanged


def tidy_local(g):
    """Close accidental band slits, fill only new pockets, and preserve the drawn topology.

    This repairs the producer's pen geometry before fitting. At HALF S155,
    눑's local band leaves 2-3-unit slits: integer curves cannot keep those
    slits open without making false counters. Closing adds about 1.6 percent
    ink instead of falling back to the much lighter plain pen. Fitting keeps
    FIT_MAX and ROUND_MAX against this corrected pen outline.
    """
    q = _fill_new_holes(_gbuf(_gbuf(g, LOCAL_CLOSE), -LOCAL_CLOSE), g)
    if q.is_valid and _topo(q) == _topo(g) and abs(q.area - g.area) <= LOCAL_AREA * g.area:
        return q
    return g


# ------------------------------------------------------------------ curves back: polyline -> quadratic splines
# The pen works on GEOS polygons; fit_ring() turns each ring back into TrueType curves. Corners are where the ring
# turns more than CORNER degrees within CORNER_L units; a straight side is one edge of at least LINE_MIN (every curve
# reaches the fit in chords shorter than that, see G_FLAT, G_ARC), snapped exactly horizontal or vertical within
# SNAP_DEG (fontbakery outline_semi_vertical); curved runs are split at their extrema (on-curve points there, with
# horizontal / vertical tangents) and fitted with cubics (Schneider's least squares, tangent-continuous at every
# break that is not a corner) within FIT_TOL, then converted to quadratics within QUAD_TOL (fontTools cu2qu).
CORNER = 38.0

CORNER_L = 2.0
LINE_TOL = 0.25        # a run within this of its chord is a line ...
LINE_MIN = 8.0         # ... if at least this long
FIT_TOL = 0.3          # cubic fit, units
QUAD_TOL = 0.2         # cubic -> quadratic
SNAP_DEG = 4.0         # lines this close to H / V become exactly H / V ...
SNAP_OFF = 1.5         # ... if that moves an end by at most this


def _ring_clean(P):
    """drop repeated and collinear points of a closed ring (N x 2)."""
    P = np.asarray(P, float)
    if len(P) > 1 and np.allclose(P[0], P[-1]): P = P[:-1]
    keep = [0]
    for i in range(1, len(P)):
        if np.hypot(*(P[i] - P[keep[-1]])) > 0.05: keep.append(i)
    P = P[keep]
    if len(P) > 2 and np.hypot(*(P[0] - P[-1])) <= 0.05: P = P[:-1]
    # collinear
    changed = True
    while changed and len(P) > 3:
        changed = False
        a = np.roll(P, 1, 0); b = np.roll(P, -1, 0)
        cr = np.abs((P[:, 0] - a[:, 0]) * (b[:, 1] - a[:, 1]) - (P[:, 1] - a[:, 1]) * (b[:, 0] - a[:, 0]))
        L = np.hypot(*(b - a).T) + 1e-12
        dev = cr / L
        dot = ((P - a) * (b - P)).sum(1)
        drop = (dev < 0.01) & (dot > 0)
        # never drop two neighbours in one pass
        idx = np.where(drop)[0]
        if len(idx):
            sel = []; last = -3
            for i in idx:
                if i - last > 1: sel.append(i); last = i
            if sel and sel[-1] == len(P) - 1 and sel[0] == 0: sel.pop()
            mask = np.ones(len(P), bool); mask[sel] = False; P = P[mask]; changed = True
    return P


def _arc(P):
    d = np.hypot(*np.diff(np.vstack([P, P[:1]]), axis=0).T)
    return d, np.concatenate([[0.0], np.cumsum(d)])


def _dir_at(P, s, i, L, sign):
    """unit direction from P[i] to the point at arc distance L along the ring (sign +1 forward, -1 back)."""
    n = len(P); tot = s[-1]
    target = (s[i] + sign * L) % tot
    # find segment containing target
    j = np.searchsorted(s, target, side="right") - 1
    j = min(max(j, 0), n - 1)
    seg = s[j + 1] - s[j]
    t = 0.0 if seg <= 0 else (target - s[j]) / seg
    q = P[j] + t * (P[(j + 1) % n] - P[j])
    v = (q - P[i]) * sign
    nv = math.hypot(*v)
    return v / nv if nv > 1e-9 else np.array([0.0, 0.0])


def _corners(P):
    n = len(P); d, s = _arc(P); tot = s[-1]
    L = min(CORNER_L, tot / 8)
    turn = np.zeros(n)
    for i in range(n):
        a = _dir_at(P, s, i, L, -1); b = _dir_at(P, s, i, L, +1)
        turn[i] = math.degrees(math.atan2(a[0] * b[1] - a[1] * b[0], a[0] * b[0] + a[1] * b[1]))
    out = []
    cand = [i for i in range(n) if abs(turn[i]) > CORNER]
    for i in sorted(cand, key=lambda i: -abs(turn[i])):
        if any(min(abs(s[i] - s[j]), tot - abs(s[i] - s[j])) < 2 * L for j in out): continue
        out.append(i)
    return sorted(out), turn


def _bez(ctrl, t):
    t = np.asarray(t)[:, None]; u = 1 - t
    p0, p1, p2, p3 = ctrl
    return u ** 3 * p0 + 3 * u * u * t * p1 + 3 * u * t * t * p2 + t ** 3 * p3


def _bez_d(ctrl, t):
    t = np.asarray(t)[:, None]; u = 1 - t
    p0, p1, p2, p3 = ctrl
    return 3 * u * u * (p1 - p0) + 6 * u * t * (p2 - p1) + 3 * t * t * (p3 - p2)


def _bez_dd(ctrl, t):
    t = np.asarray(t)[:, None]; u = 1 - t
    p0, p1, p2, p3 = ctrl
    return 6 * u * (p2 - 2 * p1 + p0) + 6 * t * (p3 - 2 * p2 + p1)


def _chord_param(Q):
    d = np.hypot(*np.diff(Q, axis=0).T); s = np.concatenate([[0.0], np.cumsum(d)])
    return s / s[-1] if s[-1] > 0 else np.linspace(0, 1, len(Q))


def _fit_cubic(Q, t0, t1, u):
    """least-squares handle lengths for fixed end tangents (Schneider)."""
    p0, p3 = Q[0], Q[-1]
    A1 = (3 * (1 - u) ** 2 * u)[:, None] * t0
    A2 = (3 * (1 - u) * u ** 2)[:, None] * t1
    C00 = (A1 * A1).sum(); C01 = (A1 * A2).sum(); C11 = (A2 * A2).sum()
    base = _bez((p0, p0, p3, p3), u)
    X0 = (A1 * (Q - base)).sum(); X1 = (A2 * (Q - base)).sum()
    det = C00 * C11 - C01 * C01
    L = math.hypot(*(p3 - p0))
    if abs(det) > 1e-12:
        a1 = (X0 * C11 - X1 * C01) / det; a2 = (C00 * X1 - C01 * X0) / det
    else:
        a1 = a2 = L / 3
    if a1 < 1e-6 * L or a2 < 1e-6 * L or a1 > 2 * L or a2 > 2 * L:
        a1 = a2 = L / 3
    return (p0, p0 + a1 * t0, p3 + a2 * t1, p3)


def _reparam(ctrl, Q, u):
    for _ in range(2):
        B = _bez(ctrl, u); d1 = _bez_d(ctrl, u); d2 = _bez_dd(ctrl, u)
        num = ((B - Q) * d1).sum(1); den = (d1 * d1).sum(1) + ((B - Q) * d2).sum(1)
        ok = np.abs(den) > 1e-12
        u = u.copy(); u[ok] -= num[ok] / den[ok]
        u = np.clip(u, 0, 1); u[0], u[-1] = 0, 1
        u = np.maximum.accumulate(u)
    return u


def _err(ctrl, Q, u):
    B = _bez(ctrl, u); e = np.hypot(*(B - Q).T)
    i = int(np.argmax(e)); return e[i], i


def _unit(v):
    n = math.hypot(*v); return v / n if n > 1e-12 else v


def fit_run(Q, t0, t1, tol=FIT_TOL, depth=0):
    """Q: open polyline (M x 2) from breakpoint to breakpoint; t0: unit tangent leaving Q[0]; t1: unit tangent
    pointing back from Q[-1] (i.e. -direction of arrival). Returns list of cubic control tuples."""
    L = math.hypot(*(Q[-1] - Q[0]))
    if L < 1e-6 or (len(Q) == 2 and L < 3.0):
        return [(Q[0], Q[0] + t0 * L / 3, Q[-1] + t1 * L / 3, Q[-1])]
    if len(Q) == 2:                        # one long edge: its own points, so the fit is checked like any other
        Q = _densify(Q, 1.5)
    # densify so the least squares sees the shape between sparse vertices
    Q = _densify(Q)
    u = _chord_param(Q)
    ctrl = _fit_cubic(Q, t0, t1, u)
    e, i = _err(ctrl, Q, u)
    for _ in range(6):
        if e <= tol: break
        u = _reparam(ctrl, Q, u); ctrl = _fit_cubic(Q, t0, t1, u); e, i = _err(ctrl, Q, u)
    if e <= tol or depth > 12 or len(Q) < 4:
        return [ctrl]
    i = min(max(i, 1), len(Q) - 2)
    tc = _unit(Q[i + 1] - Q[i - 1])
    return fit_run(Q[:i + 1], t0, -tc, tol, depth + 1) + fit_run(Q[i:], tc, t1, tol, depth + 1)


def _densify(Q, step=1.5):
    out = [Q[0]]
    for a, b in zip(Q[:-1], Q[1:]):
        L = math.hypot(*(b - a)); n = int(L / step)
        for k in range(1, n + 1):
            out.append(a + (b - a) * k / (n + 1))
        out.append(b)
    return np.array(out)


def _lines(R):
    """[(i, j)] straight runs of the open polyline R: every point within LINE_TOL of the chord, and at least
    LINE_MIN long when one edge (the pen samples every curve finer than that) or LINE_RUN when several (a gentle
    curve of radius under ~LINE_RUN^2 / 8 LINE_TOL stays out). Two lines meeting at a turn under 6 degrees are left
    to the curve fit (fontbakery outline_colinear_vectors)."""
    m = len(R); out = []; i = 0
    while i < m - 1:
        lo, hi = -math.pi, math.pi; best = i; base = None
        for j in range(i + 1, m):
            v = R[j] - R[i]; d = math.hypot(*v)
            if d < 1e-9: continue
            a = math.atan2(v[1], v[0])
            if base is None: base = a
            a = (a - base + math.pi) % (2 * math.pi) - math.pi
            if not (lo - 1e-12 <= a <= hi + 1e-12):
                break
            w = math.asin(min(1.0, LINE_RUN_TOL / d))
            lo, hi = max(lo, a - w), min(hi, a + w)
            best = j
        L = math.hypot(*(R[best] - R[i])) if best > i else 0.0
        if best > i and L >= (LINE_MIN if best == i + 1 else LINE_RUN) and _dev(R[i:best + 1]) <= LINE_RUN_TOL:
            out.append([i, best]); i = best
        else:
            i += 1
    keep = [True] * len(out)
    for a in range(len(out) - 1):
        (i0, j0), (i1, j1) = out[a], out[a + 1]
        if keep[a] and j0 == i1 and _turn(R[j0] - R[i0], R[j1] - R[i1]) < 6.0:
            short = a if math.dist(R[i0], R[j0]) < math.dist(R[i1], R[j1]) else a + 1
            keep[short] = False                      # the shorter one goes to the curve fit
    return [tuple(o) for o, k_ in zip(out, keep) if k_]


LINE_RUN = 30.0         # a line of several edges: at least this long ...
LINE_RUN_TOL = 0.08     # ... and this straight (a curve of radius under ~1,400 is not a line)


def _turn(a, b):
    return abs(math.degrees(math.atan2(a[0] * b[1] - a[1] * b[0], a[0] * b[0] + a[1] * b[1])))


def _dev(Q):
    a, b = Q[0], Q[-1]; L = math.hypot(*(b - a))
    if L < 1e-9: return 0.0
    return float(np.max(np.abs((Q[:, 0] - a[0]) * (b[1] - a[1]) - (Q[:, 1] - a[1]) * (b[0] - a[0])) / L))


def _extrema(C, s):
    """indices of C (open polyline, arc s) where the tangent turns vertical or horizontal, with the axis."""
    n = len(C)
    if n < 3: return []
    tot = s[-1]
    T = []
    for k in range(n):
        a = np.searchsorted(s, s[k] - 1.2); b = np.searchsorted(s, s[k] + 1.2, side="right") - 1
        a = max(0, min(a, k - 1 if k > 0 else 0)); b = min(n - 1, max(b, k + 1 if k < n - 1 else n - 1))
        T.append(_unit(C[b] - C[a]))
    T = np.array(T); out = []
    for ax in (0, 1):       # ax 0: x component changes sign -> vertical tangent
        for k in range(1, n):
            if T[k - 1][ax] * T[k][ax] < 0 or (T[k][ax] == 0 and 0 < k < n - 1 and T[k - 1][ax] * T[k + 1][ax] < 0):
                kk = k if abs(T[k][ax]) <= abs(T[k - 1][ax]) else k - 1
                if s[kk] < 1.5 or tot - s[kk] < 1.5: continue
                out.append((kk, ax, T[kk]))
    out.sort(key=lambda e: (e[0], e[1]))
    keep = []
    for e in out:
        if keep and s[e[0]] - s[keep[-1][0]] < 1.5: continue
        keep.append(e)
    return keep


def _snapdir(v):
    """The exact axis direction of a line within SNAP_DEG of it and off by at most SNAP_OFF units; else None."""
    ang = math.degrees(math.atan2(abs(v[1]), abs(v[0])))
    if ang < SNAP_DEG and abs(v[1]) <= SNAP_OFF: return np.array([math.copysign(1.0, v[0]), 0.0])
    if ang > 90 - SNAP_DEG and abs(v[0]) <= SNAP_OFF: return np.array([0.0, math.copysign(1.0, v[1])])
    return None


def fit_ring(P, fit_tol=FIT_TOL, quad_tol=QUAD_TOL, hints=None):
    """closed ring (N x 2) -> [("L", p0, p1) | ("Q", [p0, c1 .. cn, p1])], closed, same orientation. hints:
    [(x, y, tx, ty)] where the parent had a smooth on-curve point (moved by the pen): breakpoints with the parent's
    tangent, so a span between two is first tried as one quadratic (the pen's offset of one parent quadratic),
    and only a span that fails that is fitted afresh (extrema, cubics, cu2qu)."""
    P = _ring_clean(P)
    if len(P) < 3: return []
    P, hint_at = _insert_hints(P, hints) if hints else (P, {})
    n = len(P)
    cs, _ = _corners(P)
    d_, s_ = _arc(P); tot = s_[-1]
    for c in cs:                                  # a corner wins over a hint next to it
        for i in list(hint_at):
            if min(abs(s_[i] - s_[c]), tot - abs(s_[i] - s_[c])) < 2.0:
                del hint_at[i]
    keys = sorted(set(cs) | set(hint_at))
    start = keys[0] if keys else int(np.argmax(P[:, 1]))
    P = np.roll(P, -start, 0).copy()
    cs = sorted((c - start) % n for c in cs)
    hint_at = {(i - start) % n: t for i, t in hint_at.items()}
    B = {}                                   # breakpoint index -> tangent (forward unit vector) or "corner"
    for i, t in hint_at.items(): B[i] = t
    for c in cs: B[c] = "corner"
    if not B:
        d = P[1] - P[-1]
        B[0] = np.array([math.copysign(1.0, d[0]) if d[0] else 1.0, 0.0])
    Pc = np.vstack([P, P[:1]])               # index n == 0

    def runs():
        ks = sorted(B)
        return [(ks[k], ks[k + 1] if k + 1 < len(ks) else n) for k in range(len(ks))]
    lines = {}
    for a, b in runs():
        for i, j in _lines(Pc[a:b + 1]):
            lines[(a + i) % n] = (a + j) % n if a + j != n else n
    # snap near-horizontal / vertical lines, set breakpoint tangents
    for i, j in list(lines.items()):
        jj = j % n
        d = _snapdir(Pc[j] - Pc[i])
        if d is not None:
            if d[0] == 0:
                x = (P[i, 0] + P[jj, 0]) / 2; P[i, 0] = x; P[jj, 0] = x
            else:
                y = (P[i, 1] + P[jj, 1]) / 2; P[i, 1] = y; P[jj, 1] = y
        else:
            d = _unit(P[jj] - P[i])
        for q in (i, jj):
            if not isinstance(B.get(q), str):
                B[q] = d
        lines[i] = (j, d)
    Pc = np.vstack([P, P[:1]])
    res = []
    for a, b in runs():
        if a in lines and lines[a][0] == b:
            A_, B_ = Pc[a].copy(), Pc[b].copy(); v = B_ - A_
            ang = math.degrees(math.atan2(min(abs(v[0]), abs(v[1])), max(abs(v[0]), abs(v[1]))))
            if 0 < ang <= 0.6:
                # a long line a fraction of a degree off the axis that could not be snapped without moving an end
                # further than SNAP_OFF: drawn as a straight quadratic (fontbakery outline_semi_vertical reads lines)
                res.append(("Q", [A_, (A_ + B_) / 2, B_])); continue
            res.append(("L", A_, B_)); continue
        Q = Pc[a:b + 1]
        ta, tb = B[a], B[b % n]
        t0 = _lead(Q) if isinstance(ta, str) else ta
        t1 = _lead(Q[::-1]) if isinstance(tb, str) else -tb
        tol1 = HINT_TOL
        sp = _quads(Q, None if isinstance(ta, str) else ta, None if isinstance(tb, str) else tb, tol1) if _SPLINES else None
        if sp is not None:
            res += sp; continue
        # afresh: split at the extrema (on-curve points there, horizontal / vertical tangents), cubics, cu2qu
        dd = np.hypot(*np.diff(Q, axis=0).T); sq = np.concatenate([[0.0], np.cumsum(dd)])
        cuts = [(0, t0)]
        for kk, ax, tv in _extrema(Q, sq):
            t = np.array([0.0, math.copysign(1.0, tv[1])]) if ax == 0 else np.array([math.copysign(1.0, tv[0]), 0.0])
            cuts.append((kk, t))
        cuts.append((len(Q) - 1, -t1))
        for (i0, u0), (i1, u1) in zip(cuts, cuts[1:]):
            R = Q[i0:i1 + 1]
            if len(R) < 2: continue
            sp = _quads(R, u0, u1, HINT_TOL) if _SPLINES else None
            if sp is not None:
                res += sp; continue
            for c in fit_run(R, u0, -u1, fit_tol):
                qs = curve_to_quadratic([tuple(map(float, p)) for p in c], quad_tol)
                res.append(("Q", [np.array(q) for q in qs]))
    return _axis_pass(_merge_tiny(res))


def _axis_pass(res):
    """Every line within SNAP_DEG of an axis and off by at most SNAP_OFF made exactly so (its neighbours follow
    its ends); one off by less than a degree that cannot be (a long, slightly slanted stroke) drawn as a straight
    quadratic, so no line of the outline is a fraction of a degree off vertical or horizontal (fontbakery
    outline_semi_vertical)."""
    out = [list(s_) for s_ in res]
    n = len(out)

    def set_start(sg, q):
        if sg[0] == "L": sg[1] = q
        else: sg[1] = [q] + list(sg[1][1:])

    def set_end(sg, q):
        if sg[0] == "L": sg[2] = q
        else: sg[1] = list(sg[1][:-1]) + [q]
    for i in range(n):
        sg = out[i]
        if sg[0] != "L": continue
        A_, B_ = np.asarray(sg[1], float).copy(), np.asarray(sg[2], float).copy()
        v = B_ - A_
        if max(abs(v[0]), abs(v[1])) < 1e-9: continue
        d = _snapdir(v)
        if d is not None:
            ax = 0 if d[0] == 0 else 1
            if A_[ax] != B_[ax]:
                m = (A_[ax] + B_[ax]) / 2; A_[ax] = m; B_[ax] = m
                sg[1], sg[2] = A_, B_
                set_end(out[i - 1], A_.copy()); set_start(out[(i + 1) % n], B_.copy())
            continue
        ang = math.degrees(math.atan2(min(abs(v[0]), abs(v[1])), max(abs(v[0]), abs(v[1]))))
        if ang <= 0.6:
            out[i] = ["Q", [A_, (A_ + B_) / 2, B_]]
    return [tuple(sg) for sg in out]


HINT_R = 3.0            # units: a hint further than this from the ring is not used
HINT_ANGLE = 15.0       # degrees: a hint whose tangent disagrees with the ring's by more is not used


def _insert_hints(P, hints):
    """Put each hint on the ring (a vertex at its nearest point) -> (P, {index: forward unit tangent})."""
    from shapely.geometry import LinearRing, Point
    ring = LinearRing(P)
    d_, s_ = _arc(P); tot = s_[-1]
    at = []
    for x, y, tx, ty in hints:
        pt = Point(x, y)
        if ring.distance(pt) > HINT_R: continue
        at.append((ring.project(pt) % tot, np.array([tx, ty])))
    if not at:
        return P, {}
    at.sort(key=lambda a: a[0])
    # merge hints within 2 units of each other along the ring
    kept = []
    for pos, t in at:
        if kept and pos - kept[-1][0] < 2.0: continue
        kept.append((pos, t))
    if len(kept) > 1 and tot - kept[-1][0] + kept[0][0] < 2.0: kept.pop()
    pts = list(P); idx = {}
    # insert from the end so earlier indices hold
    n = len(P)
    ins = []
    for pos, t in kept:
        j = int(np.searchsorted(s_, pos, side="right") - 1); j = min(max(j, 0), n - 1)
        L = s_[j + 1] - s_[j]; f = 0.0 if L <= 0 else (pos - s_[j]) / L
        q = P[j] + f * (P[(j + 1) % n] - P[j])
        if f * L < 0.3: ins.append((j, None, t))
        elif (1 - f) * L < 0.3: ins.append(((j + 1) % n, None, t))
        else: ins.append((j, q, t))
    out = []; tangents = {}
    for i in range(n):
        out.append(P[i])
        for j, q, t in ins:
            if j == i and q is None: tangents[len(out) - 1] = t
        for j, q, t in ins:
            if j == i and q is not None:
                out.append(q); tangents[len(out) - 1] = t
    Pn = np.array(out)
    d2, s2 = _arc(Pn); tot2 = s2[-1]
    good = {}
    for i, t in tangents.items():
        a = _dir_at(Pn, s2, i, 1.5, -1); b = _dir_at(Pn, s2, i, 1.5, +1)
        loc = _unit(a + b)
        if np.hypot(*loc) < 1e-6: continue
        tt = _unit(t)
        if (tt * loc).sum() < 0: tt = -tt
        if math.degrees(math.acos(max(-1.0, min(1.0, float((tt * loc).sum()))))) <= HINT_ANGLE:
            good[i] = tt
    return Pn, good


HINT_TOL = 0.4          # units: a span between two breakpoints is fitted within this (with the rest, <= 1)
SPLINE_MAX = 12         # off-curve points at most in one span's quadratic spline


def _quads(Q, ta, tb, tol):
    """The span Q as one TrueType quadratic spline (off-curve points c1..cn, the on-curve points between them
    implied at their midpoints, so the spline is tangent-continuous by construction), leaving Q[0] along ta and
    arriving at Q[-1] along tb (either None: free), with the fewest off-curve points that keep it within tol of Q
    both ways (least squares on the controls, three reparameterizations). -> [("Q", [A, c1, .., cn, B])] or None."""
    if ta is not None and tb is not None:
        one = _one_quad(Q, ta, tb, tol)
        if one is not None:
            return [one]
    Qd = _densify(Q, 1.5)
    if len(Qd) < 4:
        return None
    d = np.hypot(*np.diff(Qd, axis=0).T); sq = np.concatenate([[0.0], np.cumsum(d)])
    if sq[-1] <= 0:
        return None
    # A free endpoint permits a single least-squares control. Starting at two
    # controls needlessly stores a spline even when one quadratic fits the span.
    first = 1 if ta is None or tb is None else 2
    for n in range(first, SPLINE_MAX + 1):
        u = sq / sq[-1] * n
        C = None
        for _ in range(12 if n == 1 else 4):
            C = _spline_lsq(Qd, u, n, ta, tb)
            if C is None:
                break
            u = _spline_param(C, Qd[0], Qd[-1], Qd, n)
            if n == 1 and _spline_err(C, Qd[0], Qd[-1], Qd) <= tol:
                break
        if C is None:
            continue
        if ta is not None and ((C[0] - Qd[0]) * ta).sum() <= 0: continue
        if tb is not None and ((Qd[-1] - C[-1]) * tb).sum() <= 0: continue
        if _spline_err(C, Qd[0], Qd[-1], Qd) <= tol:
            return [("Q", [Q[0].copy()] + [c for c in C] + [Q[-1].copy()])]
    return None


def _spline_basis(u, n):
    """Per sample: segment i (0-based), t, and the weights of (m_i, c_i, m_{i+1})."""
    i = np.minimum(np.floor(u).astype(int), n - 1); t = u - i
    return i, t, (1 - t) ** 2, 2 * (1 - t) * t, t * t


def _spline_lsq(Qd, u, n, ta, tb):
    """Least-squares controls c_1..c_n (as an n x 2 array) of the spline through u (0..n) fitting Qd."""
    A, B = Qd[0], Qd[-1]
    # unknowns: c_1 = A + a ta (or free 2), c_n = B - b tb (or free 2), c_2..c_{n-1} free (2 each)
    cols = []; base = np.zeros((n, 2)); J = [np.zeros((2, 0)) for _ in range(n)]
    k = 0
    def add(j, M):
        nonlocal k
        for jj in range(n):
            J[jj] = np.hstack([J[jj], np.zeros((2, M.shape[1]))])
        J[j][:, -M.shape[1]:] = M
        k += M.shape[1]
    for j in range(n):
        if j == 0 and ta is not None:
            base[j] = A; add(j, np.asarray(ta, float).reshape(2, 1))
        elif j == n - 1 and tb is not None:
            base[j] = B; add(j, -np.asarray(tb, float).reshape(2, 1))
        else:
            add(j, np.eye(2))
    # on-curve points m_0 = A, m_i = (c_i + c_{i+1}) / 2, m_n = B
    mb = [A] + [(base[j] + base[j + 1]) / 2 for j in range(n - 1)] + [B]
    mJ = [np.zeros((2, k))] + [(J[j] + J[j + 1]) / 2 for j in range(n - 1)] + [np.zeros((2, k))]
    i, t, w0, w1, w2 = _spline_basis(u, n)
    # Preserve sample/coordinate row order while assembling all rows at once.
    J, mJ, mb = np.asarray(J), np.asarray(mJ), np.asarray(mb)
    M = (w0[:, None, None] * mJ[i] + w1[:, None, None] * J[i] + w2[:, None, None] * mJ[i + 1]).reshape(-1, k)
    r = (Qd - (w0[:, None] * mb[i] + w1[:, None] * base[i] + w2[:, None] * mb[i + 1])).reshape(-1)
    try:
        X, *_ = np.linalg.lstsq(M, r, rcond=None)
    except np.linalg.LinAlgError:
        return None
    return np.array([base[j] + J[j] @ X for j in range(n)])


def _spline_pts(C, A, B, steps=24):
    n = len(C)
    m = [A] + [(C[j] + C[j + 1]) / 2 for j in range(n - 1)] + [B]
    t = np.linspace(0, 1, steps)[:, None]
    segs = [((1 - t) ** 2) * m[j] + (2 * (1 - t) * t) * C[j] + (t * t) * m[j + 1] for j in range(n)]
    return np.vstack(segs), np.concatenate([j + np.linspace(0, 1, steps) for j in range(n)])


def _spline_param(C, A, B, Qd, n):
    pts, us = _spline_pts(C, A, B, 40)
    # Project onto sampled edges rather than quantizing to the nearest sample.
    v = pts[1:] - pts[:-1]; ww = (v * v).sum(1); ww[ww == 0] = 1e-12
    t = np.clip(((Qd[:, None] - pts[None, :-1]) * v[None]).sum(-1) / ww[None], 0, 1)
    d = ((Qd[:, None] - (pts[None, :-1] + t[..., None] * v[None])) ** 2).sum(-1)
    best = np.argmin(d, 1)
    u = us[best] + t[np.arange(len(Qd)), best] * (us[best + 1] - us[best])
    u[0], u[-1] = 0.0, float(n)
    return np.maximum.accumulate(np.minimum(u, n))


def _pl_dist(X, L):
    """Largest distance from the points X to the polyline L (projection onto its segments)."""
    sa, sb = L[:-1], L[1:]; v = sb - sa; ww = (v * v).sum(1); ww[ww == 0] = 1e-12
    tt = np.clip((((X[:, None, :] - sa[None]) * v[None]).sum(-1)) / ww[None], 0, 1)
    return float(np.sqrt(((X[:, None, :] - (sa[None] + tt[..., None] * v[None])) ** 2).sum(-1)).min(1).max())


def _spline_err(C, A, B, Qd):
    pts, _ = _spline_pts(C, A, B, 32)
    return max(_pl_dist(Qd, pts), _pl_dist(pts, Qd))


def _one_quad(Q, ta, tb, tol):
    """One quadratic (or a line) from Q[0] leaving along ta to Q[-1] arriving along tb, if within tol of Q both ways."""
    A, B = Q[0], Q[-1]
    ch = B - A; L = math.hypot(*ch)
    if L < 1e-6: return None
    ta, tb = _unit(np.asarray(ta, float)), _unit(np.asarray(tb, float))
    det = ta[0] * tb[1] - ta[1] * tb[0]             # A + s ta = B - u tb
    if abs(det) < 1e-9:
        if _dev(Q) <= tol and (ta * ch).sum() > 0: return ("L", A.copy(), B.copy())
        return None
    s = (ch[0] * tb[1] - ch[1] * tb[0]) / det
    u = (ta[0] * ch[1] - ta[1] * ch[0]) / det
    if s <= 0 or u <= 0 or s > 1.5 * L or u > 1.5 * L:
        return None
    C = A + s * ta
    if _spline_err(np.array([C]), A, B, _densify(Q, 2.0)) > tol:
        return None
    return ("Q", [A.copy(), C, B.copy()])


TINY = 0.4              # units: a fitted segment shorter than this (ends and controls) merges into its neighbours


def _merge_tiny(res):
    """Drop fitted segments shorter than TINY (a unit step at a pen corner rounds to a loop): its two neighbours
    meet at its midpoint instead (each end moves by at most TINY / 2)."""
    def span(s):
        pts = [s[1], s[2]] if s[0] == "L" else s[1]
        return max(math.dist(pts[0], q) for q in pts[1:])

    def with_end(s, q):
        return ("L", s[1], q) if s[0] == "L" else ("Q", list(s[1][:-1]) + [q])

    def with_start(s, q):
        return ("L", q, s[2]) if s[0] == "L" else ("Q", [q] + list(s[1][1:]))
    out = list(res)
    changed = True
    while changed and len(out) > 3:
        changed = False
        for i, s in enumerate(out):
            if span(s) < TINY:
                a, b = (s[1], s[2]) if s[0] == "L" else (s[1][0], s[1][-1])
                mid = (np.asarray(a) + np.asarray(b)) / 2
                j, k = (i - 1) % len(out), (i + 1) % len(out)
                out[j] = with_end(out[j], mid); out[k] = with_start(out[k], mid)
                del out[i]; changed = True
                break
    return out


def _lead(Q, L=3.0):
    d = np.hypot(*np.diff(Q, axis=0).T); s = np.concatenate([[0.0], np.cumsum(d)])
    L = min(L, s[-1] / 3) if s[-1] > 0 else L
    j = int(np.searchsorted(s, L))
    j = min(max(j, 1), len(Q) - 1)
    return _unit(Q[j] - Q[0])


# ------------------------------------------------------------------ the data's outline, read back
_DTOK = re.compile(r"[MmLlHhVvQqTtCcZz]|-?(?:\d+\.?\d*|\.\d+)(?:[eE][-+]?\d+)?")


def d_contours(d):
    """SVG d -> [[segment]], segment = ("L", p0, p1) | ("Q", p0, c, p1) | ("C", p0, c1, c2, p1), absolute."""
    toks = _DTOK.findall(d or "")
    out, cur = [], []
    i, cmd = 0, None
    x = y = sx = sy = 0.0
    qc = None

    def num():
        nonlocal i
        v = float(toks[i]); i += 1
        return v
    while i < len(toks):
        t = toks[i]
        if t.isalpha():
            cmd = t; i += 1
            if cmd in "Zz":
                if cur:
                    if (x, y) != (sx, sy): cur.append(("L", (x, y), (sx, sy)))
                    out.append(cur)
                cur = []; x, y = sx, sy; qc = None
                continue
        rel = cmd.islower(); c = cmd.upper()
        ox, oy = (x, y) if rel else (0.0, 0.0)
        if c == "M":
            if cur: out.append(cur); cur = []
            x, y = num() + ox, num() + oy; sx, sy = x, y; qc = None
            cmd = "l" if rel else "L"
        elif c == "L":
            nx, ny = num() + ox, num() + oy; cur.append(("L", (x, y), (nx, ny))); x, y = nx, ny; qc = None
        elif c == "H":
            nx = num() + (x if rel else 0); cur.append(("L", (x, y), (nx, y))); x = nx; qc = None
        elif c == "V":
            ny = num() + (y if rel else 0); cur.append(("L", (x, y), (x, ny))); y = ny; qc = None
        elif c == "Q":
            a, b, nx, ny = num() + ox, num() + oy, num() + ox, num() + oy
            cur.append(("Q", (x, y), (a, b), (nx, ny))); qc = (a, b); x, y = nx, ny
        elif c == "T":
            a, b = (2 * x - qc[0], 2 * y - qc[1]) if qc else (x, y)
            nx, ny = num() + ox, num() + oy
            cur.append(("Q", (x, y), (a, b), (nx, ny))); qc = (a, b); x, y = nx, ny
        elif c == "C":
            a, b, e, f, nx, ny = (num() + ox, num() + oy, num() + ox, num() + oy, num() + ox, num() + oy)
            cur.append(("C", (x, y), (a, b), (e, f), (nx, ny))); x, y = nx, ny; qc = None
    if cur: out.append(cur)
    return out


def d_flatten(con, step=2.5):
    pts = []
    for s in con:
        p0 = s[1]; pts.append(p0)
        if s[0] == "L":
            continue
        L = sum(math.dist(s[k], s[k + 1]) for k in range(1, len(s) - 1))
        n = max(2, min(32, int(L / step) + 1))
        for k in range(1, n):
            t = k / n; u = 1 - t
            if s[0] == "Q":
                _, a, c, b = s
                pts.append((u * u * a[0] + 2 * u * t * c[0] + t * t * b[0], u * u * a[1] + 2 * u * t * c[1] + t * t * b[1]))
            else:
                _, a, c1, c2, b = s
                pts.append((u ** 3 * a[0] + 3 * u * u * t * c1[0] + 3 * u * t * t * c2[0] + t ** 3 * b[0],
                            u ** 3 * a[1] + 3 * u * u * t * c1[1] + 3 * u * t * t * c2[1] + t ** 3 * b[1]))
    return pts


def geom_of_d(d):
    """(region, every ring simple) of an SVG d by even-odd nesting, as a browser or a font file fills it."""
    from shapely.geometry import LinearRing, Polygon
    from shapely.validation import make_valid
    g = None; simple = True
    for con in d_contours(d):
        pts = d_flatten(con)
        if len(pts) < 3:
            simple = False; continue
        if not LinearRing(pts).is_simple:
            simple = False
        q = Polygon(pts)
        if not q.is_valid:
            q = make_valid(q)
        g = q if g is None else g.symmetric_difference(q)
    return (g if g is not None else Polygon()), simple


# ------------------------------------------------------------------ geometry -> the data's outline
def fit_geom(g, fit_tol=FIT_TOL, quad_tol=QUAD_TOL, hints=None):
    """shapely (Multi)Polygon -> pathops outline of quadratic splines and lines (y down), wound by nesting."""
    from shapely.geometry import LineString
    out = pathops.Path(); pen = out.getPen()
    for poly in _polys(g):
        for ring in [poly.exterior] + list(poly.interiors):
            segs = fit_ring(np.asarray(ring.coords), fit_tol, quad_tol, hints)
            if segs and _seg_dev(segs, LineString(ring.coords)) > FIT_MAX:
                # this ring afresh, the conservative way: no hints, no splines (cubics and cu2qu), no merging
                global _SPLINES
                keep = _SPLINES; _SPLINES = False
                try:
                    segs2 = fit_ring(np.asarray(ring.coords), fit_tol / 3, quad_tol / 3, None)
                finally:
                    _SPLINES = keep
                if segs2 and _seg_dev(segs2, LineString(ring.coords)) < _seg_dev(segs, LineString(ring.coords)):
                    segs = segs2
            if not segs:
                continue
            pen.moveTo(tuple(segs[0][1] if segs[0][0] == "L" else segs[0][1][0]))
            for s in segs:
                if s[0] == "L":
                    pen.lineTo(tuple(s[2]))
                else:
                    pen.qCurveTo(*[tuple(q) for q in s[1][1:]])
            pen.closePath()
    return orient(out)


def _seg_dev(segs, line):
    """Largest distance from the fitted segments (sampled) to the ring they were fitted to."""
    import shapely
    pts = []
    for sg in segs:
        if sg[0] == "L":
            pts += [sg[1], (np.asarray(sg[1]) + np.asarray(sg[2])) / 2]
        else:
            q = [np.asarray(c, float) for c in sg[1]]
            n = len(q) - 2
            on = [q[0]] + [(q[i] + q[i + 1]) / 2 for i in range(1, n)] + [q[-1]]
            for i in range(n):
                for t in (0.0, 0.25, 0.5, 0.75):
                    pts.append((1 - t) ** 2 * on[i] + 2 * (1 - t) * t * q[i + 1] + t * t * on[i + 1])
    if not pts:
        return 0.0
    return float(shapely.distance(shapely.points(np.asarray(pts, float)), line).max())


_SPLINES = True


def _poly_path(g):
    out = pathops.Path(); pen = out.getPen()
    for poly in _polys(g):
        for ring in [poly.exterior] + list(poly.interiors):
            cs = [(round(x), round(y)) for x, y in list(ring.coords)[:-1]]
            if len(cs) < 3: continue
            pen.moveTo(cs[0])
            for q in cs[1:]: pen.lineTo(q)
            pen.closePath()
    return orient(out)


def _topo(g):
    ps = _polys(g)
    return len(ps), sum(len(p.interiors) for p in ps)


SEMI_FIX = 1.0          # degrees: a rounded line this close to an axis is put on it ...
SEMI_OFF = 1            # ... if that moves its end by at most this many units


def _repair_rounded(d, reach):
    """The rounded outline d with its degenerate bits dropped: a segment whose points all lie within `reach` of its
    start (rounding a short piece at a corner folds it into a loop); its neighbours meet at its start. -> pathops
    outline of integer points (d_compact writes it back exactly)."""
    out = pathops.Path(); pen = out.getPen()
    for con in d_contours(d):
        segs = [list(sg) for sg in con]
        changed = True
        while changed and len(segs) > 3:
            changed = False
            for i, sg in enumerate(segs):
                pts = sg[1:]
                if reach and max(math.dist(pts[0], q) for q in pts[1:]) <= reach:
                    nxt = segs[(i + 1) % len(segs)]
                    nxt[1] = sg[1]
                    del segs[i]; changed = True
                    break
        if len(segs) < 2:
            continue
        # a line a unit off vertical or horizontal (rounding, or a neighbour moved above) made exact: its end moves
        # onto its start's axis, and the next segment starts there
        n = len(segs)
        for i, sg in enumerate(segs):
            if sg[0] != "L": continue
            (x0, y0), (x1, y1) = sg[1], sg[2]
            dx, dy = x1 - x0, y1 - y0
            if max(abs(dx), abs(dy)) < 4 or min(abs(dx), abs(dy)) == 0: continue
            if math.degrees(math.atan2(min(abs(dx), abs(dy)), max(abs(dx), abs(dy)))) < SEMI_FIX:
                if min(abs(dx), abs(dy)) <= SEMI_OFF:
                    e = (x0, y1) if abs(dx) < abs(dy) else (x1, y0)
                    sg[2] = e; segs[(i + 1) % n][1] = e
                else:                               # too far to move: a straight quadratic (not a line)
                    segs[i] = ["Q", sg[1], (round((x0 + x1) / 2), round((y0 + y1) / 2)), sg[2]]
        pen.moveTo(tuple(segs[0][1]))
        for sg in segs:
            if sg[0] == "L": pen.lineTo(tuple(sg[2]))
            elif sg[0] == "Q": pen.qCurveTo(tuple(sg[2]), tuple(sg[3]))
            else: pen.curveTo(tuple(sg[2]), tuple(sg[3]), tuple(sg[4]))
        pen.closePath()
    return out


def _stored_points(d):
    """Point count after TrueType drops exact midpoint on-curve points."""
    count = 0
    for con in d_contours(d):
        segs = [s for s in con if not (s[0] == "L" and s[1] == s[2])]
        for i, s in enumerate(segs):
            prev = segs[i - 1]
            implied = s[0] == prev[0] == "Q" and all(abs((prev[2][a] + s[2][a]) / 2 - s[1][a]) < 1e-9 for a in (0, 1))
            count += (0 if implied else 1) + (len(s) - 3 if s[0] != "L" else 0)
    return count


@lru_cache(maxsize=None)
def parent_stored_points(ch, master):
    """Raw matching-master TrueType points, or None when that parent has no drawn outline."""
    if not is_syllable(ch):
        return None
    gs, cmap, _ = _masters()[master]
    name = cmap.get(ord(ch))
    if name is None:
        return None
    glyf = gs.font["glyf"]
    glyph = glyf[name]
    return len(glyph.getCoordinates(glyf)[0]) if glyph.numberOfContours else None


@lru_cache(maxsize=None)
def parent_drawn(ch):
    """Avoid synthesizing composed topology merely to discover that no raw parent budget exists."""
    return is_syllable(ch) and any(parent_stored_points(ch, m) is not None for m in range(len(MASTERS)))


def fit_checked(g, S, hints=None, accept=None, max_points=None):
    """The first valid bounded fit of the pen geometry, in the order of the tries below.

    Every accepted fit, including smoothed fallbacks, is within FIT_MAX before
    rounding and ROUND_MAX afterwards, with valid simple rings and unchanged
    topology. accept(d), when supplied, adds caller checks on serialized data.
    max_points (optional; the release build passes none) rejects candidates above
    that stored-point budget. Trying every candidate for the fewest points instead
    of taking the first valid one tripled the build's fitting time.
    False denotes the rejected polygon fallback; builders must retry or fail.
    """
    from fontTools.pens.svgPathPen import SVGPathPen
    g = snap_axes(g)
    want = _topo(g)
    global HINT_TOL, TINY
    keep = HINT_TOL, TINY
    best = None

    def candidate(source, ft, qt, hs, htol, tiny, reaches=(0.0, 1.0, 1.5, 2.2)):
        nonlocal best
        global HINT_TOL, TINY
        HINT_TOL, TINY = htol, tiny
        try:
            p = fit_geom(source, ft, qt, hs)
        finally:
            HINT_TOL, TINY = keep
        sp = SVGPathPen(None); p.draw(sp)
        hf, simple = geom_of_d(sp.getCommands())
        if not simple or not hf.is_valid or _topo(hf) != want or not _within(hf, g, FIT_MAX):
            return False
        dd = d_compact(p)
        for reach in reaches:
            p = _repair_rounded(dd, reach); dd2 = d_compact(p)
            h, simple = geom_of_d(dd2)
            if simple and h.is_valid and _topo(h) == want and _within(h, g, ROUND_MAX):
                score = (_stored_points(dd2), len(dd2))
                if max_points is not None and score[0] > max_points:
                    continue
                if accept is not None and not accept(dd2):
                    continue
                if best is None or score < best[0]:
                    best = score, p
                return max_points is None or score[0] <= max_points
        return False

    # Parent breakpoints are useful candidates, but are not compulsory: fitting
    # an offset independently often needs fewer controls at the same accuracy.
    tries = [(FIT_TOL, QUAD_TOL, None, 0.85, TINY), (FIT_TOL, QUAD_TOL, None, 0.65, TINY),
             (FIT_TOL, QUAD_TOL, hints, HINT_TOL, TINY)]
    for ft, qt, hs, htol, tiny in tries:
        if candidate(g, ft, qt, hs, htol, tiny):
            return best[1], True
    if best is not None:
        return best[1], True

    # Expensive conservative fits are only needed when the small portfolio fails.
    tries = []
    if hints:
        tries.append((FIT_TOL, QUAD_TOL, hints, HINT_TOL / 2, TINY))
    tries += [(FIT_TOL / 3, QUAD_TOL / 3, None, HINT_TOL / 2, TINY),
              (FIT_TOL / 3, QUAD_TOL / 3, None, HINT_TOL / 2, 0.0)]
    for ft, qt, hs, htol, tiny in tries:
        candidate(g, ft, qt, hs, htol, tiny)
        if best is not None:
            return best[1], True

    # Close hairline tips that would cross when rounded. The fitted result is
    # still checked against the original pen geometry at BOTH original bounds.
    g2 = _gbuf(_gbuf(_gbuf(_gbuf(g, CLOSE_TIP), -CLOSE_TIP), -CLOSE_TIP), CLOSE_TIP)
    if _topo(g2) != want:
        # a neck thinner than 2 units (rounding splits it): thickened by one unit there
        thin = _diff(g, _open(g, 1.0))
        g2 = _union([g, _inter(_gbuf(thin, 1.0), _gbuf(g, 1.0))])
    if _topo(g2) == want:
        candidate(g2, FIT_TOL / 3, QUAD_TOL / 3, None, keep[0], keep[1])
        if best is not None:
            return best[1], True
    # Smooth unit-sized pen steps only if the same strict bounds still hold.
    for r in (LAST_R, 2 * LAST_R):
        g3 = _gbuf(_gbuf(_gbuf(_gbuf(g, r), -r), -r), r)
        if _topo(g3) != want:
            continue
        candidate(g3, FIT_TOL, QUAD_TOL, None, keep[0], keep[1], (0.0, 1.5))
        if best is not None:
            return best[1], True
    return _poly_path(g), False


LAST_R = 1.5


CLOSE_TIP = 2.0


AXIS_SNAP = 0.6         # degrees: an edge of the pen's outline this close to vertical / horizontal is made exactly so
AXIS_EDGE = 20.0        # ... if at least this long (fontbakery outline_semi_vertical flags 0.5: NanumSquareRound's
                        # ㄴ ㄷ ㄸ ㄹ stems lean 1-3 units over their height)


def snap_axes(g):
    """Every edge of g's outline at least AXIS_EDGE long and within AXIS_SNAP of vertical or horizontal made
    exactly so (both ends to their mean)."""
    from shapely.geometry import Polygon
    out = []
    changed = False
    for poly in _polys(g):
        rings = []
        for r in [poly.exterior] + list(poly.interiors):
            P = np.asarray(r.coords)[:-1].copy(); n = len(P)
            for i in range(n):
                j = (i + 1) % n
                dx, dy = P[j] - P[i]
                L = math.hypot(dx, dy)
                if L < AXIS_EDGE: continue
                ang = math.degrees(math.atan2(min(abs(dx), abs(dy)), max(abs(dx), abs(dy))))
                if 0 < ang <= AXIS_SNAP:
                    ax = 0 if abs(dx) < abs(dy) else 1
                    m = (P[i, ax] + P[j, ax]) / 2; P[i, ax] = m; P[j, ax] = m; changed = True
            rings.append(P)
        out.append(Polygon(rings[0], rings[1:]))
    if not changed:
        return g
    q = _union([p if p.is_valid else p.buffer(0) for p in out])
    return q if _topo(q) == _topo(g) else g


FIT_MAX = 1.0           # units: the fitted curves stay this close to the pen's outline, both ways
ROUND_MAX = 1.6         # units: and the outline rounded to units (on- and off-curve points each move up to 0.71)


def _within(a, b, tol):
    """a and b are within tol of each other everywhere (up to a sliver of area tol^2 / 4)."""
    lim = tol * tol / 4
    return a.difference(_gbuf(b, tol)).area <= lim and b.difference(_gbuf(a, tol)).area <= lim


# ------------------------------------------------------------------ symbols (release QA: outlines B3 S11, visual S6-S8)
# The pen above is solved on the syllables; one pen per weight with a master switch at 400, 600 and 800 made the
# brackets and geometric symbols lighter at each switch (「: ink 36.2k -> 33.1k from 300 to 400) and left their
# mitred corners. They are drawn from one master (R) at every weight instead:
#   stroke    eroded to within SKEL of its skeleton (half the thinnest stroke, less SKEL) and regrown with a round
#             pen to R's own stroke / V0 x the weight's stroke: round joins and round ends at every weight, the
#             stroke tied to the weight, the frame the syllables' (k and dy of the weight)
#   filled    its corners rounded (an opening of FILL_ROUND x R's stroke) and the ink grown by FILL_GROW x half the
#             change of the weight's stroke from 400's, at 400's scale: strictly heavier at every step
#   Latin     the square units and circled figures are Limn's own letters and figures (the play data of the same
#             weight, the shoulderless m, the superior 2), set at UNIT_SCALE / CIRCLE_FIG and given back their
#             stroke with a round pen; the circle of ①-⑩ is a ring whose stroke follows the weight
STROKE_SYM = set("「」『』〈〉《》〔〕〜～○□△▽◁▷◇☆♡。※♪")
FILL_SYM = set("●■▲▼◀▶◆★♠♣♥☎【】、ㆍ・")
UNIT_SYM = {"㎏": "kg", "㎝": "cm", "㎞": "km", "㎡": "m²", "℃": "°C"}
CIRCLED = {chr(0x2460 + i): str(i + 1) for i in range(10)}
SKEL = 1.0              # units left either side of the skeleton before the regrowth
SYM_COUNTER = 0.2       # x S: the white a stroke symbol keeps inside (『 』's), so its ink still rises
FILL_ROUND = 0.15       # x R's stroke at the scale: corner radius of the filled symbols
FILL_GROW = 0.5         # x half the change of the weight's stroke from 400's: growth of the filled symbols
UNIT_SCALE = 0.6        # Limn letters in ㎏ ㎝ ㎞ ㎡ (the widest, cm and km, fill the cell at this)
UNIT_STROKE = 0.85      # x the Latin stem: stroke of those letters
DEGC_SCALE = 0.72       # ℃: Limn's ° and C
CIRCLE_FIG = 0.46       # Limn figures in ①-⑩: cap height 700 x this
CIRCLE_GAP = 0.08       # x the figure height: white between the two figures of ⑩


def is_symbol(ch):
    return ch in STROKE_SYM or ch in FILL_SYM or ch in UNIT_SYM or ch in CIRCLED


@lru_cache(maxsize=None)
def _half_stroke(ch):
    """Half the thinnest stroke of a symbol in R (unscaled): the smaller of area / perimeter of its thinnest piece
    (a stroke of width s and length L has area s L and perimeter about 2 L) and the largest erosion that keeps
    its pieces and holes (a note's stem is thinner than its head)."""
    g = geom_of(outline(ch, 1)[0])
    ap = min(q.area / q.exterior.length if not q.interiors else q.area / q.length for q in _polys(g))
    t0 = _topo(g); lo, hi = 0.5, 150.0
    for _ in range(22):
        mid = (lo + hi) / 2
        e = _gbuf(g, -mid)
        if _topo(e) == t0 and all(q.area > 1.0 for q in _polys(e)): lo = mid
        else: hi = mid
    return 0.97 * min(ap, lo)


@lru_cache(maxsize=None)
def _play():
    import json
    p = HERE.parent / "limn-font-play.js"
    if not p.exists():
        raise FileNotFoundError(f"{p} missing: the square units and circled figures are Limn's own glyphs (make play first)")
    t = p.read_text(encoding="utf-8")
    i = t.index("window.LIMN_PLAY=") + len("window.LIMN_PLAY=")
    return json.loads(t[i:t.rindex(";")])


def _latin(w, ch):
    """A Limn glyph of weight w as shapely (y down, baseline 0), its advance, the weight's stem."""
    F = _play()[str(w)]
    g = F["glyphs"][ch]
    return geom_of_d(g["d"])[0], g["adv"], F["s"]


def _setword(w, text, scale, stroke):
    """Limn letters of weight w set at scale on the baseline (kerned as the engine kerns, and each pair opened by
    what the pen adds to both), their stroke brought back to `stroke` by the Hangul pen (counters and the white
    between letters held as a syllable's are). -> shapely, from x = 0."""
    from shapely import affinity
    F = _play()[str(w)]
    S = F["s"]
    d = (stroke - scale * S) / 2
    parts, x, prev = [], 0.0, None
    for ch in text:
        g, adv, _ = _latin(w, ch)
        if prev:
            K = F["kern"]; KC = F.get("kcls", {})
            kv = K.get(prev + ch)
            if kv is None:
                l = (KC.get(prev) or [None])[0] or prev; r = (KC.get(ch) or [None, None])[1] or ch
                kv = K.get(l + r, 0) if l + r != prev + ch else 0
            x += kv * scale + 2 * max(d, 0.0)
        parts.append(affinity.translate(affinity.scale(g, scale, scale, origin=(0, 0)), x, 0))
        x += adv * scale; prev = ch
    word = _union(parts)
    return pen_steps(word, {"S": params(w)["S"], "V": stroke, "delta": d, "hx": 0.0, "H0": stroke})


def _centre_x(g, A):
    from shapely import affinity
    x0, _, x1, _ = g.bounds
    return affinity.translate(g, A / 2 - (x0 + x1) / 2, 0)


def symbol_geom(w, ch):
    """A symbol of hangul.PUNCT at weight w (shapely, y down, centred in its one advance)."""
    from shapely import affinity
    from shapely.geometry import Point
    P, P4 = params(w), params(400)
    A = advance(ch)
    f = instance_facts(1)
    if ch in UNIT_SYM:
        text = UNIT_SYM[ch]
        sc = DEGC_SCALE if ch == "℃" else UNIT_SCALE
        return tidy_geom(_centre_x(_setword(w, text, sc, UNIT_STROKE * P["S"]), A), P["S"])
    if ch in CIRCLED:
        # the ring: NanumSquareRound R's ①'s outer circle at 400's pairing, its stroke R's ring / V0 x the stroke
        p, _ = outline("①", 1, P4["k"], (A - P4["k"] * _rec("①", 1)[1]) / 2, P4["dy"])
        x0, y0, x1, y1 = p.bounds
        cx, cy, Ro = (x0 + x1) / 2, (y0 + y1) / 2, (x1 - x0 + y1 - y0) / 4
        sw = 2 * P4["k"] * _half_stroke("①") * P["V"] / (P4["k"] * f["V0"])
        ring = Point(cx, cy).buffer(Ro, quad_segs=64).difference(Point(cx, cy).buffer(Ro - sw, quad_segs=64))
        figs = CIRCLED[ch]
        wmin = GAP_MIN * P["S"] + CLEAR_PAD
        inner = Point(cx, cy).buffer(Ro - sw, quad_segs=64)
        for step in range(12):                  # the figures as large as keeps GAP_MIN S of white to the ring
            sc = CIRCLE_FIG * (1 - 0.04 * step)
            if len(figs) == 1:
                word = _setword(w, figs, sc, sw)
            else:                               # ⑩: the two figures set by their ink, GAP_MIN S apart at least
                a = _setword(w, figs[0], sc, sw); b = _setword(w, figs[1], sc, sw)
                gap = max(CIRCLE_GAP * 700 * sc, wmin)
                b = affinity.translate(b, a.bounds[2] + gap - b.bounds[0], 0)
                word = _union([a, b])
            bx0, by0, bx1, by1 = word.bounds
            word = affinity.translate(word, cx - (bx0 + bx1) / 2, cy - (-700 * sc / 2))
            if _gbuf(inner, -wmin).contains(word):
                break
        return tidy_geom(_union([ring, word]), P["S"])
    if ch in STROKE_SYM:
        k, dy = P["k"], P["dy"]
        g = geom_of(outline(ch, 1, k, (A - k * _rec(ch, 1)[1]) / 2, dy)[0])
        h = k * _half_stroke(ch)
        sw = 2 * h * P["V"] / (k * f["V0"])
        core = _gbuf(g, -(h - SKEL)); e = sw / 2 - SKEL
        out = _gbuf(core, e) if e > 0 else core
        # two pieces (《 》's chevrons, ※'s dots and cross) keep GAP_MIN S between them, as a syllable's jamo do
        band, _ = clearance(core, max(e, 0.0), GAP_MIN * P["S"] + CLEAR_PAD)
        if not band.is_empty:
            out = _union([core, _diff(out, band)])
        # a counter keeps what the syllables' counters keep: grown into only as far as leaves cmin across it (the
        # white of 『 』 holds, and their lines grow outward)
        from shapely.geometry import Polygon
        cmin = SYM_COUNTER * P["S"] + CLEAR_PAD
        for poly in _polys(g):
            for ring in poly.interiors:
                H = Polygon(ring); mic = 2 * _mic(H)
                x = max(0.0, (mic - cmin) / 2)
                out = _diff(out, _gbuf(H, -x) if x > 0 else H)
        return tidy_geom(out, P["S"])
    # filled
    k, dy = P4["k"], P4["dy"]
    g = geom_of(outline(ch, 1, k, (A - k * _rec(ch, 1)[1]) / 2, dy)[0])
    rho = FILL_ROUND * k * f["V0"]
    delta = FILL_GROW * (P["V"] - P4["V"]) / 2
    base = _gbuf(g, delta) if delta < 0 else g
    out = _open(base, rho)
    if delta > 0:
        out = _gbuf(out, delta)
    # a hole (☎'s dial) keeps COUNTER_MIN S across, as a counter does
    from shapely.geometry import Polygon
    cmin = COUNTER_MIN * P["S"] + CLEAR_PAD
    for poly in _polys(g):
        for ring in poly.interiors:
            Hh = Polygon(ring); mic = 2 * _mic(Hh)
            x = max(0.0, min(max(delta, 0.0), (mic - cmin) / 2))
            out = _diff(out, _gbuf(Hh, -x) if x > 0 else Hh)
    return tidy_geom(out, P["S"])


# ------------------------------------------------------------------ one glyph
def advance(ch):
    """One advance at every weight (release QA, visual S3: 가 ran 815-826 across the weights, so Korean lines changed
    width with the weight): NanumSquareRound's R advance x the scale of 400 by the stroke rule, + its tracking.
    Every weight centres its ink in it."""
    k, track = _adv_rule()
    return round(_rec(ch, 1)[1] * k + track)


@lru_cache(maxsize=None)
def _adv_rule():
    P = solve_at(400, ratio(400) * stem(400))
    return P["k"], P["track"]


def min_gap(g):
    """Nearest white between two pieces of g (inf for one piece)."""
    ps = _polys(g)
    return min((ps[i].distance(ps[j]) for i in range(len(ps)) for j in range(i + 1, len(ps))), default=math.inf)


def pen_geom(w, ch, P=None, lighter=0.0, local=None):
    """The pen's outline of ch at weight w (shapely, y down, in its advance): steps 1-4 of the section above;
    and the parent's hints moved by the pen."""
    P = master_for(ch, P or params(w))
    f = instance_facts(P["m"])
    k, dy = P["k"], P["dy"]
    dx = (advance(ch) - k * _rec(ch, P["m"])[1]) / 2
    p, _ = outline(ch, P["m"], k, dx, dy)
    g = fillet_cusps(geom_of(p), CUSP * k * f["V0"])
    hints = [(k * x + dx, -k * y + dy, a, -b) for x, y, a, b in parent_hints(ch, P["m"])]
    return pen_steps(g, P, lighter, local), _hints_offset(hints, g, P["delta"] - lighter, P["hx"])


def glyph(w, ch):
    """(path y down in limn units, advance) of a Hangul glyph at limn weight w."""
    p, adv, _ = glyph_ex(w, ch)
    return p, adv


def glyph_ex(w, ch, lighter=0.0):
    """glyph() and whether the pen's outline was fitted with curves (False: the rounded polygon, a build failure)."""
    P = params(w)
    if P.get("hit"):
        # the brand's anchors (400 and 700 on curve A: the logo 림 is 700's): NanumSquareRound's own outline at the
        # pairing's scale, exactly as it was drawn before the release rules
        p, adv = outline(ch, P["m"], P["k"], P["track"] / 2, P["dy"])
        return orient(clean(p, P["S"])), adv + P["track"], True
    g, hints = (symbol_geom(w, ch), None) if is_symbol(ch) else pen_geom(w, ch, lighter=lighter)
    path, fitted = fit_checked(g, P["S"], hints)
    return path, advance(ch), fitted


# ------------------------------------------------------------------ 림
RIM_GAP = 0.35                            # white between pin and stem, in ㅣ widths (user 2026-09-28), at the brand
# The stem's top is one line at every weight, RIM_DROP under the ㅣ's top, as the Latin i holds its stem at the
# x-height and its pin at the ascender and lets the white between take the difference. With the gap held at 0.35
# instead, the stem lost 1.35 x the ㅣ width from its top and shortened as the weight grew (user 2026-09-28: "림 글자의
# ㅣ 가 굵어질수록 짧아지는 버그"). RIM_DROP is the brand's own (Quicksand Bold, ㅣ 111.5 wide): the logo is unchanged.
RIM_DROP = (1 + RIM_GAP) * 111.46
# ... but held there the white grew as the weight thinned (131 at 100 against a pin of 19; user 2026-09-29: "얇아지면
# i의 점과 세로획 사이 간격이 벌어지는 버그"). So the white is also held to the Latin i's own proportion: white / pin
# diameter as the Latin i has it at that weight (latin_white, from build_font), over the brand's (48 / 157), times
# 0.35 — the smaller of that and the room under the ㅣ's top. The brand keeps 0.35 (both are equal there); the light
# weights' pins come down with their white, as the Latin i's do.
RIM_BRAND_WHITE = 48.0 / 157.0


def _stem(cx, w, ytop, ybot):
    """A vertical stem of width w, round at both ends, y down."""
    h = w / 2
    p = _rect(cx - h, ytop + h, cx + h, ybot - h)
    for cy in (ytop + h, ybot - h):
        p = pathops.op(p, W._circle(cx, cy, h), pathops.PathOp.UNION)
    return p


def rim(w, latin_white=None):
    """NanumSquareRound's own 림 at weight w with its ㅣ replaced by an i built from the ㅣ itself (the user's
    rule, 2026-09-28): pin diameter = stem width = the ㅣ's own width; white between them 0.35 of it at the brand
    (RIM_DROP: the stem's top is one line at every weight) and never wider, in proportion to the pin, than the Latin
    i's white at that weight (latin_white); the stem down to the ㅣ's bottom. The pin top meets the ㅣ's top at the
    brand and sits lower at the light weights. The pin is not in the outline: the engine draws it (vermilion in the
    logo, ink in text).
    Returns (rest + stem path, y down), advance, (pin x, pin y down, pin r)."""
    p, adv = glyph(w, "림")
    x0, y0, x1, y1 = p.bounds; H = y1 - y0
    cs = []
    for c in p.contours:
        q = pathops.Path(); q.addPath(c); cs.append((q, q.bounds))
    # the ㅣ: the rightmost tall narrow contour that does not reach the floor (NanumSquareRound draws it apart)
    tall = [(q, b) for q, b in cs if b[3] - b[1] >= 0.3 * H and b[2] - b[0] <= 0.45 * (b[3] - b[1]) and b[3] < y1 - 0.12 * H]
    if not tall:
        raise RuntimeError(f"림 at {w}: no separate ㅣ")
    iq, ib = max(tall, key=lambda t: (t[1][0] + t[1][2]) / 2)
    rr = runs_row(iq, (ib[1] + ib[3]) / 2)
    wi = rr[-1][1] - rr[-1][0]; cx = (rr[-1][0] + rr[-1][1]) / 2
    r = wi / 2; gap = RIM_DROP - wi
    if latin_white is not None:
        gap = min(gap, RIM_GAP * wi * latin_white / RIM_BRAND_WHITE)
    if gap < 0.15 * wi and __import__("os").environ.get("LIMN_RIM_CLAMP", "1") == "1":
        gap = 0.15 * wi          # a 900 heavier than S ~140 (HALF: 155) leaves the pinned 림 no room; hold the white
    if gap < 0.15 * wi:
        raise RuntimeError(f"림 at {w}: pin and stem {gap:.1f} apart")
    stem_top = ib[1] + RIM_DROP                          # y down: one line at every weight
    pin_cy = stem_top - gap - r                          # on the ㅣ's top where the white is RIM_DROP - wi (brand, heavy)
    rest = pathops.Path()
    for q, b in cs:
        if q is not iq: rest.addPath(q)
    out = bop(rest, _stem(cx, wi, stem_top, ib[3]), pathops.PathOp.UNION)
    return out, adv, (cx, pin_cy, r), {"w": wi, "gap": gap, "top": ib[1], "bottom": ib[3]}


# ------------------------------------------------------------------ SVG path data, compact
class _DPen(BasePen):
    """SVG d with integer coordinates: absolute M, then relative l / q / c; a command letter only when it
    changes, and no separator before a minus. Rounding happens on absolute points, so nothing drifts."""

    def __init__(self):
        super().__init__(None)
        self.out = []; self.last = None; self.cur = (0, 0); self.start = (0, 0); self.qc = None

    @staticmethod
    def _r(q):
        return (int(round(q[0])), int(round(q[1])))

    def _emit(self, cmd, vals):
        s = ""
        for v in vals:
            t = str(v)
            s += t if (not s or t.startswith("-")) else " " + t
        if cmd == self.last and cmd not in "Mz":
            self.out.append(s if s.startswith("-") else " " + s)
        else:
            self.out.append(cmd + s)
        self.last = cmd

    def _rel(self, *pts):
        c = self.cur
        return tuple(v for q in pts for v in (q[0] - c[0], q[1] - c[1]))

    def _moveTo(self, pt):
        self.cur = self.start = self._r(pt); self._emit("M", self.cur)

    def _lineTo(self, pt):
        e = self._r(pt)
        if e != self.cur: self._emit("l", self._rel(e)); self.cur = e

    def _qCurveToOne(self, c, e):
        c, e = self._r(c), self._r(e)
        if c == e == self.cur: return
        if c == self.cur or c == e: self._lineTo(e); self.qc = None; return
        q = self.qc if self.last in ("q", "t") else None
        if q is not None:
            rc = (2 * self.cur[0] - q[0], 2 * self.cur[1] - q[1])     # the control a smooth "t" implies
            if abs(rc[0] - c[0]) <= 1 and abs(rc[1] - c[1]) <= 1:
                self._emit("t", self._rel(e)); self.qc = rc; self.cur = e
                return
        self._emit("q", self._rel(c, e)); self.qc = c; self.cur = e

    def _curveToOne(self, c1, c2, e):
        c1, c2, e = self._r(c1), self._r(c2), self._r(e)
        if c1 == c2 == e == self.cur: return
        self._emit("c", self._rel(c1, c2, e)); self.cur = e

    def _closePath(self):
        self._emit("z", ()); self.cur = self.start

    _endPath = _closePath


def d_compact(p):
    pen = _DPen(); p.draw(pen)
    return "".join(pen.out)


def box(p):
    x0, y0, x1, y1 = p.bounds
    return [math.floor(x0), math.floor(y0), math.ceil(x1), math.ceil(y1)]


# 400 anchor: R at the k that gives it 700's ink frame (see frame_target) — 3 % larger than the skeleton rule's
PIN[400] = (1, ink_frame() / instance_facts(1)["body"])
