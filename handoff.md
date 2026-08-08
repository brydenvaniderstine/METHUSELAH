# METHUSELAH — Handoff (2026-08-08)

For full project background read `SESSION_HANDOFF.md` first. This file covers
one continuous work session spanning 2026-08-04 → 2026-08-08 (across several
real days/nights, reviewed each morning) and is organized so the next chat
can pick up cold. Supersedes the 2026-08-03 handoff — that session's items
are resolved or superseded below.

---

## 1) Goal

Same two threads as before, still both active:

1. **Make overnight ring capture reliable and self-adapting to real life** —
   survive BLE flakiness and irregular schedules without manual intervention,
   and produce a genuinely trustworthy `sleep_duration_hrs`/
   `sleep_duration_estimate_hrs` reading.
2. **Dashboard**: kept consistent across devices (resolved prior session);
   this session added a visual-legibility thread (see section 2).

---

## 2) Current State

- **A live daemon session is running RIGHT NOW** as this handoff is written
  (11:09am, 2026-08-08) — `gen3_daemon_20260807_220000.txt`, PID under
  `gen3_daemon_watchdog.py` (PID 54960), currently on its 4th restart of the
  morning. A WAKE-DETECT candidate is open, capped at max reading 49 (well
  under the real-walk threshold of 80) — genuinely unresolved, not a bug.
  **A background Bash watch was armed in the prior session** (`until tail
  ... | grep -qE "Confirmed real wake-up|Candidate discarded"`) watching
  `daemon_launchd.log` from line 455031 onward for this candidate's
  resolution — **this may not survive the `/clear`**; don't assume a
  notification will arrive in the new conversation. Check
  `daemon_launchd.log`'s tail directly instead.
- **WakeDetector real-steps bug: FOUND, FIXED, VERIFIED (commit `30b74fd`).**
  Root cause of three straight nights (08-02/03 through 08-04/05) falsely
  ending the session ~1am off a routine washroom trip: `cycle_real_steps`
  summed every 0x6B "Motion period" packet's `step_count` per cycle, *and*
  that per-cycle sum was accumulated again across the whole 15-35min
  candidate window. 0x6B's `step_count` is a documented wrapping idle
  counter that's never 0 at rest (range 1-63) — summing it, even once,
  trivially clears any small threshold from pure noise. `classify()`
  elsewhere in the same file already avoided this (compares a per-cycle MAX
  against `MIN_REAL_STEP_COUNT=80`); `WakeDetector` now does the same.
  Verified by replaying all 332 real Motion-period packets from the
  08-04/05 log through the actual decoder: max value all night was 63,
  confirming the fix would have prevented that night's false confirm.
  Two-stage confirmation (`WAKE_VERIFY_MINUTES`, from a prior session) is
  unchanged and still layered on top.
- **Wake-detection fix validated on two more real nights since** (08-05/06,
  08-07/08): real rest-noise candidates correctly sat capped below 80 and
  were **correctly discarded** rather than falsely confirming. No false
  positive since the fix landed. This part of the original goal is done.
- **A new, real, NOT-yet-fixed finding from this morning (08-08): a
  watchdog stall-restart silently wipes WakeDetector's in-memory candidate
  state with no resolution log line at all** (no "confirmed" or
  "discarded" — the candidate just vanishes when the daemon subprocess is
  killed and relaunched). Confirmed today: the 09:41:21 candidate never
  resolved before a 10:37:25 stall-restart, and a fresh candidate started
  cold right after. Not investigated further or fixed this session — worth
  a closer look if the watchdog is restarting frequently on nights when a
  real wake-up might be forming right around a restart. Not logged to
  `known_issues.md` yet either.
- **Dashboard visual restyle: tried, reverted, then partially redone
  differently.** A full OKLCH/IBM-Plex-Mono/brushed-button restyle from a
  design handoff Bryden supplied (commits `37e85fc`, `c531343`) went live,
  then Bryden asked to revert it ("not right") — done via `git revert` on
  both commits (`2fbfff1`, `88d0f2b`). Dashboard is back to the original
  Space Mono / hex-color look. **Kept from that whole thread**: a
  collapsible "Raw Telemetry" panel (commits `4c7732c`, `237629d`) that
  replaced the old cramped single-line `GEN3 INTERCEPT: ...` log entry with
  a legible label/value grid (RHR/IBI_HR/SPO2/BATTERY/TEMP/STEPS/sleep
  stages) — re-skinned to match the *current* (reverted) style, not the
  abandoned redesign's tokens. Includes the same staleness treatment
  (dimming + `[FLAG: STALE]`) as the primary tiles.
- **Sleep-duration freshness gap: FOUND, FIXED, verified but NOT yet seen
  succeeding on a real fresh night (commit `f9500bc`).** Bryden's question
  ("we have real stage-minute numbers, can't we just sum them?") exposed
  that bout freshness (new-this-session vs. carryover) was previously
  diagnostic-only in `sleep_duration_estimate.py` — it could make an error
  message more informative but could never actually block a 100% stale
  bout from passing every other check and being reported as if it were
  tonight's real sleep. New Condition 3: the final bout's last known total
  must have grown past whatever was already checkpointed for that same
  `bout_start` before this session began. Verified three ways against real
  data (no-checkpoint case unchanged at the 6.6h reference-night result;
  unrelated-checkpoint case unchanged; a genuinely-stale checkpoint match
  now correctly declines instead of silently reporting). **Not yet
  observed accepting a real, freshly-growing bout in production** — no
  night since deployment has produced one; the underlying stuck-0x4C-
  decoder problem (see below) is still unresolved, so this fix is proven
  correct but not yet proven useful on real data. Watch for this.
- **The original stuck-0x4C-decoder mystery is STILL UNRESOLVED and was
  NOT the focus this session.** Every recompute this week (08-05/06 through
  08-07/08) reports either 0 new bouts or a non-monotonic final sample —
  the ring's firmware is still not reliably finalizing fresh sleep
  summaries. This session fixed *what happens around* that problem
  (session-ending false positives, and not mis-reporting stale data as
  fresh) but did not fix the problem itself. `sleep_duration_hrs`/
  `sleep_duration_estimate_hrs` have been null on the live dashboard all
  week as a direct result.
- **Launchd ceiling trimmed 14h → 13h** (22:00 → 11:00, was noon), Bryden's
  direct request to review results an hour earlier. Plist edited and
  reloaded (`launchctl unload`/`load`) — takes effect from tonight
  (08-08/09) onward; did not affect the session that was already running
  when the change was made. An adaptive "give up after sustained
  ring-unreachability" alternative (more correct than a fixed ceiling, per
  the known weekend-sleep-in regression risk documented in the plist's own
  comment history) was proposed twice this session and **explicitly
  deferred both times** — still on the table if wanted later.
- **Playwright** was installed ad hoc into `web/node_modules` this session
  (via `npm install playwright`, using `channel: 'chrome'` to drive the
  system Chrome rather than downloading a bundled binary, since this Mac's
  macOS version isn't in Playwright's supported download matrix). Not
  saved to `package.json` (`--no-save`) — it's there on disk but not a
  tracked dependency. Useful for any future UI verification work; no
  cleanup needed, but don't assume it persists on a fresh `npm install`.

---

## 3) Active Files

| File | Role |
|---|---|
| `pipeline/tools/oura_gen3_ble_daemon.py` | Overnight daemon. `WakeDetector` class fixed this session (max-per-cycle real-steps gate, `MIN_REAL_STEP_COUNT` moved up near `ACTIVITY_TAGS` so the class can reference it as a constructor default). |
| `pipeline/tools/sleep_duration_estimate.py` | Bout-aware sleep estimate. New Condition 3 (freshness enforcement) added this session — see section 2. |
| `pipeline/tools/recompute_bridge_from_daemon.py` | Post-run recompute; unchanged this session but run manually twice (see Failed Attempts) to understand/fix the recompute-skip behavior. |
| `pipeline/data/findings/known_issues.md` | One new dated entry this session (2026-08-05, the WakeDetector sum-vs-max falsification). The watchdog-silently-resets-candidate finding from today is **not** logged there yet. |
| `web/src/App.js` | Dashboard. Restyled, then reverted (see section 2); `RawTelemetryPanel` component added and kept. |
| `~/Library/LaunchAgents/ca.methuselah.gen3daemon.plist` | Not in repo. Duration ceiling changed `14`→`13` this session; full change history is in its own comment block. |
| `pipeline/data/bridge/bout_checkpoint.json` | Not in repo (data). Now load-bearing for the new freshness Condition 3, not just diagnostic — same growth-unbounded caveat as before, still not trimmed. |

---

## 4) Changes Made (commits, chronological)

- `4f9c4ee` — Committed the morning-pull line-buffering/crash-safety/
  reconnect-experiment changes that had been sitting uncommitted in the
  working tree for several prior sessions (found during this session's
  Discover phase).
- `37e85fc`, `c531343` — Full dashboard visual restyle (OKLCH, IBM Plex
  Mono, brushed buttons), then a size correction. **Both reverted below.**
- `30b74fd` — WakeDetector real-steps fix (max-per-cycle, not a sum). See
  section 2 for full detail. Also logged to `known_issues.md`.
- `2fbfff1`, `88d0f2b` — Reverted the dashboard restyle (Bryden: "not
  right"), in reverse order. Dashboard back to original look.
- `4c7732c` — Added the collapsible Raw Telemetry panel, re-skinned to the
  reverted/original style.
- `237629d` — Raw Telemetry panel polish: toggle label reflects open/closed
  state, panel gets the same staleness treatment as the primary tiles.
- `f9500bc` — Sleep-duration freshness enforcement (Condition 3). See
  section 2.
- **Not a commit**: `~/Library/LaunchAgents/ca.methuselah.gen3daemon.plist`
  duration `14`→`13`, reloaded via `launchctl unload`/`load`.

---

## 5) Failed Attempts / Learnings

- **Manually interrupting the daemon (SIGINT) once Bryden was already up**
  (08-05/06 morning): correctly preserves already-logged data and the last
  bridge push (this is the daemon's own documented, supported manual-stop
  path), **but skips the automatic post-run recompute + supplementary
  morning pull** — those only run on the loop's own natural exit path
  (wake-confirm or ceiling). Result: Sleep Duration stayed blank that
  morning even though the night's data was otherwise fine. Fixed by running
  `recompute_bridge_from_daemon.py --push` manually afterward — but even
  that didn't produce a duration (non-monotonic final bout). **Lesson,
  acted on since**: let it finish on its own; don't interrupt, even when
  the answer already looks known.
- **Assuming a 14h ceiling "wastes" hours if you leave the house with the
  ring**: checked the actual loop code — `scan_for_ring` is always bounded
  by remaining time to the ceiling, so it can never hang past it, and
  hitting the ceiling runs the exact same natural-completion pipeline as a
  real wake-confirm. Confirmed this really happens (08-06/07 night: daemon
  ran unattended all the way to the old noon ceiling while Bryden was at
  work, then completed cleanly on its own with no data loss). Not a bug —
  just tightened from 14h to 13h afterward per direct request, not out of
  necessity.
- **Testing `sleep_duration_estimate.py`'s regression against the
  production `bout_checkpoint.json`**: comparing an old (07-19/20) log
  against *today's* checkpoint isn't a valid test — the checkpoint is
  stateful and has moved on since, so an old night's bout will always look
  "stale" by later comparison regardless of the code's correctness. Correct
  method: call `estimate_sleep_duration()` directly with an explicit
  `prior_bout_totals` (`None`, an unrelated dict, or a deliberately
  matching one) rather than relying on the live checkpoint file for
  regression testing.

---

## 6) Next Steps

1. **Check the outcome of the wake-detect candidate that was live when this
   handoff was written** (started 10:38:04, 2026-08-08) — read
   `pipeline/logs/daemon_launchd.log`'s tail directly; don't assume the
   prior session's background watch notified anyone.
2. **Investigate the watchdog-restart-silently-resets-WakeDetector-state
   finding** from this morning (section 2) — currently unfixed and
   unlogged. Decide whether it's worth a fix (e.g., persist minimal
   candidate state across a restart) or just documenting as an accepted
   edge case.
3. **Watch for the freshness-gate fix (`f9500bc`) to actually accept a
   real night** — it's been verified correct (declines stale data properly)
   but hasn't yet had a real fresh bout to prove the accept path in
   production, because the underlying stuck-0x4C-decoder problem is still
   open.
4. **The stuck-0x4C-decoder problem itself remains unresolved** — every
   real night this week either produced 0 new bouts or a non-monotonic
   final sample. This is the actual blocker on ever seeing a real
   `sleep_duration_estimate_hrs` again, separate from everything fixed this
   session. Not investigated this session; still open.
5. **13h ceiling is unverified in practice** — tonight (08-08/09) is its
   first real test.
6. If revisiting the dashboard again, the full old-vs-new restyle tokens
   and revert commits are in Claude's memory
   (`methuselah_dashboard_restyle_2026-08-04.md`) and the Raw Telemetry
   panel's own commits/revert-path are in
   `methuselah_raw_telemetry_panel_2026-08-05.md`.
