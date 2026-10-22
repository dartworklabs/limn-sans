"""Serialized attachment must position marks without changing cluster advances or outlines."""

import io
import unittest

import build_ttf as build
import check_ttf as check
import uharfbuzz as hb
from fontTools.pens.ttGlyphPen import TTGlyphPen
from hypothesis import given, settings
from hypothesis import strategies as st


def rectangle(x0, y0, x1, y1):
    """Make a deliberately asymmetric ink fixture with exact integer bounds."""
    pen = TTGlyphPen(None)
    pen.moveTo((x0, y0))
    pen.lineTo((x0, y1))
    pen.lineTo((x1, y1))
    pen.lineTo((x1, y0))
    pen.closePath()
    glyph = pen.glyph()
    glyph.recalcBounds(None)
    return glyph


def fixture():
    """Use the source's o-width reference and optical x anchor, with all five mark roles."""
    data = {
        "xh": 510,
        "xo": 515,
        "cap": 700,
        "s": 40,
        "pin": {"r": 35.56, "gap": 79.61, "dotgap": 74.61},
        "glyphs": {"o": {"adv": 597}},
        "kern": {"xx": -30},
        "kcls": {},
    }
    wt = build.Weight(100, data, {})
    records = {
        ".notdef": (None, (0, 0, 500, 700), 600),
        "space": (" ", (0, 0, 0, 0), 270),
        "x": ("x", (44, 0, 446, 510), 490),
        "o": ("o", (50, 0, 547, 515), 597),
        "A": ("A", (100, 0, 500, 700), 600),
        "a.ss01": ("a", (40, 0, 440, 510), 500),
        "a": ("a", (40, 0, 420, 510), 500),
        "i": ("i", (80, 0, 150, 665), 230),
        "j": ("j", (50, -200, 150, 665), 230),
        "dotlessi": ("ı", (80, 0, 150, 510), 230),
        "uni0237": ("ȷ", (50, -200, 150, 510), 230),
        "uni1ECB": ("ị", (80, -130, 150, 665), 230),
        "iogonek": ("į", (80, -160, 150, 665), 230),
        "gravecomb": ("\u0300", (-406, 590, -281, 727), 0),
        "acutecomb": ("\u0301", (-316, 590, -191, 727), 0),
        "uni030A": ("\u030a", (-380, 585, -217, 748), 0),
        "uni031B": ("\u031b", (-218, 457, 24, 649), 0),
        "dotbelowcomb": ("\u0323", (-334, -130, -263, -59), 0),
        "uni0327": ("\u0327", (-352, -126, -239, 37), 0),
        "uni0328": ("\u0328", (-214, -160, -74, 35), 0),
        "uni0335": ("\u0335", (-398, 238, -199, 272), 0),
    }
    for name, (char, box, advance) in records.items():
        wt.glyphs[name] = rectangle(*box)
        wt.adv[name] = advance
        if char is not None:
            wt.chars[name] = char
            if "." not in name:
                wt.cmap[ord(char)] = name
    wt.alts["ss01"]["a"] = "a.ss01"
    return wt


def shape(font, text, features=None):
    """Shape the serialized font through HarfBuzz, returning glyph names and actual positions."""
    stream = io.BytesIO()
    font.save(stream)
    hbf = hb.Font(hb.Face(stream.getvalue()))
    hbf.scale = (1000, 1000)
    buffer = hb.Buffer()
    buffer.add_str(text)
    buffer.guess_segment_properties()
    hb.shape(hbf, buffer, features or {})
    return [
        (font.getGlyphName(info.codepoint), pos.x_advance, pos.x_offset, pos.y_offset)
        for info, pos in zip(buffer.glyph_infos, buffer.glyph_positions)
    ]


class MarkAttachmentContracts(unittest.TestCase):
    """The exporter must carry semantic anchors, outward stacking and dot replacement."""

    def setUp(self):
        """Compile a real SFNT, keeping fixtures independent of the attachment implementation."""
        self.weight = fixture()
        self.font = build.make_font(self.weight, 970, -330, "test")

    def test_grave_and_acute_share_semantic_endpoint_and_preserve_advance(self):
        """Slanted marks attach by the o reference, never by their different ink centres."""
        for mark in ("\u0300", "\u0301"):
            with self.subTest(mark=mark):
                got = shape(self.font, "x" + mark)
                self.assertEqual(sum(row[1] for row in got), 490)
                self.assertEqual(got[1][2:], (53, 0))

    def test_above_stacks_clear_ink_even_with_intervening_below(self):
        """Filtering must attach the second above mark beyond the first, skipping below marks."""
        for text in ("x\u0300\u0301", "x\u0300\u0323\u0301"):
            got = shape(self.font, text)
            grave = next(row for row in got if row[0] == "gravecomb")
            acute = next(row for row in got if row[0] == "acutecomb")
            self.assertGreater(acute[3] + 590, grave[3] + 727)
            self.assertEqual(sum(row[1] for row in got), 490)

    def test_below_stacks_move_outward_and_overlay_stays_at_midline(self):
        """Below accents must not occupy the same ink; overlay retains its source vertical role."""
        got = shape(self.font, "x\u0323\u0323\u0335")
        below = [row for row in got if row[0] == "dotbelowcomb"]
        self.assertLess(below[1][3] - 59, below[0][3] - 130)
        self.assertEqual(next(row for row in got if row[0] == "uni0335")[3], 0)

    def test_above_marks_replace_i_j_pin_across_below_marks(self):
        """Existing dotless glyphs replace the pin only when an above mark follows."""
        for char, name in (("i", "dotlessi"), ("j", "uni0237")):
            self.assertEqual(shape(self.font, char + "\u0323\u0300")[0][0], name)
            self.assertEqual(shape(self.font, char + "\u0323")[0][0], "uni1ECB" if char == "i" else char)

    def test_precomposed_below_i_loses_pin_only_before_surviving_above(self):
        """Canonical composition must not hide the pin under a surviving ring or acute."""
        for composed, decomposed, below, above in (
            ("ị", "i\u0323", "dotbelowcomb", "\u030a"),
            ("į", "i\u0328", "uni0328", "\u0301"),
        ):
            with self.subTest(base=composed):
                for text in (composed + above, decomposed + above):
                    names = [row[0] for row in shape(self.font, text)]
                    self.assertEqual(names[0:2], ["dotlessi", below])
                self.assertEqual(shape(self.font, composed), shape(self.font, decomposed))
                self.assertNotEqual(shape(self.font, composed)[0][0], "dotlessi")

    def test_pin_context_skips_overlay_but_stops_at_the_next_base(self):
        """Filtering can cross intervening marks without removing an unrelated letter's pin."""
        for text in ("i\u0335\u030a", "i\u0323\u0335\u030a"):
            self.assertEqual(shape(self.font, text)[0][0], "dotlessi")
        for text, expected in (("ix\u030a", "i"), ("ịx\u030a", "uni1ECB")):
            self.assertEqual(shape(self.font, text)[0][0], expected)

    def test_capitals_and_alternates_have_their_own_attachment_geometry(self):
        """Capitals rise by the source cap gap; ss01 attachment follows its own optical ink."""
        cap = shape(self.font, "A\u0300")
        self.assertEqual(cap[1][3], 171)
        alternate = shape(self.font, "a\u0300", {"ss01": True})
        default = shape(self.font, "a\u0300")
        self.assertEqual(alternate[0][0], "a.ss01")
        self.assertEqual(alternate[1][2] - default[1][2], 10)

    def test_readback_rejects_dropped_and_wrong_anchors(self):
        """A resealed file with absent or incorrect GPOS must fail strict source readback."""
        check.fails.clear()
        check.check_release_layout(100, self.font, self.weight)
        self.assertEqual(check.fails, [])
        mark = next(lookup for lookup in self.font["GPOS"].table.LookupList.Lookup if lookup.LookupType == 4)
        anchor = mark.SubTable[0].MarkArray.MarkRecord[0].MarkAnchor
        anchor.XCoordinate += 50
        self.assertNotEqual(shape(self.font, "x\u0300")[1][2:], (53, 0))
        check.check_release_layout(100, self.font, self.weight)
        self.assertTrue(any("GPOS layout differs" in failure for failure in check.fails))
        del self.font["GPOS"]
        check.fails.clear()
        check.check_release_layout(100, self.font, self.weight)
        self.assertTrue(any("GPOS layout differs" in failure for failure in check.fails))

    def test_readback_rejects_kern_value_and_lookup_flag_changes(self):
        """Serialization normalization cannot discard effective kerning values or flags."""
        kern = next(lookup for lookup in self.font["GPOS"].table.LookupList.Lookup if lookup.LookupType == 2)
        value = next(
            record.Value1
            for row in kern.SubTable[0].Class1Record
            for record in row.Class2Record
            if record.Value1 and record.Value1.XAdvance
        )
        self.assertEqual(sum(row[1] for row in shape(self.font, "xx")), 950)
        value.XAdvance += 1
        self.assertEqual(sum(row[1] for row in shape(self.font, "xx")), 951)
        check.fails.clear()
        check.check_release_layout(100, self.font, self.weight)
        self.assertTrue(any("GPOS layout differs" in failure for failure in check.fails))
        value.XAdvance -= 1
        kern.LookupFlag = 2  # IgnoreBaseGlyphs: a plausible leaked lookupflag changes actual kerning.
        self.assertEqual(sum(row[1] for row in shape(self.font, "xx")), 980)
        check.fails.clear()
        check.check_release_layout(100, self.font, self.weight)
        self.assertTrue(any("GPOS layout differs" in failure for failure in check.fails))

    @settings(max_examples=40, deadline=None)
    @given(
        st.lists(
            st.sampled_from(["\u0300", "\u0301", "\u031b", "\u0323", "\u0327", "\u0328", "\u0335"]),
            min_size=1,
            max_size=5,
        )
    )
    def test_generated_surviving_clusters_preserve_base_advance(self, marks):
        """Generated interleaved short stacks retain zero mark advance after serialization."""
        got = shape(self.font, "x" + "".join(marks))
        self.assertEqual(sum(row[1] for row in got), 490)
        self.assertTrue(all(row[1] == 0 for row in got[1:]))


if __name__ == "__main__":
    unittest.main()
