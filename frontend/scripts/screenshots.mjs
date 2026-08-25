/**
 * Renders the UI to PNGs.
 *
 *   node scripts/screenshots.mjs [baseUrl]
 *
 * Doubles as the visual-regression baseline plan.md 14 calls for: the same
 * shots, committed, are what a future change gets diffed against.
 *
 * Captures each surface in light and dark, at desktop and mobile widths, and
 * once with reduced transparency so the Tier-B glass fallback is verified
 * rather than assumed.
 */

import { mkdir } from 'node:fs/promises';
import { dirname, join } from 'node:path';
import { fileURLToPath } from 'node:url';

import { chromium } from 'playwright';

const base = process.argv[2] ?? 'http://localhost:5173';
const outDir = join(dirname(fileURLToPath(import.meta.url)), '..', '..', 'screenshots');

const DESKTOP = { width: 1440, height: 1100 };
const MOBILE = { width: 390, height: 844 };

/** The seeded administrator (README). */
const ADMIN_PHONE = '+994500000001';

/** path, file, viewport, theme, accent, extra */
const SHOTS = [
  ['/', 'home-desktop-light', DESKTOP, 'light', null, {}],
  ['/', 'home-desktop-dark', DESKTOP, 'dark', null, {}],
  ['/', 'home-desktop-bronze', DESKTOP, 'light', 'bronze', {}],
  ['/', 'home-mobile-light', MOBILE, 'light', null, {}],
  ['/', 'home-mobile-dark', MOBILE, 'dark', null, {}],
  ['/dev/kitchen-sink', 'kitchen-desktop-light', DESKTOP, 'light', null, { full: true }],
  ['/dev/kitchen-sink', 'kitchen-desktop-dark', DESKTOP, 'dark', null, { full: true }],
  ['/dev/kitchen-sink', 'kitchen-desktop-bronze-dark', DESKTOP, 'dark', 'bronze', { full: true }],
  ['/dev/kitchen-sink', 'kitchen-reduced-transparency', DESKTOP, 'light', null, { reduced: true }],

  // The admin panel needs a signed-in administrator, so these carry `auth`.
  ['/admin', 'admin-dashboard-light', DESKTOP, 'light', null, { auth: ADMIN_PHONE }],
  ['/admin/products', 'admin-products-dark', DESKTOP, 'dark', null, { auth: ADMIN_PHONE }],
  [
    '/admin/products/new',
    'admin-product-form-light',
    DESKTOP,
    'light',
    null,
    { auth: ADMIN_PHONE, full: true },
  ],
  [
    '/admin/settings',
    'admin-settings-light',
    DESKTOP,
    'light',
    null,
    { auth: ADMIN_PHONE, full: true },
  ],
  ['/profile/orders', 'account-orders-light', DESKTOP, 'light', null, { auth: ADMIN_PHONE }],
  ['/admin/products', 'admin-products-mobile', MOBILE, 'light', null, { auth: ADMIN_PHONE }],
];

/**
 * Sign in through the real OTP flow.
 *
 * The refresh token is an httpOnly cookie, so completing the flow in the page
 * leaves the browser context signed in and the app's boot-time refresh picks
 * it up - no test-only login endpoint, and nothing to keep in sync with the
 * real one.
 */
async function signIn(page, phone) {
  await page.goto(base + '/', { waitUntil: 'domcontentloaded' });
  return page.evaluate(async (number) => {
    const sent = await fetch('/api/v1/auth/phone/send-otp', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ phone: number }),
    });
    if (!sent.ok) return { ok: false, reason: `send-otp ${sent.status}` };

    // The inbox is a global ring buffer; take the code issued for THIS
    // number, not whatever was sent last. Phones are masked (+99450***0001).
    const inbox = await (await fetch('/api/v1/dev/otp-inbox')).json();
    const tail = number.slice(-4);
    const code = (inbox.items ?? []).find((i) => i.phone.endsWith(tail) && !i.expired)?.code ?? '';
    if (!code) return { ok: false, reason: 'no OTP issued (send limit)' };
    const verified = await fetch('/api/v1/auth/phone/verify-otp', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ phone: number, code }),
    });
    return { ok: verified.ok, reason: `verify-otp ${verified.status}` };
  }, phone);
}

/** Cached admin session, populated by the first shot that needs one. */
let adminState = null;

async function main() {
  await mkdir(outDir, { recursive: true });

  const browser = await chromium.launch();
  let captured = 0;

  for (const [path, name, viewport, theme, accent, extra] of SHOTS) {
    const context = await browser.newContext({
      viewport,
      deviceScaleFactor: 2,
      colorScheme: theme,
      // Reuse the admin session across shots. Signing in per shot would burn
      // through the OTP send limit (3 per number per 15 minutes, plan.md 9.4)
      // and every capture after the third would silently show the signed-out
      // guard instead of the panel.
      ...(extra.auth && adminState ? { storageState: adminState } : {}),
      // Verifies the Tier-B fallback renders, instead of trusting that it does.
      reducedMotion: extra.reduced ? 'reduce' : 'no-preference',
      ...(extra.reduced ? { forcedColors: 'none' } : {}),
    });

    const page = await context.newPage();

    // Apply theme/accent before first paint, exactly as index.html does.
    await page.addInitScript(
      ({ t, a }) => {
        try {
          localStorage.setItem('ui:theme', t);
          if (a) localStorage.setItem('ui:accent', a);
          else localStorage.removeItem('ui:accent');
        } catch {
          /* ignore */
        }
      },
      { t: theme, a: accent },
    );

    if (extra.auth && !adminState) {
      const result = await signIn(page, extra.auth);
      if (!result.ok) {
        // Capturing the signed-out guard and calling it an admin screenshot
        // is worse than capturing nothing. The usual cause is the OTP send
        // limit - three per number per fifteen minutes (plan.md 9.4) - after
        // several runs in a row.
        console.warn(`  skip ${name} (sign-in failed: ${result.reason})`);
        await context.close();
        continue;
      }
    }

    // domcontentloaded, not networkidle: the catalogue hotlinks remote
    // photography, so "no connections for 500 ms" may never hold and the
    // capture times out on a slow link. The font/image settle below is what
    // actually guarantees a fully-rendered frame.
    const response = await page.goto(base + path, {
      waitUntil: 'domcontentloaded',
      timeout: 30_000,
    });
    await page.waitForSelector('#main', { timeout: 20_000 }).catch(() => null);

    // #main exists as soon as the shell mounts - before the data arrives.
    // Waiting only for it captured every page with empty product tiles, which
    // is how a whole run of screenshots came out looking like a broken shop.
    // Wait for whichever content block this route actually renders.
    await page
      .waitForSelector(
        '.product-card, .detail__info, .contact-card, .admin__form, .stat, .table, .request-card, .ks-section, .empty-state',
        { timeout: 20_000 },
      )
      .catch(() => null);
    if (!response || response.status() >= 400) {
      console.warn(`  skip ${name} (HTTP ${response?.status() ?? 'no response'})`);
      await context.close();
      continue;
    }

    if (extra.reduced) {
      await page.evaluate(() => {
        document.documentElement.dataset.glass = 'reduced';
      });
    }

    // Below-the-fold images are loading="lazy" and content-visibility:auto, so
    // a fullPage capture would otherwise show empty card slots. Scroll the
    // whole page to trigger them, then return to the top.
    if (extra.full) {
      await page.evaluate(async () => {
        const step = window.innerHeight;
        for (let y = 0; y < document.body.scrollHeight; y += step) {
          window.scrollTo(0, y);
          await new Promise((resolve) => setTimeout(resolve, 90));
        }
        window.scrollTo(0, 0);
      });
      // Best-effort settle: hotlinked photography may never leave the
      // network idle, so this is bounded and its failure is not fatal - the
      // image-decode wait below is what actually guarantees the frame.
      await page.waitForLoadState('networkidle', { timeout: 8000 }).catch(() => null);
    }

    // Let webfonts and images settle so nothing renders half-ready.
    //
    // Waits on the LOAD event rather than `img.decode()`: decode rejects for
    // some cross-origin images, and a rejection that is caught and ignored is
    // indistinguishable from a finished image - which is how a run of
    // screenshots came out with every product photo blank.
    // Every image the page has decided to load has finished, one way or the
    // other. Bounded and non-fatal: one stalled remote photograph must not
    // take the whole run down.
    await page
      .waitForFunction(() => [...document.images].every((img) => img.complete), null, {
        timeout: 15_000,
      })
      .catch(() => null);
    await page.evaluate(() => document.fonts.ready);
    await page.waitForTimeout(400);

    await page.screenshot({
      path: join(outDir, `${name}.png`),
      fullPage: Boolean(extra.full),
    });
    // Re-capture the session AFTER the shot, not before.
    //
    // Refresh tokens rotate on every use and presenting a used one revokes
    // the whole family (plan.md 6.3) - so replaying a saved state signs the
    // next context straight out. Saving the state the page has just finished
    // with hands the next context the fresh, unused token instead.
    if (extra.auth) adminState = await context.storageState();

    console.log(`  ${name}.png`);
    captured += 1;
    await context.close();
  }

  await browser.close();
  console.log(`\n✓ ${captured} screenshots written to screenshots/`);
}

main().catch((error) => {
  console.error('screenshots failed:', error);
  process.exit(1);
});
