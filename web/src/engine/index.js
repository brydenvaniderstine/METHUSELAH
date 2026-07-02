// PRIORITY ORDER — when multiple vectors breach simultaneously,
// only the highest-priority command fires. Order is deliberate:
// 1. Glucose — acute metabolic signal, highest priority
// 2. HRV — cardiovascular recovery
// 3. RHR — secondary cardiovascular signal
// 4. Deep sleep — recovery quality
// To change priority, reorder the if-blocks below. Do not add
// a multi-command output without a v3 architecture discussion first.

import { THRESHOLDS, BRI_BRACKETS, BRI_LEVELS } from "./thresholds.js";
import { COMMANDS } from "./commands.js";

export { THRESHOLDS, BRI_BRACKETS, BRI_LEVELS, COMMANDS };

// evaluate(vectors) — main entry point for web/src/App.js
// vectors: { glucose, hrv, rhr, deepSleepPct }
// Returns a logic object identical in shape to what App.js previously built inline.
export function evaluate(vectors) {
  const { glucose, hrv, rhr, deepSleepPct } = vectors;

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

  if (deepSleepPct !== null && deepSleepPct < THRESHOLDS.deepSleep) {
    return {
      ...COMMANDS.deepSleep,
      rat: COMMANDS.deepSleep.rat(deepSleepPct),
      briefing: COMMANDS.deepSleep.briefing(deepSleepPct, THRESHOLDS.deepSleep),
    };
  }

  return {
    ...COMMANDS.nominal,
    rat: COMMANDS.nominal.rat,
    briefing: COMMANDS.nominal.briefing(),
  };
}

// calculateBRI(vectors) — Biological Readiness Index
// Returns { score, label, color } — identical output to the old inline calculateBRI in App.js.
export function calculateBRI({ glucose, hrv, rhr, deepSleepPct, glucosePending }) {
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

  if (deepSleepPct === null)                      { score += 15; }
  else if (deepSleepPct >= b.deepSleep.optimal)   { score += 25; }
  else if (deepSleepPct >= b.deepSleep.nominal)   { score += 15; }

  const level = BRI_LEVELS.find(l => score >= l.min) || BRI_LEVELS[BRI_LEVELS.length - 1];
  return { score, label: level.label, color: level.color };
}
