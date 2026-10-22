"""Gates on the Hangul data (make hangul): any failure exits 1, so `make check` fails.

  uv run --no-project --with skia-pathops --with fonttools --with numpy --with shapely python3 tools/audit_hangul.py
      [w ...]            only these weights (the cross-weight gates then run on them only)
      --json FILE        every measure, per glyph and weight
      --no-parent        skip the parent (NanumSquareRound) topology reference

Reads site/limn-hangul-<w>.js and site/limn-hangulext-<w>.js (tools/build_hangul.py) and measures every glyph from its
rounded outline, as a browser or a font file draws it: even-odd region of the flattened curves (shapely/GEOS), its
pieces, their holes and the white between them. S is the weight's Latin stem (the data's pair.S).

  coverage     all 11,172 modern syllables U+AC00-D7A3, the compatibility jamo and hangul.PUNCT at every weight
  advance      one advance per glyph at every weight
  polygon      no outline of more than 12 points without an off-curve point (the pen output is curve-fitted)
  topology     pieces and holes the same at every weight, and the syllables' and jamo's those of the parent
               (hangul.ref_topo: what most of NanumSquareRound's masters draw): no counter closes or opens, no two
               jamo touch
  counter      the smallest hole of a syllable or jamo holds a disc of COUNTER_MIN x S (inscribed-circle diameter)
  gap          the white between two pieces of a glyph is at least GAP_MIN x S (nearest distance)
               (both less ROUND units: the outline is rounded to units after the pen held them)
  specks       no piece smaller than (0.3 S)^2, no hole as small that is thinner than half a counter (a pinhole
               or slit), no contour of 3 points or fewer, every contour simple
  ink          ink area rises with the weight, strictly, for every glyph
  vertical     no line within 0.5 degrees of vertical or horizontal that is not exactly so (fontbakery
               outline_semi_vertical)
"""
import sys as _sys, pathlib as _pl; _sys.path.insert(0, str(_pl.Path(__file__).parent))
import json
import math
import os
import re
import sys
from multiprocessing import Pool
from pathlib import Path

SITE = Path(__file__).resolve().parent.parent
DATA = Path(os.environ.get("LIMN_KO_OUT") or SITE)        # where build_hangul.py wrote (its test hook)
WEIGHTS = tuple(range(100, 1000, 100))
COUNTER_MIN = 0.3        # x S, inscribed-circle diameter of the smallest counter
GAP_MIN = 0.3            # x S, nearest white between two pieces (jamo, or the parts of one jamo)
SPECK = 0.3              # (SPECK S)^2: smallest hole or piece
ROUND = 1.0              # units of slack on counter and gap for the rounding to units
SEMI = 0.5               # degrees: a line this close to vertical / horizontal must be exactly so (fontbakery)
SYLLABLES = [chr(c) for c in range(0xAC00, 0xD7A4)]


def load(w):
    """{ch: {d, adv, box}} of weight w, main file and extension merged; (data meta, glyphs)."""
    def read(p, marker):
        t = p.read_text(encoding="utf-8")
        i = t.index(marker) + len(marker)
        return json.loads(t[i:t.rindex(";")])
    main = read(DATA / f"limn-hangul-{w}.js", f"window.LIMN_HANGUL[{w}]=")
    glyphs = dict(main["glyphs"])
    ext = DATA / f"limn-hangulext-{w}.js"
    if ext.exists():
        glyphs.update(read(ext, f"window.LIMN_HANGUL_EXT[{w}]=")["glyphs"])
    return main, glyphs


# ------------------------------------------------------------------ outline parsing (the data's compact SVG)
_TOK = re.compile(r"[MmLlHhVvQqTtCcZz]|-?(?:\d+\.?\d*|\.\d+)")


def contours(d):
    """SVG d -> [[segment]], segment = ("L", p0, p1) | ("Q", p0, c, p1) | ("C", p0, c1, c2, p1); absolute."""
    toks = _TOK.findall(d or "")
    out, cur = [], []
    i, cmd = 0, None
    x = y = sx = sy = 0.0
    qc = None                                # last quadratic control (for t)

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


def flatten(con):
    pts = []
    for s in con:
        p0 = s[1]; pts.append(p0)
        if s[0] == "L":
            continue
        L = sum(math.dist(s[k], s[k + 1]) for k in range(1, len(s) - 1))
        n = max(2, min(24, int(L / 2.5) + 1))
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


def points(con):
    """(on-curve, off-curve) point counts of a contour as TrueType stores it: an on-curve point exactly midway
    between the off-curve points on either side is implied, not stored (build_ttf.py drops it)."""
    segs = [s for s in con if not (s[0] == "L" and s[1] == s[2])]
    n = len(segs); on = 0
    for i, s in enumerate(segs):
        prev = segs[i - 1]
        if s[0] == "Q" and prev[0] == "Q":
            c0, c1, p = prev[2], s[2], s[1]
            if abs((c0[0] + c1[0]) / 2 - p[0]) < 1e-9 and abs((c0[1] + c1[1]) / 2 - p[1]) < 1e-9:
                continue
        on += 1
    off = sum(len(s) - 3 for s in segs if s[0] != "L")
    return on, off


# ------------------------------------------------------------------ one glyph
def measure(d, S):
    from shapely import maximum_inscribed_circle
    from shapely.geometry import LinearRing, Polygon
    from shapely.validation import make_valid
    cons = contours(d)
    on = off = 0; tiny = 0; bad_ring = 0; semi = []
    region = None
    for con in cons:
        a, b = points(con); on += a; off += b
        if a + b <= 3 and Polygon(flatten(con) or [(0, 0)] * 3).area < (SPECK * S) ** 2:
            tiny += 1                                   # a stray contour (a real triangle counter has room)
        for s in con:
            if s[0] != "L": continue
            (x0, y0), (x1, y1) = s[1], s[2]
            dx, dy = abs(x1 - x0), abs(y1 - y0)
            if max(dx, dy) < 4: continue
            ang = math.degrees(math.atan2(min(dx, dy), max(dx, dy)))
            if 0 < ang < SEMI:
                semi.append(((x0, y0), (x1, y1)))
        pts = flatten(con)
        if len(pts) < 3:
            bad_ring += 1; continue
        ring = LinearRing(pts)
        if not ring.is_simple:
            bad_ring += 1
        poly = Polygon(pts)
        if not poly.is_valid:
            poly = make_valid(poly)
        region = poly if region is None else region.symmetric_difference(poly)
    res = {"on": on, "off": off, "nc": len(cons), "tiny": tiny, "badring": bad_ring, "semi": len(semi)}
    if region is None or region.is_empty:
        res.update(ink=0.0, ncomp=0, nhole=0, holes=[], gap=None, specks=0)
        return res
    polys = [region] if region.geom_type == "Polygon" else [g for g in getattr(region, "geoms", []) if g.geom_type == "Polygon"]
    lim = (SPECK * S) ** 2
    holes = []
    specks = 0
    for p in polys:
        if p.area < lim: specks += 1
        for h in p.interiors:
            hp = Polygon(h)
            try:
                r = maximum_inscribed_circle(hp, tolerance=0.25).length
            except Exception:
                r = 0.0
            if hp.area < lim and 2 * r < 0.5 * COUNTER_MIN * S: specks += 1      # a pinhole or slit, not a counter
            holes.append((round(hp.area, 1), round(2 * r, 2)))
    gap = None
    for i in range(len(polys)):
        bi = polys[i].bounds
        for j in range(i + 1, len(polys)):
            bj = polys[j].bounds
            if bi[2] + 2 * S < bj[0] or bj[2] + 2 * S < bi[0] or bi[3] + 2 * S < bj[1] or bj[3] + 2 * S < bi[1]:
                continue
            g = polys[i].distance(polys[j])
            gap = g if gap is None else min(gap, g)
    res.update(ink=round(region.area, 1), ncomp=len(polys), nhole=len(holes), holes=holes,
               gap=None if gap is None else round(gap, 2), specks=specks)
    return res


def _task(args):
    w, S, items = args
    return w, {ch: measure(d, S) for ch, d in items}


def _parent_task(chars):
    import hangul as H
    return {ch: tuple(H.ref_topo(ch)) for ch in chars}


def point_excess(w, glyphs):
    """Check the raw matching-master ceiling on every drawn syllable."""
    import hangul as H
    rows = []
    P = H.params(w)
    for ch, glyph in glyphs.items():
        if not H.parent_drawn(ch):
            continue
        master = H.master_for(ch, P)["m"]
        raw = H.parent_stored_points(ch, master)
        count = sum(sum(points(c)) for c in contours(glyph["d"]))
        if raw is not None and count > math.floor(1.5 * raw):
            rows.append({"w": w, "ch": ch, "points": count, "raw_parent": raw,
                         "limit": math.floor(1.5 * raw), "master": H.MASTERS[master]})
    return rows


PARENT_INK_MIN = 0.5     # a syllable's ink over 가's, against the same in its weight's master: under it, it lost its weight
PARENT_INK_INFO = 0.8    # reported, not failed: the whites the rules keep cost a dense syllable some ink at 800-900


def parent_ink(m):
    """Ink of every drawn syllable over the ink of 가 in NanumSquareRound master m (decomposed outlines)."""
    import hangul as H
    import pathops
    from fontTools.pens.recordingPen import DecomposingRecordingPen
    gs, cmap, _ = H._masters()[m]
    font = gs.font; glyphs = font.getGlyphSet(); cm = font.getBestCmap()
    out = {}
    for ch in SYLLABLES:
        name = cm.get(ord(ch))
        if name is None:
            continue
        rp = DecomposingRecordingPen(glyphs); glyphs[name].draw(rp)
        if not rp.value:
            continue
        p = pathops.Path(); rp.replay(p.getPen()); p.simplify(fix_winding=True)
        out[ch] = abs(p.area)
    base = out["가"]
    return {ch: a / base for ch, a in out.items()}


def parent_ink_findings(ws, meta, M, chars, ratios):
    """(fails, reports): (x, w, ch) where a syllable's ink over 가's at weight w, divided by the same ratio in that
    weight's master (ratios(master name) -> {ch: ratio}), is under PARENT_INK_MIN, or under PARENT_INK_INFO."""
    pink, low, info = {}, [], []
    for w in ws:
        name = meta[w]["pair"]["master"]
        if name not in pink:
            pink[name] = ratios(name)
        pr, base = pink[name], M[w]["가"]["ink"]
        for ch in chars:
            if ch in pr:
                x = M[w][ch]["ink"] / base / pr[ch]
                if x < PARENT_INK_MIN: low.append((round(x, 2), w, ch))
                elif x < PARENT_INK_INFO: info.append((round(x, 2), w, ch))
    return low, info


def chunks(seq, n):
    k = max(1, len(seq) // n)
    return [seq[i:i + k] for i in range(0, len(seq), k)]


def main():
    args = sys.argv[1:]
    jpath = None
    if "--json" in args:
        i = args.index("--json"); jpath = args[i + 1]; del args[i:i + 2]
    parent = "--no-parent" not in args
    args = [a for a in args if a != "--no-parent"]
    ws = [int(a) for a in args] or list(WEIGHTS)
    procs = int(os.environ.get("LIMN_PROCS", os.cpu_count() or 4))
    import hangul as H
    want = SYLLABLES + H.JAMO + H.PUNCT
    data, meta = {}, {}
    fails = []

    def fail(kind, msg):
        fails.append((kind, msg))
    tasks = []
    for w in ws:
        m, g = load(w)
        meta[w] = m; data[w] = g
        miss = [c for c in want if c not in g]
        if miss:
            fail("coverage", f"{w}: {len(miss)} missing, e.g. {''.join(miss[:20])}")
        S = m["pair"]["S"]
        for part in chunks(sorted(g.items()), procs * 4):
            tasks.append((w, S, [(ch, v["d"]) for ch, v in part]))
    M = {w: {} for w in ws}
    ref = {}
    with Pool(procs) as pool:
        pj = pool.map_async(_parent_task, chunks(SYLLABLES + H.JAMO, procs * 2)) if parent else None
        for w, r in pool.imap_unordered(_task, tasks):
            M[w].update(r)
        if pj is not None:
            for r in pj.get():
                ref.update(r)
    chars = sorted(set.intersection(*[set(M[w]) for w in ws]))
    ko = lambda c: H.is_syllable(c) or c in H.JAMO
    stats = {k: {w: 0 for w in ws} for k in ("polygon", "counter", "gap", "specks", "tiny", "badring", "semi")}
    worst = {k: [] for k in ("counter", "gap")}
    for w in ws:
        S = meta[w]["pair"]["S"]
        for ch in chars:
            r = M[w][ch]
            if r["on"] + r["off"] > 12 and r["off"] == 0: stats["polygon"][w] += 1
            for k in ("specks", "tiny", "badring", "semi"):
                if r[k]: stats[k][w] += 1
            if ko(ch) and r["holes"]:
                c = min(h[1] for h in r["holes"])
                if c < COUNTER_MIN * S - ROUND:
                    stats["counter"][w] += 1; worst["counter"].append((round(c / S, 3), w, ch))
            if r["gap"] is not None and r["gap"] < GAP_MIN * S - ROUND:
                stats["gap"][w] += 1; worst["gap"].append((round(r["gap"] / S, 3), w, ch))
    for k, v in stats.items():
        if any(v.values()):
            ex = ""
            if k in worst:
                ex = " worst " + " ".join(f"{ch}{w}:{x}" for x, w, ch in sorted(worst[k])[:12])
            fail(k, "per weight " + " ".join(f"{w}:{n}" for w, n in v.items()) + ex)
    excess = [row for w in ws for row in point_excess(w, data[w])]
    if excess:                  # information, not a gate: the release fits for accuracy, not for the fewest points
        print(f"  info points: {len(excess)} drawn glyph-weights over 1.5 x the matching master's points, e.g. "
              + " ".join(f"{r['ch']}{r['w']}:{r['points']}>{r['limit']}" for r in excess[:12]))
    # cross-weight gates
    topo, mono, adv, pref = [], [], [], []
    for ch in chars:
        seq = [M[w][ch] for w in ws]
        t = {(r["ncomp"], r["nhole"]) for r in seq}
        if len(t) > 1:
            topo.append(ch)
        elif parent and ko(ch) and ch in ref and next(iter(t)) != ref[ch]:
            pref.append(ch)
        ink = [r["ink"] for r in seq]
        if any(b <= a for a, b in zip(ink, ink[1:])):
            mono.append(ch)
        if len({data[w][ch]["adv"] for w in ws}) > 1:
            adv.append(ch)
    if topo: fail("topology", f"{len(topo)} glyphs change pieces or holes across weights: {''.join(topo[:60])}")
    if pref: fail("topology", f"{len(pref)} glyphs differ from the parent's pieces / holes at every weight: {''.join(pref[:60])}")
    if mono: fail("ink", f"{len(mono)} glyphs whose ink does not rise with the weight: {''.join(mono[:60])}")
    if adv: fail("advance", f"{len(adv)} glyphs whose advance changes with the weight: {''.join(adv[:60])}")
    # each weight against its master: a dense syllable held back as a whole kept 쪽 at Regular's ink at 900, and the
    # ink order then held every weight under it (2026-10-01, 0.30 of the master's proportion); no other gate saw it
    if parent:
        low, info = parent_ink_findings(ws, meta, M, chars, lambda name: parent_ink(H.MASTERS.index(name)))
        if low:
            fail("parent-ink", f"{len(low)} glyph-weights under {PARENT_INK_MIN} of their master's ink proportion: "
                 + " ".join(f"{ch}{w}:{x}" for x, w, ch in sorted(low)[:20]))
        if info:
            per = {w: sum(1 for _, v, _c in info if v == w) for w in ws}
            print(f"  info parent-ink: {len(info)} glyph-weights {PARENT_INK_MIN}-{PARENT_INK_INFO} of their master's "
                  f"proportion, per weight " + " ".join(f"{w}:{n}" for w, n in per.items()) + "; lowest "
                  + " ".join(f"{ch}{w}:{x}" for x, w, ch in sorted(info)[:12]))
    # summary
    tot = {w: (sum(M[w][c]["on"] for c in chars), sum(M[w][c]["off"] for c in chars)) for w in ws}
    print(f"audit_hangul: {len(chars)} glyphs x {len(ws)} weights")
    print("  points on/off per weight: " + "  ".join(f"{w}:{a}/{b}" for w, (a, b) in tot.items()))
    for kind, msg in fails:
        print(f"  FAIL {kind}: {msg}")
    if jpath:
        Path(jpath).write_text(json.dumps({"metrics": {str(w): M[w] for w in ws}, "parent": ref,
                                           "point_excess": excess, "fails": fails}, ensure_ascii=False))
    print("audit_hangul: OK" if not fails else f"audit_hangul: {len(fails)} gates failed")
    sys.exit(1 if fails else 0)


if __name__ == "__main__":
    main()
