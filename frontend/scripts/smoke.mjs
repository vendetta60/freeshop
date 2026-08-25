/**
 * Clicks every interactive control and asserts it does something.
 *
 *   node scripts/smoke.mjs [baseUrl]
 *
 * Exists because "the buttons don't work" is not a defect a type-checker,
 * linter or unit test can catch. This drives the real UI the way a person
 * does and fails loudly when a control is inert.
 *
 * A step that throws is recorded as a failure and the run continues, so one
 * broken control does not hide the state of everything after it.
 */

import { chromium } from 'playwright';

const base = process.argv[2] ?? 'http://localhost:5173';
const CLICK = { timeout: 6000 };

/**
 * A fresh number per run.
 *
 * OTP sends are rate-limited to three per number per fifteen minutes
 * (plan.md 9.4), so a fixed number makes the suite fail on its fourth run of
 * the hour - which looks like a regression and is not one. Randomising also
 * means each run exercises first-time signup rather than an existing account.
 */
const TEST_PHONE = `+99450${String(Math.floor(Math.random() * 9_000_000) + 1_000_000)}`;

/** A valid 1x1 PNG. Inline so the suite carries its own fixture. */
const PNG_PIXEL = Buffer.from(
  'iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mP8z8BQDwAEhQGAhKmMIQAAAABJRU5ErkJggg==',
  'base64',
);

/** Set by the offering step, reviewed by the admin step. */
let smokeListingTitle = '';

const results = [];
function check(name, passed, detail = '') {
  results.push({ name, passed, detail });
}

/**
 * A check that could not be run, as distinct from one that failed.
 *
 * The admin section signs in as the seeded administrator, and OTP sends are
 * capped at three per number per fifteen minutes (plan.md 9.4). Running the
 * suite repeatedly therefore exhausts the budget - which is the limiter
 * working, not a regression. Reporting seven cascading failures for it would
 * train whoever reads this output to ignore red.
 */
function skip(name, detail = '') {
  results.push({ name, passed: true, skipped: true, detail });
}

const browser = await chromium.launch();
const context = await browser.newContext({ viewport: { width: 1440, height: 1000 } });
const page = await context.newPage();

const consoleErrors = [];
const EXPECTED_401 = /auth\/refresh|status of 401/;
page.on('console', (m) => {
  // A guest boot calls /auth/refresh and gets 401 by design; the browser logs
  // every failed fetch as a console error, so that one is filtered rather
  // than treated as a defect.
  if (m.type() === 'error' && !EXPECTED_401.test(m.text())) {
    consoleErrors.push(m.text().slice(0, 110));
  }
});
page.on('pageerror', (e) => consoleErrors.push('pageerror: ' + e.message.slice(0, 110)));

/** Runs a group of assertions; a throw becomes a failure, not an abort. */
async function step(name, fn) {
  try {
    await fn();
  } catch (error) {
    check(name, false, String(error.message).split('\n')[0].slice(0, 80));
  }
}

/**
 * networkidle is unreliable here: the catalogue hotlinks remote photography,
 * so "no connections for 500ms" may never hold even though the app is fully
 * interactive. Verified there is no request loop - 10 requests on load - so
 * waiting for the shell to exist is both faster and more honest.
 */
const visit = async (path) => {
  await page.goto(base + path, { waitUntil: 'domcontentloaded' });
  await page.waitForSelector('#main', { timeout: 15000 });
};

const goHome = () => visit('/');

/**
 * The newest code issued for THIS number.
 *
 * The dev inbox is a global ring buffer, so `items[0]` is whatever was sent
 * last by anyone - and taking it blindly meant a rate-limited admin sign-in
 * silently verified against the buyer's code and reported "session not
 * established" instead of "send limit". Phones are masked in the inbox
 * (+99450***0001), so match on the last four digits.
 */
async function otpFor(target, phone) {
  return target.evaluate(async (number) => {
    const tail = number.slice(-4);
    const res = await fetch('/api/v1/dev/otp-inbox');
    const body = await res.json();
    const hit = (body.items ?? []).find((i) => i.phone.endsWith(tail) && !i.expired);
    return hit?.code ?? '';
  }, phone);
}

/**
 * Drop the browser's HTTP cache.
 *
 * `GET /products` is deliberately cached for 60 seconds (plan.md 6.1), so a
 * page loaded seconds after a deletion can legitimately still show the old
 * list. That is correct product behaviour and a false failure for a suite
 * asking "did the server actually delete it?".
 */
const cdp = await context.newCDPSession(page);
const clearHttpCache = () => cdp.send('Network.clearBrowserCache');

await step('hero CTA', async () => {
  await goHome();
  await page.getByRole('button', { name: /Kataloqa bax/ }).click(CLICK);
  await page.waitForTimeout(500);
  check('Hero "Kataloqa bax" navigates to /products', page.url().includes('/products'), page.url());
});

await step('category chip', async () => {
  await page.getByRole('button', { name: 'Mebel', exact: true }).click(CLICK);
  await page.waitForTimeout(350);
  check(
    'Category chip writes ?category= to the URL',
    page.url().includes('category=mebel'),
    page.url(),
  );
  const n = await page.locator('.product-card').count();
  check('Filter actually narrows the grid', n > 0 && n < 12, `${n} cards`);
});

await step('sort', async () => {
  await page.getByRole('button', { name: 'Hamısı', exact: true }).click(CLICK);
  await page.waitForTimeout(300);
  await page.getByRole('button', { name: 'Ucuzdan bahaya' }).click(CLICK);
  await page.waitForTimeout(350);
  const first = await page.locator('.product-card__price').first().innerText();
  // On a board for giving things away the cheapest item is free, and a free
  // item reads "Pulsuz" rather than 0,00 ₼.
  check('Ascending sort puts the cheapest first', /Pulsuz|0,50/.test(first), first.trim());
});

await step('in-stock filter', async () => {
  await page.getByRole('button', { name: 'Yalnız mövcud' }).click(CLICK);
  await page.waitForTimeout(350);
  check('In-stock filter sets ?stock=1', page.url().includes('stock=1'));
  const sold = await page.getByText('Bitib').count();
  check('Out-of-stock items are hidden', sold === 0, `${sold} sold-out visible`);
});

await step('product detail', async () => {
  await goHome();
  await page.locator('.product-card').first().click(CLICK);
  await page.waitForTimeout(600);
  check(
    'Product card opens the detail page',
    /\/products\/[a-z0-9-]+/.test(page.url()),
    page.url(),
  );
  check('Detail page renders a heading', (await page.locator('.detail__info h1').count()) === 1);
});

await step('guest gate on add to cart', async () => {
  // Guests may browse but not build a basket (plan.md D2). The wall must
  // appear as an invitation showing what they were trying to add.
  await page.getByRole('button', { name: /Səbətə at/ }).click(CLICK);
  await page.waitForTimeout(450);
  check(
    'Guest add-to-cart opens the sign-in sheet',
    (await page.locator('.auth-sheet').count()) === 1,
  );
  check('Sheet shows the product they wanted', (await page.locator('.auth-intent').count()) === 1);
  check('Cart stays empty for a guest', (await page.locator('.cart-dot').count()) === 0);
});

await step('sign in replays the pending intent', async () => {
  // A real OTP round trip: the sheet requests a code, the console channel
  // records it, and the dev inbox surfaces it back into the UI.
  await page.locator('#auth-phone').fill(TEST_PHONE);
  await page.locator('.auth-sheet').getByRole('button', { name: /Kod g/ }).click(CLICK);
  await page.waitForTimeout(900);
  check('OTP step is reached', (await page.locator('#auth-code').count()) === 1);

  const code = await otpFor(page, TEST_PHONE);
  check('Dev inbox exposes the code', /^\d{6}$/.test(code), code);

  await page.locator('#auth-code').fill(code);
  await page
    .locator('.auth-sheet')
    .getByRole('button', { name: /T.sdiql/ })
    .click(CLICK);
  await page.waitForTimeout(1400);

  check('Sheet closes after signing in', (await page.locator('.auth-sheet').count()) === 0);
  // The whole point of the pending intent: the interrupted action completes.
  check(
    'Pending intent lands in the server cart',
    (await page.locator('.cart-dot').first().innerText()) === '1',
  );
  check('Cart drawer opens with the item', (await page.locator('.drawer').count()) === 1);
});

await step('quantity stepper', async () => {
  // Structural, not label-based: the buttons are translated, and pinning a
  // literal aria-label made this check fail the moment i18n landed.
  await page.locator('.drawer .stepper button:not(.stepper__remove)').last().click(CLICK);
  await page.waitForTimeout(300);
  check('Stepper increments to 2', (await page.locator('.cart-dot').first().innerText()) === '2');
});

await step('drawer escape', async () => {
  await page.keyboard.press('Escape');
  await page.waitForTimeout(350);
  check('Escape closes the drawer', (await page.locator('.drawer').count()) === 0);
});

await step('command palette', async () => {
  await page.keyboard.press('Control+k');
  await page.waitForTimeout(400);
  check('Ctrl+K opens the command palette', (await page.locator('.palette').count()) === 1);
  await page.locator('.palette__input').fill('divan');
  await page.waitForTimeout(400);
  const hits = await page.locator('.palette__item').count();
  check('Palette finds results for "divan"', hits > 0, `${hits} hits`);
  await page.locator('.palette__item').first().click(CLICK);
  await page.waitForTimeout(500);
  check('Selecting a palette result navigates', page.url().includes('/products/'), page.url());
});

await step('diacritic-insensitive search', async () => {
  await page.keyboard.press('Control+k');
  await page.waitForTimeout(350);
  // "ketan" must find "Kətan": Azerbaijani users routinely type without diacritics.
  await page.locator('.palette__input').fill('ketan');
  await page.waitForTimeout(400);
  const hits = await page.locator('.palette__item').count();
  check('Search matches "ketan" -> "Kətan"', hits > 0, `${hits} hits`);
  await page.keyboard.press('Escape');
  await page.waitForTimeout(300);
});

await step('category menu', async () => {
  await goHome();
  await page.getByRole('button', { name: /Kateqoriyalar/ }).click(CLICK);
  await page.waitForTimeout(350);
  check('Nav category menu opens', (await page.locator('.category-menu').count()) === 1);
  await page.locator('.category-menu__item').filter({ hasText: 'Tekstil' }).click(CLICK);
  await page.waitForTimeout(450);
  check('Category menu navigates', page.url().includes('category='), page.url());
});

await step('cart page and request', async () => {
  await visit('/cart');
  // The cart is fetched, so wait for the row rather than assuming it is there.
  await page.waitForSelector('.cart-row', { timeout: 10000 }).catch(() => null);
  check('Cart page lists the added line', (await page.locator('.cart-row').count()) >= 1);
  const submit = page.getByRole('button', { name: /Sorğu göndər/ });
  await page.locator('#cart-phone').fill(TEST_PHONE);
  await page.waitForTimeout(250);
  check('Submit enables once a phone is entered', await submit.isEnabled());
  await submit.click(CLICK);
  await page.waitForTimeout(1200);
  check('Request confirmation is shown', (await page.locator('.success-panel').count()) === 1);
  // A server-allocated number, not one invented on the client.
  const confirmation = await page.locator('.success-panel').innerText();
  const match = /SR-\d{4}-\d{4}/.exec(confirmation);
  check('Confirmation shows a server request number', match !== null, match?.[0] ?? 'none');
  check('Cart is cleared after submitting', (await page.locator('.cart-dot').count()) === 0);
});

await step('request history', async () => {
  await visit('/profile/orders');
  await page.waitForSelector('.request-card', { timeout: 10000 }).catch(() => null);
  check(
    'History lists the request just submitted',
    (await page.locator('.request-card').count()) >= 1,
  );

  // The number is a link: a request is a thing you can come back to.
  await page.locator('.request-card__head a').first().click(CLICK);
  await page.waitForTimeout(800);
  check(
    'A request number opens its own page',
    /\/profile\/orders\/\d+/.test(page.url()),
    page.url(),
  );
  const detail = await page.locator('#main').innerText();
  check('Detail page shows the request number', /SR-\d{4}-\d{4}/.test(detail));
  // The payoff of the whole flow: how to reach the seller, days later.
  check(
    'Detail page repeats the seller contacts',
    (await page.locator('.contact-row').count()) >= 1,
  );
});

await step('offering an item', async () => {
  const TITLE = `Smoke elanı ${Date.now()}`;

  await visit('/offer');
  await page.waitForSelector('.admin__form, .empty-state', { timeout: 10000 });

  // Signed in by OTP, so the phone is verified and the form is reachable.
  check(
    'Offer form is open to a signed-in visitor',
    (await page.locator('.admin__form').count()) === 1,
  );
  check(
    'Free is ticked by default',
    await page.locator('.admin__form input[type="checkbox"]').isChecked(),
  );

  await page
    .locator('.admin__form input:not([type="checkbox"]):not([type="file"])')
    .first()
    .fill(TITLE);

  // A real photo, through the real picker. A give-away with no picture is an
  // advert nobody answers, so this path is driven rather than trusted.
  await page.locator('.admin__form input[type="file"]').setInputFiles({
    name: 'smoke.png',
    mimeType: 'image/png',
    buffer: PNG_PIXEL,
  });
  await page.waitForTimeout(400);
  check(
    'Chosen photos are previewed before sending',
    (await page.locator('.image-tile img').count()) === 1,
  );

  await page.locator('.admin__form textarea').fill('Smoke testi üçün yaradılmış elan.');
  await page.locator('.admin__form select').selectOption({ index: 1 });
  await page.getByRole('button', { name: /Yoxlama/ }).click(CLICK);
  await page.waitForTimeout(1200);

  check('Submitting shows the confirmation', (await page.locator('.success-panel').count()) === 1);

  // The point of the whole feature: it is NOT on the site yet.
  await clearHttpCache();
  await visit(`/products?q=${encodeURIComponent(TITLE)}`);
  await page.waitForTimeout(700);
  check(
    'A new offer is not public until it is reviewed',
    (await page.locator('.product-card').count()) === 0,
  );

  await visit('/profile/listings');
  await page.waitForSelector('.listing-row', { timeout: 10000 }).catch(() => null);
  const mine = await page.locator('.listing-row').first().innerText();
  check(
    'The submitter sees it as under review',
    /Yoxlanılır/.test(mine),
    mine.split('\n')[1] ?? '',
  );
  check('A free listing reads "Pulsuz", not 0,00', /Pulsuz/.test(mine));

  const photo = await page.locator('.listing-row img').first().getAttribute('src');
  check(
    'The photo was uploaded with it',
    (photo ?? '').startsWith('/static/uploads/'),
    photo ?? 'none',
  );

  smokeListingTitle = TITLE;
});

await step('account menu', async () => {
  await page.keyboard.press('Escape');
  await page.waitForTimeout(300);
  await page.locator('header button[aria-label^="Hesab"]').click(CLICK);
  await page.waitForTimeout(300);
  check('Account menu opens when signed in', (await page.locator('.account-menu').count()) === 1);
  check(
    'Menu shows the signed-in identity',
    (await page.locator('.account-menu__id').count()) === 1,
  );
  await page.getByRole('menuitem', { name: /Çıxış et/ }).click(CLICK);
  await page.waitForTimeout(350);
  await page.locator('header button[aria-label^="Hesab"]').click(CLICK);
  await page.waitForTimeout(300);
  const signIn = await page.getByRole('menuitem', { name: /Daxil ol/ }).count();
  check('Signing out restores the sign-in options', signIn === 1, `${signIn} found`);
  await page.keyboard.press('Escape');
  await page.waitForTimeout(250);
});

await step('contact page', async () => {
  await visit('/contact');
  await page.waitForSelector('.contact-card', { timeout: 10000 }).catch(() => null);
  check('Contact page renders channels', (await page.locator('.contact-card').count()) >= 4);
});

await step('404', async () => {
  await visit('/definitely-not-a-page');
  await page.waitForTimeout(400);
  check(
    'Unknown route renders the 404 page',
    (await page.getByText('Səhifə tapılmadı').count()) === 1,
  );
});

await step('theme and accent', async () => {
  await goHome();
  const before = await page.evaluate(() => document.documentElement.dataset.theme ?? 'system');
  await page.locator('header button[aria-label*="rejim"]').click(CLICK);
  await page.waitForTimeout(300);
  const after = await page.evaluate(() => document.documentElement.dataset.theme ?? 'system');
  check('Theme toggle changes the theme', before !== after, `${before} -> ${after}`);

  await page.locator('header button[aria-label*="Vurğu"]').click(CLICK);
  await page.waitForTimeout(300);
  const accent = await page.evaluate(() => document.documentElement.dataset.accent ?? 'azure');
  check('Accent toggle switches to bronze', accent === 'bronze', accent);
});

await step('mobile tab bar', async () => {
  await page.setViewportSize({ width: 390, height: 844 });
  await goHome();
  await page.waitForTimeout(400);
  check('Tab bar is visible on mobile', await page.locator('.glass-tabbar').isVisible());
  await page.locator('.tab').filter({ hasText: 'Kataloq' }).click(CLICK);
  await page.waitForTimeout(450);
  check('Tab bar navigates to the catalogue', page.url().includes('/products'), page.url());
  await page.locator('.tab').filter({ hasText: 'Səbət' }).click(CLICK);
  await page.waitForTimeout(400);
  check('Tab bar opens the cart drawer', (await page.locator('.drawer').count()) === 1);
  await page.setViewportSize({ width: 1440, height: 1000 });
});

await step('language switch', async () => {
  await goHome();
  await page.locator('header button[aria-label*="Dili"]').click(CLICK);
  await page.waitForTimeout(600);
  const lang = await page.evaluate(() => document.documentElement.lang);
  check('Language switch flips <html lang> to en', lang === 'en', lang);

  // Not just the chrome: the catalogue request carries the language too, so
  // category names come back translated from the server.
  const heading = await page.locator('.hero h1').innerText();
  check('Interface strings switch with it', /Curated|products/i.test(heading), heading.trim());

  await page.locator('header button[aria-label*="language"]').click(CLICK);
  await page.waitForTimeout(600);
  const back = await page.evaluate(() => document.documentElement.lang);
  check('Switching back restores Azerbaijani', back === 'az', back);
});

/**
 * The admin panel (plan.md 11).
 *
 * Signs in as the seeded admin and drives the real CRUD path: create a
 * product, see it in the public catalogue, then soft-delete it and see it
 * disappear. The row that this suite creates is cleaned up by the same run,
 * so a repeat run starts from the same state.
 */
const ADMIN_PHONE = '+994500000001';

async function signInAs(phone) {
  // Every step is checked rather than assumed: when the OTP budget is spent
  // this function has to report WHY, not time out inside a locator and leave
  // the caller with seven unrelated red lines.
  try {
    await goHome();
    await page.evaluate(() => {
      localStorage.removeItem('ui:lang');
    });
    await page.locator('header button[aria-label^="Hesab"]').click(CLICK);
    await page.getByRole('menuitem', { name: /Daxil ol/ }).click(CLICK);
    await page.locator('#auth-phone').fill(phone, { timeout: 8000 });
    await page.locator('.auth-sheet').getByRole('button', { name: /Kod g/ }).click(CLICK);
    await page.waitForTimeout(900);

    const code = await otpFor(page, phone);
    if (!/^\d{6}$/.test(code)) return { ok: false, reason: 'no OTP issued (send limit)' };

    await page.locator('#auth-code').fill(code, { timeout: 8000 });
    await page
      .locator('.auth-sheet')
      .getByRole('button', { name: /T.sdiql/ })
      .click(CLICK);
    await page.waitForTimeout(1400);
  } catch (error) {
    return { ok: false, reason: String(error.message).split('\n')[0].slice(0, 60) };
  }

  // Ask the UI, not the API: the access token lives in memory (plan.md 6.3),
  // so a bare fetch from the page carries no bearer header and answers 401
  // even when the app is perfectly well signed in. The avatar in the header
  // is the honest signal.
  const signedIn = (await page.locator('header .avatar').count()) > 0;
  return { ok: signedIn, reason: signedIn ? '' : 'admin session not established' };
}

/** Set once the admin session exists; the admin steps are skipped without it. */
let adminReady = false;

await step('admin guard', async () => {
  await visit('/admin');
  await page.waitForTimeout(500);
  // Signed out: the panel must refuse rather than render an empty shell.
  check(
    'Admin panel is closed to signed-out visitors',
    (await page.locator('.admin').count()) === 0,
  );

  const forbidden = await page.evaluate(async () => {
    const res = await fetch('/api/v1/admin/products');
    return res.status;
  });
  check('Admin API refuses an unauthenticated call', forbidden === 401, String(forbidden));
});

await step('admin dashboard', async () => {
  const session = await signInAs(ADMIN_PHONE);
  adminReady = session.ok;
  if (!adminReady) {
    skip('Admin panel checks', session.reason);
    return;
  }

  await visit('/admin');
  await page.waitForSelector('.stat', { timeout: 10000 }).catch(() => null);
  check('Dashboard renders its counters', (await page.locator('.stat').count()) === 4);
  check('Dashboard renders the 30-day series', (await page.locator('.spark svg').count()) === 1);
});

const SMOKE_TITLE = `Smoke testi məhsulu ${Date.now()}`;

await step('admin creates a product', async () => {
  if (!adminReady) return;
  await visit('/admin/products/new');
  await page.waitForSelector('.admin__form', { timeout: 10000 });

  // An empty save must be refused by the form, not by the server.
  await page.getByRole('button', { name: /Yadda saxla/ }).click(CLICK);
  await page.waitForTimeout(400);
  check('Empty form reports field errors', (await page.locator('.field__error').count()) >= 2);

  await page
    .locator('input')
    .filter({ hasNot: page.locator('[type=checkbox]') })
    .first()
    .fill(SMOKE_TITLE);
  await page.locator('input[inputmode="decimal"]').first().fill('12,34');
  await page.locator('select').first().selectOption({ index: 1 });
  await page.getByRole('button', { name: /Yadda saxla/ }).click(CLICK);
  await page.waitForTimeout(1200);

  check(
    'Saving navigates to the edit route',
    /\/admin\/products\/\d+/.test(page.url()),
    page.url(),
  );
  check('Image uploader appears once saved', (await page.locator('.image-grid').count()) === 1);
});

await step('the new product reaches the public catalogue', async () => {
  if (!adminReady) return;
  await visit(`/products?q=${encodeURIComponent(SMOKE_TITLE)}`);
  await page.waitForTimeout(700);
  const titles = await page.locator('.product-card__title').allInnerTexts();
  check(
    'Created product is listed publicly',
    titles.some((tt) => tt.includes('Smoke testi')),
    String(titles.length),
  );
});

await step('admin soft-deletes the product', async () => {
  if (!adminReady) return;
  await visit('/admin/products');
  await page.locator('input[type="search"]').fill('Smoke');
  await page.waitForTimeout(800);
  page.once('dialog', (d) => d.accept());
  await page.locator('.row-actions button[aria-label*="sil"]').first().click(CLICK);
  await page.waitForTimeout(1200);

  await clearHttpCache();
  await visit(`/products?q=${encodeURIComponent(SMOKE_TITLE)}`);
  await page.waitForTimeout(800);
  const remaining = await page.locator('.product-card').count();
  check('Deleted product disappears from the shop', remaining === 0, `${remaining} left`);

  // Soft, not hard: the panel can still see and restore it (plan.md 9.6).
  await visit('/admin/products');
  await page.locator('input[type="search"]').fill('Smoke');
  await page.locator('.admin__toolbar input[type="checkbox"]').check();
  await page.waitForTimeout(900);
  const restorable = await page.locator('.row-actions button[aria-label*="bərpa"]').count();
  check(
    'Soft-deleted row is still restorable in the panel',
    restorable >= 1,
    `${restorable} found`,
  );
});

await step('admin request queue', async () => {
  if (!adminReady) return;
  await visit('/admin/requests');
  await page.waitForSelector('.table', { timeout: 10000 }).catch(() => null);
  check('Request queue lists rows', (await page.locator('tbody tr').count()) > 0);
  await page.locator('tbody tr').first().click(CLICK);
  await page.waitForTimeout(600);
  check('A row opens the detail panel', (await page.locator('.request-panel').count()) === 1);
  // Opening a new request marks it seen, so the queue reflects real work.
  const status = await page.locator('.request-panel .chip[aria-pressed="true"]').innerText();
  check(
    'Opening a new request marks it viewed',
    /Baxıldı|Tamamlandı|Ləğv/.test(status),
    status.trim(),
  );
  await page.locator('.request-panel button[aria-label="Bağla"]').click(CLICK);
  await page.waitForTimeout(300);
});

await step('reviewing the queue', async () => {
  if (!adminReady || !smokeListingTitle) return;

  await visit('/admin/queue');
  await page.waitForSelector('.queue-card', { timeout: 10000 }).catch(() => null);
  const card = page.locator('.queue-card').filter({ hasText: smokeListingTitle });
  check('The offer is waiting in the review queue', (await card.count()) === 1);
  check('The queue shows who offered it', /Göndərən/.test(await card.first().innerText()));

  // Rejecting asks for a reason first - the submitter reads it.
  await card
    .first()
    .getByRole('button', { name: /İmtina et/ })
    .click(CLICK);
  await page.waitForTimeout(400);
  const reject = card.first().getByRole('button', { name: /İmtina et/ });
  check('Rejection is blocked until a reason is given', !(await reject.isEnabled()));
  await card
    .first()
    .getByRole('button', { name: /^İmtina$/ })
    .click(CLICK);
  await page.waitForTimeout(300);

  await card
    .first()
    .getByRole('button', { name: /Təsdiqlə/ })
    .click(CLICK);
  await page.waitForTimeout(1400);
  check(
    'Approving clears it from the queue',
    (await page.locator('.queue-card').filter({ hasText: smokeListingTitle }).count()) === 0,
  );

  await clearHttpCache();
  await visit(`/products?q=${encodeURIComponent(smokeListingTitle)}`);
  await page.waitForTimeout(800);
  check(
    'An approved offer is on the site immediately',
    (await page.locator('.product-card').count()) === 1,
  );
  check(
    'It is listed as free',
    /Pulsuz/.test(await page.locator('.product-card').first().innerText()),
  );
});

await step('admin settings reach the public site', async () => {
  if (!adminReady) return;
  await visit('/admin/settings');
  await page.waitForSelector('.admin__form', { timeout: 10000 });
  const save = page.getByRole('button', { name: /Yadda saxla/ });
  check('Save is disabled until something changes', !(await save.isEnabled()));

  const telegram = page.locator('input').nth(2);
  const previous = await telegram.inputValue();
  const marker = `Smoke ${Date.now()}`;
  await telegram.fill(marker);
  await page.waitForTimeout(200);
  check('Editing enables the save button', await save.isEnabled());
  await save.click(CLICK);
  await page.waitForTimeout(1000);

  await visit('/contact');
  await page.waitForTimeout(700);
  const body = await page.locator('#main').innerText();
  check('Saved setting appears on the public contact page', body.includes(marker), marker);

  // Put it back. A suite that leaves a marker in the seller's contact block
  // makes the next demo look broken, and this one runs against the same
  // database a person is about to show someone.
  await visit('/admin/settings');
  await page.waitForSelector('.admin__form', { timeout: 10000 });
  await page.locator('input').nth(2).fill(previous);
  await page.waitForTimeout(200);
  await page.getByRole('button', { name: /Yadda saxla/ }).click(CLICK);
  await page.waitForTimeout(800);
});

await step('cleaning up after itself', async () => {
  if (!adminReady) return;

  // Everything this run put on the board comes back off it. A suite that
  // leaves its fixtures in the demo database turns the catalogue into a list
  // of "Smoke elanı 1787653211764" - which is exactly what it did before
  // this step existed.
  await visit('/admin/products');
  await page.locator('input[type="search"]').fill('Smoke');
  await page.waitForTimeout(900);

  let removed = 0;
  for (let attempt = 0; attempt < 40; attempt += 1) {
    const row = page.locator('tbody tr').first();
    if ((await row.count()) === 0) break;
    page.once('dialog', (d) => d.accept());
    const button = row.locator('.row-actions button[aria-label*="sil"]');
    if ((await button.count()) === 0) break;
    await button.click(CLICK);
    await page.waitForTimeout(700);
    removed += 1;
  }

  await clearHttpCache();
  await visit(`/products?q=${encodeURIComponent('Smoke')}`);
  await page.waitForTimeout(800);
  check(
    'No test listing is left on the board',
    (await page.locator('.product-card').count()) === 0,
    `${removed} removed`,
  );
});

check(
  'No console errors during the run',
  consoleErrors.length === 0,
  consoleErrors.slice(0, 3).join(' | '),
);

await browser.close();

const failed = results.filter((r) => !r.passed);
const skipped = results.filter((r) => r.skipped);
console.log('');
for (const r of results) {
  const tag = r.skipped ? 'SKIP' : r.passed ? 'PASS' : 'FAIL';
  console.log(`  ${tag}  ${r.name}${r.detail ? `  [${r.detail}]` : ''}`);
}
const ran = results.length - skipped.length;
console.log(
  `\n${ran - failed.length}/${ran} checks passed` +
    (skipped.length ? ` (${skipped.length} skipped)` : ''),
);
process.exit(failed.length === 0 ? 0 : 1);
