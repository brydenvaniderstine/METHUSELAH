#!/usr/bin/env python3
"""
METHUSELAH // Gen3 BLE daemon watchdog

Wraps oura_gen3_ble_daemon.py to recover from the confirmed connect()
deadlock: 2 confirmed occurrences (2026-07-17, 2026-07-22/23) and 1
likely-but-unconfirmed (2026-07-21/22) -- the daemon process stays alive
(the Mac itself never sleeps, confirmed via `pmset -g log` for all 3
nights) but goes silent for 74-155+ minutes, undetected until manual
intervention the next morning. See known_issues.md, 2026-07-23 entries.

Detection signal: real wall-clock time since the daemon's log file was
last written to -- NOT the packet-corruption ("garbage burst") tail
signature seen in the 2026-07-22/23 incident. That signature is not a
reliable marker: the 2026-07-21/22 incident shows the identical
multi-hour-silence symptom with a perfectly clean tail (confirmed by
direct inspection, known_issues.md 2026-07-23 investigation) -- a
burst-based detector would have missed it. "Time since last real event"
catches both without depending on which failure mode (if any) produced
extra corruption on the way down.

Threshold: STALE_MINUTES=20, justified against real timing data on
record, not picked arbitrarily:
  - 2026-07-20/21's real, confirmed-healthy end-of-night connectivity gap
    was 11 minutes (known_issues.md 2026-07-23) -- 20min clears that with
    ~1.8x real margin.
  - Both the confirmed (2026-07-22/23: 155min) and likely (2026-07-21/22:
    74min) deadlock gaps clear 20min with 3.7x-7.75x margin.
  - gen3_ble_connection.py's own scan_for_ring() can legitimately run
    silent for up to 30 real minutes in a single call if the ring simply
    isn't advertising (`timeout_seconds=min(1800, remaining)`) -- 20min
    sits BELOW that theoretical single-cycle ceiling, so in principle a
    fully legitimate long scan could trigger a restart. Accepted
    deliberately: restarting mid-scan is cheap (a fresh process just
    resumes scanning within seconds; see "Never loses data" below) while
    every extra minute spent not catching a real deadlock is a chunk of
    that night's data gone. No real night on record has ever shown a
    legitimate silent gap anywhere near 20 minutes outside the two
    confirmed/likely-deadlock nights -- this is a real, accepted
    asymmetry, not a blind spot, and is why STALE_MINUTES is a module-
    level constant instead of buried inline: revisit if a future healthy
    night ever approaches it.

Never loses data: every restart passes the SAME log_path back to a fresh
oura_gen3_ble_daemon.py process. That script's own resume-detection (an
existing non-empty file at that path) makes it append rather than
overwrite, skip re-writing the header line (recompute_bridge_from_daemon.py
trusts exactly one header per file for session_span_hrs), and seed
last_boot_ts from the file's own last real entry so the first history
request after a restart asks for only genuinely new data instead of
re-fetching (and re-logging as duplicates) the ring's entire buffer. See
oura_gen3_ble_daemon.py's _last_real_boot_ts_in_log / is_resume.

No second reconnection mechanism: a restart is just a normal fresh launch
of oura_gen3_ble_daemon.py, which already contains the validated
2026-07-21 event-driven scan-then-connect logic (gen3_ble_connection.py).
This script only ever decides WHEN to relaunch it -- it never touches BLE
directly.

Usage (replaces a direct daemon launch for overnight runs):
    python3 pipeline/tools/gen3_daemon_watchdog.py [poll_seconds] [duration_hours]

Defaults match the daemon's own: poll_seconds=5, duration_hours=8.
Stop any time with Ctrl+C -- the current daemon subprocess is terminated
cleanly and already-logged data is preserved exactly as it always has
been.
"""
import os
import signal
import subprocess
import sys
import time

TOOLS_DIR = os.path.dirname(os.path.abspath(__file__))
DAEMON_SCRIPT = os.path.join(TOOLS_DIR, "oura_gen3_ble_daemon.py")

STALE_MINUTES = 20
CHECK_INTERVAL_SECONDS = 60
GRACEFUL_KILL_TIMEOUT_SECONDS = 10
# Matches the already-established real-data finding (oura_gen3_ble_daemon.py
# POST-RUN section, 2026-07-14-confirmed) that CoreBluetooth needs a buffer
# after a disconnect before a fresh connectPeripheral: from a new process
# won't itself queue indefinitely behind the just-killed peripheral bond.
POST_KILL_RELEASE_BUFFER_SECONDS = 10
# A crash loop (e.g. a real bug, not a BLE hang) should fail loudly rather
# than spin forever -- this many consecutive exits within
# RAPID_EXIT_WINDOW_SECONDS of their own launch stops the watchdog.
MAX_CONSECUTIVE_RAPID_EXITS = 5
RAPID_EXIT_WINDOW_SECONDS = 30
# Bound on waiting for the FINAL segment's own shutdown (its POST-RUN
# recompute_bridge_from_daemon.py + oura_gen3_morning_pull.py) once nominal
# end_time is reached. Generous relative to those steps' own documented
# real cost (10s CoreBluetooth release buffer + a recompute over even the
# largest real log on record, ~30MB, well under a minute + a real morning-
# pull BLE connect/auth/request) while still bounded -- without this, a
# deadlock recurring in the last segment right at the tail would hang the
# watchdog itself forever, with nothing left to catch it. Caught by a real
# test (fake_daemon_stubborn scenario) during this feature's own build.
FINAL_SEGMENT_GRACE_SECONDS = 600


def is_stale(last_activity_epoch, now_epoch, stale_minutes=STALE_MINUTES):
    """Pure trigger logic, kept separate from the process/IO loop so it can
    be tested directly against real recorded gap durations without running
    any subprocess. See module docstring for the real-data threshold
    justification."""
    return (now_epoch - last_activity_epoch) >= stale_minutes * 60


def launch_daemon(poll_seconds, duration_hr, log_path, end_time):
    """Inherits the parent's stdout/stderr (no PIPE) -- capturing output
    without continuously draining it would fill the OS pipe buffer and
    block the child's own print() calls once full, which would be a
    self-inflicted version of the exact silent-hang failure mode this
    watchdog exists to catch. The existing `nohup ... > logfile 2>&1 &`
    launch pattern already redirects at the shell level; inheriting here
    preserves that unchanged."""
    return subprocess.Popen([
        sys.executable, DAEMON_SCRIPT,
        str(poll_seconds), str(duration_hr), log_path, str(end_time),
    ])


def kill_process(proc, label):
    print(f"[WATCHDOG {time.strftime('%H:%M:%S')}] Sending SIGTERM to {label} "
          f"(pid {proc.pid})...")
    proc.terminate()
    try:
        proc.wait(timeout=GRACEFUL_KILL_TIMEOUT_SECONDS)
        return
    except subprocess.TimeoutExpired:
        pass
    # SIGTERM relies on the interpreter checking for pending signals between
    # bytecode instructions -- if the process is genuinely stuck inside a
    # blocking native CoreBluetooth call (the exact failure this watchdog
    # exists to route around), that check may never run. SIGKILL is not
    # catchable/ignorable by the process at all -- the OS terminates it
    # unconditionally, which is what makes a full subprocess restart the
    # reliable option here rather than in-process asyncio-level
    # cancellation (already documented elsewhere as insufficient against
    # this specific macOS/CoreBluetooth behavior).
    print(f"[WATCHDOG {time.strftime('%H:%M:%S')}] {label} did not exit within "
          f"{GRACEFUL_KILL_TIMEOUT_SECONDS}s of SIGTERM -- sending SIGKILL.")
    proc.kill()
    proc.wait()


def run(poll_seconds, duration_hr, log_path=None, end_time=None,
        stale_minutes=STALE_MINUTES, check_interval=CHECK_INTERVAL_SECONDS):
    """Core watchdog loop, factored out of main() so a test can pass a
    fake/short-lived daemon script's own log path and a tiny stale_minutes/
    check_interval without waiting real minutes or touching real BLE
    hardware. Returns the number of restarts performed."""
    log_dir = os.path.join(TOOLS_DIR, '..', 'data', 'raw_pulls', 'gen3_daemon')
    os.makedirs(log_dir, exist_ok=True)
    if log_path is None:
        log_path = os.path.join(log_dir, f"gen3_daemon_{time.strftime('%Y%m%d_%H%M%S')}.txt")
    if end_time is None:
        end_time = time.time() + duration_hr * 3600

    print(f"[WATCHDOG {time.strftime('%H:%M:%S')}] Starting daemon watchdog.")
    print(f"  log:              {log_path}")
    print(f"  nominal end:      {time.strftime('%Y-%m-%d %H:%M:%S', time.localtime(end_time))}")
    print(f"  stale threshold:  {stale_minutes} min")
    print(f"  check interval:   {check_interval}s")

    restart_count = 0
    rapid_exits = 0
    proc = launch_daemon(poll_seconds, duration_hr, log_path, end_time)
    launch_time = time.time()

    try:
        while time.time() < end_time:
            time.sleep(min(check_interval, max(0, end_time - time.time())))

            exit_code = proc.poll()
            if exit_code is not None:
                if time.time() >= end_time - 5:
                    print(f"[WATCHDOG {time.strftime('%H:%M:%S')}] Daemon exited "
                          f"(code {exit_code}) at/after nominal end time -- "
                          f"session complete.")
                    return restart_count
                elapsed_since_launch = time.time() - launch_time
                print(f"[WATCHDOG {time.strftime('%H:%M:%S')}] Daemon exited early "
                      f"(code {exit_code}, {elapsed_since_launch:.0f}s after its own "
                      f"launch) before nominal end -- relaunching.")
                if elapsed_since_launch < RAPID_EXIT_WINDOW_SECONDS:
                    rapid_exits += 1
                    if rapid_exits >= MAX_CONSECUTIVE_RAPID_EXITS:
                        print(f"[WATCHDOG {time.strftime('%H:%M:%S')}] {rapid_exits} "
                              f"consecutive exits within {RAPID_EXIT_WINDOW_SECONDS}s of "
                              f"launch -- this looks like a crash loop, not a BLE hang. "
                              f"Stopping rather than spinning forever.")
                        return restart_count
                else:
                    rapid_exits = 0
                time.sleep(POST_KILL_RELEASE_BUFFER_SECONDS)
                proc = launch_daemon(poll_seconds, duration_hr, log_path, end_time)
                launch_time = time.time()
                restart_count += 1
                continue

            last_write = os.path.getmtime(log_path) if os.path.exists(log_path) else 0
            reference = max(launch_time, last_write)
            stale_for_min = (time.time() - reference) / 60
            if is_stale(reference, time.time(), stale_minutes):
                print(f"[WATCHDOG {time.strftime('%H:%M:%S')}] No new real event logged "
                      f"in {stale_for_min:.1f} min (>= {stale_minutes}min threshold) -- "
                      f"killing and restarting daemon subprocess "
                      f"(restart #{restart_count + 1}).")
                kill_process(proc, "daemon")
                time.sleep(POST_KILL_RELEASE_BUFFER_SECONDS)
                proc = launch_daemon(poll_seconds, duration_hr, log_path, end_time)
                launch_time = time.time()
                restart_count += 1
                rapid_exits = 0

        # Nominal end reached -- let the currently-running segment finish its
        # own POST-RUN recompute + morning-pull naturally rather than killing
        # it right at the boundary, but bounded: if THIS final segment is
        # itself hung (a deadlock recurring right at the tail), there is
        # nothing left to catch it once the main loop has exited.
        if proc.poll() is None:
            print(f"[WATCHDOG {time.strftime('%H:%M:%S')}] Nominal end reached -- "
                  f"waiting up to {FINAL_SEGMENT_GRACE_SECONDS}s for the daemon's "
                  f"final segment to complete its own shutdown "
                  f"(recompute + morning pull)...")
            try:
                proc.wait(timeout=FINAL_SEGMENT_GRACE_SECONDS)
            except subprocess.TimeoutExpired:
                print(f"[WATCHDOG {time.strftime('%H:%M:%S')}] Final segment did not "
                      f"complete its own shutdown within {FINAL_SEGMENT_GRACE_SECONDS}s "
                      f"-- it is likely hung too. Killing it directly; the night's data "
                      f"up to now is already safely on disk, but the automatic "
                      f"recompute/morning-pull did not run and should be triggered "
                      f"manually.")
                kill_process(proc, "final daemon segment")
        return restart_count
    except KeyboardInterrupt:
        print(f"\n[WATCHDOG {time.strftime('%H:%M:%S')}] Stopped by user -- terminating "
              f"current daemon subprocess. Already-logged data is preserved.")
        if proc.poll() is None:
            kill_process(proc, "daemon")
        raise


def main():
    poll_seconds = float(sys.argv[1]) if len(sys.argv) > 1 else 5
    duration_hr = float(sys.argv[2]) if len(sys.argv) > 2 else 8
    restart_count = run(poll_seconds, duration_hr)
    print(f"[WATCHDOG {time.strftime('%H:%M:%S')}] Watchdog session complete. "
          f"{restart_count} restart(s) this session.")


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        pass
