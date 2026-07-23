"""Provisional sleep-duration estimate from the 0x4C per-bout accumulator.

Separate, provisional companion to sleep_duration_hrs (which stays None
pending multi-night validation -- see recompute_bridge_from_daemon.py and
gen3_bridge.py). This module must never write to sleep_duration_hrs.

Background (pipeline/data/findings/known_issues.md, 2026-07-19/20 entry):
0x4C ("Sleep summary (2)") does not report a whole-night total -- it resets
per accumulation bout. The paired "Bedtime period" tag (0x76, fires in the
same cluster) decodes as [bout_start_boot_ts, current_boot_ts] (both u32 LE)
and confirms this: bout_start is held constant across every 0x4C firing that
belongs to the same bout, and only changes when the bout resets. The best
available single-night estimate is therefore: take the FINAL bout's last
stage-total snapshot, then add an "uncovered tail" for the gap between that
snapshot and the first real wake/activity signal -- since 0x4C's own
accumulation always lags slightly behind the true current moment.

Build order matters here more than usual: the decline/fallback checks
(fewer than 3 samples, non-monotonic growth, no wake signal, tail too large)
are the load-bearing part of this module. The happy-path arithmetic is the
easy 5% -- it already worked once (2026-07-19/20, final bout -> ~6.0h against
a real ~6h20m night). The risk is a messy night silently producing a bad
number, not the arithmetic itself.

Two additions from the 2026-07-22 whole-session-reconciliation investigation
(known_issues.md, "Whole-session reconciliation for sleep-duration estimate"
entry) -- both real-data-tested, both explicitly NOT the full multi-bout
merge that investigation discarded (no calibration data exists yet for a
between-bout gap constant) and NOT a daemon-start/stop sleep-boundary
substitute (confirmed unsafe -- see that entry's Finding C):

1. Outer-ceiling decline (CEILING_TOLERANCE, `session_span_hrs` param):
   caps any estimate at the real, connected daemon session's own wall-clock
   span -- this is the same category of gap that let the already-fixed
   92.0-HRS production bug (known_issues.md, 2026-07-21 session 4) reach the
   bridge. A session cannot produce more sleep-classified minutes than it
   was connected for.
2. Cross-session bout dedup (`prior_bout_totals` param): diagnostic-only,
   per that investigation's Finding A -- most bouts in a given night's log
   are stale carryover from a prior session (the daemon's since_boot_ts=0
   full-history re-request on every fresh connection), not new data. Makes
   decline reasons state the true freshness instead of a misleading "thin
   sample" message when the real state is "no new data at all this
   session." Does not change whether/what the function declines or
   estimates -- confirmed by the regression check in the commit that added
   this (same 3 real nights, same numeric outcomes).
"""

import struct

# --- Calibrated constants -------------------------------------------------

# Ticks per minute of real elapsed time, *within a single accumulation bout*.
# Derived 2026-07-19/20 from (bedtime_period.current - bedtime_period.bout_start)
# / 0x4C's own reported stage-total minutes, across 18 independent bout
# observations in gen3_daemon_20260719_212709.txt (individual ratios ranged
# 630.2-722.9 ticks/min, tightly clustered). 655 is the documented midpoint.
# Re-derived directly from that same log this session for the final bout
# specifically: 649.6 ticks/min -- consistent with the range above.
#
# NOTE -- deliberately NOT re-derived from the whole log's first-to-last
# boot_ts span: doing that this session gave ~14,650 ticks/min (~244/sec),
# about 22x faster, which cannot be reconciled with a bout that self-reports
# hundreds of minutes of stage accumulation while its own bout_start-to-now
# span is only tens of thousands of ticks. That whole-log figure is real but
# answers a different question (average tick rate across a night containing
# many BLE reconnects -- see known_issues.md Finding 3) and is out of scope
# here. The per-bout ratio is the one independently cross-validated against
# a second tag and is the only one applicable to a short post-bout window
# like the uncovered tail below. Flagged, not resolved, in known_issues.md.
TICK_RATE_PER_MIN = 655

# Minimum 0x4C samples the final bout must have before its trend is trusted.
# Below this a "smooth" read is indistinguishable from noise. The one fully
# verified final bout (2026-07-19/20) had 4 samples; this stays one below
# that as a floor, not a target.
MIN_BOUT_SAMPLES = 3

# Sanity cap on the "uncovered tail" (last 0x4C sample -> first clear
# wake/activity signal), in minutes. Tonight's real tail was ~38 min under
# the sustained-run definition below. 90 min gives headroom for a slower or
# messier wake without accepting an open-ended guess when the anchor point
# is implausibly far away. Tunable -- revisit once more real nights exist.
TAIL_CAP_MINUTES = 90

# A "clear wake/activity signal" is the start of a *sustained* run of
# Motion event / Real step feature (1) packets -- not an isolated blip.
# Both tags fire throughout the night as background telemetry (confirmed
# this session: ~13/min even in the middle of confirmed sleep), so a single
# occurrence is not a reliable wake marker. A run counts as sustained once
# this many consecutive events all land within SUSTAINED_MAX_GAP_TICKS of
# each other. Calibrated against tonight's real wake burst, which showed a
# tight, regular ~270-300 tick spacing between consecutive events, clearly
# distinct from the more variable (hundreds to several thousand ticks)
# gaps seen during isolated overnight movement.
SUSTAINED_MIN_EVENTS = 5
SUSTAINED_MAX_GAP_TICKS = 400

# How close (in ticks) a Sleep summary (2) firing's own boot_ts must be to
# the preceding Bedtime period firing's boot_ts to be treated as the same
# cluster. Observed gaps in real data: 4-86 ticks; this is deliberately
# generous relative to that.
CLUSTER_PAIR_MAX_TICKS = 500

# Multiplier applied to the real, connected daemon-session wall-clock span
# (header start timestamp -> log file mtime, both real logged/observed
# times, never assumed) to get the outer ceiling an estimate may not
# exceed. >1.0 to allow real headroom for the still-unresolved tick-rate
# uncertainty documented above (TICK_RATE_PER_MIN's ~22x whole-log-vs-
# bout-local discrepancy) without silently accepting an open-ended guess.
# 1.1 chosen per the 2026-07-22 reconciliation investigation's own
# proposal -- not re-derived from a specific real overcap case, since none
# of the 3 real nights on record ever get close to the ceiling at all (see
# known_issues.md for the hand-tested margins: 6.6h est. vs 7h59m57s cap on
# 07-19/20, well clear). Tunable -- revisit if a real night ever approaches
# it.
CEILING_TOLERANCE = 1.1

ACTIVITY_TAG_NAMES = {"Motion event", "Real step feature (1)"}
BEDTIME_TAG_NAME = "Bedtime period"
SLEEP_SUMMARY_TAG_NAME = "Sleep summary (2)"


def _decode_bedtime(payload: bytes):
    a = payload[0] | (payload[1] << 8) | (payload[2] << 16) | (payload[3] << 24)
    b = payload[4] | (payload[5] << 8) | (payload[6] << 16) | (payload[7] << 24)
    return a, b


def _decode_stage_total_min(payload: bytes) -> float:
    f = struct.unpack_from("<7H", payload, 0)
    # f[0..3] = stage3(deep)/stage2(rem)/stage1(light)/stage0(wake) epoch
    # counts, 30s epochs -- see pipeline/decoders/0x4c.py.
    return (f[0] + f[1] + f[2] + f[3]) * 30 / 60


def _group_bouts(entries):
    """Pair each Sleep summary (2) firing with its preceding Bedtime period
    firing (same cluster) and group by bout_start. Returns bouts in
    chronological order of first appearance:
      [{'bout_start': int, 'samples': [(boot_ts, stage_total_min), ...]}]
    """
    bouts = {}
    order = []
    last_bedtime = None  # (bout_start, current, boot_ts)

    for e in entries:
        if e["tag_name"] == BEDTIME_TAG_NAME:
            try:
                bout_start, current = _decode_bedtime(e["payload"])
            except Exception:
                continue
            last_bedtime = (bout_start, current, e["boot_ts"])
        elif e["tag_name"] == SLEEP_SUMMARY_TAG_NAME:
            if last_bedtime is None:
                continue
            bout_start, _current, bedtime_ts = last_bedtime
            if abs(e["boot_ts"] - bedtime_ts) > CLUSTER_PAIR_MAX_TICKS:
                continue  # not the same cluster -- stale Bedtime period
            try:
                total_min = _decode_stage_total_min(e["payload"])
            except Exception:
                continue
            if bout_start not in bouts:
                bouts[bout_start] = []
                order.append(bout_start)
            bouts[bout_start].append((e["boot_ts"], total_min))

    return [{"bout_start": bs, "samples": bouts[bs]} for bs in order]


def bout_totals_snapshot(entries):
    """Public helper for callers that want to persist a cross-session
    checkpoint (see `prior_bout_totals` below). Returns {bout_start:
    latest_total_min} for every bout observed in `entries`, using each
    bout's own final (highest-boot_ts) sample -- the same value a caller
    would want to carry forward so a future session can tell a bout that
    kept accumulating (see known_issues.md: bout 76149641 grew 359.5min ->
    399.0min across a real session boundary) from one that's genuinely
    unchanged stale carryover.
    """
    bouts = _group_bouts(entries)
    return {
        b["bout_start"]: sorted(b["samples"], key=lambda s: s[0])[-1][1]
        for b in bouts if b["samples"]
    }


def _label_bout_freshness(bouts, prior_bout_totals):
    """Diagnostic-only split of `bouts` into new-this-session vs.
    carryover-from-a-prior-session, using a {bout_start: last_seen_total_min}
    map the caller persisted after a previous run (see bout_totals_snapshot
    above). Returns None if no prior checkpoint was supplied at all (first
    real run, or caller doesn't have one yet) -- distinct from "checkpoint
    supplied but every bout turned out new," which is a real 0/0 split, not
    an absence of information.

    Purely a labeling function -- does not filter, sum, or otherwise use
    the split to change any estimate. See module docstring for why (the
    2026-07-22 investigation explicitly discarded summing multiple bouts
    as premature; this only makes existing decline reasons honest about
    which bout produced them).
    """
    if prior_bout_totals is None:
        return None
    new_bouts, carryover_bouts = [], []
    for b in bouts:
        (carryover_bouts if b["bout_start"] in prior_bout_totals else new_bouts).append(b)
    return {"new": new_bouts, "carryover": carryover_bouts}


def _freshness_note(freshness):
    """Short, human-readable suffix for a decline `reason` string, or ''
    if no freshness info is available. See _label_bout_freshness."""
    if freshness is None:
        return ""
    n_new, n_carry = len(freshness["new"]), len(freshness["carryover"])
    if n_new == 0 and n_carry > 0:
        return (f" {n_carry} bout(s) observed this session, all carryover "
                 f"from a prior session's log (0 new bouts) -- the ring's "
                 f"firmware never finalized a fresh sleep summary during "
                 f"this connected session.")
    if n_new > 0:
        return f" {n_new} new bout(s) this session, {n_carry} carryover."
    return ""


def _find_wake_signal(entries, after_boot_ts):
    """boot_ts of the first event in a sustained activity run after
    after_boot_ts, or None if no such run exists in this log."""
    activity_ts = sorted(
        e["boot_ts"]
        for e in entries
        if e["tag_name"] in ACTIVITY_TAG_NAMES and e["boot_ts"] > after_boot_ts
    )
    run_start = None
    run_len = 0
    prev = None
    for ts in activity_ts:
        if prev is None or ts - prev > SUSTAINED_MAX_GAP_TICKS:
            run_start = ts
            run_len = 1
        else:
            run_len += 1
        if run_len >= SUSTAINED_MIN_EVENTS:
            return run_start
        prev = ts
    return None


def estimate_sleep_duration(entries, session_span_hrs=None, prior_bout_totals=None):
    """Provisional sleep-duration estimate from the final 0x4C accumulation
    bout in `entries` (the parsed-daemon-log entry list: dicts with
    tag_name/boot_ts/payload, as produced by
    recompute_bridge_from_daemon.parse_daemon_log()).

    Decline conditions are checked first (see module docstring) -- any one
    of them returns sleep_duration_estimate_hrs=None with a specific reason.
    Conditions 1 and 2 are structural (checked directly on the final bout's
    samples); condition 4 (no wake signal at all) is checked before
    condition 3 (tail too large) since the tail can't be computed without
    first finding a signal to measure it against. Condition 5 (outer
    ceiling) is checked last, after a candidate number exists.

    session_span_hrs: optional real, caller-supplied wall-clock span of the
    connected daemon session (real logged start timestamp -> real observed
    end, never assumed -- see recompute_bridge_from_daemon.py for how this
    is derived). When supplied, caps the estimate (condition 5 below).
    Analysis-only if omitted -- existing behavior is unchanged.

    prior_bout_totals: optional {bout_start: last_seen_total_min} map from
    a prior session (see bout_totals_snapshot), used only to make decline
    `reason` strings honest about which bouts are new vs. carryover.
    Diagnostic only -- never changes which condition fires or what number
    (if any) is returned; omitting it reproduces the exact prior behavior.

    Returns:
      {
        'sleep_duration_estimate_hrs': float or None,
        'reason': str,        # which condition declined, or how the
                               # estimate was built
        'confidence': dict or None,  # inspectable inputs behind the number
      }
    """
    bouts = _group_bouts(entries)
    if not bouts:
        return {
            "sleep_duration_estimate_hrs": None,
            "reason": "No 0x4C/Bedtime period cluster fired in this log.",
            "confidence": None,
        }

    freshness = _label_bout_freshness(bouts, prior_bout_totals)
    freshness_counts = (
        {"new_bouts_this_session": len(freshness["new"]),
         "carryover_bouts_this_session": len(freshness["carryover"])}
        if freshness is not None else {}
    )

    final_bout = bouts[-1]
    samples = sorted(final_bout["samples"], key=lambda s: s[0])

    # Condition 1 -- minimum sample count.
    if len(samples) < MIN_BOUT_SAMPLES:
        return {
            "sleep_duration_estimate_hrs": None,
            "reason": (f"Final bout has only {len(samples)} sample(s), "
                       f"below MIN_BOUT_SAMPLES={MIN_BOUT_SAMPLES}."
                       f"{_freshness_note(freshness)}"),
            "confidence": {"final_bout_samples": len(samples), **freshness_counts},
        }

    # Condition 2 -- roughly monotonic growth within the bout.
    totals = [s[1] for s in samples]
    for i in range(1, len(totals)):
        if totals[i] < totals[i - 1]:
            return {
                "sleep_duration_estimate_hrs": None,
                "reason": (f"Final bout stage total is not monotonic: "
                           f"sample {i - 1}={totals[i - 1]:.1f}min -> "
                           f"sample {i}={totals[i]:.1f}min."
                           f"{_freshness_note(freshness)}"),
                "confidence": {"final_bout_samples": len(samples),
                               "totals_min": [round(t, 1) for t in totals],
                               **freshness_counts},
            }

    last_boot_ts, last_total_min = samples[-1]

    # Condition 4 -- a wake/activity anchor must exist at all.
    wake_ts = _find_wake_signal(entries, last_boot_ts)
    if wake_ts is None:
        return {
            "sleep_duration_estimate_hrs": None,
            "reason": (f"No clear wake/activity signal (sustained run of "
                       f"{SUSTAINED_MIN_EVENTS}+ Motion/Real-step events) "
                       "found after the final bout's last 0x4C sample."
                       f"{_freshness_note(freshness)}"),
            "confidence": {"final_bout_samples": len(samples),
                           "final_bout_total_min": round(last_total_min, 1),
                           **freshness_counts},
        }

    tail_ticks = wake_ts - last_boot_ts
    tail_min = tail_ticks / TICK_RATE_PER_MIN

    # Condition 3 -- uncovered tail sanity cap.
    if tail_min > TAIL_CAP_MINUTES:
        return {
            "sleep_duration_estimate_hrs": None,
            "reason": (f"Uncovered tail ({tail_min:.1f}min) exceeds "
                       f"TAIL_CAP_MINUTES={TAIL_CAP_MINUTES}."
                       f"{_freshness_note(freshness)}"),
            "confidence": {
                "final_bout_samples": len(samples),
                "final_bout_total_min": round(last_total_min, 1),
                "tail_min": round(tail_min, 1),
                "tail_capped": True,
                **freshness_counts,
            },
        }

    raw_total_min = last_total_min + tail_min

    # Condition 5 -- outer ceiling: a real, connected daemon session cannot
    # produce more sleep-classified minutes than it was connected for. This
    # is the gap that let the already-fixed 92.0-HRS bug (known_issues.md,
    # 2026-07-21 session 4) reach production through a different code path
    # -- closing it here too, not just at that bug's specific mechanism.
    # session_span_hrs is real (caller-derived from a logged start
    # timestamp + observed end), never assumed -- see
    # recompute_bridge_from_daemon.py. Declining, not clipping: a number
    # that's merely capped to the ceiling would still be fabricated.
    if session_span_hrs is not None:
        ceiling_min = session_span_hrs * 60 * CEILING_TOLERANCE
        if raw_total_min > ceiling_min:
            return {
                "sleep_duration_estimate_hrs": None,
                "reason": (f"Candidate estimate ({raw_total_min / 60:.2f}h) "
                           f"exceeds the real connected-session span "
                           f"({session_span_hrs:.2f}h x "
                           f"{CEILING_TOLERANCE} tolerance = "
                           f"{ceiling_min / 60:.2f}h ceiling)."
                           f"{_freshness_note(freshness)}"),
                "confidence": {
                    "final_bout_samples": len(samples),
                    "final_bout_total_min": round(last_total_min, 1),
                    "tail_min": round(tail_min, 1),
                    "session_span_hrs": round(session_span_hrs, 2),
                    "ceiling_hrs": round(ceiling_min / 60, 2),
                    "ceiling_exceeded": True,
                    **freshness_counts,
                },
            }

    estimate_hrs = round(raw_total_min / 60, 2)
    return {
        "sleep_duration_estimate_hrs": estimate_hrs,
        "reason": (f"OK: final bout total {last_total_min:.1f}min + "
                   f"uncovered tail {tail_min:.1f}min "
                   f"(tick rate {TICK_RATE_PER_MIN}/min)."),
        "confidence": {
            "final_bout_samples": len(samples),
            "final_bout_total_min": round(last_total_min, 1),
            "tail_min": round(tail_min, 1),
            "tail_capped": False,
            "tick_rate_per_min": TICK_RATE_PER_MIN,
            "session_span_hrs": round(session_span_hrs, 2) if session_span_hrs is not None else None,
            **freshness_counts,
        },
    }
