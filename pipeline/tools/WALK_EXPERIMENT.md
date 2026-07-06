# Timed Walk Experiment — Decoder Unblocking Protocol

## Purpose
Unblock three decoder investigations simultaneously:
- 0x7E / 0x7F — step features (needs known step count for validation)
- 0x6E — SpO2 IBI+amplitude (needs activity with real SpO2 variance)
- 0x77 — SpO2 DC event (same requirement as 0x6E)

## Pre-walk checklist
- [ ] Gen3 ring on finger
- [ ] Phone Bluetooth turned OFF (Settings → Bluetooth → OFF)
  — Critical: if Oura app holds BLE connection, it drains the buffer before pull
- [ ] Step counter ready (phone pedometer app, manual count, or tally counter)
- [ ] Mac open and pull script ready to run immediately after walk

## Walk protocol
- Walk exactly 500 steps at a comfortable pace
- Count every step — accuracy matters for 0x7E/0x7F validation
- Keep phone in pocket (Bluetooth OFF, pedometer still works via accelerometer)
- Do not stop to check anything during the walk

## Immediately after walk
- Return to Mac within 60 seconds of completing 500th step
- Run pull immediately — do not take ring off, do not do anything else first:
```bash
cd ~/Desktop/METHUSELAH && python3 pipeline/tools/oura_gen3_morning_pull.py
```
- Note exact step count and approximate walk duration in the output filename area

## What to look for in the output
- 0x7E / 0x7F packets — should appear with step feature data
- 0x6E / 0x77 packets — may appear with SpO2 readings during activity
- 0x6B packets — motion_period data may appear

## Known failure mode to avoid
Previous walk experiment (2026-06-28) returned INCONCLUSIVE — both
"after" pulls were byte-identical to "before," most likely because the
Oura app's own BLE connection drained the buffer before the pull script
could read it. Phone Bluetooth OFF is the critical fix for this session.
