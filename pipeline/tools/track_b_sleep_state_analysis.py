#!/usr/bin/env python3
"""Track B Condition #1 — Full-night sleep state timeline from daemon log.

Reads a gen3_daemon log file, decodes all 0x6A (Sleep period info 2)
entries, and produces a full-night state-transition timeline.

This analysis was not possible with morning pulls (7-15 samples, ~10min
window). The daemon captures ~250 samples across a full 8-hour night,
exposing real state oscillations.

Condition #1 definition (ARCHITECTURE.md):
  "sleep_state (0x6A) returns real stage transitions across a full night —
  not a flat '100% state=1' result. At minimum: REM, Light, and Deep
  stages must appear in a single night's pull."

Current status: 0x6A provides 2 states (0 and 1), not the 3-stage
REM/Light/Deep breakdown the condition requires. The 0x5A cluster (when
it fires on a daemon night) provides 4-stage data — cross-referencing
0x6A timing with 0x5A epochs is the path to closing this condition.

Usage:
  cd ~/Desktop/METHUSELAH/pipeline
  python3 tools/track_b_sleep_state_analysis.py data/raw_pulls/gen3_daemon/<logfile>
"""

import sys, os, re

sys.path.insert(0, os.path.dirname(__file__))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from decoders import decode_sleep_period_info_2

STATE_LABELS = {0: "AWAKE/LIGHT", 1: "ASLEEP/DEEP"}


def parse_daemon_log(filepath):
    entries = []
    with open(filepath) as f:
        for line in f:
            line = line.strip()
            if '[Sleep period info (2)]' not in line:
                continue
            parts = line.split()
            try:
                boot_ts = int(next(p for p in parts if p.startswith('boot_ts=')).split('=')[1])
                payload_hex = next(p for p in parts if p.startswith('payload=')).split('=')[1]
                d = decode_sleep_period_info_2(bytes.fromhex(payload_hex))
                entries.append((boot_ts, d))
            except Exception:
                continue
    return entries


def state_runs(entries):
    runs = []
    prev_state = None
    run_start_ts = run_start_idx = 0
    for i, (bt, d) in enumerate(entries):
        s = d['sleep_state']
        if s != prev_state:
            if prev_state is not None:
                runs.append({
                    'state': prev_state,
                    'start_ts': run_start_ts,
                    'end_ts': bt,
                    'n': i - run_start_idx,
                    'span_ticks': bt - run_start_ts,
                })
            prev_state = s
            run_start_ts = bt
            run_start_idx = i
    if prev_state is not None:
        runs.append({
            'state': prev_state,
            'start_ts': run_start_ts,
            'end_ts': entries[-1][0],
            'n': len(entries) - run_start_idx,
            'span_ticks': entries[-1][0] - run_start_ts,
        })
    return runs


def hr_stats(entries, state=None):
    hrs = [d['average_hr'] for _, d in entries if state is None or d['sleep_state'] == state]
    if not hrs:
        return None
    return {'min': min(hrs), 'max': max(hrs), 'avg': round(sum(hrs)/len(hrs), 1), 'n': len(hrs)}


def main(logfile):
    if not os.path.exists(logfile):
        print(f"ERROR: file not found: {logfile}")
        sys.exit(1)

    print(f"=== TRACK B CONDITION #1 — Full-night sleep state analysis ===")
    print(f"Source: {os.path.basename(logfile)}")
    print()

    entries = parse_daemon_log(logfile)
    if not entries:
        print("No 0x6A entries found in this log.")
        sys.exit(0)

    total_span = entries[-1][0] - entries[0][0]
    print(f"Samples: {len(entries)}  boot_ts span: {entries[0][0]}→{entries[-1][0]}  ({total_span} ticks)")
    print()

    # State distribution
    from collections import Counter
    dist = Counter(d['sleep_state'] for _, d in entries)
    print("State distribution:")
    for s in sorted(dist):
        pct = dist[s] / len(entries) * 100
        stats = hr_stats(entries, s)
        print(f"  state={s} [{STATE_LABELS.get(s,'?'):12s}]: {dist[s]:>4} samples ({pct:4.1f}%)  "
              f"HR {stats['min']:.1f}–{stats['max']:.1f} bpm  avg {stats['avg']:.1f}")
    print()

    # State-transition runs
    runs = state_runs(entries)
    transitions = sum(1 for i in range(1, len(runs)) if runs[i]['state'] != runs[i-1]['state'])
    print(f"State transitions: {transitions}  (across {len(runs)} runs)")
    print()

    # Long runs (most meaningful — represent real sleep architecture blocks)
    print("Run sequence (state=1 spans ≥ 3 samples highlighted):")
    cumulative_ticks = 0
    for r in runs:
        marker = " ◀ DEEP BLOCK" if r['state'] == 1 and r['n'] >= 5 else ""
        label = STATE_LABELS.get(r['state'], '?')
        print(f"  state={r['state']} [{label:12s}]  samples={r['n']:>4}  "
              f"span={r['span_ticks']:>7} ticks{marker}")
        cumulative_ticks += r['span_ticks']
    print()

    # Summary for condition #1
    unique_states = set(d['sleep_state'] for _, d in entries)
    print("=== CONDITION #1 ASSESSMENT ===")
    print(f"States observed: {sorted(unique_states)} (need 3+ distinct stages for closure)")
    print(f"Transitions this night: {transitions}")
    if transitions >= 4:
        print("  Real sleep architecture visible: multiple state oscillations across night.")
    else:
        print("  Few transitions — may be a single consolidated block or limited data window.")
    print()
    print("Blocker: 0x6A is a 2-state signal (0=AWAKE/LIGHT, 1=ASLEEP/DEEP).")
    print("Full condition requires REM/Light/Deep identification.")
    print("Path: wait for 0x5A cluster to fire on a daemon night, then")
    print("cross-reference 0x5A stage epochs with 0x6A transition timing.")


if __name__ == "__main__":
    if len(sys.argv) < 2:
        ddir = os.path.join(os.path.dirname(__file__), '..', 'data', 'raw_pulls', 'gen3_daemon')
        logs = sorted(f for f in os.listdir(ddir) if f.endswith('.txt'))
        if not logs:
            print("Usage: python3 track_b_sleep_state_analysis.py <daemon_log>")
            sys.exit(1)
        logfile = os.path.join(ddir, logs[-1])
        print(f"(No file specified — using latest: {logs[-1]})")
        print()
    else:
        logfile = sys.argv[1]
    main(logfile)
