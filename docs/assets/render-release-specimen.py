"""Outline the README specimen from an extracted release package, without fallback.

Run with uv --with fonttools --with uharfbuzz; pass the release directory and an
output SVG path. No font or brand artwork is generated or modified. HarfBuzz
shapes every label from the selected final TTF; FontTools preserves its outlines.
A sibling .provenance.json records all source hashes and specimen runs.

The package's own `fonts.json` is the authority for which release this is: the
version, the build revision stamped into nameID 5, the codepoint inventory and
each face's glyph count all come from it, and every TTF must agree with it. So a
new release renders its own specimen without editing this file, and a TTF that
does not belong to the manifest beside it still fails loudly.
"""

import argparse
import hashlib
import json
from html import escape
from pathlib import Path

import uharfbuzz as hb
from fontTools.pens.svgPathPen import SVGPathPen
from fontTools.ttLib import TTFont


def sha256(path: Path) -> str:
    """Return a source file's SHA-256 for the specimen's reproducible provenance."""
    return hashlib.sha256(path.read_bytes()).hexdigest()


def outline_run(directory: Path, run: dict, item: dict, manifest: dict) -> str:
    """Shape a supported run from its final TTF, failing on missing or wrong fonts."""
    path = directory / item["ttf"]
    version, rev = manifest["version"], manifest["rev"]
    with TTFont(path) as font:
        if (font["head"].unitsPerEm != 1000 or len(font.getBestCmap()) != len(manifest["codepoints"])
                or len(font.getGlyphOrder()) != item["glyphs"]):
            raise ValueError(f"Not the {version} inventory: {path}")
        if font["name"].getDebugName(5) != f"Version {version}; {rev}":
            raise ValueError(f"Wrong font version: {path}")
        if not set(map(ord, run["text"])) <= set(font.getBestCmap()):
            raise ValueError(f"Unsupported specimen characters: {run['text']}")
        hbfont = hb.Font(hb.Face(path.read_bytes()))
        hbfont.scale = (1000, 1000)
        buffer = hb.Buffer()
        buffer.add_str(run["text"])
        buffer.guess_segment_properties()
        hb.shape(hbfont, buffer)
        glyphs = font.getGlyphSet()
        order = font.getGlyphOrder()
        paths, x, y = [], 0, 0
        for info, pos in zip(buffer.glyph_infos, buffer.glyph_positions):
            if info.codepoint == 0:
                raise ValueError("HarfBuzz returned .notdef")
            pen = SVGPathPen(glyphs)
            glyphs[order[info.codepoint]].draw(pen)
            paths.append(
                f'<path transform="translate({x + pos.x_offset} {y + pos.y_offset})" d="{pen.getCommands()}"/>'
            )
            x += pos.x_advance
            y += pos.y_advance
        if run["x"] + x * run["size"] / 1000 > 1216:
            raise ValueError(f"Specimen run exceeds right margin: {run['text']}")
        scale = run["size"] / 1000
        return (
            f'<g aria-label="{escape(run["text"], quote=True)}" transform="translate({run["x"]} {run["y"]}) scale({scale} {-scale})">'
            + "".join(paths)
            + "</g>"
        )


def main() -> None:
    """Write an SVG of release outlines and its exact font/run provenance."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("release", type=Path)
    parser.add_argument("output", type=Path)
    args = parser.parse_args()
    manifest = json.loads((args.release / "fonts.json").read_text())
    if manifest["profile"] != "latin-symbols" or not manifest.get("releaseSupported"):
        raise ValueError("A release-supported latin-symbols package is required")
    version = manifest["version"]
    files = {item["w"]: item for item in manifest["files"]}
    runs = [
        dict(text=f"{version} / English & symbols", w=400, size=32, x=72, y=92),
        dict(text="Pin it. Fix it. Done.", w=700, size=88, x=72, y=210),
        dict(text="ABCDEFGHIJKLMNOPQRSTUVWXYZ", w=400, size=42, x=72, y=294),
        dict(text="abcdefghijklmnopqrstuvwxyz 0123456789", w=400, size=42, x=72, y=352),
        dict(text="& @ # % $ € £ ¥ ₩ ± × ÷ ≠ ≤ ≥ ∞ → ✓", w=500, size=42, x=72, y=421),
    ]
    for i, w in enumerate(range(100, 1000, 100)):
        runs.append(dict(text=f"{w} {files[w]['name']}", w=w, size=32, x=72 + (i % 3) * 392, y=509 + (i // 3) * 56))
    provenance = dict(
        release=f"https://github.com/dartworklabs/limn-sans/releases/tag/v{version}",
        releaseRev=manifest["rev"],
        manifestSHA256=sha256(args.release / "fonts.json"),
        ttfSHA256={item["ttf"]: sha256(args.release / item["ttf"]) for item in files.values()},
        renderer="HarfBuzz shaping + FontTools SVGPathPen; no installed fonts or fallback",
        canvas=[1288, 694],
        runs=runs,
    )
    body = "".join(outline_run(args.release, run, files[run["w"]], manifest) for run in runs)
    svg = '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 1288 694" role="img" aria-labelledby="title desc">\n'
    svg += f'<title id="title">Limn Sans {version} — English and symbols</title>\n'
    svg += '<desc id="desc">Actual final release outlines: English letters, figures, symbols and nine static weights, Thin 100 to Black 900.</desc>\n'
    svg += "<metadata>" + escape(json.dumps(provenance, sort_keys=True)) + "</metadata>\n"
    svg += '<path fill="#fbfaf7" d="M0 0H1288V694H0Z"/>\n<g fill="#15161a">' + body + "</g>\n</svg>\n"
    args.output.write_text(svg)
    provenance["svgSHA256"] = sha256(args.output)
    args.output.with_suffix(".provenance.json").write_text(json.dumps(provenance, indent=2) + "\n")


if __name__ == "__main__":
    main()
