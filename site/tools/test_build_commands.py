"""Build commands propagate failures and stamp isolated previews portably."""

import hashlib
import os
import re
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
REFERENCE_NAMES = (
    "Comfortaa.ttf",
    "Fredoka.ttf",
    "Inter.ttf",
    "Nunito.ttf",
    "Poppins-Bold.ttf",
    "Quicksand.ttf",
    "VarelaRound.ttf",
    "Baloo2[wght].ttf",
    "MPLUSRounded1c-Bold.ttf",
    "Pretendard-Regular.ttf",
    "NotoSansKR.ttf",
)
LICENSE_NAMES = (
    "OFL-Inter.txt",
    "OFL-Pretendard.txt",
    "OFL-NotoSansKR.txt",
    "OFL-Quicksand.txt",
    "OFL-Nunito.txt",
    "OFL-Fredoka.txt",
)
PREVIEW_REFS = ("Quicksand.ttf", "Nunito.ttf", "Fredoka.ttf", "OFL-Quicksand.txt", "OFL-Nunito.txt", "OFL-Fredoka.txt")


class BuildCommandContracts(unittest.TestCase):
    """Exercise real shells and temporary files without building fonts or using the network."""

    def setUp(self):
        """Give every command its own source, output, and executable search directory."""
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        self.root = Path(temp.name).resolve()
        self.site = self.root / "site"
        self.tools = self.site / "tools"
        self.tools.mkdir(parents=True)
        shutil.copyfile(ROOT / "Makefile", self.root / "Makefile")
        shutil.copyfile(ROOT / "site/tools/fetch_refs.sh", self.tools / "fetch_refs.sh")
        # Keep real transfer/checksum behavior while substituting the unmanaged HTTP response bytes.
        manifest = (ROOT / "site/tools/comparison_refs.tsv").read_text().splitlines()
        digest = hashlib.sha256(b"downloaded font bytes").hexdigest()
        entries = []
        for entry in manifest:
            if entry and not entry.startswith("#"):
                name, _, url = entry.split("\t")
                entries.append("\t".join((name, digest, url)))
        (self.tools / "comparison_refs.tsv").write_text("\n".join(entries) + "\n")
        stamp = ROOT / "site/tools/stamp_preview.py"
        if stamp.exists():
            shutil.copyfile(stamp, self.tools / stamp.name)

    def run_command(self, *args, env=None):
        """Run a command against the isolated tree and retain its status and diagnostic output."""
        return subprocess.run(
            args, cwd=self.root, env=env, text=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, check=False
        )

    def test_font_and_play_fail_when_builder_fails(self):
        """Filtering builder output must retain each builder's nonzero exit status."""
        for target in ("font", "play"):
            with self.subTest(target=target):
                result = self.run_command("make", "-o", "hangul-fonts", target, "R=false")
                self.assertNotEqual(result.returncode, 0, result.stdout)

    def test_all_runs_pages_after_font_exports_are_ready(self):
        """The all orchestration waits for existing build prerequisites before coverage consumes fonts."""
        # Substitute expensive leaf builds, retaining the actual all/pages dependency orchestration.
        with (self.root / "Makefile").open("a") as makefile:
            makefile.write("\nplay font cuts hangul hangul-fonts hangul-measure icons refs:\n\t@true\n")
            makefile.write("fonts:\n\t@touch site/fonts-ready\n")
            makefile.write("coverage-page:\n\t@test -f site/fonts-ready && touch site/coverage-ready\n")
        result = self.run_command("make", "all", "R=true")
        self.assertEqual(result.returncode, 0, result.stdout)
        self.assertTrue((self.site / "coverage-ready").is_file(), result.stdout)

    def test_font_and_play_succeed_when_builder_succeeds(self):
        """A successful builder remains a successful command after output filtering."""
        for target in ("font", "play"):
            with self.subTest(target=target):
                result = self.run_command("make", "-o", "hangul-fonts", target, "R=true")
                self.assertEqual(result.returncode, 0, result.stdout)

    def test_font_output_filter_consumes_verbose_success_without_sigpipe(self):
        """A successful verbose builder cannot fail because the output filter closes early."""
        builder = self.tools / "verbose-builder"
        builder.write_text("#!/usr/bin/env python3\nfor _ in range(10000): print('font build progress ' * 8)\n")
        builder.chmod(0o755)
        result = self.run_command("make", "-o", "hangul-fonts", "font", "R=" + str(builder))
        self.assertEqual(result.returncode, 0, result.stdout)

    def reference_environment(self, failure):
        """Substitute curl only at the downloader boundary, including partial failed output."""
        binary = self.root / "bin"
        binary.mkdir(exist_ok=True)
        curl = binary / "curl"
        curl.write_text("""#!/usr/bin/env bash
set -eu
output=
while [ "$#" -gt 0 ]; do
  if [ "$1" = -o ]; then output=$2; shift 2; else shift; fi
done
if [ "${EMPTY_DOWNLOAD:-}" = yes ]; then
  : > "$output"
elif [ "${WRONG_BYTES:-}" = yes ]; then
  printf 'corrupt font bytes' > "$output"
else
  printf 'downloaded font bytes' > "$output"
fi
case "$FAIL_DOWNLOAD" in
  all) exit 22 ;;
  one) case "$output" in *Inter.ttf*) exit 22 ;; esac ;;
esac
""")
        curl.chmod(0o755)
        return {**os.environ, "PATH": str(binary) + os.pathsep + os.environ["PATH"], "FAIL_DOWNLOAD": failure}

    def test_reference_download_failure_is_not_reported_as_success(self):
        """One or all failed parallel transfers make the download command fail."""
        for failure in ("all", "one"):
            with self.subTest(failure=failure):
                shutil.rmtree(self.site / "refs", ignore_errors=True)
                result = self.run_command("bash", "site/tools/fetch_refs.sh", env=self.reference_environment(failure))
                self.assertNotEqual(result.returncode, 0, result.stdout)
                self.assertNotIn("reference fonts:", result.stdout)

    def test_failed_reference_download_does_not_leave_a_cached_partial_font(self):
        """A partial transfer cannot become a nonempty cached font on the next run."""
        self.run_command("bash", "site/tools/fetch_refs.sh", env=self.reference_environment("all"))
        self.assertEqual(list((self.site / "refs").iterdir()), [])

    def test_reference_download_success_and_cached_success(self):
        """All reference files survive successful downloads and a later offline cached run."""
        result = self.run_command("bash", "site/tools/fetch_refs.sh", env=self.reference_environment("none"))
        self.assertEqual(result.returncode, 0, result.stdout)
        self.assertIn("reference fonts: 11", result.stdout)
        self.assertEqual({path.name for path in (self.site / "refs").iterdir()}, set(REFERENCE_NAMES + LICENSE_NAMES))
        result = self.run_command("bash", "site/tools/fetch_refs.sh", env=self.reference_environment("all"))
        self.assertEqual(result.returncode, 0, result.stdout)

    def test_reference_checksum_rejects_wrong_download_bytes(self):
        """A successful HTTP response with incorrect pinned bytes cannot enter the cache."""
        env = {**self.reference_environment("none"), "WRONG_BYTES": "yes"}
        result = self.run_command("bash", "site/tools/fetch_refs.sh", env=env)
        self.assertNotEqual(result.returncode, 0, result.stdout)
        self.assertIn("checksum mismatch", result.stdout)
        for name in ("Inter.ttf", "Pretendard-Regular.ttf", "NotoSansKR.ttf") + LICENSE_NAMES:
            self.assertFalse((self.site / "refs" / name).exists())
        self.assertFalse(list((self.site / "refs").glob("*.part.*")))

    def test_reference_checksum_rechecks_existing_cached_font(self):
        """An invalid cached comparison font is repaired from the verified download."""
        refs = self.site / "refs"
        refs.mkdir()
        (refs / "Inter.ttf").write_text("corrupt cached font")
        result = self.run_command("bash", "site/tools/fetch_refs.sh", env=self.reference_environment("none"))
        self.assertEqual(result.returncode, 0, result.stdout)
        self.assertEqual((refs / "Inter.ttf").read_bytes(), b"downloaded font bytes")

    def test_reference_download_rejects_empty_successful_responses(self):
        """HTTP success with an empty body is not a usable cached reference."""
        env = {**self.reference_environment("none"), "EMPTY_DOWNLOAD": "yes"}
        result = self.run_command("bash", "site/tools/fetch_refs.sh", env=env)
        self.assertNotEqual(result.returncode, 0, result.stdout)
        self.assertIn("empty reference download", result.stdout)
        self.assertEqual(list((self.site / "refs").iterdir()), [])

    def test_preview_stamps_versions_without_backup_files_or_private_cache(self):
        """Preview copies update only version tokens, keeping content and private caches safe."""
        original = b'<script src="data.js?v=old123"></script>\r\n<p>Unchanged</p>\r\n'
        (self.site / "sample page.html").write_bytes(original)
        (self.site / ".glyph-cache").mkdir()
        (self.site / ".glyph-cache/private.json").write_text("private build data")
        private = (
            "tools/hangul/.params-cache.json",
            "tools/hangul/.params-cache.lock",
            "tools/hangul/.pending-incomplete",
            "tools/hangul/.glyph-cache/private.json",
        )
        for relative in private:
            path = self.site / relative
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text("private build data")
        refs = self.site / "refs"
        refs.mkdir()
        for name in REFERENCE_NAMES + LICENSE_NAMES:
            (refs / name).write_text("reference data")
        preview = self.root / "preview"
        result = self.run_command("make", "preview", "PREVIEW=" + str(preview))
        self.assertEqual(result.returncode, 0, result.stdout)
        stamped = (preview / "sample page.html").read_bytes()
        self.assertRegex(stamped, rb"\?v=[0-9]{12}")
        self.assertEqual(re.sub(rb"\?v=[0-9]{12}", b"?v=old123", stamped), original)
        self.assertFalse(list(preview.glob("*.html-*")))
        self.assertFalse((preview / ".glyph-cache").exists())
        for relative in private:
            self.assertFalse((preview / relative).exists(), relative)
        self.assertEqual({path.name for path in (preview / "refs").iterdir()}, set(PREVIEW_REFS))

    def test_preview_accepts_a_destination_with_spaces(self):
        """The user-selected preview directory stays one path through the make recipe."""
        (self.site / "page.html").write_text('<script src="data.js?v=old"></script>')
        preview = self.root / "preview with spaces"
        result = self.run_command("make", "preview", "PREVIEW=" + str(preview))
        self.assertEqual(result.returncode, 0, result.stdout)
        self.assertTrue((preview / "page.html").is_file())


if __name__ == "__main__":
    unittest.main()
