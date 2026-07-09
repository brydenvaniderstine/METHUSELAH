# Source Selector Test — How to verify Gen3/Gen4 switching

Manual verification steps for `engine/sources.js`'s interchangeable-input
architecture on the live site. Automated verification (direct `node` checks
against `engine/`, plus a local dev-server pass with the accessibility
snapshot/screenshot tools) was already run during the build session — see
`SESSION_HANDOFF.md`. This doc is for confirming the same behavior on
methuselah.ca after deploy, where that tooling isn't available.

## Test A — Gen4 unavailable → Gen3 takes over for RHR

1. Open methuselah.ca in browser.
2. Open dev tools → Console.
3. Paste: `localStorage.removeItem("oura_token"); location.reload();`
4. Enter the master key, skip the Oura setup prompt if it appears.
5. Confirm: CARDIAC LOAD tile shows `65.1` (or whatever the latest Gen3 pull
   reads) with `● GEN3 BLE` in cyan, instead of `● OURA LIVE`.
6. Confirm: the sys-log's `GEN3 INTERCEPT` line still shows `SPO2 XX.X%` —
   this is a direct read of the bridge JSON, not gated by the source
   selector, so it should always be present whenever `gen3_latest.json` is
   fresh, token or no token.
7. Confirm: HRV tile shows `AWAITING DATA` — no Gen3 fallback exists yet
   (0x5D overnight decoder incomplete).
8. Confirm: REPAIR DEPTH tile shows `AWAITING DATA` — no Gen3 fallback yet
   (0x6A has no sleep-stage breakdown).
9. Confirm: if CARDIAC LOAD is above 63 bpm, the command panel fires
   "INITIATE ACTIVE RECOVERY PROTOCOL" off the Gen3-sourced value — proves
   the command engine, not just the tile label, is reading the resolved
   vector.
10. Restore: paste your Oura token back via
    `localStorage.setItem("oura_token", "YOUR_TOKEN"); location.reload();`

## Test B — no sources at all → AWAITING TELEMETRY, not BIOLOGY OPTIMAL

`engine/index.js`'s `evaluate()` distinguishes "every vector is null" from
"every vector is null-or-in-range" — only the former should show
`AWAITING TELEMETRY.` in the command panel. `BIOLOGY OPTIMAL.` means data
was checked and is fine; it should never appear when there was no data to
check.

1. With no Oura token saved (per Test A) and the Gen3 bridge fetch blocked
   or the ring never having pulled (`gen3_latest.json` 404s or is stale
   >24h), reload the app.
2. Confirm: all four tiles show `AWAITING DATA` / `AWAITING INTERCEPT`.
3. Confirm: the command panel shows `AWAITING TELEMETRY.` — not
   `BIOLOGY OPTIMAL.` and not an `EXECUTE PROTOCOL` button (there's nothing
   to execute against).
4. This is hard to trigger organically on a device with a working Gen3
   bridge — easiest local repro is devtools → Application → Local Storage →
   remove `oura_token`, then Network tab → block request to
   `/gen3_latest.json`, then reload.

## Expected state after July 13th (Oura API token lapses)

| Tile | Source | Notes |
|---|---|---|
| CARDIAC LOAD | GEN3 BLE | `0x6A rhr_bpm`, auto-switches once Gen4 goes stale >24h |
| GLYCEMIC LOAD | Manual entry | unchanged — no wearable source on either generation |
| HRV // SYSTEMIC FRICTION | AWAITING DATA | until the 0x5D overnight decoder is validated |
| REPAIR DEPTH | AWAITING DATA | until the 0x6A sleep-stage decoder is validated |
| (sys-log only) SpO2 | GEN3 BLE | `0x6F spo2_avg_pct` — resolved in `engine/sources.js` as telemetry, not a UI tile; Track B condition #3 closed 2026-07-08 |

If ALL FOUR tiles are simultaneously `AWAITING DATA` (e.g. Gen3 bridge also
stale/missing), the command panel should read `AWAITING TELEMETRY.` per
Test B — this is the expected degraded state, not a bug.
