// Single source of truth for all user-facing command strings and rationale templates.
// Never hardcode these in web/ — import from here only.

export const COMMANDS = {
  glucose: {
    name:    "24-HOUR WATER FAST",
    cmd:     "INITIATE 24-HOUR WATER FAST.",
    rat:     (value) => `GLYCEMIC FRICTION DETECTED (${value.toFixed(1)} MMOL/L).`,
    color:   "var(--accent-red)",
    border:  "var(--accent-red)",
    level:   "critical",
    briefing: (value, threshold) =>
      `Your fasting glucose read ${value.toFixed(1)} mmol/L, above your threshold of ${threshold} mmol/L. A 24-hour fast resets insulin sensitivity and brings glucose back into range.`,
  },
  hrv: {
    name:    "ZONE 2 OUTPUT",
    cmd:     "EXECUTE 45-MIN ZONE 2 OUTPUT.",
    rat:     (value) => `AUTONOMIC STRESS DETECTED (${Math.round(value)} MS HRV).`,
    color:   "var(--text-main)",
    border:  "var(--accent-amber)",
    level:   "warn",
    briefing: (value, threshold) =>
      `Your HRV read ${Math.round(value)}ms, below your threshold of ${threshold}ms. Zone 2 training stimulates parasympathetic recovery and rebuilds HRV over time.`,
  },
  rhr: {
    name:    "ACTIVE RECOVERY PROTOCOL",
    cmd:     "INITIATE ACTIVE RECOVERY PROTOCOL.",
    rat:     (value) => `CARDIAC LOAD ELEVATED (${value} BPM RHR).`,
    color:   "var(--text-main)",
    border:  "var(--accent-amber)",
    level:   "warn",
    briefing: (value, threshold) =>
      `Your resting heart rate read ${value} bpm, above your threshold of ${threshold} bpm. Active recovery — light movement, no training load — allows your cardiovascular system to reset.`,
  },
  sleepDuration: {
    name:    "SLEEP PROTOCOL",
    cmd:     "INITIATE SLEEP PROTOCOL TONIGHT.",
    rat:     (value) => `SLEEP DEBT DEFICIENT (${value.toFixed(1)}H LAST NIGHT).`,
    color:   "var(--text-main)",
    border:  "var(--accent-amber)",
    level:   "warn",
    briefing: (value, threshold) =>
      `You slept ${value.toFixed(1)} hours last night, below your threshold of ${threshold}h. Follow the sleep protocol tonight to restore recovery and hormonal repair.`,
  },
  nominal: {
    name:    "",
    cmd:     "BIOLOGY OPTIMAL.",
    rat:     "",
    color:   "var(--text-main)",
    border:  "var(--accent-green)",
    level:   "optimal",
    briefing: () => "All four vectors are within range. No action required today.",
  },
  awaitingTelemetry: {
    name:    "",
    cmd:     "AWAITING TELEMETRY.",
    rat:     "",
    color:   "var(--text-dim)",
    border:  "var(--text-dim)",
    level:   "awaiting",
    briefing: () => "No data from any source yet. Connect Oura or bring the Gen3 ring into Bluetooth range.",
  },
};
