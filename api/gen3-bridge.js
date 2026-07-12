// Serves the latest Gen3 BLE bridge snapshot without ever committing it to
// git — reads/writes a Vercel KV store (Upstash-compatible REST API) instead
// of a static file, so real biometric data never lands in the public repo.
//
// Requires two env vars set in the Vercel project (Settings -> Environment
// Variables), not committed anywhere:
//   KV_REST_API_URL, KV_REST_API_TOKEN  — auto-injected once a KV store is
//     created and linked to this project in the Vercel dashboard.
//   GEN3_BRIDGE_WRITE_SECRET — a secret you choose, so only the pull script
//     (which sends it back as a header) can write here. Anyone can still GET
//     this data unauthenticated, same as the static file it replaces was.
//
// NOT YET LIVE-TESTED — written against the documented Upstash REST wire
// format (POST {url}/set/{key} with the value as the raw body; GET
// {url}/get/{key} returns { result: <stringified value> }), but there is no
// KV store provisioned yet to verify against. Smoke-test both GET and POST
// once the store exists, before relying on this.

const KEY = "gen3_latest";

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
      if (!result) return res.status(404).json({ error: "No Gen3 bridge data available yet" });
      return res.status(200).json(JSON.parse(result));
    } catch (err) {
      return res.status(500).json({ error: err.message });
    }
  }

  if (req.method === "POST") {
    const secret = req.headers["x-write-secret"];
    if (!secret || secret !== process.env.GEN3_BRIDGE_WRITE_SECRET) {
      return res.status(401).json({ error: "Unauthorized" });
    }
    const body = req.body;
    if (!body || typeof body !== "object" || body.source !== "gen3_ble") {
      return res.status(400).json({ error: "Invalid gen3 bridge payload (expected source: 'gen3_ble')" });
    }
    try {
      const kvRes = await fetch(`${kvUrl}/set/${KEY}`, {
        method: "POST",
        headers: { Authorization: `Bearer ${kvToken}` },
        body: JSON.stringify(body),
      });
      if (!kvRes.ok) return res.status(502).json({ error: `KV write failed: ${kvRes.status}` });
      return res.status(200).json({ ok: true });
    } catch (err) {
      return res.status(500).json({ error: err.message });
    }
  }

  return res.status(405).json({ error: "Method not allowed" });
}
