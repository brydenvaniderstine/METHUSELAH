#!/usr/bin/env python3
"""METHUSELAH // Sleep confidence instrumentation pass (PARALLEL ANALYSIS ONLY)

Does NOT modify oura_gen3_ble_daemon.py, oura_gen3_morning_pull.py,
sleep_duration_estimate.py, or any bridge output. Reads an existing daemon
log, replays the real classify() function from the daemon for ground-truth
comparison, and computes a separate weighted 5-signal sleep-confidence score
per cycle. Prints a cycle-by-cycle table plus an agreement/divergence
summary. Nothing here is wired into the live pipeline.

Built 2026-07-22 to answer three open questions:
  1. Which function produced last night's ACTIVE/MIXED/SLEEP split, and is
     it the same classify() fixed 2026-07-21 (commit 99a502c)?
  2. Is there a real off-wrist hard-gate signal (idle ring on a counter
     showing 0 motion/steps + drifting temp -- see known_issues.md
     "dishes episode", 2026-07-19) that should veto the confidence score
     entirely, separate from lowering it?
  3. Cycle-by-cycle, where does a weighted multi-signal score agree or
     diverge from the existing classify() label?

Usage:
  cd ~/Desktop/METHUSELAH
  python3 pipeline/tools/sleep_confidence_analysis.py [daemon_log_path] [--out FILE]

Defaults to the most recent file in pipeline/data/raw_pulls/gen3_daemon/.
"""
import os as _os
import re
import sys as _sys
import time

_TOOLS_DIR = _os.path.dirname(_os.path.abspath(__file__))
_sys.path.insert(0, _TOOLS_DIR)
_sys.path.insert(0, _os.path.join(_TOOLS_DIR, '..'))

from oura_gen3_ble_daemon import classify, EVENT_TAGS, SLEEP_TAGS, ACTIVITY_TAGS
from sleep_duration_estimate import SUSTAINED_MIN_EVENTS, SUSTAINED_MAX_GAP_TICKS
from decoders import (
    decode_sleep_period_info_2, decode_hrv_event, decode_sleep_temp_event,
    decode_motion_period, decode_wear_event,
)

TAG_NAME_TO_NUM = {v: k for k, v in EVENT_TAGS.items()}
DAEMON_DIR = _os.path.join(_TOOLS_DIR, '..', 'data', 'raw_pulls', 'gen3_daemon')

# --- Off-wrist gate -----------------------------------------------------
#
# Investigated against gen3_daemon_20260721_213131.txt AND the real dishes
# false-positive (gen3_pull_20260719_163325.txt, known_issues.md 2026-07-21
# entry) before deciding what gets to hard-veto here:
#
# - 0x53 STATE_CHARGING_PHASE (8): real, unambiguous (ring cannot be worn
#   while charging -- already load-bearing in classify()). VETOES.
# - 0x5D HR/HRV validity (PPG requires skin contact -- a flat/zero reading
#   is physiologically well-motivated as an off-wrist signal): NOT wired as
#   a veto. Neither available real off-wrist dataset can validate it --
#   last night's log never went off-wrist (0/40 wear events were
#   CHARGING_PHASE, and every 0x5D packet decoded to plausible 50-83bpm all
#   night, never a fully-invalid packet), and the one real off-wrist episode
#   on record (the dishes pull) captured ZERO 0x5D packets at all --
#   absence, not proof of invalidity, because that was a short manual pull
#   and 0x5D is a low-frequency tag (~1 packet/7.5min here) that the
#   dishes pull's short buffer window plausibly never reached (same
#   eviction mechanism already documented for 0x53 in known_issues.md).
#   Logged here as a CANDIDATE signal only (ppg_flag column) -- not a gate,
#   per the explicit instruction not to assume a signal works without a
#   real positive+negative case to check it against.
CHARGING_STATE = 8

# HR/HRV carry-forward window: 0x5D fires roughly every 5-8 real minutes
# (54 packets / ~405 real min in gen3_daemon_20260721_213131.txt), so most
# 5s cycles have no fresh reading. Stale readings older than this are
# treated as unavailable rather than silently reused indefinitely.
CARRY_FORWARD_SEC = 15 * 60

# Signal weights -- steps highest (most direct evidence of movement),
# motion lowest (brief/isolated movement must not flip the score -- only
# a SUSTAINED run counts, reusing SUSTAINED_MIN_EVENTS/MAX_GAP_TICKS from
# sleep_duration_estimate.py rather than redefining "sustained"). HR/HRV
# ranked above temp (temp is the slowest-moving, laggiest of the three).
# Tunable -- not derived from data, just an explainable default ordering.
WEIGHTS = {"steps": 0.35, "hr": 0.20, "hrv": 0.20, "temp": 0.15, "motion": 0.10}

LINE_RE = re.compile(r'^\[(.+?)\] boot_ts=(\d+) payload=([0-9a-f]+)$')
HEADER_RE = re.compile(r'=== Daemon started (\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}) '
                        r'\(poll=([\d.]+)s, duration=([\d.]+)h\)')


def parse_log(path):
    """Returns (header dict, list of (tag_name, boot_ts, payload_hex))."""
    header = {}
    entries = []
    with open(path) as f:
        for line in f:
            line = line.strip()
            hm = HEADER_RE.match(line)
            if hm:
                header = {"start": hm.group(1), "poll_s": float(hm.group(2)),
                          "duration_h": float(hm.group(3))}
                continue
            m = LINE_RE.match(line)
            if m:
                entries.append((m.group(1), int(m.group(2)), m.group(3)))
    return header, entries


def split_cycles(entries):
    """Split into per-cycle groups using UNKNOWN (0x11) as the real
    end-of-transfer boundary marker the daemon's own BLE protocol emits
    once per successful history request. Verified against
    gen3_daemon_20260721_213131.txt: 554 groups, matching the 554 total
    (288 SLEEP + 199 ACTIVE + 67 MIXED) cycles referenced as last night's
    split -- replaying classify() over these exact groups reproduces
    287/198/67/2(UNCLEAR) SLEEP/ACTIVE/MIXED/UNCLEAR, a 552/554 exact match.
    The residual 2-cycle gap is two genuinely ambiguous cycles (only
    State change + Debug data, no sleep or activity tags at all) that
    classify() correctly falls through to UNCLEAR on; how a prior count
    folded those 2 into SLEEP/ACTIVE isn't reproducible from this file
    alone (not logged) -- flagged, not silently matched.
    """
    cycles = []
    cur = []
    for name, bts, payload in entries:
        if name == "UNKNOWN (0x11)":
            cycles.append(cur)
            cur = []
        else:
            cur.append((name, bts, payload))
    if cur:
        cycles.append(cur)
    return cycles


def mark_sustained_motion(entries):
    """Same algorithm as sleep_duration_estimate._find_wake_signal, but
    marking every event that belongs to a qualifying run (not just the
    first run's start) -- generalized from "first sustained run in the
    file" to "which boot_ts values are part of ANY sustained run",
    because per-cycle scoring needs a yes/no for every cycle, not one
    global anchor point. Same constants, same tags, same definition of
    "sustained" -- 0x47 only here (0x7E/0x7F excluded per the task's
    explicit "Motion (0x47)" scope, unlike sleep_duration_estimate.py
    which also includes Real step feature (1)).
    """
    motion_ts = sorted(bts for name, bts, _ in entries if name == "Motion event")
    sustained = set()
    run = []
    for ts in motion_ts:
        if run and ts - run[-1] > SUSTAINED_MAX_GAP_TICKS:
            if len(run) >= SUSTAINED_MIN_EVENTS:
                sustained.update(run)
            run = []
        run.append(ts)
    if len(run) >= SUSTAINED_MIN_EVENTS:
        sustained.update(run)
    return sustained


def derive_tick_rate(header, entries, log_path):
    """Ticks/sec across the WHOLE log -- deliberately NOT
    sleep_duration_estimate.TICK_RATE_PER_MIN (655/min), which is a
    bout-local rate already documented (known_issues.md) as ~22x slower
    than the whole-log rate and not reconcilable with it. Derived fresh
    from this log's own real header start time vs the file's real last-
    write time (mtime), the same category of real-data derivation
    recompute_bridge_from_daemon.py uses, but anchored to actual elapsed
    wall time instead of the nominal --duration argument (which overstates
    elapsed time if the run stopped early, as this one did: nominal 8h,
    real ~6h46m).

    Excludes any tag not in EVENT_TAGS (mirrors the daemon's own checkpoint-
    calculation exclusion) -- confirmed necessary against this real log:
    UNKNOWN (0x11) end-of-transfer acks carry garbage boot_ts bytes that can
    land on EITHER side of the real range (both far above, e.g. 736755967,
    and far below, e.g. 5112063 -- 8 such outliers found in this file), not
    just above it, so a magnitude-only filter (e.g. "<100_000_000") is not
    sufficient on its own and silently produced a ~35x-wrong tick rate
    before this exclusion was added.
    """
    meaningful = [bts for name, bts, _ in entries if TAG_NAME_TO_NUM.get(name) in EVENT_TAGS]
    span_ticks = max(meaningful) - min(meaningful)
    start_struct = time.strptime(header["start"], "%Y-%m-%d %H:%M:%S")
    start_epoch = time.mktime(start_struct)
    end_epoch = _os.path.getmtime(log_path)
    span_secs = end_epoch - start_epoch
    if span_secs <= 0:
        span_secs = header["duration_h"] * 3600  # fallback, shouldn't happen
    return span_ticks / span_secs, min(meaningful)


def compute_baseline(entries, first_boot_ts, tick_rate, window_min=60):
    """Personal baseline from the first `window_min` minutes of REAL boot_ts
    (pre-sleep awake window), not a fixed/generic threshold. Real values
    only -- 0x5D pairs with hr_bpm==0 are excluded (invalid/uninitialized
    slot, not a real 0bpm reading).
    """
    end_bts = first_boot_ts + int(window_min * 60 * tick_rate)
    hr_vals, hrv_vals, temp_vals = [], [], []
    for name, bts, payload in entries:
        if not (first_boot_ts <= bts <= end_bts):
            continue
        try:
            if name == "HRV event":
                for pair in decode_hrv_event(bytes.fromhex(payload))["samples_5min"]:
                    if pair["hr_bpm"] > 0:
                        hr_vals.append(pair["hr_bpm"])
                        hrv_vals.append(pair["rmssd_ms"])
            elif name == "Sleep temp event":
                temp_vals.extend(decode_sleep_temp_event(bytes.fromhex(payload))["temps_c"])
        except ValueError:
            pass
    if not hr_vals or not temp_vals:
        return None  # caller must handle: no baseline, no confidence score
    return {
        "hr": sum(hr_vals) / len(hr_vals),
        "hrv": sum(hrv_vals) / len(hrv_vals),
        "temp": sum(temp_vals) / len(temp_vals),
        "n_hr": len(hr_vals), "n_temp": len(temp_vals),
        "window_min": window_min,
    }


def score_cycles(cycles, sustained_motion_ts, baseline, tick_rate, first_boot_ts):
    """Returns list of per-cycle result dicts, in cycle order."""
    results = []
    last_hr = last_hrv = last_hr_ts = None  # carry-forward state
    last_temp = last_temp_ts = None
    ppg_invalid_streak = 0
    max_ppg_invalid_streak = 0

    for idx, cyc in enumerate(cycles):
        tags_seen, motion_count, charging_seen = set(), 0, False
        step_count, has_step_reading = 0, False
        max_step_count = None  # max single 0x6B packet value this cycle -- what classify()'s
                                # MIN_REAL_STEP_COUNT check compares against (a cycle-level sum
                                # can exceed it purely from grouping multiple rest-noise packets
                                # in one poll cycle -- see oura_gen3_ble_daemon.py). Kept separate
                                # from step_count (the sum), which still feeds the "steps" vote below.
        cycle_hr = cycle_hrv = cycle_temp = None
        cycle_has_motion_evt = False
        cycle_boot_ts = cyc[-1][1] if cyc else None
        ppg_packet_fully_invalid = None  # None = no 0x5D this cycle

        for name, bts, payload in cyc:
            tag = TAG_NAME_TO_NUM.get(name)
            if tag is None:
                continue
            tags_seen.add(tag)
            if tag == 0x47:
                motion_count += 1
                cycle_has_motion_evt = True
            try:
                if tag == 0x53:
                    d = decode_wear_event(bytes.fromhex(payload))
                    if d["state"] == CHARGING_STATE:
                        charging_seen = True
                elif tag == 0x6B:
                    d = decode_motion_period(bytes.fromhex(payload))
                    step_count += d["step_count"]
                    max_step_count = d["step_count"] if max_step_count is None else max(max_step_count, d["step_count"])
                    has_step_reading = True
                elif tag == 0x5D:
                    d = decode_hrv_event(bytes.fromhex(payload))
                    pairs = d["samples_5min"]
                    ppg_packet_fully_invalid = all(p["hr_bpm"] == 0 for p in pairs)
                    valid_pairs = [p for p in pairs if p["hr_bpm"] > 0]
                    if valid_pairs:
                        cycle_hr = sum(p["hr_bpm"] for p in valid_pairs) / len(valid_pairs)
                        cycle_hrv = sum(p["rmssd_ms"] for p in valid_pairs) / len(valid_pairs)
                        last_hr, last_hrv, last_hr_ts = cycle_hr, cycle_hrv, bts
                elif tag == 0x75:
                    d = decode_sleep_temp_event(bytes.fromhex(payload))
                    if d["temps_c"]:
                        cycle_temp = sum(d["temps_c"]) / len(d["temps_c"])
                        last_temp, last_temp_ts = cycle_temp, bts
            except ValueError:
                pass

        if ppg_packet_fully_invalid is True:
            ppg_invalid_streak += 1
            max_ppg_invalid_streak = max(max_ppg_invalid_streak, ppg_invalid_streak)
        elif ppg_packet_fully_invalid is False:
            ppg_invalid_streak = 0

        # --- off-wrist hard gate ---
        # charging_seen (real 0x53 CHARGING_PHASE this cycle) overrides the
        # entire score to N/A, regardless of what the other 5 signals say --
        # per the task requirement this is a veto, not a downweight, so the
        # vote/confidence block below is skipped entirely when gated.
        gated = charging_seen

        # --- weighted confidence (skipped entirely when gated) ---
        votes, weights_used = {}, {}
        if not gated:
            if has_step_reading:
                votes["steps"] = 1.0 if step_count == 0 else 0.0
                weights_used["steps"] = WEIGHTS["steps"]
            votes["motion"] = 0.0 if (cycle_has_motion_evt and any(
                bts in sustained_motion_ts for name2, bts, _ in cyc if name2 == "Motion event")) else 1.0
            weights_used["motion"] = WEIGHTS["motion"]

            hr_fresh = last_hr is not None and cycle_boot_ts is not None and \
                (cycle_boot_ts - last_hr_ts) <= CARRY_FORWARD_SEC * tick_rate
            if baseline and hr_fresh:
                votes["hr"] = 1.0 if last_hr < baseline["hr"] else 0.0
                votes["hrv"] = 1.0 if last_hrv > baseline["hrv"] else 0.0
                weights_used["hr"] = WEIGHTS["hr"]
                weights_used["hrv"] = WEIGHTS["hrv"]

            temp_fresh = last_temp is not None and cycle_boot_ts is not None and \
                (cycle_boot_ts - last_temp_ts) <= CARRY_FORWARD_SEC * tick_rate
            if baseline and temp_fresh:
                votes["temp"] = 1.0 if last_temp < baseline["temp"] else 0.0
                weights_used["temp"] = WEIGHTS["temp"]

        total_w = sum(weights_used.values())
        confidence = (sum(votes[k] * weights_used[k] for k in votes) / total_w
                      if (not gated and total_w > 0) else None)

        results.append({
            "idx": idx, "tags_seen": tags_seen, "motion_count": motion_count,
            "charging_seen": charging_seen, "step_count": step_count if has_step_reading else None,
            "max_step_count": max_step_count,
            "gated": gated, "confidence": confidence, "votes": votes,
            "boot_ts": cycle_boot_ts, "ppg_packet_fully_invalid": ppg_packet_fully_invalid,
        })
    return results, max_ppg_invalid_streak


def main(log_path, out_path=None):
    lines_out = []

    def emit(s=""):
        print(s)
        lines_out.append(s)

    emit("=== SLEEP CONFIDENCE INSTRUMENTATION PASS (parallel analysis, not wired to live pipeline) ===")
    emit(f"Source: {_os.path.basename(log_path)}")
    emit()

    header, entries = parse_log(log_path)
    if not header:
        emit("FATAL: no daemon header found in this log -- not a daemon-format file.")
        return
    cycles = split_cycles(entries)
    emit(f"Header: {header}")
    emit(f"Total parsed event lines: {len(entries)}  |  Cycles (0x11-delimited): {len(cycles)}")

    tick_rate, first_boot_ts = derive_tick_rate(header, entries, log_path)
    emit(f"Derived whole-log tick rate: {tick_rate:.3f} ticks/sec "
         f"(NOT sleep_duration_estimate.TICK_RATE_PER_MIN=655/min -- that's bout-local, ~22x slower, "
         f"see known_issues.md)")

    baseline = compute_baseline(entries, first_boot_ts, tick_rate, window_min=60)
    if baseline:
        emit(f"Personal baseline (first {baseline['window_min']}min, pre-sleep awake window): "
             f"HR={baseline['hr']:.1f}bpm (n={baseline['n_hr']}), "
             f"HRV(RMSSD)={baseline['hrv']:.1f}ms, "
             f"temp={baseline['temp']:.2f}C (n={baseline['n_temp']})")
    else:
        emit("WARNING: could not compute a personal baseline (missing 0x5D or 0x75 data in the "
             "first 60min) -- HR/HRV/temp signals will be unavailable for every cycle, confidence "
             "score will fall back to steps+motion only where present.")
    emit()

    sustained_motion_ts = mark_sustained_motion(entries)
    emit(f"Sustained motion runs (>={SUSTAINED_MIN_EVENTS} consecutive 0x47 events within "
         f"{SUSTAINED_MAX_GAP_TICKS} ticks -- same definition as sleep_duration_estimate.py, "
         f"0x47 only): {len(sustained_motion_ts)} of the 0x47 events in this log belong to a "
         f"sustained run.")
    emit()

    results, max_ppg_invalid_streak = score_cycles(cycles, sustained_motion_ts, baseline, tick_rate, first_boot_ts)

    # Now compute real classify() labels with a proper interpolated local_hour
    # (no per-cycle wall-clock is persisted in the log; interpolating start->mtime
    # across cycle index is the same approximation validated against the
    # 287/198/67/2 reproduction above -- documented, not hidden).
    start_struct = time.strptime(header["start"], "%Y-%m-%d %H:%M:%S")
    start_epoch = time.mktime(start_struct)
    end_epoch = _os.path.getmtime(log_path)
    class_counts = {}
    divergences = []
    for r, cyc in zip(results, cycles):
        frac = r["idx"] / max(1, len(cycles) - 1)
        approx_epoch = start_epoch + frac * (end_epoch - start_epoch)
        local_hour = time.localtime(approx_epoch).tm_hour
        pull_class = classify(r["tags_seen"], r["motion_count"],
                               charging_seen=r["charging_seen"], local_hour=local_hour,
                               step_count=r["max_step_count"])
        r["pull_class"] = pull_class
        class_counts[pull_class] = class_counts.get(pull_class, 0) + 1

    emit(f"Ground-truth classify() split (real function, imported from "
         f"oura_gen3_ble_daemon.py, replayed over the {len(cycles)} real cycles): " +
         ", ".join(f"{v} {k}" for k, v in sorted(class_counts.items(), key=lambda x: -x[1])))
    emit()

    # --- off-wrist gate summary ---
    n_gated = sum(1 for r in results if r["gated"])
    emit(f"--- OFF-WRIST HARD GATE ---")
    emit(f"Cycles gated off-wrist (0x53 CHARGING_PHASE present): {n_gated}/{len(results)}")
    if n_gated == 0:
        emit("  -> Gate never fired tonight. Consistent with real data: 0/40 real 0x53 wear "
             "events this log decoded to state=8 (CHARGING_PHASE) -- the ring was worn "
             "continuously, never on the charger. This does NOT validate the gate's absence of "
             "false negatives; it means tonight simply contains no positive case to test it against.")
    emit(f"Longest run of fully-invalid 0x5D packets (candidate signal, NOT wired as a gate): "
         f"{max_ppg_invalid_streak} consecutive packet(s).")
    if max_ppg_invalid_streak == 0:
        emit("  -> Every 0x5D packet that fired tonight had at least one physiologically valid "
             "pair. No real evidence either way for a PPG-invalidity off-wrist detector from "
             "this log -- see the module docstring for why the dishes episode can't fill that "
             "gap either (0 real 0x5D packets captured in that pull).")
    emit()

    # --- per-cycle table ---
    emit(f"--- PER-CYCLE TABLE ({len(results)} cycles) ---")
    emit(f"{'idx':>4} {'classify()':<14} {'gate':<8} {'conf':>6}  votes")
    for r in results:
        gate_str = "OFF-WRIST" if r["gated"] else "-"
        conf_str = f"{r['confidence']:.2f}" if r["confidence"] is not None else "n/a"
        votes_str = ",".join(f"{k}={v:.0f}" for k, v in r["votes"].items())
        emit(f"{r['idx']:>4} {r['pull_class']:<14} {gate_str:<8} {conf_str:>6}  {votes_str}")

        # divergence: classifier says SLEEP WINDOW but confidence score disagrees (< 0.5),
        # or classifier says ACTIVE WINDOW but confidence score is high (> 0.5).
        if r["confidence"] is not None:
            if r["pull_class"] == "SLEEP WINDOW" and r["confidence"] < 0.5:
                divergences.append((r["idx"], "classify()=SLEEP WINDOW but confidence "
                                    f"{r['confidence']:.2f} (active-leaning)"))
            elif r["pull_class"] == "ACTIVE WINDOW" and r["confidence"] > 0.5:
                divergences.append((r["idx"], "classify()=ACTIVE WINDOW but confidence "
                                    f"{r['confidence']:.2f} (sleep-leaning)"))
    emit()

    emit(f"--- AGREEMENT / DIVERGENCE SUMMARY ---")
    by_class = {}
    for r in results:
        if r["confidence"] is None:
            continue
        by_class.setdefault(r["pull_class"], []).append(r["confidence"])
    for cls, vals in sorted(by_class.items()):
        emit(f"  {cls:<14} n={len(vals):4d}  mean_confidence={sum(vals)/len(vals):.2f}  "
             f"min={min(vals):.2f}  max={max(vals):.2f}")
    emit(f"  Cycles with no confidence score at all (no fresh signal of any kind): "
         f"{sum(1 for r in results if r['confidence'] is None)}")
    emit()
    emit(f"Divergent cycles ({len(divergences)}):")
    for idx, msg in divergences:
        emit(f"  cycle {idx}: {msg}")
    if not divergences:
        emit("  none")

    if out_path:
        with open(out_path, "w") as f:
            f.write("\n".join(lines_out) + "\n")
        print(f"\n[Also written to {out_path}]")


if __name__ == "__main__":
    args = _sys.argv[1:]
    out_path = None
    if "--out" in args:
        i = args.index("--out")
        out_path = args[i + 1]
        args = args[:i] + args[i + 2:]

    if args:
        log_path = args[0]
    else:
        logs = sorted(f for f in _os.listdir(DAEMON_DIR) if f.endswith(".txt"))
        if not logs:
            print("No daemon logs found.")
            _sys.exit(1)
        log_path = _os.path.join(DAEMON_DIR, logs[-1])
        print(f"(No file specified — using latest: {logs[-1]})\n")

    main(log_path, out_path=out_path)
