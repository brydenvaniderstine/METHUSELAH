// Regression tests for resolveVectors(), especially the sleepDurationHrs
// three-tier fallback and its measuredAt field -- the direct fix for the
// false-freshness bug logged in known_issues.md 2026-08-10/11.
//
// Synced into web/src/engine/ by the same cp step as the file under test --
// see index.test.js's header comment for why.

import { resolveVectors, STAGE_SUM_FALLBACK_ENABLED, SOURCE_GEN4 } from "./sources.js";

const NOW = new Date().toISOString();
const OLD = "2026-08-09T05:33:24.579623"; // > 24h before "now" in any real run of this suite

const REAL_STAGES = { wake_min: 34.0, light_min: 386.5, rem_min: 167.5, deep_min: 27.5 };

function gen3(vectors, { timestamp = NOW, sleep_data_ts = null } = {}) {
  return { timestamp, sleep_data_ts, vectors };
}

describe("resolveVectors() -- sleepDurationHrs fallback tiers", () => {
  test("strict tier (sleep_duration_hrs) wins when present", () => {
    const v = resolveVectors(null, gen3({ sleep_duration_hrs: 7.5, sleep_duration_estimate_hrs: 5.0,
      sleep_duration_stage_sum_hrs: 5.26 }, { sleep_data_ts: NOW }), {});
    expect(v.sleepDurationHrs.value).toBe(7.5);
    expect(v.sleepDurationHrs.estimateMethod).toBeNull();
  });

  test("bout_tail tier used when strict is null", () => {
    const v = resolveVectors(null, gen3({ sleep_duration_hrs: null, sleep_duration_estimate_hrs: 6.2,
      sleep_duration_stage_sum_hrs: 5.26 }, { sleep_data_ts: NOW }), {});
    expect(v.sleepDurationHrs.value).toBe(6.2);
    expect(v.sleepDurationHrs.estimateMethod).toBe("bout_tail");
  });

  test("stage_sum tier used when both strict and bout_tail are null", () => {
    // STAGE_SUM_FALLBACK_ENABLED is a plain module const, currently true in
    // production (Door B) -- this test asserts against its real live value
    // rather than mocking it, since that's the actual behavior shipping.
    expect(STAGE_SUM_FALLBACK_ENABLED).toBe(true);
    const v = resolveVectors(null, gen3({ sleep_duration_hrs: null, sleep_duration_estimate_hrs: null,
      sleep_duration_stage_sum_hrs: 5.83 }, { sleep_data_ts: NOW }), {});
    expect(v.sleepDurationHrs.value).toBe(5.83);
    expect(v.sleepDurationHrs.estimateMethod).toBe("stage_sum");
  });

  test("all three null resolves to a clean null vector, not an error", () => {
    const v = resolveVectors(null, gen3({ sleep_duration_hrs: null, sleep_duration_estimate_hrs: null,
      sleep_duration_stage_sum_hrs: null }, { sleep_data_ts: NOW }), {});
    expect(v.sleepDurationHrs.value).toBeNull();
    expect(v.sleepDurationHrs.estimateMethod).toBeNull();
    expect(v.sleepDurationHrs.measuredAt).toBeNull();
  });

  test("gen4, when fresh, outranks gen3 entirely for the strict tier", () => {
    const gen4 = { totalSleepHrs: 8.1, isLive: true, timestamp: NOW };
    const v = resolveVectors(gen4, gen3({ sleep_duration_hrs: 7.5 }, { sleep_data_ts: NOW }), {});
    expect(v.sleepDurationHrs.value).toBe(8.1);
    expect(v.sleepDurationHrs.source).toBe(SOURCE_GEN4);
    expect(v.sleepDurationHrs.measuredAt).toBeNull(); // measuredAt is gen3-specific, not gen4
  });
});

describe("resolveVectors() -- measuredAt (the false-freshness bug fix)", () => {
  test("measuredAt reflects sleep_data_ts, independent of a fresh overall bridge timestamp", () => {
    // The exact 2026-08-10/11 incident: HRV/RHR fresh this cycle (bridge
    // timestamp = now), but sleep data backfilled from two nights earlier.
    const bridge = gen3(
      { hrv_ms: 56.0, rhr_bpm: 60.0, sleep_duration_hrs: null, sleep_duration_estimate_hrs: null,
        sleep_duration_stage_sum_hrs: 5.26 },
      { timestamp: NOW, sleep_data_ts: OLD },
    );
    const v = resolveVectors(null, bridge, {});
    expect(v.sleepDurationHrs.value).toBe(5.26);
    expect(v.sleepDurationHrs.measuredAt).toBe(OLD);
    expect(v.sleepDurationHrs.measuredAt).not.toBe(bridge.timestamp);
    expect(v.hrv.value).toBe(56.0); // unrelated vector, unaffected, still resolves normally
  });

  test("measuredAt is fresh when sleep data really was fresh this pull", () => {
    const v = resolveVectors(null, gen3({ sleep_duration_stage_sum_hrs: 5.83 }, { sleep_data_ts: NOW }), {});
    expect(v.sleepDurationHrs.measuredAt).toBe(NOW);
  });
});

describe("resolveVectors() -- whole-bridge staleness gate (distinct from measuredAt)", () => {
  test("a gen3 bridge older than the 24h freshness window is not consulted at all", () => {
    const veryOld = new Date(Date.now() - 25 * 3600 * 1000).toISOString();
    const v = resolveVectors(null, gen3({ rhr_bpm: 55, sleep_duration_stage_sum_hrs: 5.83 },
      { timestamp: veryOld, sleep_data_ts: veryOld }), {});
    expect(v.rhr.value).toBeNull();
    expect(v.sleepDurationHrs.value).toBeNull();
  });
});

describe("resolveVectors() -- glucose has no wearable source on either generation", () => {
  test("glucose only ever resolves from manual entry", () => {
    const gen4 = { hrv: 50, isLive: true, timestamp: NOW };
    const v = resolveVectors(gen4, gen3({ hrv_ms: 50 }, { sleep_data_ts: NOW }), { glucose: 4.2 });
    expect(v.glucose.value).toBe(4.2);
    expect(v.glucose.source).toBe("manual");
  });
});
