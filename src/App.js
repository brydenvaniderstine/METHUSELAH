import React, { useState, useEffect } from "react";
import { connectRoche } from "./ble";

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
  height: 100%; width: 100%;
  background: var(--bg); color: var(--text-main);
  font-family: var(--font-mono); font-size: 12px;
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
  display: grid; grid-template-rows: auto auto 1fr auto;
  height: 100%; width: 100%; max-width: 860px;
  margin: 0 auto; padding: 20px; position: relative; z-index: 1; gap: 16px;
}

.header {
  display: flex; justify-content: space-between; align-items: flex-end;
  border-bottom: 2px solid var(--text-main); padding-bottom: 10px;
}

.brand-wrap { display: flex; flex-direction: column; gap: 2px; }
.brand { font-size: 22px; font-weight: 700; letter-spacing: 4px; }
.brand-sub { font-size: 9px; color: var(--text-dim); letter-spacing: 3px; }

.header-right { display: flex; flex-direction: column; align-items: flex-end; gap: 6px; }
.header-top-row { display: flex; gap: 12px; align-items: center; }
.live-badge { display: flex; align-items: center; gap: 6px; font-size: 9px; letter-spacing: 2px; }
.blink { width: 7px; height: 7px; border-radius: 50%; animation: pulse 1.5s infinite; }
@keyframes pulse { 0%,100% { opacity: 1; box-shadow: 0 0 8px currentColor; } 50% { opacity: 0.15; box-shadow: none; } }
.clock { font-size: 9px; color: var(--text-dim); letter-spacing: 1px; }

.ble-btn {
  font-family: var(--font-mono); font-size: 9px; letter-spacing: 2px; padding: 4px 10px;
  border: 1px solid var(--line-bright); background: transparent; color: var(--text-mid);
  cursor: pointer; text-transform: uppercase; transition: 0.2s;
}
.ble-btn:hover:not(:disabled) { border-color: var(--accent-amber); color: var(--accent-amber); }
.ble-btn:disabled { opacity: 0.5; cursor: wait; }
.ble-btn.live { border-color: var(--accent-green); color: var(--accent-green); }
.ble-btn.roche { border-color: var(--accent-blue); color: var(--accent-blue); }

.telemetry-grid {
  display: grid; grid-template-columns: repeat(3, 1fr);
  gap: 2px; background: var(--line); border: 1px solid var(--line-bright);
}
.tel-block { background: var(--panel); padding: 14px 16px; position: relative; overflow: hidden; }
.tel-label { font-size: 9px; color: var(--text-dim); letter-spacing: 1.5px; margin-bottom: 6px; }
.tel-value { font-size: 30px; font-weight: 700; line-height: 1; font-variant-numeric: tabular-nums; }
.tel-unit { font-size: 10px; color: var(--text-dim); }
.tel-bar-wrap { height: 2px; background: var(--line); margin: 8px 0; }
.tel-bar { height: 100%; transition: width 1s ease, background 0.5s; }
.tel-status { font-size: 9px; font-weight: 700; letter-spacing: 1px; }
.tel-source { font-size: 8px; color: var(--accent-blue); letter-spacing: 1px; margin-top: 4px; }

.command-wrap {
  display: flex; flex-direction: column; justify-content: center; align-items: center;
  border: 2px solid var(--line-bright); padding: 32px 40px; text-align: center;
  background: var(--panel); position: relative; overflow: hidden; transition: border-color 0.5s;
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

.cmd-meta { font-size: 9px; color: var(--text-dim); margin-bottom: 16px; letter-spacing: 2px; }
.cmd-text { font-size: 24px; font-weight: 700; margin-bottom: 12px; transition: color 0.5s; max-width: 500px; }
.cmd-rationale { font-size: 10px; color: var(--text-mid); line-height: 1.7; max-width: 480px; margin-bottom: 24px; letter-spacing: 0.5px; }

.btn-execute {
  background: var(--text-main); color: var(--bg); border: none; padding: 14px 40px;
  font-family: var(--font-mono); font-size: 12px; font-weight: 700; letter-spacing: 3px;
  cursor: pointer; box-shadow: 4px 4px 0 var(--accent-amber);
  transition: transform 0.08s, box-shadow 0.08s;
}
.btn-execute:hover { transform: translate(2px,2px); box-shadow: 2px 2px 0 var(--accent-amber); }
.btn-execute:active { transform: translate(4px,4px); box-shadow: none; }
.btn-execute.done { background: var(--line-bright); color: var(--text-dim); box-shadow: none; cursor: not-allowed; transform: none; }

.optimal-label { color: var(--accent-green); font-weight: 700; letter-spacing: 3px; font-size: 12px; animation: breathe 3s infinite; }
@keyframes breathe { 0%,100% { opacity: 1; } 50% { opacity: 0.35; } }

.sys-log { height: 80px; overflow-y: auto; border-top: 1px solid var(--line-bright); padding-top: 10px; display: flex; flex-direction: column; gap: 2px; }
.log-line { font-size: 9px; color: var(--text-dim); display: flex; gap: 12px; animation: fadeIn 0.3s ease; }
@keyframes fadeIn { from { opacity: 0; transform: translateY(-3px); } to { opacity: 1; transform: translateY(0); } }
.log-time { color: var(--accent-amber); min-width: 80px; flex-shrink: 0; }
.log-roche { color: var(--accent-blue); }

.auth-overlay {
  position: fixed; inset: 0; background: var(--bg); z-index: 10000;
  display: flex; flex-direction: column; justify-content: center; align-items: center; gap: 24px;
  font-family: 'Space Mono', 'Courier New', Courier, monospace;
}
.auth-title { font-size: 13px; color: var(--accent-amber); letter-spacing: 4px; font-weight: 700; }
.auth-input {
  background: transparent; border: 1px solid var(--line-bright); color: var(--accent-green);
  font-family: var(--font-mono); font-size: 20px; padding: 12px; text-align: center;
  letter-spacing: 8px; width: 300px; outline: none; transition: border-color 0.2s;
}
.auth-input:focus { border-color: var(--accent-green); }
.auth-hint { font-size: 9px; color: var(--text-dim); letter-spacing: 2px; }
.auth-error { font-size: 9px; color: var(--accent-red); letter-spacing: 2px; animation: fadeIn 0.2s ease; }
`;

const MASTER_KEY = "METHUSELAH_V1";

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
  const [input,       setInput]       = useState("");
  const [authError,   setAuthError]   = useState(false);
  const [clock,       setClock]       = useState(ts());
  const [telemetry,   setTelemetry]   = useState({ hrv: 45, glucose: 5.4, lactate: 1.1, isRealData: false });
  const [history,     setHistory]     = useState({ hrv: [45], glucose: [5.4], lactate: [1.1] });
  const [executed,    setExecuted]    = useState(false);
  const [isScanning,  setIsScanning]  = useState(false);
  const [bleStatus,   setBleStatus]   = useState("DISCONNECTED");
  const [rocheDevice, setRocheDevice] = useState(null);
  const [logs,        setLogs]        = useState([{ time: ts(), msg: "SYS_INIT // METHUSELAH v1.0.5", type: "" }]);

  const addLog = (msg, type = "") => setLogs(prev => [{ time: ts(), msg, type }, ...prev].slice(0, 12));

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
    if (!locked) addLog("ACCESS GRANTED // TELEMETRY ACTIVE", "event");
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
    if (input === MASTER_KEY) { setLocked(false); setAuthError(false); }
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

  // ── ROCHE BLE BRIDGE v1.1.0 — CAPACITOR NATIVE / WEB BT ADAPTER ─────────
  const handleHardwareConnect = async () => {
    if (isScanning || bleStatus === "ROCHE_LIVE") return;
    setIsScanning(true);

    try {
      await connectRoche({
        onData: (data) => {
          const flags = data.getUint8(0);
          let offset = 1;
          offset += 2;  // sequence number
          offset += 7;  // base time
          if (flags & 0x01) offset += 2;  // time offset
          if (flags & 0x04) offset += 2;  // type/location

          if (offset + 2 > data.byteLength) {
            addLog("SYS_WARN: PACKET TOO SHORT // REJECTED", "event");
            return;
          }

          const mmolValue = decodeSFLOAT(data, offset);

          if (mmolValue < 1.0 || mmolValue > 33.3) {
            addLog(`SYS_WARN: VALUE OUT OF RANGE (${mmolValue.toFixed(1)}) // REJECTED`, "event");
            return;
          }

          const finalVal = parseFloat(mmolValue.toFixed(1));
          setTelemetry(prev => ({ ...prev, glucose: finalVal, isRealData: true }));
          setHistory(h => ({ ...h, glucose: [...h.glucose, finalVal].slice(-20) }));
          addLog(`ROCHE INTERCEPT: ${finalVal} mmol/L`, "roche");
        },
        onLog:        addLog,
        onStatus:     setBleStatus,
        onDevice:     setRocheDevice,
        onDisconnect: () => setTelemetry(p => ({ ...p, isRealData: false })),
      });
    } catch (error) {
      setBleStatus("DISCONNECTED");
      addLog(`BRIDGE FAILED: ${error.message}`, "event");
    } finally {
      setIsScanning(false);
    }
  };

  // ── LOGIC ENGINE ──────────────────────────────────────────────────────────
  let logic = {
    cmd:    "HOMEOSTASIS OPTIMAL",
    rat:    "All biological vectors within nominal range. No corrective intervention required.",
    color:  "var(--text-main)",
    border: "var(--line-bright)",
    level:  "optimal",
  };

  if (telemetry.glucose > 5.8) {
    logic = {
      cmd:    "INITIATE 24-HOUR WATER FAST.",
      rat:    `GLYCEMIC FRICTION DETECTED (${telemetry.glucose.toFixed(1)} MMOL/L). INSULIN SENSITIVITY RESET REQUIRED. — ATTIA / SINCLAIR`,
      color:  "var(--accent-red)",
      border: "var(--accent-red)",
      level:  "critical",
    };
  } else if (telemetry.hrv < 40) {
    logic = {
      cmd:    "EXECUTE 45-MIN ZONE 2 OUTPUT.",
      rat:    `AUTONOMIC STRESS DETECTED (${Math.round(telemetry.hrv)} MS HRV). PARASYMPATHETIC ACTIVATION REQUIRED. — HUBERMAN / GALPIN`,
      color:  "var(--text-main)",
      border: "var(--accent-amber)",
      level:  "warn",
    };
  } else if (telemetry.lactate > 2.0) {
    logic = {
      cmd:    "INITIATE ACTIVE RECOVERY PROTOCOL.",
      rat:    `LACTATE CLEARANCE DELAYED (${telemetry.lactate.toFixed(1)} MMOL/L). TISSUE OXYGENATION REQUIRED. — SAN MILLÁN / ATTIA`,
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
      addLog("DE-ESCALATION CONFIRMED // RETURNING TO HOMEOSTASIS", "event");
    }, 2500);
  };

  const bleColor = bleStatus === "ROCHE_LIVE" ? "var(--accent-blue)"
    : bleStatus === "SCANNING..." || bleStatus === "CONNECTING..." ? "var(--accent-amber)"
    : "var(--text-dim)";

  if (locked) {
    return (
      <>
        <style>{CSS}</style>
        <div className="auth-overlay">
          <div className="auth-title">METHUSELAH // ACCESS REQUIRED</div>
          <input
            autoFocus
            className="auth-input"
            type="password"
            value={input}
            onChange={e => { setInput(e.target.value); setAuthError(false); }}
            onKeyDown={handleKeyDown}
            placeholder="********"
          />
          <div className="auth-hint">INPUT MASTER KEY → PRESS RETURN</div>
          {authError && <div className="auth-error">⚠ ACCESS DENIED // INVALID KEY</div>}
        </div>
      </>
    );
  }

  return (
    <div className="shell">
      <div className="header">
        <div className="brand-wrap">
          <div className="brand">METHUSELAH</div>
          <div className="brand-sub">
            Biological Logic Engine // v1.0.5 // Node_01 // Oliver_BC
            {rocheDevice && ` // ${rocheDevice}`}
          </div>
        </div>
        <div className="header-right">
          <div className="header-top-row">
            <div className="live-badge" style={{ color: bleColor }}>
              <div className="blink" style={{ background: bleColor }} />
              {bleStatus === "ROCHE_LIVE" ? "ROCHE LIVE" : bleStatus === "DISCONNECTED" ? "SIMULATION" : bleStatus}
            </div>
            <button
              className={`ble-btn ${bleStatus === "ROCHE_LIVE" ? "roche" : ""}`}
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
          label="Systemic Friction (HRV)"
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
          <div className="optimal-label">// AWAITING SYSTEM DRIFT //</div>
        )}
      </div>

      <div className="sys-log">
        {logs.map((l, i) => (
          <div key={i} className="log-line">
            <span className="log-time">[{l.time}]</span>
            <span className={l.type === "roche" ? "log-roche" : ""}>{l.msg}</span>
          </div>
        ))}
      </div>
    </div>
  );
}
