"""Check the font files (make fonts) against the engine data they were built from.

  uv run --no-project --with fonttools --with brotli --with skia-pathops --with uharfbuzz python3 tools/check_ttf.py

Per weight: glyph counts; the cmap covers every character of limn-font-play.js and limn-hangul-<w>.js (with its
extension limn-hangulext-<w>.js: all 11,172 syllables), 가 has one advance at every weight,
림 maps to the plain syllable; no mapped glyph is empty but space; OS/2 weight, names and one line box
over every glyph; outer contours clockwise; advances = the engine's (advOf, rounded); every pin is ink
at its centre and white just outside; kerning shaped with HarfBuzz = kernOf (every kern pair, every
pkern pair under pnum, and a random sample of all pairs); the proof sentences set by HarfBuzz = the
engine's pen advance; if LIMN_TTF_HINT built the file (the default), it carries TrueType instructions
(fpgm/prep + glyf bytecode on at least one glyph). Core/ext WOFF2 cmaps must be disjoint, their union
must equal the full cmap, with exactly 2,350 / 8,822 modern syllables, and fonts.css must declare the
same coverage. Checks retained glyphs, instructions, licence/line metadata and core layout behavior.
Uses the same LIMN_TTF_OUT / LIMN_TTF_HANGUL_IN / LIMN_TTF_PLAY_IN hooks as build_ttf. Exits 1 on failure.
The latin-symbols release also binds every manifest input hash to the configured producer files and
compares every Unicode cmap, source glyph coordinate/contour/flag tuple and horizontal metric exactly.
"""
import sys as _sys, pathlib as _pl; _sys.path.insert(0, str(_pl.Path(__file__).parent))
import random
import hashlib
import json
import os
import io
import re
import sys

import pathops
import uharfbuzz as hb
from fontTools.misc.roundTools import otRound
from fontTools.misc.timeTools import timestampSinceEpoch
from fontTools.pens.areaPen import AreaPen
from fontTools.feaLib.builder import addOpenTypeFeaturesFromString
from fontTools.ttLib import TTFont

from build_ttf import PROFILE, VERSION, RELEASE_VERSION, RELEASE_COVERAGE, is_hangul, load_profile_data, HINT, KSX1001, OUT, PLAY_IN, RIM, SPACE_PROVENANCE_IN, SYMBOLS_IN, SYLLABLES, WEIGHTS, Weight, load_hangul, load_js, space_provenance, space_table

SENTENCES = ["limn에 핀을 꽂아 두면 다시 읽힌다", "원고 PDF 3개 · 핀 12개 · Resolve all",
             "Sphinx of black quartz, judge my vow. 0123456789", "오늘의 manuscript를 pin it, fix it, done.",
             # typographic spaces and zero-width marks (spaceOf), the symbols added 2026-09-28
             "10\u202f000\u00a0km · a\u2009b\u2002c\u2003d · 가\u3000나 · soft\u00adware · zero\u200bwidth · T\u00adA",
             "₩12,000 ￦5 · № 5 · 5′ 11″ · 1⁄2 · 555‒1234 · e‐mail non‑stop 1990―2000 · ¤ · ○●□■△▲☆★→←↑↓ ℃ ㎡ ①⑩ ㆍ・～"]
fails = []


def fail(w, msg):
    fails.append(f"{w}: {msg}")


def kern_of(K, KC, a, b):          # limn-brand.js kernOf
    v = K.get(a + b)
    if v is not None:
        return v
    l = (KC.get(a) or [None])[0] or a
    r = (KC.get(b) or [None, None])[1] or b
    return K.get(l + r, 0) if l + r != a + b else 0


def engine_width(W, H, wt, s, tnum=True):
    """Pen advance of LIMN_playset(s, {w, tnum}) with the default rules (no optical size, no track)."""
    x, prev = 0.0, None
    SP = space_table(W, H)
    for ch in s:
        if ch == " ":
            x += W["space"]
            prev = None
            continue
        if ch in SP:                  # spaceOf: a space breaks the kerning; a zero-width mark is skipped
            if SP[ch]:
                x += SP[ch]
                prev = None
            continue
        if not tnum and ch in W.get("pglyph", {}):
            g = W["pglyph"][ch]
        elif ch == RIM:
            g = H["glyphs"][ch]
        else:
            g = W["glyphs"].get(ch) or H["glyphs"].get(ch)
        pn = W["pnum"].get(ch) if not tnum and ch not in W.get("pglyph", {}) else None
        if prev:
            x += W["pkern"][prev + ch] if not tnum and (prev + ch) in W["pkern"] else kern_of(W["kern"], W["kcls"], prev, ch)
        x += pn[0] if pn else (wt.adv_of(ch, g) if ch in W["glyphs"] and g is W["glyphs"][ch] else g["adv"])
        prev = ch
    return x


def shape(hbfont, s, feats=None):
    buf = hb.Buffer()
    buf.add_str(s)
    buf.guess_segment_properties()
    hb.shape(hbfont, buf, feats or {})
    return buf


def shaping_font(font):
    """HarfBuzz needs SFNT bytes; decompress a web font once for multiple shaping probes."""
    data = io.BytesIO()
    flavor = font.flavor
    font.flavor = None
    font.save(data)
    font.flavor = flavor
    return hb.Font(hb.Face(data.getvalue()))


def shaping_signature(font, s, feats=None, hbfont=None):
    """Compare names and positions, since subsetting renumbers glyph IDs."""
    buf = shape(hbfont or shaping_font(font), s, feats)
    return [(font.getGlyphName(g.codepoint), p.x_advance, p.y_advance, p.x_offset, p.y_offset)
            for g, p in zip(buf.glyph_infos, buf.glyph_positions)]


def css_coverage(css, filename, w):
    """Read the actual stylesheet's face selection, independent of its range serializer."""
    faces = [face for face in re.findall(r"@font-face\s*\{([^}]+)\}", css)
             if re.search(rf'url\("{re.escape(filename)}"\)', face)]
    if len(faces) != 1 or not re.search(rf"font-weight:\s*{w}\s*;", faces[0]):
        raise ValueError(f"{filename}: missing, duplicated or wrong weight CSS face")
    field = re.search(r"unicode-range:\s*([^;]+);", faces[0])
    if not field:
        raise ValueError(f"{filename}: no unicode-range")
    cps = set()
    for token in field[1].split(","):
        match = re.fullmatch(r"\s*U\+([0-9A-F]+)(?:-([0-9A-F]+))?\s*", token)
        if not match:
            raise ValueError(f"{filename}: invalid range {token!r}")
        a, b = int(match[1], 16), int(match[2] or match[1], 16)
        if a > b or b > 0x10FFFF:
            raise ValueError(f"{filename}: invalid codepoint range")
        span = set(range(a, b + 1))
        if cps & span:
            raise ValueError(f"{filename}: duplicate CSS coverage")
        cps.update(span)
    return cps


def check_web_subsets(w, full, out=OUT):
    """Validate the serialized subset boundary, metadata, outlines, hints and feature behavior."""
    cmap = full.getBestCmap()
    full_order = set(full.getGlyphOrder())
    expected = {"core": (set(cmap) - SYLLABLES) | KSX1001, "ext": SYLLABLES - KSX1001}
    actual = {}
    css = (out / "fonts.css").read_text(encoding="utf-8")
    names = lambda font: {(n.nameID, n.platformID, n.platEncID, n.langID): n.toBytes()
                          for n in font["name"].names}
    for kind, want in expected.items():
        path = out / f"LimnSans-{WEIGHTS[w]}-{kind}.woff2"
        with TTFont(path) as part:
            pcmap = part.getBestCmap()
            actual[kind] = set(pcmap)
            if actual[kind] != want or css_coverage(css, path.name, w) != want:
                fail(w, f"{kind}: cmap / CSS differ from the required subset")
            if names(part) != names(full):
                fail(w, f"{kind}: name / licence metadata changed")
            for table, attrs in (("head", ("unitsPerEm", "fontRevision")),
                                 ("OS/2", ("usWeightClass", "fsType", "fsSelection", "sTypoAscender", "sTypoDescender", "sTypoLineGap", "usWinAscent", "usWinDescent")),
                                 ("hhea", ("ascent", "descent", "lineGap"))):
                if any(getattr(part[table], attr) != getattr(full[table], attr) for attr in attrs):
                    fail(w, f"{kind}: {table} metadata changed")
            for table in ("fpgm", "prep", "cvt ", "gasp"):
                if (table in part) != (table in full) or (table in full and part[table].compile(part) != full[table].compile(full)):
                    fail(w, f"{kind}: {table.rstrip()} hinting changed")
            if any(gn != cmap.get(cp) for cp, gn in pcmap.items()):
                fail(w, f"{kind}: cmap glyph names changed")
            for gn in part.getGlyphOrder():
                if gn not in full_order:
                    fail(w, f"{kind}: unexpected glyph {gn}")
                    continue
                g, original = part["glyf"][gn], full["glyf"][gn]
                if part["hmtx"][gn] != full["hmtx"][gn] or g.getCoordinates(part["glyf"]) != original.getCoordinates(full["glyf"]):
                    fail(w, f"{kind}: {gn} glyph / metrics changed")
                pg, fg = getattr(g, "program", None), getattr(original, "program", None)
                if (pg.getBytecode() if pg else b"") != (fg.getBytecode() if fg else b""):
                    fail(w, f"{kind}: {gn} glyph hinting changed")
            if kind == "core":
                for table in ("GSUB", "GPOS"):
                    tags = lambda f: {r.FeatureTag for r in f[table].table.FeatureList.FeatureRecord} if table in f else set()
                    if tags(part) != tags(full):
                        fail(w, f"core: {table} feature tags changed")
                samples = ["AV To Wa éÀ 0123456789 ag", "림 가 나 ℃ ㎡ ①⑩"]
            else:
                samples = ["".join(chr(cp) for cp in sorted(want)[:8])]
            part_hbf, full_hbf = shaping_font(part), shaping_font(full)
            for s in samples:
                for feats in (None, {"pnum": True}, {"ss01": True}, {"zero": True},
                              {"pnum": True, "zero": True}, {"tnum": True}, {"ss02": True}):
                    if shaping_signature(part, s, feats, part_hbf) != shaping_signature(full, s, feats, full_hbf):
                        fail(w, f"{kind}: shaping changed for {s!r}, {feats}")
            print(f"  {kind}: {len(pcmap):,} codepoints, {len(actual[kind] & SYLLABLES):,} syllables, {path.stat().st_size:,} B", flush=True)
    if actual["core"] & actual["ext"] or actual["core"] | actual["ext"] != set(cmap):
        fail(w, "subset cmaps overlap or their union differs from the full font")
    if len(actual["core"] & SYLLABLES) != 2350 or len(actual["ext"]) != 8822:
        fail(w, "subsets must have exactly 2,350 / 8,822 syllables")


def check_release_glyphs(w: int, font: TTFont, expected: set[str]) -> None:
    """Reject every unexpected glyph, including unencoded GSUB targets and the pinned logo."""
    if set(font.getGlyphOrder()) != expected:
        fail(w, "release glyph inventory differs (unencoded Hangul/logo or missing alternate)")
    if any(is_hangul(cp) for table in font["cmap"].tables if table.isUnicode() for cp in table.cmap):
        fail(w, "release cmap contains Hangul")
    tags = {r.FeatureTag for table in ("GSUB", "GPOS") if table in font
            for r in font[table].table.FeatureList.FeatureRecord}
    if "ss02" in tags:
        fail(w, "release retains logo ss02")


def check_release_source(w: int, font: TTFont, expected: Weight) -> None:
    """Bind all serialized Unicode mappings, outlines and metrics to one built release Weight.

    Every release codepoint is in the BMP, so every Unicode cmap must equal expected.cmap.
    The admitted ttfautohint pipeline preserves the source coordinates, contour endpoints,
    on-curve flags and hmtx exactly, including unencoded alternates; bytecode is checked separately.
    No auxiliary glyphs are introduced by this pipeline (the exact inventory check remains required).
    """
    if font.getBestCmap() != expected.cmap or any(
            table.cmap != expected.cmap for table in font["cmap"].tables if table.isUnicode()):
        fail(w, "release source cmap differs from admitted codepoint-to-glyph mappings")
    glyf = font["glyf"]
    for name, original in expected.glyphs.items():
        if name not in glyf:
            continue  # The inventory check reports missing source glyphs.
        if glyf[name].getCoordinates(glyf) != original.getCoordinates(None):
            fail(w, f"release source {name} outline differs (coordinates / contours / flags)")
        metrics = (expected.adv[name], original.xMin if original.numberOfContours else 0)
        if font["hmtx"][name] != metrics:
            fail(w, f"release source {name} metrics differ (advance / LSB)")


def check_release_layout(w: int, font: TTFont, expected: Weight) -> None:
    """Reject resealed missing/wrong anchors or substitutions against the admitted exporter layout.

    Compile with the serialized glyph order so matching TTF/WOFF2 mutations cannot
    hide changed mark placement. Behavioral attachment tests separately check the
    source rules; this readback binds those rules to every final binary.
    """
    reference = TTFont()
    reference.setGlyphOrder(font.getGlyphOrder())
    addOpenTypeFeaturesFromString(reference, expected.features())
    # SFNT save resolves large-offset PairPos splits/ExtensionPos wrappers. Compare
    # the fully serialized layout, retaining every lookup flag, index and value.
    stream = io.BytesIO()
    reference.save(stream)
    stream.seek(0)
    reference = TTFont(stream)
    reference.setGlyphOrder(font.getGlyphOrder())
    for tag in ("GDEF", "GPOS", "GSUB"):
        if tag not in font or tag not in reference or font[tag].compile(font) != reference[tag].compile(reference):
            fail(w, f"release source {tag} layout differs (anchors / kerning / substitutions)")


def check_release_inputs(meta: dict, play_in=PLAY_IN, symbols_in=SYMBOLS_IN,
                         space_in=SPACE_PROVENANCE_IN) -> None:
    """Reject absent, stale or extra input identities against all eleven configured producer files.

    Paths are the same explicit inputs used for release reconstruction. File-read and provenance
    errors propagate and fail the command; even pre-supplied supplemental spaces require authority.
    """
    if symbols_in is None or space_in is None:
        fail("package", "release requires configured supplemental inputs and U+3000 provenance")
        return
    space_provenance(space_in)
    actual = {"playSHA256": hashlib.sha256(play_in.read_bytes()).hexdigest(),
              "spaceProvenanceSHA256": hashlib.sha256(space_in.read_bytes()).hexdigest(),
              "supplementalSHA256": {f"limn-hangul-{w}.js": hashlib.sha256(
                  (symbols_in / f"limn-hangul-{w}.js").read_bytes()).hexdigest() for w in WEIGHTS}}
    if meta.get("inputs") != actual:
        fail("package", "manifest input identities differ from configured producer files")


def check_release_web(w: int, full: TTFont, out=OUT) -> None:
    """Read back the single web face, verify CSS, final hinted tables, and shaped feature parity."""
    path = out / f"LimnSans-{WEIGHTS[w]}.woff2"
    css = (out / "fonts.css").read_text(encoding="utf-8")
    if css_coverage(css, path.name, w) != set(full.getBestCmap()):
        fail(w, "release CSS differs from exact font coverage")
    with TTFont(path, recalcTimestamp=False) as web:
        if set(web.keys()) != set(full.keys()):
            fail(w, "release web table inventory changed")
        # WOFF2 may normalize glyf encoding/loca and set head.flags bit 11. Check glyph semantics
        # separately; all hint/layout/name/metrics tables must retain identical final hinted bytes.
        for tag in full.keys():
            if tag in ("GlyphOrder", "head", "loca", "glyf") or tag not in web:
                continue
            if full[tag].compile(full) != web[tag].compile(web):
                fail(w, f"release web {tag} table changed")
        head = lambda f: (f["head"].unitsPerEm, f["head"].fontRevision, f["head"].flags & ~0x800)
        if head(full) != head(web):
            fail(w, "release web head metadata changed")
        if full.getBestCmap() != web.getBestCmap() or full.getGlyphOrder() != web.getGlyphOrder():
            fail(w, "release web glyph inventory changed")
        for gn in set(full.getGlyphOrder()) & set(web.getGlyphOrder()):
            g, original = web["glyf"][gn], full["glyf"][gn]
            if g.getCoordinates(web["glyf"]) != original.getCoordinates(full["glyf"]):
                fail(w, f"release web {gn} outline changed")
            pg, fg = getattr(g, "program", None), getattr(original, "program", None)
            if (pg.getBytecode() if pg else b"") != (fg.getBytecode() if fg else b""):
                fail(w, f"release web {gn} hinting changed")
        full_hbf, web_hbf = shaping_font(full), shaping_font(web)
        for feats in ({}, {"pnum": True}, {"tnum": True}, {"ss01": True}, {"zero": True},
                      {"pnum": True, "zero": True}, {"kern": False}):
            sample = "AV To Wa ag 0123456789 ℃ ㎡ ①⑩"
            if shaping_signature(full, sample, feats, full_hbf) != shaping_signature(web, sample, feats, web_hbf):
                fail(w, f"release web shaping changed: {feats}")



def check_release_package(out=OUT, *, play_in=PLAY_IN, symbols_in=SYMBOLS_IN,
                          space_in=SPACE_PROVENANCE_IN) -> None:
    """Verify input identities, portable manifests, exact inventory, sizes, licences and checksums."""
    meta = json.loads((out / "fonts.json").read_text(encoding="utf-8"))
    check_release_inputs(meta, play_in, symbols_in, space_in)
    if (meta.get("profile"), meta.get("version"), meta.get("hinted"), meta.get("codepoints")) != (
            "latin-symbols", f"{RELEASE_VERSION:.3f}", True, sorted(RELEASE_COVERAGE)):
        fail("package", "manifest profile / version / hinting / exact coverage differs")
    if load_js(out / "fonts.js", "window.LIMN_FONT_FILES=") != meta:
        fail("package", "JavaScript manifest differs from final portable JSON manifest")
    records = meta.get("files", [])
    if [r.get("w") for r in records] != list(WEIGHTS):
        fail("package", "manifest must contain each of the nine weights once")
    expected = {"fonts.css", "fonts.js", "fonts.json", "README.md", "OFL.txt", "OFL-Quicksand.txt",
                "OFL-NanumSquareRound.txt", "SHA256SUMS"}
    for w, style in WEIGHTS.items():
        expected.update(f"LimnSans-{style}.{ext}" for ext in ("ttf", "woff2"))
    if {path.name for path in out.iterdir()} != expected:
        fail("package", "package inventory differs (missing file or stale subset)")
    for record in records:
        if record.get("w") not in WEIGHTS:
            continue
        for ext in ("ttf", "woff2"):
            filename = f"LimnSans-{WEIGHTS[record['w']]}.{ext}"
            if record.get(ext) != filename or record.get(ext + "Bytes") != (out / filename).stat().st_size:
                fail("package", f"manifest {ext} portable filename / size differs")
    sums = (out / "SHA256SUMS").read_text(encoding="utf-8").splitlines()
    wanted = {f"{hashlib.sha256((out / name).read_bytes()).hexdigest()}  {name}"
              for name in expected - {"SHA256SUMS"}}
    if len(sums) != len(wanted) or set(sums) != wanted:
        fail("package", "SHA256SUMS differs from exact package bytes")



def main():
    """Validate the selected profile against its admitted engine inputs and serialized output."""
    PLAY = load_js(PLAY_IN, "window.LIMN_PLAY=")
    rnd = random.Random(7)
    hangul_adv = {}
    print(f"{'w':>4} {'glyphs':>6} {'Hangul':>6} {'Latin':>5} {'pairs':>6} {'ttf B':>10} {'woff2 B':>9}  sentence drift % (HarfBuzz vs engine)")
    for w, name in WEIGHTS.items():
        W, H = load_profile_data(w, PLAY)
        path = OUT / f"LimnSans-{name}.ttf"
        f = TTFont(path, recalcTimestamp=False)
        TTFont(OUT / f"LimnSans-{name}.woff2").getGlyphOrder()   # the woff2 opens too
        wt = Weight(w, W, H)
        cmap = f.getBestCmap()
        glyf, hmtx = f["glyf"], f["hmtx"]
        order = f.getGlyphOrder()
        n_ko = sum(1 for c in cmap if 0xAC00 <= c <= 0xD7A3)
        # hinting (LIMN_TTF_HINT, default on): fpgm/prep present, and at least one glyph carries bytecode
        if HINT:
            if "fpgm" not in f or "prep" not in f:
                fail(w, "LIMN_TTF_HINT=1 but fpgm/prep missing (hint_ttf didn't run or was stripped)")
            elif not any(glyf[gn].numberOfContours and getattr(glyf[gn], "program", None) and glyf[gn].program.getBytecode()
                         for gn in order):
                fail(w, "LIMN_TTF_HINT=1 but no glyph carries TrueType instructions")
        elif "fpgm" in f or "prep" in f:
            fail(w, "LIMN_TTF_HINT=0 but fpgm/prep present (stale hinted file? rebuild)")
        # coverage
        SP = space_table(W, H)
        want = set(W["glyphs"]) | set(H["glyphs"]) | {" "} | set(SP)
        miss = [c for c in want if ord(c) not in cmap]
        if miss:
            fail(w, f"cmap misses {''.join(sorted(miss))}")
        if PROFILE == "full" and n_ko != 11172:                 # every modern syllable, from the data (release 2026-09-30)
            fail(w, f"{n_ko} of the 11,172 syllables in the cmap")
        if PROFILE == "full":
            check_web_subsets(w, f)
        else:
            if set(cmap) != RELEASE_COVERAGE:
                fail(w, "release coverage differs from the frozen non-Hangul repertoire")
            wt.build()
            check_release_glyphs(w, f, set(wt.glyphs))
            check_release_source(w, f, wt)
            check_release_layout(w, f, wt)
            check_release_web(w, f)
            tags = {r.FeatureTag for tag in ("GSUB", "GPOS") if tag in f
                    for r in f[tag].table.FeatureList.FeatureRecord}
            if not {"pnum", "tnum", "kern", "ss01", "zero"} <= tags:
                fail(w, "release missing required OpenType features")
            for text, feature, expected in (("ag", "ss01", ["a.ss01", "g.ss01"]),
                                            ("0", "zero", ["zero.zero"]),
                                            ("01", "pnum", ["zero.pnum", "one.pnum"])):
                got = [item[0] for item in shaping_signature(f, text, {feature: True})]
                if got != expected:
                    fail(w, f"release {feature} substitution differs: {got}")
        adv0 = hangul_adv.setdefault("가", hmtx[cmap[0xAC00]][0]) if 0xAC00 in cmap else None
        if adv0 is not None and hmtx[cmap[0xAC00]][0] != adv0:
            fail(w, f"가 advance {hmtx[cmap[0xAC00]][0]}, another weight has {adv0} (one Hangul advance for every weight)")
        for ch, adv in SP.items():       # spaces: the engine's width, no ink
            gn = cmap.get(ord(ch))
            if gn and (f["hmtx"][gn][0] != otRound(adv) or f["glyf"][gn].numberOfContours):
                fail(w, f"space U+{ord(ch):04X}: {f['hmtx'][gn][0]} vs {adv}")
        if PROFILE == "full" and cmap.get(ord(RIM)) != "uniB9BC":
            fail(w, f"림 maps to {cmap.get(ord(RIM))}, not the syllable")
        if ("uniB9BC.ss02" in order) != (__import__("os").environ.get("LIMN_TTF_LOGO") == "1"):
            fail(w, "the pinned logo 림 (ss02) is in the file only with LIMN_TTF_LOGO=1")
        for cp, gn in cmap.items():
            if cp != 0x20 and chr(cp) not in SP and glyf[gn].numberOfContours == 0:
                fail(w, f"empty glyph {gn} for U+{cp:04X}")
        # names, OS/2, line box
        os2, hhea = f["OS/2"], f["hhea"]
        if os2.usWeightClass != w:
            fail(w, f"usWeightClass {os2.usWeightClass}")
        if PROFILE == "latin-symbols" and os.environ.get("SOURCE_DATE_EPOCH"):
            epoch = timestampSinceEpoch(int(os.environ["SOURCE_DATE_EPOCH"]))
            if f["head"].created != epoch or f["head"].modified != epoch:
                fail(w, "SOURCE_DATE_EPOCH timestamps not retained after hinting")
        nm = f["name"]
        if abs(f["head"].fontRevision - VERSION) > 0.00002 or not (nm.getDebugName(5) or "").startswith(f"Version {VERSION:.3f}"):
            fail(w, "font revision / version name differs from selected profile")
        if not (nm.getDebugName(3) or "").startswith(f"{VERSION:.3f};"):
            fail(w, "unique font identifier version differs from selected profile")
        fam = nm.getDebugName(16) or nm.getDebugName(1)
        if fam != "Limn Sans" or nm.getDebugName(6) != f"LimnSans-{name}":
            fail(w, f"names {fam!r} {nm.getDebugName(6)!r}")
        if "Open Font License" not in (nm.getDebugName(13) or "") or "NAVER" not in (nm.getDebugName(0) or "") or "Quicksand" not in nm.getDebugName(0):
            fail(w, "licence / copyright names")
        asc, desc = hhea.ascent, hhea.descent
        if (os2.sTypoAscender, os2.sTypoDescender, os2.usWinAscent, -os2.usWinDescent) != (asc, desc, asc, desc) or not os2.fsSelection & 0x80:
            fail(w, "typo / hhea / win differ")
        gs = f.getGlyphSet()
        for gn in order:
            g = glyf[gn]
            if not g.numberOfContours:
                continue
            if g.yMax > asc or g.yMin < desc:
                fail(w, f"{gn} {g.yMin}..{g.yMax} outside the line box {desc}..{asc}")
            ap = AreaPen(gs)
            gs[gn].draw(ap)
            if ap.value >= 0:
                fail(w, f"{gn}: outer contours not clockwise (area {ap.value:.0f})")
        # advances
        for ch, g in W["glyphs"].items():
            if ch == RIM:
                continue
            if hmtx[cmap[ord(ch)]][0] != otRound(wt.adv_of(ch, g)):
                fail(w, f"advance {ch} {hmtx[cmap[ord(ch)]][0]} vs {wt.adv_of(ch, g)}")
        for ch, g in H["glyphs"].items():
            if (ch not in W["glyphs"] or ch == RIM) and hmtx[cmap[ord(ch)]][0] != otRound(g["adv"]):
                fail(w, f"advance {ch}")
        # pins: ink at the centre, white just outside (above for the i rule, below for base)
        npins = 0
        for ch, dt in W["dots"].items():
            gn = cmap[ord(ch)]
            p = pathops.Path()
            gs[gn].draw(p.getPen())
            for x, y, r in wt.pins_of(ch, W["glyphs"][ch]):
                npins += 1
                if not p.contains((x, y)):
                    fail(w, f"pin of {ch} missing at {x:.0f},{y:.0f}")
            k0 = dt["pins"][0][0]
            if k0 in ("i", "base"):
                x, y, r = wt.pins_of(ch, W["glyphs"][ch])[0]
                probe = (x, y + r + 3) if k0 == "i" else (x, y - r - 3)
                if p.contains(probe):
                    fail(w, f"pin of {ch} not a circle (ink at {probe})")
        # kerning with HarfBuzz
        hbf = hb.Font(hb.Face(hb.Blob.from_file_path(str(path))))
        K, KC, PK = W["kern"], W["kcls"], W["pkern"]
        chars = [c for c in W["glyphs"] if c != RIM]
        pairs = [(k[0], k[1], True) for k in K] + [(k[0], k[1], False) for k in PK]
        pairs += [(rnd.choice(chars), rnd.choice(chars), rnd.random() < 0.8) for _ in range(4000)]
        bad = 0
        for a, b, tn in pairs:
            buf = shape(hbf, a + b, None if tn else {"pnum": True})
            if len(buf.glyph_infos) != 2:
                continue
            ga = f.getGlyphName(buf.glyph_infos[0].codepoint)
            got = buf.glyph_positions[0].x_advance - hmtx[ga][0]
            want = PK[a + b] if not tn and (a + b) in PK else kern_of(K, KC, a, b)
            if got != otRound(want):
                bad += 1
                if bad <= 5:
                    fail(w, f"kern {a}{b} ({'tnum' if tn else 'pnum'}) {got} vs {want}")
        if bad > 5:
            fail(w, f"... {bad} kern pairs off in all")
        # sentences
        drift = []
        sentences = SENTENCES + ["원고 PDF 3개 · 핀 12개 · 0123456789"]
        if PROFILE == "latin-symbols":
            sentences = ["".join(c for c in sentence if not is_hangul(ord(c))) for sentence in sentences]
        for s in sentences:
            tn = not s.endswith("0123456789") or s.startswith("Sphinx")
            e = engine_width(W, H, wt, s, tnum=tn)
            buf = shape(hbf, s, None if tn else {"pnum": True})
            got = sum(p.x_advance for p in buf.glyph_positions)
            drift.append(f"{100 * (got - e) / e:+.3f}{'' if tn else 'p'}")
            if abs(got - e) > 0.005 * e:
                fail(w, f"sentence {s!r}: {got} vs engine {e:.1f}")
        print(f"{w:>4} {len(order):>6} {n_ko:>6} {len(W['glyphs']) - 1:>5} {len(pairs):>6} {path.stat().st_size:>10,} "
              f"{(OUT / f'LimnSans-{name}.woff2').stat().st_size:>9,}  {' '.join(drift)}  pins {npins}", flush=True)
    if PROFILE == "latin-symbols":
        check_release_package()
    print("OK" if not fails else f"{len(fails)} FAILURES:\n  " + "\n  ".join(fails[:60]))
    sys.exit(1 if fails else 0)


if __name__ == "__main__":
    main()
