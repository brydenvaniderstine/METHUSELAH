// METHUSELAH Source Selector
//
// Gen4 (Oura API) and Gen3 (BLE bridge) are the same hardware family —
// same sensors, same underlying vectors. This file is what makes them
// interchangeable: each vector is resolved independently from whichever
// source has fresh data, so the engine and the UI never need to know
// which ring produced a value.
//
// Priority per vector: Gen4 (fresh) -> Gen3 (fresh) -> manual -> null.
// A vector is null only when no source has data. Gen3 is only offered
// for a vector once its decoder is validated — see readiness notes below.
//
// Decoder readiness (see SESSION_HANDOFF.md for the latest status):
// - RHR: Gen3 READY (0x6A confirmed, cross-validated +/-1.1 bpm vs Gen4)
// - SpO2: Gen3 READY (0x6F confirmed — Track B condition #3 CLOSED 2026-07-08,
//   three consecutive nights within +/-5% gate: 1.9%, 4.5%, 3.2%). Resolved
//   below as telemetry only — there is no THRESHOLDS/COMMANDS entry for it,
//   so it does not participate in evaluate()'s priority cascade. Adding a
//   fifth command vector is a v3 discussion per the priority-order comment
//   in engine/index.js; this just makes the value/source interchangeable.
// - HRV: Gen3 NOT READY (0x5D does not fire reliably overnight)
// - Deep sleep: Gen3 NOT READY (0x6A has no sleep-stage breakdown yet)
// - Glucose: no wearable source on either generation — manual entry only

const FRESHNESS_WINDOW_MS = 24 * 60 * 60 * 1000;

export const SOURCE_GEN4 = "gen4_api";
export const SOURCE_GEN3 = "gen3_ble";
export const SOURCE_MANUAL = "manual";

function isFresh(timestamp) {
  if (!timestamp) return false;
  const age = Date.now() - new Date(timestamp).getTime();
  return age >= 0 && age < FRESHNESS_WINDOW_MS;
}

function resolveVector(gen4Value, gen3Value, manualValue) {
  if (gen4Value != null) return { value: gen4Value, source: SOURCE_GEN4, ready: true };
  if (gen3Value != null) return { value: gen3Value, source: SOURCE_GEN3, ready: true };
  if (manualValue != null) return { value: manualValue, source: SOURCE_MANUAL, ready: true };
  return { value: null, source: null, ready: false };
}

/**
 * Resolve the best available value for each engine vector.
 *
 * @param {Object|null} gen4 - Oura API state, shape { hrv, rhr, deepSleepPct, isLive, timestamp }
 * @param {Object|null} gen3 - Gen3 bridge JSON, shape { timestamp, vectors: { rhr_bpm, hrv_ms, deep_sleep_pct, ... } }
 * @param {Object} manual - manually entered values, shape { glucose }
 * @returns {{ glucose: Vector, hrv: Vector, rhr: Vector, deepSleepPct: Vector, spo2: Vector }}
 */
export function resolveVectors(gen4, gen3, manual = {}) {
  const gen4Fresh = gen4 && gen4.isLive && isFresh(gen4.timestamp) ? gen4 : null;
  const gen3Fresh = gen3 && isFresh(gen3.timestamp) ? gen3 : null;

  return {
    rhr: resolveVector(
      gen4Fresh?.rhr ?? null,
      gen3Fresh?.vectors?.rhr_bpm ?? null,
      null
    ),

    // Telemetry only — not a THRESHOLDS/COMMANDS vector, doesn't drive evaluate()
    spo2: resolveVector(
      gen4Fresh?.spo2 ?? null,
      gen3Fresh?.vectors?.spo2_avg_pct ?? null,
      null
    ),

    // Gen3 not offered — 0x5D overnight decoder incomplete
    hrv: resolveVector(gen4Fresh?.hrv ?? null, null, null),

    // Gen3 not offered — 0x6A has no sleep-stage breakdown yet
    deepSleepPct: resolveVector(gen4Fresh?.deepSleepPct ?? null, null, null),

    // No wearable source on either generation
    glucose: resolveVector(null, null, manual?.glucose ?? null),
  };
}
