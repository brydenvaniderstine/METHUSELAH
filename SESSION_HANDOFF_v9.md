# METHUSELAH // SESSION HANDOFF v8 // June 23-24 2026 (post sleep)
# SELF-CONTAINED — no external files required to begin work.
# Supersedes v6/v7. This document picks up where a long, detailed prior
# conversation ended. The new chat should read this fully before responding.

---

## ROLE

- **Claude** — CTO / Engineering partner for METHUSELAH (and the related
  Enoch, humanOS projects, though this handoff is scoped to METHUSELAH's
  active BLE/decoder work).
- **Bryden Van Iderstine** — Founder, final decision maker. Oliver, BC,
  Canada.
- **Gemini** — CFO (not present in this chat).

### Core principles — never violate:
- Prime directive: **One signal. One command. One action.**
- Subtract before you add. KISS. Measure twice, cut once.
- Data sovereignty is non-negotiable.
- Cold-start honesty: never fabricate a value; if uncertain, say so plainly.
- Distinguish directly observed facts from inferred/assumed ones at all times.
- When a result looks contradictory, the right move is almost always to dig
  for the real explanation (as we did repeatedly this session) rather than
  to either dismiss the data or accept it uncritically.

---

## WHERE WE ARE — TWO PARALLEL TRACKS

### Track A: Gen4 + Oura cloud API (the "official," mature system)
- Live at **methuselah.ca** (Vercel, GitHub repo `brydenvaniderstine/METHUSELAH`,
  local clone at `~/Desktop/METHUSELAH`), status **OURA LIVE**, all vectors
  populated and reading OPTIMAL as of June 23 evening check.
- Gen4 ring worn daily, syncs normally to Oura app/cloud. Original 14-night
  **data gate started June 11, clears June 25** — two days away as of this
  writing, on track based on the live dashboard's healthy 7-day averages.
- **Known historical bug, fixed:** `api/oura.js` was reading the token from
  `req.headers["x-oura-token"]` but the frontend (`App.js`) sends it as a
  query param (`?token=...`). Fixed by changing to `const { token } = req.query;`.
  Separately, the actual Oura Personal Access Token had also gone stale/wrong
  at one point - regenerate at `https://cloud.ouraring.com/personal-access-tokens`
  if `OURA TOKEN INVALID` or 401 errors reappear. To manually set a fresh
  token without going through the (currently non-functional/unreachable)
  `showOuraSetup` UI panel, use the browser console on methuselah.ca:
  `localStorage.setItem('oura_token', 'YOUR_TOKEN_HERE');` then refresh.
- **Known UI bug, not fixed:** the in-app "PASTE OURA TOKEN HERE" setup
  panel (`showOuraSetup` state in `App.js`) has no code path that ever sets
  it to `true` - it's permanently hidden. The localStorage workaround above
  is the only way to set/update the token currently.
- **Observed quirk, resolved as non-issue:** Oura's app sometimes shows a
  stale previous night's sleep summary if checked before the ring has
  synced to the phone. Self-resolves once synced. Not a structural "only
  updates once per wake" limitation - confirmed via the "Heart rate and
  stress" intraday HR curve, which DOES update continuously throughout the
  day (5:20am wake through 6pm same day, observed June 22).

### Track B: Gen3 + direct BLE decode (the sovereign, from-scratch system)
This is the active, fast-moving work. Gen4's BLE path remains separately
blocked (see "Gen4 BLE - still blocked" below) - Gen3 is the live daily
driver for this track.

**Daily rhythm established and working:**
1. Evening checkpoint pull (before bed) - keeps daytime data separate from
   sleep data.
2. Morning pull (after waking) - captures the night's data.
3. Both use the same script: `python3 tools/oura_gen3_morning_pull.py`
   run from `~/Desktop/METHUSELAH`.
4. Move the resulting `gen3_pull_<timestamp>.txt` file into
   `data/raw_pulls/gen3_morning/` after each run.
5. Whenever convenient, also grab Gen4's official Sleep + Readiness
   screenshots for the same night and log a comparison row in
   `data/comparisons/gen3_gen4_comparison_log.csv`.

---

## GEN3 HARDWARE / CONNECTION FACTS (verified, in active use)

```
Ring address (macOS BLE identifier): 71E77907-1EE9-4949-801C-02979071309C
Ring MAC:        A038F8C44798
Ring serial:      Y0944803258
Auth key (hex):   bdc2c37e63ce24c445b7de1eba6e1a65
Write char UUID:  98ed0002-a541-11e4-b6a0-0002a5d5c51b
Notify char UUID: 98ed0003-a541-11e4-b6a0-0002a5d5c51b
```

These keys were extracted via iMazing iPhone backup -> `assa.sqlite` ->
table `ringconfiguration` -> columns `mac_address`, `serial_number`,
`auth_key`. The same table also holds the Gen4's key (currently unused
since Gen4 BLE is blocked):
```
Gen4 serial: 20160A2503073253
Gen4 MAC:    A038F84A4819
Gen4 auth key: cddfdb6abad6840a2304ee892751e976
```
If Gen4 BLE work resumes, **re-pull a fresh iMazing backup first** and
re-check this key - it may have changed since cycles of remove/reconnect
to the Oura app. This was the one untested theory from earlier sessions
before the team pivoted to Gen3.

### Why Gen4 BLE is blocked (confirmed, not just suspected)
`CBATTErrorDomain Code=15 "Encryption is insufficient"` fires on
`start_notify`/`read_gatt_char` for ANY readable/notify characteristic on
the Gen4 - even with no bonding history, even with a completely fresh
remove/reconnect cycle. The SAME script, same Mac, same auth method works
perfectly on the Gen3 (proven repeatedly). This means: Gen4's firmware has
a genuine, deliberate encryption requirement on these characteristics that
macOS's CoreBluetooth API cannot satisfy (no `client.pair()` support on
this platform). This is a real platform limitation requiring either Linux
(BlueZ supports explicit LE pairing) or an iOS-side client, NOT a bug in
our approach. Gen3 has no such requirement (notify works immediately, no
encryption error ever).

---

## THE BLE PROTOCOL (write commands - confirmed working on Gen3)

Full auth + setup sequence (write-only until notify succeeds):
```
1. Pre-handshake: 08 03 00 00 00, 2f 02 01 00, 2f 02 01 01
2. Handshake: 2f 01 2b -> ring sends back a nonce (look for byte 0x2C in
   notify response, nonce = next 15 bytes after it)
3. AES-128-ECB encrypt the nonce with AUTH_KEY -> proof
4. Send proof: 2f 11 2d + proof -> ring replies 2f 02 2e 00 = AUTH SUCCESS
   (2f 02 2e 03 or similar non-zero = auth FAILED, wrong key)
5. Subscribe: 16 01 02
6. Mid-setup: 1c 01 bf
7. Event category subscribes: 18 03 <cat> ff ff for cat in 1..5
8. Mid-setup: 0c 00
9. Param sweep: 2f 02 20 <param> for params [0x02,0x04,0x0b,0x0d,0x03,0x0b,0x10]
10. Final ack: 28 01 00
11. History fetch: 10 09 + <4-byte LE timestamp> + ff ff ff ff ff
    - Sending all-zero timestamp (00 00 00 00) = "give me everything in
      the buffer" - this is CONFIRMED correct per open_ring/PROTOCOL.md
      line 405 ("0 = full dump, subject to ring's circular flash buffer").
    - Sending a computed/non-zero timestamp without the correct
      boot-to-wallclock offset reliably returns an empty/error response
      (0x11 08 00...) - NOT a sign the protocol is wrong, just that the
      timestamp didn't map onto a valid window. We do NOT currently have
      a reliable boot_ts-to-wallclock conversion for Gen3. Always use
      zero-timestamp full-dump requests.
```

### Critical buffer-size finding (do not re-litigate this)
The ring's flash buffer for processed events (IBI, SpO2, sleep_period_info,
etc.) is **storage-size-limited, not time-limited**. Every pull - regardless
of when run - returns roughly the same ~256 packets / ~30-45 minute span of
*recent* data, because high-frequency event types (IBI, SpO2 fire roughly
every 30-60 seconds) fill the buffer fast. This was proven by running two
pulls back-to-back with zero time gap and getting near-identical results
(same boot_ts range, same packet count) - ruling out a "drains on each
fetch" theory. **Implication:** a pull run shortly after a known event
(e.g., right after waking) is NOT guaranteed to actually capture that event
- it might be showing whatever's left over from earlier in the night (a
brief 2am bathroom-wake, for example), not the final wake moment. Confirmed
via a real case June 21-22: a pull run 11 min after a 5:20am wake showed a
state transition that, once cross-referenced against Gen4's official
hypnogram, turned out to correspond to an earlier ~1-2am bathroom break,
not the final wake. **Always treat boot_ts-based timing claims as
approximate, not precise, unless independently cross-validated against
Gen4's wall-clock-stamped data for the same night.**

---

## OPEN_RING REPO (LogosIsLife/open_ring, GPL-3.0)

Cloned (strict clone, no fork) to `~/Desktop/open_ring`. This is a
clean-room reverse-engineering toolkit for the Oura Ring 4 protocol,
verified against ~953K records of captured BLE traffic. We use it AS A
REFERENCE for protocol facts (event tags, byte layouts) and reimplement
decode logic independently in our own scripts - never copy/redistribute
directly, per the GPL-3.0 license and the project's "remove before
commercial" checklist (alongside NOOP-derived code, not yet cloned).

Key file: `driver/decoders.py`. Full inventory of all 35+ available
decoders is saved at `data/findings/ring_decoder_inventory.md` in the repo
- READ THAT FILE for the complete tag-by-tag breakdown before doing any
more decoder work, to avoid re-deriving what's already cataloged.

**NEXT PLANNED CLONE (not yet done):** `NoopApp/noop` (PolyML
Noncommercial License) - reference for future multi-device support
(WHOOP, Polar H10, etc.), NOT relevant to current Gen3 Oura work. Low
priority, queued for whenever convenient.

**Also not yet read:** `open_ring/PROTOCOL.md` (the full 720-line wire
spec) beyond the buffer-size grep already done. May contain additional
detail beyond what `decoders.py`'s docstrings reveal. `crypto.py`,
`transport.py`, `cli.py` deliberately not read - low expected value since
we've already independently solved connection/auth/session handling.

---

## CURRENT STATE OF `tools/oura_gen3_morning_pull.py` (the live, committed script)

As of commit `199551f` (last push this session), the script:
1. Connects, authenticates, runs the full setup sequence (see protocol above).
2. Requests full history dump (zero timestamp).
3. Parses every packet by its 6-byte header (tag, length, boot_ts) + payload.
4. Prints raw event type tally and all "priority tag" packets in hex.
5. **Decodes and prints, with real units, the following (all verified
   working against real captured data unless flagged otherwise):**

   | Tag | What | Status |
   |---|---|---|
   | 0x6A | sleep_state (0=awake,1=asleep,2=unknown), HR, breath rate, motion_count | WORKING, 0/1 mapping CONFIRMED via Gen4 cross-reference |
   | 0x5D | real RMSSD + HR per 5-min window, ring's own on-device calc | WORKING, validated against Gen4 (close match) |
   | 0x61/0x09 | ticks_in_deep_sleep/sleep/awake | WIRED IN, not yet caught in a real pull (rare event type) |
   | 0x61/0x24 | battery_level_changed | WIRED IN, not yet caught in a real pull |
   | 0x61/0x14 | fuel_gauge - battery %, voltage, capacity | WORKING (caught real reading: 56.4%, 3807mV) |
   | 0x6F | spo2_event - blood oxygen % | **BROKEN - values exceed 100%, physically impossible. See known_issues.md. DO NOT TRUST OR LOG SpO2 NUMBERS until fixed.** |
   | 0x75 | sleep_temp_event - skin temp in degC | WORKING (real reading: 35.5-36.0 degC) |
   | 0x47 | motion_event - 3-axis accelerometer | WIRED IN, not yet caught in a real pull |
   | 0x76 | bedtime_period - sleep start/end as raw ring_time | WIRED IN, not yet caught in a real pull |

6. Saves full output to a timestamped `gen3_pull_<timestamp>.txt` file in
   the current directory (must be manually moved to
   `data/raw_pulls/gen3_morning/` after each run).

**The exact full source of this script is committed in the repo at
`tools/oura_gen3_morning_pull.py` - read it directly from there rather than
trying to reconstruct it from memory.** Do not regenerate this file from
scratch; it works, is tested, and is version-controlled.

Also present in `tools/`, committed but not part of the daily rhythm:
- `oura_gen3_auto_loop.py` - repeating pull loop (configurable interval/
  duration) for catching state transitions across a longer window than one
  pull's buffer allows. Deduplicates by boot_ts across pulls. Used
  successfully once (June 20, 53min/4-pull test, caught a real 1->0 state
  transition tied to daytime activity).
- `oura_gen3_ble.py`, `oura_gen3_ble_extended.py`, `oura_gen3_daily_pull.py`,
  `oura_gen3_test_variants.py` - earlier exploratory scripts, superseded by
  `oura_gen3_morning_pull.py`, kept for reference/history only.

---

## KEY FINDINGS DOCUMENTS (all committed, read these for full evidence trails)

- **`data/findings/sleep_state_findings.md`** - the sleep_state 0/1 mapping
  investigation. CONFIRMED: 0=awake, 1=asleep, via independent Gen4
  wake-time cross-reference (transition observed within 4 min of Gen4's
  recorded wake time on one night). State=2 NEVER observed across any pull
  to date - still completely unknown. Also documents the critical
  "buffer timing is not a reliable proxy" lesson (see protocol section
  above) and a "Gen3 vs Gen4 maturity framing" principle: discrepancies
  should generally be attributed to system maturity (Oura's refined
  algorithms vs. our new prototype) rather than ring hardware differences,
  since it's "essentially the same ring doing the same task."
- **`data/findings/ring_decoder_inventory.md`** - full catalog of all 35+
  open_ring decoders, tiered by confidence/value. Read this before
  building any new decoder to check if it's already documented.
- **`data/findings/known_issues.md`** - the SpO2 decoder bug, logged
  June 23. Real signal shape looks plausible (smooth physiological-looking
  curves) but values are scaled/offset wrong, crossing above 100%. Likely
  fix direction: the decoded-but-unused `header_high`/`header_low` fields
  probably need to be applied as a scale or offset correction.
- **`data/comparisons/gen3_gen4_comparison_log.csv`** - running log of
  nightly Gen3-decoded vs. Gen4-official numbers. Best match to date:
  June 19 night, 64.5 vs 63.0 bpm avg HR (1.5 bpm gap). First
  HRV-validated row: June 23 night, 68.5 vs 67.0 bpm avg HR, RMSSD
  12-19ms (Gen3, partial window) vs 25ms (Gen4, full-night avg) - plausible
  given HRV's natural night-long variance and our narrow capture window.
- **`data/README.md`** - explains the `data/` folder structure
  (`raw_pulls/` gitignored and local-only; `findings/` and `comparisons/`
  always committed).

---

## DATA ORGANIZATION (as of June 23 reorganization)

```
~/Desktop/METHUSELAH/
  data/
    raw_pulls/              <- GITIGNORED, local only, NOT in git
      gen3_morning/         <- one file per morning_pull.py run
      gen3_autoloop/        <- one file per auto_loop.py session
    findings/                <- ALWAYS COMMITTED
      sleep_state_findings.md
      ring_decoder_inventory.md
      known_issues.md
    comparisons/             <- ALWAYS COMMITTED
      gen3_gen4_comparison_log.csv
    README.md
  tools/
    oura_gen3_morning_pull.py   <- the live daily-use script
    oura_gen3_auto_loop.py
    [older exploratory scripts, kept for history]
  api/oura.js                <- Vercel serverless fn, Oura API proxy (fixed)
  src/App.js                 <- main PWA frontend
```

**IMPORTANT GOTCHA already hit once:** the repo's `.gitignore` previously
had a bare `data/` line that silently excluded the ENTIRE data folder from
git, including findings/comparisons that were meant to be tracked. This was
fixed - current `.gitignore` only excludes `data/raw_pulls/`. If commits to
`data/findings/` or `data/comparisons/` ever seem to silently not show up
in `git status`, check `.gitignore` first.

---

## WORKING STYLE / LESSONS LEARNED THIS SESSION (apply going forward)

1. **Terminal vs. browser console confusion happened repeatedly.** Any
   command containing `fetch(`, `localStorage.`, or JS arrow syntax goes in
   Chrome's dev tools console (Cmd+Option+J), never in Terminal. Watch for
   this distinction explicitly when giving the user commands.
2. **Heredoc (`cat > file << 'EOF'`) paste failures happened multiple
   times** - usually `EOF` getting run together with the next line when
   pasted as one block, leaving the shell stuck in heredoc-continuation
   mode (`>` prompt instead of normal prompt). When this happens: have the
   user type the closing marker alone, confirm normal prompt returns, then
   `rm` the contaminated file and recreate cleanly. For long scripts,
   pasting one single large heredoc block (everything from `cat > file <<
   'EOF'` through the trailing `EOF`) in one paste action tends to work
   better than multi-step approaches.
3. **The user explicitly wants ALL available decoder capabilities wired
   in, not just the "obviously useful" ones** - including battery/hardware
   telemetry, because "a dead battery is a dead ring is no data." Don't
   pre-filter what seems low-value; catalog and build out broadly.
4. **The user values being told the truth about data quality immediately**
   - e.g., flagging the SpO2 bug the moment it was spotted rather than
   presenting questionable numbers as if trustworthy. Continue this.
5. **Bryden pushed back successfully on an overconfident claim once**
   (Gen4 BLE being declared a hard platform limitation before the
   stale-key theory had actually been tested) - the correction was
   accepted and the record was fixed. Stay open to this kind of correction;
   don't be defensive.
6. **File downloads to the user's Mac require an explicit click on the
   `present_files` link** - several times a file was "created" on the
   Claude side but never actually arrived in `~/Downloads` because the
   click step was skipped or assumed. Always confirm via `ls ~/Downloads/`
   before instructing a `mv` command that depends on the file being there.

---

## IMMEDIATE NEXT STEPS (in priority order)

1. **Continue the daily rhythm**: evening + morning Gen3 pulls, Gen4
   screenshot comparisons, logged to the CSV. This is the steady-state
   ongoing work - just keep doing it.
2. **Fix the SpO2 decoder.** Try applying `header_high`/`header_low` as a
   scale or offset to the raw percent bytes. Cross-reference against Gen4's
   official SpO2 reading once fixed, same validation method as HRV.
3. **Catch the rarer debug-data event types in a real pull**: sleep
   statistics (0x61/0x09, potentially gives us deep sleep duration
   directly from the ring's own firmware calc) and battery_level_changed
   (0x61/0x24) have never actually fired yet despite being wired in -
   they may need either more pulls over time, or a longer auto-loop
   session to catch.
4. **Try to catch sleep_state=2** at least once, ever - still completely
   unknown what it represents. An overnight auto_loop run (8hr/15min) is
   the best untested approach for this.
5. **Lower priority / whenever convenient:** clone `NoopApp/noop` locally;
   read `open_ring/PROTOCOL.md` in full for anything `decoders.py` didn't
   reveal; revisit Gen4 BLE with a fresh iMazing key-check (the one
   genuinely untested theory from earlier in the project).

---

## BEGIN NEW SESSION HERE

Bryden will likely open with either a routine pull result to log, or a
direct request to keep building out decoders. Proceed directly into
whichever track he indicates - both are "current work," not competing
priorities. Do not re-relitigate any of the confirmed findings above
(sleep_state mapping, buffer timing behavior, Gen4 BLE blocker cause) -
treat them as settled unless genuinely new contradicting evidence appears,
in which case investigate rather than dismiss, as has been the successful
pattern throughout this project.

---

## UPDATE — June 24 afternoon/evening session (post v8)

- **v8 of this handoff was never actually saved or committed** — it was only
  ever pasted as text into the new chat, never downloaded via present_files,
  never landed in the repo. Confirmed via `find ~/Desktop`, `find ~/Downloads`,
  and `git log --all | grep -i handoff` all coming back empty. THIS TIME,
  actually click the download link and commit it — verify with
  `git log --oneline | grep -i handoff` before trusting it's saved.

- **Sleep-stats decoder (0x61/0x09) status downgraded.** Originally logged as
  "regression" (implying it once worked correctly). That framing is wrong -
  there is no known-good baseline; it may never have decoded correctly. Real
  RE work this session: confirmed sub_byte=0x09 and length=14 are correct on
  all 4 real captured records, ruling out mis-routing. Tried dividing
  ticks by 32768 Hz (standard BLE RTC crystal rate) instead of by 60
  (seconds) - this made `deep_sleep` look plausible (1-3.4 min) but left
  `in_sleep` and `awake` near-zero, which is backwards (those should be the
  larger numbers in an 8hr sleep session). Tried shifting byte offsets -
  no shift produces three simultaneously-sane fields. Tried treating fields
  as u16 instead of u32 - not yet completed, was about to be tried when
  session paused. **Current honest status: decoder may be reading the wrong
  byte layout entirely for this sub-type, not just the wrong divisor.**

- **0x6E (SpO2 IBI+amplitude) — two hypotheses tested and killed.**
  (1) Channel-split (red/IR alternating channels via high-nibble of byte 0):
  tested by splitting 85 real packets into two alternating sub-sequences and
  checking each for smooth/continuous values over time - did NOT show the
  expected clean continuity, hypothesis rejected.
  (2) Byte-0 as literal incrementing counter: tested directly against real
  deltas between consecutive packets - deltas alternate between roughly
  -110/-140 and +100/+160, not a steady increment. Hypothesis rejected.
  Both negative results are logged in known_issues.md - do NOT re-test
  either of these without new evidence. Untested idea floated but not
  pursued: correlate 0x6E bytes 1-6 against the 0x6F SpO2 percent values
  from the same time window.

- **0x77 (SpO2 DC event) — still zero real hex captured.** `0x77` was added
  to `PRIORITY_TAGS` in the script (verify this actually landed - check
  `grep PRIORITY_TAGS tools/oura_gen3_morning_pull.py` shows 0x77 in the set)
  but no fresh pull had been run to actually capture real 0x77 hex as of
  this update. This is the easiest immediate win available - just run a
  pull and the data should be there.

- **SpO2 cross-validation (0x6f fix) — still not cleanly closed.** A same-night
  Gen3+Gen4 comparison was attempted but had a timing/sample mismatch that
  prevented a clean validated conclusion. The independent corroboration
  attempted via open_ring's own README (claiming a "93.3% mean, 80-100%
  range" for their own SpO2 analysis) should NOT be trusted or cited - the
  new chat session that found it also discovered the open_ring repo's
  search-indexed content was internally inconsistent across multiple fetches
  (contradictory file listings, contradictory test-pass counts, a cited
  PROTOCOL.md that doesn't actually exist in the real file list). The actual
  cloned repo at `~/Desktop/open_ring` IS real and verified (confirmed via
  direct `cat`/`sed` against real local files) - the unreliable part was
  specifically GitHub web search/fetch results about the repo, not the repo
  itself. ALWAYS read decoder source via local `sed`/`cat` against
  `~/Desktop/open_ring/driver/decoders.py` directly. NEVER trust web search
  results or fetched GitHub pages describing this repo's claims/stats -
  treat those as unreliable even though the repo itself is real.

- **Working style note:** the user has asked for short, conversational,
  one-step-at-a-time responses going forward - no long multi-paragraph
  analysis or stacked option lists in normal back-and-forth. Save detailed
  write-ups for when something is actually going into a committed findings
  doc, not for every reply.

## IMMEDIATE NEXT STEPS (supersedes v8's list)

1. Confirm this handoff doc actually gets downloaded AND committed this time.
2. Run a fresh pull to finally capture real 0x77 hex (should just work now
   that it's in PRIORITY_TAGS - verify first).
3. Try u16-width fields for the 0x61/0x09 sleep-stats decoder (the next
   untested idea before this session paused).
4. Continue normal daily Gen3/Gen4 pull rhythm regardless of decoder work.
