// Shared helper for endpoints that serve or accept real personal health
// data and must only be reachable by someone who already knows the
// dashboard password -- not a second credential, reusing DASHBOARD_ACCESS_KEY
// (the same one api/auth.js checks) so the browser only ever has to remember
// one secret. The underscore prefix keeps Vercel from treating this file as
// its own route -- it's a shared module, not an endpoint.
//
// 2026-08-12: added after finding gen3-bridge.js's GET, and glucose.js /
// vector-history.js's GET *and* POST, had no protection at all -- the
// DASHBOARD_ACCESS_KEY login only ever gated the React UI, not the actual
// data underneath it. Anyone with the URL could read (and, for two of the
// three, write) real personal health data without ever seeing the login
// screen.
//
// Does NOT gate api/gen3-bridge.js's own POST path -- that path is written
// by the Python pipeline (a machine, not a browser), authenticated by its
// own separate GEN3_BRIDGE_WRITE_SECRET. Different actor, different
// credential, intentionally untouched by this helper.

export function requireDashboardKey(req, res) {
  const real = process.env.DASHBOARD_ACCESS_KEY;
  const provided = req.headers["x-dashboard-key"];
  if (!real || !provided || provided !== real) {
    res.status(401).json({ error: "Unauthorized" });
    return false;
  }
  return true;
}
