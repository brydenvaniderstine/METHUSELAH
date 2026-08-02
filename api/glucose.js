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
// No write-secret here (unlike gen3-bridge.js's GEN3_BRIDGE_WRITE_SECRET):
// that secret protects a server-side script's write path, which can keep an
// env var genuinely private. This value is written directly from the
// browser, where any embedded "secret" would be visible in the page's own
// JS/network traffic anyway -- so it offers the same protection level as
// the already-unauthenticated GET on gen3-bridge.js, not less. Value is
// still range-validated server-side (0.5-30 mmol/L) so a malformed/garbage
// POST can't corrupt what's stored.

const KEY = "manual_glucose";

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
