# Fable master audit — 2026-07-24

**Scope:** whole-system audit (not just the Gen3 decoder work), investigation and
planning only. No code was edited, nothing committed or pushed this session. This
document is the single master remediation plan for a future execution session
(Sonnet) to implement directly.

**What was read/reviewed in full:** the `methuselah` project skill; `SESSION_HANDOFF.md`
(all 400 lines); `TASK_HANDOFF.md`; `open_ring_roadmap.md`; the section map of
`known_issues.md` (7,578 lines); `fable_investigation_2026-07-24.md`;
`max86171_register_reference.md`; `ARCHITECTURE.md`; all four `engine/*.js`; all four
`web/src/engine/*.js`; `web/src/App.js` in full; the `parsers/` scaffolding;
`pipeline/tools/gen3_bridge.py`, `recompute_bridge_from_daemon.py`,
`oura_gen3_ble_daemon.py` (HRV path), `pipeline/decoders/hrv_rmssd.py`,
`analyze_0x5a_stage3_gap.py`; the live bridge JSON; and the on-disk corpus.

**Convention used below:** every item is tagged **CONFIRMED** (verified against real
code and/or real data on disk, with the citation inline) or **SUSPECTED** (plausible,
but not verified this session — the verification step is stated). Nothing is called
"confirmed" without a real-data or real-code citation, per the project's own discipline.

---

## Section A — What is already working well (do not touch)

The execution session should treat these as solid and not second-guess them:

1. **`engine/*.js` ↔ `web/src/engine/*.js` are byte-identical** across all four files
   (`thresholds.js`, `index.js`, `sources.js`, `commands.js`) — verified by `diff`.
   The `prebuild`/`prestart` sync in `web/package.json` is doing its job. The audit
   brief specifically asked about drift between the engine and its web copy; there is
   **none** at the code level. (Documentation about the engine has drifted — see B4/B5
   — but the code copies have not.)

2. **The 4-tile grid obeys the design rules.** Threshold text on every tile is pulled
   from `THRESHOLDS.*` via `metaParts()` (`App.js:497–503`), never hardcoded, so the
   displayed rule cannot drift from the evaluated rule. Staleness dims the tile
   (`.tel-stale`, opacity 0.65) and ambers the source dot at `STALE_HRS=12`
   (`App.js:200–203, 232–247`). `AWAITING DATA` renders correctly when a vector is null.

3. **The Sleep Duration tile is KISS-compliant** — a single `~X.X hrs (est.)` number
   with a one-word qualifier, no stage/confidence/pattern UI (`App.js:610–619`). Do not
   expand it.

4. **No CTA/suggestion layer exists.** The command panel is the terminus; the
   `awaiting`/`optimal`/`warn`/`critical` levels each render a terminal state, not a
   "what to do next" engagement loop.

5. **BRI is correctly kept as a log line** (`addLog("BIOLOGICAL READINESS INDEX…")` at
   `App.js:376, 401`) rather than a primary tile — compliant with design rule #1. (There
   is one narrow exception where the composite still touches a primary surface — see C3
   — but the core "BRI is a log line, not a tile" contract holds.)

6. **The decoder-pipeline discipline is exemplary and should be preserved as-is.**
   `known_issues.md` logs falsified hypotheses with the same weight as positive
   findings; `sleep_duration_estimate.py`'s decline logic and outer-ceiling check are
   conservative and correct; `recompute_bridge_from_daemon.py` correctly refuses to
   derive sleep duration from 0x6A. None of this needs rework.

7. **The Gen3 bridge pattern** (`pipeline → web/public/gen3_latest.json →` PWA fetch of
   `/api/gen3-bridge`) is the proven integration seam and should be the template for the
   Calibration Layer (see Section D).

---

## Section B — Prioritized executable fixes

Ordered by leverage: correctness-that-changes-what-the-user-is-told first, then
design-drift, then documentation. Each item is specific enough to implement without
re-deriving the reasoning.

### B1 — CONFIRMED, HIGH — HRV is whole-night RMSSD with no sleep-state filter; the served value is inflated and the "validated" claims are false

**Evidence (code):**
- `pipeline/tools/recompute_bridge_from_daemon.py:248` — `hrv_ms = calculate_rmssd(ibi_packets_all)`. `ibi_packets_all` is every 0x6E IBI packet across the entire daemon night (gathered in the loop at lines 192–194), with **no filter by 0x6A `sleep_state`**. The comment at line 247 says so literally: "HRV from all night's IBI."
- `pipeline/tools/oura_gen3_ble_daemon.py:455–456` — the live per-cycle path does the same: `nightly_hrv = calculate_rmssd(ibi_packets_all)`, gated only by `pull_class == "SLEEP WINDOW"` (a whole-pull classification), never by per-packet sleep state.
- `pipeline/decoders/hrv_rmssd.py` does within-packet artifact rejection but no sleep-state gating (it never receives state info).

**Evidence (data):** the live `web/public/gen3_latest.json` (pull_file
`gen3_daemon_20260720_213320.txt`, a full daemon night) shows `hrv_ms: 52.6`. The
project's own personal reference band (`open_ring_roadmap.md` Gen4 baseline table) is
RMSSD p25–p75 = **24–35 ms**, with **>45 ms flagged as a clear peak outlier**. 52.6 is
above that outlier threshold — consistent with the known daytime/active RMSSD range
(56–70 ms noted in the 2026-07-14 handoff) contaminating a value that should sit in the
overnight 24–31 ms range.

**Evidence (contradicted claims):**
- `engine/sources.js:21` comment: *"HRV: Gen3 READY (RMSSD from 0x6E/0x80 IBI,
  sleep-window only, validated 2026-07-13)."* — **"sleep-window only" is false**; neither
  serving path filters to sleep-window IBI.
- The `methuselah` skill's own data-trust tier says the opposite and is correct:
  *"Current RMSSD includes all overnight IBI including pre-sleep active phase —
  sleep-filtered (state=1 periods only via 0x6A boot_ts cross-reference) is the next
  refinement, not yet implemented. Until then, treat nightly RMSSD as slightly inflated
  … do not report it as fully validated."*

**Why this is the top item:** HRV is a locked primary vector with a hard 25 ms
threshold. An inflated HRV means the HRV command (`EXECUTE 45-MIN ZONE 2 OUTPUT`) fails
to fire on nights when true sleep HRV is at or below 25 ms, and the tile shows green
("optimal ≥ 25ms") when the user's real recovery signal may be suppressed. This silently
changes what the user is told to do — the single highest-stakes correctness issue in the
system.

**Fix:** implement the sleep-state filter the skill already specifies. In
`recompute_bridge_from_daemon.py`, restrict the IBI packets fed to `calculate_rmssd` to
0x6E packets whose `boot_ts` falls inside a 0x6A `sleep_state == 1` span. The loop
already tracks `state_runs` as `(state, boot_ts_start, boot_ts_end)` tuples
(`recompute…py:169, 187–222`) — reuse those: keep an 0x6E packet only if its `boot_ts`
lies within a run where `state == 1`. Apply the identical filter in the daemon's
`nightly_hrv` computation (`oura_gen3_ble_daemon.py:455`). Then fix the false
`sources.js:21` comment to describe the real mechanism and state honestly whether it is
now sleep-filtered.

**Verify against real data:** re-run `recompute_bridge_from_daemon.py` (no `--push`)
against `gen3_daemon_20260720_213320.txt` and the other full daemon nights
(`20260718_222458`, `20260719_212709`, `20260721_213131`, `20260722_211651`). Expect the
filtered RMSSD to drop from the ~50 ms range into roughly 24–35 ms (the personal band).
Compare filtered vs unfiltered per night; document the delta in `known_issues.md`. Do
**not** mark HRV "validated" on the strength of this alone — it is a correctness fix, and
external ground truth is permanently gone (Gen4 closed), so the honest status stays
"internally consistent, physiologically plausible," not "clinically validated."

**Behavior-change note for the owner:** this will change the HRV number on the live tile
and may make the HRV command fire on nights it previously stayed green. That is the
correct outcome, but it is a visible change in what the dashboard tells the user — see
Decision D-1.

### B2 — CONFIRMED, HIGH — sleep-stage breakdown (incl. deep-sleep minutes) is surfaced in the UI, contradicting the DISCARD-tier rule

**Evidence:**
- `recompute_bridge_from_daemon.py:210–214` and `gen3_bridge.py:56–63` build and emit
  `sleep_stages = { wake_min, light_min, rem_min, deep_min, source_tag: "0x4C" }`.
- `web/src/App.js:695–697` renders it into the sys-log line whenever present:
  `// STAGES W{wake_min}m L{light_min}m R{rem_min}m D{deep_min}m`. The live bridge
  currently carries `deep_min: 14.5`, so this is actively displayed, not dormant.

**Why it's a drift:** the skill's data-trust tier puts *"Deep sleep % / sleep-stage
breakdown"* in the **Discard** class — *"industry-wide guesswork … Do not chase, do not
build, AWAITING DATA is correct."* `ARCHITECTURE.md:319–320` states the design intent
that `deep_sleep_pct` is *"not surfaced in the primary UI."* The log line surfaces a
deep-sleep-minutes figure anyway. Note the important distinction from SpO2/steps: those
are **weekly-trend** tier (log-stream is explicitly allowed); deep-sleep staging is a
stricter **Discard** tier where even a log line runs against the stated stance. This is
also a prime-directive concern (surface area / more-to-doubt without added legibility).

**Recommended fix (aligns with "subtract complexity"):** remove the `STAGES …` segment
from the `App.js` log line (delete the ternary at `695–697`). Optionally also stop
emitting `sleep_stages` from the bridge builders so the Discard-tier data doesn't travel
to the client at all — but the minimal, safe change is the UI removal. The 0x4C stage
counts remain useful *internally* as the cross-validation anchor for the 0x5A decoder
work (Section C) — this fix is about not **displaying** them, not about deleting the
decode.

**This one needs owner sign-off before removal** because it touches a design rule and
someone deliberately wired it in — see Decision D-2. Recommendation is removal; do not
remove unilaterally.

**Verify:** after removal, load the PWA against the current bridge and confirm the
sys-log GEN3 INTERCEPT line renders with no `STAGES` segment and no console errors;
confirm the four tiles are unchanged.

### B3 — CONFIRMED, LOW/MEDIUM — the BRI composite score drives the command-panel border color

**Evidence:** `web/src/App.js:622` —
`<div className="command-wrap" style={{ borderColor: execState === "satisfied" ? "#00ff66" : bri.color }}>`,
where `bri = calculateBRI(...)` (`App.js:505`). The command **text/rationale** come from
the single-vector priority cascade (`logic`, via `evaluateSources`), but the panel's
**border color** — the most prominent framing element on the screen — comes from the
composite readiness index.

**Why it's a drift:** design rule #1 says a rollup index *"never replaces them on a
primary tile"* and belongs as *"a log line next to its raw inputs."* The command panel is
the primary terminus. Coupling its border to BRI produces a mixed signal: the command can
be an amber HRV warning while the border is BRI-green. It is the one remaining place the
composite silently shapes a primary surface.

**Fix:** drive the border from the same single-vector state that produced the command.
`logic` (the `evaluateSources` result) already carries `color`/`border`/`level` from
`COMMANDS.*`. Change `App.js:622` to use `logic.border` (or a level→color map derived
from `logic.level`) instead of `bri.color`. Keep the `execState === "satisfied"` green
override as-is. BRI stays exactly where it belongs — the log line.

**Verify:** with a synthetic bridge that trips one vector (e.g. HRV 20 ms), confirm the
command text and the border now agree (both the warn/critical color), and that BRI still
appears only in the log stream.

**This is borderline** (the rule literally names *tiles*, and the panel is not a tile) —
classified LOW because it's interpretive, but it's the cleanest place to honor the
directive fully. See Decision D-3 if the owner considers the coupling intentional.

### B4 — CONFIRMED, MEDIUM — `ARCHITECTURE.md` is substantially stale and contradicts both the live code and `SESSION_HANDOFF.md`

**Evidence (each is a real contradiction):**
- Build-status table (`ARCHITECTURE.md:68–72`): claims `engine/` is *"Future — Logic
  currently lives in src/App.js — extraction pending"*, `parsers/` *"Future"*, and
  pipeline decoders *"currently inline … migration … pending"* with *"34 Gen3 pulls."*
  Reality: `engine/*.js` are built and live; decoders are extracted to
  `pipeline/decoders/`; the corpus is ~7 full daemon nights plus 46 morning/evening
  pulls. `SESSION_HANDOFF.md:24–31` already records engine as "Done" and decoders as
  extracted — so the two top-level docs contradict each other.
- Source-readiness table (`ARCHITECTURE.md:100–108`): claims HRV is *"Not ready …
  Gen4-only"* and Deep sleep *"Gen4-only,"* and describes fallback behavior *"when the
  Oura API token lapses (2026-07-13)."* Reality: Gen4 is permanently dead; HRV has a Gen3
  path serving live values; there is no Gen4 to fall back from.
- Threshold section (`ARCHITECTURE.md:296, 318`): says *"sleepDuration: 7h floor"* and
  *"BRI brackets { optimal: 8h, nominal: 7h }."* Reality (`engine/thresholds.js:9–10,
  18`): `sleepDurationWarn: 8`, `sleepDurationCritical: 6`, BRI `sleepDuration
  { optimal: 8, nominal: 6 }`. The doc's 7h floor / 7h nominal no longer exist in code.

**Fix:** rewrite the build-status table, the source-readiness table, and the threshold
subsection to match current reality. Authoritative sources for the rewrite:
`SESSION_HANDOFF.md`'s build-status table, `engine/thresholds.js`, and the `methuselah`
skill's data-trust tiers. This is documentation only — no code changes — but it is
load-bearing because ARCHITECTURE.md is listed as a session-entry read.

### B5 — CONFIRMED, MEDIUM — `engine/README.md` describes the engine extraction as not-yet-done

**Evidence:** `engine/README.md` "Planned files" table marks `thresholds.js`,
`scoring.js`, `commands.js` as *"Not built — logic in src/App.js L…"*, and the "Current
violations" table lists `src/App.js` line ranges to extract. All of that extraction is
done: `thresholds.js`, `commands.js`, `index.js`, `sources.js` exist and are live. Two
further mismatches: the README references `engine/scoring.js` (never created — BRI lives
in `engine/index.js` as `calculateBRI`), and `engine/schema.py` (see B6).

**Fix:** update `engine/README.md` to reflect the built state: mark thresholds/commands
as built, note that scoring lives in `index.js` (`calculateBRI`, not a separate
`scoring.js`), delete the "Current violations" table (the extraction is complete), and
keep `schema.py` flagged as the one genuinely unbuilt file (B6).

### B6 — CONFIRMED, MEDIUM — `engine/schema.py` does not exist but is the declared contract for all parsers (this is the Calibration Layer blocker)

**Evidence:** `engine/schema.py` is absent from disk. It is referenced as the canonical
biomarker key contract in `parsers/README.md:19, 36`, `engine/README.md:49`, and
`ARCHITECTURE.md:120`. Without it, no parser can be built to spec. Full treatment in
Section D — this is called out here as a confirmed fix so it lands on the executable list.

### B7 — CONFIRMED, LOW — `engine/sources.js` sleep-duration readiness comment is stale/contradicted

**Evidence:** `engine/sources.js:22–23` comment: *"Sleep duration: Gen3 READY via daemon
(0x6A state accumulation overnight). Morning pull cannot provide this."* The 0x6A
state-accumulation mechanism for sleep duration was explicitly **rejected** (0x6A
undercounts because the ring stops emitting at `pfsm_state=8`; 0x4C is authoritative; the
live 0x6A duration computation was removed in the 2026-07-21 "92.0 HRS" fix). The real
mechanism the code actually implements (`sources.js:79–91`) is: strict
`sleep_duration_hrs` (0x4C, almost always null) → fallback `sleep_duration_estimate_hrs`
(provisional, 1 validated night). And it is not "READY" in the RHR/SpO2 sense.

**Fix:** rewrite the `sources.js:22–23` comment to describe the 0x4C-strict →
estimate-fallback mechanism and its provisional (single-night-validated) status. Comment
only; the resolver logic below it is correct and should not change.

### B8 — SUSPECTED, LOW — client-side `MASTER_KEY = "v1"` gate on a "data sovereignty" product

**Evidence:** `web/src/App.js:188` hardcodes `MASTER_KEY = "v1"`; the auth overlay
(`532–558`) is a client-side string compare. Anyone with the bundle bypasses it. Flagged
as SUSPECTED because the real data is already behind the Vercel KV write-secret and this
is a single-user personal dashboard, so the overlay may be intentionally cosmetic. **Not
recommending a fix** — flagging so the execution session doesn't mistake it for real
access control if security ever comes up. Verification if it matters: confirm with the
owner whether the gate is meant to be anything more than a casual lock.

### B9 — SUSPECTED, LOW — top badge says "OURA LIVE"/"OURA" on Gen3-only data

**Evidence:** `App.js:526` badge label is `OURA LIVE` / `OURA` / `OFFLINE` driven purely
by Gen3 bridge freshness; the per-tile source correctly reads `GEN3 BLE`. Since the Oura
Gen4 API is permanently dead, "OURA LIVE" on the top badge is arguably misleading (it *is*
an Oura Gen3 ring, so not wrong, just imprecise). Low priority; flag for the owner. A
one-line fix would relabel to `GEN3 LIVE`/`GEN3`/`OFFLINE` to match the tiles — but this
is cosmetic and should not be changed without owner preference (Decision D-4, minor).

---

## Section C — Decoder roadmap (build on `fable_investigation_2026-07-24.md`, do not re-derive)

The investigation doc's three leads are sound and are **not** re-litigated here. This
section says which decoders are worth re-checking against the current corpus size and
which are not, and folds the HRV work into the decoder picture.

**Current corpus (verified on disk):** ~7 full-length overnight daemon logs (18/19
through 22/23, each 9–31 MB, plus the short 07-24 "zero-ring" night), 30 morning pulls,
16 evening pulls, 2 walk keep-warm captures.

### C0 — The HRV sleep-state filter (B1) is the highest-value decoder-pipeline task

It's decoder-adjacent, not a new tag — but it is worth stating here so the execution
session sequences it correctly: **do B1 before any new tag work.** It changes a live,
locked-vector value; everything in this section is lower-stakes than that.

### C1 — 0x7E/0x7F re-characterization — the one genuinely corpus-size-unblocked item

**Why re-check:** the roadmap still frames 0x7E/0x7F as *"needs a controlled fast-vs-slow
walk experiment"* — a framing that predates the daemon. The investigation doc verified
the 5 full daemon logs now hold **10,664–25,672 `Real step feature (1)` packets each**,
because these fire on a ~308-tick hardware timer regardless of activity. The entire
existing byte-role story (e.g. "`b[9]` walk-responsive, mean 193.3") was built from **7
walk samples**. A quick sanity pull already complicated it (byte[9] over one night: mean
121.6, stdev 75.3, full 0–255 range).

**Concrete next steps (from the investigation doc, restated for the executor):**
1. Before planning any walk, mine the existing daemon logs: re-run the per-byte
   mean/stdev/correlation analysis from the 2026-06-27 / 2026-07-07 sessions against the
   5 daemon nights (~1000× the sample size, free, no new capture).
2. Cross-reference 0x47 (motion event) / 0x6B (motion period, confirmed step decoder)
   spikes against the same `boot_ts` windows in the 0x7E/0x7F stream — a full night
   almost certainly contains real bathroom-trip/repositioning episodes, giving
   activity-vs-rest contrast without a deliberate walk.
3. Only if (1)+(2) are exhausted, run a fresh controlled walk with the already-built
   `walk_test_keepwarm.py` (which fixes the buffer-timing race that killed prior walks).

**Note on product relevance:** step count is **weekly-trend tier**, not a primary tile
(skill data-trust). This work improves a log-line signal's characterization; it is not a
new tile and must not become one.

### C2 — 0x5A stage-3 gap — fold in 0x76 bout-grouping, then gather more growth series

**Verified state:** `analyze_0x5a_stage3_gap.py` currently dedups by `boot_ts` and groups
bouts by last-chunk `boot_ts`; it does **not** call `decode_bedtime_period` / group by the
0x76 `start_ring_time` bout identity (confirmed by grep — no `0x76`/`bedtime`/`start_ring_time`
references in the file). So the investigation's Item 1 next-step #1 is genuinely not yet
implemented.

**Concrete next steps:**
1. Fold the 0x76 bout-grouping into `pipeline/tools/analyze_0x5a_stage3_gap.py`: add a
   `decode_bedtime_period` pairing step, use its `start_ring_time` (`a`) field as the true
   bout identity, and print bouts grouped by `a` (growth series) alongside the existing
   flat table. This makes the growth-series view available by default.
2. Re-run against the full corpus to grow the n=4 growth-series sample and test whether
   the ~300-epoch "knee" (below which stage-3 relative error is large/unstable, above
   which it settles to ~0–5%) holds. Every new daemon night adds candidate series for
   free.
3. **Do NOT** re-attempt the 0xFF-adjacency or total-0xFF-count hypotheses — both already
   tested and weak/falsified 2026-07-24. 0x5A stays **PARTIAL**; this is not a promotion
   candidate.

### C3 — 0x5A stage-0 trailing-zero-padding refinement

**Verified state:** `pipeline/decoders/0x5a.py` (200 lines) treats a `0x00` byte
identically everywhere. The investigation found all 4 checked single-chunk bouts follow
`[0xFF NO_DATA header] → [short real burst] → [long unbroken 0x00 run to end of buffer]`,
consistent with zero-initialized firmware buffer padding being miscounted as WAKE epochs.

**Concrete next steps (in this order — the falsifier check comes first):**
1. **First**, check whether any bout in the corpus has a confirmed real trailing WAKE
   stretch at the very end of the transmitted buffer. If one exists, a blanket
   "trailing-0x00 = padding" rule would zero out real data — that would falsify the
   refinement and it should not ship.
2. If (1) is clean, implement the narrow rule in `0x5a.py` `decode()`: a run of `0x00`
   that extends to the very end of the reassembled buffer with no non-zero byte after it
   is a padding candidate (reclassify as NO_DATA); a `0x00` followed later by non-zero
   real data is a real epoch and stays.
3. Verify it fixes the stage-0-vs-0x4C overcount for the 7 flagged single-chunk bouts
   **without** breaking the 31 multi-chunk bouts that already exact-match 0x4C.

**Still internal-consistency only** — per the skill this does not change deep-sleep /
stage-breakdown's Discard/AWAITING-DATA status, and must not be used to justify surfacing
stages (see B2).

### C4 — Do NOT reopen the firmware/datasheet-ceilinged PARTIAL decoders

The investigation doc verified this and it is restated so the executor doesn't burn time:
`0x61/09` f2/f4, `0x4A`, `0x50`, `0x6C`, `0x6D`, `0x72`, `0x73`, `0x77`, `0x61/28`,
`0x61/33` all have an explicit, already-tested firmware/datasheet ceiling logged.
`0x61/28` (n≈26,774) and `0x61/33` (n≈9,456) grew hugely via daemon polling but were
**still** falsified against the real MAX86171 datasheet on 2026-07-21 — their ceiling is
firmware-shape, not corpus-size, so more data does not help. `0x61/09` f2/f4 is formally
closed (Gen4 cross-reference permanently unavailable). **0x7E/0x7F (C1) is the only
PARTIAL item whose ceiling was corpus-size and is now lifted.** Everything else is
correctly parked.

---

## Section D — Calibration Layer (`parsers/`) — moving from scaffolding to v1

**Current state:** `parsers/` has a top-level `README.md` and three empty source
subdirs (`lifelabs/`, `siphox/`, `insidetracker/`), each with a README and no code.
`SESSION_HANDOFF.md` and the roadmap both call this the highest-leverage build after the
BLE bridge.

**Two real blockers, both must be resolved before v1 code is worth writing:**

### D-blocker-1 — the declared contract file `engine/schema.py` doesn't exist

Every parser README says parsers import their canonical key list from `engine/schema.py`,
and `web/` consumes parser output only via `engine/`. But `engine/schema.py` is absent
(B6). **Step one of v1 is to create it** — a single canonical list of biomarker keys
(the READMEs already give the starter shape: `glucose_mmol`, `hba1c_pct`, `ferritin_ug_l`,
`vitamin_d_nmol_l`, `hscrp_mg_l`). This is a small, unblocked, do-it-now task.

### D-blocker-2 — the Python-parser → JavaScript-engine seam is undefined

This is the real architectural gap and it needs an explicit decision before building.
The `parsers/` contract is **Python** (`parse(filepath) -> dict`), but `engine/` is
**JavaScript** (`*.js`) and `web/` imports from `engine/` only. A JS engine cannot
`import engine/schema.py`, and it cannot call a Python parser directly. The docs describe
a clean contract that has no defined cross-language mechanism.

**Recommended resolution (do not build without owner confirmation — Decision D-5):** use
the pattern the codebase has already proven — a **biomarker bridge JSON**, exactly
mirroring `gen3_latest.json`. A Python parser writes a normalized biomarker JSON to a
known path (or POSTs it to a KV endpoint like `api/gen3-bridge.js`); the JS engine reads
that JSON, the same way `App.js` already fetches `/api/gen3-bridge`. `engine/schema.py`
defines the keys for the Python side; a tiny sibling (e.g. the same key list mirrored in
JS, or a generated JSON) keeps the JS side honest. This avoids inventing any new
cross-language import machinery and stays inside the removability contract (delete a
parser dir → its bridge JSON simply stops updating).

### D-blocker-3 — no real input file exists for any of the three sources

Per real-data-only discipline, a parser is not DONE until it parses a **real** export.
`SESSION_HANDOFF.md` Open Decision #4 records that v2 is *"blocked on LifeLabs PDF
export. No parser built yet."* SiPhox/InsideTracker are CSV (simpler than a PDF) but also
have no sample file on disk. So v1 cannot be validated today regardless of how much code
is written — this needs the owner to provide a real export (Decision D-6).

**What the execution session CAN do now without an input file (all unblocked):**
1. Create `engine/schema.py` with the canonical biomarker key list (B6).
2. Decide + document the Python→JS seam (recommend the bridge-JSON pattern above) in
   `parsers/README.md` and `ARCHITECTURE.md`, replacing the currently-undefined
   "import via engine" hand-wave.
3. Nothing else — do not write a parser against a fabricated fixture and call it v1; that
   violates real-data-only discipline. Writing the *interface stub* (`parse.py` returning
   all-None) for one chosen source is acceptable as scaffolding **if** clearly marked not
   validated.

---

## Section E — Open questions / decisions needing owner input (do not guess these)

**D-1 — HRV sleep-state filter (from B1).** Implementing the filter will change the live
HRV tile value (likely dropping ~50 ms → ~25–35 ms) and may cause the HRV command to
fire on nights it previously showed green. This is the correct fix, but it visibly
changes what the dashboard tells you. Approve shipping it, or defer the filter and just
correct the false "validated" claims for now?

**D-2 — Sleep-stage breakdown in the log line (from B2).** Recommendation is to remove
the `STAGES W..L..R..D..` segment (Discard-tier data on a primary surface, against the
skill's stance). But it was deliberately wired in. Remove it, keep it as raw telemetry,
or keep emitting `sleep_stages` to the bridge while dropping only the UI render?

**D-3 — Command-panel border color (from B3).** Should the primary command panel's border
be driven by the single-vector command state (recommended, honors "no composite on a
primary surface") or is the composite-BRI border coloring intentional and worth keeping?

**D-4 — Top badge label (from B9, minor).** Relabel "OURA LIVE/OURA" to "GEN3
LIVE/GEN3" to match the per-tile source, or leave as-is? Cosmetic; owner preference.

**D-5 — Calibration Layer cross-language seam (from D-blocker-2).** Confirm the
biomarker-bridge-JSON approach (mirroring Gen3) before any parser is built, or specify a
different Python↔JS contract.

**D-6 — Calibration Layer first source + real input file (from D-blocker-3).** Which
source is v1 — LifeLabs (PDF, hardest), SiPhox (CSV), or InsideTracker (CSV)? And can you
provide one real export file? Nothing can be validated without it, and per real-data-only
discipline nothing should be marked DONE against a fabricated fixture.

---

## Section F — Things explicitly checked and found NOT to be problems (so the executor doesn't chase them)

- **Engine↔web code drift:** none. All four files byte-identical (Section A1).
- **Composite readiness score replacing a tile:** not present. BRI is a log line
  (Section A5); the only composite-touches-primary-surface case is the border color
  (B3), which is narrow and interpretive.
- **Sleep Duration tile scope creep:** none. It's a single number + `(est.)` qualifier
  (Section A3). Do not expand it.
- **Threshold text drift on tiles:** none. Pulled from `THRESHOLDS.*` at render
  (Section A2). (The drift is in the prose docs — B4 — not in the tile logic.)
- **0x6A being used for sleep duration:** correctly avoided in `recompute` (it hardcodes
  `sleep_duration_hrs = None` with the right rationale, `recompute…py:224–229`). The
  stale claim about 0x6A is only in a `sources.js` *comment* (B7), not in behavior.

---

## Appendix — file:line index of every confirmed finding (for the executor)

| ID | Severity | File:line | One-line |
|----|----------|-----------|----------|
| B1 | HIGH | `pipeline/tools/recompute_bridge_from_daemon.py:248`; `oura_gen3_ble_daemon.py:455`; `engine/sources.js:21` | HRV = all-night RMSSD, no sleep-state filter; "sleep-window only, validated" comment is false; live value 52.6 ms > 45 ms outlier band |
| B2 | HIGH | `web/src/App.js:695–697`; `recompute…py:210`; `gen3_bridge.py:63` | Deep-sleep-minutes leak into UI log line vs Discard-tier rule |
| B3 | LOW | `web/src/App.js:622` | Command-panel border driven by composite BRI, not single-vector state |
| B4 | MED | `ARCHITECTURE.md:68–72, 100–108, 296, 318` | Build-status/source-readiness/threshold tables all stale, contradict code + handoff |
| B5 | MED | `engine/README.md` (Planned files + Current violations tables) | Describes completed extraction as not-yet-done; references nonexistent `scoring.js` |
| B6 | MED | `engine/schema.py` (absent); refs in `parsers/README.md:19,36`, `engine/README.md:49`, `ARCHITECTURE.md:120` | Declared parser contract file doesn't exist — Calibration Layer blocker |
| B7 | LOW | `engine/sources.js:22–23` | Sleep-duration readiness comment describes the rejected 0x6A mechanism |
| B8 | LOW (susp.) | `web/src/App.js:188` | `MASTER_KEY="v1"` client-side gate — not real access control |
| B9 | LOW (susp.) | `web/src/App.js:526` | Top badge says "OURA LIVE" on Gen3-only data |

*Logged 2026-07-24 by the Fable master-audit session. Investigation and planning only —
no code, docs, or decoder files were modified.*
