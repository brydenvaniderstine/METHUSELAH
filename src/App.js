import React, { useState, useEffect, useRef } from "react";

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
.brand-sub { font-size: 8px; color: var(--text-dim); letter-spacing: 1px; white-space: nowrap; overflow: hidden; text-overflow: ellipsis; max-width: 45vw; }

.header-right { display: flex; flex-direction: column; align-items: flex-end; gap: 6px; }
.header-top-row { display: flex; gap: 12px; align-items: center; }
.live-badge { display: flex; align-items: center; gap: 6px; font-size: 9px; letter-spacing: 2px; }
.blink { width: 7px; height: 7px; border-radius: 50%; animation: pulse 1.5s infinite; }
@keyframes pulse { 0%,100% { opacity: 1; box-shadow: 0 0 8px currentColor; } 50% { opacity: 0.15; box-shadow: none; } }
.clock { font-size: 9px; color: var(--text-dim); letter-spacing: 1px; }

.ble-btn {
  font-family: var(--font-mono); font-size: 8px; letter-spacing: 1px; padding: 3px 8px;
  border: 1px solid var(--line); background: transparent; color: var(--text-dim);
  cursor: pointer; text-transform: uppercase; transition: all 0.3s; opacity: 0.4;
}
.ble-btn:hover:not(:disabled) { border-color: var(--line-bright); color: var(--text-mid); opacity: 0.7; }
.ble-btn:disabled { opacity: 0.2; cursor: not-allowed; }
.ble-btn.live { border-color: var(--accent-green); color: var(--accent-green); opacity: 1; }
.ble-btn.roche { border-color: var(--accent-blue); color: var(--accent-blue); opacity: 1; }
.ble-btn.scanning { border-color: var(--accent-amber); color: var(--accent-amber); opacity: 1; }

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
.tel-status { font-size: 9px; font-weight: 700; letter-spacing: 1px; }
.tel-source { font-size: 8px; color: var(--accent-blue); letter-spacing: 1px; margin-top: 4px; }
.tel-tap-hint { font-size: 8px; color: var(--text-dim); letter-spacing: 1px; margin-top: 4px; }

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
.command-wrap::before {
  content: 'METHUSELAH // CORE // LOGIC';
  position: absolute; top: -9px; left: 20px; background: var(--panel);
  padding: 0 10px; font-size: 9px; color: var(--accent-amber); font-weight: 700; letter-spacing: 2px;
}
.corner { position: absolute; width: 14px; height: 14px; border: 1px solid var(--text-dim); }
.tl { top: 4px; left: 4px; border-right: 0; border-bottom: 0; }
.tr { top: 4px; right: 4px; border-left: 0; border-bottom: 0; }
.bl { bottom: 4px; left: 4px; border-right: 0; border-top: 0; }
.br { bottom: 4px; right: 4px; border-left: 0; border-top: 0; }

.cmd-meta { font-size: 9px; color: var(--text-dim); margin-bottom: 10px; letter-spacing: 2px; }
.cmd-text { font-size: 16px; font-weight: 700; margin-bottom: 10px; transition: color 0.5s; max-width: 100%; line-height: 1.3; }
.cmd-rationale { font-size: 10px; color: var(--text-mid); line-height: 1.6; max-width: 100%; margin-bottom: 18px; letter-spacing: 0.5px; }

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

.sys-log {
  flex: 1;
  overflow-y: auto;
  border-top: 1px solid var(--line-bright);
  padding-top: 8px;
  display: flex;
  flex-direction: column-reverse;
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
.oura-setup {
  position: fixed; inset: 0; background: var(--bg); z-index: 10000;
  display: flex; flex-direction: column; justify-content: center; align-items: center; gap: 16px;
  font-family: var(--font-mono); padding: 24px; box-sizing: border-box;
}
.oura-title { font-size: 13px; color: var(--accent-amber); letter-spacing: 4px; font-weight: 700; text-align: center; }
.oura-sub { font-size: 9px; color: var(--text-dim); letter-spacing: 2px; text-align: center; line-height: 1.8; }
.oura-input {
  background: transparent; border: 1px solid var(--line-bright); color: var(--accent-green);
  font-family: var(--font-mono); font-size: 11px; padding: 12px; text-align: center;
  width: 80vw; max-width: 400px; outline: none; transition: border-color 0.2s; letter-spacing: 1px;
}
.oura-input:focus { border-color: var(--accent-green); }
.oura-btn { font-family: var(--font-mono); font-size: 11px; letter-spacing: 3px; font-weight: 700; padding: 12px; background: var(--text-main); color: var(--bg); border: none; cursor: pointer; box-shadow: 3px 3px 0 var(--accent-amber); text-transform: uppercase; width: 80vw; max-width: 400px; }
.oura-skip { font-size: 9px; color: var(--text-dim); letter-spacing: 2px; cursor: pointer; text-decoration: underline; margin-top: 8px; background: none; border: none; font-family: var(--font-mono); text-transform: uppercase; }
.oura-badge { font-size: 8px; color: var(--accent-blue); letter-spacing: 1px; margin-top: 4px; }
`;

const MASTER_KEY = "v1";

function Metric({ label, val, unit, pct, color, status, isReal }) {
  return (
    <div className="tel-block">
      <div className="tel-label">{label}</div>
      <div className="tel-value" style={{ color }}>
        {val} <span className="tel-unit">{unit}</span>
      </div>
      <div className="tel-bar-wrap">
        <div className="tel-bar" style={{ width: `${Math.max(val === '--' ? 0 : 5, Math.min(100, pct))}%`, background: color }} />
      </div>
      <div className="tel-status" style={{ color }}>{status}</div>
      {isReal && <div className="tel-source">● OURA LIVE</div>}
    </div>
  );
}

function GlucosePanel({ reading, entryOpen, inputVal, onTap, onInputChange, onKeyDown, onSubmit }) {
  const hasReading = reading !== null;
  const isElevated = hasReading && reading > 5.8;
  const color = !hasReading
    ? "var(--accent-amber)"
    : isElevated
    ? "var(--accent-red)"
    : "var(--accent-green)";
  const status = !hasReading ? "AWAITING INTERCEPT" : isElevated ? "ELEVATED" : "STABLE";
  const pct = hasReading ? ((reading - 3.5) / (14 - 3.5)) * 100 : 0;

  return (
    <div
      className="tel-block"
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
          <div className="tel-bar-wrap">
            <div className="tel-bar" style={{ width: `${Math.max(hasReading ? 5 : 0, Math.min(100, pct))}%`, background: color }} />
          </div>
          <div className="tel-status" style={{ color }}>{status}</div>
          {!hasReading && <div className="tel-tap-hint">TAP TO ENTER READING</div>}
        </>
      )}
    </div>
  );
}

export default function MethuselahFinal() {
  const ts = () => new Date().toLocaleTimeString([], { hour12: false, hour: "2-digit", minute: "2-digit", second: "2-digit" });

  const [locked,          setLocked]          = useState(true);
  const [showOuraSetup,   setShowOuraSetup]   = useState(false);
  const [ouraToken,       setOuraToken]       = useState("");
  const [ouraInput,       setOuraInput]       = useState("");
  const [ouraStatus,      setOuraStatus]      = useState("DISCONNECTED");
  const [input,           setInput]           = useState("");
  const [authError,       setAuthError]       = useState(false);
  const [clock,           setClock]           = useState(ts());
  const [ouraData,        setOuraData]        = useState({ hrv: null, rhr: null, deepSleepPct: null, isLive: false });
  const [glucoseReading,  setGlucoseReading]  = useState(null);
  const [glucoseEntryOpen, setGlucoseEntryOpen] = useState(false);
  const [glucoseInput,    setGlucoseInput]    = useState("");
  const [executed,        setExecuted]        = useState(false);
  const [isScanning,      setIsScanning]      = useState(false);
  const [bleStatus,       setBleStatus]       = useState("DISCONNECTED");
  const [rocheDevice,     setRocheDevice]     = useState(null);
  const [logs,            setLogs]            = useState([{ time: ts(), msg: "BIOLOGICAL SYSTEMS ONLINE // STANDING BY", type: "" }]);
  const logRef = useRef(null);

  const addLog = (msg, type = "") => setLogs(prev => [{ time: ts(), msg, type }, ...prev].slice(0, 12));

  const fetchOuraData = async (token) => {
    try {
      const today = new Date();
      const yesterday = new Date(today);
      yesterday.setDate(yesterday.getDate() - 1);
      const fmt = (d) => d.toISOString().split("T")[0];
      const res = await fetch(
        `/api/oura?token=${token}&start_date=${fmt(yesterday)}&end_date=${fmt(today)}`
      );
      const data = await res.json();
      if (data.data && data.data.length > 0) {
        const mainSleep = data.data.find(s => s.type === "long_sleep") || data.data[0];
        if (mainSleep && mainSleep.average_hrv) {
          const hrv = mainSleep.average_hrv;
          const rhr = mainSleep.lowest_heart_rate ?? null;
          const deepSleepPct =
            mainSleep.total_sleep_duration > 0
              ? (mainSleep.deep_sleep_duration / mainSleep.total_sleep_duration) * 100
              : null;
          setOuraData({ hrv, rhr, deepSleepPct, isLive: true });
          setOuraStatus("OURA_LIVE");
          addLog(`OURA INTERCEPT: ${hrv} MS HRV // LAST NIGHT`, "roche");
          if (rhr !== null) addLog(`CARDIAC INTERCEPT: ${rhr} BPM // LAST NIGHT`, "roche");
          if (deepSleepPct !== null) addLog(`REPAIR DEPTH: ${deepSleepPct.toFixed(0)}% // LAST NIGHT`, "roche");
          return true;
        }
      }
      addLog("OURA // NO SLEEP DATA FOUND FOR LAST NIGHT", "event");
      return false;
    } catch (err) {
      addLog("OURA BRIDGE FAILED // CHECK TOKEN", "event");
      return false;
    }
  };

  const handleOuraConnect = async () => {
    if (!ouraInput.trim()) return;
    const success = await fetchOuraData(ouraInput.trim());
    if (success) {
      localStorage.setItem("oura_token", ouraInput.trim());
      setOuraToken(ouraInput.trim());
      setShowOuraSetup(false);
      addLog("OURA TOKEN SAVED // DATA SOVEREIGNTY CONFIRMED", "event");
    } else {
      addLog("OURA TOKEN INVALID // PLEASE RETRY", "event");
    }
  };

  const unlock = () => {
    setLocked(false);
    setAuthError(false);
    const saved = localStorage.getItem("oura_token");
    if (saved) {
      setOuraToken(saved);
      fetchOuraData(saved);
    } else {
      setShowOuraSetup(true);
    }
    // Load today's glucose if stored
    const storedDate    = localStorage.getItem("glucoseDate");
    const storedReading = localStorage.getItem("glucoseReading");
    const today = new Date().toISOString().split("T")[0];
    if (storedDate === today && storedReading) {
      setGlucoseReading(parseFloat(storedReading));
    }
  };

  const submitGlucose = () => {
    const val = parseFloat(glucoseInput);
    if (isNaN(val) || val < 1 || val > 30) return;
    setGlucoseReading(val);
    const today = new Date().toISOString().split("T")[0];
    localStorage.setItem("glucoseReading", val.toString());
    localStorage.setItem("glucoseDate", today);
    addLog(`GLYCEMIC INTERCEPT: ${val.toFixed(1)} MMOL/L // MANUAL ENTRY`, "roche");
    setGlucoseEntryOpen(false);
    setGlucoseInput("");
  };

  useEffect(() => {
    const s = document.createElement("style");
    s.textContent = CSS;
    document.head.appendChild(s);
    return () => document.head.removeChild(s);
  }, []);

  useEffect(() => {
    const t = setInterval(() => setClock(ts()), 1000);
    return () => clearInterval(t);
  }, []);

  useEffect(() => {
    if (!locked) {
      addLog("TELEMETRY STREAM ACTIVE // OLIVER_BC", "event");
      addLog("READY // 4 VECTORS ENGAGED", "event");
    }
  }, [locked]);

  // Logic engine — four vector priority stack (highest to lowest)
  const { hrv, rhr, deepSleepPct } = ouraData;

  let logic = {
    cmd:    "BIOLOGY OPTIMAL.",
    rat:    "",
    color:  "var(--text-main)",
    border: "var(--line-bright)",
    level:  "optimal",
  };

  if (glucoseReading !== null && glucoseReading > 5.8) {
    logic = {
      cmd:    "INITIATE 24-HOUR WATER FAST.",
      rat:    `GLYCEMIC FRICTION DETECTED (${glucoseReading.toFixed(1)} MMOL/L).`,
      color:  "var(--accent-red)",
      border: "var(--accent-red)",
      level:  "critical",
    };
  } else if (hrv !== null && hrv < 40) {
    logic = {
      cmd:    "EXECUTE 45-MIN ZONE 2 OUTPUT.",
      rat:    `AUTONOMIC STRESS DETECTED (${Math.round(hrv)} MS HRV).`,
      color:  "var(--text-main)",
      border: "var(--accent-amber)",
      level:  "warn",
    };
  } else if (rhr !== null && rhr > 60) {
    logic = {
      cmd:    "INITIATE ACTIVE RECOVERY PROTOCOL.",
      rat:    `CARDIAC LOAD ELEVATED (${rhr} BPM RHR).`,
      color:  "var(--text-main)",
      border: "var(--accent-amber)",
      level:  "warn",
    };
  } else if (deepSleepPct !== null && deepSleepPct < 15) {
    logic = {
      cmd:    "INITIATE SLEEP PROTOCOL TONIGHT.",
      rat:    `REPAIR DEPTH DEFICIENT (${deepSleepPct.toFixed(0)}% DEEP SLEEP).`,
      color:  "var(--text-main)",
      border: "var(--accent-amber)",
      level:  "warn",
    };
  }

  const hrvPct  = hrv  !== null ? ((hrv  - 25) / (95 - 25))   * 100 : 0;
  const rhrPct  = rhr  !== null ? ((rhr  - 40) / (100 - 40))  * 100 : 0;
  const deepPct = deepSleepPct !== null ? Math.min(100, (deepSleepPct / 30) * 100) : 0;

  const handleExecute = () => {
    setExecuted(true);
    addLog("PROTOCOL LOGGED: " + logic.cmd, "event");
    setTimeout(() => {
      setExecuted(false);
      addLog("PROTOCOL COMPLETE // RETURNING TO BASELINE", "event");
    }, 2500);
  };

  const handleHardwareConnect = async () => {
    // BLE path closed on web — ESP32S3 bridge handles hardware in v2
    return;
  };

  const bleColor = bleStatus === "ROCHE_LIVE" ? "var(--accent-blue)"
    : isScanning ? "var(--accent-amber)"
    : ouraStatus === "OURA_LIVE" ? "var(--accent-blue)"
    : "var(--text-dim)";

  const bleBtnClass = bleStatus === "ROCHE_LIVE" ? "ble-btn roche"
    : isScanning ? "ble-btn scanning"
    : "ble-btn";

  const badgeLabel = bleStatus === "ROCHE_LIVE" ? "ROCHE LIVE"
    : ouraStatus === "OURA_LIVE" ? "OURA LIVE"
    : isScanning ? bleStatus
    : "OFFLINE";

  return (
    <>
      <style>{CSS}</style>

      {showOuraSetup && !locked && (
        <div className="oura-setup">
          <div className="oura-title">OURA INTEGRATION</div>
          <div className="oura-sub">
            YOUR DATA. YOUR DEVICE. YOUR CONTROL.<br />
            PASTE YOUR PERSONAL ACCESS TOKEN BELOW.<br />
            STORED LOCALLY. NEVER TRANSMITTED.
          </div>
          <input
            className="oura-input"
            type="password"
            value={ouraInput}
            onChange={e => setOuraInput(e.target.value)}
            placeholder="PASTE OURA TOKEN HERE"
          />
          <button className="oura-btn" onClick={handleOuraConnect}>CONNECT OURA</button>
          <button className="oura-skip" onClick={() => setShowOuraSetup(false)}>SKIP FOR NOW</button>
          <div className="oura-badge">● OURA RING // HRV + RHR + SLEEP VECTORS</div>
        </div>
      )}

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
              <div className="brand-sub">
                v1.0.8
                {rocheDevice && ` // ${rocheDevice}`}
              </div>
            </div>
            <div className="header-right">
              <div className="header-top-row">
                <div className="live-badge" style={{ color: bleColor }}>
                  <div className="blink" style={{ background: bleColor }} />
                  {badgeLabel}
                </div>
                <button
                  className={bleBtnClass}
                  onClick={handleHardwareConnect}
                  disabled={isScanning || bleStatus === "ROCHE_LIVE"}
                >
                  {isScanning ? "SCANNING..." : bleStatus === "ROCHE_LIVE" ? "NODE CONNECTED" : "CONNECT HARDWARE"}
                </button>
              </div>
              <div className="clock">{clock}</div>
            </div>
          </div>

          <div className="telemetry-grid">
            <GlucosePanel
              reading={glucoseReading}
              entryOpen={glucoseEntryOpen}
              inputVal={glucoseInput}
              onTap={() => setGlucoseEntryOpen(true)}
              onInputChange={e => setGlucoseInput(e.target.value)}
              onKeyDown={e => { if (e.key === "Enter") submitGlucose(); if (e.key === "Escape") { setGlucoseEntryOpen(false); setGlucoseInput(""); } }}
              onSubmit={submitGlucose}
            />
            <Metric
              label="HRV // SYSTEMIC FRICTION"
              val={hrv !== null ? Math.round(hrv) : "--"}
              unit="ms"
              pct={hrvPct}
              color={hrv === null ? "var(--text-dim)" : hrv < 40 ? "var(--accent-amber)" : "var(--accent-green)"}
              status={hrv === null ? "AWAITING DATA" : hrv < 40 ? "SUPPRESSED" : "OPTIMAL"}
              isReal={ouraData.isLive}
            />
            <Metric
              label="CARDIAC LOAD"
              val={rhr !== null ? rhr : "--"}
              unit="bpm"
              pct={rhrPct}
              color={rhr === null ? "var(--text-dim)" : rhr > 60 ? "var(--accent-amber)" : "var(--accent-green)"}
              status={rhr === null ? "AWAITING DATA" : rhr > 60 ? "ELEVATED" : "OPTIMAL"}
              isReal={ouraData.isLive}
            />
            <Metric
              label="REPAIR DEPTH"
              val={deepSleepPct !== null ? deepSleepPct.toFixed(0) : "--"}
              unit="%"
              pct={deepPct}
              color={deepSleepPct === null ? "var(--text-dim)" : deepSleepPct < 15 ? "var(--accent-amber)" : "var(--accent-green)"}
              status={deepSleepPct === null ? "AWAITING DATA" : deepSleepPct < 15 ? "DEFICIENT" : "OPTIMAL"}
              isReal={ouraData.isLive}
            />
          </div>

          <div className="command-wrap" style={{ borderColor: logic.border }}>
            <div className="corner tl" /><div className="corner tr" />
            <div className="corner bl" /><div className="corner br" />
            <div className="cmd-meta">PROTOCOL // {logic.level.toUpperCase()} // {clock}</div>
            <div className="cmd-text" style={{ color: logic.color }}>{logic.cmd}</div>
            <div className="cmd-rationale">{logic.rat}</div>
            {logic.level !== "optimal" ? (
              <button
                className={`btn-execute ${executed ? "done" : ""}`}
                onClick={handleExecute}
                disabled={executed}
              >
                {executed ? "PROTOCOL LOGGED" : "EXECUTE PROTOCOL"}
              </button>
            ) : (
              <div className="optimal-label">BASELINE STABLE. // ACTIVE</div>
            )}
          </div>

          <div className="sys-log" ref={logRef}>
            {logs.map((l, i) => (
              <div key={i} className="log-line">
                <span className="log-time">[{l.time}]</span>
                <span className={l.type === "roche" ? "log-roche" : ""}>
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
