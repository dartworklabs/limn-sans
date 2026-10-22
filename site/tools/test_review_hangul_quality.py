"""Pin review metrics to the real audit and preserve its white-space acceptance boundaries."""

import unittest

import audit_hangul as A
import review_hangul_quality as R
from hypothesis import given, settings
from hypothesis import strategies as st


class ReviewMetricTests(unittest.TestCase):
    """Review artifacts must use the audit's observable ink and acceptance semantics."""

    def test_evenodd_nested_contours_keep_the_counter_white(self):
        """A same-winding inner contour is white under the audit's even-odd fill convention."""
        drawing = "M0 0L100 0L100 100L0 100zM20 20L80 20L80 80L20 80z"
        self.assertEqual(R.ink_area(drawing), 6400.0)

    def test_missing_reference_is_rejected_before_reporting_normalized_ink(self):
        """A sample without 가 cannot claim to pass a metric normalized against 가."""
        with self.assertRaisesRegex(ValueError, "requires 가"):
            R.parent_ink_check({}, [{"ch": "굶"}])

    @settings(max_examples=20, deadline=None)
    @given(st.integers(20, 200), st.integers(20, 200), st.integers(-500, 500))
    def test_ink_matches_full_audit_for_translated_rectangles(self, width, height, offset):
        """The fast area agrees with the full audit over dimensions and coordinate translations."""
        drawing = f"M{offset} 0L{offset + width} 0L{offset + width} {height}L{offset} {height}z"
        self.assertEqual(R.ink_area(drawing), A.measure(drawing, 20)["ink"])

    def test_white_gate_accepts_exact_rounding_slack_and_rejects_a_smaller_gap(self):
        """The review policy uses the release audit's inclusive white-space threshold."""
        measured = {
            "specks": 0,
            "tiny": 0,
            "badring": 0,
            "semi": 0,
            "ink": 1000,
            "on": 10,
            "off": 2,
            "gap": 29.0,
            "holes": [(1000, 29.0)],
        }
        self.assertEqual(R.measure_failures(measured, 100), [])
        measured["gap"] = 28.99
        self.assertEqual(R.measure_failures(measured, 100), ["gap"])
        measured["holes"] = [(1000, 28.99)]
        self.assertEqual(R.measure_failures(measured, 100), ["gap", "counter"])


if __name__ == "__main__":
    unittest.main()
