# Fable investigation session — 2026-07-24

**Scope:** investigation only, per instruction — no decoder files, `known_issues.md`,
`open_ring_roadmap.md`, or commits touched this session. All analysis was run via
ad hoc scratch scripts (not saved to the repo) that import and reuse the real,
already-committed decoders (`pipeline/decoders/`) against the real corpus
(`pipeline/data/raw_pulls/`) — nothing here is simulated or assumed. Read
`open_ring_roadmap.md`, `known_issues.md` (all 7,578 lines), `SESSION_HANDOFF.md`,
and `max86171_register_reference.md` in full before starting. Builds directly on
top of the **2026-07-24 (earlier session today)** work already committed — that
session already fixed a real `complete`-flag bug in `0x5a.py`, found the
corpus-wide retransmission-duplication issue, tested and falsified an
0xFF-adjacent-to-stage-3-runs hypothesis, and corrected the 2026-07-21 "3 separate
nights" claim. This session does not repeat any of that — it starts from where it
left off and pushes further, per the instruction not to re-run already-falsified
tests.

---

## Item 1 — 0x5A stage-3 gap: PARTIALLY ADVANCED, not fully resolved, not exhausted

**Status answer up front, as instructed:** this is **partially advanced**. A
genuinely new, well-evidenced angle was found and confirmed two independent ways.
It does **not** resolve the byte-level mechanism (still don't know exactly how
stage 3 is encoded), so 0x5A stays PARTIAL — this is not a promotion candidate.
It is also not "exhausted" — the new finding below opens a concrete, specific
follow-up that a future session should run before concluding there's nothing left.

### What was tested and how

The earlier-today session already showed that the "0xFF bytes cluster near
stage-3 runs" hypothesis doesn't hold up, and that raw 0xFF-count correlates only
weakly with the gap once bout length is controlled for. The one angle that
session's own tool (`pipeline/tools/analyze_0x5a_stage3_gap.py`) could not test:
it groups bouts by their own last-chunk `boot_ts`, which treats every
cluster-firing as an independent data point — it has no way to tell that several
of those "independent" bouts are actually **repeated snapshots of the same
underlying bout as it grows across the night**.

This session decoded `0x76` (Bedtime period, `pipeline/decoders/0x76.py`
→ `decode_bedtime_period`) for every matched cluster and used its `start_ring_time`
field as the true bout identity (this is exactly the `a` field the
2026-07-19/20 `known_issues.md` entry already established as the per-bout
identifier — that finding was reused here, not re-derived). Grouping the existing
38 de-duplicated bouts by this `a` value gives **4 bouts with 2+ real growth
snapshots** (7, 5, 3, and 2 snapshots respectively) — i.e., the same bout observed
at multiple points as its chunk count grew from a handful of chunks up to as many
as 29.

### Finding: the stage-3 relative error is large and unstable in small/early
### bouts, and settles into a small, bounded band once a bout passes roughly
### 300 total epochs (~2.5h of accumulated sleep-classified time)

Three of the four growth series are "clean" (their stage 0/1/2 counts still
exact-match 0x4C, so they're not contaminated by the separate single-chunk
artifact in Item 2 below). All three show the same shape:

| bout (`a`=) | early snapshot \|gap\|/total_epochs | late snapshot \|gap\|/total_epochs |
|---|---|---|
| 75298085 (7 snapshots) | +4.85% (7 chunks, 268 epochs) | **-0.40%** (29 chunks, 1252 epochs) |
| 76149641 (5 snapshots) | -3.81% (10 chunks, 472 epochs) | **-1.24%** (17 chunks, 808 epochs) |
| 76992273 (3 snapshots) | +35.98% (5 chunks, 164 epochs) | **+0.38%** (17 chunks, 780 epochs) |

This isn't just a within-bout trend — it holds up independently across the full
31-bout clean cross-section (bouts that were only ever observed once, plus the
growth-series bouts, all together): mean `|gap|/total_epochs` is **24.2%** for
bouts under 300 total epochs (n=9) vs **2.3%** for bouts at or above 300 total
epochs (n=22) — roughly an **11x** difference. `corr(|gap|/total_epochs,
total_epochs) = -0.33`. Sorting all 31 clean bouts by size (full table saved in
this session's scratch output, reproducible from the method below) shows this
isn't a smooth continuous decay — it looks more like a **threshold/knee**: wild,
large relative error below roughly 300-400 total epochs (5-10 chunks), settling
into a consistent, bounded ~0-5% relative-error band above that, with no further
shrinking trend visible all the way out to 1252 epochs (29 chunks, the largest
bout in the corpus).

**Why this matters, precisely:** it reframes the open question. The stage-3 gap
isn't randomly distributed noise, and it isn't (per Item 1's earlier-today
falsification) explained by 0xFF bytes hugging stage-3 boundaries. It's
concentrated in **early/small bouts specifically** — consistent with either (a) a
real-time classifier that needs a runway before its stage-3 (deep sleep)
assessment stabilizes, which is exactly the kind of behavior the external
sleep-science literature review (`output/sleep-stage-science-ppg-hrv.md` in the
agent workspace — cited for context only, not decoder evidence) flagged as
plausible for wearable sleep classifiers generally, or (b) some artifact specific
to how 0x5A's own buffer is populated early in a bout (related to, but distinct
from, the padding issue in Item 2).

### Concrete next steps for a follow-up session

1. **Fold the `0x76` bout-grouping into `pipeline/tools/analyze_0x5a_stage3_gap.py`
   directly** (this session's version lives only in scratch, not committed —
   correctly, per this session's scope). Add a `decode_bedtime_period` pairing
   step exactly as described above, and print bouts grouped by `a` alongside the
   existing flat table. This makes the growth-series view available by default
   for the next session instead of requiring re-derivation.
2. **Get more growth-series data before concluding the "~300 epoch" threshold is
   real and not an artifact of n=4 series.** Every future daemon night adds more
   candidate growth series for free — this doesn't need a new experiment, just
   re-running the (updated) tool against a larger corpus.
3. **Test whether the threshold tracks epochs, chunks, or wall-clock time**
   — right now these are confounded (each chunk = exactly 4 epochs, so
   "epochs" and "chunks" are just linear rescalings of each other in this
   dataset). A genuinely distinguishing test isn't possible from this corpus
   alone; flag it as a known limitation of this finding rather than a next step
   requiring new data collection.
4. **Do not re-attempt the adjacency-to-0xFF or total-0xFF-count hypotheses**
   — both already tested today, both weak/falsified, see the earlier-today
   `known_issues.md` entry.

---

## Item 2 — stage-0 overcount / possible `0x00`-as-padding: ADVANCED, still unconfirmed

**Status:** the leading hypothesis got real, if incomplete, positional support.
Not promoted — no code changed this session.

The earlier-today session flagged that all 7 single-chunk (idx=0-only) bouts show
0x5A massively over-counting stage 0 relative to 0x4C, and speculated this might
be `0x00` bytes acting as a second, unrecognized "unwritten buffer padding"
sentinel (parallel to the already-known `0xFF` NO_DATA ambiguity), concentrated at
the *end* of a barely-started accumulator.

This session decoded the full epoch sequence for 4 of the 7 flagged bouts
directly (`boot_ts` 70071641, 70895250, 72627354, 74443656) and found a
**consistent structural pattern across all 4, not just the one case checked
earlier today**:

```
70071641: [None]×8  → [1,3,3,3,1,1,3,3] (8 real-looking epochs) → [0]×36 (rest of buffer)
70895250: [None]×8  → [3,3,0,3]         (4 real-looking epochs) → [0]×40
72627354: [None]×8  → (nothing)                                  → [0]×44
74443656: [None]×32 → [3,3,0,3]         (4 real-looking epochs) → [0]×16
```

Every one of the 4 checked follows the same shape: a leading run of `0xFF`
(NO_DATA), then a short burst of plausible mixed-stage activity, then a **long,
unbroken run of `0x00` all the way to the end of the transmitted chunk.** This is
the signature you'd expect from a firmware ring buffer that zero-initializes its
backing memory and has only written a handful of real epochs into a
freshly-started accumulator — the "real" data sits right after the no-data
header, and everything past it is unwritten, not 4×"WAKE."

**What this does NOT confirm:** whether *large, mature* bouts ever legitimately
end in a real trailing WAKE stretch that this same heuristic would wrongly
zero out — that's the actual risk of implementing this as a decode change, and
it wasn't checked this session (would need to look at bouts with a confirmed real
wake period at the very end of the transmitted buffer, which the current corpus
may or may not contain).

### Concrete next step for a follow-up session

In `pipeline/decoders/0x5a.py`, the current `decode()` treats a `0x00` byte
identically everywhere in the buffer. The specific, testable refinement: **a
trailing run of `0x00` bytes that extends to the very end of the reassembled
buffer (no non-zero byte after it) is a padding candidate; a `0x00` byte
anywhere else (i.e., followed by non-zero real data later in the same buffer) is
not.** Before changing the decoder: (a) check whether any bout in the corpus has
a confirmed-real trailing WAKE stretch (this would falsify the blanket
trailing-zero-as-padding rule), and (b) check whether reclassifying trailing
`0x00` as `NO_DATA` changes the stage-0 vs 0x4C match rate for the 7 flagged
bouts specifically (expected: should fix most/all of them, if the hypothesis is
right) without breaking the 31 bouts that already match exactly.

---

## Item 3 / Item 4 — other PARTIAL items and data-volume-blocked items

Read through every PARTIAL/IN PROGRESS entry in `open_ring_roadmap.md` and its
full history in `known_issues.md` before deciding where to spend time here.
Almost everything left in PARTIAL (`0x61/09` f2/f4, `0x4A`, `0x50`, `0x6C`,
`0x6D`, `0x72`, `0x73`, `0x77`, `0x61/28`, `0x61/33`) already has an explicit,
already-tested **firmware/datasheet ceiling** logged — `0x61/33` and `0x61/28`
were specifically tested against the real MAX86171 datasheet on 2026-07-21 and
partially falsified; re-testing any of these without new external reference
material would just reproduce that session's work. Per the instruction to skip
anything blocked on an external resource, none of these were re-opened.

**One item stood out as genuinely data-volume-blocked in a way that has now
changed, and it was not on anyone's radar for this reason:**

### 0x7E / 0x7F (real step features) — the "PARTIAL, needs a controlled walk"
### framing is stale; the daemon corpus already dwarfs it by ~1000x

The roadmap's stated next step for `0x7E`/`0x7F` is still "a controlled
fast-vs-slow walk experiment" (last attempted 2026-07-09, failed to capture any
data; a stationary "keep-warm" dry run on 2026-07-21 caught 13 pairs). That framing
predates the BLE daemon (built 2026-07-12) becoming the normal way this project
captures data. Checked directly: the 5 full overnight daemon logs on disk now
contain **10,664 to 25,672 `[Real step feature (1)]` packets each**
(`gen3_daemon_20260718_222458.txt` through `gen3_daemon_20260722_211651.txt`) —
this is because 0x7E/0x7F fire on a fixed ~308-tick hardware timer regardless of
activity (already established 2026-07-09), so a continuous 8h connection
accumulates thousands of them for free, asleep or not. The entire existing
`0x7E`/`0x7F` byte-role characterization (e.g. "`b[9]` walk-responsive, mean
193.3") was built from **7 real walk samples** plus small general-activity pulls
(dozens to ~100 packets).

**A quick sanity pull against this new volume already complicates the existing
story, without resolving it.** `0x7E` byte[9] across one full overnight file
(`gen3_daemon_20260718_222458.txt`, n=12,836) has mean **121.6**, stdev **75.3**,
and uses the **full 0-255 range throughout the entire night**, including
20-way-bucketed sub-windows that all look similar (no quiet-vs-busy structure
visible at this bucket size) — this doesn't obviously match the existing
"walk-responsive (high, tight) vs. other-activity (lower, tight)" framing built
from a 7-sample walk, though it isn't a clean apples-to-apples comparison either
(different windowing/methodology). This is flagged as a real open question, not a
falsification — the right next step is a proper re-characterization, not a
walk experiment.

### Concrete next steps for a follow-up session

1. **Before planning another walk experiment, mine the existing daemon logs.**
   Re-run the same per-byte mean/stdev/correlation analysis from the 2026-06-27
   and 2026-07-07 sessions (`known_issues.md`) against the 5 daemon nights
   instead of the tiny historical pulls — this is ~1000x the sample size, free,
   and requires no new data collection.
2. **Check specifically for nighttime motion episodes already sitting in this
   corpus.** A full night's continuous capture almost certainly contains a few
   real bathroom-trip/repositioning episodes — cross-reference `0x47` (motion
   event) or `0x6B` (motion period, already-confirmed step-count decoder)
   spikes against the same boot_ts windows in the 0x7E/0x7F stream. This could
   give real activity-vs-rest contrast without needing a deliberate walk at all.
3. Only after (1) and (2) are exhausted does a fresh controlled walk (this time
   using the already-built `pipeline/tools/walk_test_keepwarm.py` from
   2026-07-21, which solves the buffer-timing race that killed every walk
   attempt before it) become the right next move.

No other PARTIAL item showed this kind of stale data-volume framing — everything
else's ceiling is genuinely firmware/datasheet-shaped, not corpus-size-shaped.

---

## Note for the V3 cross-vector roadmap (flagged only, not built)

The project's stated V3 direction is cross-vector relationship logic — e.g. what
an HRV of 28ms means differs when deep sleep is 17% vs 25%. Two things from this
session are directly relevant to that eventual work, neither acted on here:

1. **Bout-size/maturity as a confidence signal, not just a stage-3 quirk.** The
   ~300-epoch threshold effect in Item 1 might generalize: if 0x5A's reliability
   genuinely depends on how much a bout has accumulated, any future cross-vector
   logic that wants to condition on sleep-stage data (once/if it's ever promoted
   past AWAITING DATA) would need a bout-size confidence gate, not just a
   per-tag DONE/PARTIAL gate. This is a data-quality dimension the project
   doesn't currently track anywhere.
2. **The daemon corpus is now large enough to support statistical
   characterization work that wasn't possible when most decoders were last
   touched.** Several PARTIAL decoders (0x7E/0x7F most clearly, but potentially
   others) were characterized on samples of single or low-double digits and
   never revisited after the daemon started producing thousands of samples per
   night. Worth a dedicated future session auditing which other PARTIAL items
   have quietly accumulated enough real data to redo their original
   characterization at proper statistical power, independent of any specific
   V3 need.

Both are flagged for awareness only — no product, UI, or dashboard change is
implied or proposed by either point, per this session's scope boundary.

---

## Method note (for reproducibility)

All analysis in this session was done via ad hoc Python scripts run against the
real corpus, reusing `pipeline.decoders.decode_sleep_phase_data`,
`decode_sleep_summary_2`, and `decode_bedtime_period` directly (no reimplemented
decode logic). Scripts were not saved to the repo, per this session's
investigation-only scope — a follow-up session implementing the Item 1 next
step should rebuild the `0x76`-grouping addition directly in the already-committed
`pipeline/tools/analyze_0x5a_stage3_gap.py` rather than hunting for this
session's scratch files.
