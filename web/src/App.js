import React, { useState, useEffect, useRef } from "react";
import { evaluateSources, calculateBRI, THRESHOLDS, SOURCE_GEN4, SOURCE_GEN3 } from "./engine/index.js";

const CSS = `
@import url('https://fonts.googleapis.com/css2?family=Space+Mono:ital,wght@0,400;0,700;1,400;1,700&display=swap');

*, *::before, *::after { box-sizing: border-box; margin: 0; padding: 0; }

:root {
  --bg: #050505;
  --panel: #0a0a0a;
  --line: #1e1e1e;
  --line-bright: #333333;
  --text-main: #f0f0f0;
  --text-dim: #555555;
  --text-mid: #888888;
  --accent-red: #ff2a2a;
  --accent-green: #00ff66;
  --accent-amber: #ffb300;
  --accent-blue: #00aaff;
  --font-mono: 'Space Mono', 'Courier New', Courier, ui-monospace, SFMono-Regular, monospace;
}

html, body, #root {
  padding-top: env(safe-area-inset-top);
  padding-bottom: env(safe-area-inset-bottom);
  height: 100vh; width: 100%;
  background: var(--bg); color: var(--text-main);
  font-family: var(--font-mono); font-size: 11px;
  text-transform: uppercase; overflow: hidden;
}

body::after {
  content: ''; position: fixed; inset: 0;
  background: repeating-linear-gradient(0deg, transparent, transparent 2px, rgba(0,0,0,0.08) 2px, rgba(0,0,0,0.08) 4px);
  pointer-events: none; z-index: 9999;
}

body::before {
  content: ''; position: fixed; inset: 0;
  background: linear-gradient(rgba(51,51,51,0.12) 1px, transparent 1px), linear-gradient(90deg, rgba(51,51,51,0.12) 1px, transparent 1px);
  background-size: 24px 24px; pointer-events: none; z-index: 0;
}

.shell {
  display: flex;
  flex-direction: column;
  height: 100vh;
  width: 100%;
  max-width: 100%;
  margin: 0 auto;
  padding: 12px;
  position: relative;
  z-index: 1;
  gap: 16px;
  box-sizing: border-box;
  overflow: hidden;
}

.header {
  display: flex; justify-content: space-between; align-items: flex-start;
  border-bottom: 2px solid var(--text-main); padding-bottom: 10px; overflow: hidden;
}

.brand-wrap { display: flex; flex-direction: column; gap: 2px; }
.brand { font-size: 13px; font-weight: 700; letter-spacing: 2px; }

.header-right { display: flex; flex-direction: column; align-items: flex-end; gap: 6px; }
.header-top-row { display: flex; gap: 12px; align-items: center; }
.live-badge { display: flex; align-items: center; gap: 6px; font-size: 9px; letter-spacing: 2px; }
.blink { width: 7px; height: 7px; border-radius: 50%; animation: pulse 1.5s infinite; }
@keyframes pulse { 0%,100% { opacity: 1; box-shadow: 0 0 8px currentColor; } 50% { opacity: 0.15; box-shadow: none; } }
.clock { font-size: 9px; color: var(--text-dim); letter-spacing: 1px; }

.telemetry-grid {
  display: grid; grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 2px; background: var(--line); border: 1px solid var(--line-bright);
}
.tel-block { background: var(--panel); padding: 8px; position: relative; overflow: hidden; }
.tel-label { font-size: 8px; color: var(--text-dim); letter-spacing: 1px; margin-bottom: 6px; line-height: 1.3; }
.tel-value { font-size: 18px; font-weight: 700; line-height: 1; font-variant-numeric: tabular-nums; }
.tel-unit { font-size: 10px; color: var(--text-dim); }
.tel-bar-wrap { height: 2px; background: var(--line); margin: 8px 0; }
.tel-bar { height: 100%; transition: width 1s ease, background 0.5s; }
.tel-meta { font-size: 8px; color: var(--text-dim); letter-spacing: 0.2px; margin: 3px 0 2px; line-height: 1.4; }
.tel-source { font-size: 8px; color: var(--accent-blue); letter-spacing: 1px; margin-top: 2px; }
.tel-stale { opacity: 0.65; }
.tel-tap-hint { font-size: 8px; color: var(--text-dim); letter-spacing: 1px; margin-top: 4px; }

@keyframes glucosePulse {
  0%, 100% { border-color: #ffb300; }
  50% { border-color: #333333; }
}
.glucose-pulse {
  border: 1px solid #ffb300;
  animation: glucosePulse 1s ease-in-out infinite;
}

.glucose-entry { display: flex; flex-direction: column; gap: 6px; margin-top: 4px; }
.glucose-input {
  background: transparent; border: 1px solid var(--line-bright); color: var(--accent-green);
  font-family: var(--font-mono); font-size: 16px; font-weight: 700; padding: 4px 6px;
  width: 100%; outline: none; -moz-appearance: textfield;
}
.glucose-input:focus { border-color: var(--accent-green); }
.glucose-input::-webkit-outer-spin-button,
.glucose-input::-webkit-inner-spin-button { -webkit-appearance: none; margin: 0; }
.glucose-submit {
  background: var(--text-main); color: var(--bg); border: none;
  font-family: var(--font-mono); font-size: 9px; font-weight: 700;
  letter-spacing: 2px; padding: 5px; cursor: pointer; text-transform: uppercase;
}

.command-wrap {
  display: flex; flex-direction: column; justify-content: center; align-items: center;
  border: 2px solid var(--line-bright); padding: 14px 16px; text-align: center;
  background: var(--panel); position: relative; overflow: visible; transition: border-color 0.5s;
  flex-shrink: 0;
}
.corner { position: absolute; width: 14px; height: 14px; border: 1px solid var(--text-dim); }
.tl { top: 4px; left: 4px; border-right: 0; border-bottom: 0; }
.tr { top: 4px; right: 4px; border-left: 0; border-bottom: 0; }
.bl { bottom: 4px; left: 4px; border-right: 0; border-top: 0; }
.br { bottom: 4px; right: 4px; border-left: 0; border-top: 0; }

.cmd-meta { font-size: 9px; color: var(--text-dim); margin-bottom: 10px; letter-spacing: 2px; }
.cmd-text { font-size: 16px; font-weight: 700; margin-bottom: 10px; transition: color 0.5s; max-width: 100%; line-height: 1.3; }
.cmd-rationale { font-size: 10px; color: var(--text-mid); line-height: 1.6; max-width: 100%; margin-bottom: 18px; letter-spacing: 0.5px; }
.cmd-briefing { font-size: 11px; color: var(--text-dim); line-height: 1.7; max-width: 100%; margin-bottom: 14px; letter-spacing: 0.3px; border-left: 1px solid var(--text-dim); padding-left: 10px; }

.btn-execute {
  background: var(--text-main); color: var(--bg); border: none; padding: 12px 20px;
  font-family: var(--font-mono); font-size: 11px; font-weight: 700; letter-spacing: 3px;
  cursor: pointer; box-shadow: 4px 4px 0 var(--accent-amber);
  transition: transform 0.08s, box-shadow 0.08s;
}
.btn-execute:hover { transform: translate(2px,2px); box-shadow: 2px 2px 0 var(--accent-amber); }
.btn-execute:active { transform: translate(4px,4px); box-shadow: none; }
.btn-execute.done { background: var(--line-bright); color: var(--text-dim); box-shadow: none; cursor: not-allowed; transform: none; }

.optimal-label { color: var(--accent-green); font-weight: 700; letter-spacing: 3px; font-size: 11px; animation: breathe 3s infinite; }
@keyframes breathe { 0%,100% { opacity: 1; } 50% { opacity: 0.35; } }

.weekly-grid { width: 100%; display: flex; flex-direction: column; gap: 8px; margin: 10px 0 8px; }
.weekly-row { display: flex; align-items: baseline; gap: 10px; font-size: 9px; letter-spacing: 1px; }
.weekly-label { color: var(--text-dim); min-width: 90px; flex-shrink: 0; }
.weekly-val { color: var(--text-main); font-weight: 700; min-width: 80px; }
.weekly-trend { color: var(--text-dim); }
.weekly-caveat { color: var(--text-dim); font-size: 8px; opacity: 0.6; }

.sys-log {
  flex: 1;
  overflow-y: auto;
  border-top: 1px solid var(--line-bright);
  padding-top: 8px;
  display: flex;
  flex-direction: column-reverse;
  justify-content: flex-end;
  gap: 2px;
  min-height: 100px;
}
.log-line { font-size: 9px; color: var(--text-dim); display: flex; gap: 12px; animation: slideIn 0.25s ease; }
@keyframes slideIn { from { opacity: 0; transform: translateY(4px); } to { opacity: 1; transform: translateY(0); } }
@keyframes fadeIn { from { opacity: 0; transform: translateY(-3px); } to { opacity: 1; transform: translateY(0); } }
.log-time { color: var(--accent-amber); min-width: 80px; flex-shrink: 0; }
.log-roche { color: var(--accent-blue); }
.log-cursor { display: inline-block; width: 6px; height: 9px; background: var(--accent-amber); animation: blink-cursor 1s step-end infinite; margin-left: 2px; vertical-align: middle; }
@keyframes blink-cursor { 0%,100% { opacity: 1; } 50% { opacity: 0; } }

.telemetry-toggle {
  display: flex; justify-content: flex-end; align-items: center; gap: 8px;
  padding: 6px 4px; font-size: 9px; letter-spacing: 1px; color: var(--text-dim);
  cursor: pointer; user-select: none; flex-shrink: 0;
}
.telemetry-toggle:hover { color: var(--text-mid); }
.telemetry-toggle .dot {
  width: 6px; height: 6px; border-radius: 50%;
  background: var(--accent-blue); box-shadow: 0 0 4px var(--accent-blue);
}
.telemetry-panel {
  border: 1px solid var(--line-bright); background: var(--panel);
  margin-bottom: 6px; flex-shrink: 0;
}
.telemetry-inner { padding: 10px 14px; font-size: 9px; color: var(--text-mid); }
.telemetry-header { color: var(--text-main); letter-spacing: 1px; margin-bottom: 8px; }
.telemetry-divider { border-top: 1px solid var(--line-bright); margin: 8px 0; }
.telemetry-raw-grid { display: grid; grid-template-columns: 1fr 1fr; gap: 6px 24px; }
.telemetry-raw-grid .label { color: var(--text-dim); }
.telemetry-raw-grid .value { color: var(--accent-amber); }
.telemetry-stages { margin-top: 8px; color: var(--text-dim); letter-spacing: 0.3px; }

.auth-overlay {
  position: fixed; inset: 0; background: var(--bg); z-index: 10000;
  display: flex; flex-direction: column; justify-content: center; align-items: center; gap: 16px;
  font-family: 'Space Mono', 'Courier New', Courier, monospace;
  padding: env(safe-area-inset-top) 12px env(safe-area-inset-bottom); box-sizing: border-box; overflow: hidden;
}
.auth-title { font-size: 13px; color: var(--accent-amber); letter-spacing: 4px; font-weight: 700; }
.auth-input {
  background: transparent; border: 1px solid var(--line-bright); color: var(--accent-green);
  font-family: var(--font-mono); font-size: 14px; padding: 10px; text-align: center;
  letter-spacing: 4px; width: 80vw; max-width: 300px; outline: none; transition: border-color 0.2s;
}
.auth-input:focus { border-color: var(--accent-green); }
.auth-hint { font-size: 9px; color: var(--text-dim); letter-spacing: 2px; }
.auth-decrypt { font-family: var(--font-mono); font-size: 11px; letter-spacing: 3px; font-weight: 700; padding: 12px; background: var(--text-main); color: var(--bg); border: none; cursor: pointer; box-shadow: 3px 3px 0 var(--accent-amber); margin-top: 8px; text-transform: uppercase; width: 80vw; max-width: 300px; }
.auth-error { font-size: 9px; color: var(--accent-red); letter-spacing: 2px; animation: fadeIn 0.2s ease; }
`;

const MASTER_KEY = "v1";
const STALE_HRS = 12;

function formatAge(iso) {
  if (!iso) return null;
  const mins = Math.round((Date.now() - new Date(iso).getTime()) / 60000);
  if (mins < 60) return `${mins}min old`;
  const hrs = Math.floor(mins / 60);
  if (hrs < 24) return `${hrs}h old`;
  return `${Math.floor(hrs / 24)}d old`;
}

function isStale(iso) {
  if (!iso) return false;
  return Date.now() - new Date(iso).getTime() > STALE_HRS * 3600000;
}

function getTrend(history) {
  if (!history || history.length < 2) return null;
  const cur = history[history.length - 1];
  const prev = history[history.length - 2];
  if (prev === 0) return null;
  const delta = (cur - prev) / Math.abs(prev);
  if (delta > 0.05) return "trending up";
  if (delta < -0.05) return "trending down";
  return "stable";
}

// Sanity ceiling for sleep-duration history entries -- no single day can
// plausibly exceed this many hours of sleep. Guards sleepDurationHistory
// (persisted in localStorage, never otherwise bounds-checked) against any
// bad value that ever reaches it, past or future -- e.g. the now-fixed
// 92.0-HRS production bug (see known_issues.md) could still be sitting in
// an existing browser's localStorage today, silently inflating the 7-day
// average and trend for anyone who had that bug reach their device before
// it was fixed. Applied both when loading existing history (self-heals
// old contamination) and when appending a new value (stops new bad values
// from ever being written).
const SLEEP_DURATION_PLAUSIBLE_MAX_H = 24;
const isPlausibleSleepHours = (h) => typeof h === "number" && h > 0 && h <= SLEEP_DURATION_PLAUSIBLE_MAX_H;

function avgOf(history) {
  if (!history || history.length === 0) return null;
  return history.reduce((a, b) => a + b, 0) / history.length;
}

function trendGlyph(history) {
  const t = getTrend(history);
  if (t === "trending up")   return "▲";
  if (t === "trending down") return "▼";
  if (t === "stable")        return "—";
  return null;
}

// Metric — 3-line tile: label / value + context / source + age
// meta: pre-formatted "(optimal X · 7d avg Y · trend)" string
// stale: dims tile + shifts source line to amber
function Metric({ label, val, unit, color, meta, age, stale, source }) {
  const sourceLabel = source === SOURCE_GEN4 ? "OURA LIVE" : source === SOURCE_GEN3 ? "GEN3 BLE" : null;
  const sourceColor = stale ? "var(--accent-amber)" : source === SOURCE_GEN3 ? "cyan" : "var(--accent-blue)";
  return (
    <div className={`tel-block${stale ? " tel-stale" : ""}`}>
      <div className="tel-label">{label}</div>
      <div className="tel-value" style={{ color }}>
        {val} <span className="tel-unit">{unit}</span>
      </div>
      {meta && <div className="tel-meta">({meta})</div>}
      {sourceLabel
        ? <div className="tel-source" style={{ color: sourceColor }}>● {sourceLabel} · {age || "?"}{stale ? "  [flag: stale]" : ""}</div>
        : <div className="tel-source" style={{ color: "var(--text-dim)" }}>AWAITING DATA</div>
      }
    </div>
  );
}

function GlucosePanel({ reading, entryOpen, inputVal, meta, age, stale, onTap, onBLERead, onInputChange, onKeyDown, onSubmit }) {
  const hasReading = reading !== null;
  const isElevated = hasReading && reading > THRESHOLDS.glucose;
  const color = !hasReading ? "var(--accent-amber)" : isElevated ? "var(--accent-red)" : "var(--accent-green)";
  const sourceColor = stale ? "var(--accent-amber)" : "var(--accent-blue)";

  return (
    <div
      className={`tel-block${!hasReading ? " glucose-pulse" : ""}${stale ? " tel-stale" : ""}`}
      onClick={!entryOpen ? onTap : undefined}
      style={{ cursor: entryOpen ? "default" : "pointer" }}
    >
      <div className="tel-label">GLYCEMIC LOAD</div>
      {entryOpen ? (
        <div className="glucose-entry">
          <input
            className="glucose-input"
            type="number"
            step="0.1"
            min="1"
            max="30"
            value={inputVal}
            onChange={onInputChange}
            onKeyDown={onKeyDown}
            autoFocus
            placeholder="0.0"
          />
          <button className="glucose-submit" onClick={e => { e.stopPropagation(); onSubmit(); }}>
            LOG
          </button>
        </div>
      ) : (
        <>
          <div className="tel-value" style={{ color }}>
            {hasReading ? reading.toFixed(1) : "--"} <span className="tel-unit">mmol/L</span>
          </div>
          {hasReading && meta && <div className="tel-meta">({meta})</div>}
          {hasReading && age
            ? <div className="tel-source" style={{ color: sourceColor }}>● MANUAL · {age}{stale ? "  [flag: stale]" : ""}</div>
            : !hasReading && (
              <>
                <div className="tel-tap-hint">TAP TO ENTER READING</div>
                <div onClick={onBLERead} style={{ fontSize: "8px", color: "var(--accent-blue)", letterSpacing: "1px", marginTop: "4px", cursor: "pointer" }}>● BLE AUTO-READ</div>
              </>
            )
          }
        </>
      )}
    </div>
  );
}

// Collapsible raw-telemetry breakdown -- same GEN3 INTERCEPT fields the
// sys-log line already carries, reformatted into a legible label/value
// grid instead of one long `//`-separated line. No new data, no new
// primary tile -- just surfacing already-decoded fields more readably.
function RawTelemetryPanel({ bridge, open, onToggle, stale }) {
  const v = bridge.vectors;
  const stages = v.sleep_stages;
  const time = new Date(bridge.timestamp).toLocaleTimeString([], { hour12: false, hour: "2-digit", minute: "2-digit", second: "2-digit" });
  const dotColor = stale ? "var(--accent-amber)" : "var(--accent-blue)";
  return (
    <>
      <div className="telemetry-toggle" onClick={onToggle}>
        <span className="dot" style={{ background: dotColor, boxShadow: `0 0 4px ${dotColor}` }} />
        <span>{open ? "▾" : "▸"} {open ? "HIDE" : "SHOW"} RAW TELEMETRY</span>
      </div>
      {open && (
        <div className={`telemetry-panel${stale ? " tel-stale" : ""}`}>
          <div className="telemetry-inner">
            <div className="telemetry-header">
              RAW TELEMETRY // GEN3 INTERCEPT · {bridge.classifier} · [{time}]
              {stale && <span style={{ color: "var(--accent-amber)" }}> [FLAG: STALE]</span>}
            </div>
            <div className="telemetry-divider" />
            <div className="telemetry-raw-grid">
              <div><span className="label">RHR ......... </span><span className="value">{v.rhr_bpm != null ? v.rhr_bpm.toFixed(1) + " BPM" : "N/A"}</span></div>
              <div><span className="label">BATTERY ..... </span><span className="value">{v.battery_pct != null ? v.battery_pct + "%" : "N/A"}</span></div>
              <div><span className="label">IBI_HR ...... </span><span className="value">{v.ibi_hr_bpm != null ? v.ibi_hr_bpm.toFixed(1) + " BPM" : "N/A"}</span></div>
              <div><span className="label">TEMP ........ </span><span className="value">{v.sleep_temp_c != null ? v.sleep_temp_c + "°C" : "N/A"}</span></div>
              <div><span className="label">SPO2 ........ </span><span className="value">{v.spo2_avg_pct != null ? v.spo2_avg_pct + "%" : "N/A"}</span></div>
              <div><span className="label">STEPS ....... </span><span className="value">{v.step_count != null ? v.step_count : "N/A"}</span></div>
            </div>
            {stages != null && (
              <>
                <div className="telemetry-divider" />
                <div className="telemetry-stages">
                  SLEEP STAGES: WAKE {stages.wake_min}M · LIGHT {stages.light_min}M · REM {stages.rem_min}M · DEEP {stages.deep_min}M
                </div>
                {v.sleep_duration_stage_sum_hrs != null ? (
                  <div className="telemetry-stages">
                    TST (STAGE SUM, PROVISIONAL): {v.sleep_duration_stage_sum_hrs.toFixed(2)}H
                    {v.sleep_duration_stage_sum_meta?.deep_anomaly ? " [DEEP ANOMALY LOGGED]" : ""}
                  </div>
                ) : (
                  <div className="telemetry-stages">
                    TST (STAGE SUM, PROVISIONAL): -- ({v.sleep_duration_stage_sum_meta?.reason || "n/a"})
                  </div>
                )}
              </>
            )}
          </div>
        </div>
      )}
    </>
  );
}

// calculateBRI moved to engine/index.js — imported above

export default function MethuselahFinal() {
  const ts = () => new Date().toLocaleTimeString([], { hour12: false, hour: "2-digit", minute: "2-digit", second: "2-digit" });

  const [locked,          setLocked]          = useState(true);
  const [input,           setInput]           = useState("");
  const [authError,       setAuthError]       = useState(false);
  const [clock,           setClock]           = useState(ts());
  const [glucoseReading,  setGlucoseReading]  = useState(null);
  const [glucoseTimestamp, setGlucoseTimestamp] = useState(() => localStorage.getItem("glucoseTimestamp") || null);
  const [hrvHist,   setHrvHist]   = useState(() => JSON.parse(localStorage.getItem("hrvHistory") || "[]"));
  const [rhrHist,   setRhrHist]   = useState(() => JSON.parse(localStorage.getItem("rhrHistory") || "[]"));
  const [sleepHist, setSleepHist] = useState(() =>
    JSON.parse(localStorage.getItem("sleepDurationHistory") || "[]").filter(isPlausibleSleepHours));
  const [glucHist,  setGlucHist]  = useState(() => JSON.parse(localStorage.getItem("glucoseHistory") || "[]"));
  const [spo2Hist,  setSpo2Hist]  = useState(() => JSON.parse(localStorage.getItem("spo2History") || "[]"));
  const [stepHist,  setStepHist]  = useState(() => JSON.parse(localStorage.getItem("stepHistory") || "[]"));
  const [glucoseEntryOpen, setGlucoseEntryOpen] = useState(false);
  const [glucoseInput,    setGlucoseInput]    = useState("");
  const [execState,       setExecState]       = useState("idle");
  const [briefingOpen,    setBriefingOpen]    = useState(false);
  const [rawTelemetryOpen, setRawTelemetryOpen] = useState(false);
  const [gen3Bridge,      setGen3Bridge]      = useState(null);
  const [logs,            setLogs]            = useState([{ time: ts(), msg: "BIOLOGICAL SYSTEMS ONLINE // STANDING BY", type: "" }]);
  const logRef = useRef(null);

  const addLog = (msg, type = "", color = null) => setLogs(prev => [{ time: ts(), msg, type, color }, ...prev].slice(0, 12));

  const unlock = () => {
    setLocked(false);
    setAuthError(false);
    const today = new Date().toLocaleDateString("en-CA");
    const protocolDate = localStorage.getItem("protocolExecutedDate");
    if (protocolDate === today) {
      setExecState("satisfied");
    }
    const storedDate    = localStorage.getItem("glucoseDate");
    const storedReading = localStorage.getItem("glucoseReading");
    if (storedDate === today && storedReading) {
      setGlucoseReading(parseFloat(storedReading));
    }
  };

  const readBLEGlucose = async () => {
    try {
      addLog("BLE INTERCEPT // SCANNING FOR METHUSELAH BRIDGE...", "event");
      const device = await navigator.bluetooth.requestDevice({
        filters: [{ name: "METHUSELAH" }],
        optionalServices: ["4fafc201-1fb5-459e-8fcc-c5c9c331914b"]
      });
      const server = await device.gatt.connect();
      const service = await server.getPrimaryService("4fafc201-1fb5-459e-8fcc-c5c9c331914b");
      const characteristic = await service.getCharacteristic("beb5483e-36e1-4688-b7f5-ea07361b26a8");
      const value = await characteristic.readValue();
      const rawBytes = new Uint8Array(value.buffer);
      const text = new TextDecoder().decode(value);
      addLog("BLE RAW BYTES: " + Array.from(rawBytes).join(","), "roche");
      addLog("BLE TEXT: " + text, "roche");
      const parts = text.split(",");
      const glucose = parseFloat(parts[0]);
      if (!isNaN(glucose) && glucose > 0.5 && glucose < 30) {
        setGlucoseReading(glucose);
        const today = new Date().toLocaleDateString("en-CA");
        const nowIso = new Date().toISOString();
        localStorage.setItem("glucoseReading", glucose.toString());
        localStorage.setItem("glucoseDate", today);
        localStorage.setItem("glucoseTimestamp", nowIso);
        setGlucoseTimestamp(nowIso);
        const newGlucHist = [...glucHist, glucose].slice(-7);
        setGlucHist(newGlucHist);
        localStorage.setItem("glucoseHistory", JSON.stringify(newGlucHist));
        pushGlucoseToServer(glucose, nowIso);
        setGlucoseEntryOpen(false);
        setGlucoseInput("");
        addLog("BLE INTERCEPT: " + glucose.toFixed(1) + " MMOL/L // AUTO-LOGGED", "roche");
        const bri = calculateBRI({ glucose, hrv, rhr, sleepDurationHrs, glucosePending: false });
        addLog("BIOLOGICAL READINESS INDEX: " + bri.score + " // " + bri.label + " // ALL VECTORS CONFIRMED");
      } else {
        addLog("BLE // NO READING YET — ENTER MANUALLY", "event");
      }
      device.gatt.disconnect();
    } catch (err) {
      addLog("BLE // " + err.message, "event");
    }
  };

    const submitGlucose = () => {
    const val = parseFloat(glucoseInput);
    if (isNaN(val) || val < 1 || val > 30) return;
    setGlucoseReading(val);
    const today = new Date().toLocaleDateString("en-CA");
    const nowIso = new Date().toISOString();
    localStorage.setItem("glucoseReading", val.toString());
    localStorage.setItem("glucoseDate", today);
    localStorage.setItem("glucoseTimestamp", nowIso);
    setGlucoseTimestamp(nowIso);
    const newGlucHist = [...glucHist, val].slice(-7);
    setGlucHist(newGlucHist);
    localStorage.setItem("glucoseHistory", JSON.stringify(newGlucHist));
    pushGlucoseToServer(val, nowIso);
    addLog(`MANUAL GLUCOSE: ${val.toFixed(1)} MMOL/L`, "roche");
    const briGlucose = calculateBRI({ glucose: val, hrv, rhr, sleepDurationHrs, glucosePending: false });
    addLog(`BIOLOGICAL READINESS INDEX: ${briGlucose.score} // ${briGlucose.label} // ALL VECTORS CONFIRMED`, "", briGlucose.color);
    setGlucoseEntryOpen(false);
    setGlucoseInput("");
  };

  useEffect(() => {
  }, []);

  useEffect(() => {
    const t = setInterval(() => setClock(ts()), 1000);
    return () => clearInterval(t);
  }, []);

  useEffect(() => {
    const fetchBridge = () =>
      fetch('/api/gen3-bridge')
        .then(res => res.ok ? res.json() : null)
        .catch(() => null)
        .then(data => { if (data && data.source === 'gen3_ble') setGen3Bridge(data); });
    fetchBridge();
    const id = setInterval(fetchBridge, 5 * 60 * 1000); // refresh every 5 min
    return () => clearInterval(id);
  }, []);

  // Cross-device glucose sync (2026-08-02) -- localStorage never leaves the
  // browser it was written in, so a reading entered on one device was
  // invisible on any other. Adopt the server's reading if it's for today
  // and newer than whatever this device already has (covers "entered on
  // another device after this one last loaded"); submitGlucose/
  // readBLEGlucose below push new readings back up so other devices pick
  // them up on their own next fetch.
  useEffect(() => {
    fetch('/api/glucose')
      .then(res => res.ok ? res.json() : null)
      .catch(() => null)
      .then(data => {
        if (!data || data.value == null || !data.timestamp) return;
        const today = new Date().toLocaleDateString("en-CA");
        const serverDate = new Date(data.timestamp).toLocaleDateString("en-CA");
        if (serverDate !== today) return;
        const localTimestamp = localStorage.getItem("glucoseTimestamp");
        if (!localTimestamp || new Date(data.timestamp) > new Date(localTimestamp)) {
          setGlucoseReading(data.value);
          setGlucoseTimestamp(data.timestamp);
          localStorage.setItem("glucoseReading", data.value.toString());
          localStorage.setItem("glucoseDate", today);
          localStorage.setItem("glucoseTimestamp", data.timestamp);
        }
      });
  }, []);

  const pushGlucoseToServer = (value, timestamp) => {
    fetch('/api/glucose', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ value, timestamp }),
    }).catch(() => {}); // best-effort -- local state/localStorage already updated regardless
  };

  // Cross-device history sync for HRV/RHR/Sleep/SpO2/Steps (2026-08-02) --
  // same problem and same fix as glucose above: each device was building its
  // own separate 7-day history purely from localStorage, so the SAME live
  // value showed a DIFFERENT 7d avg/trend on a laptop vs. a phone (confirmed
  // side-by-side: 47ms vs 38ms HRV avg, 69 vs 62bpm RHR avg, 33.7h vs 7.6h
  // sleep avg, all for the identical live reading). Adopts the server's
  // history as authoritative on load whenever it has any entries -- the
  // "Update 7-day histories" effect below pushes each day's values back up
  // so every device converges on the same shared history.
  useEffect(() => {
    fetch('/api/vector-history')
      .then(res => res.ok ? res.json() : null)
      .catch(() => null)
      .then(history => {
        if (!history || typeof history !== 'object') return;
        const dates = Object.keys(history).sort();
        const extract = (field) => dates.map(d => history[d][field]).filter(v => v != null).slice(-7);
        const fromServer = {
          hrv: extract('hrv'),
          rhr: extract('rhr'),
          sleepDurationHrs: extract('sleepDurationHrs').filter(isPlausibleSleepHours),
          spo2: extract('spo2'),
          steps: extract('steps'),
        };
        if (fromServer.hrv.length)              { setHrvHist(fromServer.hrv);        localStorage.setItem("hrvHistory", JSON.stringify(fromServer.hrv)); }
        if (fromServer.rhr.length)              { setRhrHist(fromServer.rhr);        localStorage.setItem("rhrHistory", JSON.stringify(fromServer.rhr)); }
        if (fromServer.sleepDurationHrs.length)  { setSleepHist(fromServer.sleepDurationHrs); localStorage.setItem("sleepDurationHistory", JSON.stringify(fromServer.sleepDurationHrs)); }
        if (fromServer.spo2.length)              { setSpo2Hist(fromServer.spo2);      localStorage.setItem("spo2History", JSON.stringify(fromServer.spo2)); }
        if (fromServer.steps.length)             { setStepHist(fromServer.steps);     localStorage.setItem("stepHistory", JSON.stringify(fromServer.steps)); }
      });
  }, []);

  // Update 7-day histories from Gen3 bridge — once per bridge date.
  // Writes to localStorage (fast local cache) AND pushes to the shared
  // /api/vector-history store (2026-08-02) so every device converges on
  // the same history instead of each building its own -- see the fetch-on-
  // mount effect above. The server write is a same-date merge (see
  // api/vector-history.js), so multiple devices recording "today" is
  // harmless, not duplicated.
  useEffect(() => {
    if (!gen3Bridge?.vectors || !gen3Bridge.timestamp) return;
    const bridgeDate = new Date(gen3Bridge.timestamp).toLocaleDateString("en-CA");
    if (localStorage.getItem("lastBridgeHistoryDate") === bridgeDate) return;
    const v = gen3Bridge.vectors;
    const serverPayload = { date: bridgeDate };
    if (v.hrv_ms != null) {
      const h = [...hrvHist, v.hrv_ms].slice(-7);
      setHrvHist(h); localStorage.setItem("hrvHistory", JSON.stringify(h));
      serverPayload.hrv = v.hrv_ms;
      addLog(`GEN3 HRV: ${Math.round(v.hrv_ms)} MS`, "roche");
    }
    if (v.rhr_bpm != null) {
      const h = [...rhrHist, v.rhr_bpm].slice(-7);
      setRhrHist(h); localStorage.setItem("rhrHistory", JSON.stringify(h));
      serverPayload.rhr = v.rhr_bpm;
      addLog(`GEN3 RHR: ${Math.round(v.rhr_bpm)} BPM`, "roche");
    }
    const sleepForHistory = v.sleep_duration_hrs ?? v.sleep_duration_estimate_hrs;
    if (sleepForHistory != null && isPlausibleSleepHours(sleepForHistory)) {
      const h = [...sleepHist, sleepForHistory].slice(-7);
      setSleepHist(h); localStorage.setItem("sleepDurationHistory", JSON.stringify(h));
      serverPayload.sleepDurationHrs = sleepForHistory;
      const estFlag = v.sleep_duration_hrs == null ? " (EST)" : "";
      addLog(`GEN3 SLEEP: ${sleepForHistory.toFixed(1)}H${estFlag}`, "roche");
    }
    if (v.spo2_avg_pct != null) {
      const h = [...spo2Hist, v.spo2_avg_pct].slice(-7);
      setSpo2Hist(h); localStorage.setItem("spo2History", JSON.stringify(h));
      serverPayload.spo2 = v.spo2_avg_pct;
      const avg = h.reduce((a, b) => a + b, 0) / h.length;
      const trend = h.length >= 2 ? (h[h.length-1] - h[0] > 0.3 ? "TRENDING UP" : h[0] - h[h.length-1] > 0.3 ? "TRENDING DOWN" : "STABLE") : "BUILDING";
      addLog(`GEN3 SPO2 7D AVG: ${avg.toFixed(1)}% // ${trend} // NOTE: GEN3 READS ~3-5% LOW`, "roche");
    }
    if (v.step_count != null && v.step_count > 0) {
      const h = [...stepHist, v.step_count].slice(-7);
      setStepHist(h); localStorage.setItem("stepHistory", JSON.stringify(h));
      serverPayload.steps = v.step_count;
      const avg = Math.round(h.reduce((a, b) => a + b, 0) / h.length);
      const trend = h.length >= 2 ? (h[h.length-1] - h[0] > 200 ? "TRENDING UP" : h[0] - h[h.length-1] > 200 ? "TRENDING DOWN" : "STABLE") : "BUILDING";
      addLog(`GEN3 STEPS 7D AVG: ${avg}/DAY // ${trend}`, "roche");
    }
    if (Object.keys(serverPayload).length > 1) {
      fetch('/api/vector-history', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(serverPayload),
      }).catch(() => {}); // best-effort -- local state/localStorage already updated regardless
    }
    localStorage.setItem("lastBridgeHistoryDate", bridgeDate);
  }, [gen3Bridge]);

  useEffect(() => {
    if (!locked) {
      addLog("TELEMETRY STREAM ACTIVE", "event");
      addLog("READY // 4 VECTORS ENGAGED", "event");
    }
  }, [locked]);

  const logic = evaluateSources(null, gen3Bridge, { glucose: glucoseReading });
  const { hrv, rhr, sleepDurationHrs } = {
    hrv: logic.vectors.hrv.value,
    rhr: logic.vectors.rhr.value,
    sleepDurationHrs: logic.vectors.sleepDurationHrs.value,
  };
  const sleepEstimateMethod = logic.vectors.sleepDurationHrs.estimateMethod ?? null;
  const sleepIsEstimate = sleepEstimateMethod !== null;

  useEffect(() => { setBriefingOpen(false); }, [logic.level]);

  // Per-vector timestamps — Gen4 dead, all vectors from Gen3 bridge timestamp
  const gen3Ts  = gen3Bridge?.timestamp ?? null;
  const hrvTs   = logic.vectors.hrv.source   === SOURCE_GEN3 ? gen3Ts : null;
  const rhrTs   = logic.vectors.rhr.source   === SOURCE_GEN3 ? gen3Ts : null;
  // Prefer the sleep-data-specific timestamp (real freshness of the 0x4C
  // decode this value came from) over the bridge's general timestamp (which
  // reflects HRV/RHR refreshing live every cycle, not sleep data at all) --
  // falls back to the old behavior if a bridge predates this field.
  const sleepTs = logic.vectors.sleepDurationHrs.measuredAt
    ?? (logic.vectors.sleepDurationHrs.source === SOURCE_GEN3 ? gen3Ts : null);

  // Trend + avg per vector (histories come from state, seeded from localStorage on mount)
  const hrvAvg   = avgOf(hrvHist);
  const rhrAvg   = avgOf(rhrHist);
  const sleepAvg = avgOf(sleepHist);
  const glucAvg  = avgOf(glucHist);
  const spo2Avg  = avgOf(spo2Hist);
  const stepAvg  = avgOf(stepHist);

  // Meta strings — threshold pulled from THRESHOLDS.* so displayed rule always matches engine rule
  function metaParts(threshold, avg, trend) {
    return [threshold, avg, trend].filter(Boolean).join(" · ");
  }
  const hrvMeta   = hrv              !== null ? metaParts(`optimal ≥ ${THRESHOLDS.hrv}ms`,            hrvAvg   !== null ? `7d avg ${Math.round(hrvAvg)}ms`  : null, getTrend(hrvHist))   : null;
  const rhrMeta   = rhr              !== null ? metaParts(`optimal < ${THRESHOLDS.rhr}bpm`,            rhrAvg   !== null ? `7d avg ${Math.round(rhrAvg)}bpm` : null, getTrend(rhrHist))   : null;
  const sleepMeta = sleepDurationHrs !== null ? metaParts(`optimal ≥ ${THRESHOLDS.sleepDurationWarn}h`, sleepAvg !== null ? `7d avg ${sleepAvg.toFixed(1)}h`  : null, getTrend(sleepHist)) : null;
  const glucMeta  = glucoseReading   !== null ? metaParts(`optimal < ${THRESHOLDS.glucose}`,           glucAvg  !== null ? `7d avg ${glucAvg.toFixed(1)}`    : null, getTrend(glucHist))  : null;

  const bri = calculateBRI({ glucose: glucoseReading, hrv, rhr, sleepDurationHrs, glucosePending: glucoseReading === null });

  const handleExecute = () => {
    setExecState("active");
    addLog(`PROTOCOL EXECUTED // ${logic.name} // ${ts()}`, "event");
  };

  const handleComplete = () => {
    setExecState("complete");
    addLog(`PROTOCOL COMPLETE // RETURNING TO BASELINE // ${ts()}`, "event");
    setTimeout(() => {
      const today = new Date().toLocaleDateString("en-CA");
      localStorage.setItem("protocolExecutedDate", today);
      setExecState("satisfied");
      addLog(`PROTOCOL SATISFIED // SYSTEM STANDING DOWN // ${ts()}`, "event");
    }, 3000);
  };

  const gen3Live = gen3Bridge?.timestamp && !isStale(gen3Bridge.timestamp);
  const gen3Present = !!gen3Bridge?.timestamp;
  const badgeColor = gen3Live ? "var(--accent-blue)" : gen3Present ? "var(--accent-amber)" : "var(--text-dim)";
  const badgeLabel = gen3Live ? "OURA LIVE" : gen3Present ? "OURA" : "OFFLINE";

  return (
    <>
      <style>{CSS}</style>

      {locked ? (
        <div className="auth-overlay">
          <div className="auth-title">METHUSELAH // ACCESS REQUIRED</div>
          <input
            className="auth-input"
            type="password"
            value={input}
            onChange={e => { setInput(e.target.value); setAuthError(false); }}
            onKeyDown={e => {
              if (e.key !== "Enter") return;
              if (input === MASTER_KEY) unlock();
              else { setAuthError(true); setInput(""); }
            }}
            placeholder="********"
          />
          <div className="auth-hint">INPUT MASTER KEY → PRESS RETURN</div>
          <button
            className="auth-decrypt"
            onClick={() => {
              if (input === MASTER_KEY) unlock();
              else { setAuthError(true); setInput(""); }
            }}
          >
            ENTER
          </button>
          {authError && <div className="auth-error">⚠ ACCESS DENIED // INVALID KEY</div>}
        </div>
      ) : (
        <div className="shell" style={{ minHeight: "100vh", height: "100vh", display: "flex", flexDirection: "column", overflow: "hidden" }}>
          <div className="header">
            <div className="brand-wrap">
              <div className="brand">METHUSELAH</div>
            </div>
            <div className="header-right">
              <div className="header-top-row">
                <div className="live-badge" style={{ color: badgeColor }}>
                  <div className="blink" style={{ background: badgeColor }} />
                  {badgeLabel}
                </div>
              </div>
              <div className="clock">{clock}</div>
            </div>
          </div>

          <div className="telemetry-grid">
            <GlucosePanel
              reading={glucoseReading}
              entryOpen={glucoseEntryOpen}
              inputVal={glucoseInput}
              meta={glucMeta}
              age={formatAge(glucoseTimestamp)}
              stale={isStale(glucoseTimestamp)}
              onTap={() => setGlucoseEntryOpen(true)}
              onBLERead={readBLEGlucose}
              onInputChange={e => setGlucoseInput(e.target.value)}
              onKeyDown={e => { if (e.key === "Enter") submitGlucose(); if (e.key === "Escape") { setGlucoseEntryOpen(false); setGlucoseInput(""); } }}
              onSubmit={submitGlucose}
            />
            <Metric
              label="HRV"
              val={hrv !== null ? Math.round(hrv) : "--"}
              unit="ms"
              color={hrv === null ? "var(--text-dim)" : hrv < THRESHOLDS.hrv ? "var(--accent-amber)" : "var(--accent-green)"}
              meta={hrvMeta}
              age={formatAge(hrvTs)}
              stale={isStale(hrvTs)}
              source={logic.vectors.hrv.source}
            />
            <Metric
              label="CARDIAC LOAD"
              val={rhr !== null ? rhr : "--"}
              unit="bpm"
              color={rhr === null ? "var(--text-dim)" : rhr > THRESHOLDS.rhr ? "var(--accent-amber)" : "var(--accent-green)"}
              meta={rhrMeta}
              age={formatAge(rhrTs)}
              stale={isStale(rhrTs)}
              source={logic.vectors.rhr.source}
            />
            <Metric
              label="SLEEP DURATION"
              val={sleepDurationHrs !== null ? `${sleepIsEstimate ? "~" : ""}${sleepDurationHrs.toFixed(1)}` : "--"}
              unit={sleepEstimateMethod === "stage_sum" ? "hrs (stage sum)" : sleepEstimateMethod === "bout_tail" ? "hrs (est.)" : "hrs"}
              color={sleepDurationHrs === null ? "var(--text-dim)" : sleepDurationHrs < THRESHOLDS.sleepDurationCritical ? "var(--accent-red)" : sleepDurationHrs < THRESHOLDS.sleepDurationWarn ? "var(--accent-amber)" : "var(--accent-green)"}
              meta={sleepMeta}
              age={formatAge(sleepTs)}
              stale={isStale(sleepTs)}
              source={logic.vectors.sleepDurationHrs.source}
            />
          </div>

          <div className="command-wrap" style={{ borderColor: execState === "satisfied" ? "#00ff66" : bri.color }}>
            <div className="corner tl" /><div className="corner tr" />
            <div className="corner bl" /><div className="corner br" />
            <div className="cmd-meta">{logic.level.toUpperCase()} // {clock}</div>
            {execState === "idle" ? (
              <>
                <div
                  className="cmd-text"
                  style={{ color: logic.color, cursor: "pointer" }}
                  onClick={() => setBriefingOpen(o => !o)}
                >
                  {logic.cmd}
                </div>
                {briefingOpen && (
                  <div className="cmd-briefing">{logic.briefing}</div>
                )}
                <div className="cmd-rationale">{logic.rat}</div>
                {logic.level === "awaiting" ? (
                  <div className="tel-tap-hint">NO DATA — RUN DAEMON OR MORNING PULL</div>
                ) : logic.level !== "optimal" ? (
                  <button className="btn-execute" onClick={handleExecute}>
                    EXECUTE PROTOCOL
                  </button>
                ) : (
                  <div className="optimal-label">BASELINE STABLE.</div>
                )}
              </>
            ) : execState === "active" ? (
              <>
                <div className="cmd-text" style={{ color: logic.color }}>PROTOCOL ACTIVE.</div>
                <button className="btn-execute" onClick={handleComplete}>
                  PROTOCOL COMPLETE
                </button>
              </>
            ) : execState === "complete" ? (
              <div className="cmd-text" style={{ color: logic.color }}>PROTOCOL COMPLETE.</div>
            ) : (
              <>
                <div className="cmd-meta">WEEKLY PATTERN // 7-DAY REVIEW</div>
                <div className="weekly-grid">
                  <div className="weekly-row">
                    <span className="weekly-label">SPO2</span>
                    <span className="weekly-val">{spo2Avg !== null ? `${spo2Avg.toFixed(1)}% AVG` : '--'}</span>
                    <span className="weekly-trend">{trendGlyph(spo2Hist) || (spo2Hist.length < 2 ? 'BUILDING' : '')}</span>
                    {spo2Avg !== null && <span className="weekly-caveat">GEN3 ~3-5% LOW</span>}
                  </div>
                  <div className="weekly-row">
                    <span className="weekly-label">STEPS</span>
                    <span className="weekly-val">{stepAvg !== null ? `${Math.round(stepAvg)}/DAY` : '--'}</span>
                    <span className="weekly-trend">{trendGlyph(stepHist) || (stepHist.length < 2 ? 'BUILDING' : '')}</span>
                  </div>
                  <div className="weekly-row">
                    <span className="weekly-label">SLEEP ONSET</span>
                    <span className="weekly-val weekly-caveat">AWAITING DATA</span>
                  </div>
                </div>
                <div className="cmd-rationale" style={{ color: "var(--text-dim)" }}>PROTOCOL EXECUTED // RETURN TOMORROW</div>
              </>
            )}
          </div>

          {gen3Bridge && (
            <RawTelemetryPanel
              bridge={gen3Bridge}
              open={rawTelemetryOpen}
              onToggle={() => setRawTelemetryOpen(o => !o)}
              stale={isStale(gen3Bridge.timestamp)}
            />
          )}

          <div className="sys-log" ref={logRef}>
            {logs.map((l, i) => (
              <div key={i} className="log-line">
                <span className="log-time">[{l.time}]</span>
                <span
                  className={l.type === "roche" ? "log-roche" : ""}
                  style={l.color ? { color: l.color } : undefined}
                >
                  {l.msg}{i === 0 && <span className="log-cursor" />}
                </span>
              </div>
            ))}
          </div>
        </div>
      )}
    </>
  );
}
