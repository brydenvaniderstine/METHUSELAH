// Serves the latest manually-entered glucose reading across devices, the
// same way api/gen3-bridge.js serves ring data -- reads/writes a Vercel KV
// store instead of relying on browser localStorage, which never leaves the
// device it was written on (confirmed 2026-08-02: a reading entered on a
// laptop's browser never appeared on the same dashboard loaded on a phone,
// because localStorage is per-browser, not per-user).
//
// Separate KV key from gen3_latest (not merged into that bridge object) so
// the Python pipeline's full-object bridge pushes (which know nothing about
// glucose) can never silently wipe this out on their next write -- the two
// keys are independently owned and never overwrite each other.
//
// 2026-08-12, correcting the reasoning above: it conflated a STATIC secret
// baked into the bundle for every visitor (genuinely pointless -- that's
// exactly the MASTER_KEY mistake fixed elsewhere this session) with a
// session credential a browser only holds *after* proving it knows the real
// password. Those are not the same thing, and this endpoint had neither --
// GET and POST were both fully open, no protection at all beyond the value
// range-check below. Now requires DASHBOARD_ACCESS_KEY (same one the login
// screen checks) via requireDashboardKey() -- see api/_authCheck.js.

import { requireDashboardKey } from "./_authCheck.js";

const KEY = "manual_glucose";

export default async function handler(req, res) {
  const kvUrl = process.env.KV_REST_API_URL;
  const kvToken = process.env.KV_REST_API_TOKEN;
  if (!kvUrl || !kvToken) {
    return res.status(500).json({ error: "KV store not configured (KV_REST_API_URL/KV_REST_API_TOKEN missing)" });
  }
  if (!requireDashboardKey(req, res)) return;

  if (req.method === "GET") {
    try {
      const kvRes = await fetch(`${kvUrl}/get/${KEY}`, {
        headers: { Authorization: `Bearer ${kvToken}` },
      });
      if (!kvRes.ok) return res.status(502).json({ error: `KV read failed: ${kvRes.status}` });
      const { result } = await kvRes.json();
      if (!result) return res.status(404).json({ error: "No glucose reading available yet" });
      return res.status(200).json(JSON.parse(result));
    } catch (err) {
      return res.status(500).json({ error: err.message });
    }
  }

  if (req.method === "POST") {
    const body = req.body;
    const value = body && Number(body.value);
    const timestamp = body && body.timestamp;
    if (!value || !isFinite(value) || value <= 0.5 || value >= 30 || !timestamp) {
      return res.status(400).json({ error: "Invalid glucose payload (expected { value: number in (0.5, 30), timestamp: ISO string })" });
    }
    try {
      const kvRes = await fetch(`${kvUrl}/set/${KEY}`, {
        method: "POST",
        headers: { Authorization: `Bearer ${kvToken}` },
        body: JSON.stringify({ value, timestamp }),
      });
      if (!kvRes.ok) return res.status(502).json({ error: `KV write failed: ${kvRes.status}` });
      return res.status(200).json({ ok: true });
    } catch (err) {
      return res.status(500).json({ error: err.message });
    }
  }

  return res.status(405).json({ error: "Method not allowed" });
}
