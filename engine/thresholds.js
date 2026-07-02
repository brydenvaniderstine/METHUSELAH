// Single source of truth for all numeric cutoffs.
// Tune values only in this file — never hardcode in web/ or pipeline/.

// Command thresholds — determine which protocol fires
export const THRESHOLDS = {
  glucose:   5.8,  // mmol/L — fast if above
  hrv:       22,   // ms — Zone 2 if below
  rhr:       63,   // bpm — active recovery if above
  deepSleep: 12,   // % — sleep protocol if below
};

// BRI scoring brackets — determine the readiness index score
export const BRI_BRACKETS = {
  glucose: { optimal: 5.0, nominal: 5.8 },   // < optimal → 25pts, <= nominal → 15pts
  hrv:     { optimal: 55,  nominal: 22  },    // >= optimal → 25pts, >= nominal → 15pts
  rhr:     { optimal: 50,  nominal: 63  },    // < optimal → 25pts, <= nominal → 15pts
  deepSleep: { optimal: 20, nominal: 12 },    // >= optimal → 25pts, >= nominal → 15pts
};

// BRI score → label + color mapping
export const BRI_LEVELS = [
  { min: 85, label: "OPTIMAL",                color: "#00aaff" },
  { min: 70, label: "NOMINAL",                color: "#00ff66" },
  { min: 50, label: "MODERATE SUPPRESSION",   color: "#ffb300" },
  { min: 25, label: "SIGNIFICANT SUPPRESSION", color: "#ff2a2a" },
  { min: 0,  label: "CRITICAL",               color: "#cc0000" },
];
