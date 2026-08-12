"""
Regression tests for pipeline/tools/tst_from_stages.py.

Uses stdlib unittest -- no pytest is installed anywhere in this project and
there's no existing Python dependency file to add it to, so this matches
the project's existing zero-extra-dependency pattern instead of introducing
one for testing alone.

Run: python3 -m unittest pipeline.tests.test_tst_from_stages
     (from the repo root)
  or python3 pipeline/tests/test_tst_from_stages.py
"""
import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "tools"))

from tst_from_stages import compute_tst_from_stages, MIN_TIB_MIN, MAX_TIB_MIN  # noqa: E402


def stages(wake, light, rem, deep, source_tag="0x4C"):
    return {"sleep_stages": {
        "wake_min": wake, "light_min": light, "rem_min": rem, "deep_min": deep,
        "source_tag": source_tag,
    }}


class TestDeclinePaths(unittest.TestCase):
    def test_missing_field_declines(self):
        hrs, meta = compute_tst_from_stages({"sleep_stages": {"wake_min": 34.0, "light_min": 386.5}})
        self.assertIsNone(hrs)
        self.assertEqual(meta["reason"], "missing_stages")

    def test_no_sleep_stages_key_at_all_declines(self):
        hrs, meta = compute_tst_from_stages({})
        self.assertIsNone(hrs)
        self.assertEqual(meta["reason"], "missing_stages")

    def test_non_numeric_field_declines(self):
        hrs, meta = compute_tst_from_stages(stages("bad", 386.5, 167.5, 27.5))
        self.assertIsNone(hrs)
        self.assertEqual(meta["reason"], "non_numeric")

    def test_negative_minutes_declines(self):
        hrs, meta = compute_tst_from_stages(stages(-5, 386.5, 167.5, 27.5))
        self.assertIsNone(hrs)
        self.assertEqual(meta["reason"], "negative_minutes")

    def test_tib_below_floor_declines(self):
        # The exact failure mode Door B's MIN_TIB_MIN=420 raise was built to close:
        # a partial/reset bout fragment summing to 5-6h must not reach the tile.
        hrs, meta = compute_tst_from_stages(stages(20.0, 200.0, 100.0, 10.0))  # TIB=330min
        self.assertIsNone(hrs)
        self.assertEqual(meta["reason"], "tib_out_of_range")

    def test_tib_at_floor_boundary_passes(self):
        # wake+light+rem+deep = 420.0 exactly -- MIN_TIB_MIN is inclusive (<=).
        hrs, meta = compute_tst_from_stages(stages(20.0, 300.0, 90.0, 10.0))
        self.assertIsNotNone(hrs)
        self.assertTrue(meta["ok"])

    def test_tib_above_ceiling_declines(self):
        hrs, meta = compute_tst_from_stages(stages(34.0, 2200.0, 167.5, 27.5))
        self.assertIsNone(hrs)
        self.assertEqual(meta["reason"], "tib_out_of_range")

    def test_tst_non_positive_declines(self):
        # TIB in-range (500min) but entirely wake -- light/rem/deep all zero.
        hrs, meta = compute_tst_from_stages(stages(500.0, 0.0, 0.0, 0.0))
        self.assertIsNone(hrs)
        self.assertEqual(meta["reason"], "tst_non_positive")

    def test_floor_and_ceiling_constants_unchanged(self):
        # Not a behavior test -- a tripwire. If these ever change, Door B's own
        # risk analysis (see known_issues.md 2026-08-09) needs re-reading, not
        # just this test updated silently.
        self.assertEqual(MIN_TIB_MIN, 420.0)
        self.assertEqual(MAX_TIB_MIN, 960.0)


class TestHappyPathRealNights(unittest.TestCase):
    """Anchored to the two real nights logged this week -- if the arithmetic
    ever silently changes, these are the numbers that should catch it."""

    def test_night_2026_08_08(self):
        hrs, meta = compute_tst_from_stages(stages(93.0, 327.5, 159.0, 55.5))
        self.assertEqual(hrs, 9.03)
        self.assertEqual(meta["hhmm"], "9h02m")
        self.assertTrue(meta["ok"])
        self.assertFalse(meta["deep_anomaly"])  # deep_fraction ~0.102, inside [0.08, 0.35]

    def test_night_2026_08_09(self):
        hrs, meta = compute_tst_from_stages(stages(34.0, 386.5, 167.5, 27.5))
        self.assertEqual(hrs, 9.69)
        self.assertEqual(meta["hhmm"], "9h42m")
        self.assertTrue(meta["deep_anomaly"])  # deep_fraction ~0.047, below 0.08

    def test_night_2026_08_10_low_end(self):
        # The first real reading under the 7h warn threshold -- the actual
        # low-end test Door B's risk was accepted against.
        hrs, meta = compute_tst_from_stages(stages(101.0, 247.0, 86.0, 17.0))
        self.assertEqual(hrs, 5.83)
        self.assertEqual(meta["hhmm"], "5h50m")
        self.assertTrue(meta["ok"])


class TestDeepAnomalyIsLoggedNotDeclined(unittest.TestCase):
    """The whole point of the sum-robust-to-subdivision redesign: a garbage
    deep_min must not block the TST number, only get flagged alongside it."""

    def test_deep_fraction_zero_still_returns_a_number(self):
        hrs, meta = compute_tst_from_stages(stages(34.0, 400.0, 167.5, 0.0))
        self.assertIsNotNone(hrs)
        self.assertTrue(meta["deep_anomaly"])

    def test_deep_fraction_implausibly_high_still_returns_a_number(self):
        hrs, meta = compute_tst_from_stages(stages(34.0, 100.0, 50.0, 400.0))
        self.assertIsNotNone(hrs)
        self.assertTrue(meta["deep_anomaly"])


if __name__ == "__main__":
    unittest.main()
