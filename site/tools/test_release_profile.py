"""Release admission, serialized web faces and absence of hidden Hangul glyphs."""

import hashlib
import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

import build_ttf as build
import check_ttf as check
from fontTools.ttLib import TTFont
from test_web_subsets import fixture


class ReleaseProfileContracts(unittest.TestCase):
    """The public release preserves every non-Hangul character and rejects incomplete input."""

    def test_version_is_one_only_for_release_and_logo_is_refused(self):
        """Selecting the release is explicit, versioned, and incompatible with the trademark logo."""
        script = "import build_ttf; print(build_ttf.VERSION)"
        env = {**os.environ, "LIMN_TTF_PROFILE": "latin-symbols", "LIMN_TTF_LOGO": "0"}
        run = subprocess.run([sys.executable, "-c", script], env=env, capture_output=True, text=True)
        self.assertEqual(run.returncode, 0, run.stderr)
        self.assertEqual(float(run.stdout.strip()), 1.002)
        for profile, logo in (("latin-symbols", "1"), ("typo", "0")):
            run = subprocess.run(
                [sys.executable, "-c", script],
                env={**env, "LIMN_TTF_PROFILE": profile, "LIMN_TTF_LOGO": logo},
                capture_output=True,
                text=True,
            )
            self.assertNotEqual(run.returncode, 0)
        run = subprocess.run(
            [sys.executable, "-c", script], env={**env, "LIMN_TTF_PROFILE": "full"}, capture_output=True, text=True
        )
        self.assertLess(float(run.stdout.strip()), 1.0)

    def test_admission_preserves_symbols_and_space_and_strips_all_hangul(self):
        """All approved characters survive even when every excluded Hangul block is supplied."""
        latin = {"glyphs": {chr(cp): {} for cp in build.RELEASE_LATIN}, "spaces": {}}
        excluded = "가림가ㄱㆍꥠힰﾡ〮㈀㉠"
        latin["glyphs"].update({ch: {} for ch in excluded})
        symbols = {"glyphs": {ch: {} for ch in build.RELEASE_SYMBOLS + excluded}, "spaces": {"\u3000": 819}}
        W, H = build.release_data(latin, symbols)
        self.assertEqual(set(W["glyphs"]), {chr(cp) for cp in build.RELEASE_LATIN})
        self.assertEqual(set(H["glyphs"]), set(build.RELEASE_SYMBOLS))
        self.assertEqual(build.space_table(W, H)["\u3000"], 819)
        self.assertEqual(len(set(H["glyphs"]) - set(W["glyphs"])), 54)
        for missing in ("A", "ₑ", "Ω", "←"):
            damaged = {**latin, "glyphs": {ch: g for ch, g in latin["glyphs"].items() if ch != missing}}
            with self.assertRaisesRegex(ValueError, "coverage"):
                build.release_data(damaged, symbols)
        for missing in build.RELEASE_SYMBOLS:
            damaged = {**symbols, "glyphs": {ch: g for ch, g in symbols["glyphs"].items() if ch != missing}}
            with self.assertRaisesRegex(ValueError, "coverage"):
                build.release_data(latin, damaged)
        with self.assertRaisesRegex(ValueError, "3000"):
            build.release_data(latin, {**symbols, "spaces": {}})

    def test_space_authority_requires_all_nine_original_advances(self):
        """Missing or changed U+3000 provenance cannot silently change the frozen release width."""
        with tempfile.TemporaryDirectory() as temp:
            path = Path(temp) / "spaces.json"
            authority = {
                str(w): {"char": "\u3000", "source_glyph": "가", "advance": 819.0} for w in range(100, 1000, 100)
            }
            path.write_text(json.dumps(authority))
            self.assertEqual(build.space_provenance(path), authority)
            for damaged in ({"400": authority["400"]}, {**authority, "900": {**authority["900"], "advance": 820}}):
                path.write_text(json.dumps(damaged))
                with self.assertRaisesRegex(ValueError, "3000"):
                    build.space_provenance(path)

    def test_package_manifest_and_checksums_bind_exact_portable_files(self):
        """The package rejects stale extra faces and metadata/byte changes after checksumming."""
        with tempfile.TemporaryDirectory() as temp:
            inputs = Path(temp) / "inputs"
            inputs.mkdir()
            play, provenance = inputs / "play.js", inputs / "spaces.json"
            play.write_text("producer bytes")
            provenance.write_text(
                json.dumps({str(w): {"char": "\u3000", "advance": 819, "source_glyph": "가"} for w in build.WEIGHTS})
            )
            for w in build.WEIGHTS:
                (inputs / f"limn-hangul-{w}.js").write_text(f"symbol producer {w}")
            out = Path(temp) / "package"
            out.mkdir()
            records = []
            for w, style in build.WEIGHTS.items():
                record = {"w": w}
                for ext in ("ttf", "woff2"):
                    name = f"LimnSans-{style}.{ext}"
                    (out / name).write_bytes(b"font readback is checked separately")
                    record.update({ext: name, ext + "Bytes": (out / name).stat().st_size})
                records.append(record)
            meta = {
                "profile": "latin-symbols",
                "version": f"{build.RELEASE_VERSION:.3f}",
                "hinted": True,
                "codepoints": sorted(build.RELEASE_COVERAGE),
                "files": records,
                "inputs": {
                    "playSHA256": hashlib.sha256(play.read_bytes()).hexdigest(),
                    "spaceProvenanceSHA256": hashlib.sha256(provenance.read_bytes()).hexdigest(),
                    "supplementalSHA256": {
                        f"limn-hangul-{w}.js": hashlib.sha256((inputs / f"limn-hangul-{w}.js").read_bytes()).hexdigest()
                        for w in build.WEIGHTS
                    },
                },
            }
            for name in (
                "fonts.css",
                "fonts.js",
                "README.md",
                "OFL.txt",
                "OFL-Quicksand.txt",
                "OFL-NanumSquareRound.txt",
            ):
                (out / name).write_text("package fixture")
            (out / "fonts.json").write_text(json.dumps(meta))
            (out / "fonts.js").write_text("window.LIMN_FONT_FILES=" + json.dumps(meta) + ";")
            (out / "SHA256SUMS").write_text(
                "\n".join(f"{hashlib.sha256(path.read_bytes()).hexdigest()}  {path.name}" for path in out.iterdir())
            )
            check.fails.clear()
            check.check_release_package(out, play_in=play, symbols_in=inputs, space_in=provenance)
            self.assertEqual(check.fails, [])
            original_js = (out / "fonts.js").read_text()
            (out / "fonts.js").write_text('window.LIMN_FONT_FILES={"files":[]};')
            check.fails.clear()
            check.check_release_package(out, play_in=play, symbols_in=inputs, space_in=provenance)
            self.assertTrue(any("JavaScript manifest" in failure for failure in check.fails))
            (out / "fonts.js").write_text(original_js)
            (out / "fonts.json").write_text(json.dumps({**meta, "version": "0.100"}))
            check.fails.clear()
            check.check_release_package(out, play_in=play, symbols_in=inputs, space_in=provenance)
            self.assertTrue(any("version" in failure for failure in check.fails))
            self.assertTrue(any("SHA256" in failure for failure in check.fails))
            (out / "stale-ext.woff2").write_bytes(b"stale")
            check.fails.clear()
            check.check_release_package(out, play_in=play, symbols_in=inputs, space_in=provenance)
            self.assertTrue(any("inventory" in failure for failure in check.fails))

    def test_input_hashes_bind_every_configured_file_and_exact_manifest_shape(self):
        """Every one of eleven producer identities is required, including all nine symbol weights."""
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            play, provenance = root / "play.js", root / "spaces.json"
            play.write_text("producer bytes")
            provenance.write_text(
                json.dumps({str(w): {"char": "\u3000", "advance": 819, "source_glyph": "가"} for w in build.WEIGHTS})
            )
            symbols = {}
            for w in build.WEIGHTS:
                path = root / f"limn-hangul-{w}.js"
                path.write_text(f"symbol producer {w}")
                symbols[path.name] = hashlib.sha256(path.read_bytes()).hexdigest()
            identities = {
                "playSHA256": hashlib.sha256(play.read_bytes()).hexdigest(),
                "spaceProvenanceSHA256": hashlib.sha256(provenance.read_bytes()).hexdigest(),
                "supplementalSHA256": symbols,
            }
            check.fails.clear()
            check.check_release_inputs({"inputs": identities}, play, root, provenance)
            self.assertEqual(check.fails, [])
            # Exhaust every recorded identity, both stale digests and absent records; metadata checksums
            # cannot substitute for comparing the actual configured producer bytes.
            for key in ("playSHA256", "spaceProvenanceSHA256", *symbols):
                for missing in (False, True):
                    with self.subTest(identity=key, missing=missing):
                        damaged = json.loads(json.dumps(identities))
                        record = damaged["supplementalSHA256"] if key in symbols else damaged
                        if missing:
                            del record[key]
                        else:
                            record[key] = "0" * 64
                        check.fails.clear()
                        check.check_release_inputs({"inputs": damaged}, play, root, provenance)
                        self.assertTrue(any("input identities" in failure for failure in check.fails))
            for damaged in (
                None,
                {**identities, "extra": "0" * 64},
                {**identities, "supplementalSHA256": {**symbols, "extra.js": "0" * 64}},
            ):
                check.fails.clear()
                check.check_release_inputs({"inputs": damaged}, play, root, provenance)
                self.assertTrue(any("input identities" in failure for failure in check.fails))

    def test_every_hangul_block_is_excluded_and_other_symbols_are_retained(self):
        """Generated Unicode probes cover the full exclusion boundary, including halfwidth jamo."""
        for a, b in ((0x1100, 0x11FF), (0x3130, 0x318F), (0xA960, 0xA97F), (0xAC00, 0xD7FF), (0xFFA0, 0xFFDC)):
            for cp in range(a, b + 1):
                self.assertTrue(build.is_hangul(cp), hex(cp))
        for cp in (0x3000, 0x3001, 0x33A1, 0xFFE6, 0x20A9, 0x1F600):
            self.assertFalse(build.is_hangul(cp), hex(cp))

    def test_web_release_uses_one_face_and_keeps_final_hinted_tables(self):
        """An admitted font has a portable whole-font web face, with exact final SFNT table identity."""
        with tempfile.TemporaryDirectory() as temp:
            out = Path(temp)
            ttf = out / "LimnSans-Regular.ttf"
            fixture(ttf)
            # Use real subset machinery to create a small non-Hangul source with layout alternates.
            from fontTools import subset

            with TTFont(ttf) as font:
                options = subset.Options()
                options.layout_features = ["pnum", "tnum", "zero", "ss01", "kern"]
                options.glyph_names = True
                cutter = subset.Subsetter(options=options)
                cutter.populate(unicodes=[32, 48, 97, 0x1F600])
                cutter.subset(font)
                font.save(ttf)
            meta, css = build.write_release_web(ttf, 400, out)
            (out / "fonts.css").write_text(css)
            self.assertEqual(set(meta), {"latin-symbols"})
            self.assertEqual(len(list(out.glob("*.woff2"))), 1)
            with TTFont(ttf) as full:
                check.fails.clear()
                check.check_release_web(400, full, out)
                self.assertEqual(check.fails, [])
            with TTFont(out / "LimnSans-Regular.woff2") as web:
                web["cvt "].values[0] += 1
                web.save(out / "LimnSans-Regular.woff2")
            with TTFont(ttf) as full:
                check.fails.clear()
                check.check_release_web(400, full, out)
                self.assertTrue(any("cvt" in failure for failure in check.fails), check.fails)

    def test_real_audit_scope_removes_only_hangul_without_creating_neighbors(self):
        """The release audits the real corpus with separators and leaves bilingual defaults intact."""
        import audit

        self.assertTrue(any(build.is_hangul(ord(c)) for line in audit.proof_corpus() for c in line))
        release = audit.proof_corpus("latin-symbols")
        self.assertFalse(any(build.is_hangul(ord(c)) for line in release for c in line))
        self.assertTrue(any("Sphinx" in line for line in release))
        self.assertFalse(any(build.is_hangul(ord(c)) for pair in audit.pair_corpus("latin-symbols") for c in pair))
        self.assertIn("AV", audit.pair_corpus("latin-symbols"))

    def test_hidden_hangul_gsub_target_is_rejected(self):
        """Removing only cmap entries cannot certify a font retaining unencoded Hangul/logo outlines."""
        with tempfile.TemporaryDirectory() as temp:
            path = Path(temp) / "font.ttf"
            fixture(path)
            with TTFont(path) as font:
                for table in font["cmap"].tables:
                    if table.isUnicode():
                        table.cmap = {cp: gn for cp, gn in table.cmap.items() if not build.is_hangul(cp)}
                check.fails.clear()
                check.check_release_glyphs(
                    400, font, {".notdef", "space", "a", "a.ss01", "zero", "zero.pnum", "zero.zero"}
                )
                self.assertTrue(any("glyph" in failure for failure in check.fails), check.fails)


if __name__ == "__main__":
    unittest.main()
