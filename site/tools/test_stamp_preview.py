"""Preview version stamping preserves bytes and cannot follow HTML output links."""

import random
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from stamp_preview import stamp_versions


class PreviewStampContracts(unittest.TestCase):
    """Check token replacement and the real command's output-file boundary."""

    def test_generated_tokens_preserve_surrounding_bytes(self):
        """Across generated tokens, only the version changes and repeat stamping is stable."""
        rng = random.Random(67261)
        alphabet = "0123456789abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ"
        for _ in range(100):
            token = "".join(rng.choice(alphabet) for _ in range(rng.randint(1, 60)))
            version = "".join(rng.choice(alphabet) for _ in range(rng.randint(1, 60)))
            template = b'<!doctype html>\r\n<script src="font.js?v=%s"></script>\r\n' + "한글".encode()
            actual = stamp_versions(template % token.encode(), version)
            self.assertEqual(actual, template % version.encode(), (token, version))
            self.assertEqual(stamp_versions(actual, version), actual)

    def test_invalid_version_is_rejected_without_rewriting(self):
        """Only ASCII alphanumeric tokens can become cache-tag output."""
        for token in ("", "a&b", "a/b", "a\\b", "a b", "한글", "a\n"):
            with self.subTest(token=token), self.assertRaises(ValueError):
                stamp_versions(b"?v=old", token)

    def test_command_refuses_html_symlinks_before_rewriting_any_page(self):
        """A preview page link cannot make stamping write outside the chosen folder."""
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            outside = root / "outside.html"
            outside.write_bytes(b"?v=outside")
            preview = root / "preview"
            preview.mkdir()
            (preview / "linked.html").symlink_to(outside)
            page = preview / "first.html"
            page.write_bytes(b"?v=inside")
            result = subprocess.run(
                [sys.executable, str(Path(__file__).with_name("stamp_preview.py")), str(preview)],
                capture_output=True,
                check=False,
            )
            self.assertNotEqual(result.returncode, 0)
            self.assertIn(b"symbolic links", result.stderr)
            self.assertEqual(outside.read_bytes(), b"?v=outside")
            self.assertEqual(page.read_bytes(), b"?v=inside")


if __name__ == "__main__":
    unittest.main()
