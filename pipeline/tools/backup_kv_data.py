#!/usr/bin/env python3
"""
METHUSELAH // KV data backup

Backs up the two Vercel KV keys that have no backup anywhere else:
manual_glucose (api/glucose.js) and vector_history (api/vector-history.js).
Unlike the raw BLE pulls (already synced nightly to methuselah-raw-data by
sync.sh), these two keys are the ONLY copy of their data -- glucose is
manual entry with no raw capture file behind it, and vector_history is
derived/aggregated state with no other source. If Vercel KV is ever
cleared, corrupted, or the project deleted, both are permanently
unrecoverable without this. Found + fixed 2026-08-16.

Reuses DASHBOARD_ACCESS_KEY (the same credential a browser needs to log in)
rather than a separate machine secret like GEN3_BRIDGE_WRITE_SECRET --
deliberately different from gen3-bridge.js's write path, which needs its
own secret because an external automated pipeline writes there (see that
file's own "different actor, different credential" comment). This script
only ever READS, running locally under the account owner's own control --
the same authorized-access shape as a human logging in via browser, not a
separate machine actor writing new data. No new secret needed.

Called from methuselah-raw-data/sync.sh, same cadence as the raw-pull
backup (once per daemon session) -- these are point-in-time snapshots;
git's own commit history across each sync IS the backup history, no
snapshot-rotation logic needed here.

Usage: python3 backup_kv_data.py <output_dir>
Always exits 0, even on partial failure -- best-effort, matches
gen3_bridge.py's push_bridge_json() convention: never let this script's own
failure look like the primary raw-pull backup failed.
"""
import json
import os
import sys
import urllib.request
import urllib.error

ENDPOINTS = {
    "manual_glucose.json": "https://www.methuselah.ca/api/glucose",
    "vector_history.json": "https://www.methuselah.ca/api/vector-history",
}


def fetch(url, key, timeout=10):
    req = urllib.request.Request(url, headers={"x-dashboard-key": key})
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return json.loads(resp.read().decode("utf-8")), None
    except urllib.error.HTTPError as e:
        if e.code == 404:
            # glucose.js 404s when no reading has ever been entered yet --
            # not a failure, just nothing to back up yet.
            return None, "no data yet (404)"
        return None, f"HTTP {e.code}: {e.read().decode(errors='replace')}"
    except Exception as e:
        return None, str(e)


def main():
    if len(sys.argv) != 2:
        print("Usage: python3 backup_kv_data.py <output_dir>", file=sys.stderr)
        sys.exit(1)
    output_dir = sys.argv[1]

    key = os.environ.get("DASHBOARD_ACCESS_KEY")
    if not key:
        print("[KV BACKUP] Skipped -- DASHBOARD_ACCESS_KEY not set in this environment.")
        sys.exit(0)

    os.makedirs(output_dir, exist_ok=True)

    for filename, url in ENDPOINTS.items():
        data, err = fetch(url, key)
        if err:
            print(f"[KV BACKUP] {filename}: {err}")
            continue
        path = os.path.join(output_dir, filename)
        with open(path, "w") as f:
            json.dump(data, f, indent=2, sort_keys=True)
        print(f"[KV BACKUP] {filename}: wrote {os.path.getsize(path)} bytes")

    sys.exit(0)


if __name__ == "__main__":
    main()
