# METHUSELAH — iOS Shortcut Setup

Two lock screen shortcuts. One tap = pull runs on Mac, files itself,
no terminal required. Works at any hour, any shift, any wake time.

## Absolute paths (recorded 2026-07-01)
- Repo root: `/Users/brydenvaniderstine/Desktop/METHUSELAH`
- Python:    `/usr/bin/python3`
- Hostname:  `Brydens-MacBook-Pro.local`
- User:      `brydenvaniderstine`

## Prerequisites
- Mac: Remote Login enabled (System Settings → General → Sharing → Remote Login)
- iPhone: Shortcuts app installed
- Both devices on same network OR Mac accessible via Tailscale/VPN if remote

## Shortcut 1 — Morning pull (tap when you wake up, before getting up)

1. Open Shortcuts app → tap + to create new shortcut
2. Add action: "Run Script over SSH"
3. Configure:
   - Host: `Brydens-MacBook-Pro.local` (or Mac's local IP)
   - User: `brydenvaniderstine`
   - Authentication: Password or SSH Key (SSH Key recommended)
   - Port: 22
   - Script: `bash /Users/brydenvaniderstine/Desktop/METHUSELAH/pipeline/tools/pull_morning.sh`
4. Rename shortcut: **METHUSELAH MORNING**
5. Add to Lock Screen widget

## Shortcut 2 — Evening pull (tap before sleep)

Same steps as above but:
   - Script: `bash /Users/brydenvaniderstine/Desktop/METHUSELAH/pipeline/tools/pull_evening.sh`
   - Rename shortcut: **METHUSELAH EVENING**
   - Add to Lock Screen widget beside the morning shortcut

## Usage
- Wake up → tap **METHUSELAH MORNING** before feet hit floor
- Going to sleep → tap **METHUSELAH EVENING** before lights out
- That's it. No terminal. No manual file moves. No timing constraints.
- Works on day shift, night shift, days off, any wake time.

## Verification
After tapping a shortcut, check:
- `pipeline/data/logs/morning_pull.log` or `evening_pull.log` for output
- `pipeline/data/raw_pulls/gen3_morning/` or `gen3_evening/` for the filed pull
- `pipeline/data/bridge/gen3_latest.json` for the bridge data (feeds methuselah.ca)
