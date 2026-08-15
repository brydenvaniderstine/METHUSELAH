// Regression tests for evaluate() and calculateBRI().
//
// Lives here (not directly in web/src/engine/) so it flows through the same
// `cp ../engine/*.js src/engine/` sync (web/package.json prestart/prebuild)
// as thresholds.js/commands.js/sources.js/index.js themselves -- never
// hand-duplicated, never able to drift from what it's actually testing.
//
// Run: cd web && CI=true npx react-scripts test src/engine --watchAll=false
// (after the sync step has copied this file into src/engine/).

import { evaluate, calculateBRI, THRESHOLDS, BRI_LEVELS } from "./index.js";

const OK = { glucose: 4.0, hrv: 50, rhr: 55, sleepDurationHrs: 8.0 };

// Real name/cmd strings verified directly against engine/commands.js before
// writing these -- nominal and awaitingTelemetry both have name: "", so
// `level`/`cmd` are what actually distinguish every state here, not `name`.
describe("evaluate() priority order", () => {
  test("glucose outranks everything, even when hrv/rhr/sleep are also breached", () => {
    const logic = evaluate({ glucose: THRESHOLDS.glucose + 1, hrv: 1, rhr: 999, sleepDurationHrs: 0.1 });
    expect(logic.name).toBe("24-HOUR WATER FAST");
  });

  test("hrv outranks rhr and sleep when glucose is clean", () => {
    const logic = evaluate({ ...OK, hrv: THRESHOLDS.hrv - 1, rhr: 999, sleepDurationHrs: 0.1 });
    expect(logic.name).toBe("ZONE 2 OUTPUT");
  });

  test("rhr outranks sleep when glucose/hrv are clean", () => {
    const logic = evaluate({ ...OK, rhr: THRESHOLDS.rhr + 1, sleepDurationHrs: 0.1 });
    expect(logic.name).toBe("ACTIVE RECOVERY PROTOCOL");
  });

  test("sleepDurationCritical outranks sleepDurationWarn on the same low value", () => {
    const logic = evaluate({ ...OK, sleepDurationHrs: THRESHOLDS.sleepDurationCritical - 0.5 });
    expect(logic.level).toBe("critical");
    expect(logic.name).toBe("SLEEP PROTOCOL");
  });

  test("sleepDurationWarn fires in the warn band, not critical", () => {
    const logic = evaluate({
      ...OK,
      sleepDurationHrs: (THRESHOLDS.sleepDurationCritical + THRESHOLDS.sleepDurationWarn) / 2,
    });
    expect(logic.level).toBe("warn");
    expect(logic.name).toBe("SLEEP PROTOCOL");
  });

  test("nominal fires when nothing is breached but data exists", () => {
    const logic = evaluate(OK);
    expect(logic.cmd).toBe("BIOLOGY OPTIMAL.");
    expect(logic.level).toBe("optimal");
  });

  test("awaitingTelemetry fires only when ALL FOUR vectors are null", () => {
    const logic = evaluate({ glucose: null, hrv: null, rhr: null, sleepDurationHrs: null });
    expect(logic.cmd).toBe("AWAITING TELEMETRY.");
    expect(logic.level).toBe("awaiting");
  });

  test("one live vector (e.g. rhr) is enough to avoid awaitingTelemetry", () => {
    const logic = evaluate({ glucose: null, hrv: null, rhr: 55, sleepDurationHrs: null });
    expect(logic.level).not.toBe("awaiting");
  });
});

describe("evaluate() boundary conditions -- thresholds.js comparisons are strict, not inclusive", () => {
  test("glucose exactly at threshold does not fire (uses >)", () => {
    const logic = evaluate({ ...OK, glucose: THRESHOLDS.glucose });
    expect(logic.name).not.toBe("24-HOUR WATER FAST");
  });

  test("hrv exactly at threshold does not fire (uses <)", () => {
    const logic = evaluate({ ...OK, hrv: THRESHOLDS.hrv });
    expect(logic.level).toBe("optimal");
  });

  test("rhr exactly at threshold does not fire (uses >)", () => {
    const logic = evaluate({ ...OK, rhr: THRESHOLDS.rhr });
    expect(logic.level).toBe("optimal");
  });

  test("sleepDurationWarn exactly at threshold does not fire (uses <)", () => {
    const logic = evaluate({ ...OK, sleepDurationHrs: THRESHOLDS.sleepDurationWarn });
    expect(logic.level).toBe("optimal");
  });
});

describe("calculateBRI()", () => {
  test("all-optimal vectors score 100 and land in the top band", () => {
    const bri = calculateBRI({ glucose: 4.0, hrv: 60, rhr: 45, sleepDurationHrs: 8, glucosePending: false });
    expect(bri.score).toBe(100);
    expect(bri.label).toBe(BRI_LEVELS[0].label); // "OPTIMAL"
  });

  test("total blackout (all four vectors absent) reports awaiting telemetry, not a fabricated score", () => {
    // 2026-08-15: previously scored 60 (4 x 15) and landed in "MODERATE
    // SUPPRESSION" -- a missing sync rendering as a biological finding.
    // Matches evaluate()'s own AWAITING TELEMETRY branch for the same
    // all-null condition.
    const bri = calculateBRI({ glucose: null, hrv: null, rhr: null, sleepDurationHrs: null, glucosePending: true });
    expect(bri.score).toBeNull();
    expect(bri.label).toBe("AWAITING TELEMETRY");
  });

  test("partial data (three of four vectors present) still scores normally, only the blackout case is special-cased", () => {
    const bri = calculateBRI({ glucose: 4.0, hrv: 60, rhr: 45, sleepDurationHrs: null, glucosePending: false });
    expect(bri.score).toBe(90); // 25 + 25 + 25 + 15 (null sleep)
    expect(bri.label).not.toBe("AWAITING TELEMETRY");
  });

  test("all-worst vectors score 0 and land in the bottom band", () => {
    const bri = calculateBRI({ glucose: 10, hrv: 10, rhr: 90, sleepDurationHrs: 2, glucosePending: false });
    expect(bri.score).toBe(0);
    expect(bri.label).toBe(BRI_LEVELS[BRI_LEVELS.length - 1].label); // "CRITICAL"
  });

  test("a mixed-band example lands in NOMINAL, not OPTIMAL", () => {
    // glucose optimal(+25) + hrv nominal-only(+15) + rhr nominal-only(+15) + sleep optimal(+25) = 80
    const bri = calculateBRI({ glucose: 4.0, hrv: 30, rhr: 60, sleepDurationHrs: 8, glucosePending: false });
    expect(bri.score).toBe(80);
    expect(bri.label).toBe("NOMINAL");
  });

  test("BRI score never depends on which ring/source produced the value", () => {
    // calculateBRI takes plain resolved numbers -- confirms it has no source-awareness
    // baked in that could silently treat a Gen3-derived reading differently.
    const a = calculateBRI({ glucose: 4.0, hrv: 50, rhr: 55, sleepDurationHrs: 8, glucosePending: false });
    const b = calculateBRI({ glucose: 4.0, hrv: 50, rhr: 55, sleepDurationHrs: 8, glucosePending: false });
    expect(a).toEqual(b);
  });
});
