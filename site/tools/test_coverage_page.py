"""Coverage reports use real font cmaps and reject stale or ambiguous local inputs."""

import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from build_coverage_page import _json_object, coverage
from fontTools.fontBuilder import FontBuilder
from fontTools.pens.ttGlyphPen import TTGlyphPen
from hypothesis import example, given
from hypothesis import strategies as st

SCRIPT = Path(__file__).with_name("build_coverage_page.py")
POINTS = {32, 48, 65, 0x391, 0x410, 0x1100, 0xAC00, 0x2014, 0x2192}
EXPECTED = {
    "total": 9,
    "hangul": 1,
    "jamo": 1,
    "latin": 1,
    "greek": 1,
    "cyrillic": 1,
    "digits": 1,
    "punctuation": 1,
    "spaces": 1,
    "symbols": 1,
}


def write_font(path, points):
    """Serialize a minimal valid TTF whose cmap is the supplied observable fixture."""
    font = FontBuilder(1000, isTTF=True)
    order = [".notdef", "fixture"]
    font.setupGlyphOrder(order)
    font.setupCharacterMap({cp: "fixture" for cp in points})
    pen = TTGlyphPen(None)
    pen.moveTo((40, 0))
    pen.lineTo((40, 600))
    pen.lineTo((300, 600))
    pen.lineTo((300, 0))
    pen.closePath()
    font.setupGlyf({".notdef": TTGlyphPen(None).glyph(), "fixture": pen.glyph()})
    font.setupHorizontalMetrics({name: (500, 40) for name in order})
    font.setupHorizontalHeader(ascent=800, descent=-200)
    font.setupNameTable({"familyName": "Coverage Fixture", "styleName": "Regular"})
    font.setupOS2(sTypoAscender=800, sTypoDescender=-200, usWinAscent=800, usWinDescent=200)
    font.setupPost()
    font.save(path)


class CoveragePageContracts(unittest.TestCase):
    """The lightweight CLI must prove coverage without a full glyph or figures build."""

    def setUp(self):
        """Use nine real serialized weights and three independently readable references."""
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name)
        self.fonts = self.root / "fonts"
        self.refs = self.root / "refs"
        self.fonts.mkdir()
        self.refs.mkdir()
        self.metadata = {
            "family": "Limn Sans",
            "version": "0.100",
            "rev": "fixture",
            "files": [{"w": weight, "ttf": f"fonts/{weight}.ttf"} for weight in range(100, 901, 100)],
        }
        for entry in self.metadata["files"]:
            write_font(self.root / entry["ttf"], POINTS)
        for name in ("Inter.ttf", "Pretendard-Regular.ttf", "NotoSansKR.ttf"):
            write_font(self.refs / name, POINTS | {0x221E})
        self.write_metadata()

    def write_metadata(self):
        """Keep metadata edits observable through the same JS boundary as make fonts."""
        (self.fonts / "fonts.js").write_text(
            "/* fixture */\nwindow.LIMN_FONT_FILES=" + json.dumps(self.metadata) + ";\n"
        )

    def run_report(self, *arguments):
        """Run the actual command in a subprocess, retaining its public result and errors."""
        return subprocess.run(
            [
                sys.executable,
                str(SCRIPT),
                "--fonts",
                str(self.fonts),
                "--refs",
                str(self.refs),
                "--report-only",
                *arguments,
            ],
            text=True,
            capture_output=True,
            check=False,
        )

    def test_report_reconciles_real_cmaps_and_every_partition(self):
        """Every category and Unicode block must sum to the distinct cmap total."""
        result = self.run_report()
        self.assertEqual(result.returncode, 0, result.stderr)
        report = json.loads(result.stdout)
        self.assertEqual(report["coverage"], EXPECTED)
        self.assertEqual(sum(row["counts"][0] for row in report["blocks"]), 9)
        self.assertEqual(report["weights"], list(range(100, 901, 100)))
        self.assertEqual([font["total"] for font in report["fonts"]], [9, 10, 10, 10])
        self.assertEqual(report["manifest"], {"status": "absent"})

    def test_changed_weight_cmap_is_rejected(self):
        """A single weight cannot silently shrink the advertised intersection."""
        write_font(self.fonts / "900.ttf", POINTS - {0xAC00})
        result = self.run_report()
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("weights' cmaps differ", result.stderr)

    def test_missing_reference_is_rejected(self):
        """A missing comparator must fail instead of substituting a system font."""
        (self.refs / "Inter.ttf").unlink()
        result = self.run_report()
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("Inter.ttf", result.stderr)

    def test_manifest_agrees_or_fails_for_stale_counts(self):
        """An existing figures manifest must agree even when the total still matches."""
        manifest = self.root / "manifest.json"
        manifest.write_text(json.dumps({"coverage": EXPECTED}))
        result = self.run_report("--manifest", str(manifest))
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(json.loads(result.stdout)["manifest"]["status"], "matched")
        changed = {**EXPECTED, "latin": 0, "symbols": 2}
        manifest.write_text(json.dumps({"coverage": changed}))
        result = self.run_report("--manifest", str(manifest))
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("manifest coverage mismatch", result.stderr)

    def test_explicit_missing_manifest_is_rejected(self):
        """A requested manifest check cannot silently become an unchecked report."""
        result = self.run_report("--manifest", str(self.root / "missing.json"))
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("manifest", result.stderr)

    def test_font_metadata_cannot_escape_its_directory(self):
        """Metadata cannot read a font outside the chosen fonts directory."""
        self.metadata["files"][0]["ttf"] = "fonts/../refs/Inter.ttf"
        self.write_metadata()
        result = self.run_report()
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("font path", result.stderr)

    def test_duplicate_metadata_weight_is_rejected(self):
        """Duplicate weights cannot hide a missing member of the nine-weight family."""
        self.metadata["files"][-1]["w"] = 400
        self.write_metadata()
        result = self.run_report()
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("100–900", result.stderr)

    def test_same_count_manifest_from_another_revision_is_rejected(self):
        """Count equality alone cannot certify a manifest identifying a different font build."""
        manifest = self.root / "manifest.json"
        manifest.write_text(json.dumps({"coverage": EXPECTED, "fonts": {"rev": "other-build"}}))
        result = self.run_report("--manifest", str(manifest))
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("stale manifest font rev", result.stderr)

    def test_duplicate_json_key_is_rejected(self):
        """Ambiguous metadata must fail at the parser boundary."""
        source = (self.fonts / "fonts.js").read_text()
        (self.fonts / "fonts.js").write_text(source.replace('"rev": "fixture"', '"rev": "fixture", "rev": "other"'))
        result = self.run_report()
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("duplicate JSON key", result.stderr)

    def test_empty_font_cmap_is_rejected(self):
        """A font with no Unicode mappings cannot masquerade as a working comparator."""
        write_font(self.refs / "Inter.ttf", set())
        result = self.run_report()
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("empty or invalid Unicode cmap", result.stderr)

    def test_default_manifest_is_checked_when_present(self):
        """Independent page regeneration must reject a stale figures manifest next to its inputs."""
        figures = self.root / "figures"
        figures.mkdir()
        (figures / "manifest.json").write_text(json.dumps({"coverage": {**EXPECTED, "total": 8}}))
        result = self.run_report()
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("manifest coverage mismatch", result.stderr)

    def test_symlink_cannot_escape_reference_root(self):
        """A local reference filename must not indirectly read an unrelated selected directory."""
        (self.refs / "Inter.ttf").unlink()
        (self.refs / "Inter.ttf").symlink_to(self.fonts / "400.ttf")
        result = self.run_report()
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("reference font path escapes refs", result.stderr)

    def test_excessive_metadata_nesting_is_rejected_cleanly(self):
        """Deeply nested input must produce a boundary error instead of a Python traceback."""
        (self.fonts / "fonts.js").write_text('window.LIMN_FONT_FILES={"files":' + "[" * 2000 + "0" + "]" * 2000 + "};")
        result = self.run_report()
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("JSON nesting exceeds", result.stderr)
        self.assertNotIn("Traceback", result.stderr)


class CoveragePartitionProperties(unittest.TestCase):
    """Generated scalar sets pin the requested disjoint, exhaustive partition invariant."""

    @given(st.sets(st.characters(exclude_categories=("Cs",)).map(ord), max_size=100))
    def test_every_scalar_belongs_to_exactly_one_category(self, points):
        """For arbitrary valid cmaps, category counts conserve the number of distinct code points."""
        counts = coverage(frozenset(points))
        self.assertEqual(counts["total"], len(points))
        self.assertEqual(sum(value for key, value in counts.items() if key != "total"), len(points))
        self.assertTrue(all(value >= 0 for value in counts.values()))

    @given(
        st.dictionaries(
            st.text(max_size=30), st.one_of(st.none(), st.booleans(), st.integers(), st.text(max_size=100)), max_size=15
        )
    )
    @example({"quoted brackets": "[" * 100 + '"\\'})
    def test_metadata_objects_round_trip_without_treating_strings_as_nesting(self, metadata):
        """Generated metadata values and escaped strings survive the bounded JSON parser unchanged."""
        encoded = json.dumps(metadata)
        self.assertEqual(_json_object(encoded, Path("fixture.json")), metadata)


if __name__ == "__main__":
    unittest.main()
