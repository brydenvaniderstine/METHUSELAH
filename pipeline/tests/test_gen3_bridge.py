"""
Regression tests for pipeline/tools/gen3_bridge.py.

Uses stdlib unittest -- see test_tst_from_stages.py for why (no pytest
installed, no dependency file to add it to). Every test here traces back to
a real bug found this week; see known_issues.md 2026-08-09 through 2026-08-11
for the incidents these are guarding against.

Run: python3 -m unittest pipeline.tests.test_gen3_bridge
     (from the repo root)
"""
import json
import os
import shutil
import sys
import tempfile
import unittest
from unittest.mock import patch

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "tools"))

import gen3_bridge as gb  # noqa: E402

REAL_STAGES_08_09 = {"wake_min": 34.0, "light_min": 386.5, "rem_min": 167.5,
                     "deep_min": 27.5, "source_tag": "0x4C"}
REAL_STAGES_08_10 = {"wake_min": 101.0, "light_min": 247.0, "rem_min": 86.0,
                     "deep_min": 17.0, "source_tag": "0x4C"}


class TestBuildBridgeData(unittest.TestCase):
    def test_sleep_duration_hrs_untouched_by_stage_sum_logic(self):
        bridge = gb.build_bridge_data(pull_class="SLEEP WINDOW", pull_file="x.txt",
                                       priority_event_count=1, hrv_ms=50.0,
                                       sleep_stages=REAL_STAGES_08_09)
        self.assertIsNone(bridge["vectors"]["sleep_duration_hrs"])
        self.assertEqual(bridge["vectors"]["sleep_duration_stage_sum_hrs"], 9.69)

    def test_stage_sum_reads_the_real_nested_bridge_shape(self):
        # Regression test for the 2026-08-09 nesting-level bug: the first
        # wiring attempt passed the whole `bridge` dict to
        # compute_tst_from_stages() instead of bridge["vectors"], which
        # expects sleep_stages at ITS OWN top level -- silently declined
        # missing_stages every time despite real data being present.
        bridge = gb.build_bridge_data(pull_class="SLEEP WINDOW", pull_file="x.txt",
                                       priority_event_count=1, sleep_stages=REAL_STAGES_08_10)
        self.assertEqual(bridge["vectors"]["sleep_duration_stage_sum_hrs"], 5.83)
        self.assertTrue(bridge["vectors"]["sleep_duration_stage_sum_meta"]["ok"])

    def test_sleep_data_ts_set_when_stages_fresh(self):
        bridge = gb.build_bridge_data(pull_class="SLEEP WINDOW", pull_file="x.txt",
                                       priority_event_count=1, sleep_stages=REAL_STAGES_08_09)
        self.assertIsNotNone(bridge["sleep_data_ts"])

    def test_sleep_data_ts_none_when_no_stages(self):
        # This is the live daemon's own call shape -- it never passes
        # sleep_stages at all (confirmed by grep, oura_gen3_ble_daemon.py).
        bridge = gb.build_bridge_data(pull_class="ACTIVE WINDOW", pull_file="x.txt",
                                       priority_event_count=1, hrv_ms=56.0)
        self.assertIsNone(bridge["sleep_data_ts"])
        self.assertIsNone(bridge["vectors"]["sleep_duration_stage_sum_hrs"])


class TestMergeWithExistingBridge(unittest.TestCase):
    def setUp(self):
        self.tmpdir = tempfile.mkdtemp()
        self.bridge_dir = os.path.join(self.tmpdir, "pipeline", "data", "bridge")
        os.makedirs(self.bridge_dir)

    def tearDown(self):
        shutil.rmtree(self.tmpdir)

    def _seed_existing(self, existing_dict):
        with open(os.path.join(self.bridge_dir, "gen3_latest.json"), "w") as f:
            json.dump(existing_dict, f)

    def test_no_existing_bridge_returns_unchanged(self):
        fresh = gb.build_bridge_data(pull_class="ACTIVE WINDOW", pull_file="x.txt",
                                      priority_event_count=1, hrv_ms=50.0)
        merged = gb.merge_with_existing_bridge(fresh, self.tmpdir)
        self.assertEqual(merged, fresh)

    def test_declined_stage_sum_is_never_directly_backfilled(self):
        # The existing bridge has a deliberately WRONG stage-sum value (99.9)
        # that a real recompute would never produce -- if merge ever
        # backfills it verbatim instead of recomputing, this test catches it.
        self._seed_existing({
            "timestamp": "2026-08-09T05:00:00", "sleep_data_ts": "2026-08-09T05:00:00",
            "vectors": {"sleep_stages": REAL_STAGES_08_09,
                        "sleep_duration_stage_sum_hrs": 99.9,
                        "sleep_duration_stage_sum_meta": {"ok": True, "fake": True}},
        })
        daemon_style = gb.build_bridge_data(pull_class="ACTIVE WINDOW", pull_file="x.txt",
                                             priority_event_count=1, hrv_ms=56.0)
        merged = gb.merge_with_existing_bridge(daemon_style, self.tmpdir)
        # sleep_stages backfilled correctly, so a fresh recompute against it
        # gives the REAL number (9.69), not the fake seeded 99.9.
        self.assertEqual(merged["vectors"]["sleep_duration_stage_sum_hrs"], 9.69)

    def test_permanently_missing_stage_data_declines_cleanly(self):
        self._seed_existing({"timestamp": "2026-08-09T05:00:00", "vectors": {}})
        daemon_style = gb.build_bridge_data(pull_class="ACTIVE WINDOW", pull_file="x.txt",
                                             priority_event_count=1, hrv_ms=56.0)
        merged = gb.merge_with_existing_bridge(daemon_style, self.tmpdir)
        self.assertIsNone(merged["vectors"]["sleep_duration_stage_sum_hrs"])

    def test_fresh_bad_fragment_declines_on_its_own_merit(self):
        # A genuinely fresh but bad reading must decline for its OWN reason,
        # not get rescued by a healthy existing bridge sitting underneath it.
        self._seed_existing({
            "timestamp": "2026-08-09T05:00:00",
            "vectors": {"sleep_stages": REAL_STAGES_08_09, "sleep_duration_stage_sum_hrs": 9.69},
        })
        fragment = gb.build_bridge_data(
            pull_class="SLEEP WINDOW", pull_file="x.txt", priority_event_count=1, hrv_ms=50.0,
            sleep_stages={"wake_min": 20.0, "light_min": 200.0, "rem_min": 100.0, "deep_min": 10.0},
        )
        merged = gb.merge_with_existing_bridge(fragment, self.tmpdir)
        self.assertIsNone(merged["vectors"]["sleep_duration_stage_sum_hrs"])
        self.assertEqual(merged["vectors"]["sleep_duration_stage_sum_meta"]["reason"], "tib_out_of_range")

    def test_normal_biometric_field_still_backfills(self):
        # Regression check: none of the sleep-specific changes above should
        # have touched ordinary field backfill.
        self._seed_existing({"timestamp": "2026-08-09T05:00:00",
                              "vectors": {"sleep_temp_c": 34.9}})
        fresh = gb.build_bridge_data(pull_class="ACTIVE WINDOW", pull_file="x.txt",
                                      priority_event_count=1, hrv_ms=61.0)
        merged = gb.merge_with_existing_bridge(fresh, self.tmpdir)
        self.assertEqual(merged["vectors"]["sleep_temp_c"], 34.9)

    def test_sleep_data_ts_backfills_from_existing_when_new_pull_has_none(self):
        self._seed_existing({
            "timestamp": "2026-08-09T05:33:24.579623",
            "sleep_data_ts": "2026-08-09T05:33:24.579623",
            "vectors": {"sleep_stages": REAL_STAGES_08_09},
        })
        daemon_style = gb.build_bridge_data(pull_class="ACTIVE WINDOW", pull_file="x.txt",
                                             priority_event_count=1, hrv_ms=56.0)
        merged = gb.merge_with_existing_bridge(daemon_style, self.tmpdir)
        self.assertEqual(merged["sleep_data_ts"], "2026-08-09T05:33:24.579623")

    def test_the_exact_2026_08_10_11_false_freshness_bug_is_now_impossible(self):
        """Direct regression test for the incident logged in known_issues.md
        2026-08-10/11: a live daemon cycle with fresh HRV this cycle, but
        sleep_stages/stage-sum backfilled from two nights earlier, must NOT
        let sleep_data_ts look as fresh as the general bridge timestamp.
        Before the fix, sleep_data_ts didn't exist and the whole bridge rode
        one shared timestamp -- this is what made the tile show a two-night-
        old reading as if it were live.
        """
        old_ts = "2026-08-09T05:33:24.579623"
        self._seed_existing({
            "timestamp": old_ts, "sleep_data_ts": old_ts,
            "vectors": {"sleep_stages": REAL_STAGES_08_09,
                        "sleep_duration_stage_sum_hrs": 9.69},
        })
        daemon_style = gb.build_bridge_data(pull_class="ACTIVE WINDOW", pull_file="x.txt",
                                             priority_event_count=1, hrv_ms=56.0)
        merged = gb.merge_with_existing_bridge(daemon_style, self.tmpdir)
        self.assertNotEqual(merged["timestamp"], old_ts, "HRV really was fresh this cycle")
        self.assertEqual(merged["sleep_data_ts"], old_ts, "sleep data was NOT fresh this cycle")


class TestPushBridgeJsonFailsClosed(unittest.TestCase):
    def test_skips_without_crashing_or_networking_when_secret_missing(self):
        with patch.dict(os.environ, {}, clear=True):
            os.environ.pop("GEN3_BRIDGE_WRITE_SECRET", None)
            result = gb.push_bridge_json({"source": "gen3_ble", "vectors": {}})
        self.assertIn("Skipped", result)
        self.assertIn("GEN3_BRIDGE_WRITE_SECRET", result)


if __name__ == "__main__":
    unittest.main()
