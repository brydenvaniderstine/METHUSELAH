// PRIORITY ORDER — when multiple vectors breach simultaneously,
// only the highest-priority command fires. Order is deliberate:
// 1. Glucose — acute metabolic signal, highest priority
// 2. HRV — cardiovascular recovery
// 3. RHR — secondary cardiovascular signal
// 4. Sleep duration — recovery quantity (replaces deep sleep % 2026-07-13)
// To change priority, reorder the if-blocks below. Do not add
// a multi-command output without a v3 architecture discussion first.

import { THRESHOLDS, BRI_BRACKETS, BRI_LEVELS } from "./thresholds.js";
import { COMMANDS } from "./commands.js";
import { resolveVectors, SOURCE_GEN4, SOURCE_GEN3, SOURCE_MANUAL } from "./sources.js";

export { THRESHOLDS, BRI_BRACKETS, BRI_LEVELS, COMMANDS, resolveVectors, SOURCE_GEN4, SOURCE_GEN3, SOURCE_MANUAL };

// evaluate(vectors) — main entry point for web/src/App.js
// vectors: { glucose, hrv, rhr, sleepDurationHrs }
// Returns a logic object identical in shape to what App.js previously built inline.
export function evaluate(vectors) {
  const { glucose, hrv, rhr, sleepDurationHrs } = vectors;

  if (glucose !== null && glucose > THRESHOLDS.glucose) {
    return {
      ...COMMANDS.glucose,
      rat: COMMANDS.glucose.rat(glucose),
      briefing: COMMANDS.glucose.briefing(glucose, THRESHOLDS.glucose),
    };
  }

  if (hrv !== null && hrv < THRESHOLDS.hrv) {
    return {
      ...COMMANDS.hrv,
      rat: COMMANDS.hrv.rat(hrv),
      briefing: COMMANDS.hrv.briefing(hrv, THRESHOLDS.hrv),
    };
  }

  if (rhr !== null && rhr > THRESHOLDS.rhr) {
    return {
      ...COMMANDS.rhr,
      rat: COMMANDS.rhr.rat(rhr),
      briefing: COMMANDS.rhr.briefing(rhr, THRESHOLDS.rhr),
    };
  }

  if (sleepDurationHrs !== null && sleepDurationHrs < THRESHOLDS.sleepDuration) {
    return {
      ...COMMANDS.sleepDuration,
      rat: COMMANDS.sleepDuration.rat(sleepDurationHrs),
      briefing: COMMANDS.sleepDuration.briefing(sleepDurationHrs, THRESHOLDS.sleepDuration),
    };
  }

  // No vector triggered a command above. If that's because every vector is
  // null (no source at all, not just in-range), say so instead of claiming
  // biology is optimal on zero data.
  if (glucose === null && hrv === null && rhr === null && sleepDurationHrs === null) {
    return {
      ...COMMANDS.awaitingTelemetry,
      rat: COMMANDS.awaitingTelemetry.rat,
      briefing: COMMANDS.awaitingTelemetry.briefing(),
    };
  }

  return {
    ...COMMANDS.nominal,
    rat: COMMANDS.nominal.rat,
    briefing: COMMANDS.nominal.briefing(),
  };
}

// evaluateSources(gen4, gen3, manual) — Gen3/Gen4 interchangeable-input entry point.
// Resolves each vector to its best available source via resolveVectors(), then
// runs the same evaluate() used everywhere else. Adds `vectors` to the result —
// the resolved { value, source, ready } per vector — so callers (e.g. the UI)
// can show which ring backed each value without duplicating resolution logic.
export function evaluateSources(gen4, gen3, manual = {}) {
  const vectors = resolveVectors(gen4, gen3, manual);
  const logic = evaluate({
    glucose: vectors.glucose.value,
    hrv: vectors.hrv.value,
    rhr: vectors.rhr.value,
    sleepDurationHrs: vectors.sleepDurationHrs.value,
  });
  return { ...logic, vectors };
}

// calculateBRI(vectors) — Biological Readiness Index
// Returns { score, label, color } — identical output to the old inline calculateBRI in App.js.
export function calculateBRI({ glucose, hrv, rhr, sleepDurationHrs, glucosePending }) {
  let score = 0;
  const b = BRI_BRACKETS;

  if (glucosePending) {
    score += 15;
  } else if (glucose < b.glucose.optimal) {
    score += 25;
  } else if (glucose <= b.glucose.nominal) {
    score += 15;
  }

  if (hrv === null)                { score += 15; }
  else if (hrv >= b.hrv.optimal)   { score += 25; }
  else if (hrv >= b.hrv.nominal)   { score += 15; }

  if (rhr === null)                { score += 15; }
  else if (rhr < b.rhr.optimal)    { score += 25; }
  else if (rhr <= b.rhr.nominal)   { score += 15; }

  if (sleepDurationHrs === null)                             { score += 15; }
  else if (sleepDurationHrs >= b.sleepDuration.optimal)     { score += 25; }
  else if (sleepDurationHrs >= b.sleepDuration.nominal)     { score += 15; }

  const level = BRI_LEVELS.find(l => score >= l.min) || BRI_LEVELS[BRI_LEVELS.length - 1];
  return { score, label: level.label, color: level.color };
}
