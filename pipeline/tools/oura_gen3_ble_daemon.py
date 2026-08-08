#!/usr/bin/env python3
"""
METHUSELAH // Gen3 persistent-connection BLE daemon

Holds ONE BLE connection to the ring open continuously and polls it every
POLL_SECONDS (default 60s) using an incremental "history since boot_ts=X"
request, instead of reconnecting/re-authenticating every cycle the way
oura_gen3_auto_loop.py does. Comfortably ahead of the ring's ~1.8-minute
worst-case circular-buffer eviction window (confirmed in known_issues.md),
so no event should ever be silently overwritten while this is running.

Built 2026-07-12 after the owner confirmed the official Oura app's BLE
connection to the ring is no longer worth protecting -- it was only ever a
data pipe to Oura's cloud API, and that pipe is being cut off by the Gen4
token expiry (2026-07-13) regardless. See known_issues.md and
SESSION_HANDOFF.md for the full context/decision.

Reuses (does not duplicate):
  - pipeline/decoders/* for every decode (same imports as
    oura_gen3_morning_pull.py)
  - gen3_ble_connection.py for connect/auth/setup and the incremental
    history-request primitive (confirmed supported by
    oura_gen3_daily_pull.py's hours-ago request)
  - gen3_bridge.py for the bridge JSON shape and live-site push, so this
    can't drift out of sync with oura_gen3_morning_pull.py or
    api/gen3-bridge.js

Usage:
    python3 pipeline/tools/oura_gen3_ble_daemon.py [poll_seconds] [duration_hours]

Defaults: poll_seconds=5, duration_hours=8 (one overnight/workday session).
Revised twice on 2026-07-12 from real live-hardware observations, each one
finding a faster real event rate than the last:
  1. First run at 60s: buffer filled (256 events) in ~66s just sitting at
     a desk -- already faster than the "~1.8 min worst-case while walking"
     figure this project was previously built around.
  2. Tightened to 30s: EVERY cycle still returned exactly 256 events with
     zero gaps in the continuity check (confirmed no data loss, but no
     margin either) -- measured sustained rate ~14 events/sec, meaning
     the 256-event buffer could fill in ~18 seconds during active daytime
     use. 30s was already too close to that ceiling.
5s leaves real margin under an ~18s fill time. This may still need
revisiting once there's daytime-activity and overnight-sleep data to
compare -- the true rate likely varies a lot by context.
Stop any time with Ctrl+C -- already-logged data and the last bridge push
are preserved.
"""
import asyncio
import json as _json
import os as _os
import re as _re
import sys as _sys
import time
from collections import Counter

# 2026-08-01: a full night's output (scan attempts, cycle logs, everything)
# was lost when this process was killed -- stdout redirected to a file via
# shell '>>' is fully block-buffered by default, so print() sits in memory
# until the buffer fills or the process exits normally, and a SIGTERM
# (exactly how the watchdog restarts this script, and how a person stops
# it) skips that flush. Line-buffering forces a flush after every newline
# so a kill can never lose more than the current line.
_sys.stdout.reconfigure(line_buffering=True)
_sys.stderr.reconfigure(line_buffering=True)

_sys.path.insert(0, _os.path.dirname(__file__))
_sys.path.insert(0, _os.path.join(_os.path.dirname(__file__), '..'))

from gen3_ble_connection import open_connection, request_history, scan_for_ring, ConnectError
from gen3_bridge import build_bridge_data, merge_with_existing_bridge, write_local_bridge_file, push_bridge_json
from decoders import (
    decode_sleep_period_info_2,
    decode_spo2_event,
    decode_spo2_ibi_amplitude,
    decode_sleep_temp_event,
    decode_debug_data_fuel_gauge,
    decode_motion_period,
    decode_wear_event,
    calculate_rmssd,
)

EVENT_TAGS = {
    0x41: "Ring start", 0x42: "Time sync", 0x43: "Debug event", 0x44: "IBI event",
    0x45: "State change", 0x46: "Temp event", 0x47: "Motion event",
    0x48: "Sleep period info", 0x49: "Sleep summary (1)", 0x4A: "PPG amplitude",
    0x4B: "Sleep phase info", 0x4C: "Sleep summary (2)", 0x4D: "Ring sleep feature info",
    0x4E: "Sleep phase details", 0x4F: "Sleep summary (3)", 0x50: "Activity info",
    0x51: "Activity summary (1)", 0x52: "Activity summary (2)", 0x53: "Wear event",
    0x54: "Recovery summary", 0x55: "Sleep heart rate", 0x56: "Alert event",
    0x57: "Ring sleep feature info (2)", 0x58: "Sleep summary (4)", 0x59: "EDA event",
    0x5A: "Sleep phase data", 0x5B: "BLE connection", 0x5C: "User information",
    0x5D: "HRV event", 0x5E: "Self-test event", 0x5F: "Raw ACM event",
    0x60: "IBI and amplitude event", 0x61: "Debug data", 0x62: "On-demand MEAs",
    0x63: "PPG peak event", 0x64: "Raw PPG event", 0x65: "On-demand session",
    0x66: "On-demand motion", 0x67: "Raw PPG summary", 0x68: "Raw PPG Data",
    0x69: "Temp period", 0x6A: "Sleep period info (2)", 0x6B: "Motion period",
    0x6C: "Feature session", 0x6D: "MEAs quality event", 0x6E: "SPO2 IBI+amplitude",
    0x6F: "SPO2 event", 0x70: "SPO2 smoothed event", 0x71: "Green IBI+amplitude",
    0x72: "Sleep ACM period", 0x73: "EHR trace event", 0x74: "EHR ACM intensity",
    0x75: "Sleep temp event", 0x76: "Bedtime period", 0x77: "SPO2 DC event",
    0x79: "Self-test data event", 0x7A: "Tag event", 0x7E: "Real step feature (1)",
    0x7F: "Real step feature (2)", 0x81: "CVA raw PPG data", 0x82: "Scan start",
    0x83: "Scan end",
}
SLEEP_TAGS = {0x6A, 0x5D, 0x6F, 0x75}
ACTIVITY_TAGS = {0x7E, 0x7F}

# 0x6B (Motion period) b[0] ("step_count") is NOT a reliable literal step
# count at rest: confirmed 2026-07-22 against all 1,151 real 0x6B packets
# across 3 full overnight logs (gen3_daemon_20260719/20/21) that at rest it
# behaves as a wrapping idle counter -- 70-75% of consecutive packets step by
# exactly +1, wrapping every ~16 counts -- and NEVER once reads 0 (real
# range 1-63 across all three nights). It only becomes a genuine per-window
# step signal during real ambulatory motion: the one controlled ground-truth
# walk experiment on record (2026-07-07, ~500 real steps) measured b[0] at
# 98-101 per window. There is a clean, real gap (64-97) with zero
# observations on either side across all real data collected so far.
# MIN_REAL_STEP_COUNT sits inside that gap (17 above the confirmed rest
# ceiling, 18 below the confirmed walk floor) -- comfortably clear of a
# "1 stray step" or "2+" threshold, which real data shows would fire on
# almost every cycle (rest-state b[0] is virtually never 0) and would have
# misclassified real, confirmed sleep as active. Must be compared against
# the MAX single-packet value in a cycle, not a cycle-level sum -- summing
# multiple rest-noise packets in one poll cycle can itself exceed 80 (real
# examples on record: [63, 32] sums to 95, [45, 14, 63] sums to 122) purely
# from cycle-grouping, with no real packet in the pair anywhere near the
# real walk floor. Shared by classify() below and WakeDetector (moved up
# here 2026-08-05 so WakeDetector's default constructor arg can reference
# it -- see the WAKE_MIN_REAL_STEPS retirement note below).
MIN_REAL_STEP_COUNT = 80

# --- Live wake detection (2026-08-01, replaces guessing a fixed end time) --
# A fixed --duration requires knowing the wake time in advance, which broke
# on an irregular schedule (a weekend sleep-in needed a manually recomputed
# duration + manual relaunch the same night -- see that session's
# conversation). This ends the session based on detecting real, sustained
# movement instead, while the ring stays on the wrist the whole time (it is
# not designed to be removed except for charging every ~2 days, so a
# WEAR-EVENT-based "ring came off" signal was considered and rejected).
#
# Signal: same two tags sleep_duration_estimate.py's _find_wake_signal()
# already uses and calibrated -- "Motion event" and "Real step feature (1)"
# fire at ~13/min even in the middle of confirmed sleep (background
# telemetry), so a single occurrence means nothing; only a SUSTAINED run
# (SUSTAINED_MIN_EVENTS consecutive events each within SUSTAINED_MAX_GAP_TICKS
# of the last) is a real signal. Reusing that module's exact calibrated
# constants rather than re-deriving new ones.
#
# Confirmation, not instant action: a real wake-up and a ~1 minute bathroom
# trip look IDENTICAL at the moment a sustained burst starts -- both are
# real walking. The only thing that tells them apart is what happens next.
# So a qualifying burst only starts a CANDIDATE: if activity goes quiet
# again (no activity-tag event at all for QUIET_DISQUALIFY_MINUTES) before
# WAKE_CONFIRM_MINUTES of real wall-clock time have passed, the candidate
# is discarded (looks like a brief trip back to sleep) and detection resets
# to watch for the next one. Only a candidate that survives the full
# confirmation window without ever going quiet that long is treated as a
# real, final wake-up.
ACTIVITY_TAG_NAMES_FOR_WAKE = {"Motion event", "Real step feature (1)"}
WAKE_SUSTAINED_MIN_EVENTS = 5
WAKE_SUSTAINED_MAX_GAP_TICKS = 400
WAKE_QUIET_DISQUALIFY_MINUTES = 10
WAKE_CONFIRM_MINUTES = 15
# Don't even start watching for a wake candidate until this many real hours
# into the session -- otherwise normal pre-bed activity (getting ready,
# walking around) in the first hour would immediately look like "waking up"
# and end the session almost as soon as it started.
WAKE_DETECTION_MIN_SESSION_HOURS = 3

# 2026-08-03: a real night (08-02/03) ended the whole session at 01:21am --
# only 3h15m in -- because a candidate burst survived the full confirmation
# window without a quiet gap. The pull classifier itself still called those
# same minutes SLEEP WINDOW/MIXED WINDOW, never ACTIVE WINDOW: this was very
# likely real but restless in-bed movement (tossing/turning), not actually
# getting up. Motion event/Real step feature are FFT-classified spectral
# tags, not literal step counts (see oura_gen3_morning_pull.py's own
# decode-section header) -- sleep_duration_estimate.py's docstring already
# warned both fire as background telemetry even in the middle of confirmed
# sleep, which is exactly what this looks like in hindsight. Real step
# COUNTS come from a different tag, "Motion period" (0x6B, decode_motion_
# period's step_count field) -- genuine walking produces these; rolling
# over in bed does not. Now required in addition to the existing
# time-based confirmation: a candidate can start and stay pending on
# activity-tag bursts alone (unchanged), but cannot CONFIRM until real
# steps have also accumulated during that same window, whenever the
# confirm-minutes timer is reached (see WakeDetector.process_cycle).
#
# 2026-08-05: the above was implemented wrong and never actually gated
# anything. Two more real nights (08-03/04, 08-04/05) both confirmed a
# wake-up off a routine washroom trip Bryden explicitly confirmed as brief
# ("woke up to use the washroom around 1am then went back to bed"), the
# second one surviving the newly-added two-stage verify window too (35 min,
# 3,040 "real steps"). Root cause: this file's own MIN_REAL_STEP_COUNT
# comment (see ACTIVITY_TAGS above) already documented that 0x6B step_count
# is a wrapping idle counter that's NEVER 0 at rest and must be compared as
# a per-cycle MAX, never summed -- "summing multiple rest-noise packets in
# one poll cycle can itself exceed 80". WakeDetector did exactly that
# forbidden sum, across every cycle for the entire candidate window (see old
# real_steps_since_candidate), so WAKE_MIN_REAL_STEPS=10 was cleared by rest
# noise alone within 1-2 poll cycles, before any real walking could happen.
# classify() below never had this bug -- it already used MIN_REAL_STEP_COUNT
# (80) against a per-cycle max. WAKE_MIN_REAL_STEPS is retired; WakeDetector
# now reuses MIN_REAL_STEP_COUNT against a per-cycle max the same way.

# 2026-08-04: two real nights (08-02/03, 08-03/04) both confirmed a wake-up
# at ~1:19-1:21am off a routine washroom trip (confirmed real, not
# hypothetical -- Bryden: "get up to use the washroom around 1:00 to 1:20
# and then go back to bed"; the second occurrence cleared WAKE_MIN_REAL_STEPS
# with 1,664 real steps). The trip itself is substantial enough to clear the
# existing 15-min bar on its own, so raising that bar (or excluding a
# specific clock window) would only dodge this exact case, not the general
# problem: any vigorous nighttime trip can look identical to a real wake-up
# for its first 15 minutes. The only thing that actually tells them apart is
# what happens AFTER -- a real wake-up keeps going; a washroom trip goes
# quiet again once back in bed. Confirmation is now two-stage: the existing
# 15-min/real-steps bar only provisionally confirms and starts a second
# WAKE_VERIFY_MINUTES clock; the existing quiet-gap check (unchanged) keeps
# running through this second stage too, and a quiet gap at any point still
# discards the whole candidate. Only surviving the full provisional +
# verify window without ever going quiet counts as a real, final wake-up.
# Trade-off accepted knowingly: a real morning where activity happens to go
# quiet for 10+ min shortly after getting up (sitting with coffee, at a
# desk) would also get discarded and have to restart detection from a fresh
# burst, delaying the real end-of-session further -- accepted because
# losing a whole night's data to a false positive is far worse than the
# session running long.
WAKE_VERIFY_MINUTES = 20


class WakeDetector:
    """Live, real-time detector for "the wearer is actually awake and moving
    around" -- see the WAKE_* constants' docstring above for the full
    reasoning. Pure state machine, no I/O of its own: process_cycle() takes
    a plain list of boot_ts values and an injectable clock, so this can be
    unit-tested directly against synthetic bathroom-trip / real-wake-up
    event sequences without any real BLE hardware or file I/O.

    Two-stage confirmation (see WAKE_VERIFY_MINUTES docstring above): the
    original 15-min/real-steps bar now only provisionally confirms and
    starts a second verify-window clock; the same quiet-gap check keeps
    running through that second stage, so a candidate that goes quiet at
    any point -- during the original window OR the verify window -- still
    discards back to watching. Final confirmation requires surviving both
    windows back to back without ever going quiet that long."""

    def __init__(self, min_session_hours=WAKE_DETECTION_MIN_SESSION_HOURS,
                 sustained_min_events=WAKE_SUSTAINED_MIN_EVENTS,
                 sustained_max_gap_ticks=WAKE_SUSTAINED_MAX_GAP_TICKS,
                 quiet_disqualify_minutes=WAKE_QUIET_DISQUALIFY_MINUTES,
                 confirm_minutes=WAKE_CONFIRM_MINUTES,
                 min_real_steps=MIN_REAL_STEP_COUNT,
                 verify_minutes=WAKE_VERIFY_MINUTES):
        self.min_session_hours = min_session_hours
        self.sustained_min_events = sustained_min_events
        self.sustained_max_gap_ticks = sustained_max_gap_ticks
        self.quiet_disqualify_minutes = quiet_disqualify_minutes
        self.confirm_minutes = confirm_minutes
        self.min_real_steps = min_real_steps
        self.verify_minutes = verify_minutes
        self.streak = 0
        self.streak_last_ts = None
        self.candidate_since = None
        self.verify_since = None
        self.last_activity_wall_time = None
        self.max_real_step_seen = 0
        self.confirmed = False
        self.last_event_note = None  # "candidate_started" / "candidate_discarded" / "awaiting_steps" / "provisional_confirm" / "verifying" / "confirmed" / None

    def process_cycle(self, activity_boot_ts_list, real_steps_this_cycle, now, session_start_time):
        """activity_boot_ts_list: this cycle's ACTIVITY_TAG_NAMES_FOR_WAKE
        event boot_ts values (any order). real_steps_this_cycle: the MAX
        single 0x6B "Motion period" step_count packet value seen this cycle
        (0/None if no Motion period packet this cycle) -- NOT a sum; see
        MIN_REAL_STEP_COUNT's comment above ACTIVITY_TAGS for why summing is
        wrong (it's a wrapping idle counter, never 0 at rest -- a cycle-level
        or multi-cycle sum clears any reasonable threshold from noise alone).
        A cycle counts as real walking only if this max clears
        MIN_REAL_STEP_COUNT on its own. now/session_start_time: real
        time.time() values (injectable for tests). Returns self.confirmed."""
        self.last_event_note = None
        if (now - session_start_time) / 3600 < self.min_session_hours:
            return self.confirmed

        for ts in sorted(activity_boot_ts_list):
            if (self.streak_last_ts is not None and
                    (ts - self.streak_last_ts) <= self.sustained_max_gap_ticks):
                self.streak += 1
            else:
                self.streak = 1
            self.streak_last_ts = ts
            if self.streak >= self.sustained_min_events and self.candidate_since is None:
                self.candidate_since = now
                self.verify_since = None
                self.last_activity_wall_time = now
                self.max_real_step_seen = 0
                self.last_event_note = "candidate_started"

        if activity_boot_ts_list:
            self.last_activity_wall_time = now

        if self.candidate_since is not None:
            if real_steps_this_cycle and real_steps_this_cycle > self.max_real_step_seen:
                self.max_real_step_seen = real_steps_this_cycle

            quiet_for_min = (now - self.last_activity_wall_time) / 60
            if quiet_for_min >= self.quiet_disqualify_minutes:
                self.candidate_since = None
                self.verify_since = None
                self.streak = 0
                self.streak_last_ts = None
                self.max_real_step_seen = 0
                self.last_event_note = "candidate_discarded"
            elif self.verify_since is not None:
                if (now - self.verify_since) / 60 >= self.verify_minutes:
                    self.confirmed = True
                    self.last_event_note = "confirmed"
                else:
                    self.last_event_note = "verifying"
            elif (now - self.candidate_since) / 60 >= self.confirm_minutes:
                if self.max_real_step_seen >= self.min_real_steps:
                    self.verify_since = now
                    self.last_event_note = "provisional_confirm"
                else:
                    # Time's up but no real walking seen yet -- stay pending
                    # rather than confirm OR discard; keep watching each
                    # cycle for either real steps (confirms) or a long
                    # enough quiet gap (discards).
                    self.last_event_note = "awaiting_steps"

        return self.confirmed


# 0x6A/0x5D/0x6F/0x75 are continuous background-sensor tags -- they fire
# whenever the ring has skin contact, not only during sleep (confirmed
# 2026-07-21: an afternoon dishes episode where the ring sat motionless on a
# counter between wears produced an identical SLEEP_TAGS/motion signature to
# a real overnight sleep pull). Real 0x53 (wear event) data across 3 full
# overnight logs shows NOT_IN_FINGER/FINGER_USER_ACTIVE alternate 33-44x per
# night even during confirmed sleep, so that pair can't gate SLEEP WINDOW
# without misclassifying real sleep too -- see known_issues.md. The one
# unambiguous real signal is CHARGING_PHASE (state 8): the ring cannot be
# worn while charging. Combined with a wide local-hour plausibility band
# (grounded in the actual daemon schedule: 22:00 start, ~06:00 end, plus
# safety-net morning pulls through ~08:30) as the practical defense against
# daytime stillness being read as sleep.
PLAUSIBLE_SLEEP_HOURS = set(range(20, 24)) | set(range(0, 9))  # 20:00-08:59 local

# MIN_REAL_STEP_COUNT is defined earlier in this file, right after
# ACTIVITY_TAGS -- see that comment for the full real-data justification.


def classify(tags_seen, motion_count, charging_seen=False, local_hour=None, step_count=None):
    has_sleep = bool(tags_seen & SLEEP_TAGS)
    has_real_steps = step_count is not None and step_count >= MIN_REAL_STEP_COUNT
    has_activity = bool((tags_seen & ACTIVITY_TAGS) or motion_count >= 3 or has_real_steps)
    if has_sleep and has_activity:
        return "MIXED WINDOW"
    if has_sleep and charging_seen:
        # Ring reported itself on the charging dock during this window --
        # cannot be worn/asleep regardless of stillness-derived sleep tags.
        return "UNCLEAR"
    if has_sleep:
        if local_hour is not None and local_hour not in PLAUSIBLE_SLEEP_HOURS:
            return "UNCLEAR"
        return "SLEEP WINDOW"
    if has_activity:
        return "ACTIVE WINDOW"
    return "UNCLEAR"


def parse_event(data: bytes):
    if len(data) < 6:
        return None
    tag = data[0]
    boot_ts = int.from_bytes(data[2:6], "little")
    payload = data[6:]
    return {"tag": tag, "tag_name": EVENT_TAGS.get(tag, f"UNKNOWN (0x{tag:02x})"),
            "boot_ts": boot_ts, "payload": payload}


def decode_cycle_events(events):
    """Decode this cycle's new events into the same accumulators
    oura_gen3_morning_pull.py builds the bridge JSON from. Returns
    (accumulators dict, pull_class, decode_fail_count).
    """
    hr_avgs, spo2_avgs, temps, ibi_ms_all = [], [], [], []
    ibi_packets = []  # per-packet IBI lists, for HRV RMSSD (needs packet boundaries preserved)
    fuel_gauge_pct = None
    total_steps, motion_period_found = 0, False
    max_step_count = None  # max single 0x6B packet value this cycle -- classify()'s real-movement
                            # check, kept separate from total_steps (a cycle-level sum across
                            # possibly multiple 0x6B packets, which is the right thing for the
                            # bridge-facing step count but the wrong thing to threshold against
                            # for real-vs-rest detection -- see MIN_REAL_STEP_COUNT above).
    cadence_samples = []
    tags_seen = set()
    motion_event_count = 0
    charging_seen = False
    fails = 0

    asleep_6a_count = 0  # 0x6A packets with sleep_state != 0 — used for duration accumulation
    for ev in events:
        tags_seen.add(ev["tag"])
        if ev["tag"] == 0x47:
            motion_event_count += 1
        try:
            if ev["tag"] == 0x6A:
                d = decode_sleep_period_info_2(ev["payload"])
                hr_avgs.append(d["average_hr"])
                if d["sleep_state"] != 0:
                    asleep_6a_count += 1
            elif ev["tag"] == 0x6F:
                d = decode_spo2_event(ev["payload"])
                if d["spo2_percent"]:
                    spo2_avgs.append(sum(d["spo2_percent"]) / len(d["spo2_percent"]))
            elif ev["tag"] == 0x6E:
                d = decode_spo2_ibi_amplitude(ev["payload"])
                ibi_ms_all.extend(v for v in d["ibi_ms"] if 300 <= v <= 2000)
                ibi_packets.append(d["ibi_ms"])
            elif ev["tag"] == 0x75:
                d = decode_sleep_temp_event(ev["payload"])
                temps.extend(d["temps_c"])
            elif ev["tag"] == 0x6B:
                d = decode_motion_period(ev["payload"])
                motion_period_found = True
                total_steps += d["step_count"]
                max_step_count = d["step_count"] if max_step_count is None else max(max_step_count, d["step_count"])
                if d["cadence_spm"] and d["cadence_spm"] > 0:
                    cadence_samples.append(d["cadence_spm"])
            elif ev["tag"] == 0x61 and len(ev["payload"]) > 0 and ev["payload"][0] == 0x14:
                d = decode_debug_data_fuel_gauge(ev["payload"])
                fuel_gauge_pct = round(d["battery_percentage"], 1)
            elif ev["tag"] == 0x53:
                d = decode_wear_event(ev["payload"])
                if d["state"] == 8:  # STATE_CHARGING_PHASE
                    charging_seen = True
        except ValueError:
            fails += 1

    ibi_hr_bpm = None
    if ibi_ms_all:
        ibi_hr_bpm = round(60000 / (sum(ibi_ms_all) / len(ibi_ms_all)), 1)
    hrv_ms = calculate_rmssd(ibi_packets)

    accum = {
        "hr_avgs": hr_avgs, "spo2_avgs": spo2_avgs, "temps": temps,
        "ibi_hr_bpm": ibi_hr_bpm, "fuel_gauge_pct": fuel_gauge_pct,
        "step_count": total_steps if motion_period_found else None,
        "cadence_spm": round(sum(cadence_samples) / len(cadence_samples), 1) if cadence_samples else None,
        "hrv_ms": hrv_ms,
        "asleep_6a_count": asleep_6a_count,  # asleep-state packets this cycle, ~60s each
        "ibi_packets": ibi_packets,  # raw IBI packet lists this cycle, for nightly accumulation
    }
    pull_class = classify(tags_seen, motion_event_count, charging_seen=charging_seen,
                          local_hour=time.localtime().tm_hour, step_count=max_step_count)
    return accum, pull_class, fails


_LOG_LINE_RE = _re.compile(r'^\[(.+?)\] boot_ts=(\d+) payload=([0-9a-f]+)$')


def _last_real_boot_ts_in_log(log_path):
    """Highest EVENT_TAGS-known boot_ts already present in an existing log
    file, or 0 if the file doesn't exist / has none yet.

    Used only when resuming a session at an already-existing log_path (see
    main()'s is_resume check) -- lets a watchdog-restarted process's first
    history request start from where the previous (dead) process left off,
    instead of a since_boot_ts=0 full-history re-fetch that would re-log
    everything already captured as duplicates in the same file. Mirrors
    the live loop's own checkpoint filter (tag in EVENT_TAGS) exactly,
    reading tag_name strings back out of the file instead of numeric tags.
    """
    if not _os.path.exists(log_path):
        return 0
    valid_names = set(EVENT_TAGS.values())
    max_ts = 0
    with open(log_path) as f:
        for line in f:
            m = _LOG_LINE_RE.match(line.strip())
            if m and m.group(1) in valid_names:
                ts = int(m.group(2))
                if ts > max_ts:
                    max_ts = ts
    return max_ts


# 2026-08-08: cross-NIGHT sync cursor -- experimental, testing the
# "since_boot_ts=0 every night" hypothesis in known_issues.md (0x4C never
# finalizing a fresh bout). _last_real_boot_ts_in_log above already makes a
# watchdog-restarted process resume mid-night correctly; this extends the
# same idea ACROSS nights, mirroring open_oura's decompiled Android-app
# behavior (docs/sync-orchestration.md: a persisted `nextEventToSync`
# cursor, never a from-scratch re-fetch). Separate from bout_checkpoint.json
# (which only labels bouts NEW vs carryover after the fact and never
# changed what we ask the ring for) -- this changes the actual BLE request.
SYNC_CURSOR_PATH = _os.path.join(
    _os.path.dirname(__file__), '..', 'data', 'bridge', 'last_synced_boot_ts.json')


def load_sync_cursor():
    """Highest boot_ts confirmed captured as of the end of any prior
    session, or 0 if no checkpoint exists yet / it's unreadable. Only used
    to seed a BRAND NEW night's first request (see main()) -- an in-session
    watchdog resume still uses _last_real_boot_ts_in_log, unchanged."""
    if not _os.path.exists(SYNC_CURSOR_PATH):
        return 0
    try:
        with open(SYNC_CURSOR_PATH) as f:
            return int(_json.load(f).get('last_boot_ts', 0))
    except (ValueError, OSError, TypeError):
        return 0


def save_sync_cursor(boot_ts):
    _os.makedirs(_os.path.dirname(SYNC_CURSOR_PATH), exist_ok=True)
    with open(SYNC_CURSOR_PATH, 'w') as f:
        _json.dump({'last_boot_ts': boot_ts, 'saved_at': time.strftime('%Y-%m-%dT%H:%M:%S')}, f, indent=2)


# 2026-08-08: WakeDetector candidate-state persistence, across a watchdog
# restart WITHIN one night. Real finding (known_issues.md, not yet logged
# there as of this comment -- see handoff.md 2026-08-08): a stall-restart
# killing the daemon subprocess mid-candidate silently drops WakeDetector()
# (in-memory only, recreated fresh in main()) with no "confirmed" or
# "discarded" line at all -- confirmed on a real night (09:41:21 candidate
# never resolved before a 10:37:25 stall-restart; a new candidate started
# cold right after). All persisted fields are wall-clock time.time() epoch
# values, so restoring them after a real restart gap is correct by
# construction -- the elapsed downtime itself counts toward the candidate's
# quiet-gap/confirm/verify windows exactly as if the process had never died.
# Scoped to ONE night by keying the file to log_path (which is itself
# timestamped per night) -- a brand new night can never collide with a
# leftover file from a previous one.
WAKE_STATE_FIELDS = (
    'streak', 'streak_last_ts', 'candidate_since', 'verify_since',
    'last_activity_wall_time', 'max_real_step_seen',
)


def wake_state_path(log_path):
    return log_path + '.wake_state.json'


def load_wake_state(log_path):
    path = wake_state_path(log_path)
    if not _os.path.exists(path):
        return None
    try:
        with open(path) as f:
            return _json.load(f)
    except (ValueError, OSError):
        return None


def save_wake_state(log_path, detector):
    with open(wake_state_path(log_path), 'w') as f:
        _json.dump({field: getattr(detector, field) for field in WAKE_STATE_FIELDS}, f)


async def main():
    poll_seconds = float(_sys.argv[1]) if len(_sys.argv) > 1 else 5
    duration_hr = float(_sys.argv[2]) if len(_sys.argv) > 2 else 8
    # Optional 3rd/4th args: an explicit log_path + absolute end_epoch,
    # supplied by gen3_daemon_watchdog.py so a restarted process resumes
    # the SAME overnight session instead of starting a fresh one. If
    # log_path already exists and is non-empty, this is a resume: skip the
    # header line (recompute_bridge_from_daemon.py's parser keeps exactly
    # one true header per file) and seed last_boot_ts from the file's own
    # last real entry. A manual/normal launch (no args) behaves exactly as
    # before -- this is purely additive.
    explicit_log_path = _sys.argv[3] if len(_sys.argv) > 3 else None
    explicit_end_epoch = float(_sys.argv[4]) if len(_sys.argv) > 4 else None
    # Original session start (not this restart's launch time) -- passed
    # through unchanged across every watchdog restart so wake-detection
    # below measures real elapsed session time, not a clock that resets
    # every time the watchdog relaunches this script. Falls back to "now"
    # for a manual/standalone launch with no 5th arg.
    explicit_session_start_epoch = float(_sys.argv[5]) if len(_sys.argv) > 5 else None
    session_start_time = explicit_session_start_epoch if explicit_session_start_epoch is not None else time.time()
    morning_pull_threshold_hrs = 4  # fire safety-net morning pull if less than this captured

    repo_root = _os.path.join(_os.path.dirname(_os.path.abspath(__file__)), '..', '..')
    log_dir = _os.path.join(repo_root, 'pipeline', 'data', 'raw_pulls', 'gen3_daemon')
    _os.makedirs(log_dir, exist_ok=True)

    if explicit_log_path:
        log_path = explicit_log_path
        end_time = explicit_end_epoch if explicit_end_epoch is not None else time.time() + duration_hr * 3600
    else:
        log_path = _os.path.join(log_dir, f"gen3_daemon_{time.strftime('%Y%m%d_%H%M%S')}.txt")
        end_time = time.time() + duration_hr * 3600

    is_resume = _os.path.exists(log_path) and _os.path.getsize(log_path) > 0

    digest_every = max(1, round(600 / poll_seconds))  # ~every 10 minutes
    tag_tally_since_digest = Counter()
    if is_resume:
        last_boot_ts = _last_real_boot_ts_in_log(log_path)
        cross_night_cursor_pending = False
    else:
        # 2026-08-08: seed a brand new night from the cross-night sync
        # cursor instead of always 0 -- see SYNC_CURSOR_PATH above. If the
        # ring rebooted since the checkpoint was saved, its boot_ts axis
        # reset and this stale-high value would make the first request
        # silently return nothing; cross_night_cursor_pending flags that
        # case so the first poll can retry with since_boot_ts=0 once
        # instead of being mistaken for "ring genuinely has no new data."
        last_boot_ts = load_sync_cursor()
        cross_night_cursor_pending = last_boot_ts != 0
    total_events_logged = 0
    # All IBI packet lists across all cycles, for nightly RMSSD. On a watchdog
    # resume this starts empty like everywhere else in this function -- a
    # fresh process has no memory of the pre-restart segment's IBI packets,
    # so LIVE per-cycle HRV pushes during the resumed segment are based on
    # only the new segment until enough cycles accumulate. Not fixed here:
    # the authoritative source is always the post-run recompute
    # (recompute_bridge_from_daemon.py), which re-parses the COMPLETE log
    # file from scratch regardless of how many process restarts occurred,
    # so this is a minor live-view-only gap, not a data-correctness issue.
    ibi_packets_all: list = []
    recent_tags: set = set()    # tags seen in the last two cycles; used to classify disconnects
    disconnected = asyncio.Event()

    # Live wake-detection (see WAKE_* constants + WakeDetector above).
    wake_detector = WakeDetector()
    wake_confirmed = False
    restored_wake_state = None
    if is_resume:
        restored_wake_state = load_wake_state(log_path)
        if restored_wake_state:
            for field, value in restored_wake_state.items():
                setattr(wake_detector, field, value)

    def on_disconnect(_client):
        disconnected.set()

    if is_resume:
        print(f"[{time.strftime('%Y-%m-%d %H:%M:%S')}] RESUMING existing session (watchdog "
              f"restart or manual resume): {log_path}, seeded last_boot_ts={last_boot_ts}, "
              f"original session end={time.strftime('%H:%M:%S', time.localtime(end_time))}")
        if restored_wake_state and restored_wake_state.get('candidate_since') is not None:
            print(f"[{time.strftime('%H:%M:%S')}] [WAKE-DETECT] Restored an in-progress "
                  f"candidate across the restart (candidate_since="
                  f"{time.strftime('%H:%M:%S', time.localtime(restored_wake_state['candidate_since']))}, "
                  f"max_real_step_seen={restored_wake_state['max_real_step_seen']}) -- "
                  f"continuing it instead of silently dropping it.")
        else:
            print(f"[{time.strftime('%H:%M:%S')}] [WAKE-DETECT] No in-progress candidate to "
                  f"restore (was already idle before the restart).")
    else:
        print(f"[{time.strftime('%Y-%m-%d %H:%M:%S')}] Starting Gen3 BLE daemon: "
              f"poll every {poll_seconds}s, for up to {duration_hr}h. Ctrl+C to stop.")
    print(f"Logging to: {log_path}")

    with open(log_path, "a") as logf:
        if not is_resume:
            logf.write(f"=== Daemon started {time.strftime('%Y-%m-%d %H:%M:%S')} "
                        f"(poll={poll_seconds}s, duration={duration_hr}h) ===\n")
            logf.flush()

        client = None
        cycle = 0
        while time.time() < end_time and not wake_confirmed:
            if client is None:
                # Scan first: BleakClient.connect() on macOS does not respect its
                # timeout= for bonded peripherals — CoreBluetooth queues the request
                # indefinitely instead of raising after 30s, producing ~2h gaps between
                # real reconnect attempts (confirmed 2026-07-14 overnight run).
                # BleakScanner.discover() uses a short-lived scan window so we know the
                # ring is actively advertising before calling open_connection().
                scan_timeout = max(0, min(1800, int(end_time - time.time())))
                print(f"[{time.strftime('%H:%M:%S')}] Scanning for ring (up to {scan_timeout}s)...")
                found = await scan_for_ring(timeout_seconds=scan_timeout)
                if not found:
                    print(f"[{time.strftime('%H:%M:%S')}] Ring not found in scan window — will retry.")
                    continue
                try:
                    print(f"[{time.strftime('%H:%M:%S')}] Ring detected — connecting...")
                    # 25s asyncio-level timeout: BleakClient.connect(timeout=30) does not
                    # reliably fire on macOS for bonded peripherals (CoreBluetooth queues
                    # connectPeripheral: indefinitely). The ring also stops advertising
                    # within seconds of a sleep-stage transition, so if we don't connect
                    # within ~25s the window has closed — confirmed 2026-07-17 overnight
                    # where connect() blocked from 04:31 until manually killed at 05:27.
                    client, received = await asyncio.wait_for(
                        open_connection(disconnected_callback=on_disconnect),
                        timeout=25,
                    )
                    disconnected.clear()
                    print(f"[{time.strftime('%H:%M:%S')}] Connected and authenticated.")
                except asyncio.TimeoutError:
                    print(f"[{time.strftime('%H:%M:%S')}] Connect timed out (ring likely "
                          f"stopped advertising) — will rescan.")
                    client = None
                    continue
                except (ConnectError, Exception) as e:
                    print(f"[{time.strftime('%H:%M:%S')}] Connect failed: {e} — will rescan.")
                    client = None
                    await asyncio.sleep(5)
                    continue

            try:
                # +1 makes this exclusive of the last event already captured --
                # confirmed 2026-07-12 (real hardware run) that the ring's
                # since_boot_ts filter is inclusive, causing one duplicate event
                # per cycle boundary without this.
                since = last_boot_ts + 1 if last_boot_ts else 0
                raw = await request_history(client, received, since_boot_ts=since)
                if cross_night_cursor_pending and not raw:
                    # First poll of a new night, seeded from the persisted
                    # cross-night cursor, came back empty. Can't tell from an
                    # empty response alone whether the ring genuinely has
                    # nothing new or whether it rebooted since the cursor was
                    # saved (its boot_ts axis would have reset, making this
                    # since_boot_ts meaningless) -- retry once with a full
                    # since_boot_ts=0 fetch before trusting an empty result.
                    print(f"[{time.strftime('%H:%M:%S')}] First poll using cross-night "
                          f"cursor (since_boot_ts={since}) returned nothing -- retrying "
                          f"with a full since_boot_ts=0 fetch in case the ring rebooted.")
                    raw = await request_history(client, received, since_boot_ts=0)
                cross_night_cursor_pending = False
            except Exception as e:
                print(f"[{time.strftime('%H:%M:%S')}] Poll failed: {e} — will reconnect.")
                disconnected.set()
                raw = []

            if disconnected.is_set():
                # Task 3 instrumentation: 0x53 (Wear event) in the last two cycles
                # suggests the ring was removed before the drop; absence suggests pure
                # range-drop. This is the only way to resolve off-finger vs out-of-range
                # advertising behavior with real data over time.
                wear_tag_seen = 0x53 in recent_tags
                disconnect_type = "WEAR-EVENT (ring possibly removed)" if wear_tag_seen else "RANGE-DROP (no recent 0x53)"
                print(f"[{time.strftime('%H:%M:%S')}] Disconnected [{disconnect_type}] — will rescan.")
                try:
                    await client.disconnect()
                except Exception:
                    pass
                client = None
                recent_tags.clear()
                await asyncio.sleep(2)
                continue

            # 2026-08-04: 0x11 diagnostic decode. This project has always
            # treated 0x11 as a content-free end-of-transfer ack with
            # "garbage boot_ts bytes" (see parse_event's caller-side
            # EVENT_TAGS-membership filters) -- because parse_event()
            # applies the generic tag|length|4-byte-boot_ts|payload layout
            # to it, which is the WRONG layout for this specific tag.
            # open_oura's reverse-engineering (EventBatchSummary::parse,
            # cross-checked live against real hardware) gives 0x11's real
            # structure: byte[2]=events_received, byte[3]=
            # sleep_analysis_progress, bytes[4:8]=bytes_left (u32 LE). What
            # our own code was reading as a nonsensical "boot_ts" was
            # actually these real fields misinterpreted. Decoded here
            # read-only, purely for visibility into whether the ring's
            # sleep-analysis subsystem is even running -- does not touch
            # parse_event(), the checkpoint/dedup logic, or anything
            # boot_ts-based, all of which already correctly exclude 0x11
            # from EVENT_TAGS and are left exactly as-is.
            for pkt in raw:
                if len(pkt) >= 8 and pkt[0] == 0x11:
                    events_received = pkt[2]
                    sleep_analysis_progress = pkt[3]
                    bytes_left = int.from_bytes(pkt[4:8], "little")
                    print(f"[{time.strftime('%H:%M:%S')}] [SLEEP-ANALYSIS] "
                          f"progress={sleep_analysis_progress} "
                          f"events_received={events_received} "
                          f"bytes_left={bytes_left}")

            parsed = [p for p in (parse_event(pkt) for pkt in raw) if p]
            cycle += 1

            # --- Live wake detection (see WAKE_* constants + WakeDetector) --
            cycle_activity_ts = [p["boot_ts"] for p in parsed if p["tag_name"] in ACTIVITY_TAG_NAMES_FOR_WAKE]
            # MAX single-packet value this cycle, not a sum -- see
            # MIN_REAL_STEP_COUNT's comment above ACTIVITY_TAGS.
            cycle_real_steps = 0
            for p in parsed:
                if p["tag_name"] == "Motion period":
                    try:
                        step_count = decode_motion_period(p["payload"])["step_count"]
                        cycle_real_steps = max(cycle_real_steps, step_count)
                    except (ValueError, KeyError):
                        pass
            wake_confirmed = wake_detector.process_cycle(
                cycle_activity_ts, cycle_real_steps, time.time(), session_start_time)
            save_wake_state(log_path, wake_detector)
            if wake_detector.last_event_note == "candidate_started":
                print(f"[{time.strftime('%H:%M:%S')}] [WAKE-DETECT] Candidate wake burst "
                      f"started -- confirming over the next {WAKE_CONFIRM_MINUTES} min "
                      f"before treating as a real wake-up (vs. e.g. a brief bathroom trip "
                      f"or restless in-bed movement).")
            elif wake_detector.last_event_note == "candidate_discarded":
                print(f"[{time.strftime('%H:%M:%S')}] [WAKE-DETECT] Candidate discarded -- "
                      f"quiet again, looks like a brief wake (not the real one). "
                      f"Back to watching.")
            elif wake_detector.last_event_note == "awaiting_steps":
                print(f"[{time.strftime('%H:%M:%S')}] [WAKE-DETECT] Confirmation window "
                      f"elapsed but no real walking seen yet (max single-packet reading "
                      f"{wake_detector.max_real_step_seen} so far, need {MIN_REAL_STEP_COUNT}) "
                      f"-- likely still just restless movement, not actually up. Still watching.")
            elif wake_detector.last_event_note == "provisional_confirm":
                print(f"[{time.strftime('%H:%M:%S')}] [WAKE-DETECT] Provisionally confirmed "
                      f"({WAKE_CONFIRM_MINUTES} min of activity, max real-walking reading "
                      f"{wake_detector.max_real_step_seen}) -- verifying "
                      f"for a further {WAKE_VERIFY_MINUTES} min before ending the session, "
                      f"in case this is a washroom trip that's about to go quiet again.")
            elif wake_detector.last_event_note == "verifying":
                print(f"[{time.strftime('%H:%M:%S')}] [WAKE-DETECT] Still verifying -- "
                      f"activity hasn't gone quiet yet, holding the session open.")
            elif wake_detector.last_event_note == "confirmed":
                print(f"[{time.strftime('%H:%M:%S')}] [WAKE-DETECT] Confirmed real wake-up "
                      f"({WAKE_CONFIRM_MINUTES} min initial + {WAKE_VERIFY_MINUTES} min "
                      f"verify, max real-walking reading {wake_detector.max_real_step_seen}, "
                      f"never quiet that long) -- wrapping up the session now instead of "
                      f"waiting for the {duration_hr}h ceiling.")

            # Rolling two-cycle tag window for disconnect classification (Task 3).
            # 0x53 in this window means a wear-state change preceded the drop.
            if parsed:
                recent_tags = {p["tag"] for p in parsed}

            if parsed:
                # Some tags are protocol control/terminator packets, not real
                # historical telemetry -- confirmed 2026-07-12 (real hardware
                # run) for both 0x11 (end-of-transfer ack, garbage boot_ts
                # bytes) and 0x1f (empty payload, also garbage boot_ts). Both
                # are outside EVENT_TAGS' known 0x41-0x83 event range. Rather
                # than hardcode each one as discovered, exclude ANY tag not in
                # EVENT_TAGS from checkpoint calculation -- still logged for
                # visibility, just not trusted to advance the checkpoint.
                checkpoint_candidates = [p["boot_ts"] for p in parsed if p["tag"] in EVENT_TAGS]
                if checkpoint_candidates:
                    new_max = max(checkpoint_candidates)
                    if new_max < last_boot_ts:
                        print(f"[{time.strftime('%H:%M:%S')}] boot_ts regressed "
                              f"({new_max} < {last_boot_ts}) — ring likely rebooted, "
                              f"resetting checkpoint.")
                        last_boot_ts = 0
                    else:
                        last_boot_ts = new_max
                    # Persist across nights (not just in-memory for this
                    # process) -- see SYNC_CURSOR_PATH above. Cheap enough to
                    # write every cycle that has real EVENT_TAGS data; a
                    # reboot-triggered reset to 0 is persisted too, so a
                    # rebooted ring doesn't keep getting seeded from a stale
                    # pre-reboot value on the next restart either.
                    save_sync_cursor(last_boot_ts)

                for p in parsed:
                    logf.write(f"[{p['tag_name']}] boot_ts={p['boot_ts']} payload={p['payload'].hex()}\n")
                    tag_tally_since_digest[p["tag_name"]] += 1
                logf.flush()
                total_events_logged += len(parsed)

                accum, pull_class, fails = decode_cycle_events(parsed)
                print(f"[{time.strftime('%H:%M:%S')}] cycle {cycle}: {len(parsed)} new events "
                      f"({pull_class}), {fails} decode fails")

                if pull_class == "SLEEP WINDOW":
                    # Accumulate IBI across all sleep cycles for nightly RMSSD.
                    # Per-cycle window (~5s) has too few pairs for calculate_rmssd's min_pairs=10.
                    ibi_packets_all.extend(accum["ibi_packets"])

                priority_data_present = any([
                    accum["hr_avgs"], accum["spo2_avgs"], accum["temps"],
                    accum["ibi_hr_bpm"], accum["fuel_gauge_pct"],
                    accum["step_count"] is not None,
                ])
                if priority_data_present:
                    # HRV: use nightly accumulated IBI (not per-cycle) so there are enough
                    # successive-difference pairs. Only push in sleep context.
                    nightly_hrv = calculate_rmssd(ibi_packets_all) if ibi_packets_all else None
                    hrv_for_bridge = nightly_hrv if pull_class == "SLEEP WINDOW" else None
                    bridge_data = build_bridge_data(
                        pull_class=pull_class,
                        pull_file=_os.path.basename(log_path),
                        priority_event_count=len(parsed),
                        hr_avgs=accum["hr_avgs"],
                        ibi_hr_bpm=accum["ibi_hr_bpm"],
                        temps=accum["temps"],
                        spo2_avgs=accum["spo2_avgs"],
                        fuel_gauge_pct=accum["fuel_gauge_pct"],
                        step_count=accum["step_count"],
                        cadence_spm=accum["cadence_spm"],
                        hrv_ms=hrv_for_bridge,
                        sleep_duration_hrs=None,  # 0x6A-derived duration is unreliable (undercounts --
                        # ring stops emitting 0x6A before sleep ends -- AND the live per-cycle packet-count
                        # x60s-per-packet assumption previously here was also wrong by roughly an order of
                        # magnitude: real 0x6A packets fire far more often than once per 60s, confirmed
                        # 2026-07-21 against gen3_daemon_20260720_213320.txt, 9,617 packets across a real
                        # 7h49m session = ~1 every 2.9s, not 60s -- this produced a live 92.03h "last
                        # night" push. recompute_bridge_from_daemon.py already made 0x6A unreliable for
                        # this field and hardcodes None for the same reason (2026-07-18, commit 5983beb);
                        # this live per-cycle path just never got the same fix (flagged open in
                        # SESSION_HANDOFF.md 2026-07-19, Finding 1). 0x4C is authoritative going forward --
                        # see sleep_duration_estimate_hrs for the provisional per-bout estimate.
                    )
                    bridge_data = merge_with_existing_bridge(bridge_data, repo_root)
                    write_local_bridge_file(bridge_data, repo_root)
                    push_result = push_bridge_json(bridge_data)
                    print(f"[{time.strftime('%H:%M:%S')}] [BRIDGE PUSH] {push_result}")
            else:
                print(f"[{time.strftime('%H:%M:%S')}] cycle {cycle}: no new events")

            if cycle % digest_every == 0 and tag_tally_since_digest:
                print(f"\n=== DIGEST (last ~{digest_every * poll_seconds / 60:.0f} min) ===")
                for name, count in tag_tally_since_digest.most_common():
                    print(f"  {count:4d}  {name}")
                print(f"  Total events logged this session: {total_events_logged}\n")
                tag_tally_since_digest.clear()

            await asyncio.sleep(poll_seconds)

        had_live_client = client is not None
        if client is not None:
            try:
                await client.disconnect()
            except Exception:
                pass

    print(f"\n=== Daemon session complete. Total events logged: {total_events_logged} ===")
    print(f"Full log: {log_path}")

    # Real-timestamped, persistent record of the daemon->morning-pull handoff.
    # Every automated post-daemon morning pull on record (all 4 real nights,
    # 2026-07-19/20 through 2026-07-22/23, including the one fully healthy
    # night) has failed to produce output, and stdout is only ever inherited
    # (never captured to a surviving file) across this handoff -- so there is
    # currently no way to tell, after the fact, how long the OS actually took
    # to release the peripheral or how long the scan ran before giving up.
    # This does not change the 10s buffer or the morning pull's own scan
    # timeout (known_issues.md 2026-07-23: no real timing measurement exists
    # yet to justify a specific new number, so none is guessed here) -- it
    # exists so the NEXT occurrence produces the real evidence needed to make
    # that decision instead of another unexplained silent failure.
    handoff_log = _os.path.join(repo_root, 'pipeline', 'logs', 'morning_pull_handoff.log')
    _os.makedirs(_os.path.dirname(handoff_log), exist_ok=True)

    def _log_handoff(msg):
        with open(handoff_log, "a") as hf:
            hf.write(f"[{time.strftime('%Y-%m-%d %H:%M:%S')}] {msg}\n")

    _log_handoff(f"Daemon loop exited (log={_os.path.basename(log_path)}). "
                 f"Live client at exit: {had_live_client} "
                 f"({'disconnect() called' if had_live_client else 'client was already None -- no clean disconnect to make, likely a prior unresolved connect() attempt'}).")

    # Always recompute the final bridge from the complete daemon log.
    # This runs after the main loop so it has all IBI + sleep data for the
    # nightly RMSSD and sleep duration — more accurate than per-cycle pushes
    # which only see a 5-second slice.
    print(f"\n[POST-RUN] Recomputing bridge from full daemon log...")
    import subprocess as _subprocess
    recompute_script = _os.path.join(_os.path.dirname(_os.path.abspath(__file__)),
                                      "recompute_bridge_from_daemon.py")
    _rc = _subprocess.run([_sys.executable, recompute_script, log_path, "--push"],
                          capture_output=False)
    if _rc.returncode == 0:
        print("[POST-RUN] Bridge recomputed and pushed.")
    else:
        print(f"[POST-RUN] Recompute exited with code {_rc.returncode}.")

    # Brief pause so CoreBluetooth fully releases the peripheral before the
    # morning pull opens a new connection. Without this, connectPeripheral
    # queues indefinitely behind the just-disconnected bond (macOS bug, confirmed
    # 2026-07-14). 10s is conservative; 5s has been seen to be insufficient.
    import time as _time
    print("[POST-RUN] Waiting 10s for CoreBluetooth to release peripheral...")
    _log_handoff("Starting 10s post-recompute wait before firing morning pull.")
    _time.sleep(10)

    # Always fire a morning pull immediately after the daemon ends.
    # The ring's 0x4C sleep summary (authoritative total sleep duration) only
    # appears in a fresh BLE pull while the completed session is still buffered.
    # The daemon's own 0x6A stream does not contain 0x4C. Running the pull
    # right here (~06:47) catches the ring before the buffer rolls or the
    # session transitions to active state.
    print(f"\n[MORNING PULL] Firing post-daemon pull to capture 0x4C sleep summary...")
    _log_handoff("Firing oura_gen3_morning_pull.py subprocess now.")
    pull_script = _os.path.join(_os.path.dirname(_os.path.abspath(__file__)),
                                 "oura_gen3_morning_pull.py")
    result = _subprocess.run([_sys.executable, pull_script], capture_output=False)
    if result.returncode == 0:
        print("[MORNING PULL] Completed.")
    else:
        print(f"[MORNING PULL] Exited with code {result.returncode}.")
    _log_handoff(f"Morning pull subprocess exited with code {result.returncode}. "
                 f"See oura_gen3_morning_pull.py's own morning_pull_handoff.log entries "
                 f"above for its real scan start/outcome timestamps.")


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\nStopped by user. Already-logged data and the last bridge push are preserved.")
