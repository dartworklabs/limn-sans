"""Exercise release checker CLI against a real admitted package, including resealed corruptions.

Set LIMN_RELEASE_TEST_PACKAGE and the three LIMN_TTF_*_IN hooks to run the opt-in
release acceptance checks. LIMN_RELEASE_TEST_LOGS preserves raw checker output.
"""

import hashlib
import json
import os
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from fontTools.ttLib import TTFont


@unittest.skipUnless(os.environ.get("LIMN_RELEASE_TEST_PACKAGE"), "requires an admitted release package and inputs")
class ReleaseReadbackAcceptance(unittest.TestCase):
    """Checksums and matching TTF/WOFF2 cannot hide incorrect source or cmap identity."""

    def setUp(self):
        """Copy one package per test, preserving the admitted original and cleaning all variants."""
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.work = Path(temporary.name)
        self.package = self.work / "fonts"
        shutil.copytree(os.environ["LIMN_RELEASE_TEST_PACKAGE"], self.package)
        self.env = {
            **os.environ,
            "LIMN_TTF_PROFILE": "latin-symbols",
            "LIMN_TTF_LOGO": "0",
            "LIMN_TTF_HINT": "1",
            "LIMN_TTF_OUT": str(self.package),
        }

    def run_checker(self, label):
        """Run the actual checker entry point; optionally retain its output outside the temporary copy."""
        result = subprocess.run(
            [sys.executable, str(Path(__file__).with_name("check_ttf.py"))],
            env=self.env,
            capture_output=True,
            text=True,
        )
        if destination := os.environ.get("LIMN_RELEASE_TEST_LOGS"):
            logs = Path(destination)
            logs.mkdir(parents=True, exist_ok=True)
            (logs / f"{label}.log").write_text(result.stdout + result.stderr, encoding="utf-8")
            for filename in ("fonts.json", "fonts.js", "SHA256SUMS"):
                shutil.copyfile(self.package / filename, logs / f"{label}-{filename}")
        return result

    def reseal(self, meta=None):
        """Refresh both portable manifests, sizes and every checksum after an adversarial change."""
        meta = meta or json.loads((self.package / "fonts.json").read_text())
        for record in meta["files"]:
            for ext in ("ttf", "woff2"):
                record[ext + "Bytes"] = (self.package / record[ext]).stat().st_size
        (self.package / "fonts.json").write_text(json.dumps(meta, ensure_ascii=False, indent=2) + "\n")
        (self.package / "fonts.js").write_text("window.LIMN_FONT_FILES=" + json.dumps(meta, ensure_ascii=False) + ";\n")
        (self.package / "SHA256SUMS").write_text(
            "".join(
                f"{hashlib.sha256(path.read_bytes()).hexdigest()}  {path.name}\n"
                for path in sorted(self.package.iterdir())
                if path.name != "SHA256SUMS"
            )
        )

    def replace_play_outline(self):
        """Keep advances intact while changing Regular A to B in a newly configured producer file."""
        text = Path(self.env["LIMN_TTF_PLAY_IN"]).read_text()
        marker = "window.LIMN_PLAY="
        prefix, data = text.split(marker, 1)
        play = json.loads(data[: data.rindex(";")])
        play["400"]["glyphs"]["A"]["d"] = play["400"]["glyphs"]["B"]["d"]
        path = self.work / "changed-play.js"
        path.write_text(prefix + marker + json.dumps(play, ensure_ascii=False) + ";\n")
        self.env["LIMN_TTF_PLAY_IN"] = str(path)
        return hashlib.sha256(path.read_bytes()).hexdigest()

    def test_admitted_nine_weight_package_passes(self):
        """The unmodified actual package passes all strict release checks."""
        result = self.run_checker("baseline")
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)

    def test_changed_configured_input_is_rejected(self):
        """F1: changed geometry must fail even when its advance matches the recorded producer."""
        self.replace_play_outline()
        result = self.run_checker("wrong-input")
        self.assertEqual(result.returncode, 1, result.stdout + result.stderr)
        self.assertIn("manifest input identities differ", result.stdout)

    def test_resigned_input_metadata_cannot_hide_source_geometry_change(self):
        """Rehashing a changed source cannot certify an old font whose outline no longer matches."""
        digest = self.replace_play_outline()
        meta = json.loads((self.package / "fonts.json").read_text())
        meta["inputs"]["playSHA256"] = digest
        self.reseal(meta)
        result = self.run_checker("resigned-input")
        self.assertEqual(result.returncode, 1, result.stdout + result.stderr)
        self.assertIn("release source A outline", result.stdout)

    def test_resealed_cmap_swap_is_rejected(self):
        """F2: same-advance circle glyphs cannot be exchanged in both formats and rechecksummed."""
        path = self.package / "LimnSans-Regular.ttf"
        with TTFont(path, recalcTimestamp=False) as font:
            original = dict(font.getBestCmap())
            for table in font["cmap"].tables:
                if table.isUnicode():
                    table.cmap = {**table.cmap, 0x25CB: original[0x25CF], 0x25CF: original[0x25CB]}
            font.save(path)
        with TTFont(path, recalcTimestamp=False) as font:
            self.assertEqual(font.getBestCmap()[0x25CB], original[0x25CF])
            self.assertEqual(font.getBestCmap()[0x25CF], original[0x25CB])
            font.flavor = "woff2"
            font.save(path.with_suffix(".woff2"))
        self.reseal()
        result = self.run_checker("wrong-cmap")
        self.assertEqual(result.returncode, 1, result.stdout + result.stderr)
        self.assertIn("release source cmap", result.stdout)

    def test_resealed_encoded_alternate_and_metric_changes_are_rejected(self):
        """Source identity covers encoded outlines, unencoded feature alternates and both metrics."""
        path = self.package / "LimnSans-Regular.ttf"
        with TTFont(path, recalcTimestamp=False) as font:
            circle = font.getBestCmap()[0x25CB]
            for name in (circle, "a.ss01"):
                glyph = font["glyf"][name]
                glyph.coordinates[0] = (glyph.coordinates[0][0] + 1, glyph.coordinates[0][1])
            advance, lsb = font["hmtx"]["zero.pnum"]
            font["hmtx"]["zero.pnum"] = (advance + 1, lsb + 1)
            font.save(path)
        with TTFont(path, recalcTimestamp=False) as font:
            font.flavor = "woff2"
            font.save(path.with_suffix(".woff2"))
        self.reseal()
        result = self.run_checker("wrong-glyphs")
        self.assertEqual(result.returncode, 1, result.stdout + result.stderr)
        for failure in (
            f"release source {circle} outline",
            "release source a.ss01 outline",
            "release source zero.pnum metrics",
        ):
            self.assertIn(failure, result.stdout)


if __name__ == "__main__":
    unittest.main()
