"""Reproduce the bounded #30 ink sheet and point/size experiment without changing production.

Run from the repository root with the build dependencies (and brotli):
  uv run --no-project --with fonttools --with skia-pathops --with numpy --with shapely \
    --with scipy --with brotli python3 site/tools/review_hangul_quality.py sheet --out /tmp/hangul-quality
Replace ``sheet`` with ``benchmark`` to compare a three-candidate portfolio with the first valid fit.
All outputs are review artifacts, not replacement production glyphs. Pairings are frozen from the input JS;
these contain four-decimal values, so regenerated first-fit glyphs need not equal the historical build.
"""

import argparse
import hashlib
import html
import importlib.metadata
import json
import multiprocessing
import platform
import time
from pathlib import Path

import audit_hangul as A
import build_hangul as B
import hangul as H
from fontTools.fontBuilder import FontBuilder
from fontTools.pens.svgPathPen import SVGPathPen
from fontTools.pens.ttGlyphPen import TTGlyphPen
from shapely.geometry import Polygon
from shapely.validation import make_valid

__all__ = ["ink_area", "measure_failures", "main"]

SAMPLE = "가굶쬡똴쫠헬쪽헤를훑갂훻"
STYLE = """
body{font:15px/1.5 system-ui,sans-serif;margin:24px;color:#20282a;background:#f2f3ef}
main{max-width:1440px;margin:auto}h1{font-size:28px}h2{margin-top:40px;border-bottom:2px solid #bac3c0}
.cards{display:grid;grid-template-columns:repeat(auto-fit,minmax(315px,1fr));gap:12px}
article{background:white;border:1px solid #d5dbd7;border-radius:10px;padding:12px}
.pair{display:flex;gap:8px}.glyph{flex:1;min-width:0;text-align:center}.glyph svg{display:block;width:100%;height:140px}
.glyph small{font-size:12px;color:#465756}p{max-width:95ch}.meta{font-size:12px;color:#465756}
table{border-collapse:collapse;background:white}td,th{padding:6px 12px;border:1px solid #d5dbd7;text-align:right}
@media(max-width:600px){body{margin:12px}.cards{grid-template-columns:1fr}.glyph svg{height:135px}}
"""


def ink_area(d: str) -> float:
    """Return ink with the audit's identical flattening and even-odd composition, omitting white-circle work."""
    region = None
    for contour in A.contours(d):
        points = A.flatten(contour)
        if len(points) < 3:
            continue
        polygon = Polygon(points)
        if not polygon.is_valid:
            polygon = make_valid(polygon)
        region = polygon if region is None else region.symmetric_difference(polygon)
    return 0.0 if region is None else round(region.area, 1)


def measure_failures(measured: dict, stem: float) -> list[str]:
    """Return the existing serialized audit gate names failed by a modern Hangul syllable."""
    failed = [key for key in ("specks", "tiny", "badring", "semi") if measured[key]]
    if measured["ink"] <= 0:
        failed.append("empty")
    if measured["on"] + measured["off"] > 12 and not measured["off"]:
        failed.append("polygon")
    if measured["gap"] is not None and measured["gap"] < A.GAP_MIN * stem - A.ROUND:
        failed.append("gap")
    if any(diameter < A.COUNTER_MIN * stem - A.ROUND for _, diameter in measured["holes"]):
        failed.append("counter")
    return failed


def _inputs(source: Path) -> tuple[dict, dict]:
    """Load all nine immutable JS inputs through the audit's existing reader."""
    A.DATA = source
    meta, data = {}, {}
    for weight in A.WEIGHTS:
        meta[weight], data[weight] = A.load(weight)
    return meta, data


def _provenance(source: Path) -> dict:
    """Hash every outline, parent and producer input needed to identify this review independently."""
    files = list(source.glob("limn-hangul*.js"))
    files += list(H.FDIR.glob("*.ttf"))
    files += [Path(__file__), Path(A.__file__), Path(B.__file__), Path(H.__file__), Path(H.W.__file__)]
    files.append(Path(__file__).with_name("build_ttf.py"))
    return {
        "python": platform.python_version(),
        "platform": platform.platform(),
        "packages": {
            name: importlib.metadata.version(name)
            for name in ("fonttools", "skia-pathops", "numpy", "shapely", "scipy", "brotli")
        },
        "sha256": {str(path): hashlib.sha256(path.read_bytes()).hexdigest() for path in sorted(files)},
        "pairing_precision": "Input JS pairings serialize floats to four decimal places.",
    }


def _ink_weight(args: tuple) -> tuple:
    """Measure one weight's ink only in a worker, preserving the audit's rounded area values."""
    weight, glyphs = args
    return weight, {char: {"ink": ink_area(glyphs[char]["d"])} for char in A.SYLLABLES}


def _svg(d: str, label: str) -> str:
    """Render an outline in a fixed 1000-UPM frame shared by every before/after and parent pair."""
    return (
        '<div class="glyph"><svg viewBox="-100 -900 1050 1100" role="img" '
        f'aria-label="{html.escape(label)}"><path d="{html.escape(d)}" fill="#152b2e" '
        'fill-rule="evenodd"/><path d="M-100 0H950" stroke="#adb9b6" stroke-width="1"/></svg>'
        f"<small>{html.escape(label)}</small></div>"
    )


def _page(title: str, intro: str, sections: list[str]) -> str:
    """Return a self-contained responsive review page whose glyph drawings need no fonts or network."""
    return (
        '<!doctype html><html lang="ko"><meta charset="utf-8">'
        '<meta name="viewport" content="width=device-width, initial-scale=1">'
        f"<title>{html.escape(title)}</title><style>{STYLE}</style><main><h1>{html.escape(title)}</h1>"
        f"<p>{intro}</p>{''.join(sections)}</main></html>"
    )


def sheet(source: Path, out: Path, procs: int) -> None:
    """Save exact low-ink findings and scaled parent comparisons for all nine historical weights."""
    started = time.perf_counter()
    meta, data = _inputs(source)
    H._PRE.update({w: meta[w]["pair"] for w in A.WEIGHTS})
    with multiprocessing.Pool(procs) as pool:
        measured = dict(pool.map(_ink_weight, [(w, data[w]) for w in A.WEIGHTS]))
    parent = {name: A.parent_ink(i) for i, name in enumerate(H.MASTERS)}
    low, info = A.parent_ink_findings(A.WEIGHTS, meta, measured, A.SYLLABLES, parent.__getitem__)
    crosschecks = []
    for weight, char in [(300, "굶"), (400, "쫠"), (700, "헬"), (900, "를"), (900, "가")]:
        full = A.measure(data[weight][char]["d"], meta[weight]["pair"]["S"])["ink"]
        fast = measured[weight][char]["ink"]
        if full != fast:
            raise RuntimeError(f"Ink fast path differs from audit: {weight} {char}: {fast} != {full}")
        crosschecks.append({"w": weight, "ch": char, "ink": full, "equal": True})
    findings, sections = [], []
    for weight in A.WEIGHTS:
        cards = []
        for _, _, char in sorted(row for row in low + info if row[1] == weight):
            nominal = meta[weight]["pair"]
            effective = H.master_for(char, nominal)
            ratio = measured[weight][char]["ink"] / measured[weight]["가"]["ink"] / parent[nominal["master"]][char]
            row = {
                "w": weight,
                "ch": char,
                "codepoint": f"U+{ord(char):04X}",
                "ratio": ratio,
                "nominal_master": nominal["master"],
                "effective_master": effective["master"],
                "master_substituted": nominal["m"] != effective["m"],
            }
            findings.append(row)
            dx = (data[weight][char]["adv"] - nominal["k"] * H._rec(char, nominal["m"])[1]) / 2
            path, _ = H.outline(char, nominal["m"], nominal["k"], dx, nominal["dy"])
            svg = SVGPathPen(None)
            path.draw(svg)
            cards.append(
                f'<article><strong>{char} · {ratio:.4f}</strong><div class="meta">{row["codepoint"]} '
                f'· nominal {nominal["master"]}, effective {effective["master"]}</div><div class="pair">'
                + _svg(data[weight][char]["d"], f"Limn {weight}")
                + _svg(svg.getCommands(), f"Parent {nominal['master']} × {nominal['k']:.4f}")
                + "</div></article>"
            )
        sections.append(f'<h2>{weight} · {len(cards)} glyphs</h2><div class="cards">{"".join(cards)}</div>')
        print(f"sheet weight {weight}: {len(cards)} low glyphs", flush=True)
    report = {
        "provenance": _provenance(source),
        "elapsed_seconds": time.perf_counter() - started,
        "under_05": len(low),
        "under_08": len(low) + len(info),
        "findings": findings,
        "crosschecks": crosschecks,
        "metric": "(Limn ink(ch)/ink(가)) / (nominal parent ink(ch)/ink(가)); audit flatten/evenodd semantics",
    }
    (out / "ink-sheet.json").write_text(json.dumps(report, ensure_ascii=False, indent=2))
    (out / "ink-sheet.html").write_text(
        _page(
            "Hangul parent-ink review · #30",
            f"{len(findings)} glyph-weights below 0.8; {len(low)} below 0.5. Every drawing uses the same "
            "1000-UPM frame and baseline. Parent outlines use the nominal pairing scale and position; there is no "
            "per-glyph size normalization. The score normalizes each family against its own 가. "
            "The effective master records topology-driven substitution. This sheet is the historical outline baseline.",
            sections,
        )
    )
    print(json.dumps({"sheet": str(out / "ink-sheet.html"), "seconds": report["elapsed_seconds"]}), flush=True)


def _portfolio(source, stem: float, hints) -> list[tuple]:
    """Evaluate three bounded candidates with the fitter's unchanged float and rounded acceptance bounds.

    The portfolio excludes expensive smoothing fallbacks; the actual accepted first-fit outline is always
    supplied separately by the experiment. This is a minimum within three candidates, not a global optimum.
    """
    geometry = H.snap_axes(source)
    want = H._topo(geometry)
    keep = H.HINT_TOL, H.TINY
    accepted = []
    tries = [(None, 0.85), (None, 0.65), (hints, keep[0])]
    for index, (candidate_hints, tolerance) in enumerate(tries):
        H.HINT_TOL = tolerance
        try:
            path = H.fit_geom(geometry, H.FIT_TOL, H.QUAD_TOL, candidate_hints)
        finally:
            H.HINT_TOL, H.TINY = keep
        svg = SVGPathPen(None)
        path.draw(svg)
        fitted, simple = H.geom_of_d(svg.getCommands())
        if not simple or not fitted.is_valid or H._topo(fitted) != want or not H._within(fitted, geometry, H.FIT_MAX):
            continue
        compact = H.d_compact(path)
        for reach in (0.0, 1.0, 1.5, 2.2):
            rounded_path = H._repair_rounded(compact, reach)
            d = H.d_compact(rounded_path)
            rounded, simple = H.geom_of_d(d)
            if (
                not simple
                or not rounded.is_valid
                or H._topo(rounded) != want
                or not H._within(rounded, geometry, H.ROUND_MAX)
            ):
                continue
            measured = A.measure(d, stem)
            if not measure_failures(measured, stem):
                accepted.append((H._stored_points(d), len(d), index, d, measured))
                break
    return accepted


def _family(args: tuple) -> dict:
    """Regenerate one whole family, capture its accepted pre-fit sources, and select a bounded point policy."""
    char, pairings, historical = args
    H._PRE.update(pairings)
    original = B._fit_output
    captured = {}

    def capture(weight, glyph, source, cap):
        """Keep the source actually accepted by the normal builder, including held-ink retries."""
        result = original(weight, glyph, source, cap)
        if result is not None:
            captured[weight] = result
        return result

    started = time.perf_counter()
    B._fit_output = capture
    try:
        baseline, _, held = B._one((list(A.WEIGHTS), [char]))
    finally:
        B._fit_output = original
    baseline_seconds = time.perf_counter() - started
    started = time.perf_counter()
    rows, candidate = [], {}
    for weight in reversed(A.WEIGHTS):
        base = baseline[weight][char]
        _, _, measure, source = captured[weight]
        options = _portfolio(source[0], pairings[weight]["S"], source[1])
        options.append((H._stored_points(base["d"]), len(base["d"]), -1, base["d"], measure))
        selected = min(options, key=lambda item: item[:3])
        candidate[weight] = dict(base, d=selected[3])
        rows.append(
            {
                "ch": char,
                "w": weight,
                "baseline_points": H._stored_points(base["d"]),
                "candidate_points": selected[0],
                "candidate_index": selected[2],
                "valid_candidates": len(options) - 1,
                "baseline_measure": measure,
                "candidate_measure": selected[4],
                "historical_equal": base["d"] == historical[weight]["d"],
                "source_area": source[0].area,
            }
        )
    failures = []
    for row in rows:
        weight = row["w"]
        failures += [f"{weight}:{name}" for name in measure_failures(row["candidate_measure"], pairings[weight]["S"])]
        if (row["candidate_measure"]["ncomp"], row["candidate_measure"]["nhole"]) != H.ref_topo(char):
            failures.append(f"{weight}:parent-topology")
    ordered = sorted(rows, key=lambda row: row["w"])
    if any(b["candidate_measure"]["ink"] <= a["candidate_measure"]["ink"] for a, b in zip(ordered, ordered[1:])):
        failures.append("ink-order")
    if len({glyph["adv"] for glyph in candidate.values()}) != 1:
        failures.append("advance")
    if failures:
        candidate = {w: baseline[w][char] for w in A.WEIGHTS}
    result = {
        "ch": char,
        "baseline_seconds": baseline_seconds,
        "search_seconds": time.perf_counter() - started,
        "rejected_family": failures,
        "held": held,
        "rows": rows,
        "baseline": {w: baseline[w][char] for w in A.WEIGHTS},
        "candidate": candidate,
    }
    print(
        f"benchmark {char}: {sum(r['baseline_points'] for r in rows)} -> "
        f"{sum(H._stored_points(g['d']) for g in candidate.values())} points; "
        f"{baseline_seconds:.1f}s baseline + {result['search_seconds']:.1f}s search; rejected={failures}",
        flush=True,
    )
    return result


def _subset(glyphs: dict, weight: int, prefix: Path) -> dict:
    """Serialize a fixed, unhinted sample using production outline conversion, returning real file sizes."""
    import build_ttf as T

    names = {char: f"uni{ord(char):04X}" for char in glyphs}
    builder = FontBuilder(1000, isTTF=True)
    builder.setupGlyphOrder([".notdef", *names.values()])
    builder.setupCharacterMap({ord(char): name for char, name in names.items()})
    outlines = {".notdef": TTGlyphPen(None).glyph()}
    outlines.update({names[char]: T.outline(glyph["d"], implied=True) for char, glyph in glyphs.items()})
    builder.setupGlyf(outlines)
    builder.setupHorizontalMetrics(
        {
            ".notdef": (1000, 0),
            **{
                names[char]: (round(glyph["adv"]), getattr(outlines[names[char]], "xMin", 0))
                for char, glyph in glyphs.items()
            },
        }
    )
    builder.setupHorizontalHeader(ascent=970, descent=-330)
    builder.setupNameTable(
        {
            "familyName": "Limn Quality Sample",
            "styleName": str(weight),
            "uniqueFontIdentifier": f"LimnQuality{weight}",
            "fullName": f"Limn Quality {weight}",
            "psName": f"LimnQuality{weight}",
            "version": "Version 0.100",
        }
    )
    builder.setupOS2(sTypoAscender=970, sTypoDescender=-330, usWinAscent=970, usWinDescent=330, usWeightClass=weight)
    builder.setupPost()
    builder.setupMaxp()
    builder.font["head"].created = builder.font["head"].modified = 3800000000
    builder.font.recalcTimestamp = False
    builder.font.save(str(prefix) + ".ttf")
    stored = sum(len(g.getCoordinates(builder.font["glyf"])[0]) for g in outlines.values() if g.numberOfContours)
    glyph_points = {char: len(outlines[name].getCoordinates(builder.font["glyf"])[0]) for char, name in names.items()}
    builder.font.flavor = "woff2"
    builder.font.save(str(prefix) + ".woff2")
    return {
        "ttf": Path(str(prefix) + ".ttf").stat().st_size,
        "woff2": Path(str(prefix) + ".woff2").stat().st_size,
        "stored_points": stored,
        "glyph_points": glyph_points,
    }


def comparison_page(families: list[dict], sizes: list[dict]) -> str:
    """Render equal-scale glyph pairs and actual font sizes, distinguishing SVG and TrueType point counts."""
    sections, table = [], []
    for size in sizes:
        weight = size["w"]
        before_size, after_size = size["baseline"], size["candidate"]
        table.append(
            f"<tr><td>{weight}</td><td>{before_size['stored_points']} → {after_size['stored_points']}</td>"
            f"<td>{before_size['ttf']} → {after_size['ttf']}</td>"
            f"<td>{before_size['woff2']} → {after_size['woff2']}</td></tr>"
        )
        cards = []
        for family in families:
            char = family["ch"]
            before, after = family["baseline"][weight], family["candidate"][weight]
            cards.append(
                f"<article><strong>{char} · SVG {_audit_points(before['d'])} → {_audit_points(after['d'])}</strong>"
                f'<div class="meta">TTF points {before_size["glyph_points"][char]} → '
                f'{after_size["glyph_points"][char]}</div><div class="pair">'
                + _svg(before["d"], "First valid")
                + _svg(after["d"], "Three-candidate minimum")
                + "</div></article>"
            )
        sections.append(f'<h2>{weight}</h2><div class="cards">{"".join(cards)}</div>')
    totals = {
        policy: {metric: sum(size[policy][metric] for size in sizes) for metric in ("stored_points", "ttf", "woff2")}
        for policy in ("baseline", "candidate")
    }
    before, after = totals["baseline"], totals["candidate"]
    table.append(
        f"<tr><th>Total</th><td>{before['stored_points']} → {after['stored_points']}</td>"
        f"<td>{before['ttf']} → {after['ttf']}</td><td>{before['woff2']} → {after['woff2']}</td></tr>"
    )
    sections.insert(
        0,
        "<table><tr><th>Weight</th><th>TTF points</th><th>TTF bytes</th><th>WOFF2 bytes</th></tr>"
        + "".join(table)
        + "</table>",
    )
    return _page(
        "Hangul point portfolio · before / after · #30",
        f"{len(families)} syllables × 9 weights. Identical pre-fit geometry; shared 1000-UPM frame and baseline. "
        "SVG counts follow the audit; TTF counts are measured after production outline conversion. "
        "All file sizes are unhinted sample fonts (+ .notdef), not full release/core fonts. "
        "The bounded policy minimizes (SVG audit points, SVG bytes) over the baseline and three ordinary candidates. "
        "Pairings come from four-decimal historical JS; the regenerated baseline is not byte-identical to production. "
        "No production default changes.",
        sections,
    )


def _audit_points(d: str) -> int:
    """Count stored-style points in the SVG outline before production overlap removal and serialization."""
    return H._stored_points(d)


def parent_ink_check(meta: dict, families: list[dict]) -> dict:
    """Recheck the 0.5 parent-ink gate on actual final outlines, including any rejected-family fallback.

    The sample must include 가, the normalization reference. Trial measures in a rejected family's rows are
    deliberately ignored. Both policies use the full audit metric and the nominal master, as production does.
    """
    chars = [family["ch"] for family in families]
    if "가" not in chars:
        raise ValueError("The benchmark requires 가 to check normalized parent ink")
    ratios = {name: A.parent_ink(i) for i, name in enumerate(H.MASTERS)}
    result = {}
    for policy in ("baseline", "candidate"):
        measured = {
            weight: {
                family["ch"]: A.measure(family[policy][weight]["d"], meta[weight]["pair"]["S"]) for family in families
            }
            for weight in A.WEIGHTS
        }
        low, info = A.parent_ink_findings(A.WEIGHTS, meta, measured, chars, ratios.__getitem__)
        failures = []
        for family in families:
            char = family["ch"]
            for weight in A.WEIGHTS:
                metric = measured[weight][char]
                failures += [f"{char}{weight}:{name}" for name in measure_failures(metric, meta[weight]["pair"]["S"])]
                if (metric["ncomp"], metric["nhole"]) != H.ref_topo(char):
                    failures.append(f"{char}{weight}:parent-topology")
            ink = [measured[w][char]["ink"] for w in A.WEIGHTS]
            if any(b <= a for a, b in zip(ink, ink[1:])):
                failures.append(f"{char}:ink-order")
            if len({family[policy][w]["adv"] for w in A.WEIGHTS}) != 1:
                failures.append(f"{char}:advance")
        result[policy] = {"under_05": low, "under_08": info, "failures": failures, "final_measures": measured}
    return result


def benchmark(source: Path, out: Path, chars: str, procs: int) -> None:
    """Save real sample font sizes, wall clocks, full audit measures and visual before/after pairs."""
    meta, historical = _inputs(source)
    pairings = {w: meta[w]["pair"] for w in A.WEIGHTS}
    started = time.perf_counter()
    families = []
    with multiprocessing.Pool(procs) as pool:
        for family in pool.imap_unordered(
            _family, [(char, pairings, {w: historical[w][char] for w in A.WEIGHTS}) for char in chars]
        ):
            families.append(family)
            (out / f"family-{ord(family['ch']):04x}.json").write_text(json.dumps(family, ensure_ascii=False, indent=2))
    families.sort(key=lambda item: chars.index(item["ch"]))
    elapsed = time.perf_counter() - started
    parent_gate = parent_ink_check(meta, families)
    if any(parent_gate[policy]["under_05"] or parent_gate[policy]["failures"] for policy in ("baseline", "candidate")):
        raise RuntimeError("The final sample fails the existing serialized Hangul audit gates")
    sizes = []
    for weight in A.WEIGHTS:
        size = {"w": weight}
        for policy in ("baseline", "candidate"):
            glyphs = {family["ch"]: family[policy][weight] for family in families}
            size[policy] = _subset(glyphs, weight, out / f"sample-{policy}-{weight}")
        sizes.append(size)
    report = {
        "provenance": _provenance(source),
        "chars": chars,
        "weights": list(A.WEIGHTS),
        "procs": procs,
        "family_wall_seconds": elapsed,
        "families": families,
        "parent_ink_gate": parent_gate,
        "historical_reference": {
            "stored_points": sum(H._stored_points(historical[w][char]["d"]) for w in A.WEIGHTS for char in chars),
            "matching_outlines": sum(row["historical_equal"] for family in families for row in family["rows"]),
            "total_outlines": len(chars) * len(A.WEIGHTS),
        },
        "sizes": sizes,
        "policy": "Min(points, SVG bytes) of baseline + three ordinary fitting candidates; reject a whole "
        "family if any serialized audit gate, parent topology, weight order or advance fails.",
        "font_scope": f"Unhinted {len(chars)}-character sample + .notdef, production outline conversion; not full font/core sizes.",
    }
    (out / "benchmark.json").write_text(json.dumps(report, ensure_ascii=False, indent=2))
    (out / "point-comparison.html").write_text(comparison_page(families, sizes))
    print(json.dumps({"benchmark": str(out / "benchmark.json"), "seconds": elapsed}), flush=True)


def main() -> None:
    """Parse the review command and write only into its explicitly selected artifact directory."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("mode", choices=("sheet", "benchmark"))
    parser.add_argument("--source", type=Path, default=A.SITE)
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--chars", default=SAMPLE)
    parser.add_argument("--procs", type=int, default=3)
    args = parser.parse_args()
    if args.procs < 1:
        parser.error("--procs must be positive")
    if not args.chars or len(set(args.chars)) != len(args.chars) or any(not H.is_syllable(c) for c in args.chars):
        parser.error("--chars must contain distinct modern Hangul syllables")
    if args.mode == "benchmark" and "가" not in args.chars:
        parser.error("--chars must include 가 for the normalized parent-ink gate")
    args.out.mkdir(parents=True, exist_ok=True)
    if args.mode == "sheet":
        sheet(args.source.resolve(), args.out, args.procs)
    else:
        benchmark(args.source.resolve(), args.out, args.chars, args.procs)


if __name__ == "__main__":
    main()
