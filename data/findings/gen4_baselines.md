# Gen4 Official App — Personal Baseline Reference

**Source:** `data/reference/gen4_official_trends_2025-06-14_2026-06-07.csv`
**Coverage:** 2025-06-14 → 2026-06-07 (359 nights, 0 gaps within range)
**Purpose:** Ground truth reference for validating Gen3 decoded values. Any Gen3
measurement that falls outside the personal percentile bands below should be flagged
as either a decode error or a genuine physiological outlier.

**Critical gap:** This export ends 2026-06-07. All Gen3 pulls from 2026-06-28 onward
fall outside this window — no same-night Gen4 cross-validation is possible from this
file. Future exports will be needed to close the gap.

---

## Cardiovascular

| Metric | Mean ± SD | p5 | p25 | p50 | p75 | p95 | Range |
|---|---|---|---|---|---|---|---|
| Average RHR (bpm) | 63.1 ± 5.6 | 54.8 | 59.2 | 62.3 | 66.5 | 72.9 | 52–87 |
| Lowest RHR (bpm) | 54.7 ± 3.9 | 49 | 52 | 54 | 56.5 | 61 | 45–76 |
| Average HRV (ms) | 29.3 ± 7.7 | 18 | 24 | 29 | 35 | 43 | 10–52 |

**Decoder context:**
- Gen3 0x6A `avg_hr` field decodes as `p[0] × 0.5`. Typical decoded values 54–56 bpm
  during confirmed sleep pulls land at the p50 of Lowest RHR — consistent.
- Gen3 0x5D HRV events produce RMSSD values; Gen4 "Average HRV" is also RMSSD-based.
  When the 0x5D decoder is validated, expect values in the 24–35ms range (p25–p75)
  on a typical night. Nights below 18ms (p5) indicate suppressed HRV — sickness,
  heavy alcohol, or overtraining.
- The 54bpm Lowest RHR on the 2026-06-28 cross-validation night sits exactly at p50
  (median for this person), confirming it was a physiologically unremarkable night for HR.

---

## Respiratory Rate

| Metric | Mean ± SD | p5 | p25 | p50 | p75 | p95 | Range |
|---|---|---|---|---|---|---|---|
| Respiratory Rate (breaths/min) | 13.09 ± 0.43 | 12.5 | 12.75 | 13.1 | 13.4 | 13.8 | 12.0–15.1 |

**Decoder context:**
- This is Bryden's tightest metric (SD = 0.43 breaths/min). A decoded Gen3 respiratory
  rate outside 12.0–14.0 breaths/min would be a strong signal of either a decode error
  or genuine pathology. The 13.2 breaths/min on 2026-06-28 is exactly at p50.
- No Gen3 respiratory rate decoder identified yet — when one is found, validate first
  against this narrow band.

---

## Temperature

| Metric | Mean ± SD | p5 | p25 | p50 | p75 | p95 | Range |
|---|---|---|---|---|---|---|---|
| Temp Deviation (°C) | +0.04 ± 0.41 | −0.53 | −0.21 | +0.08 | +0.29 | +0.60 | −1.35–+2.59 |

**Decoder context:**
- Gen3 0x75 skin temp during sleep: 34.88–35.26°C confirmed on 2026-06-28. This is
  the absolute skin reading; Gen4 reports a deviation from a rolling baseline.
- The +2.59°C deviation on 2025-12-20 (illness event) is the largest in 359 nights.
  If a Gen3 pull coincides with a similar event, the 0x75 values should be elevated
  above the typical 34.9–35.3°C baseline by a proportional amount.
- Deviation baseline (p50 = +0.08°C) is essentially zero, confirming Gen4's rolling
  reference tracks absolute skin temp tightly.

---

## Sleep Architecture

| Metric | Mean ± SD | p5 | p25 | p50 | p75 | p95 | Range |
|---|---|---|---|---|---|---|---|
| Total Sleep (h) | 7.76 ± 1.13 | 5.89 | 7.05 | 7.66 | 8.50 | 9.62 | 3.86–10.83 |
| Light Sleep (min) | 279 ± 50 | 197 | 248 | 279 | 311 | 360 | 114–420 |
| Deep Sleep (min) | 75 ± 20 | 45 | 61 | 75 | 88 | 107 | 30–149 |
| REM Sleep (min) | 111 ± 27 | 68 | 93 | 111 | 130 | 153 | 21–198 |
| Awake Time (min) | 77 ± 37 | 38 | 53 | 68 | 85 | 151 | 21–271 |
| Sleep Efficiency (%) | 86.1 ± 5.4 | 75 | 84.5 | 87 | 90 | 92 | 60–95 |
| Sleep Latency (min) | 16.0 ± 11.3 | 4 | 8.5 | 14 | 20 | 37.2 | 0.5–108.5 |
| Restless Sleep (events) | 297 ± 75 | 191 | 246 | 291 | 339 | 429 | 104–625 |

**Stage composition (% of total sleep):**
- Light: 60.0%
- Deep: 16.2%
- REM: 23.8%

**Decoder context:**
- Gen3 0x6A `sleep_state` decoder currently returns state=1 for all samples on the
  only cross-validated night (2026-06-28). Gen4 shows 29% REM / 52% Light / 19% Deep
  that same night — confirming the sleep_state decoder has a gap (see known_issues.md).
- The 255-event buffer holds ~10 0x6A samples per pull. These sample a small window;
  they will not sum to the Gen4 totals. Use Gen4 stage durations as ground truth for
  stage decoder validation, not as a per-pull comparison target.
- When the sleep_state decoder is fixed, expect stage distribution to roughly match
  the 60/16/24 Light/Deep/REM split across many nights.

---

## Scores

| Metric | Mean ± SD | p5 | p25 | p50 | p75 | p95 | Range |
|---|---|---|---|---|---|---|---|
| Sleep Score | 81.7 ± 7.9 | 68 | 78 | 83 | 87 | 92 | 31–96 |
| Readiness Score | 78.5 ± 9.2 | 62 | 74 | 80 | 84 | 90 | 29–95 |
| Activity Score | 66.5 ± 13.4 | 50 | 54 | 64 | 79 | 89 | 44–99 |

---

## Activity

| Metric | Mean ± SD | p50 | p95 | Range |
|---|---|---|---|---|
| Steps | 6,296 ± 3,471 | 6,103 | 13,184 | 6–19,635 |

---

## Monthly Trends

### HRV (ms)
| Month | Mean | SD | n |
|---|---|---|---|
| 2025-06 | 27.2 | 4.4 | 17 |
| 2025-07 | 30.7 | 8.8 | 31 |
| 2025-08 | 32.0 | 7.0 | 31 |
| 2025-09 | **37.3** | 7.7 | 30 |
| 2025-10 | 32.7 | 7.8 | 31 |
| 2025-11 | 30.2 | 9.3 | 30 |
| 2025-12 | 26.1 | 6.4 | 29 |
| 2026-01 | 27.1 | 9.0 | 30 |
| 2026-02 | 26.1 | 4.5 | 28 |
| 2026-03 | 28.7 | 5.5 | 30 |
| 2026-04 | 28.5 | 5.5 | 30 |
| 2026-05 | 24.1 | 4.3 | 31 |
| 2026-06 | 26.3 | 5.7 | 7 |

### Average RHR (bpm)
| Month | Mean | SD | n |
|---|---|---|---|
| 2025-06 | 61.4 | 2.3 | 17 |
| 2025-07 | 61.3 | 5.5 | 31 |
| 2025-08 | 60.3 | 4.2 | 31 |
| 2025-09 | **57.3** | 4.6 | 30 |
| 2025-10 | 62.0 | 5.7 | 31 |
| 2025-11 | 65.1 | 7.2 | 30 |
| 2025-12 | 66.0 | 6.3 | 29 |
| 2026-01 | 65.3 | 7.2 | 30 |
| 2026-02 | 65.3 | 2.7 | 28 |
| 2026-03 | 62.6 | 3.6 | 30 |
| 2026-04 | 64.8 | 4.4 | 30 |
| 2026-05 | 65.3 | 4.1 | 31 |
| 2026-06 | 62.7 | 3.1 | 7 |

**Seasonal pattern:** Peak cardiovascular fitness visible in September 2025 (HRV=37.3ms,
RHR=57.3bpm). Winter decline Nov 2025–Feb 2026 (HRV drops to 26ms, RHR rises to 65bpm).
This matters for decoder validation: a Gen3 pull from Sep 2025 would show lower HR and
higher HRV than one from Jan 2026 — both correct, not a decode error.

---

## Notable Outlier Nights

These are the highest-signal dates for cross-validation — nights where physiology was
extreme enough that Gen3 decoded values should show clear deviation from baseline.

### December 2025 illness cluster (highest-priority retrospective target)
| Date | HRV (ms) | Temp Dev (°C) | Readiness | Restless |
|---|---|---|---|---|
| 2025-12-19 | 22 | n/a | 60 | **624** |
| 2025-12-20 | **10** | **+2.59** | **29** | 443 |
| 2025-12-21 | 16 | +1.36 | 39 | 470 |
| 2025-12-22 | 20 | +0.76 | 44 | — |
| 2025-12-28 | 16 | +0.44 | 68 | **625** |

2025-12-20 is the most extreme night in the dataset: HRV crashed to 10ms (p<1%), temp
deviation +2.59°C (absolute max), readiness=29 (absolute min). If Gen3 flash logs
from this night still exist (via boot_ts alignment), they would be the best possible
test of whether Gen3 physiological decoders track real illness signals.

### Peak recovery nights (Sep 2025)
| Date | HRV (ms) | RHR (bpm) | Sleep (h) |
|---|---|---|---|
| 2025-09-22 | **52** | — | — |
| 2025-09-04 | 49 | — | — |
| 2025-09-02 | 48 | — | — |
| 2025-10-06 | 48 | — | — |
| 2025-11-03 | 48 | — | — |

These nights represent peak cardiovascular state. Gen3 HRV events from a nearby pull
should show elevated RMSSD values — useful for validating the upper end of the decoder.

### Longest sleep nights (most Gen3 data density)
| Date | Total Sleep (h) |
|---|---|
| 2025-12-28 | 10.8 |
| 2026-01-02 | 10.5 |
| 2025-09-15 | 10.5 |
| 2025-10-18 | 10.3 |

Longer sleep = more events in the Gen3 flash buffer = richer pulls. If a retrospective
pull is possible (via boot_ts alignment to a past flash window), these are the best
candidates for stage-distribution cross-validation.

---

## Cross-Validation Status

| Night | Gen3 pull | Gen4 data in CSV | Cross-validated |
|---|---|---|---|
| 2026-06-28 | Yes (partial — missed sleep window) | **No** (export ends 2026-06-07) | Partial (manual Gen4 screenshot only) |
| 2026-06-29 | Yes (pre-bed, post-workout) | **No** | No |
| 2026-06-30 | Yes (morning, active window) | **No** | No |

**Action required:** Export a fresh Gen4 CSV covering 2026-06-08 onward to enable
same-night cross-validation for the June 2026 pull set.

*Logged 2026-06-30.*
