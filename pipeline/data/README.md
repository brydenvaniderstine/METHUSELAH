# METHUSELAH // data/ directory structure

This directory holds all BLE pull outputs and derived findings. Organized
as of 2026-06-21 reorganization.

## Structure

```
data/
  raw_pulls/
    gen3_morning/       <- output of oura_gen3_morning_pull.py, one file per run
    gen3_autoloop/      <- output of oura_gen3_auto_loop.py, one file per session
  findings/
    sleep_state_findings.md      <- sleep_state enum mapping investigation
  comparisons/
    gen3_gen4_comparison_log.csv <- nightly bpm/HRV comparison between
                                     Gen3 decode and Gen4 official Oura data
```

## What gets committed to git

- `findings/` and `comparisons/` — always committed. These are curated,
  written artifacts meant to be preserved and referenced.
- `raw_pulls/` — NOT committed by default (see .gitignore). These are bulky,
  numerous, and mostly superseded once their contents are summarized into
  findings/comparisons. Kept locally for reference but not pushed to GitHub
  to avoid repo bloat.

If a specific raw pull becomes important as primary evidence (e.g., the
pull that captured the first sleep_state transition), copy the relevant
excerpt into the findings doc directly rather than committing the whole
raw file.

## Adding new data

When running a new pull:
- `python3 tools/oura_gen3_morning_pull.py` -> move output to
  `data/raw_pulls/gen3_morning/`
- `python3 tools/oura_gen3_auto_loop.py` -> move output to
  `data/raw_pulls/gen3_autoloop/`

When logging a new comparison night: append a row to
`data/comparisons/gen3_gen4_comparison_log.csv`

When updating a hypothesis/investigation: edit the relevant file in
`data/findings/` directly (don't create dated duplicate files - keep one
running document per topic, with a changelog-style "Updated [date]" note
at the bottom, same pattern as sleep_state_findings.md).
