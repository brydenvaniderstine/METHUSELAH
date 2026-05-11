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
  display: grid; grid-template-columns: repeat(3, minmax(0, 1fr));
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
        <div className="tel-bar" style={{ width: `${Math.max(5, Math.min(100, pct))}%`, background: color }} />
      </div>
      <div className="tel-status" style={{ color }}>{status}</div>
      {isReal && <div className="tel-source">● ROCHE INTERCEPT</div>}
    </div>
  );
}

export default function MethuselahFinal() {
  const ts = () => new Date().toLocaleTimeString([], { hour12: false, hour: '2-digit', minute: '2-digit', second: '2-digit' });

  const [locked,      setLocked]      = useState(true);
  const [showOuraSetup, setShowOuraSetup] = useState(false);
  const [ouraToken,     setOuraToken]     = useState("");
  const [ouraInput,     setOuraInput]     = useState("");
  const [ouraStatus,    setOuraStatus]    = useState("DISCONNECTED");
  const [input,       setInput]       = useState("");
  const [authError,   setAuthError]   = useState(false);
  const [clock,       setClock]       = useState(ts());
  const [telemetry,   setTelemetry]   = useState({ hrv: 45, glucose: 5.4, lactate: 1.1, isRealData: false });
  const [history,     setHistory]     = useState({ hrv: [45], glucose: [5.4], lactate: [1.1] });
  const [executed,    setExecuted]    = useState(false);
  const [isScanning,  setIsScanning]  = useState(false);
  const [bleStatus,   setBleStatus]   = useState("DISCONNECTED");
  const [rocheDevice, setRocheDevice] = useState(null);
  const [logs,        setLogs]        = useState([{ time: ts(), msg: "BIOLOGICAL SYSTEMS ONLINE // STANDING BY", type: "" }]);
  const logRef = useRef(null);

  const addLog = (msg, type = "") => setLogs(prev => [{ time: ts(), msg, type }, ...prev].slice(0, 12));

  const fetchOuraHRV = async (token) => {
    try {
      const today = new Date();
      const yesterday = new Date(today);
      yesterday.setDate(yesterday.getDate() - 1);
      const fmt = (d) => d.toISOString().split('T')[0];
      const res = await fetch(
        `https://api.ouraring.com/v2/usercollection/sleep?start_date=${fmt(yesterday)}&end_date=${fmt(today)}`,
        { headers: { Authorization: `Bearer ${token}` } }
      );
      const data = await res.json();
      if (data.data && data.data.length > 0) {
        const mainSleep = data.data.find(s => s.type === 'long_sleep') || data.data[0];
        if (mainSleep && mainSleep.average_hrv) {
          const hrv = mainSleep.average_hrv;
          setTelemetry(prev => ({ ...prev, hrv }));
          setOuraStatus("OURA_LIVE");
          addLog(`OURA INTERCEPT: ${hrv} MS HRV // LAST NIGHT`, "roche");
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
    const success = await fetchOuraHRV(ouraInput.trim());
    if (success) {
      localStorage.setItem('oura_token', ouraInput.trim());
      setOuraToken(ouraInput.trim());
      setShowOuraSetup(false);
      addLog("OURA TOKEN SAVED // DATA SOVEREIGNTY CONFIRMED", "event");
    } else {
      addLog("OURA TOKEN INVALID // PLEASE RETRY", "event");
    }
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
    if (!locked) { addLog("TELEMETRY STREAM ACTIVE // OLIVER_BC", "event"); addLog("READY // 3 VECTORS ENGAGED", "event"); }
  }, [locked]);

  useEffect(() => {
    if (locked || bleStatus === "ROCHE_LIVE") return;
    const t = setInterval(() => {
      setTelemetry(p => ({
        ...p,
        hrv:     Math.max(25,  Math.min(95,  p.hrv     + (Math.random() - 0.5) * 5)),
        glucose: Math.max(3.5, Math.min(14,  p.glucose  + (Math.random() - 0.5) * 0.3)),
        lactate: Math.max(0.6, Math.min(4.5, p.lactate  + (Math.random() - 0.5) * 0.3)),
      }));
    }, 3000);
    return () => clearInterval(t);
  }, [locked, bleStatus]);

  const handleKeyDown = (e) => {
    if (e.key !== "Enter") return;
    if (input === MASTER_KEY) { setLocked(false); setAuthError(false); const saved = localStorage.getItem("ouraToken"); if (saved) { setOuraToken(saved); fetchOuraHRV(saved); } else { setShowOuraSetup(true); } }
    else { setAuthError(true); setInput(""); }
  };

  const decodeSFLOAT = (view, offset) => {
    const bytes = view.getUint16(offset, true);
    const mantissa = bytes & 0x0FFF;
    let exponent = bytes >> 12;
    if (exponent >= 8) exponent -= 16;
    const signedMantissa = mantissa >= 2048 ? mantissa - 4096 : mantissa;
    return signedMantissa * Math.pow(10, exponent);
  };

  const handleHardwareConnect = async () => {
    // BLE path closed on web — ESP32S3 bridge handles hardware in v2
    return;
    if (isScanning || bleStatus === "ROCHE_LIVE") return;
    setIsScanning(true);
    try {
      await connectRoche({
        onData: (data) => {
          const parts = new TextDecoder().decode(data).split(",");
          if (parts.length === 3) {
            const glucose = parseFloat(parts[0]);
            const hrv = parseFloat(parts[1]);
            const lactate = parseFloat(parts[2]);
            if (!isNaN(glucose) && glucose > 1.0 && glucose < 33.3) {
              setTelemetry(prev => ({ ...prev, glucose, hrv, lactate, isRealData: true }));
              addLog(`ROCHE INTERCEPT: ${glucose.toFixed(1)} mmol/L`, "roche");
            }
          }
        },
        onLog: addLog,
        onStatus: setBleStatus,
        onDevice: setRocheDevice,
        onDisconnect: () => setTelemetry(p => ({ ...p, isRealData: false })),
      });
    } catch (error) {
      setBleStatus("DISCONNECTED");
      addLog(`BRIDGE FAILED: ${error.message}`, "event");
    } finally {
      setIsScanning(false);
    }
  };

  let logic = {
    cmd:    "BIOLOGY OPTIMAL.",
    rat:    "",
    color:  "var(--text-main)",
    border: "var(--line-bright)",
    level:  "optimal",
  };

  if (telemetry.glucose > 5.8) {
    logic = {
      cmd:    "INITIATE 24-HOUR WATER FAST.",
      rat:    `GLYCEMIC FRICTION DETECTED (${telemetry.glucose.toFixed(1)} MMOL/L).`,
      color:  "var(--accent-red)",
      border: "var(--accent-red)",
      level:  "critical",
    };
  } else if (telemetry.hrv < 40) {
    logic = {
      cmd:    "EXECUTE 45-MIN ZONE 2 OUTPUT.",
      rat:    `AUTONOMIC STRESS DETECTED (${Math.round(telemetry.hrv)} MS HRV).`,
      color:  "var(--text-main)",
      border: "var(--accent-amber)",
      level:  "warn",
    };
  } else if (telemetry.lactate > 2.0) {
    logic = {
      cmd:    "INITIATE ACTIVE RECOVERY PROTOCOL.",
      rat:    `LACTATE CLEARANCE DELAYED (${telemetry.lactate.toFixed(1)} MMOL/L).`,
      color:  "var(--text-main)",
      border: "var(--accent-amber)",
      level:  "warn",
    };
  }

  const glucosePct = ((telemetry.glucose - 3.5) / (14 - 3.5))   * 100;
  const hrvPct     = ((telemetry.hrv - 25)       / (95 - 25))    * 100;
  const lactatePct = ((telemetry.lactate - 0.6)  / (4.5 - 0.6)) * 100;

  const handleExecute = () => {
    setExecuted(true);
    addLog("PROTOCOL LOGGED: " + logic.cmd, "event");
    setTimeout(() => {
      setExecuted(false);
      addLog("PROTOCOL COMPLETE // RETURNING TO BASELINE", "event");
    }, 2500);
  };

  const bleColor = bleStatus === "ROCHE_LIVE" ? "var(--accent-blue)"
    : bleStatus === "SCANNING..." || bleStatus === "CONNECTING..." ? "var(--accent-amber)"
    : "var(--text-dim)";

  const bleBtnClass = bleStatus === "ROCHE_LIVE" ? "ble-btn roche"
    : isScanning ? "ble-btn scanning"
    : "ble-btn";

  return (
    <>
      <style>{CSS}</style>

      {showOuraSetup && !locked && (
        <div className="oura-setup">
          <div className="oura-title">OURA INTEGRATION</div>
          <div className="oura-sub">
            YOUR DATA. YOUR DEVICE. YOUR CONTROL.<br/>
            PASTE YOUR PERSONAL ACCESS TOKEN BELOW.<br/>
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
          <div className="oura-badge">● OURA RING // HRV VECTOR</div>
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
            onKeyDown={handleKeyDown}
            placeholder="********"
          />
          <div className="auth-hint">INPUT MASTER KEY → PRESS RETURN</div>
          <button className="auth-decrypt" onClick={() => {
            if (input === MASTER_KEY) { setLocked(false); setAuthError(false); const saved = localStorage.getItem("ouraToken"); if (saved) { setOuraToken(saved); fetchOuraHRV(saved); } else { setShowOuraSetup(true); } }
            else { setAuthError(true); setInput(""); }
          }}>ENTER</button>
          {authError && <div className="auth-error">⚠ ACCESS DENIED // INVALID KEY</div>}
        </div>
      ) : (
        <div className="shell" style={{minHeight: "100vh", height: "100vh", display: "flex", flexDirection: "column", overflow: "hidden"}}>
          <div className="header">
            <div className="brand-wrap">
              <div className="brand">METHUSELAH</div>
              <div className="brand-sub">
                v1.0.6
                {rocheDevice && ` // ${rocheDevice}`}
              </div>
            </div>
            <div className="header-right">
              <div className="header-top-row">
                <div className="live-badge" style={{ color: bleColor }}>
                  <div className="blink" style={{ background: bleColor }} />
                  {bleStatus === "ROCHE_LIVE" ? "ROCHE LIVE" : ouraStatus === "OURA_LIVE" ? "OURA LIVE" : bleStatus === "DISCONNECTED" ? "SIMULATION" : bleStatus}
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
            <Metric
              label="Glycemic Load"
              val={telemetry.glucose.toFixed(1)}
              unit="mmol/L"
              pct={glucosePct}
              color={telemetry.glucose > 5.8 ? "var(--accent-red)" : "var(--accent-green)"}
              status={telemetry.glucose > 5.8 ? "▲ VOLATILE" : "● STABLE"}
              isReal={telemetry.isRealData}
            />
            <Metric
              label="HRV // FRICTION"
              val={Math.round(telemetry.hrv)}
              unit="ms"
              pct={hrvPct}
              color={telemetry.hrv < 40 ? "var(--accent-amber)" : "var(--accent-green)"}
              status={telemetry.hrv < 40 ? "▼ SUPPRESSED" : "● OPTIMAL"}
              isReal={false}
            />
            <Metric
              label="Mito Clearance"
              val={telemetry.lactate.toFixed(1)}
              unit="mmol/L"
              pct={lactatePct}
              color={telemetry.lactate > 2.0 ? "var(--accent-amber)" : "var(--accent-green)"}
              status={telemetry.lactate > 2.0 ? "▲ DELAYED" : "● EFFICIENT"}
              isReal={false}
            />
          </div>

          <div className="command-wrap" style={{ borderColor: logic.border }}>
            <div className="corner tl" /><div className="corner tr" />
            <div className="corner bl" /><div className="corner br" />
            <div className="cmd-meta">
              PROTOCOL // {logic.level.toUpperCase()} // {clock}
              {telemetry.isRealData && " // ROCHE INTERCEPT ACTIVE"}
            </div>
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
