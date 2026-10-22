"""Fitting accuracy, serialized acceptance and quadratic storage regressions.

Run with the Hangul build dependencies:
  uv run --no-project --with skia-pathops --with fonttools --with numpy \
    --with shapely --with scipy python3 tools/test_hangul_fit.py
"""
import unittest
import math
from unittest.mock import patch

import numpy as np
from shapely.affinity import translate
from shapely.geometry import box, Point
from shapely.ops import unary_union

import hangul as H
import build_hangul as B
import audit_hangul as A


class HangulFitTests(unittest.TestCase):
    def test_availability_matches_cmap_without_constructing_outlines(self):
        cmap = H._masters()[1][1]
        with patch.object(H, "_rec", side_effect=AssertionError("availability constructed an outline")):
            for ch in H.charset() + ["A", "\U0001F600"]:
                self.assertEqual(H.has(ch), ord(ch) in cmap)

    def test_failed_composition_remains_an_outline_error(self):
        with patch.object(H, "compose", side_effect=RuntimeError("composition failed")):
            self.assertTrue(H.has("갂"))
            # Availability must not turn failed synthesis into an empty outline.
            with self.assertRaisesRegex(RuntimeError, "composition failed"):
                H._rec("갂", 1)

    def test_free_quadratic_stores_one_control_within_tolerance(self):
        t = np.linspace(0, 1, 65)[:, None]
        a, c, b = np.array([0., 0.]), np.array([37., 70.]), np.array([100., 10.])
        q = (1 - t) ** 2 * a + 2 * (1 - t) * t * c + t ** 2 * b
        segments = H._quads(q, None, None, .2)
        self.assertIsNotNone(segments)
        self.assertEqual(len(segments[0][1]), 3)
        self.assertLessEqual(H._spline_err(np.array([segments[0][1][1]]), a, b, q), .2)

    def test_reparameterization_projects_between_curve_samples(self):
        a, c, b = np.array([0., 0.]), np.array([37., 70.]), np.array([100., 10.])
        t = np.array([0., .123, 1.])[:, None]
        q = (1 - t) ** 2 * a + 2 * (1 - t) * t * c + t ** 2 * b
        u = H._spline_param(np.array([c]), a, b, q, 1)
        self.assertAlmostEqual(u[1], .123, delta=.001)
        self.assertEqual((u[0], u[-1]), (0., 1.))

    def test_least_squares_recovers_known_free_quadratic_control(self):
        a, c, b = np.array([0., 0.]), np.array([37., 70.]), np.array([100., 10.])
        u = np.linspace(0, 1, 101)
        t = u[:, None]
        q = (1 - t) ** 2 * a + 2 * (1 - t) * t * c + t ** 2 * b
        fitted = H._spline_lsq(q, u, 1, None, None)
        np.testing.assert_allclose(fitted[0], c, atol=1e-10, rtol=0)

    def test_stored_count_drops_only_exact_midpoint_on_curve(self):
        self.assertEqual(H._stored_points("M0 0Q5 10 10 0Q15 -10 20 0L0 0z"), 4)
        self.assertEqual(H._stored_points("M0 0Q5 10 10 0Q15 -12 20 0L0 0z"), 5)

    def test_smoothing_fallback_rejects_fit_outside_original_bounds(self):
        g = box(0, 0, 100, 100)
        displaced = H._poly_path(translate(g, xoff=2))
        # Isolate the fitter boundary: even a valid, same-topology result must
        # fail when smoothing would previously have relaxed its error bound.
        with patch.object(H, "fit_geom", return_value=displaced):
            _, fitted = H.fit_checked(g, 75.9)
        self.assertFalse(fitted)

    def test_fallback_rejects_float_error_even_when_rounding_passes(self):
        g = box(0, 0, 100, 100)
        displaced = H.pathops.Path(); pen = displaced.getPen()
        pen.moveTo((1.3, 0)); pen.lineTo((101.3, 0))
        pen.lineTo((101.3, 100)); pen.lineTo((1.3, 100)); pen.closePath()
        rounded, simple = H.geom_of_d(H.d_compact(displaced))
        self.assertTrue(simple and H._within(rounded, g, H.ROUND_MAX))
        with patch.object(H, "fit_geom", return_value=displaced):
            _, fitted = H.fit_checked(g, 75.9)
        self.assertFalse(fitted)

    def test_serialized_acceptance_can_reject_every_candidate(self):
        seen = []
        def reject(d):
            seen.append(d)
            return False
        _, fitted = H.fit_checked(box(0, 0, 100, 100), 75.9, accept=reject)
        self.assertTrue(seen)
        self.assertFalse(fitted)

    def test_point_budget_rejects_every_valid_over_budget_candidate(self):
        g = box(0, 0, 100, 100)
        with patch.object(H, "fit_geom", return_value=H._poly_path(g)):
            _, fitted = H.fit_checked(g, 75.9, max_points=3)
        self.assertFalse(fitted, "a valid four-point outline exceeds a three-point budget")

    def test_drawn_non_ks_syllable_has_actual_parent_point_count(self):
        gs, cmap, _ = H._masters()[1]
        glyf = gs.font["glyf"]
        ch = next(c for c in H.syllables() if c not in B.KSX1001 and glyf[cmap[ord(c)]].numberOfContours)
        expected = len(glyf[cmap[ord(ch)]].getCoordinates(glyf)[0])
        self.assertEqual(B._parent_budget(ch, 1), expected)

    def test_builder_fits_without_a_point_budget(self):
        g = box(0, 0, 100, 100)
        seen = []
        original = H.fit_checked
        def fit(*args, **kwargs):
            seen.append(kwargs.get("max_points"))
            return original(*args, **kwargs)
        with patch.object(H, "params", return_value={"S": 75.9}), \
             patch.object(H, "master_for", return_value={"m": 1}), \
             patch.object(B, "_parent_budget", return_value=2), \
             patch.object(H, "fit_checked", side_effect=fit):
            result = B._fit_output(400, "가", (g, None), math.inf)
        self.assertEqual(seen, [None])
        self.assertIsNotNone(result, "a parent with fewer points must not reject an accurate outline")
        rounded, simple = H.geom_of_d(result[1])
        self.assertTrue(simple and rounded.is_valid and H._within(rounded, g, H.ROUND_MAX))

    def test_without_a_budget_the_first_valid_fit_is_taken(self):
        calls = []
        original = H.fit_geom
        def count(*args, **kwargs):
            calls.append(args[3] if len(args) > 3 else kwargs.get("hints"))
            return original(*args, **kwargs)
        with patch.object(H, "fit_geom", side_effect=count):
            _, fitted = H.fit_checked(box(0, 0, 100, 100), 75.9)
        self.assertTrue(fitted)
        self.assertEqual(len(calls), 1, "no further candidates once one passes every bound")

    def test_point_budget_keeps_accurate_source_before_lightening_the_glyph(self):
        circle = Point(100, 100).buffer(50, quad_segs=32)
        sources = {400: (circle, None), 500: (box(0, 0, 200, 200), None)}

        def pen(w, ch, lighter=0.0, local=False):
            return (box(75, 75, 125, 125), None) if lighter else sources[w]

        with patch.object(H, "params", return_value={"S": 75.9}), \
             patch.object(H, "master_for", return_value={"m": 1}), \
             patch.object(H, "pen_geom", side_effect=pen), \
             patch.object(H, "advance", return_value=200), \
             patch.object(B, "_parent_budget", return_value=3):
            out, _, _ = B._one(([400, 500], ["가"]))
        rounded, simple = H.geom_of_d(out[400]["가"]["d"])
        self.assertTrue(simple and rounded.is_valid)
        self.assertTrue(rounded.contains(Point(70, 70)), "storage must not replace the accurate circle with a lighter square")
        self.assertGreater(rounded.area, 7500)
        self.assertGreater(H._stored_points(out[400]["가"]["d"]), 4, "the accurate storage excess must remain visible")

    def test_audit_reports_excess_using_effective_master_and_stored_points(self):
        d = "M0 0Q5 10 10 0Q15 -10 20 0L0 0z"  # Four stored points, one implied midpoint.
        with patch.object(H, "params", return_value={"m": 0}), \
             patch.object(H, "master_for", return_value={"m": 2}), \
             patch.object(H, "parent_stored_points", side_effect=lambda ch, m: 2 if m == 2 else 100):
            rows = A.point_excess(400, {"가": {"d": d}, "A": {"d": d}})
        self.assertEqual(len(rows), 1)
        self.assertEqual((rows[0]["ch"], rows[0]["points"], rows[0]["limit"], rows[0]["master"]),
                         ("가", 4, 3, H.MASTERS[2]))

    def test_local_cleanup_removes_accidental_slit_without_filling_counter(self):
        g = box(0, 0, 300, 300).difference(box(149, 200, 152, 301)).difference(box(40, 40, 100, 100))
        self.assertFalse(g.contains(Point(150, 250)))
        repaired = H.tidy_local(g)
        self.assertTrue(repaired.contains(Point(150, 250)))
        self.assertFalse(repaired.contains(Point(70, 70)), "the drawn counter must remain white")
        self.assertEqual(H._topo(repaired), H._topo(g))
        self.assertLessEqual(abs(repaired.area - g.area), .02 * g.area)

    def test_local_cleanup_rejects_a_repair_that_removes_a_genuine_counter(self):
        g = box(0, 0, 100, 100).difference(box(48, 48, 52, 52))
        repaired = H.tidy_local(g)
        self.assertTrue(repaired.equals(g))

    def test_heavier_retry_source_is_the_accepted_serialized_outline(self):
        sources = {100: (box(0, 0, 98, 98), None), 200: (box(.25, 0, 100.25, 100), None)}
        seen = []
        original = B._fit_under
        def record(w, ch, source, plain, upper, cap):
            if upper is not None:
                seen.append(upper[0])
            return original(w, ch, source, plain, upper, cap)
        with patch.object(H, "params", return_value={"S": 75.9}), \
             patch.object(H, "pen_geom", side_effect=lambda w, ch: sources[w]), \
             patch.object(H, "advance", return_value=100), \
             patch.object(B, "_fit_under", side_effect=record):
            out, _, _ = B._one(([100, 200], ["A"]))
        accepted, _ = H.geom_of_d(out[200]["A"]["d"])
        self.assertEqual(len(seen), 1)
        self.assertTrue(seen[0].equals(accepted), "retries must borrow the heavier outline that actually passed")


    # ---- the pen at a weight its whites hold back (2026-10-01: 쪽 똑 헤 at Thin ink at every weight)
    PEN = {"S": 100.0, "V": 100.0, "delta": 20.0, "hx": 0.0}

    def test_a_piece_its_whites_hold_back_grows_everywhere_else(self):
        # two round pieces 6 units apart, as NanumSquareRound R draws the halves of ㅉ, and a stem away from them
        g = unary_union([Point(0, 0).buffer(60, quad_segs=32), Point(126, 0).buffer(60, quad_segs=32),
                         box(-30, 100, 30, 400)])
        auto, rigid = H.pen_steps(g, self.PEN), H.pen_steps(g, self.PEN, local=False)
        self.assertGreater(auto.area, 1.3 * rigid.area, "a held piece must still grow away from the white it keeps")
        self.assertEqual(H._topo(auto), H._topo(g))
        self.assertGreaterEqual(H.min_gap(auto), H.GAP_MIN * self.PEN["S"] + H.CLEAR_PAD - 0.5)

    def test_the_local_pen_never_joins_pieces(self):
        # flat parallel bars 12 apart: here the local pen joins the two near ones (훻 at 900 lost a piece so)
        g = unary_union([box(0, 0, 40, 300), box(52, 0, 92, 300), box(200, 0, 240, 300)])
        self.assertNotEqual(H._topo(H.pen_steps(g, self.PEN, local=True)), H._topo(g), "the case must be real")
        auto = H.pen_steps(g, self.PEN)
        self.assertEqual(H._topo(auto), H._topo(g))
        self.assertAlmostEqual(auto.area, H.pen_steps(g, self.PEN, local=False).area, places=3)

    def test_parent_ink_fails_a_syllable_far_under_its_masters_proportion(self):
        meta = {900: {"pair": {"master": "EB"}}}
        M = {900: {"가": {"ink": 100.0}, "쪽": {"ink": 45.0}, "헤": {"ink": 120.0}, "빽": {"ink": 105.0}}}
        ratios = lambda name: {"가": 1.0, "쪽": 1.5, "헤": 1.4, "빽": 1.62}
        low, info = A.parent_ink_findings([900], meta, M, ["가", "쪽", "헤", "빽"], ratios)
        self.assertEqual([(x, c) for x, _, c in low], [(0.3, "쪽")])
        self.assertEqual([(x, c) for x, _, c in info], [(0.65, "빽")], "헤 at 0.86 passes")

    def test_parent_ink_ratios_come_from_the_master(self):
        r = A.parent_ink(H.MASTERS.index("R"))
        self.assertEqual(r["가"], 1.0)
        self.assertTrue(1.3 < r["쪽"] < 1.8 and 1.3 < r["빽"] < 2.0, (r["쪽"], r["빽"]))


if __name__ == "__main__":
    unittest.main(verbosity=2)
