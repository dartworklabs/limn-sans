"""Limn Sans as font files: TTF and WOFF2 at weights 100-900 -> site/fonts/.

  uv run --no-project --with fonttools --with brotli --with skia-pathops python3 tools/build_ttf.py

The source is the engine's own data, not Quicksand: limn-font-play.js (make play) and limn-hangul-<w>.js
(make hangul). A line set in the browser with these files must match the same line set by the engine,
LIMN_playset(str, {w}) in limn-brand.js with its defaults, so every rule below is the engine's:

  pins      the engine draws dots as circles on top of the outlines (pinsOf: the i rule, base, top, mid).
            A font is monochrome, so each pin is baked into the outline as an ink circle and merged
            with it (skia-pathops). Glyphs that are only pins (. : · ...) take the engine's advance too.
  kerning   kernOf(K, KC, a, b): the pair, else the base pair of the two kerning classes (é kerns as e).
            GPOS kern = class pairs (PairPos format 2, one class per base) + the pairs that differ from
            their class (format 1, looked up first).
  figures   tabular by default (the engine's tnum). pnum swaps in the proportional figures (pnum: the
            same drawing moved inside a narrower advance; pglyph: its own drawing, the flagged 1) and
            their kerning (pkern); tnum swaps them back.
  spaces    the engine's spaceOf: no-break, thin, narrow no-break, en, em and U+3000 (가's advance) are empty
            glyphs of those widths; soft hyphen and ZWSP are empty and zero-width (HarfBuzz hides both and
            kerns across them, as the engine does).
  Hangul    every character the Latin data lacks comes from limn-hangul-<w>.js (+ limn-hangulext-<w>.js: all
            11,172 syllables) of the same weight; its implied on-curve points are left implied.
            The Latin|Hangul boundary white (bnd) is 0 at every weight; if it ever is not, it becomes
            a kern pair lookup (browsers split script runs, so it may not reach there).
  림        in text it is the plain Hangul syllable (cmap). The pinned 림 of the Latin data is the logo,
            which the README keeps outside the OFL, so the files leave it out; LIMN_TTF_LOGO=1 adds it
            as ss02 (ss01 is the engine's double-storey a g; zero is its dotted 0) for in-house builds.

Metrics: typo = hhea = win, ascender 970 and descender -330 (the Latin 740 / -200 plus 360 of line
gap, 230 above and 130 below), no line gap, USE_TYPO_METRICS: line height 1.3 em on every platform, and
every glyph of every weight inside it (tallest Å at 900, 968; deepest Ģ at 900, -327; Hangul 765 / -60).
If a later build draws past it, the box grows to cover (the build says so).

Writes site/fonts/LimnSans-<Name>.ttf and .woff2, and site/fonts/fonts.js (file list, sizes and metrics
for fonts.html). Each weight also gets -core.woff2 (all non-syllables + the 2,350 KS X 1001 syllables)
and -ext.woff2 (the other 8,822 syllables). fonts.css declares their exact complementary unicode-range
coverage, with URLs relative to that stylesheet. All layout features and name/licence records survive
in the core face; layout closure retains applicable alternates in either subset.

The approved release profile uses LIMN_TTF_PROFILE=latin-symbols (1.002 licence-metadata correction), explicit PLAY_IN,
SYMBOLS_IN and OUT; no Hangul/extension dataset is needed. It emits one hinted WOFF2 face per weight,
exact coverage/inputs in fonts.json, portable CSS, installation README, licences and checksums.
The default full profile stays 0.100 and requires all bilingual data. See docs/release-profile.md.

LIMN_TTF_OUT selects a separate font output directory. LIMN_TTF_HANGUL_IN selects the Hangul JS input
directory (default LIMN_KO_OUT, then site/), while LIMN_TTF_PLAY_IN selects a Latin JS input file
(default site/limn-font-play.js). For the HALF trial, for example:
  LIMN_TTF_HANGUL_IN=/tmp/limn-half-data LIMN_TTF_OUT=/tmp/limn-half-fonts make fonts
This reads HALF Hangul and the existing Latin data without copying either over site/ files.

Hinting: every TTF is autohinted in place (ttfautohint-py) before the .woff2 is cut from it, so both
carry the same instructions. LIMN_TTF_HINT=0 skips this and writes the un-hinted (delta-only) glyf, for
a size comparison or if ttfautohint-py is not installed. See hint_ttf() for the option choices.
"""
import sys as _sys, pathlib as _pl; _sys.path.insert(0, str(_pl.Path(__file__).parent))
import json
import hashlib
import shutil
import math
import os
import subprocess
import sys
import unicodedata
from pathlib import Path

import pathops
from fontTools import agl
from fontTools import subset
from fontTools.feaLib.builder import addOpenTypeFeaturesFromString
from fontTools.fontBuilder import FontBuilder
from fontTools.misc.roundTools import otRound
from fontTools.misc.timeTools import timestampSinceEpoch
from fontTools.pens.cu2quPen import Cu2QuPen
from fontTools.pens.transformPen import TransformPen
from fontTools.pens.ttGlyphPen import TTGlyphPen
from fontTools.svgLib.path import parse_path
from fontTools.ttLib import TTFont, newTable

from mark_attachment import attachment_features

PROFILE = os.environ.get("LIMN_TTF_PROFILE", "full")
if PROFILE not in ("full", "latin-symbols"):
    raise ValueError("LIMN_TTF_PROFILE must be full or latin-symbols")
if PROFILE == "latin-symbols" and os.environ.get("LIMN_TTF_LOGO") == "1":
    raise ValueError("latin-symbols refuses LIMN_TTF_LOGO=1")
LOGO_RIM = os.environ.get("LIMN_TTF_LOGO") == "1"   # the pinned logo 림 is not OFL (README): only on request
HINT = os.environ.get("LIMN_TTF_HINT", "1") != "0"  # TrueType autohint (ttfautohint-py); LIMN_TTF_HINT=0 skips it

HERE = Path(__file__).resolve().parent
SITE = HERE.parent
OUT = Path(os.environ.get("LIMN_TTF_OUT", SITE / "fonts")).resolve()
PLAY_IN = Path(os.environ.get("LIMN_TTF_PLAY_IN", SITE / "limn-font-play.js")).resolve()
HANGUL_IN = Path(os.environ.get("LIMN_TTF_HANGUL_IN", os.environ.get("LIMN_KO_OUT", SITE))).resolve()
SPACE_PROVENANCE_IN = (Path(os.environ["LIMN_TTF_SPACE_PROVENANCE_IN"]).resolve()
                       if os.environ.get("LIMN_TTF_SPACE_PROVENANCE_IN") else None)
SYMBOLS_IN = Path(os.environ["LIMN_TTF_SYMBOLS_IN"]).resolve() if os.environ.get("LIMN_TTF_SYMBOLS_IN") else None
WEIGHTS = {100: "Thin", 200: "ExtraLight", 300: "Light", 400: "Regular", 500: "Medium",
           600: "SemiBold", 700: "Bold", 800: "ExtraBold", 900: "Black"}
FAMILY = "Limn Sans"
RELEASE_VERSION = 1.002  # licence metadata + U+25CC; published 1.000 and 1.001 are immutable
VERSION = RELEASE_VERSION if PROFILE == "latin-symbols" else 0.1
MAX_ERR = 0.5           # cubic -> quadratic tolerance, font units
LINE_ASC, LINE_DESC = 970, -330
# One underline for the whole family, the way the line box above is one box. post.underlineThickness
# may not vary across a family (fontbakery opentype/family/underline_thickness), and through 1.001 it
# did: 0.8 of each weight's own stem, 32 at Thin to 124 at Black. The family value is that same rule
# read off the Regular, so body text - where an underline is actually read - keeps exactly the line it
# had and the other eight faces take the Regular's. make_font checks the derivation still holds.
UNDERLINE_POSITION, UNDERLINE_THICKNESS = -100, 61
RIM = "림"              # U+B9BC
SYLLABLES = frozenset(range(0xAC00, 0xD7A4))
# EUC-KR's 25 Hangul rows are KS X 1001, not CP949's larger syllable repertoire.
KSX1001 = frozenset(ord(bytes((hi, lo)).decode("euc-kr"))
                   for hi in range(0xB0, 0xC9) for lo in range(0xA1, 0xFF))

# Version 1.000 freezes the current repertoire, including informational Greek/extended Latin.
# Adding/removing a character requires an explicit profile revision, never a silent subset.
# Revision, U+25CC DOTTED CIRCLE: the family carries combining marks (U+0300-030C and the rest, with ccmp/mark/
# mkmk), and a shaper draws a mark typed without a base over this placeholder. Without the glyph it fell back to
# .notdef (fontbakery's dotted_circle check, nine WARNs). The drawing is tools/sym_math.py's ◌; this range is the
# only coverage edit it needs, so the Latin set is 856 codepoints and the package 919 / 933.
_RELEASE_LATIN_RANGES = (
    "0021-007E 00A1-00AC 00AE-017F 01A0-01A1 01AF-01B0 01F0 0218-021B 0237 02B2 02C6-02C7 02D8-02DD 02E3 "
    "0300-030C 0312 031B 0323 0326-0328 0335 037E-037F 0384-038A 038C 038E-03A1 03A3-03CE 03D1 03D5-03D6 "
    "03F0-03F3 03F5 03F9 1D40 1D62 1E80-1E85 1E9E 1EA0-1EF9 2010-2027 2030-203A 203C-2049 204E 2050-2051 2053 "
    "2055 2057 2070-2071 2074-208E 2090-2093 2095-209C 20A1 20A3-20AE 20B1-20B5 20B8-20BA 20BC-20BF 2100-2103 "
    "2105 2109 210F 2113 2115-2117 211A 211D 2120 2122 2124 2126 212A-212B 212E 2150-217F 2189 2190-2199 21A6 "
    "21A9-21AA 21B0-21B1 21B3-21B5 21BA-21BB 21D0-21D5 21DE-21DF 21E4-21E5 21E7 21EA 2200 2202-2209 220B-220C "
    "220F 2211-2213 2215-221A 221D-221E 2220 2223 2225 2227-222C 222E 2234-2236 223C 2243 2245 2248 2250 2252 "
    "2254 225D 2260-2262 2264-2265 226A-226B 2282-2283 2286-2287 2295-2299 22A2 22A4-22A5 22C5 22EE-22EF 22F1 "
    "2303 2305 2308-230B 2318 2325-2327 232B 2387 238B 23CE-23CF 25CC 25E6 26A0 2713-2714 2717-2718 27E8-27E9 "
    "27F5-27F7 2C7C FFE6 "
)
RELEASE_LATIN = frozenset(cp for span in _RELEASE_LATIN_RANGES.split()
                          for cp in range(int(span.split("-")[0], 16), int(span.split("-")[-1], 16) + 1))
RELEASE_SYMBOLS = "「」『』〈〉《》【】〔〕、。※〜・～○●□■△▲☆★℃㎡㎏㎝㎞①②③④⑤⑥⑦⑧⑨⑩▶▷▼▽◀◁◆◇♠♡♥♣♪☎"
RELEASE_SPACES = frozenset((0x20, 0xA0, 0xAD, 0x2002, 0x2003, 0x2009, 0x200B, 0x202F, 0x3000))
RELEASE_COVERAGE = RELEASE_LATIN | frozenset(map(ord, RELEASE_SYMBOLS)) | RELEASE_SPACES


def is_hangul(cp: int) -> bool:
    """Exclude all Hangul blocks, tone marks and enclosed Hangul forms, including unassigned block slots."""
    return any(a <= cp <= b for a, b in ((0x1100, 0x11FF), (0x302E, 0x302F), (0x3130, 0x318F),
                                        (0x3200, 0x321E), (0x3260, 0x327E), (0xA960, 0xA97F),
                                        (0xAC00, 0xD7FF), (0xFFA0, 0xFFDC)))


def release_data(W: dict, H: dict) -> tuple[dict, dict]:
    """Admit complete frozen non-Hangul inputs; require explicit U+3000 advance authority.

    Returns copies with all Hangul records removed before glyph/GSUB construction. The supplemental
    producer owns the ideographic-space width; the exporter never reconstructs it from a fake syllable.
    """
    W = {**W, "glyphs": {ch: g for ch, g in W["glyphs"].items() if not is_hangul(ord(ch))}}
    H = {**H, "glyphs": {ch: g for ch, g in H["glyphs"].items() if not is_hangul(ord(ch))}, "bnd": 0}
    for label, actual, expected in (("Latin", set(map(ord, W["glyphs"])), RELEASE_LATIN),
                                    ("supplemental", set(map(ord, H["glyphs"])), set(map(ord, RELEASE_SYMBOLS)))):
        if actual != expected:
            raise ValueError(f"{label} coverage differs: missing {unicode_range(expected - actual)}; "
                             f"extra {unicode_range(actual - expected)}")
    if set(H.get("spaces", {})) != {"\u3000"}:
        raise ValueError("supplemental spaces must contain only the U+3000 authority")
    advance = H["spaces"]["\u3000"]
    if isinstance(advance, bool) or not isinstance(advance, (float, int)) or advance != 819.0:
        raise ValueError("supplemental input requires explicit U+3000 spaces authority (original advance 819)")
    return W, H


def space_provenance(path: Path) -> dict:
    """Parse the nine original U+3000 advance attestations, rejecting absent or inconsistent authority."""
    data = json.loads(path.read_text(encoding="utf-8"))
    if set(data) != {str(w) for w in WEIGHTS}:
        raise ValueError("U+3000 provenance requires exactly nine weights")
    for record in data.values():
        if record.get("char") != "\u3000" or record.get("advance") != 819.0 or record.get("source_glyph") != "가":
            raise ValueError("U+3000 provenance differs from the original 가 advance")
    return data



def load_profile_data(w: int, play: dict) -> tuple[dict, dict]:
    """Load the selected profile's weight; the release needs no full Hangul or extension dataset."""
    if PROFILE == "full":
        return play[str(w)], load_hangul(w)
    if SYMBOLS_IN is None:
        raise ValueError("latin-symbols requires LIMN_TTF_SYMBOLS_IN")
    H = load_js(SYMBOLS_IN / f"limn-hangul-{w}.js", f"window.LIMN_HANGUL[{w}]=")
    if "spaces" not in H:
        if SPACE_PROVENANCE_IN is None:
            raise ValueError("release requires explicit U+3000 provenance")
        authority = space_provenance(SPACE_PROVENANCE_IN)
        H = {**H, "spaces": {"\u3000": authority[str(w)]["advance"]}}
    W, H = release_data(play[str(w)], H)
    if set(map(ord, space_table(W, H))) | {0x20} != RELEASE_SPACES:
        raise ValueError(f"{w}: space coverage differs from the release profile")
    return W, H


# nameID 0 stays under the 500-character limit external distribution channels enforce, and declares no
# Reserved Font Name of its own; OFL.txt carries the full text and NAVER's complete reserved-name list.
COPYRIGHT = (
    'Copyright 2026 The Limn Sans Project Authors (https://github.com/dartworklabs/limn-sans). '
    'Copyright 2011 The Quicksand Project Authors (https://github.com/andrew-paglinawan/QuicksandFamily), '
    'with Reserved Font Name "Quicksand". '
    'Copyright (c) 2010, NAVER Corporation (https://www.navercorp.com/), with Reserved Font Names '
    '"Nanum" and others as listed in OFL.txt.'
)
if len(COPYRIGHT) > 500:   # a raise, not an assert: python -O would drop the guard and ship the long string
    raise ValueError(f"nameID 0 is {len(COPYRIGHT)} characters; external distribution channels reject over 500")
LICENSE = ("This Font Software is licensed under the SIL Open Font License, Version 1.1. "
           "This license is available with a FAQ at: https://openfontlicense.org")
LICENSE_URL = "https://openfontlicense.org"
DESCRIPTION = ("Limn Sans, the typeface of limn: a Modified Version of Quicksand (Latin) and of "
               "NanumSquareRound (Hangul), under the SIL Open Font License 1.1.")
if PROFILE == "latin-symbols":
    DESCRIPTION = ("Limn Sans, English and symbols; Hangul excluded. Modified Version of Quicksand "
                   "and NanumSquareRound, under the SIL Open Font License 1.1.")


# ---------------------------------------------------------------- data
def load_js(path, marker):
    """The JSON a generated data file assigns after marker (the header keeps '=' and ';' out of it)."""
    if not path.exists():
        sys.exit(f"build_ttf: {path.name} missing - run make play hangul first")
    t = path.read_text(encoding="utf-8")
    i = t.index(marker) + len(marker)
    return json.loads(t[i:t.rindex(";")])


def load_hangul(w):
    """limn-hangul-<w>.js with limn-hangulext-<w>.js merged in (the syllables outside KS X 1001, build_hangul.py)."""
    H = load_js(HANGUL_IN / f"limn-hangul-{w}.js", f"window.LIMN_HANGUL[{w}]=")
    if H.get("ext"):
        ext = (HANGUL_IN / H["ext"]).resolve()
        if ext.parent != HANGUL_IN:
            sys.exit("build_ttf: Hangul extension must be in the Hangul input directory")
        X = load_js(ext, f"window.LIMN_HANGUL_EXT[{w}]=")
        H["glyphs"].update(X["glyphs"])
    return H


def gname(ch):
    cp = ord(ch)
    return agl.UV2AGL.get(cp) or (f"uni{cp:04X}" if cp <= 0xFFFF else f"u{cp:05X}")


def space_table(W, H):
    """limn-brand.js spaceOf: the data's "spaces" (no-break, thin, narrow no-break, en, em: advances; soft hyphen and
    ZWSP: 0), explicit supplemental spaces, and U+3000 (가 in full development).
    A symbol-only release input supplies U+3000 directly from its original advance provenance."""
    out = {**W.get("spaces", {}), **H.get("spaces", {})}
    if "가" in H["glyphs"]:
        out["\u3000"] = H["glyphs"]["가"]["adv"]
    return out


def git_rev():
    try:
        rev = subprocess.run(["git", "rev-parse", "--short", "HEAD"], cwd=HERE, capture_output=True, text=True, check=True).stdout.strip()
        dirty = subprocess.run(["git", "status", "--porcelain", "--", "site/tools"], cwd=HERE.parent.parent, capture_output=True, text=True).stdout.strip()
        return rev + ("-dirty" if dirty else "")
    except (OSError, subprocess.CalledProcessError):
        return None


def hint_ttf(path):
    """Autohint the saved TTF in place (ttfautohint-py, bundles libttfautohint): rounds stems and snaps
    flat segments to the pixel grid at small sizes, replacing FreeType's un-hinted (delta-only) rendering.

    default_script="latn" covers the Latin letters and the punctuation/symbols ttfautohint recognises.
    Hangul and the KS X 1001 symbols (ㆍ・～ ○●□■△▲☆★ ▶▷▼▽◀◁◆◇♠♡♥♣♪☎ ℃ ㎡㎏㎝㎞ ①-⑩) have no script module here
    (checked: no hang/hani/kore in `ttfautohint --help`'s script table), so they fall through to the
    fallback path. Tried both documented choices and compared rendered 11-16px Thin/Regular/Bold samples
    (not assumption): fallback_script="none" (autohint them too, from their own shape) rounds the three
    close horizontal strokes of dense syllables like 을 onto the same or adjacent pixel rows and crushes
    the counters black - reproduces at every weight tried, worse as the stems get thinner. fallback_scaling
    (scale, don't hint) keeps every Hangul stroke separated and reads like the un-hinted control at every
    size tested, while Latin stems stay fully hinted (fallback_scaling only touches glyphs already off the
    default_script path, so latn hinting is unaffected) - this is what's built.

    windows_compatibility adds usWinAscent/usWinDescent blue zones (cheap insurance; this face's line box
    already clears every glyph by a wide margin). hint_composites is a no-op here - every glyph build_ttf
    emits is a simple outline (pathops union), never a composite. no_info keeps this build's own version
    string (git rev, SOURCE_DATE_EPOCH) as the only one in `name` - ttfautohint's own info string is
    dropped rather than appended, so the name table stays exactly what make_font wrote."""
    import ttfautohint
    kwargs = dict(
        in_file=path, out_file=path,
        default_script="latn", fallback_script="none", fallback_scaling=True,
        hinting_range_min=8, hinting_range_max=50, hinting_limit=200,
        increase_x_height=14, windows_compatibility=True, no_info=True,
    )
    epoch = os.environ.get("SOURCE_DATE_EPOCH")
    if epoch:
        kwargs["epoch"] = int(epoch)
    ttfautohint.ttfautohint(**kwargs)


# ---------------------------------------------------------------- outlines
K = 0.5522847498   # circle from four cubic quarters


def circle(pen, cx, cy, r):
    k = K * r
    pen.moveTo((cx + r, cy))
    pen.curveTo((cx + r, cy + k), (cx + k, cy + r), (cx, cy + r))
    pen.curveTo((cx - k, cy + r), (cx - r, cy + k), (cx - r, cy))
    pen.curveTo((cx - r, cy - k), (cx - k, cy - r), (cx, cy - r))
    pen.curveTo((cx + k, cy - r), (cx + r, cy - k), (cx + r, cy))
    pen.closePath()


def _clean_path(p):
    """The simplified outline without its dirt: contours under 1 unit² go, and so do segments that end within
    0.5 unit of where they start (zero-length and near-duplicate points) and points where two straight segments
    run back along each other (a zero-width spike)."""
    out = pathops.Path(); pen = out.getPen()
    for c in p.contours:
        if abs(c.area) < 1.0:
            continue
        start = cur = None; segs = []
        if next(iter(c.segments))[0] != "moveTo":
            c.draw(pen); continue
        for verb, pts in c.segments:
            if verb == "moveTo":
                start = cur = pts[0]
            elif verb in ("lineTo", "qCurveTo", "curveTo"):
                if pts[-1] is None:                          # a contour of off-curve points only (a circle)
                    segs.append((verb, pts)); continue
                if all(math.dist(q, cur) < 0.5 for q in pts):
                    continue
                segs.append((verb, pts)); cur = pts[-1]
        if len(segs) > 1 and segs[-1][0] == "lineTo" and math.dist(segs[-1][1][-1], start) < 0.5:
            segs.pop()                                       # closePath draws that line
        i = 0
        while i < len(segs) - 1:
            if segs[i][0] == segs[i + 1][0] == "lineTo":
                a = start if i == 0 else segs[i - 1][1][-1]
                b, e = segs[i][1][-1], segs[i + 1][1][-1]
                u, v = (b[0] - a[0], b[1] - a[1]), (e[0] - b[0], e[1] - b[1])
                lu, lv = math.hypot(*u), math.hypot(*v)
                if lu and lv and (u[0] * v[0] + u[1] * v[1]) / (lu * lv) < -0.996:
                    del segs[i]; i = max(0, i - 1); continue
            i += 1
        if not segs or (len(segs) < 2 and segs[0][1][-1] is not None):
            continue
        pen.moveTo(start)
        for verb, pts in segs:
            getattr(pen, verb)(*pts)
        pen.closePath()
    return out


def _clean_glyph(g):
    """The same on the TrueType points, after rounding to the unit grid: a point on top of its neighbour goes (an
    off-curve point before an on-curve one), and so does an on-curve point where the contour steps back by at most
    2 units (a jaggy corner)."""
    if not g.numberOfContours:
        return g
    from array import array
    from fontTools.ttLib.tables._g_l_y_f import GlyphCoordinates
    coords, flags, ends = list(g.coordinates), list(g.flags), list(g.endPtsOfContours)
    out_c, out_f, out_e, s = [], [], [], 0
    for e in ends:
        pts = [(coords[k], flags[k] & 1) for k in range(s, e + 1)]
        s = e + 1
        changed = True
        while changed and len(pts) > 2:
            changed = False
            n = len(pts)
            for i in range(n):
                (p0, o0), (p1, o1) = pts[i], pts[(i + 1) % n]
                if p0 == p1:
                    del pts[i if not o0 else (i + 1) % n]; changed = True; break
                (pa, oa), (pc, oc) = pts[i - 1], pts[(i + 1) % n]
                if o0:
                    u, v = (p0[0] - pa[0], p0[1] - pa[1]), (pc[0] - p0[0], pc[1] - p0[1])
                    lu, lv = math.hypot(*u), math.hypot(*v)
                    if lu and lv and ((oa and lu <= 2) or (oc and lv <= 2)) and (u[0] * v[0] + u[1] * v[1]) < -0.5 * lu * lv:
                        del pts[i]; changed = True; break
        if len(pts) < 3 or not any(o for _, o in pts):
            continue
        out_c += [q for q, _ in pts]; out_f += [o for _, o in pts]; out_e.append(len(out_c) - 1)
    g.coordinates = GlyphCoordinates(out_c)
    g.flags = array("B", out_f)
    g.endPtsOfContours = out_e
    g.numberOfContours = len(out_e)
    return g


def outline(d, pins=(), dx=0.0, implied=False):
    """Engine drawing (SVG path, y down, nonzero fill) + pins (x, y up, r) -> one TrueType glyph.

    The outline is flipped to y up, the pins merged in, overlaps removed; outer contours come out
    clockwise (TrueType), cubics (the pins) become quadratics within MAX_ERR. The result is cleaned before and
    after rounding to the unit grid (_clean_path, _clean_glyph). implied (the Hangul): an on-curve point exactly
    midway between two off-curves is left implied, as TrueType allows (the data's smooth "t" joins); the Hangul is
    already fitted on the unit grid and gated by audit_hangul.py, so it skips the cleaning."""
    p = pathops.Path()
    if d:
        parse_path(d, TransformPen(p.getPen(), (1, 0, 0, -1, dx, 0)))
    if pins:
        c = pathops.Path()
        cp = c.getPen()
        for x, y, r in pins:
            circle(cp, x + dx, y, r)
        p = pathops.op(p, c, pathops.PathOp.UNION, fix_winding=True, keep_starting_points=False, clockwise=True)
    else:
        p = pathops.simplify(p, fix_winding=True, keep_starting_points=False, clockwise=True)
    if not implied:
        p = _clean_path(p)
    tt = TTGlyphPen(None)
    p.draw(Cu2QuPen(tt, MAX_ERR, reverse_direction=False))
    return tt.glyph(dropImpliedOnCurves=True) if implied else _clean_glyph(tt.glyph())


# ---------------------------------------------------------------- one weight
class Weight:
    def __init__(self, w, W, H):
        self.w, self.W, self.H = w, W, H
        self.glyphs, self.adv, self.cmap = {}, {}, {}
        self.chars = {}          # glyph name -> the character the engine kerns it as
        self.pnum, self.tnum = {}, {}   # tabular -> proportional glyph (and back)
        self.alts = {"ss01": {}, "ss02": {}, "zero": {}}
        r, gap = W["pin"]["r"], W["pin"]["gap"]
        self.r, self.gap = r, gap

    def add(self, name, ch, d, adv, pins=(), dx=0.0, implied=False):
        assert name not in self.glyphs, name
        gl = self.glyphs[name] = outline(d, pins, dx, implied)
        gl.recalcBounds(None)      # simple glyphs only, no table needed
        self.adv[name] = otRound(adv)
        if ch is not None:
            self.chars[name] = ch

    # limn-brand.js LIMN_playset: pinsOf (y up here) and advOf, rule pins (fit), no optical size
    def pins_of(self, ch, g):
        W, r, gap = self.W, self.r, self.gap
        if ch == RIM:
            if "pinx" not in g:
                return []
            return [(g["pinx"], -g["piny"], g["pinr"])] if g.get("pinr") else [(g["pinx"], W["xh"] + gap + r, r)]
        dt = W["dots"].get(ch)
        if not dt:
            return []
        os_ = W["xo"] - W["xh"]     # pins overshoot like o
        out = []
        for k, x, y, r0 in dt["pins"]:
            nx = x + (r - r0) if dt["only"] else x
            cy = W["xh"] + gap + r if k == "i" else r - os_ if k == "base" else W["xo"] - r if k == "top" else y
            out.append((nx, cy, r))
        return out

    def adv_of(self, ch, g):
        dt = self.W["dots"].get(ch)
        return dt["adv0"] + 2 * (self.r - dt["pins"][0][3]) if dt and dt["only"] else g["adv"]

    def build(self):
        W, H = self.W, self.H
        # .notdef: the engine's tofu, an open box of cap height (limn-brand.js tofu)
        cap, s = W["cap"], W["s"]
        t, A = 0.4 * s, otRound(0.6 * cap + 80)
        a, b = 40, A - 40
        self.add(".notdef", None, f"M{a} 0H{b}V{-cap}H{a}Z M{a + t} {-t}V{-cap + t}H{b - t}V{-t}Z", A)
        self.add("space", " ", "", W["space"])
        self.cmap[0x20] = self.cmap[0xA0] = "space"   # no-break space: the same white
        # typographic spaces and zero-width marks: the engine's spaceOf (limn-brand.js), widths from the data
        for ch, adv in sorted(space_table(W, H).items()):
            if ord(ch) in self.cmap: continue
            n = gname(ch)
            self.add(n, None, "", adv)
            self.cmap[ord(ch)] = n
        # Latin (and every symbol) from the play data
        for ch, g in W["glyphs"].items():
            if ch == RIM:       # the pinned logo 림: never the syllable; in the files only on request (LOGO_RIM)
                if LOGO_RIM:
                    self.add("uniB9BC.ss02", RIM, g["d"], g["adv"], self.pins_of(ch, g))
                    self.alts["ss02"]["uniB9BC"] = "uniB9BC.ss02"
                continue
            n = gname(ch)
            self.add(n, ch, g["d"], self.adv_of(ch, g), self.pins_of(ch, g))
            self.cmap[ord(ch)] = n
        # figures: tabular in the cmap, proportional behind pnum
        for ch in "0123456789":
            n = gname(ch)
            if ch in W.get("pglyph", {}):
                pg = W["pglyph"][ch]
                self.add(n + ".pnum", ch, pg["d"], pg["adv"], self.pins_of(ch, pg))
            else:
                adv, off = W["pnum"][ch]
                self.add(n + ".pnum", ch, W["glyphs"][ch]["d"], adv, self.pins_of(ch, W["glyphs"][ch]), dx=-off)
            self.pnum[n] = n + ".pnum"
        # alternates: ss01 double-storey a g, zero the dotted 0 (engine switches ss01, zero)
        for ch, g in W.get("alt", {}).items():
            n = gname(ch)
            if ch == "0":
                self.add("zero.zero", ch, g["d"], g["adv"], self.pins_of(ch, g))
                self.alts["zero"]["zero"] = "zero.zero"
                if "0" in W.get("pglyph", {}):      # the engine keeps a dotted 0 tabular then
                    self.add("zero.zero.pnum", ch, g["d"], g["adv"], self.pins_of(ch, g))
                else:
                    adv, off = W["pnum"]["0"]
                    self.add("zero.zero.pnum", ch, g["d"], adv, self.pins_of(ch, g), dx=-off)
                self.pnum["zero.zero"] = "zero.zero.pnum"
                self.alts["zero"]["zero.pnum"] = "zero.zero.pnum"
            elif ch in "ag":
                self.add(n + ".ss01", ch, g["d"], g["adv"], self.pins_of(ch, g))
                self.alts["ss01"][n] = n + ".ss01"
            else:
                sys.exit(f"build_ttf: alternate {ch!r} has no feature - add it here")
        self.tnum = {v: k for k, v in self.pnum.items()}
        # Hangul: whatever the Latin lacks (the 림 syllable included)
        for ch, g in sorted(H["glyphs"].items()):
            if ch in W["glyphs"] and ch != RIM:
                continue
            n = gname(ch)
            self.add(n, ch, g["d"], g["adv"], implied=True)
            self.cmap[ord(ch)] = n
        return self

    # ------------------------------------------------------------ kerning (limn-brand.js kernOf, pkern)
    def kerning(self):
        W = self.W
        KN, KC = W["kern"], W["kcls"]
        L = lambda c: (KC.get(c) or [None, None])[0] or c
        R = lambda c: (KC.get(c) or [None, None])[1] or c
        allg, pnumg = {}, {}      # char -> glyphs the engine kerns as that char (always / with tnum false)
        for n, ch in self.chars.items():
            allg.setdefault(ch, []).append(n)
            if ch.isdigit() and ch.isascii():
                if n in self.tnum:     # a proportional figure
                    pnumg.setdefault(ch, []).append(n)
            else:
                pnumg.setdefault(ch, []).append(n)
        lcls, rcls = {}, {}
        for ch, ns in allg.items():
            lcls.setdefault(L(ch), []).extend(ns)
            rcls.setdefault(R(ch), []).extend(ns)
        classv, pairs = {}, {}
        for key, v in KN.items():
            a, b = key       # every key is two characters (checked: no surrogates)
            if a in lcls and b in rcls:
                classv[(a, b)] = v
        for key, v in KN.items():
            a, b = key
            if L(a) == a and R(b) == b:
                continue
            if v == KN.get(L(a) + R(b), 0):
                continue      # the class already gives it
            for ga in allg.get(a, []):
                for gb in allg.get(b, []):
                    pairs[(ga, gb)] = v
        for key, v in W.get("pkern", {}).items():   # tnum false: pkern wins over kernOf
            a, b = key
            for ga in pnumg.get(a, []):
                for gb in pnumg.get(b, []):
                    if ga in self.tnum or gb in self.tnum:
                        pairs[(ga, gb)] = v
        bnd = self.H.get("bnd") or 0
        bndpairs = None
        if bnd:
            print(f"  {self.w}: Latin|Hangul boundary white {bnd} -> kern lookup (browsers split script runs; check it shows)")
            ko = lambda c: "ᄀ" <= c <= "ᇿ" or "ㄱ" <= c <= "ㆎ" or "가" <= c <= "힣"
            letters = [n for n, ch in self.chars.items() if unicodedata.category(ch).startswith("L")]
            bndpairs = ([n for n in letters if not ko(self.chars[n])], [n for n in letters if ko(self.chars[n])], otRound(bnd))
        return lcls, rcls, classv, pairs, bndpairs

    def features(self):
        """Serialize existing substitutions/kerning and explicit source-rule mark attachment."""
        lcls, rcls, classv, pairs, bndpairs = self.kerning()
        cid = {}
        out = ["languagesystem DFLT dflt;", "languagesystem latn dflt;", "languagesystem hang dflt;", ""]

        def cls(side, key, names):
            k = (side, key)
            if k not in cid:
                cid[k] = f"@k{side}{len(cid)}"
                out.append(f"{cid[k]} = [{' '.join(names)}];")
            return cid[k]
        body = []
        for (ga, gb), v in sorted(pairs.items()):
            body.append(f"  pos {ga} {gb} {otRound(v)};")
        for (a, b), v in sorted(classv.items()):
            if otRound(v):
                body.append(f"  pos {cls('L', a, lcls[a])} {cls('R', b, rcls[b])} {otRound(v)};")
        out += ["", "lookup kern_pairs {"] + body + ["} kern_pairs;", ""]
        kern = ["feature kern {", "  lookup kern_pairs;"]
        if bndpairs:
            lat, ko, v = bndpairs
            out += ["@bndLatin = [" + " ".join(lat) + "];", "@bndHangul = [" + " ".join(ko) + "];",
                    "lookup kern_boundary {", f"  pos @bndLatin @bndHangul {v};", f"  pos @bndHangul @bndLatin {v};", "} kern_boundary;", ""]
            kern.append("  lookup kern_boundary;")
        out += kern + ["} kern;", ""]
        # GDEF: the combining marks (zero width, category Mn) are marks, every other glyph with ink a base
        marks = sorted(n for n, ch in self.chars.items() if unicodedata.category(ch) == "Mn")
        if marks:
            bases = sorted(n for n, g in self.glyphs.items() if n not in marks and g.numberOfContours and n != ".notdef")
            out += ["table GDEF {", f"  GlyphClassDef [{' '.join(bases)}], , [{' '.join(marks)}], ;", "} GDEF;", ""]

        def single(tag, m, label=None):
            if not m:
                return
            out.append(f"feature {tag} {{")
            if label:
                out.append(f'  featureNames {{ name "{label}"; }};')
            out.extend([f"  sub {a} by {b};" for a, b in m.items()] + [f"}} {tag};", ""])
        single("pnum", self.pnum)
        single("tnum", self.tnum)
        single("ss01", self.alts["ss01"], "Double-storey a and g")
        single("ss02", self.alts["ss02"], r"Pinned \B9BC (the limn logo)")
        single("zero", self.alts["zero"])
        out.append(attachment_features(self.glyphs, self.chars, self.W))
        return "\n".join(out)


# ---------------------------------------------------------------- font
def fsel(w):
    return (0x20 if w == 700 else 0x40) | 0x80     # BOLD or REGULAR, USE_TYPO_METRICS


def make_font(wt, asc, desc, version_tail):
    """Build one SFNT using the selected profile version and the family-wide line metrics."""
    w, W = wt.w, wt.W
    style = WEIGHTS[w]
    ribbi = w in (400, 700)
    fam = FAMILY if ribbi else f"{FAMILY} {style}"
    sub = style if ribbi else "Regular"
    ps = f"LimnSans-{style}"
    order = [".notdef", "space"] + [n for n in wt.glyphs if n not in (".notdef", "space")]
    fb = FontBuilder(1000, isTTF=True)
    fb.setupGlyphOrder(order)
    fb.setupCharacterMap(wt.cmap)
    fb.setupGlyf({n: wt.glyphs[n] for n in order})
    glyf = fb.font["glyf"]
    metrics = {}
    for n in order:
        g = glyf[n]
        g.recalcBounds(glyf)
        metrics[n] = (wt.adv[n], g.xMin if g.numberOfContours else 0)
    fb.setupHorizontalMetrics(metrics)
    fb.setupHorizontalHeader(ascent=asc, descent=desc, lineGap=0)
    vstr = f"Version {VERSION:.3f}" + (f"; {version_tail}" if version_tail else "")
    names = {
        "copyright": COPYRIGHT, "familyName": fam, "styleName": sub,
        "uniqueFontIdentifier": f"{VERSION:.3f};NONE;{ps}", "fullName": f"{FAMILY} {style}",
        "version": vstr, "psName": ps, "manufacturer": "The Limn Sans Project Authors",
        "description": DESCRIPTION, "vendorURL": "https://github.com/dartworklabs/limn-sans",
        "licenseDescription": LICENSE, "licenseInfoURL": LICENSE_URL,
    }
    if not ribbi:
        names.update(typographicFamily=FAMILY, typographicSubfamily=style)
    fb.setupNameTable(names, mac=False)
    fb.setupOS2(version=4, usWeightClass=w, usWidthClass=5, fsType=0, achVendID="NONE", fsSelection=fsel(w),
                sTypoAscender=asc, sTypoDescender=desc, sTypoLineGap=0, usWinAscent=asc, usWinDescent=-desc,
                sxHeight=otRound(W["xh"]), sCapHeight=otRound(W["cap"]), usDefaultChar=0, usBreakChar=32,
                usMaxContext=2)
    if w == 400 and max(20, otRound(0.8 * W["s"])) != UNDERLINE_THICKNESS:
        raise ValueError(f"the Regular's stem now gives {max(20, otRound(0.8 * W['s']))}, not the frozen "
                         f"UNDERLINE_THICKNESS {UNDERLINE_THICKNESS}; the family value has to follow it")
    fb.setupPost(keepGlyphNames=True, underlinePosition=UNDERLINE_POSITION, underlineThickness=UNDERLINE_THICKNESS)
    font = fb.font
    head = font["head"]
    head.fontRevision, head.macStyle = VERSION, 1 if w == 700 else 0
    if os.environ.get("SOURCE_DATE_EPOCH"):     # reproducible builds
        head.created = head.modified = timestampSinceEpoch(int(os.environ["SOURCE_DATE_EPOCH"]))
        font.recalcTimestamp = False
    gasp = newTable("gasp")
    gasp.version = 1
    gasp.gaspRange = {0xFFFF: 0x000F}
    font["gasp"] = gasp
    addOpenTypeFeaturesFromString(font, wt.features())
    os2 = font["OS/2"]
    os2.recalcUnicodeRanges(font)
    os2.recalcCodePageRanges(font)
    os2.recalcAvgCharWidth(font)
    os2.updateFirstAndLastCharIndex(font)
    return font


def subset_coverage(cmap):
    """Complementary web faces: every non-syllable + KS X 1001, then the other syllables."""
    cps = set(cmap)
    if cps & SYLLABLES != SYLLABLES or len(KSX1001) != 2350:
        raise ValueError("web subsets require all 11,172 modern syllables and 2,350 KS X 1001 syllables")
    return {"core": cps - SYLLABLES | KSX1001, "ext": SYLLABLES - KSX1001}


def unicode_range(cps):
    """Exact CSS ranges; gaps must stay gaps so a face never claims the other subset's text."""
    spans = []
    start = end = None
    for cp in sorted(cps):
        if end is not None and cp == end + 1:
            end = cp
            continue
        if start is not None:
            spans.append((start, end))
        start = end = cp
    if start is not None:
        spans.append((start, end))
    return ", ".join(f"U+{a:04X}" + (f"-{b:04X}" if a != b else "") for a, b in spans)


def web_css(w, name, coverage):
    return "\n".join(
        f'@font-face {{\n  font-family: "{FAMILY}";\n  font-style: normal;\n  font-weight: {w};\n'
        f'  font-display: swap;\n  src: url("LimnSans-{name}-{kind}.woff2") format("woff2");\n'
        f'  unicode-range: {unicode_range(cps)};\n}}'
        for kind, cps in coverage.items())


def write_subsets(ttf, w, out=OUT):
    """Subset the final hinted TTF; keep layout closure, glyph names and all licence/name records."""
    with TTFont(ttf) as full:
        coverage = subset_coverage(full.getBestCmap())
    result = {}
    for kind, cps in coverage.items():
        options = subset.Options()
        options.layout_features = ["*"]
        # fontTools' '*' covers only IDs below 256; extension pruning removes the ss01 feature name.
        # Enumerate every existing ID to preserve those feature-name records as well as licence metadata.
        with TTFont(ttf, lazy=True) as source:
            options.name_IDs = sorted({record.nameID for record in source["name"].names})
        options.name_languages = ["*"]
        options.name_legacy = True
        options.glyph_names = True
        options.notdef_outline = True
        options.recalc_timestamp = False
        with TTFont(ttf, recalcTimestamp=False) as font:
            cutter = subset.Subsetter(options=options)
            cutter.populate(unicodes=cps)
            cutter.subset(font)
            if set(font.getBestCmap()) != set(cps):
                raise ValueError(f"{kind}: layout closure changed the requested cmap")
            path = out / f"LimnSans-{WEIGHTS[w]}-{kind}.woff2"
            font.flavor = "woff2"
            font.save(path)
            result[kind] = {"woff2": "fonts/" + path.name, "woff2Bytes": path.stat().st_size,
                            "codepoints": len(cps), "syllables": len(cps & SYLLABLES)}
    return result, web_css(w, WEIGHTS[w], coverage)


def write_release_web(ttf: Path, w: int, out: Path) -> tuple[dict, str]:
    """Compress the final hinted TTF without subsetting, using one portable CSS face per weight."""
    path = out / f"LimnSans-{WEIGHTS[w]}.woff2"
    with TTFont(ttf, recalcTimestamp=False) as font:
        cps = set(font.getBestCmap())
        if any(is_hangul(cp) for cp in cps):
            raise ValueError("release web font contains Hangul")
        font.flavor = "woff2"
        font.save(path)
    css = web_css(w, WEIGHTS[w], {"latin-symbols": cps}).replace(
        f"-{WEIGHTS[w]}-latin-symbols.woff2", f"-{WEIGHTS[w]}.woff2")
    return {"latin-symbols": {"woff2": "fonts/" + path.name, "woff2Bytes": path.stat().st_size,
                              "codepoints": len(cps), "syllables": 0}}, css


def main():
    """Export the selected nine-weight family and manifests; release admission precedes all writes."""
    if PROFILE == "latin-symbols":
        if SPACE_PROVENANCE_IN is None:
            raise ValueError("release requires LIMN_TTF_SPACE_PROVENANCE_IN")
        space_provenance(SPACE_PROVENANCE_IN)
    PLAY = load_js(PLAY_IN, "window.LIMN_PLAY=")
    built = []
    for w in WEIGHTS:
        W, H = load_profile_data(w, PLAY)
        built.append(Weight(w, W, H).build())
        print(f"  {w}: {len(built[-1].glyphs)} glyphs", flush=True)
    # one line box for the family: the 970 / -330 box, grown if any glyph of any weight leaves it
    ymax = max(g.yMax for wt in built for g in wt.glyphs.values() if g.numberOfContours)
    ymin = min(g.yMin for wt in built for g in wt.glyphs.values() if g.numberOfContours)
    asc, desc = max(LINE_ASC, 10 * math.ceil(ymax / 10)), min(LINE_DESC, 10 * math.floor(ymin / 10))
    if (asc, desc) != (LINE_ASC, LINE_DESC):
        print(f"build_ttf: glyphs reach {ymax} / {ymin}; line box grown to {asc} / {desc}")
    if PROFILE == "latin-symbols":
        if not HINT:
            raise ValueError("latin-symbols release requires hinting")
        if OUT.exists() and any(OUT.iterdir()):
            raise ValueError("release output directory must be empty (avoid stale full/subset fonts)")
    OUT.mkdir(parents=True, exist_ok=True)
    tail = git_rev()
    files, css = [], ["/* generated by tools/build_ttf.py; URLs are relative to this stylesheet */"]
    for wt in built:
        font = make_font(wt, asc, desc, tail)
        base = OUT / f"LimnSans-{WEIGHTS[wt.w]}"
        font.save(str(base) + ".ttf")
        if HINT:
            hint_ttf(str(base) + ".ttf")     # in place: ttfautohint reads the whole input before it opens out_file
            font = TTFont(str(base) + ".ttf", recalcTimestamp=False)
            if os.environ.get("SOURCE_DATE_EPOCH"):
                font["head"].created = font["head"].modified = timestampSinceEpoch(int(os.environ["SOURCE_DATE_EPOCH"]))
            font["head"].flags |= 0x0008     # hinted: PPEM rounded to an integer (ttfautohint leaves the bit clear)
            font.save(str(base) + ".ttf")
        font = TTFont(str(base) + ".ttf", recalcTimestamp=False)
        font.flavor = "woff2"
        font.save(str(base) + ".woff2")
        ttf, woff2 = Path(str(base) + ".ttf"), Path(str(base) + ".woff2")
        subsets, face_css = (write_release_web(ttf, wt.w, OUT) if PROFILE == "latin-symbols"
                             else write_subsets(ttf, wt.w))
        css.append(face_css)
        files.append({"w": wt.w, "name": WEIGHTS[wt.w], "ttf": "fonts/" + ttf.name, "woff2": "fonts/" + woff2.name,
                      "ttfBytes": ttf.stat().st_size, "woff2Bytes": woff2.stat().st_size, "glyphs": len(wt.glyphs),
                      "subsets": subsets})
        print(f"wrote {ttf.name} {ttf.stat().st_size:,} B, {woff2.name} {woff2.stat().st_size:,} B ({len(wt.glyphs)} glyphs){' hinted' if HINT else ''}", flush=True)
        if PROFILE == "full":
            print(f"  web core {subsets['core']['woff2Bytes']:,} B (2,350 syllables + all non-syllables), "
              f"ext {subsets['ext']['woff2Bytes']:,} B (8,822 syllables)", flush=True)
    meta = {"profile": PROFILE, "releaseSupported": PROFILE == "latin-symbols", "hinted": HINT, "family": FAMILY, "version": f"{VERSION:.3f}", "rev": tail, "upm": 1000, "asc": asc, "desc": desc, "files": files}
    if PROFILE == "full":
        (OUT / "fonts.js").write_text("/* generated by tools/build_ttf.py, do not edit */\nwindow.LIMN_FONT_FILES=" +
                                      json.dumps(meta, ensure_ascii=False) + ";\n", encoding="utf-8")
    (OUT / "fonts.css").write_text("\n\n".join(css) + "\n", encoding="utf-8")
    if PROFILE == "latin-symbols":
        meta = json.loads(json.dumps(meta))
        for record in meta["files"]:
            record["ttf"] = Path(record["ttf"]).name
            record["woff2"] = Path(record["woff2"]).name
            for face in record["subsets"].values():
                face["woff2"] = Path(face["woff2"]).name
        meta["codepoints"] = sorted(RELEASE_COVERAGE)
        meta["unicodeRange"] = unicode_range(RELEASE_COVERAGE)
        meta["sourceDateEpoch"] = int(os.environ["SOURCE_DATE_EPOCH"]) if os.environ.get("SOURCE_DATE_EPOCH") else None
        meta["inputs"] = {"spaceProvenanceSHA256": hashlib.sha256(SPACE_PROVENANCE_IN.read_bytes()).hexdigest(),
                          "playSHA256": hashlib.sha256(PLAY_IN.read_bytes()).hexdigest(),
                          "supplementalSHA256": {f"limn-hangul-{w}.js": hashlib.sha256(
                              (SYMBOLS_IN / f"limn-hangul-{w}.js").read_bytes()).hexdigest() for w in WEIGHTS}}
        meta["qualityScope"] = "English and supported symbols; Greek/extended Latin included without language QA"
        meta["knownIssues"] = ["Alphabetic subscript ₑ: 800→900 ink area about −1.06%; informational, unchanged",
                               "Arbitrary mixed attached/free mark stacks can have engine-dependent host order and placement; no extended-Latin language QA"]
        (OUT / "fonts.json").write_text(json.dumps(meta, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        (OUT / "fonts.js").write_text("/* generated by tools/build_ttf.py, do not edit */\nwindow.LIMN_FONT_FILES=" +
                                      json.dumps(meta, ensure_ascii=False) + ";\n", encoding="utf-8")
        for source, name in ((SITE.parent / "OFL.txt", "OFL.txt"),
                             (HERE / "OFL-Quicksand.txt", "OFL-Quicksand.txt"),
                             (HERE / "hangul/OFL-NanumSquareRound.txt", "OFL-NanumSquareRound.txt")):
            shutil.copyfile(source, OUT / name)
        install = (SITE.parent / "docs/release-install.md").read_text(encoding="utf-8")
        install = install[install.index("This package covers"):]
        (OUT / "README.md").write_text(f"# Limn Sans {VERSION:.3f} — English and symbols\n\n" + install,
                                      encoding="utf-8")
        checksums = [f"{hashlib.sha256(path.read_bytes()).hexdigest()}  {path.name}"
                     for path in sorted(OUT.iterdir()) if path.is_file() and path.name != "SHA256SUMS"]
        (OUT / "SHA256SUMS").write_text("\n".join(checksums) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
