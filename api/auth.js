// Server-side check for the dashboard's "ACCESS REQUIRED" gate.
//
// Previously the whole check was client-side (`if (input === MASTER_KEY)`
// with MASTER_KEY hardcoded in App.js) -- that value ships inside the public
// JS bundle every visitor's browser downloads, so it was never actually
// secret, just a speed bump. This moves the real comparison here, where the
// secret lives only in a Vercel env var and is never sent to the client.
//
// Requires one env var set in the Vercel project (Settings -> Environment
// Variables), not committed anywhere: DASHBOARD_ACCESS_KEY.

export default async function handler(req, res) {
  if (req.method !== "POST") {
    return res.status(405).json({ error: "Method not allowed" });
  }

  const real = process.env.DASHBOARD_ACCESS_KEY;
  if (!real) {
    return res.status(500).json({ error: "DASHBOARD_ACCESS_KEY not configured" });
  }

  const { key } = req.body || {};
  if (!key || key !== real) {
    return res.status(401).json({ error: "Unauthorized" });
  }

  return res.status(200).json({ ok: true });
}
