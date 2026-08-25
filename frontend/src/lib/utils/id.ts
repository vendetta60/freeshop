/**
 * A random UUID, in every context the app actually runs in.
 *
 * `crypto.randomUUID()` exists only in a **secure context** — HTTPS, or
 * `localhost`. Serve the dev server on a LAN address so a colleague can open
 * it from another machine and the whole cart page throws
 * `crypto.randomUUID is not a function`, because the idempotency key for the
 * order request is generated there. Found exactly that way, by running the
 * interaction suite against `http://172.22.111.13:5173`.
 *
 * `crypto.getRandomValues` carries no such restriction, so the fallback is
 * still cryptographically random — not `Math.random()` dressed up as a UUID.
 */
export function randomId(): string {
  if (typeof crypto.randomUUID === 'function') return crypto.randomUUID();

  const bytes = crypto.getRandomValues(new Uint8Array(16));
  // RFC 4122 §4.4: version 4, variant 10xx.
  bytes[6] = (bytes[6]! & 0x0f) | 0x40;
  bytes[8] = (bytes[8]! & 0x3f) | 0x80;

  const hex = [...bytes].map((b) => b.toString(16).padStart(2, '0')).join('');
  return `${hex.slice(0, 8)}-${hex.slice(8, 12)}-${hex.slice(12, 16)}-${hex.slice(16, 20)}-${hex.slice(20)}`;
}
