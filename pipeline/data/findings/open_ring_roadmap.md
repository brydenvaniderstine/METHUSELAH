# ── UPDATE RULE ──────────────────────────────────────────────
# Claude Code must append to this file at the end of any session
# that produces a new finding, confirmed pattern, or resolved/
# unresolved decoder question. Do not wait to be asked explicitly.
# If a session ends without touching this file and a finding occurred,
# that is an error. Last updated: 2026-07-07 (0x5D firing context confirmed ACTIVITY-only; 0x6B DONE; step count in bridge)
# ─────────────────────────────────────────────────────────────
#
# ── CREDENTIAL HANDLING ─────────────────────────────────────
# Do not paste live tokens/credentials into this file. Reference that a
# credential exists and where it's stored — never the literal value.
# ─────────────────────────────────────────────────────────────

# METHUSELAH // open_ring Decoder Roadmap (COMPLETE — all 38 decoders tracked)

Scope: every single decoder that exists in open_ring's driver/decoders.py,
per the full inventory. Nothing omitted, including low-value diagnostic
sub-types. This supersedes the earlier partial roadmap.

## Rules of the road (apply to every decoder, no exceptions)
1. Real source only — read `~/Desktop/open_ring/driver/decoders.py`
   directly via `cat`/`sed`. Never trust web search or fetched GitHub
   pages about this repo (confirmed unreliable 2026-06-24).
2. No decoder is "working" until tested against real captured hex from
   your own ring.
3. Negative results (killed hypotheses) get logged, not discarded.
4. One decoder at a time.

## DONE — working, validated against real data (16)
- [x] 0x6A sleep_period_info_2 (sleep_state)
- [x] 0x5D hrv_event (HRV/RMSSD) — ACTIVITY-ONLY. Fires during DHR session only (2026-07-07).
      Single corpus packet: HR 70-72 bpm (activity HR), co-occurs with step features and EHR boundary.
      Zero packets in any of 10 sleep pulls. Buffer window during sleep = 7-12 min (255 packets ÷ 3.70
      ticks/sec); if 0x5D fired during sleep, 1-2 events WOULD appear. Definitive: does not fire in sleep.
      Sleep HRV NOT accessible via 0x5D — must be derived from 0x6E/0x80 IBI streams or is server-computed.
      Track B condition #2 (0x5D in 3 consecutive morning pulls) cannot be met as defined. Owner decision
      required: redefine using IBI-RMSSD, change pull timing, or remove gate.
      RE-VERIFIED 2026-07-10 against the current full corpus (roughly 2x the original sample): 0/21
      SLEEP WINDOW files contain any 0x5D packet, zero exceptions. 1/5 MIXED files do (same single
      instance already tracked). Confirms hardware/protocol limitation, not a decoding gap — see
      known_issues.md. Condition #2 was already redefined to evening-activity-only (2026-07-07,
      Option A); this finding does not affect that track.
- [x] 0x61/0x14 fuel_gauge_statistics (battery %, voltage, capacity)
- [x] 0x75 sleep_temp_event (skin temp, degC)
- [x] 0x47 motion_event (3-axis accelerometer)
- [x] 0x6F spo2_event (SpO2, fixed with offset=+6, internal consistency
      confirmed; Gen4 cross-validation: systematic low bias confirmed.
      Mean gap Gen4−Gen3: +3.97% across 3 paired nights (stdev 1.86%).
      Bias is in raw sensor bytes, not arithmetic. Fixed calibration offset
      NOT applied — gap varies too widely (1.9%→5.5%) for ±2% gate.
      Need ≥5 paired nights with stdev <1.0%. Decoder unchanged 2026-07-07.)
- [x] 0x53 wear_event — format: state:u8 + text:ascii (duration of prior
      state in seconds, as numeric string). STATE_CHANGE enum confirmed
      (states 1 and 3 validated against 2 real packets 2026-06-27).
- [x] 0x69 temp_period — i16 LE / 100 = °C. CONFIRMED 2026-06-27 by
      cross-check with 0x75 at ts=40728926/40728928 (2-tick gap, values
      match to within 0.06°C). Same formula as 0x75; 0x69 appears to be
      a single-value period average of the same skin-temp sensor.
- [x] 0x6E spo2_ibi_and_amplitude_event — IBI CONFIRMED 2026-07-06. Fixed 13 bytes.
      b0=channel byte (bit7=A/B optical channel, low7=beat index); b1..b5=5× IBI
      high bytes; b6..b10=5× IBI low+amp; b11=mid bits for IBI[0..3]; b12=amp shift
      nibble. Same bit-pack as 0x60 but 5 pairs. 549/549 corpus packets decode without
      error. Cross-validated vs 0x6A avg_hr (5 sleep files): delta −1.1 to +1.3 bpm.
      Activity context divergence (+7-8 bpm) is expected and physiologically correct.
      Amplitude physical units and IBI[4] mid bits still unresolved (open).
      Decoder: `pipeline/decoders/0x6e.py`. Wired into pull script.
- [x] 0x6B motion_period — DONE 2026-07-07. b[0] = per-window step count confirmed via
      timed walk experiment (~500 steps ground truth; decoded sum 497, 0.6% error).
      b[1] = cadence candidate (steps/min; 116-120 observed at brisk walk pace).
      open_ring MOTION_STATE enum is WRONG for b[0] — values 98-101 are far outside {0-3}.
      Remaining fields: b[2] unknown, b[3] approaching uint8 ceiling during activity,
      b[4]=overflow flag (fires 1 when b[3]≥246). Decoder: `pipeline/decoders/0x6b.py`.
      Wired into pull script — prints per-packet steps + cadence + running total.
- [x] 0x80 green_ibi_quality_event — VALIDATED 2026-06-30. Format:
      N×(b_low,b_high) pairs (payload always even; 345/361 pkts are 14 bytes = 7
      samples). 11-bit IBI: (b_low<<3)|(b_high&0x07). quality_a: (b_high>>3)&0x03.
      quality_b: (b_high>>5)&0x07. HR = 60000/IBI_ms.
      Cross-validated against 0x6A avg_hr on 3 pulls: delta −0.1 to +1.6bpm
      (mean +0.9bpm) — essentially perfect agreement. IBI=2000ms is a sentinel
      (60 exact hits = "no beat detected"; 11-bit max is 2047). Session-gated:
      only fires when GREEN_IBI session active — present in 9/29 pulls, absent
      in others by design (not a gap). quality_a=1 dominant (65%); qa=0/2/3
      semantics unresolved. NOT activity-only — fires in sleep, transitional,
      and active windows wherever the GREEN_IBI session is running.
- [x] 0x61/0x04 _dd_alt_text — DONE 2026-07-11. Literal ASCII debug text (n=2:
      "EHRts;47", "EHRts;45"). Decoder: `pipeline/decoders/0x61_04.py`.
- [x] 0x61/0x0a _dd_flash_usage_statistics — DONE 2026-07-11, n=57. u32 LE trio
      matches open_ring exactly. Fires as a fixed bundle with 0x61/0x0c/0x0d
      immediately after every 0x61/0x09 event. Decoder: `pipeline/decoders/0x61_0a.py`.
- [x] 0x61/0x0c _dd_period_info_statistics — DONE 2026-07-11, n=57. Strong
      cross-tag validation: ticks_measuring_last_period matches 0x61/0x0d's
      ticks_advertising_mode within single digits across all 57 samples;
      pfsm_state field matches the already-confirmed 0x61/0x09 field exactly.
      Decoder: `pipeline/decoders/0x61_0c.py`.
- [x] 0x61/0x0d _dd_ble_usage_statistics — DONE 2026-07-11, n=57. See 0x61/0x0c
      cross-validation. fast/slow mode ticks always 0 (idle/monitoring pulls
      only, no active phone connection observed). Decoder: `pipeline/decoders/0x61_0d.py`.
- [x] 0x61/0x29 _dd_acm_configuration_changed — DONE 2026-07-11, n=37. Clean
      discrete accelerometer config states (mode/odr/range move together:
      2/5/2, 3/7/2, 4/10/3). Gyro fields always 0 — gyro appears disabled.
      Decoder: `pipeline/decoders/0x61_29.py`.
- [x] 0x61/0x24 _dd_battery_level_changed — DONE, decoder already existed
      and was correct; was mislabeled "never caught a real packet yet" in
      the old Tier 3 list. Re-verified 2026-07-11 against all 10 corpus
      packets, all physically plausible. See known_issues.md 2026-07-10/11.

## IN PROGRESS — real RE work started, not yet solved (3)
- [ ] 0x61/0x09 _dd_sleep_statistics — 68 packets across corpus (updated 2026-07-07).
      Layout confirmed: b1-b2=f0, b3-b4=o3(secs_in_pfsm), b5-b6=f2(decaying),
      b7-b8=pad(0), b9-b10=f4(dynamic), b11-b12=f5(flag), b13=pfsm_state.
      pfsm_state values in corpus: {3, 4, 5, 6, 128}.
      NEW FINDING (2026-07-06): pfsm_state values segregate by sleep vs activity
      context. pfsm=6 fires ONLY in sleep context (co-present with 0x6A packets).
      pfsm=3/4 fire ONLY in activity/waking context. pfsm=5 fires in both.
      pfsm=128 = always companion/echo record (ts gap <12 ticks from primary).
      f2 decay rate by state: pfsm=3→128: ~4.5% retention (fast-decaying, active);
      pfsm=5→128: ~10-12% retention; pfsm=6→128: ~55% retention (slow, sleep).
      open_ring has NO enum for pfsm_state — raw u8 only. No pfsm=0,1,2 seen.
      CEILING: exact state machine enum needs firmware. Physical meaning of f0/f2/f4
      unconfirmed. Whether pfsm=5 is boundary state or parallel state unknown.
      STATUS: structure confirmed / pfsm context hypothesis new / meaning open.
      F2/F4 HYPOTHESIS TEST (2026-07-10): systematically tested offset/endianness/
      signed/bitfield hypotheses against 114 real records — all ruled out, confirmed
      u16 LE unsigned layout stands. Also fully explained the 2026-06-24 "impossible
      values" bug: it was open_ring's u32-width misread (ticks_in_sleep==f2 exactly
      in 113/114 records; ticks_awake==f4+f5*65536 always) — already fixed by the
      u16 layout, not a live issue. Gen4 deep_pct cross-reference (n=5 nights):
      r=0.17 (f2) / r=0.44 (f4), not significant at this sample size — inconclusive,
      not negative. Huge within-night f2/f4 variance (up to 137x) argues these are
      fast-changing instantaneous values, not stable per-night summaries — would
      need far more same-night samples to test properly. See known_issues.md
      2026-07-10 for full writeup. deep_sleep% extraction remains blocked, but by
      data scarcity, not a decode bug.
      CAPTURE SPARSITY QUANTIFIED (2026-07-11): 5 of 14 clean sleep-window pulls
      (36%) have zero 0x61/0x09 records despite confirmed 0x6A sleep data present —
      not occasional bad luck, a frequent recurring gap. Directly explains why the
      Gen4 correlation sample (n=5 nights) grows slowly: roughly a third of
      sleep-window pulls contribute nothing to it regardless of pull timing/quality.
      See known_issues.md 2026-07-11.
      Behaviorally-derived labels wired into pull script output (2026-07-07):
      pfsm=6→SLEEP_REGIME, pfsm=3/4→ACTIVE_REGIME, pfsm=5→TRANSITIONAL,
      pfsm=128→ECHO_RECORD. NOT firmware-confirmed.
      OFFSET-3 CROSS-REFERENCE (2026-07-10): tested against 0x6A sleep_state
      timeline (independent of the existing echo-pair validation). All 16
      pfsm=6 records corpus-wide have a 0x6A record within ~45s — sharpens
      the co-occurrence finding to an actual distance measurement. Onset-
      consistency sub-test inconclusive (12/16), not a falsification — see
      known_issues.md for why. f2/f4 remain the real ceiling; not attempted
      this session. deep_sleep% extraction still blocked.
- [~] 0x7E/0x7F real_steps_features — PARTIAL (promoted 2026-07-09 from IN PROGRESS).
      Decoders written: `pipeline/decoders/0x7e.py`, `pipeline/decoders/0x7f.py`
      (one file per tag per the decoders/ naming convention). Both return all 14 raw
      bytes; only 7E b[9] and 7F b[10] have any confirmed interpretation (walk vs.
      other-activity, NOT pace-sensitive — see NOT CONFIRMED note in each docstring).
      Wired into the pull script with a new decode/print section. Structure confirmed
      (14-byte payload, timer-driven pairing), most individual byte meanings still
      UNRESOLVED — this is a PARTIAL decoder, not DONE. First ground-truth decode 2026-07-07.
      64 prior pairs from 3 activity pulls + 7 new pairs from controlled walk experiment.
      Raw pull lost to buffer roll — payloads recovered from terminal output and preserved in
      `pipeline/data/raw_pulls/gen3_evening/walk_experiment_20260707_decoded.txt`.
      Ground truth: ~500 net steps. Phone BT OFF (revised protocol from 2026-06-28 failure).

      PRIOR FINDINGS (still valid):
      Invalid pairs (7F[3]=7F[4]=7F[7]=0) caused by Feature session restart — NOT decode error.
      7F[3] highest-variance field (stdev 61.4, range 7–230), primary step output candidate.
      7E[4] ↔ 7F[6] r=+0.374 cross-tag. 7F[11] ↔ 7F[12] r=−0.568 (anti-correlated).

      WALK EXPERIMENT FINDINGS (2026-07-07):
      Boot_ts spacing: 296, 326, 302, 301, 321, 301 ticks — mean 307.8, stdev ~11 (3.6%).
      Packets fire at near-constant ~308-tick cadence — timer-driven, NOT step-triggered.
      b[9] of 7E consistently dominant (range 151-235, mean 193.3) across all 7 packets.
      Pair 4 anomalous: b[1]=b[2]=b[5]=0 — possible brief pause or missed cadence window.
      STEP COUNT GATE: No single byte column sums to ~500. Nearest: 7E b[2]=485, 7E b[4]=482
      — both fail gate (zero in pair 4, not robust). These are FFT spectral features, not
      direct step counters. open_ring confirms: "FFTset sub-messages, meaning not documented."
      CEILING: byte-level field names need firmware RE or proto source (FFTset message schema).
      b[9] dominance and b[2]/b[4] near-500 clusters are hypotheses only — not confirmed.

      CROSS-FILE ANALYSIS (2026-07-07, 8 pull files, 92 total 7E packets):
      7E b[9] WALK-RESPONSIVE: mean=193.3 (walk, stdev=31) vs mean=60-125 (other activity).
      Walk is 1.5-3x higher, suggesting b[9] encodes cadence-band spectral peak.
      7F b[10] HIGH in general activity (mean 188-206, stdev 3-15) and LOWER in walk (128, stdev 5).
      7E b[0] ↔ 7E b[8] track within <10 units across ALL files — likely same signal or redundant.
      Analysis tool: `pipeline/tools/analyze_fft_walk.py` — compare files byte-by-byte.
      Fixed 2026-07-09: only matched the live pull script's exact label ("Real step
      feature (1)/(2)"), silently failing on `walk_experiment_20260707_decoded.txt`'s
      `[0x7E]`/`[0x7F]` shorthand too — now matches both formats.

      SECOND WALK ATTEMPT (2026-07-09, slow pace ~60-70 spm) — CAPTURE FAILURE, no
      comparison possible. Pull captured zero 0x7E/0x7F and zero 0x6B packets — not a
      tool issue, the pull itself has none (verified: 13 unique event labels in the
      file, none step/motion-period related; auto-classifier tagged it SLEEP WINDOW,
      the ~9-min buffer window read was sleep-context signal, not the walk that had
      just happened). Same buffer/timing constraint documented during the 0x5D HRV
      investigation (sleep buffer window ~7-12 min) — the walk's activity window
      appears to have aged out of the ring's buffer before the pull connected.
      Pace-sensitivity of b[9] remains UNTESTED — need a walk attempt that actually
      captures step features to compare against. See known_issues.md 2026-07-09.
(0x6E promoted to DONE — see above. 0x80 moved to DONE — see above.)
- [ ] 0x77 spo2_dc_event — PARTIAL DECODE, decoder written and validated 2026-07-06.
      384/384 corpus packets decode without error. 357 real, 27 sentinel (aaaab2 tail).
      b[0] = channel byte (bit7=A/B, bit6..0=beat_counter). Channel balance A=178/B=179.
      b[1..n-1] = signed i8 DC samples (Hyp A — conservative; all remaining bytes).
      Dominant 14-byte form → 13 samples. DC range −128 to +127 (full range used),
      mean −3.70, stdev 43.84. Time-series structure confirmed: lag-1 r=+0.49.
      Cross-channel A/B correlation for matched pairs: r=+0.80 to +0.93 (real signal).
      Decoder: `pipeline/decoders/0x77.py`. Wired into pull script.
      CEILING: whether b1..b3 are a header (beat_index + u16 ts) leaving b4..= as samples,
      or all b1..= are DC samples — indistinguishable from corpus. Band identity (red/IR),
      i8 encoding (raw/gain/delta), DC reference units — all need firmware disassembly.
      NOT promoted to DONE — ceiling maintained per working rules.

**WALK EXPERIMENT COMPLETED 2026-07-07 (revised protocol — phone BT OFF).**
Protocol: `pipeline/tools/WALK_EXPERIMENT.md`. Results logged above.
- 0x7E/0x7F: 7 pairs decoded. PARTIAL (2026-07-09) — decoders written, byte fields mostly still not named. FFT spectral features confirmed.
- 0x6B: b[0] step count CONFIRMED. Remaining fields (b[1]-b[3]) still hypotheses.
- 0x6E IBI: DONE — promoted prior session.
- 0x77: PARTIAL — unchanged.
Raw pull file lost (buffer roll before save). Payloads preserved in decoded file.
NEXT ACTION for 0x7E/0x7F: firmware RE or proto source to identify FFTset sub-message fields.
A working third walk experiment (fixing the buffer/timing capture failure — see
known_issues.md 2026-07-09) would also let pace-sensitivity of b[9]/b[10] finally be tested.

## NOT STARTED — Tier 1, high biometric value (1)
- [ ] 0x76 bedtime_period — wired into script, never caught a real packet. Re-verified
      2026-07-08: zero matches across all 23 raw pull files on disk (literal "0x76",
      "Bedtime period" label, case-insensitive "bedtime" all checked). See known_issues.md.

(0x7E/0x7F moved to PARTIAL 2026-07-09 — see IN PROGRESS section. Count corrected;
was previously listed here despite having active RE work, a pre-existing inconsistency.)

## NOT STARTED — Tier 2, weaker/auto-extracted confidence (12)
- [ ] 0x49 sleep_summary_1 — Gen3 does NOT emit (0 packets across all 27 pulls)
- [ ] 0x4C sleep_summary_2 — Gen3 does NOT emit (0 packets)
- [ ] 0x4F sleep_summary_3 — Gen3 does NOT emit (0 packets)
- [ ] 0x4A ppg_amplitude_ind — 243 packets. Format 5×u16 LE (NOT just first u16
      as open_ring claims). ANALYSIS COMPLETE (2026-06-29):
      f0: r=−0.561 with SpO2; saturates at 65535 when SpO2=88%; f0=0 universally
      in activity (red/IR LED off). Interpretation: optical AGC / LED drive level
      — ring increases LED power when desaturation detected.
      f1-f4: sleep-only (all-zero in activity), range 0–30, r=0.89-0.99
      inter-field (one signal×4), r=+0.41-0.51 with motion_count. Best hypothesis:
      4-channel motion-artifact rejection counts within SpO2 measurement window.
      CEILING: f1-f4 semantic (artifact vs valid-sample count) needs firmware;
      f0 gain/drive interpretation needs optical register access.
- [ ] 0x50 activity_info_event — PARTIAL DECODE (2026-06-30). 13 packets.
      b[0] = activity class enum ∈ {0,21,23,60,97,198}. b[0]=0 → sedentary/rest
      (surrounds SPO2, Sleep ACM, Temp events); non-zero → active (always followed
      by Motion event at t+1). Values scale with intensity: 21/23=light, 60=moderate,
      97=vigorous, 198=intense. Trailing bytes (loop-read by firmware — auto-extractor
      missed them): 13-sample per-epoch intensity array for 14-byte packets. Values
      9–16 in rest/light context, up to 91 in intense context. MET×8 encoding plausible
      (9/8=1.1 MET rest, 91/8=11.4 MET vigorous). Short packets (3, 7, 10 bytes) are
      rare variants; structure differs from 14-byte form.
      CEILING: exact activity class enum labels (only 6 values observed); MET×8 unconfirmed
      without simultaneous Gen4 Average MET cross-validation.
- [ ] 0x5B ble_connection_ind — PARTIAL DECODE (2026-06-30). 50 packets across
      pulls. Open_ring decoder reads isolated u8s at offsets 0,1,6,7,8,9 — wrong.
      Actual structure: byte[0] = subtype ∈ {2,3,4,5}; each subtype is a distinct
      fixed-size record. Subtypes 2/4/5 always fire as a consecutive trio (1 tick
      apart) on every BLE connection event; subtype 3 logs the peer MAC separately.
      Sub=3: bytes[1]=addr_type (2=random-resolvable, 0=public), bytes[2:8]=6-byte
      BLE MAC address. 7 unique MACs across all pulls (phone rotates random address).
      Sub=4: u16_le(p[1:3])=u16_le(p[3:5]) always (min=max=fixed interval).
      207×1.25ms=258.75ms (sleep/low-power mode); 27×1.25ms=33.75ms (active/app-open
      mode). BLE spec confirmed — no firmware needed for these two fields.
      Sub=2: b[7]∈{14,16,24,30} = negotiated connection interval (×1.25ms);
      b[10]=8–180 = likely RSSI or packet error metric; b[2]∈{0,1,2,3} = reconnect
      count within session.
      Sub=5: 4×u16_le at offsets 1,5,7,9 — ranges 0–923 — likely TX/RX packet
      counts or error counters; exact labels need firmware.
- [ ] 0x5E selftest_event — 0 packets. Gen3 may not emit or very rare.
- [ ] 0x6C feature_session — PARTIAL DECODE extended (2026-06-30). b0 session classes:
      0x02=GREEN_IBI, 0x03=unknown, 0x04=unknown, 0x08=EHR_INHIBIT,
      0x0b=EHR/DHR_BOUNDARY, 0x0d=CVA. b1 direction now fully mapped via ASCII context:
      b1=1=START (all types; preceded by DHR_state:4, followed by DHR_state:2)
      b1=2=PAUSE/TRANSITION (GREEN_IBI only; EHR session interrupting GREEN_IBI)
      b1=3=STOP (all types; followed by AFs aggregate or CVA_state:0)
      b1=9=EHR_BOUNDARY PRE-ANNOUNCE (fires before EHRst;1;0;1 — EHR about to start)
      b1=10=EHR_BOUNDARY CONFIRMED (fires after EHRst;1;0;1 — EHR now active)
      b0=8 confirmed: always co-occurs with pp_rt_start + EHR_INH;9 + CVA_state:1 →
      EHR_INHIBIT session (EHR suppressed to give CVA exclusive optical access).
      b2: 4=COMPLETED(activity), 1=ONGOING(CVA), 0=UNSPECIFIED(boundary).
      CEILING: b0=3 and b0=4 session classes unidentified (single occurrence each);
      b1=9 vs b1=10 distinction (pre-announce vs confirmed) needs more EHR start events.
- [ ] 0x6D MEAs quality event — 23 packets. NOT ON ORIGINAL ROADMAP. No open_ring
      decoder (raw hex fallback). Format CONFIRMED (2026-06-29): byte[0]=0x00 +
      4×i24 LE, all values negative (-2 to -216). ACTIVITY-ONLY (no sleep pulls
      contain this tag). Fires every 121 ticks (~1.57s) fixed cadence. Inter-field
      r=0.44–0.66 (4 distinct correlated channels, NOT identical×4). Zero
      correlation with motion magnitude — FALSIFIED motion-quality hypothesis.
      Best hypothesis: 4-channel optical noise floor / per-channel SNR residuals
      from PPG system (green×2, red, IR). Ceiling: needs firmware disassembly or
      simultaneous 0x77/0x6E in same activity pull to progress.
- [ ] 0x72 sleep_acm_period — PARTIAL DECODE (2026-06-30). 215 packets across
      27/29 pulls (all window types). Format: 6×u16 LE (open_ring reads u8 at
      offsets 6–11, incorrect). Invariants hold at 0 violations across 215 pkts:
      f4>=f3, f1=max(f0,f1,f2).
      {f0,f1,f2} = per-axis ACM energy. f1=gravity axis (dominant lying down;
      quiet medians 12/22/13; heavy motion peaks 6767/11602/8780). All 3 corr
      r=0.96-0.97 with each other, r=0.76-0.92 cross-group.
      {f3,f4,f5} = motion summary. f3=period floor (min=24, quiet median=29);
      f4=period peak (always >=f3, quiet median=34, active median=193); f5=sparse
      overflow (r=+0.963 with f3; 88% of values <=10).
      Sleep_state split: state=0 has ~2x higher all-field medians vs state=1,
      confirming 0x72 tracks real motion differences between sleep states even
      with the sleep_state enum gap.
      CEILING: which physical axis maps to f0/f1/f2, exact ACM formula (RMS?
      variance?), and f5 overflow semantics need firmware disassembly.
- [ ] 0x73 ehr_trace_event — PARTIAL DECODE (2026-06-30). 48 packets, 1 activity pull.
      Firmware name confirmed: DHR (Dynamic Heart Rate), not EHR (debug event
      DHR_state:1 at ts=39153941). Activity-only; zero packets in any sleep pull.
      Structure: 4-packet bursts at ~122-tick (1.58s) intervals:
      14b(ch0)+5b(ch0)+14b(ch1)+5b(ch1). b[0]=sequence counter; b[1]=channel(0/1).
      14-byte: 5xU16_LE optical samples; f2 notably lower (mean 2681/8810) vs f0/f1/f3/f4
      (mean 16k-39k) -- likely DC offset/noise, not a 5th optical sample.
      5-byte: u16_LE aggregate (ch0 mean 33724, ch1 mean 23816) + b[4]=quality/count
      (ch0: 4-7 tight; ch1: 4-43 wide mean 25 -- ch1 may be primary beat-detection channel).
      Cross-channel u16 r=-0.094 (independent signals). open_ring decoder reads flat u8
      samples -- misses pair structure, channel field, u16 encoding entirely.
      CEILING: channel-wavelength mapping (red/IR/green); f2 physical meaning; b[4]
      semantics; no HR cross-validation (0x6A absent in DHR window).
- [x] 0x80 green_ibi_quality_event — DONE 2026-06-28. See DONE section above.
- [ ] 0x82/0x83 scan_start / scan_end — 0 packets. Gen3 does not emit.

## NOT STARTED — unidentified/low-confidence (2)
- [ ] 0x56 unknown_56 — NOT OBSERVED (2026-06-30). Zero packets across 34 pulls.
      open_ring has internal contradiction: decoder calls it "confirmed real wire tag"
      (4 occurrences, 4 captures); parser lists it as example of mid-stream misparsed
      byte that "never appears at start of real notification." Not actionable.
- [ ] 0x85 unknown_85 — NOT OBSERVED (2026-06-30). Zero packets across 34 pulls.
      open_ring: 16 samples May 2-6 2026, format confirmed: unix_s:u32 + 4×0x00 +
      trailer:u16 (502/504 alternating). Low-cadence or condition-specific; not
      actionable without catching it in a future pull.

## NOT STARTED — Tier 3, debug/diagnostic sub-types under 0x61 (19 confirmed zero-data + 2 PARTIAL)
All dispatched via sub-byte at payload offset 0, tag 0x61 itself.

SWEPT 2026-07-11: surveyed all sub-bytes against the full 29-file corpus
before attempting any decode. 0x04/0x0A/0x0C/0x0D/0x24/0x29 had real data,
decoded, and moved to DONE above. 0x28/0x33 had real data and are PARTIAL
(below). 0x15 had real but too-sparse data (n=4), decoded raw only, stays
here. The remaining 19 are CONFIRMED zero packets across all 29 files, not
just unattempted — see known_issues.md 2026-07-11 for the full survey.

- [~] 0x61/0x28 _dd_afe_statistics_values — PARTIAL, n=114 (largest sample
      in the sweep). 104/114 records have non-zero stats bytes — richer
      than open_ring's own reference capture. Real data exists to push
      further than open_ring did; not attempted this pass. Good next
      candidate. Decoder: `pipeline/decoders/0x61_28.py`.
- [~] 0x61/0x33 _dd_open_afe_ppg_settings_data — PARTIAL, n=68. **Confirms
      the Gen3 ring's PPG sensor chip is a MAX86171** (chip_variant=1 in
      all 68 samples) — real hardware ID, not inferred. Settings bytes
      beyond that are vendor register dumps, needs the MAX86171 datasheet
      to decode further. Decoder: `pipeline/decoders/0x61_33.py`.
- [ ] 0x61/0x15 _dd_finger_detection — checked 2026-07-11, n=4 (confirmed
      real, too few to hypothesis-test). Raw u64, no bitfield guess
      attempted. Decoder: `pipeline/decoders/0x61_15.py`.
- [ ] 0x61/0x0F _dd_security_failure — CONFIRMED zero packets (2026-07-11 sweep).
- [ ] 0x61/0x1A _dd_event_sync_statistics — CONFIRMED zero packets.
- [ ] 0x61/0x1B _dd_bootloader_debug_log — CONFIRMED zero packets.
- [ ] 0x61/0x1E _dd_fuel_gauge_register_dump — CONFIRMED zero packets.
- [ ] 0x61/0x1F _dd_ring_hw_information — CONFIRMED zero packets.
- [ ] 0x61/0x20 _dd_charging_ended_statistics — CONFIRMED zero packets (would
      need a real charging/dock session capture, none in current corpus).
- [ ] 0x61/0x21 _dd_fuel_gauge_logging_registers — CONFIRMED zero packets.
- [ ] 0x61/0x23 _dd_event_sync_cache_statistics — CONFIRMED zero packets.
- [ ] 0x61/0x25 _dd_hardware_test_start_values — CONFIRMED zero packets.
- [ ] 0x61/0x26 _dd_hardware_test_result_values — CONFIRMED zero packets.
- [ ] 0x61/0x27 _dd_charging_ended_statistics_continued — CONFIRMED zero packets.
- [ ] 0x61/0x2A _dd_field_test_information — CONFIRMED zero packets.
- [ ] 0x61/0x2B _dd_stack_usage_statistics — CONFIRMED zero packets (debug-only,
      genuinely zero biometric value regardless).
- [ ] 0x61/0x30 _dd_alt_periodic_counter — CONFIRMED zero packets.
- [ ] 0x61/0x35 _dd_ppg_signal_quality_stats — CONFIRMED zero packets. Would be
      genuinely valuable (SNR/signal quality, tells us how trustworthy other
      readings are) if it ever fires — worth re-checking as the corpus grows.
- [ ] 0x61/0x36 _dd_charger_information — CONFIRMED zero packets (needs a dock session).
- [ ] 0x61/0x3B _dd_alt_afe_period_tick — CONFIRMED zero packets.
- [ ] 0x61/0x3C _dd_alt_ppg_cont — CONFIRMED zero packets.
- [ ] 0x61/0x3D _dd_charger_debug_information — CONFIRMED zero packets (needs a dock session).
- [ ] 0x61/0x3F _dd_daily_drop_sample — CONFIRMED zero packets.

## Count check
16 done + 3 in progress + 2 Tier-3 PARTIAL + 1 not-started-T1 + ~12 Tier-2 + 2 unidentified
+ 19 Tier-3 confirmed-zero + 1 Tier-3 checked-too-sparse = **~56 decoder entries tracked**
(Updated 2026-07-11: Tier 3 backlog swept — 9 sub-types had real data (6 promoted to
DONE: 0x61/0x04/0x0A/0x0C/0x0D/0x24/0x29; 2 PARTIAL: 0x61/0x28/0x33; 1 checked-too-sparse:
0x61/0x15). 19 Tier-3 sub-types confirmed zero packets across the full corpus, not just
unattempted. See known_issues.md 2026-07-11. Count is approximate due to bundles.)

## Suggested next-session order (updated 2026-07-06)

**BLOCKED until controlled walk:**
Protocol: `pipeline/tools/WALK_EXPERIMENT.md` — 500 steps, phone BT OFF, pull immediately.
- 0x7E/0x7F: zero packets in corpus — need the walk
- 0x6E / 0x77: existing sleep packets ceiling-blocked — need activity variance from the walk
- 0x6B: only 4 packets observed — needs more activity context
- 0x61/0x09: Oura app sleep-stage cross-reference for same night (structural confirmed, physical meaning blocked)

**IMMEDIATELY actionable from existing 27 pulls:**

1. ~~**0x72 sleep_acm_period**~~ — PARTIAL DECODE logged 2026-06-30. See IN PROGRESS section.

2. ~~**0x80 green_ibi_quality_event**~~ — DONE 2026-06-30. See DONE section.

3. **0x6B motion_period** — collect more packets by capturing pull during
   deliberate motion (sit→walk→sit transitions). Only 4 packets currently.

4. **0x76 bedtime_period** — has never fired. Re-verified 2026-07-08 against all 23
   raw pull files on disk — still zero packets. Decoder pipeline is fully wired
   (PRIORITY_TAGS includes 0x76, pull script has a dedicated decode/print section,
   `pipeline/decoders/0x76.py` already implements open_ring's exact layout) — this
   is a data-capture gap, not a tooling gap. No confirmed mechanism for the absence;
   open_ring itself notes 0x68 (`API_RAW_PPG_DATA`) as "declared but not observed in
   any capture" in their own reference data, so genuinely rare/conditional emission
   is an established pattern in this tag space, not unique to our setup. Not
   actionable without catching it in a future pull — no known trigger to force it.
   Re-confirmed again same day: a claimed "3 decoded packets" (cross-validation
   promotion gate) traced to unsaved claude.ai session output with no hex payloads
   or file reference — could not be located anywhere in the repo after an
   exhaustive re-check (strict `[Bedtime period]` label match, pull/error logs,
   decoder inventory). Per real-data-only discipline, not counted as a finding.
   0x76 stays NOT PROMOTED — see `known_issues.md` addendum, 2026-07-08.

## Gen4 Ground Truth Reference (added 2026-06-30)

**File:** `data/reference/gen4_official_trends_2025-06-14_2026-06-07.csv`
**Full baseline doc:** `data/findings/gen4_baselines.md`
**Coverage:** 359 nights, 2025-06-14 → 2026-06-07 (no gaps)

Personal reference bands for decoder validation — use these to sanity-check any decoded value:

| Signal | Typical range (p25–p75) | Clear outlier threshold |
|---|---|---|
| Average RHR | 59–67 bpm | <52 or >75 bpm |
| Lowest RHR | 52–57 bpm | <47 or >63 bpm |
| HRV (RMSSD) | 24–35 ms | <15 ms (suppressed) / >45 ms (peak) |
| Respiratory rate | 12.75–13.38 br/min | <12 or >14.5 br/min |
| Skin temp deviation | −0.21 to +0.29°C | >+0.6°C likely illness |
| Total sleep | 7.1–8.5 h | <5.9 h or >9.6 h |
| Deep sleep | 61–88 min | <45 min or >107 min |
| REM sleep | 93–130 min | <68 min or >153 min |
| Sleep efficiency | 84.5–90% | <75% |

**Gap warning:** Export ends 2026-06-07. All Gen3 pulls from 2026-06-28 onward fall
outside this window. Export a fresh Gen4 CSV (2026-06-08+) to enable same-night
cross-validation for the current pull set.

**Highest-priority retrospective target:** 2025-12-20 (HRV=10ms, temp+2.59°C, readiness=29
— absolute extremes across 359 nights). If Gen3 boot_ts can be aligned to that date's
flash window, it is the single best test of whether physiological decoders track illness.

## How to use this doc
Check a box, move an item between sections, or add a note inline as
hypotheses get tested. This is the single source of truth for "have we
tried this tag yet" across the entire 38-entry surface — check here before
re-investigating anything.

---

## Infrastructure: decoder extraction — COMPLETE (2026-07-01)

All 9 inline `decode_*` functions extracted from `pipeline/tools/oura_gen3_morning_pull.py`
into individual files in `pipeline/decoders/`:

| File | Decoder | Status |
|---|---|---|
| `pipeline/decoders/0x6a.py` | sleep_period_info_2 | VALIDATED |
| `pipeline/decoders/0x5d.py` | hrv_event | VALIDATED |
| `pipeline/decoders/0x61_09.py` | debug_data_sleep_statistics | PARTIAL |
| `pipeline/decoders/0x61_14.py` | debug_data_fuel_gauge | VALIDATED |
| `pipeline/decoders/0x61_24.py` | debug_data_battery_level | VALIDATED |
| `pipeline/decoders/0x6f.py` | spo2_event | VALIDATED |
| `pipeline/decoders/0x75.py` | sleep_temp_event | VALIDATED |
| `pipeline/decoders/0x47.py` | motion_event | VALIDATED |
| `pipeline/decoders/0x76.py` | bedtime_period | NEVER OBSERVED (re-verified 2026-07-08) |
| `pipeline/decoders/0x6e.py` | spo2_ibi_and_amplitude | VALIDATED |
| `pipeline/decoders/0x77.py` | spo2_dc_event | PARTIAL DECODE |
| `pipeline/decoders/0x7e.py` | real_step_feature_1 | PARTIAL (2026-07-09) — only b[9] confirmed |
| `pipeline/decoders/0x7f.py` | real_step_feature_2 | PARTIAL (2026-07-09) — only b[10] confirmed |

Shared helpers (`_i8`, `_u32`) moved to `pipeline/decoders/utils.py`. Pull script now
imports from `pipeline.decoders`. Output verified byte-for-byte identical against known
good pull values (0x6A avg_hr=54.5, 0x6F spo2=[93,93,93], 0x75 temps confirmed).

`pipeline/decoders/` is now the canonical source of truth for all decoder logic.

*Logged 2026-07-01.*
