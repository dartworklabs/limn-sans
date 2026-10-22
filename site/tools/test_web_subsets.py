"""Web font export contracts, using real serialized fonts with layout alternates."""
import array
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from fontTools.feaLib.builder import addOpenTypeFeaturesFromString
from fontTools.fontBuilder import FontBuilder
from fontTools.pens.ttGlyphPen import TTGlyphPen
from fontTools.ttLib import TTFont, newTable
from fontTools.ttLib.tables.ttProgram import Program

import build_ttf as build
import check_ttf as check


def fixture(path):
    fb = FontBuilder(1000, isTTF=True)
    order = [".notdef", "space", "a", "a.ss01", "zero", "zero.pnum", "zero.zero", "hangul", "logo"]
    fb.setupGlyphOrder(order)
    cmap = {cp: "hangul" for cp in range(0xAC00, 0xD7A4)}
    cmap.update({32: "space", 48: "zero", 97: "a", 0x3131: "hangul", 0x1F600: "a"})
    fb.setupCharacterMap(cmap)
    glyphs = {}
    for i, name in enumerate(order):
        pen = TTGlyphPen(None)
        if name != "space":
            pen.moveTo((20, 0))
            pen.lineTo((20, 600 + i))
            pen.lineTo((300 + i, 600 + i))
            pen.lineTo((300 + i, 0))
            pen.closePath()
        glyphs[name] = pen.glyph()
    fb.setupGlyf(glyphs)
    fb.setupHorizontalMetrics({name: (500 + i, 20 if name != "space" else 0) for i, name in enumerate(order)})
    fb.setupHorizontalHeader(ascent=970, descent=-330)
    fb.setupNameTable({"familyName": "Limn Sans", "styleName": "Regular", "psName": "LimnSans-Regular",
                       "licenseDescription": build.LICENSE, "copyright": build.COPYRIGHT})
    fb.setupOS2(usWeightClass=400, sTypoAscender=970, sTypoDescender=-330, usWinAscent=970, usWinDescent=330)
    fb.setupPost(keepGlyphNames=True)
    for tag in ("fpgm", "prep"):
        table = newTable(tag)
        table.program = Program()
        table.program.fromBytecode([0xB0, 0, 0x21])  # PUSHB 0; POP
        fb.font[tag] = table
    cvt = newTable("cvt ")
    cvt.values = array.array("h", [20, 40])
    fb.font["cvt "] = cvt
    glyphs["a"].program = Program()
    glyphs["a"].program.fromBytecode([0xB0, 0, 0x21])
    addOpenTypeFeaturesFromString(fb.font, """
        languagesystem DFLT dflt;
        feature pnum { sub zero by zero.pnum; } pnum;
        feature tnum { sub zero.pnum by zero; } tnum;
        feature zero { sub zero by zero.zero; } zero;
        feature ss01 { featureNames { name "Double-storey a"; }; sub a by a.ss01; } ss01;
        feature ss02 { sub hangul by logo; } ss02;
        feature kern { pos a zero -30; } kern;
    """)
    fb.font.save(path)


class WebSubsetContracts(unittest.TestCase):
    def setUp(self):
        """Match the resolved production input root, including macOS /var symlinks."""
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.out = Path(self.temp.name).resolve()
        self.ttf = self.out / "LimnSans-Regular.ttf"
        fixture(self.ttf)

    def test_serialized_subsets_have_complementary_coverage_and_preserve_layout(self):
        meta, css = build.write_subsets(self.ttf, 400, self.out)
        (self.out / "fonts.css").write_text(css)
        # Independent admission oracle: two-byte EUC-KR Hangul rows, rather than the exporter constants.
        ks = set()
        for cp in range(0xAC00, 0xD7A4):
            encoded = chr(cp).encode("euc-kr")
            if len(encoded) == 2 and 0xB0 <= encoded[0] <= 0xC8:
                ks.add(cp)
        self.assertEqual(len(ks), 2350)
        with TTFont(self.ttf) as full, TTFont(self.out / "LimnSans-Regular-core.woff2") as core, TTFont(self.out / "LimnSans-Regular-ext.woff2") as ext:
            cc, ec = set(core.getBestCmap()), set(ext.getBestCmap())
            self.assertEqual(cc & set(range(0xAC00, 0xD7A4)), ks)
            self.assertEqual(len(ec), 8822)
            self.assertFalse(cc & ec)
            self.assertEqual(cc | ec, set(full.getBestCmap()))
            self.assertIn(0x1F600, cc)
            self.assertIn(0x3131, cc)
            self.assertTrue({"a.ss01", "zero.pnum", "zero.zero", "logo"} <= set(core.getGlyphOrder()))
            check.fails.clear()
            check.check_web_subsets(400, full, self.out)
            self.assertEqual(check.fails, [])
            self.assertEqual(check.shaping_signature(core, "a0", {"ss01": True, "pnum": True}),
                             check.shaping_signature(full, "a0", {"ss01": True, "pnum": True}))
            self.assertIn("logo", ext.getGlyphOrder())
            self.assertEqual(check.shaping_signature(ext, "똠", {"ss02": True}),
                             check.shaping_signature(full, "똠", {"ss02": True}))
            self.assertEqual(meta["core"]["syllables"], 2350)
            self.assertEqual(meta["ext"]["syllables"], 8822)

    def test_export_rejects_incomplete_full_hangul_coverage(self):
        with self.assertRaises(ValueError):
            build.subset_coverage({0xAC00: "ga", 97: "a"})

    def test_checker_rejects_changed_hint_control_values(self):
        _, css = build.write_subsets(self.ttf, 400, self.out)
        (self.out / "fonts.css").write_text(css)
        path = self.out / "LimnSans-Regular-core.woff2"
        with TTFont(path) as part:
            part["cvt "].values[0] += 1
            part.save(path)
        with TTFont(self.ttf) as full:
            check.fails.clear()
            check.check_web_subsets(400, full, self.out)
            self.assertEqual(check.fails, ["400: core: cvt hinting changed"])

    def test_checker_rejects_changed_units_per_em(self):
        _, css = build.write_subsets(self.ttf, 400, self.out)
        (self.out / "fonts.css").write_text(css)
        path = self.out / "LimnSans-Regular-core.woff2"
        with TTFont(path) as part:
            part["head"].unitsPerEm += 1
            part.save(path)
        with TTFont(self.ttf) as full:
            check.fails.clear()
            check.check_web_subsets(400, full, self.out)
            self.assertEqual(check.fails, ["400: core: head metadata changed"])

    def test_hangul_hook_merges_extension_without_touching_site_data(self):
        def js(path, marker, data):
            path.write_text(marker + json.dumps(data) + ";")
        js(self.out / "limn-hangul-400.js", "window.LIMN_HANGUL[400]=", {"glyphs": {"가": {"adv": 815}}, "ext": "limn-hangulext-400.js"})
        js(self.out / "limn-hangulext-400.js", "window.LIMN_HANGUL_EXT[400]=", {"glyphs": {"똠": {"adv": 815}}})
        with patch.object(build, "HANGUL_IN", self.out):
            self.assertEqual(set(build.load_hangul(400)["glyphs"]), {"가", "똠"})

    def test_css_parser_rejects_duplicated_coverage(self):
        css = '@font-face {font-weight: 400; src: url("test.woff2"); unicode-range: U+AC00-AC02, U+AC01;}'
        with self.assertRaises(ValueError):
            check.css_coverage(css, "test.woff2", 400)

    def test_hangul_hook_rejects_extension_path_outside_input_directory(self):
        (self.out / "limn-hangul-400.js").write_text(
            'window.LIMN_HANGUL[400]=' + json.dumps({"glyphs": {}, "ext": "../outside.js"}) + ";")
        with patch.object(build, "HANGUL_IN", self.out), self.assertRaisesRegex(SystemExit, "input directory"):
            build.load_hangul(400)

    def test_hangul_hook_rejects_symlinked_extension_outside_input_directory(self):
        """Resolving the extension must reject a symlink escape even with a local basename."""
        inputs = self.out / "input"
        inputs.mkdir()
        outside = self.out / "outside.js"
        outside.write_text('window.LIMN_HANGUL_EXT[400]={"glyphs":{}};')
        (inputs / "extension.js").symlink_to(outside)
        (inputs / "limn-hangul-400.js").write_text(
            'window.LIMN_HANGUL[400]=' + json.dumps({"glyphs": {}, "ext": "extension.js"}) + ";")
        with patch.object(build, "HANGUL_IN", inputs), self.assertRaisesRegex(SystemExit, "input directory"):
            build.load_hangul(400)


if __name__ == "__main__":
    unittest.main()
