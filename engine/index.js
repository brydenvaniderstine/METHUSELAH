// PRIORITY ORDER — when multiple vectors breach simultaneously,
// only the highest-priority command fires. Order is deliberate:
// 1. Glucose — acute metabolic signal, highest priority
// 2. HRV — cardiovascular recovery
// 3. RHR — secondary cardiovascular signal
// 4. Deep sleep — recovery quality
// To change priority, reorder the if-blocks below. Do not add
// a multi-command output without a v3 architecture discussion first.

// ── THRESHOLDS ────────────────────────────────────────────────────────────────
// All numeric cutoffs live here. Tune only in this file.
// TODO: pull exact values from web/src/App.js L278–294 and L640–658 during engine build session.
const THRESHOLDS = {
  glucose: null,   // fill from App.js
  hrv:     null,   // fill from App.js
  rhr:     null,   // fill from App.js
  deepSleep: null, // fill from App.js
};

// ── COMMANDS ──────────────────────────────────────────────────────────────────
// All user-facing command strings live here. Never inline these in web/.
// TODO: pull exact strings from web/src/App.js L484–525 during engine build session.
const COMMANDS = {
  glucose: { command: null, briefing: null },
  hrv:     { command: null, briefing: null },
  rhr:     { command: null, briefing: null },
  deepSleep: { command: null, briefing: null },
};

// ── EVALUATE ──────────────────────────────────────────────────────────────────
// Main entry point. Takes a vectors object with the four biomarker readings.
// Returns a { command, briefing } object. Never returns null.
export function evaluate(vectors) {
  if (vectors.glucose > THRESHOLDS.glucose) {
    return {
      command: COMMANDS.glucose.command,
      briefing: COMMANDS.glucose.briefing,
    };
  }

  if (vectors.hrv < THRESHOLDS.hrv) {
    return {
      command: COMMANDS.hrv.command,
      briefing: COMMANDS.hrv.briefing,
    };
  }

  if (vectors.rhr > THRESHOLDS.rhr) {
    return {
      command: COMMANDS.rhr.command,
      briefing: COMMANDS.rhr.briefing,
    };
  }

  if (vectors.deepSleep < THRESHOLDS.deepSleep) {
    return {
      command: COMMANDS.deepSleep.command,
      briefing: COMMANDS.deepSleep.briefing,
    };
  }

  return {
    command: "ALL VECTORS NOMINAL",
    briefing: "All four vectors are within range. No action required today.",
  };
}
