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

import crypto from "crypto";

// Plain `===` short-circuits on the first mismatched byte, so how long the
// comparison takes leaks how many leading characters of a guess were
// correct -- a timing side-channel against DASHBOARD_ACCESS_KEY. Pad both
// sides to the same length before the constant-time compare so a wrong
// length can never return early either; timingSafeEqual itself throws on
// mismatched buffer lengths rather than just returning false.
export function timingSafeEqualStr(a, b) {
  const bufA = Buffer.from(String(a ?? ""));
  const bufB = Buffer.from(String(b ?? ""));
  const len = Math.max(bufA.length, bufB.length, 1);
  const paddedA = Buffer.alloc(len);
  const paddedB = Buffer.alloc(len);
  bufA.copy(paddedA);
  bufB.copy(paddedB);
  // Compute both before combining -- `lengthsMatch && timingSafeEqual(...)`
  // would skip the crypto call entirely on a length mismatch, leaking length
  // through timing the same way the `===` this replaces did.
  const paddedEqual = crypto.timingSafeEqual(paddedA, paddedB);
  const lengthsMatch = bufA.length === bufB.length;
  return paddedEqual && lengthsMatch;
}

export function requireDashboardKey(req, res) {
  const real = process.env.DASHBOARD_ACCESS_KEY;
  const provided = req.headers["x-dashboard-key"];
  if (!real || !provided || !timingSafeEqualStr(provided, real)) {
    res.status(401).json({ error: "Unauthorized" });
    return false;
  }
  return true;
}
