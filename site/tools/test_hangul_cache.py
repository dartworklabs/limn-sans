"""Exact identities, bounded records and durable recovery using real local cache files.

The optional real-glyph test runs existing geometry/fitting without test doubles;
LIMN_KO_CACHE_REAL=1 enables it after official parent fonts are fetched.
"""

import ast
import copy
import json
import multiprocessing
import os
import random
import re
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import hangul_cache as C


def sample(ch="가", weights=(100, 900)):
    """Supply a valid family record with explicit float advance and original held order."""
    return C.GlyphRecord(
        {w: {ch: {"d": "M0 0q5 10 10 0l-10 0z", "adv": 815.0, "box": [0, 0, 10, 5]}} for w in weights}, [(100, ch, 1.2)]
    )


def contender(root, start, log):
    """Two independent spawned producers publish one same-key family at most once."""
    cache = C.GlyphCache(Path(root), [100, 900], {}, {})
    start.wait(10)
    with cache.lock("가"):
        if isinstance(cache.read("가"), C.Miss):
            with open(log, "a") as stream:
                stream.write("produced\n")
            cache.store("가", sample())


def interrupted(root):
    """Exit after publishing one glyph while holding its lock, simulating an interrupted build."""
    cache = C.GlyphCache(Path(root), [100, 900], {}, {})
    with cache.lock("가"):
        cache.store("가", sample())
        os._exit(17)


class GlyphCacheTests(unittest.TestCase):
    """Record behavior depends only on exact inputs, and malformed state is disposable."""

    def setUp(self):
        """Give every test a real isolated cache with a frozen family identity."""
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name) / "records"
        self.weights = [100, 900]
        self.params = {100: {"S": 39.5, "m": 0}, 900: {"S": 155.0, "m": 3}}
        self.inputs = {
            "code": "producer",
            "fonts": ["L", "R", "B", "EB"],
            "latin": "source",
            "dependencies": "installed",
            "environment": {},
        }
        self.cache = C.GlyphCache(self.root, self.weights, self.params, self.inputs)

    def test_every_authoritative_input_and_weight_order_separates_keys(self):
        """Changing each determinant, including weight sequence and full params, causes a miss."""
        key = self.cache.key("가")
        self.assertNotEqual(key, self.cache.key("갂"))
        self.assertNotEqual(key, C.GlyphCache(self.root, self.weights[::-1], self.params, self.inputs).key("가"))
        self.assertNotEqual(key, C.GlyphCache(self.root, [100], self.params, self.inputs).key("가"))
        for weight in self.params:
            for field in self.params[weight]:
                params = copy.deepcopy(self.params)
                params[weight][field] += 0.01
                self.assertNotEqual(key, C.GlyphCache(self.root, self.weights, params, self.inputs).key("가"))
        for field in self.inputs:
            inputs = copy.deepcopy(self.inputs)
            inputs[field] = "changed"
            self.assertNotEqual(key, C.GlyphCache(self.root, self.weights, self.params, inputs).key("가"))

    def test_record_round_trip_preserves_property_order_numeric_types_and_held(self):
        """Hits serialize byte-for-byte like their cold producer, even when stored object keys reorder."""
        record = sample()
        self.assertIsInstance(self.cache.read("가"), C.Miss)
        self.cache.store("가", record)
        path = self.root / (self.cache.key("가") + ".json")
        raw = json.loads(path.read_text())
        path.write_text(json.dumps(raw, sort_keys=True))
        loaded = self.cache.read("가")
        self.assertEqual(loaded, record)
        self.assertEqual(json.dumps(loaded.glyphs, ensure_ascii=False), json.dumps(record.glyphs, ensure_ascii=False))
        self.assertIs(type(loaded.glyphs[100]["가"]["adv"]), float)
        rng = random.Random(22019)
        for i in range(24):
            ch = chr(0xAC00 + i)
            generated = sample(ch)
            for glyphs in generated.glyphs.values():
                glyph = glyphs[ch]
                glyph["adv"] = rng.uniform(100, 1000)
                x, y = rng.randrange(-500, 500), rng.randrange(-500, 500)
                glyph["d"] = f"M{x} {y}q5 10 10 0l-10 0z"
                glyph["box"] = [x, y, x + 10, y + 5]
            self.cache.store(ch, generated)
            restored = self.cache.read(ch)
            self.assertEqual(json.dumps(generated.glyphs), json.dumps(restored.glyphs))
            self.assertEqual(generated.held, restored.held)

    def test_partial_bad_checksum_bad_schema_and_bad_svg_are_misses(self):
        """Neither truncated publication nor internally inconsistent cache bytes reach generated JS."""
        self.cache.store("가", sample())
        path = self.root / (self.cache.key("가") + ".json")
        original = path.read_bytes()
        for raw in (
            b"{",
            original[: len(original) // 2],
            b'{"key":1,"key":2}',
            b"[" * 30 + b"]" * 30,
            b"NaN",
            b"1e999",
            b"x" * (C.MAX_BYTES + 1),
        ):
            path.write_bytes(raw)
            self.assertIsInstance(self.cache.read("가"), C.Miss)
        for mutation in ("checksum", "weight", "glyph", "held", "svg"):
            row = json.loads(original)
            if mutation == "checksum":
                row["glyphs"][0]["adv"] += 1
            else:
                row.pop("sha256")
                if mutation == "weight":
                    row["weights"].reverse()
                elif mutation == "glyph":
                    row["glyphs"].pop()
                elif mutation == "held":
                    row["held"][0][1] = "갂"
                else:
                    row["glyphs"][0]["d"] = "M0 0q1z"
                row["sha256"] = C.identity(row)
            path.write_text(json.dumps(row))
            self.assertIsInstance(self.cache.read("가"), C.Miss, mutation)

    def test_arbitrary_bounded_bytes_are_hits_or_misses_without_parser_crashes(self):
        """Seeded fuzzing covers the local JSON boundary and never returns partially parsed glyphs."""
        rng = random.Random(22018)
        path = self.root / (self.cache.key("가") + ".json")
        for _ in range(200):
            path.write_bytes(rng.randbytes(rng.randrange(2048)))
            self.assertIsInstance(self.cache.read("가"), C.Miss)

    def test_symlink_entry_is_a_miss_and_atomic_write_leaves_target_untouched(self):
        """A local stale/malicious cache symlink cannot redirect a cache read or publication."""
        self.cache.store("가", sample())
        path = self.root / (self.cache.key("가") + ".json")
        original = path.read_bytes()
        path.unlink()
        target = Path(self.temp.name) / "outside"
        target.write_bytes(original)
        path.symlink_to(target)
        self.assertIsInstance(self.cache.read("가"), C.Miss)
        self.cache.store("가", sample())
        self.assertEqual(target.read_bytes(), original)
        self.assertIsInstance(self.cache.read("가"), C.GlyphRecord)
        with self.assertRaises(ValueError):
            self.cache.key("../outside")

    def test_concurrent_misses_publish_once(self):
        """Real spawned processes coalesce a same-key miss under the retained POSIX lock."""
        ctx = multiprocessing.get_context("spawn")
        start = ctx.Event()
        log = Path(self.temp.name) / "produced.log"
        processes = [ctx.Process(target=contender, args=(str(self.root), start, str(log))) for _ in range(2)]
        for process in processes:
            process.start()
        start.set()
        for process in processes:
            process.join(15)
            if process.is_alive():
                process.kill()
                process.join()
            self.assertEqual(process.exitcode, 0)
        self.assertEqual(log.read_text(), "produced\n")

    def test_interruption_preserves_completed_glyph_and_releases_lock(self):
        """A fresh process can resume from completed records after a producer exits inside its lock."""
        process = multiprocessing.get_context("spawn").Process(target=interrupted, args=(str(self.root),))
        process.start()
        process.join(15)
        self.assertEqual(process.exitcode, 17)
        resumed = C.GlyphCache(self.root, [100, 900], {}, {})
        with resumed.lock("가"):
            self.assertEqual(resumed.read("가"), sample())
        self.assertIsInstance(resumed.read("갂"), C.Miss)

    def test_disabled_cache_bypasses_glyph_and_smoothing_reads_and_writes(self):
        """The cold switch leaves real cache files untouched and preserves the smoothing algorithm."""
        import build_hangul as B
        import hangul as H

        self.cache.store("가", sample())
        before = {p.name: p.read_bytes() for p in self.root.iterdir()}
        params = Path(self.temp.name) / ".params-cache.json"
        params.write_text('{"old":"keep"}')

        def solve_map(function, values):
            """Supply solved corpus boundaries to exercise cache I/O without a full corpus solve."""
            if function is H._raw_ink:
                return [(w, 40.0 + w / 10, 10000.0 + w) for w in values]
            return [(w, stroke) for w, _, stroke in values]

        produced = ({100: {"가": {"d": "M0 0l1 1z", "adv": 1.0, "box": [0, 0, 1, 1]}}}, {100: []}, [])
        with (
            patch.dict(os.environ, {"LIMN_KO_CACHE": "0"}),
            patch.object(H, "FDIR", Path(self.temp.name)),
            patch.object(H, "_SMOOTH_TARGETS", None),
            patch.object(B, "_GLYPH_CACHE", self.cache),
            patch.object(B, "_one", return_value=produced),
        ):
            self.assertTrue(H.SMOOTH_INK)
            self.assertEqual(H._cache()[1], {})
            self.assertEqual(B._cached_one(([100], "가")), (*produced, False))
            self.assertEqual(len(H.smooth_solve(solve_map)), 9)
        self.assertEqual(params.read_text(), '{"old":"keep"}')
        self.assertEqual(before, {p.name: p.read_bytes() for p in self.root.iterdir()})

    def test_reported_failed_fit_is_not_published(self):
        """A producer failure marker cannot become a later successful cache hit."""
        import build_hangul as B

        failed = (sample().glyphs, {100: ["가"], 900: []}, [])
        with patch.object(B, "_GLYPH_CACHE", self.cache), patch.object(B, "_one", return_value=failed):
            self.assertEqual(B._cached_one((self.weights, "가")), (*failed, False))
        self.assertIsInstance(self.cache.read("가"), C.Miss)

    def test_fingerprint_tracks_actual_producer_font_latin_bytes_and_rule_environment(self):
        """The build identity invalidates on actual files; output/progress controls do not change glyphs."""
        tools = Path(self.temp.name) / "tools"
        (tools / "hangul").mkdir(parents=True)
        files = [
            tools / name
            for name in (
                "hangul.py",
                "build_hangul.py",
                "audit_hangul.py",
                "weights.py",
                "ofl_header.py",
                "hangul_cache.py",
            )
        ]
        files += [tools / "hangul" / f"NanumSquareRound{master}.ttf" for master in ("L", "R", "B", "EB")]
        files += [tools.parent / "limn-font-play.js"]
        for path in files:
            path.write_bytes(b"original")
        before = C.fingerprint(tools)
        for path in files:
            path.write_bytes(b"changed")
            self.assertNotEqual(before, C.fingerprint(tools), path.name)
            path.write_bytes(b"original")
        with patch.dict(os.environ, {"LIMN_KO_CONTRAST": "0.91"}):
            self.assertNotEqual(before, C.fingerprint(tools))
        with patch.dict(os.environ, {"LIMN_KO_OUT": "/tmp/elsewhere", "LIMN_PROCS": "8", "LIMN_KO_CHARS": "가"}):
            self.assertEqual(before, C.fingerprint(tools))

    def test_changed_build_inputs_can_discard_only_their_family(self):
        """Discarding detected mutable inputs cannot remove records from another content identity."""
        self.cache.store("가", sample())
        other = C.GlyphCache(self.root, self.weights, {}, {})
        other.store("가", sample())
        self.cache.discard(["가", "갂"])
        self.assertIsInstance(self.cache.read("가"), C.Miss)
        self.assertEqual(other.read("가"), sample())

    def test_fingerprint_keeps_all_actual_rule_inputs_and_ignores_latin_invocation_controls(self):
        """Per-weight output/temp paths cannot repeat a global solve, while every producer rule still invalidates."""
        tools = Path(C.__file__).parent
        before = C.fingerprint(tools)
        rules = {
            node.value
            for name in ("hangul.py", "weights.py")
            for node in ast.walk(ast.parse((tools / name).read_text()))
            if isinstance(node, ast.Constant)
            and isinstance(node.value, str)
            and re.fullmatch(r"LIMN_[A-Z0-9_]+", node.value)
        }
        for name in rules:
            with patch.dict(os.environ, {name: "a-distinct-rule-input"}):
                self.assertNotEqual(before, C.fingerprint(tools), name)
        for w in (100, 900):
            controls = {
                "LIMN_WGHT": str(w),
                "LIMN_PLAY_OUT": f"/tmp/play-{w}",
                "LIMN_PUNCT_DUMP": f"/tmp/punct-{w}",
                "LIMN_FONT_OUT": f"/tmp/font-{w}",
                "LIMN_SPACING_OUT": f"/tmp/spacing-{w}",
                "LIMN_OPT_PX": "16",
                "LIMN_JOBS": "2",
                "LIMN_TIMING": "1",
            }
            with patch.dict(os.environ, controls):
                self.assertEqual(before, C.fingerprint(tools))

    def test_smoothing_cache_requires_complete_finite_targets(self):
        """An automatic params-cache identity cannot turn malformed stroke values into accepted params."""
        import hangul as H

        targets = {str(w): 40.0 + w / 10 for w in H.WEIGHTS}
        path = Path(self.temp.name) / ".params-cache.json"

        def entry(values):
            """Seal a smoothing payload so target-shape rejection is independent of checksum rejection."""
            row = {"targets": values, "raw_ink": targets, "want_ink": targets}
            row["sha256"] = C.identity(row)
            return row

        with patch.object(H, "FDIR", Path(self.temp.name)), patch.dict(os.environ, {"LIMN_KO_CACHE": "1"}):
            key = H._smooth_key()
            C.atomic_json(path, {key: entry(targets)})
            self.assertEqual(H._cached_targets(), targets)
            for bad in (None, [], {"100": 50.0}, {**targets, "100": False}, {**targets, "100": -1}):
                C.atomic_json(path, {key: entry(bad)})
                self.assertIsNone(H._cached_targets())
            corrupt = entry(targets)
            corrupt["targets"] = {**targets, "100": 70.0}
            C.atomic_json(path, {key: corrupt})
            self.assertIsNone(H._cached_targets())
            for section in ("targets", "raw_ink", "want_ink"):
                malformed = json.loads(json.dumps(entry(targets)))
                malformed[section]["100"] = "OVERFLOW"
                path.write_text(json.dumps({key: malformed}).replace('"OVERFLOW"', "1e999"))
                self.assertIsNone(C.read_json(path))
                self.assertIsNone(H._cached_targets())
            for section in ("targets", "raw_ink", "want_ink"):
                malformed = json.loads(json.dumps(entry(targets)))
                malformed[section]["100"] = "\ud800"
                path.write_text(json.dumps({key: malformed}))
                self.assertIsNone(C.read_json(path))
                self.assertIsNone(H._cached_targets())
            C.atomic_json(path, {key: entry({**targets, "100": 9 * 10**308})})
            self.assertIsNone(H._cached_targets())

    def test_subset_cli_rejects_site_and_nested_or_symlinked_site_outputs_before_writing(self):
        """A probe cannot leave partial datasets in any directory the normal site preview can copy."""
        import build_hangul as B

        name = "cache-probe-" + Path(self.temp.name).name
        nested = B.SITE / name
        self.addCleanup(shutil.rmtree, nested, ignore_errors=True)
        link = Path(self.temp.name) / "site-link"
        link.symlink_to(B.SITE, target_is_directory=True)
        for destination in (B.SITE, nested, link / name):
            env = {
                **os.environ,
                "LIMN_KO_CHARS": "가",
                "LIMN_KO_OUT": str(destination),
                "LIMN_KO_CACHE": "0",
                "LIMN_KO_SMOOTH": "0",
                "LIMN_PROCS": "1",
            }
            result = subprocess.run(
                [sys.executable, str(Path(B.__file__)), "400"],
                env=env,
                text=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                timeout=30,
            )
            self.assertNotEqual(result.returncode, 0)
            self.assertIn("requires LIMN_KO_OUT outside site/", result.stdout)
        self.assertFalse(nested.exists())

    def test_corrupt_or_oversized_smoothing_history_is_replaced_by_valid_current_solve(self):
        """Unrelated stale entries cannot crash publication or force every later build to solve again."""
        import hangul as H

        path = Path(self.temp.name) / ".params-cache.json"

        def solve_map(function, values):
            """Use owned corpus-solve boundaries while exercising actual cache persistence and parsing."""
            if function is H._raw_ink:
                return [(w, 40.0 + w / 10, 10000.0 + w) for w in values]
            return [(w, stroke) for w, _, stroke in values]

        stale_values = (
            '{"obsolete":"\\ud800"}',
            '{"\\ud800":"obsolete"}',
            json.dumps({"obsolete": "x" * (C.MAX_BYTES - 64)}),
        )
        with (
            patch.object(H, "FDIR", Path(self.temp.name)),
            patch.dict(os.environ, {"LIMN_KO_CACHE": "1"}),
            patch.object(H, "_SMOOTH_TARGETS", None),
        ):
            for raw in stale_values:
                path.write_text(raw)
                current = H.smooth_solve(solve_map)
                self.assertEqual(H._cached_targets(), current)
                self.assertLessEqual(path.stat().st_size, C.MAX_BYTES)

    @unittest.skipUnless(os.environ.get("LIMN_KO_CACHE_REAL") == "1", "set LIMN_KO_CACHE_REAL=1 for real glyph fits")
    def test_real_parent_composed_jamo_symbol_families_equal_cached_bytes(self):
        """Real official-parent geometry and serialized bytes survive cold-to-hit family round trips."""
        import build_hangul as B
        import hangul as H

        ws = [100, 400, 900]
        pre = {w: H.params(w) for w in ws}
        cache = C.GlyphCache(self.root, ws, pre, C.fingerprint(H.HERE))
        with patch.object(B, "_GLYPH_CACHE", cache):
            for ch in "가갂ㄱ○":
                cold = B._cached_one((ws, ch))
                hit = B._cached_one((ws, ch))
                self.assertFalse(cold[3])
                self.assertTrue(hit[3])
                self.assertEqual(json.dumps(cold[:3], ensure_ascii=False), json.dumps(hit[:3], ensure_ascii=False))


if __name__ == "__main__":
    unittest.main()
