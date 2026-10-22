"""Hangul data per weight: site/limn-hangul-<w>.js = window.LIMN_HANGUL[w] and site/limn-hangulext-<w>.js =
window.LIMN_HANGUL_EXT[w] (tools/hangul.py has the rules).

  uv run --no-project --with fonttools --with skia-pathops --with numpy --with shapely --with scipy python3 tools/build_hangul.py [w ...]

Glyphs: all 11,172 modern syllables U+AC00-D7A3, the compatibility jamo ㄱ-ㅣ and the Korean punctuation limn's
Latin lacks (hangul.PUNCT), in the Latin data's format ({d, adv, box}, y down, baseline 0), coordinates rounded to
units. The pages load the main file (the 2,350 KS X 1001 syllables, the jamo and the punctuation: what Korean
text sets nearly always) and the extension (the other 8,822) only when a text asks for one of them
(limn-brand.js LIMN_loadHangul); the font files (build_ttf.py) take both.

Every weight runs in one pool (LIMN_PROCS, default every core): the pairing of each weight is solved first, in
parallel, and handed to the workers. The brand 림 (its ㅣ turned into an i) lives in the Latin data
(build_font.py); here 림 is NanumSquareRound's own, for running text that asks for it (LIMN_playset {rim: "plain"}).
"""
import sys as _sys, pathlib as _pl; _sys.path.insert(0, str(_pl.Path(__file__).parent))
from ofl_header import header
import json
import math
import os
import sys
import time
from multiprocessing import Pool
from pathlib import Path
from functools import lru_cache

import hangul as H
import audit_hangul as A
import hangul_cache as HC

SITE = Path(__file__).resolve().parent.parent
OUTDIR = Path(os.environ.get("LIMN_KO_OUT") or SITE)      # test hook: write the data elsewhere (with LIMN_KO_STEMS)
KSX1001 = frozenset(H.ksx1001())
_GLYPH_CACHE = None


def _init(pre, cache=None):
    """Install frozen pairings and the optional record owner in each spawned/forked worker."""
    global _GLYPH_CACHE
    H._PRE.update(pre)
    _GLYPH_CACHE = cache


def _solve(args):
    """Solve a pairing with the already resolved smoothing targets, including cache-disabled builds."""
    w, targets = args
    H._SMOOTH_TARGETS = targets
    return w, H.params(w)


@lru_cache(maxsize=None)
def _parent_budget(ch, master):
    """Actual stored points for every drawn parent syllable, including non-KS syllables."""
    return H.parent_stored_points(ch, master)


def _fit_output(w, ch, source, cap):
    """Accept the final serialized outline, including white gates and its ink under the next weight."""
    S = H.params(w)["S"]
    measures = {}

    def accept(d):
        if d not in measures:
            measures[d] = A.measure(d, S)
        r = measures[d]
        if r["ink"] <= 0 or r["ink"] >= cap:
            return False
        if any(r[k] for k in ("specks", "tiny", "badring", "semi")):
            return False
        if r["on"] + r["off"] > 12 and not r["off"]:
            return False
        if r["gap"] is not None and r["gap"] < A.GAP_MIN * S - A.ROUND:
            return False
        if (H.is_syllable(ch) or ch in H.JAMO) and any(diameter < A.COUNTER_MIN * S - A.ROUND for _, diameter in r["holes"]):
            return False
        return True

    # No point budget: the first fit within the bounds wins. main() and the audit report the glyphs stored with
    # more than 1.5 x their parent's points, as information.
    p, fitted = H.fit_checked(source[0], S, source[1], accept=accept)
    if not fitted:
        return None
    d = H.d_compact(p)
    if not accept(d):
        return None
    return p, d, measures[d], source


def _fit_under(w, ch, source, plain, upper, cap):
    """A failed held fit may use the plain pen only when its rounded output keeps the family ordered."""
    fit = lambda candidate: _fit_output(w, ch, candidate, cap)
    result = fit(source)
    if result is not None:
        return result, None
    if source is not plain:
        result = fit(plain)
        if result is not None:
            return result, "plain"
    # the pen held back as a whole, one pen per piece: the outline the local pen started from, when its own
    # outline will not fit (a band's smoothing can leave a step no curve keeps within the bounds)
    rigid = H.pen_geom(w, ch, local=False)
    if abs(rigid[0].area - plain[0].area) > 0.5:
        result = fit(rigid)
        if result is not None:
            return result, "per-piece"
    if upper is None:
        return None, None
    t0 = H._topo(source[0])
    # A held outline may have acute unit-scale tips that cannot survive rounding. Retry this weight's own
    # lighter pen against the serialized cap before borrowing the heavier geometry, as in the prepass.
    previous = 0.0
    for lighter in (1.0, 2.0, 4.0, 8.0, 16.0, 32.0):
        candidate = H.pen_geom(w, ch, lighter=lighter)
        if H._topo(candidate[0]) != t0:
            continue
        if candidate[0].area >= cap * 0.995:
            previous = lighter
            continue
        lo, hi = previous, lighter
        for _ in range(5):
            mid = (lo + hi) / 2
            trial = H.pen_geom(w, ch, lighter=mid)
            if H._topo(trial[0]) == t0 and trial[0].area < cap * 0.995:
                hi, candidate = mid, trial
            else:
                lo = mid
        for extra in (0.0, 0.2, 0.6):
            trial = candidate if not extra else H.pen_geom(w, ch, lighter=hi + extra)
            if H._topo(trial[0]) != t0:
                continue
            result = fit(trial)
            if result is not None:
                return result, f"rounded-light-{hi + extra:.1f}"
        previous = lighter
    # Use the same topology-preserving erosion already used by the geometric prepass, now against the
    # actually accepted heavier outline. Its whites widen; every candidate still passes fit + rounded gates.
    g1, h1 = upper
    lo, hi = 0.0, 12.0
    for _ in range(9):
        mid = (lo + hi) / 2
        if H.erode_parts(g1, -mid, ORDER_STROKE).area >= cap * 0.995:
            lo = mid
        else:
            hi = mid
    for x in (hi + 0.2, hi + 0.6, hi + 1.2, hi + 2.5, hi + 5.0):
        e = H.erode_parts(g1, -x, ORDER_STROKE)
        if H._topo(e) != t0:
            continue
        candidate = e, H._hints_offset(h1, g1, -x) if h1 else None
        result = fit(candidate)
        if result is not None:
            return result, f"rounded-{x:.1f}"
    return None, None


def _one(args):
    """All weights of a few glyphs, built together so each glyph's ink rises with the weight: from the heaviest
    down, a weight whose pen outline has no less ink than INK_STEP under the next is built again with a lighter pen
    (bisection on hangul.pen_steps' `lighter`). A dense syllable the clearance holds back at 900 is held back as
    much at 800, and so on down: its whites are then only wider, and its weights keep their order."""
    ws, chars = args
    out = {w: {} for w in ws}; bad = {w: [] for w in ws}; held = []
    for ch in chars:
        try:
            sym = H.is_symbol(ch)
            geo = {w: (H.symbol_geom(w, ch), None) if sym else H.pen_geom(w, ch) for w in ws}
            plain = dict(geo)
            for rnd in range(0 if sym else 3):
                if all(geo[a][0].area < geo[b][0].area / (1 + INK_STEP) for a, b in zip(ws, ws[1:])):
                    break
                for i in range(len(ws) - 2, -1, -1):
                    w, up = ws[i], geo[ws[i + 1]][0].area
                    if geo[w][0].area < up / (1 + INK_STEP):
                        continue
                    t0 = H._topo(geo[w][0])

                    def lighten(floor):
                        """The least lighter pen that puts w under the weight above (keeping its pieces), if its
                        ink stays above floor."""
                        want = up / (1 + INK_STEP)
                        ok = lambda x: H._topo(x[0]) == t0 and x[0].area < want
                        for lt in (1.0, 2.0, 4.0, 8.0, 16.0, 32.0):
                            c = H.pen_geom(w, ch, lighter=lt)
                            if c[0].area < floor or H._topo(c[0]) != t0:
                                return None
                            if ok(c):
                                lo, hi, found = (lt / 2 if lt > 1 else 0.0), lt, (c, lt)
                                for _ in range(5):
                                    mid = (lo + hi) / 2
                                    c2 = H.pen_geom(w, ch, lighter=mid)
                                    if ok(c2): hi, found = mid, (c2, mid)
                                    else: lo = mid
                                return found
                        return None
                    # first a lighter pen here, if it costs this weight at most LIGHTEN_MAX of its ink
                    found = lighten((1 - LIGHTEN_MAX) * geo[w][0].area)
                    if found:
                        geo[w] = found[0]; held.append((w, ch, round(found[1], 1))); continue
                    # then the heavier weight with the local pen (its whites held in bands, not by one pen per
                    # piece), if that keeps its pieces and whites and stays under the weight above it
                    wu = ws[i + 1]
                    cap = geo[ws[i + 2]][0].area / (1 + INK_STEP) if i + 2 < len(ws) else math.inf
                    c = H.pen_geom(wu, ch, local=True)
                    clear = min(H.min_gap(geo[wu][0]), H.GAP_MIN * H.params(wu)["S"] + H.CLEAR_PAD - 1)
                    if H._topo(c[0]) == H._topo(geo[wu][0]) and up < c[0].area < cap and H.min_gap(c[0]) >= clear:
                        geo[wu] = c; up = c[0].area; held.append((wu, ch, "local"))
                        if geo[w][0].area < up / (1 + INK_STEP):
                            continue
                    # then any lighter pen
                    found = lighten(0.0)
                    if found:
                        geo[w] = found[0]; held.append((w, ch, round(found[1], 1))); continue
                    want = up / (1 + INK_STEP)
                    # no lighter pen keeps the pieces: the heavier weight's own outline, eroded just enough
                    g1, h1 = geo[ws[i + 1]]
                    lo, hi = 0.0, 12.0
                    for _ in range(9):
                        mid = (lo + hi) / 2
                        if H.erode_parts(g1, -mid, ORDER_STROKE).area >= want: lo = mid
                        else: hi = mid
                    for x in (hi + 0.2, hi + 0.6, hi + 1.2, hi + 2.5, hi + 5.0):   # past the bisection's edge
                        e = H.erode_parts(g1, -x, ORDER_STROKE)
                        if H._topo(e) == t0 and e.area < want:
                            geo[w] = (e, H._hints_offset(h1, g1, -x) if h1 else None); held.append((w, ch, -round(x, 1)))
                            break
            cap, upper = math.inf, None
            for w in reversed(ws):
                result, adjustment = _fit_under(w, ch, geo[w], plain[w], upper, cap)
                if result is None:
                    raise RuntimeError(f"weight {w}: no curve fit passes geometry, whites and rounded ink order")
                p, d, measured, selected = result
                out[w][ch] = {"d": d, "adv": float(H.advance(ch)), "box": H.box(p)}
                if adjustment is not None:
                    held.append((w, ch, adjustment))
                # The cap is measured after rounding. Borrow that same accepted
                # outline for erosion, rather than reintroducing raw pen tips
                # that were removed by its checked fit.
                upper = H.geom_of_d(d)[0], selected[1]
                cap = measured["ink"] / (1 + INK_STEP)
        except Exception as ex:                      # reported with the glyph, never skipped
            import traceback
            raise RuntimeError(f"{ch} (U+{ord(ch):04X}): {ex}\n{traceback.format_exc()}") from None
    return out, bad, held


INK_STEP = 0.02         # each weight's pen outline at least 2 % more ink than the one below
LIGHTEN_MAX = 0.08      # a lighter pen is tried first if it costs at most this share of the weight's ink
ORDER_STROKE = 2.0     # units: held erosion must leave necks wide enough to survive integer rounding


def main_set():
    """What the main file carries: KS X 1001, the jamo, the punctuation."""
    return H.ksx1001() + H.JAMO + H.PUNCT


def _cached_one(args):
    """Complete and publish one character before the next; same-key concurrent builds coalesce."""
    ws, ch = args
    if _GLYPH_CACHE is None or not HC.cache_enabled():
        return (*_one((ws, [ch])), False)
    with _GLYPH_CACHE.lock(ch):
        record = _GLYPH_CACHE.read(ch)
        if isinstance(record, HC.GlyphRecord):
            return record.glyphs, {w: [] for w in ws}, record.held, True
        out, bad, held = _one((ws, [ch]))
        if not any(bad.values()):
            _GLYPH_CACHE.store(ch, HC.GlyphRecord(out, held))
        return out, bad, held, False


def write(w, glyphs, P):
    """Serialize glyphs in the existing charset/property order to the main and extension JS files."""
    main = set(main_set())
    order = [c for c in H.charset() if c in glyphs]
    meta = {k: (round(v, 4) if isinstance(v, float) else v) for k, v in P.items()}
    track = round(H.advance("가") - P["k"] * H._rec("가", P["m"])[1], 2)
    ext = [c for c in order if c not in main]
    data = {"w": w, "parent": "NanumSquareRound " + P["master"] + " (NAVER, SIL OFL 1.1)", "pair": meta,
            "track": track, "bnd": H.BOUNDARY, "ext": f"limn-hangulext-{w}.js" if ext else None, "n": len(order),
            "glyphs": {c: glyphs[c] for c in order if c in main}}
    out = OUTDIR / f"limn-hangul-{w}.js"
    out.write_text(header("build_hangul.py") + "window.LIMN_HANGUL=window.LIMN_HANGUL||{};window.LIMN_HANGUL[" + str(w) + "]="
                   + json.dumps(data, ensure_ascii=False, separators=(",", ":")) + ";\n")
    xout = OUTDIR / f"limn-hangulext-{w}.js"
    xdata = {"w": w, "glyphs": {c: glyphs[c] for c in ext}}
    xout.write_text(header("build_hangul.py") + "window.LIMN_HANGUL_EXT=window.LIMN_HANGUL_EXT||{};window.LIMN_HANGUL_EXT[" + str(w) + "]="
                    + json.dumps(xdata, ensure_ascii=False, separators=(",", ":")) + ";\n")
    return out, xout


def main():
    """Build the selected family, reusing exact records and reporting durable per-glyph progress."""
    ws = [int(a) for a in sys.argv[1:]] or list(H.WEIGHTS)
    procs = int(os.environ.get("LIMN_PROCS", os.cpu_count() or 4))
    if procs < 1:
        raise ValueError("LIMN_PROCS must be positive")
    t0 = time.time()
    inputs = HC.fingerprint(H.HERE) if HC.cache_enabled() else None
    requested = H.charset()
    if "LIMN_KO_CHARS" in os.environ:
        if not os.environ.get("LIMN_KO_OUT") or OUTDIR.resolve().is_relative_to(SITE.resolve()):
            raise ValueError("LIMN_KO_CHARS requires LIMN_KO_OUT outside site/ to protect full build data")
        selected = set(os.environ["LIMN_KO_CHARS"])
        if not selected or selected.difference(requested):
            raise ValueError("LIMN_KO_CHARS must select characters from the Hangul charset")
        requested = [c for c in requested if c in selected]
    OUTDIR.mkdir(parents=True, exist_ok=True)
    chars = [c for c in requested if H.has(c)]
    missing = [c for c in requested if not H.has(c)]
    # Symbols use params(400) even for subset weights. Freeze that resolved input too.
    solved_weights = list(dict.fromkeys(ws + [400]))
    with Pool(min(procs, len(H.WEIGHTS) * 2)) as pool:
        targets = None
        if H.SMOOTH_INK:
            targets = H._cached_targets()
            if targets is None:
                targets = H.smooth_solve(pool.map)
        pre = dict(pool.map(_solve, [(w, targets) for w in solved_weights]))
    print(f"pairing solved for {' '.join(map(str, ws))} in {time.time() - t0:.0f} s", flush=True)
    for w in ws:
        P = pre[w]
        print(f"  {w}: {P['master']:>2} pen {P['delta']:+6.2f} vertical {P['hx']:+5.2f} k {P['k']:.4f} dy {P['dy']:+6.1f}"
              f" V {P['V']:6.1f} (rule {P.get('V_rule', P['V']):6.1f}) S {P['S']:6.1f}", flush=True)
    cache = None
    if HC.cache_enabled():
        if HC.fingerprint(H.HERE) != inputs:
            raise RuntimeError("Hangul inputs changed while solving pairings; retry with frozen inputs")
        root = Path(os.environ.get("LIMN_KO_CACHE_DIR") or H.FDIR / ".glyph-cache")
        cache = HC.GlyphCache(root, ws, pre, inputs)
    glyphs = {w: {} for w in ws}
    bad = {w: [] for w in ws}
    held = []
    reused, created, pending = 0, 0, []
    for ch in chars:
        record = cache.read(ch) if cache else HC.Miss()
        if isinstance(record, HC.Miss):
            pending.append(ch)
        else:
            for w in ws:
                glyphs[w].update(record.glyphs[w])
            held += record.held
            reused += 1
    print(f"glyph cache: reused {reused}, pending {len(pending)} / {len(chars)} characters", flush=True)
    if pending:
        with Pool(procs, initializer=_init, initargs=(pre, cache)) as pool:
            tasks = [(ws, ch) for ch in pending]
            for part, b, hd, hit in pool.imap_unordered(_cached_one, tasks, chunksize=1):
                for w in ws:
                    glyphs[w].update(part[w]); bad[w] += b[w]
                held += hd
                reused += int(hit)
                created += int(not hit)
                done = reused + created
                if done % 100 == 0 or done == len(chars):
                    elapsed = time.time() - t0
                    new_done = done - (len(chars) - len(pending))
                    eta = elapsed * (len(chars) - done) / max(1, new_done)
                    print(f"glyphs {done}/{len(chars)}; reused {reused}, new {created}; "
                          f"elapsed {elapsed:.0f} s, remaining ~{eta:.0f} s", flush=True)
    print(f"glyph cache: reused {reused}, new {created}; {time.time() - t0:.1f} s", flush=True)
    if cache and HC.fingerprint(H.HERE, refresh_dependencies=True) != inputs:
        cache.discard(chars)
        raise RuntimeError("Hangul inputs changed during production; discarded family records, retry with frozen inputs")
    # Cache hits need these same frozen pairings when the main process writes metadata/reports.
    H._PRE.update(pre)
    print(f"held lighter so the ink rises: {len(held)} glyph-weights, e.g. {' '.join(f'{c}{w}-{x}' for w, c, x in held[:12])}", flush=True)
    for w in ws:
        out, xout = write(w, glyphs[w], pre[w])
        print(f"{out.name} + {xout.name}: {len(glyphs[w])} glyphs, {out.stat().st_size / 1e6:.2f} + {xout.stat().st_size / 1e6:.2f} MB"
              + (f", NOT FITTED (polygon): {''.join(bad[w][:40])}" if bad[w] else "")
              + (f", not in NanumSquareRound: {''.join(missing)}" if missing else ""), flush=True)
    excess = []
    for w in ws:
        for ch, glyph in glyphs[w].items():
            if not H.parent_drawn(ch):
                continue
            master = H.master_for(ch, pre[w])["m"]
            raw = _parent_budget(ch, master)
            count = H._stored_points(glyph["d"])
            if raw is not None and count > math.floor(1.5 * raw):
                excess.append({"w": w, "ch": ch, "points": count, "raw_parent": raw,
                               "limit": math.floor(1.5 * raw), "master": H.MASTERS[master]})
    report = OUTDIR / "hangul-point-excess.json"
    if excess:
        report.write_text(json.dumps(excess, ensure_ascii=False, indent=2) + "\n")
        print(f"points: {len(excess)} glyph-weights stored with more than 1.5 x their parent's points (information), "
              f"in {report.name}", flush=True)
    elif report.exists():
        report.unlink()
    print(f"build_hangul: {len(ws)} weights in {time.time() - t0:.0f} s")
    if any(bad.values()):
        sys.exit(1)


if __name__ == "__main__":
    main()
