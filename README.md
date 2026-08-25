# FreeShop

A **community give-away board**. People list things they no longer use — most of them free — and
neighbours ask for what they need. Every listing is read by an administrator before it appears, so
the board stays what it is for. There is no payment and no checkout: a request produces a contact,
and the two people arrange the rest themselves.

There are no shops and no vendors. One administrator, appointed from the environment; everybody
else is a neighbour with something to give away.

Bilingual **AZ (default) / EN**. Interface styled as *Quiet Glass* — translucent, layered chrome
over a strictly neutral canvas, where the only colour comes from photography and a single accent.

> **The full specification is [`plan.md`](plan.md).** It is the authoritative document: architecture,
> data model, API contract, design tokens, performance budgets, security checklist, and a decision log
> recording every trade-off and why it was made. §13.7 records how the product changed shape from the
> catalogue originally specified into the board it is now.

---

## Requirements

| Tool | Version | Notes |
| --- | --- | --- |
| Node | >= 22.12 | 24.x tested |
| Python | >= 3.12 | 3.12 tested |
| Docker | any recent | Only needed for the production stack |

---

## Quick start (local development)

```bash
cp .env.example .env
```

**Backend** — http://localhost:8000 (docs at `/docs`):

```bash
cd backend && python -m venv .venv && .venv/Scripts/python.exe -m pip install -e ".[dev]" && .venv/Scripts/python.exe -m uvicorn app.main:app --reload
```

**Frontend** — http://localhost:5173:

```bash
cd frontend && npm ci && npm run dev
```

Vite proxies `/api` to the backend, so the SPA and API are same-origin in development exactly as they
are behind Caddy in production. That is what lets the httpOnly refresh cookie behave identically in
both environments.

On Linux/macOS use `.venv/bin/python` instead of `.venv/Scripts/python.exe`.

---

## Production (local Docker)

```bash
docker compose up -d --build
```

Serves **http://localhost:8090**. Two running containers: `caddy` and `api`. The frontend is built
once and served as static files — **no Node process runs in production**.

The host port is `HTTP_PORT` (default `8090`). Port 80 is often taken on Windows by a system
service, and 8080 by another project, so the default avoids both. Change it with `HTTP_PORT=9000`
plus a matching `PUBLIC_URL` in `.env`.

> **Never run `docker compose down -v`.** The `-v` flag deletes the named volumes, which hold the
> SQLite database and every uploaded product image. Use `docker compose down`.

Back up and verify a restore before you rely on it:

```bash
docker compose --profile backup run --rm backup
```

---

## Signing in to the demo

There are no passwords. Sign-in is by phone with a one-time code, and in the local stack that code
is shown to you rather than sent by SMS: it appears in the sign-in sheet itself, in the container log
as a boxed banner, and at `/api/v1/dev/otp-inbox`.

| Account | Phone | What it shows |
| --- | --- | --- |
| **Admin (seller)** | `+994 50 000 00 01` | Admin endpoints, request management, stats |
| Buyer (Aysel) | `+994 50 000 00 10` | A populated request history |
| Buyer (phone-only) | `+994 50 000 00 42` | An account with no email address |

Any other number works too and creates a fresh account, which is what a real visitor signing up
would experience.

This works because `DEMO_MODE=true` permits the console OTP channel under `ENV=production`. It is an
explicit opt-in, startup logs a prominent warning, and it must be turned off for anything reachable
from the internet — at which point either Google sign-in or a real OTP channel needs wiring
(`plan.md` §18/W1, W2). Without it the local stack has no working sign-in at all, since there are no
Google credentials and no SMS gateway.

> Sends are rate-limited to **three per number per fifteen minutes**. If a code stops arriving during
> a rehearsal, that is the limiter working, not a bug — use a different number.

---

## How a listing gets on the site

```
   somebody signs in            an administrator reads it          it is on the board
  ┌────────────────────┐        ┌───────────────────────┐        ┌──────────────────┐
  │  /offer            │  →     │  /admin/queue         │  →     │  /products       │
  │  photo, a few words│        │  Təsdiqlə / İmtina et │        │  free, requestable│
  └────────────────────┘        └───────────────────────┘        └──────────────────┘
          │                               │
          │  pending                      │  rejected + a reason
          ▼                               ▼
     /profile/listings  ────────────────────────────────►  the giver reads the reason
```

Three rules hold this together:

- **A listing is `pending` until somebody approves it.** The database column defaults to `pending`,
  so a new code path that forgets to set it publishes nothing. Not in the catalogue, not on its own
  URL, not addable to a cart.
- **Rejection carries a reason**, and the person who offered the item reads it on their own listings
  page. A refusal with no explanation costs you the next donation.
- **Publishing needs a verified phone.** Signing in by OTP verifies it, so most people never notice;
  a Google-only account is sent to **Profil** first. Giving something away is a promise to meet
  somebody.

Free is the default. `price_minor = 0` renders as **Pulsuz**, never `0,00 ₼`, and the submission form
has the box ticked before anyone touches it.


---

## Running the board

Everything below is done from the browser; nothing needs the database or a redeploy.

Sign in as the admin (`+994 50 000 00 01`) and the account menu gains **İdarəetmə paneli**
(`/admin`):

| Screen | What it does |
| --- | --- |
| **İcmal** | Counters, a 30-day request series, and the latest requests |
| **Yeni elanlar** | The review queue: every listing a visitor has sent in, oldest first, with who offered it and on what number. Approve, or reject with a reason |
| **Məhsullar** | Every listing, with search, an `EN` translation marker, and deleted rows behind a toggle |
| Product form | AZ / EN tabs, price in manat, stock, featured flag, and image upload with a main-image pick |
| **Kateqoriyalar** | Two-level category manager; deleting one that still holds products is refused, and says what is in the way |
| **Sorğular** | The request queue. Opening a row marks it viewed, and status plus an internal note are edited in place |
| **İstifadəçilər** | Registered users, searchable. Read-only by design — there is no self-service admin |
| **Tənzimləmələr** | Contacts, appearance (accent, starting theme), language (`default_lang`, `enabled_langs`) and every static page string, in both languages |

Two rules worth knowing before the demo:

- **Publishing requires a verified phone number** (`plan.md` §9.3) — for visitors offering an item
  and for the administrator alike. Signing in by OTP verifies it, so the seeded admin already
  passes; a Google-only account is sent to **Profil** first.
- **Deleting a product is a soft delete.** It leaves the shop immediately and stays in the panel
  behind *Silinmişləri göstər*, where it can be restored. Historical requests keep the title and
  price they were submitted with, whatever happens to the product afterwards.

---

## Language

The `AZ` / `EN` button in the header switches the whole interface, and the API request carries the
language too — so product and category names come back translated (falling back to Azerbaijani where
no translation exists). The choice is stored per browser and, for signed-in users, saved to the
profile.

What a first-time visitor sees is set in **Tənzimləmələr → Dil**, and turning EN off hides the
switch entirely rather than leaving a control that goes nowhere.

Translations live in `frontend/src/lib/i18n/locales/{az,en}.json` as flat dot-namespaced keys.
`npm run i18n:check` fails the build if a key exists in one file and not the other, if a value is
empty, or if the two disagree about their `{placeholder}` names.

---

## Project layout

```
freeshop/
├── plan.md                 # the specification — start here
├── docker-compose.yml      # local production stack
├── Caddyfile               # reverse proxy, static serving, security headers
├── backend/                # FastAPI + SQLAlchemy 2 (async) + SQLite
│   ├── app/                # config, core, db, api, services
│   ├── alembic/            # migrations
│   ├── seeds/              # deterministic fixtures (plan.md 8.1)
│   └── tests/
└── frontend/               # React 19 + Vite + TypeScript + Tailwind 4
    └── src/
        ├── brand/          # THE only place brand literals may appear
        ├── styles/         # OKLCH design tokens
        ├── components/  lib/  pages/  stores/
```

---

## Commands

| Where | Command | Does |
| --- | --- | --- |
| backend | `ruff check . && ruff format --check .` | Lint + format |
| backend | `mypy app` | Strict type check |
| backend | `pytest` | Tests |
| backend | `alembic upgrade head` | Apply migrations |
| backend | `python seeds/seed.py --tier demo` | Seed fixtures |
| frontend | `npm run lint` / `npm run typecheck` | Quality gates |
| frontend | `npm test` | Unit tests |
| frontend | `npm run build` | Production build |
| frontend | `node scripts/check-bundle-budget.mjs` | Enforce the performance budget |
| frontend | `npm run i18n:check` | Fail on an AZ/EN key or placeholder mismatch |
| frontend | `npm run brand:assets` | Regenerate favicons, OG image, manifest |
| frontend | `npm run gen:api` | Regenerate API types from OpenAPI |
| frontend | `npm run smoke` | **Click every control and assert it works** (needs a running server) |
| frontend | `npm run demo:fetch` | Download demo images locally for an offline demo |
| frontend | `npm run demo:images` | Regenerate the demo product imagery |
| frontend | `npm run screenshots` | Re-render `screenshots/` (dev server must be running) |

> `smoke` and `screenshots` both sign in as the seeded admin, and OTP sends are capped at three
> per number per fifteen minutes. Running them back to back is fine; running either three times
> in a row is not — the screenshot script then skips the admin shots with a warning rather than
> quietly capturing the signed-out screen.

---

## Rebranding

The project name and logo are **not final**, and the codebase is built for that. A rename is a
one-file edit plus a command:

1. Edit `frontend/src/brand/brand.config.ts` — change the `BRAND_NAME` constant.
2. Drop in `frontend/src/brand/assets/logo.svg` and `logo-mark.svg` (square, using `currentColor`).
3. `npm run brand:assets`
4. Update `APP_NAME`, `REQUEST_PREFIX`, `FRONTEND_URL`, `CORS_ORIGINS` in `.env`.
5. Rebuild.

Nothing else. An ESLint rule bans the brand name as a literal anywhere outside `src/brand/`, and a CI
job renames the project to a nonsense string, rebuilds, and fails if any trace of the old name
survives — so this stays true rather than merely being intended.

**Do not rename** the repo folder, Docker service or volume names, the SQLite filename, or the
package names. Those are internal identifiers; renaming them gains nothing and risks the volumes that
hold your data.

---

## Configuration notes

- **Google sign-in** is wired but needs credentials. Until `GOOGLE_CLIENT_ID` is set, the API starts
  normally, logs one clear warning, and `/auth/google` returns `GOOGLE_NOT_CONFIGURED`. See
  `plan.md` §18/W2 — for a local project the consent screen stays in *Testing* mode with `localhost`
  origins, so there is no domain verification and no review.
- **Phone/OTP** is built and tested but delivered through `OTP_CHANNEL=console`: codes are printed as
  a boxed line in the terminal *and* listed at `/api/v1/dev/otp-inbox`, so the whole verification flow
  demos on one screen with no SMS gateway. That dev router is **never registered** outside
  `ENV=development`, and a test asserts it 404s in production.
- **The app refuses to boot** in `ENV=production` with a placeholder `JWT_SECRET`, a secret under 32
  characters, a wildcard in `CORS_ORIGINS`, or `OTP_CHANNEL=console` **while phone auth is enabled**.
- **Prices are formatted explicitly, not by `Intl` `style:'currency'`.** Chromium ships no AZN
  currency pattern, so the built-in path renders `AZN 489.00` in a browser while rendering
  `489,00 ₼` in Node — tests would pass while users saw the wrong thing. See `plan.md` §13.2/C1.

---

## Status

**Phases 0 to 11 are complete; phase 12 (hardening) is partly done.** Authentication, the
catalogue, the cart, order requests, the admin panel and the AZ/EN switch all run against the API
and a seeded SQLite database. Submitting a request creates a real row and returns the seller's
contact channels; publishing a product from the panel puts it in the public catalogue immediately.

Verified rather than asserted: **100 backend tests**, **29 frontend unit tests**, and **63 interaction
checks** driving the real UI — including the full admin path (create a product, see it in the shop,
soft-delete it, find it still restorable) and the language switch.

Known limits, stated plainly:

- **Google sign-in is unconfigured.** The code path is complete and tested; it needs a client ID
  (`plan.md` §18/W2). The API starts fine without one and returns `GOOGLE_NOT_CONFIGURED`.
- **Telegram OTP raises `NotImplementedError` on purpose.** It needs a `users.telegram_chat_id`
  populated by a bot-link flow; a channel that fails silently is worse than one that is honestly
  switched off.
- **Rate-limit counters are in-process**, which is correct for the single-worker deployment here and
  is the piece to move to Redis before running more than one worker.
- **Backup is scripted but has never been restored.** Until one real restore has been run into a
  fresh container, treat it as untested (`plan.md` §13, phase 12).
- **Phase-12 leftovers:** the rest of the metadata pass — per-route OG tags, `hreflang`,
  `sitemap.xml` and JSON-LD `Product` (per-route `<title>` and `robots.txt` are done) — and a
  keyboard-navigation audit.

See `plan.md` §13.1 to §13.6 for what changed during implementation and why.

Rendered screenshots of the current UI live in [`screenshots/`](screenshots/) — light and dark,
desktop and mobile, both accents, the reduced-transparency glass fallback, and the admin panel.
