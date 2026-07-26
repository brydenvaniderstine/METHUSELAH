#!/usr/bin/env python3
"""Track B Condition #1 — 0x6A state transitions vs 0x5A sleep-phase cluster.

PARALLEL ANALYSIS ONLY (mirrors analyze_0x5a_stage3_gap.py's convention) --
does not modify any pipeline/decoders file or the live bridge.

Condition #1 definition (ARCHITECTURE.md): "sleep_state (0x6A) returns real
stage transitions across a full night -- not a flat '100% state=1' result.
At minimum: REM, Light, and Deep stages must appear in a single night's
pull." track_b_sleep_state_analysis.py already established 0x6A alone is a
2-state signal (0/1), not 3-stage, and flagged the path to closure as
cross-referencing 0x6A timing against the 0x5A cluster's 4-value stage
epochs (0=WAKE?, 1=LIGHT confirmed, 2=REM?, 3=DEEP?) -- this script is that
cross-reference, run for the first time against real data.

Method:
  1. Reuse recompute_bridge_from_daemon.py's real per-file tick-rate
     derivation (header start timestamp -> file mtime, full meaningful
     boot_ts span) -- not a fallback constant -- to convert 0x5A's 30s/epoch
     grid into the same boot_ts tick axis 0x6A already uses.
  2. Take the richest true-complete 0x5A burst in the file (most chunks =
     fullest reassembled epoch sequence for the night's bout), anchor its
     LAST epoch at the burst's firing boot_ts, and walk backward 30s/epoch
     (in ticks) to assign every epoch an approximate real boot_ts.
  3. For every 0x6A sample, find the nearest-in-time 0x5A epoch and build a
     contingency table: 0x6A state (0/1) x 0x5A stage (0/1/2/3/no-data).
  4. Separately check TRANSITION alignment: for every 0x6A 0<->1 transition,
     is there an 0x5A stage transition (0 <-> {1,2,3}) within a tolerance
     window nearby?

Usage:
  cd ~/methuselah && python3 pipeline/tools/track_b_condition1_crossref.py
"""
import os
import re
import sys

REPO = os.path.expanduser("~/methuselah")
sys.path.insert(0, REPO)
sys.path.insert(0, os.path.join(REPO, "pipeline", "tools"))

from pipeline.decoders import decode_sleep_phase_data, decode_sleep_period_info_2  # noqa: E402
from recompute_bridge_from_daemon import parse_daemon_log, VALID_TAG_NAMES  # noqa: E402

DAEMON_FILE = os.path.join(REPO, "pipeline", "data", "raw_pulls", "gen3_daemon",
                           "gen3_daemon_20260719_212709.txt")
BURST_GAP_THRESH = 40
EPOCH_SECS = 30
ALIGN_TOLERANCE_EPOCHS = 1  # +/- 1 epoch (~30s) tolerance for transition-alignment check


def segment_bursts(phase_pkts):
    bursts = []
    cur = {}
    cur_last_ts = None
    for ts, idx, data in phase_pkts:
        starts_new = cur and (
            (cur_last_ts is not None and ts - cur_last_ts > BURST_GAP_THRESH) or idx in cur
        )
        if starts_new:
            bursts.append((cur, cur_last_ts))
            cur = {}
        cur[idx] = data
        cur_last_ts = ts
    if cur:
        bursts.append((cur, cur_last_ts))
    return bursts


def true_complete(packets):
    if not packets:
        return False
    return set(packets.keys()) == set(range(max(packets.keys()) + 1))


def main():
    print("=== TRACK B CONDITION #1 CROSS-REFERENCE: 0x6A vs 0x5A ===")
    print(f"Source: {os.path.basename(DAEMON_FILE)}\n")

    header, entries = parse_daemon_log(DAEMON_FILE)
    print(f"Daemon started: {header['start']}, nominal duration={header['duration_h']}h")

    import time
    start_epoch = time.mktime(time.strptime(header['start'], '%Y-%m-%d %H:%M:%S'))
    end_epoch = os.path.getmtime(DAEMON_FILE)
    session_span_hrs = (end_epoch - start_epoch) / 3600
    meaningful = [e['boot_ts'] for e in entries if e['tag_name'] in VALID_TAG_NAMES]
    span_ticks = max(meaningful) - min(meaningful)
    tick_rate = span_ticks / (session_span_hrs * 3600)
    print(f"Real session span: {session_span_hrs:.3f}h  ->  tick_rate = {tick_rate:.3f} ticks/sec "
          f"(derived from this file's own header+mtime, not the fallback constant)\n")

    # ---- 0x6A timeline ----
    sixa = []
    for e in entries:
        if e['tag_name'] == 'Sleep period info (2)':
            try:
                d = decode_sleep_period_info_2(e['payload'])
                sixa.append((e['boot_ts'], d['sleep_state'], d['average_hr']))
            except Exception:
                continue
    sixa.sort()
    print(f"0x6A samples: {len(sixa)}  boot_ts range: {sixa[0][0]} - {sixa[-1][0]}\n")

    # ---- richest true-complete 0x5A burst in this file ----
    phase_pkts = []
    line_re = re.compile(r'^\[(.+?)\] boot_ts=(\d+) payload=([0-9a-f]+)$')
    with open(DAEMON_FILE) as f:
        for line in f:
            m = line_re.match(line.strip())
            if m and m.group(1) == 'Sleep phase data':
                payload = bytes.fromhex(m.group(3))
                if len(payload) == 14:
                    phase_pkts.append((int(m.group(2)), payload[0], payload[1:]))

    bursts = segment_bursts(phase_pkts)
    complete = [(b, ts) for b, ts in bursts if true_complete(b)]
    best_packets, best_ts = max(complete, key=lambda x: max(x[0].keys()))
    n_chunks = max(best_packets.keys()) + 1
    result = decode_sleep_phase_data(best_packets)
    epochs = result['epochs']
    n_epochs = len(epochs)
    print(f"Richest true-complete 0x5A burst: {n_chunks} chunks, {n_epochs} total epochs "
          f"({result['valid_epochs']} valid), firing boot_ts={best_ts}")
    print(f"Stage counts (0x5A): {result['stage_counts']}\n")

    # ---- anchor each epoch to an approximate boot_ts ----
    epoch_tick_len = EPOCH_SECS * tick_rate
    epoch_boot_ts = [best_ts - (n_epochs - 1 - i) * epoch_tick_len for i in range(n_epochs)]
    print(f"Epoch time anchor: epoch[0] ~ boot_ts {epoch_boot_ts[0]:.0f}  "
          f"epoch[-1] ~ boot_ts {epoch_boot_ts[-1]:.0f}  "
          f"(span {(epoch_boot_ts[-1]-epoch_boot_ts[0])/3600/tick_rate:.2f}h in ticks/rate)\n")

    # ---- for every 0x6A sample, find nearest 0x5A epoch by boot_ts ----
    def nearest_epoch_idx(ts):
        # binary-search-free linear scan is fine here (n_epochs ~1500, sixa ~9700 -> ~15M ops, acceptable)
        best_i, best_d = None, None
        for i, et in enumerate(epoch_boot_ts):
            d = abs(et - ts)
            if best_d is None or d < best_d:
                best_d, best_i = d, i
        return best_i

    # Restrict 0x6A samples to those falling within the 0x5A bout's time range
    # (+/- one epoch) -- outside that, there is no 0x5A epoch to compare against.
    lo, hi = epoch_boot_ts[0] - epoch_tick_len, epoch_boot_ts[-1] + epoch_tick_len
    paired = []
    for ts, state, hr in sixa:
        if lo <= ts <= hi:
            idx = nearest_epoch_idx(ts)
            paired.append((ts, state, hr, epochs[idx]))

    print(f"0x6A samples within the 0x5A bout's time window: {len(paired)} / {len(sixa)}\n")

    # ---- contingency table: 0x6A state x 0x5A stage ----
    from collections import Counter
    contingency = Counter((state, stage) for _, state, _, stage in paired)
    print("=== CONTINGENCY: 0x6A state x 0x5A stage ===")
    print(f"{'0x6A state':<12}{'5A stage 0 (WAKE?)':<20}{'5A stage 1 (LIGHT)':<20}"
          f"{'5A stage 2 (REM?)':<19}{'5A stage 3 (DEEP?)':<19}{'5A no-data':<12}")
    for state in (0, 1):
        row = [contingency.get((state, s), 0) for s in (0, 1, 2, 3, None)]
        total = sum(row)
        pct = [f"{100*c/total:.1f}%" if total else "n/a" for c in row]
        print(f"{state:<12}" + "".join(f"{c} ({p})".ljust(20 if i < 3 else 19 if i==3 else 12)
              for i, (c, p) in enumerate(zip(row, pct))))
    print()

    # ---- headline check: does 0x6A state=1 predominantly map to 0x5A sleep stages (1/2/3), ----
    # ---- and state=0 predominantly map to stage 0 (WAKE?)? ----
    state1_rows = [s for _, state, _, s in paired if state == 1]
    state0_rows = [s for _, state, _, s in paired if state == 0]
    state1_sleep_pct = 100 * sum(1 for s in state1_rows if s in (1, 2, 3)) / len(state1_rows) if state1_rows else 0
    state0_wake_pct = 100 * sum(1 for s in state0_rows if s == 0) / len(state0_rows) if state0_rows else 0
    print(f"0x6A state=1 samples landing on 0x5A stage 1/2/3 (any sleep stage): {state1_sleep_pct:.1f}%")
    print(f"0x6A state=0 samples landing on 0x5A stage 0 (WAKE?):               {state0_wake_pct:.1f}%\n")

    # ---- transition alignment ----
    print("=== TRANSITION ALIGNMENT (0x6A 0<->1 vs nearest 0x5A 0<->{1,2,3} epoch boundary) ===")
    sixa_transitions = []
    for i in range(1, len(sixa)):
        if sixa[i][1] != sixa[i - 1][1]:
            sixa_transitions.append(sixa[i][0])  # boot_ts of the transition

    def epoch_class(stage):
        if stage is None:
            return None
        return "SLEEP" if stage in (1, 2, 3) else "WAKE"

    epoch_classes = [epoch_class(s) for s in epochs]
    fivea_transition_epochs = [i for i in range(1, len(epoch_classes))
                                if epoch_classes[i] != epoch_classes[i - 1]
                                and epoch_classes[i] is not None and epoch_classes[i - 1] is not None]
    fivea_transition_ts = [epoch_boot_ts[i] for i in fivea_transition_epochs]

    print(f"0x6A transitions in this file: {len(sixa_transitions)}")
    print(f"0x5A WAKE<->SLEEP epoch-boundary transitions in this bout: {len(fivea_transition_ts)}\n")

    tol_ticks = ALIGN_TOLERANCE_EPOCHS * epoch_tick_len
    matched = 0
    for t6 in sixa_transitions:
        if any(abs(t6 - t5) <= tol_ticks for t5 in fivea_transition_ts):
            matched += 1
    match_pct = 100 * matched / len(sixa_transitions) if sixa_transitions else 0
    print(f"0x6A transitions with a matching 0x5A transition within +/-{ALIGN_TOLERANCE_EPOCHS} "
          f"epoch(s) (~{ALIGN_TOLERANCE_EPOCHS*EPOCH_SECS}s): {matched}/{len(sixa_transitions)} ({match_pct:.1f}%)\n")

    print("=== CONDITION #1 ASSESSMENT ===")
    print("0x6A remains a 2-state signal; 0x5A provides the only real 3+ stage data available.")
    print(f"State-level agreement: state=1 -> sleep-stage {state1_sleep_pct:.1f}%, "
          f"state=0 -> WAKE-stage {state0_wake_pct:.1f}%.")
    print(f"Transition-level agreement: {match_pct:.1f}% of 0x6A transitions land near an 0x5A "
          f"WAKE<->SLEEP boundary.")
    print("Caveats: epoch timing is APPROXIMATE (anchored via a derived tick rate, not an exact "
          "shared clock); nearest-neighbor matching, not interpolation; this is one bout from one "
          "night, not a corpus-wide result.")


if __name__ == "__main__":
    main()
