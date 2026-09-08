// Regression tests for resolveVectors(), especially the sleepDurationHrs
// three-tier fallback and its measuredAt field -- the direct fix for the
// false-freshness bug logged in known_issues.md 2026-08-10/11.
//
// Synced into web/src/engine/ by the same cp step as the file under test --
// see index.test.js's header comment for why.

import { resolveVectors, resolveVector, STAGE_SUM_FALLBACK_ENABLED, SOURCE_GEN4 } from "./sources.js";

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

describe("resolveVectors() -- n/agg provenance pass-through (Task 1b fields)", () => {
  test("rhr/hrv carry n and agg through from the bridge when both are present", () => {
    const v = resolveVectors(null, gen3({
      rhr_bpm: 62, rhr_n: 489, rhr_agg: "session_mean",
      hrv_ms: 48.7, hrv_n: 25320, hrv_agg: "session_mean",
    }), {});
    expect(v.rhr.n).toBe(489);
    expect(v.rhr.agg).toBe("session_mean");
    expect(v.hrv.n).toBe(25320);
    expect(v.hrv.agg).toBe("session_mean");
  });

  test("n and agg default to null independently when the bridge omits either", () => {
    // rhr_n present, rhr_agg absent -- and the reverse for hrv -- to prove
    // neither field's absence drags the other one to null with it.
    const v = resolveVectors(null, gen3({
      rhr_bpm: 62, rhr_n: 489,
      hrv_ms: 48.7, hrv_agg: "session_mean",
    }), {});
    expect(v.rhr.n).toBe(489);
    expect(v.rhr.agg).toBeNull();
    expect(v.hrv.n).toBeNull();
    expect(v.hrv.agg).toBe("session_mean");
  });

  test("a bridge that predates Task 1b (no n/agg fields at all) resolves both to null", () => {
    const v = resolveVectors(null, gen3({ rhr_bpm: 62, hrv_ms: 48.7 }), {});
    expect(v.rhr.n).toBeNull();
    expect(v.rhr.agg).toBeNull();
    expect(v.hrv.n).toBeNull();
    expect(v.hrv.agg).toBeNull();
  });

  test("sleepDurationHrs carries agg (no n -- nothing to count) regardless of which tier wins", () => {
    const v = resolveVectors(null, gen3({
      sleep_duration_hrs: 7.5, sleep_duration_agg: "onboard_summary",
    }, { sleep_data_ts: NOW }), {});
    expect(v.sleepDurationHrs.agg).toBe("onboard_summary");
    expect(v.sleepDurationHrs.n).toBeUndefined();
  });

  test("a stale (>24h) bridge resolves n/agg to null along with value, not independently fresh", () => {
    const veryOld = new Date(Date.now() - 25 * 3600 * 1000).toISOString();
    const v = resolveVectors(null, gen3({ rhr_bpm: 62, rhr_n: 489, rhr_agg: "session_mean" },
      { timestamp: veryOld }), {});
    expect(v.rhr.value).toBeNull();
    expect(v.rhr.n).toBeNull();
    expect(v.rhr.agg).toBeNull();
  });
});

describe("resolveVector() -- priority-ordered candidate array", () => {
  test("first non-null candidate wins, regardless of array length", () => {
    const v = resolveVector([
      { value: null, source: "a" },
      { value: null, source: "b" },
      { value: 42, source: "c" },
      { value: 99, source: "d" },
    ]);
    expect(v).toEqual({ value: 42, source: "c", ready: true });
  });

  test("a fourth candidate slots in ahead of existing ones without touching resolveVector itself", () => {
    // Simulates adding a new instrument with higher priority than gen4/gen3/manual --
    // the function takes whatever array it's given; this only changes at the call site.
    const v = resolveVector([
      { value: 7.1, source: "new_instrument" },
      { value: 50, source: SOURCE_GEN4 },
      { value: 48, source: "gen3_ble" },
      { value: 45, source: "manual" },
    ]);
    expect(v).toEqual({ value: 7.1, source: "new_instrument", ready: true });
  });

  test("all-null candidates resolve to a clean null vector, not an error", () => {
    const v = resolveVector([{ value: null, source: "a" }, { value: null, source: "b" }]);
    expect(v).toEqual({ value: null, source: null, ready: false });
  });

  test("empty candidate array resolves to a clean null vector", () => {
    expect(resolveVector([])).toEqual({ value: null, source: null, ready: false });
  });
});
