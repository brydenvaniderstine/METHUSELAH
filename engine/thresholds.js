// Single source of truth for all numeric cutoffs.
// Tune values only in this file — never hardcode in web/ or pipeline/.

// Command thresholds — determine which protocol fires
export const THRESHOLDS = {
  glucose:   5.8,  // mmol/L — fast if above
  hrv:       25,   // ms — personal baseline −1SD (355-night avg 29.3ms); personalised to this user
  rhr:       63,   // bpm — active recovery if above
  sleepDurationWarn: 7,     // hrs — below this: yellow (sleep protocol tonight)
  sleepDurationCritical: 4, // hrs — below this: red (acute deficit)
};

// BRI scoring brackets — determine the readiness index score
export const BRI_BRACKETS = {
  glucose:       { optimal: 5.0, nominal: 5.8 }, // < optimal → 25pts, <= nominal → 15pts
  hrv:           { optimal: 55,  nominal: 22  },  // >= optimal → 25pts, >= nominal → 15pts
  rhr:           { optimal: 50,  nominal: 63  },  // < optimal → 25pts, <= nominal → 15pts
  sleepDuration: { optimal: 7,   nominal: 4   },  // >= 7h → 25pts (green), >= 4h → 15pts (yellow), < 4h → 0pts (red)
};

// Comparison direction for each threshold above -- a separate, small table,
// not a reshape of THRESHOLDS itself. THRESHOLDS.rhr etc. are read as plain
// numbers in ~29 places across engine/index.js, its own tests, and
// web/src/App.js; reshaping to {value, operator} would touch every one of
// them. This adds the one new fact (direction) the UI needs to render the
// literal predicate ("RHR > 63") without touching anything that already
// works. 2026-08-21.
export const THRESHOLD_OPERATORS = {
  glucose:               ">",
  hrv:                   "<",
  rhr:                   ">",
  sleepDurationWarn:     "<",
  sleepDurationCritical: "<",
};

// BRI score → label + color mapping
export const BRI_LEVELS = [
  { min: 85, label: "OPTIMAL",                color: "#00aaff" },
  { min: 70, label: "NOMINAL",                color: "#00ff66" },
  { min: 50, label: "MODERATE SUPPRESSION",   color: "#ffb300" },
  { min: 25, label: "SIGNIFICANT SUPPRESSION", color: "#ff2a2a" },
  { min: 0,  label: "CRITICAL",               color: "#cc0000" },
];
