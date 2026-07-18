#!/usr/bin/env python3
"""Track B Condition #5 — Consecutive SLEEP WINDOW nights streak counter.

Scans all pull files (gen3_morning, gen3_evening, gen3_daemon), groups by
calendar date, classifies each date, and computes the current streak.

Classification rules (in priority order):
  DAEMON   — date has a gen3_daemon log (implies overnight BLE capture)
  SLEEP_WINDOW — at least one non-_MIXED pull file for this date where
                 sleep_lines >= SLEEP_LINES_MIN (real sleep data present)
  MIXED    — all pull files for this date are _MIXED.txt or have very
             few sleep lines (transitional data only)
  NONE     — no pull file for this date at all

A date counts toward the streak if classified SLEEP_WINDOW or DAEMON.
MIXED and NONE break the streak.

Usage:
  cd ~/Desktop/METHUSELAH/pipeline
  python3 tools/track_b_streak_counter.py [--verbose]
"""

import os
import re
import sys
from collections import defaultdict
from datetime import date, timedelta

PULL_ROOT = os.path.join(os.path.dirname(__file__), '..', 'data', 'raw_pulls')
FOLDERS = ['gen3_morning', 'gen3_evening', 'gen3_daemon']

# Minimum sleep period info (2) lines to consider a file as SLEEP WINDOW
SLEEP_LINES_MIN = 4

VERBOSE = '--verbose' in sys.argv


def count_sleep_lines(filepath):
    count = 0
    try:
        with open(filepath) as f:
            for line in f:
                if 'Sleep period info (2)' in line:
                    count += 1
    except Exception:
        pass
    return count


def classify_date(date_str, files_by_folder):
    """
    Returns (classification, notes) for a given date.
    files_by_folder: dict of folder_name -> list of (filename, filepath, is_mixed)
    """
    all_files = []
    for folder, entries in files_by_folder.items():
        for fname, fpath, is_mixed in entries:
            all_files.append((folder, fname, fpath, is_mixed))

    if not all_files:
        return 'NONE', ''

    # Daemon log is a first-class SLEEP_WINDOW — it captures the full night
    daemon_files = [(f, fp) for folder, f, fp, m in all_files if folder == 'gen3_daemon']
    if daemon_files:
        return 'DAEMON', f"daemon:{daemon_files[0][0]}"

    # Check non-MIXED files for sleep data
    non_mixed = [(folder, f, fp) for folder, f, fp, m in all_files if not m]
    mixed_only = all(m for _, _, _, m in all_files)

    if mixed_only:
        return 'MIXED', f"all_mixed({len(all_files)})"

    best_sleep_lines = 0
    best_file = ''
    for folder, fname, fpath in non_mixed:
        sl = count_sleep_lines(fpath)
        if sl > best_sleep_lines:
            best_sleep_lines = sl
            best_file = f"{folder}/{fname}"

    if best_sleep_lines >= SLEEP_LINES_MIN:
        return 'SLEEP_WINDOW', f"sleep_lines={best_sleep_lines} from {best_file}"
    elif best_sleep_lines > 0:
        return 'MIXED', f"sparse_sleep_lines={best_sleep_lines} from {best_file}"
    else:
        return 'MIXED', f"0 sleep lines in {len(non_mixed)} non-mixed files"


def daemon_credit_date(date_str, time_str):
    """Return the calendar date that this daemon log's data counts toward.

    Overnight daemons (start hour >= 18 or < 8) capture the sleep session
    that ends the NEXT morning, so their data credits the next calendar date.
    Afternoon daemons (8 <= hour < 18) captured daytime activity; credit the
    same date.
    """
    hour = int(time_str[:2])
    d = date(int(date_str[:4]), int(date_str[4:6]), int(date_str[6:8]))
    if hour >= 18 or hour < 8:
        return (d + timedelta(days=1)).strftime('%Y%m%d')
    return date_str


def scan_all_files():
    """Returns dict: date_str -> { folder: [(fname, fpath, is_mixed), ...] }"""
    by_date = defaultdict(lambda: defaultdict(list))
    pull_re = re.compile(r'gen3_pull_(\d{8})_\d{6}')
    daemon_re = re.compile(r'gen3_daemon_(\d{8})_(\d{6})\.txt')

    for folder in FOLDERS:
        folder_path = os.path.join(PULL_ROOT, folder)
        if not os.path.isdir(folder_path):
            continue
        for fname in sorted(os.listdir(folder_path)):
            fpath = os.path.join(folder_path, fname)
            is_mixed = '_MIXED' in fname

            if folder == 'gen3_daemon':
                m = daemon_re.match(fname)
                if not m:
                    continue
                # Credit to the date the daemon's sleep session ends
                credit_date = daemon_credit_date(m.group(1), m.group(2))
                by_date[credit_date][folder].append((fname, fpath, is_mixed))
            else:
                m = pull_re.search(fname)
                if not m:
                    continue
                date_str = m.group(1)
                by_date[date_str][folder].append((fname, fpath, is_mixed))

    return by_date


def main():
    by_date = scan_all_files()
    all_dates = sorted(by_date.keys())

    print("=== TRACK B CONDITION #5 — Consecutive SLEEP WINDOW streak ===")
    print()

    # Build classification table
    classified = []
    for ds in all_dates:
        d_obj = date(int(ds[:4]), int(ds[4:6]), int(ds[6:8]))
        cls, notes = classify_date(ds, by_date[ds])
        classified.append((d_obj, ds, cls, notes))

    # Print table
    print(f"{'Date':<12} {'Class':<14} Notes")
    print("-" * 60)
    for d_obj, ds, cls, notes in classified:
        marker = '✓' if cls in ('SLEEP_WINDOW', 'DAEMON') else '✗'
        if VERBOSE or True:
            print(f"{d_obj.strftime('%Y-%m-%d'):<12} {cls:<14} {marker} {notes}")

    # Check for gaps (dates with no pull that fall between pull dates)
    first_date = classified[0][0]
    last_date = classified[-1][0]
    all_date_objs = {d_obj for d_obj, _, _, _ in classified}
    gaps = []
    cursor = first_date
    while cursor <= last_date:
        if cursor not in all_date_objs:
            gaps.append(cursor)
        cursor += timedelta(days=1)

    if gaps:
        print()
        print(f"Dates with no pull file (gap = NONE = streak-breaker):")
        for g in gaps:
            print(f"  {g.strftime('%Y-%m-%d')} — NONE ✗")

    # Compute current streak (working backward from the most recent classified date)
    print()
    print("=== STREAK CALCULATION ===")

    # Build a dict of date_obj -> (cls, notes)
    cls_map = {d_obj: (cls, notes) for d_obj, ds, cls, notes in classified}

    # Include gap dates as NONE
    cursor = first_date
    while cursor <= last_date:
        if cursor not in cls_map:
            cls_map[cursor] = ('NONE', 'no_pull')
        cursor += timedelta(days=1)

    # Work backward from most recent
    sorted_dates = sorted(cls_map.keys(), reverse=True)
    streak = 0
    streak_dates = []
    for d_obj in sorted_dates:
        cls, _ = cls_map[d_obj]
        if cls in ('SLEEP_WINDOW', 'DAEMON'):
            streak += 1
            streak_dates.append(d_obj)
        else:
            break  # streak broken

    print(f"Current consecutive streak: {streak} nights")
    if streak_dates:
        print(f"  From: {min(streak_dates).strftime('%Y-%m-%d')}")
        print(f"  To:   {max(streak_dates).strftime('%Y-%m-%d')}")
    print()
    print(f"Target: 14 consecutive nights")
    print(f"Remaining: {max(0, 14 - streak)} nights")

    if streak >= 14:
        print("  *** CONDITION #5 CLOSED ***")
    else:
        # Find what broke the current streak
        if len(sorted_dates) > streak:
            break_date = sorted_dates[streak]
            break_cls, break_notes = cls_map[break_date]
            print(f"Streak broken at {break_date.strftime('%Y-%m-%d')}: {break_cls} ({break_notes})")


if __name__ == "__main__":
    main()
