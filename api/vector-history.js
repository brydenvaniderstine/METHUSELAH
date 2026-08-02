// Shared, cross-device 7-day history for the vectors whose CURRENT value
// already syncs via api/gen3-bridge.js but whose ROLLING HISTORY (used for
// the "7d avg" / trend shown on each tile) did not -- confirmed 2026-08-02:
// a laptop and a phone loading the same live HRV/RHR/Sleep-Duration number
// showed different 7-day averages and trends, because each browser was
// building its own separate history purely from localStorage.
//
// Stored as one object keyed by calendar date ("YYYY-MM-DD"), so multiple
// devices independently recording "today's" value is idempotent (same-day
// writes just overwrite that date's entry, never duplicate it) rather than
// needing any distinct-value dedup logic. Separate KV key from both
// gen3_latest and manual_glucose so none of the three can ever clobber
// another.

const KEY = "vector_history";
const MAX_DAYS_KEPT = 10; // only ever need the last 7 for the UI; a little headroom

const FIELDS = ["hrv", "rhr", "sleepDurationHrs", "spo2", "steps"];

export default async function handler(req, res) {
  const kvUrl = process.env.KV_REST_API_URL;
  const kvToken = process.env.KV_REST_API_TOKEN;
  if (!kvUrl || !kvToken) {
    return res.status(500).json({ error: "KV store not configured (KV_REST_API_URL/KV_REST_API_TOKEN missing)" });
  }

  if (req.method === "GET") {
    try {
      const kvRes = await fetch(`${kvUrl}/get/${KEY}`, {
        headers: { Authorization: `Bearer ${kvToken}` },
      });
      if (!kvRes.ok) return res.status(502).json({ error: `KV read failed: ${kvRes.status}` });
      const { result } = await kvRes.json();
      return res.status(200).json(result ? JSON.parse(result) : {});
    } catch (err) {
      return res.status(500).json({ error: err.message });
    }
  }

  if (req.method === "POST") {
    const body = req.body;
    const date = body && body.date;
    if (!date || !/^\d{4}-\d{2}-\d{2}$/.test(date)) {
      return res.status(400).json({ error: "Invalid payload (expected { date: 'YYYY-MM-DD', ...vector fields })" });
    }
    const entry = {};
    for (const f of FIELDS) {
      const v = Number(body[f]);
      if (body[f] != null && isFinite(v)) entry[f] = v;
    }
    if (Object.keys(entry).length === 0) {
      return res.status(400).json({ error: "No valid vector fields in payload" });
    }
    try {
      const getRes = await fetch(`${kvUrl}/get/${KEY}`, {
        headers: { Authorization: `Bearer ${kvToken}` },
      });
      const { result } = getRes.ok ? await getRes.json() : { result: null };
      const history = result ? JSON.parse(result) : {};
      history[date] = { ...(history[date] || {}), ...entry };

      // Trim to the most recent MAX_DAYS_KEPT dates.
      const trimmed = {};
      for (const d of Object.keys(history).sort().slice(-MAX_DAYS_KEPT)) {
        trimmed[d] = history[d];
      }

      const setRes = await fetch(`${kvUrl}/set/${KEY}`, {
        method: "POST",
        headers: { Authorization: `Bearer ${kvToken}` },
        body: JSON.stringify(trimmed),
      });
      if (!setRes.ok) return res.status(502).json({ error: `KV write failed: ${setRes.status}` });
      return res.status(200).json({ ok: true });
    } catch (err) {
      return res.status(500).json({ error: err.message });
    }
  }

  return res.status(405).json({ error: "Method not allowed" });
}
