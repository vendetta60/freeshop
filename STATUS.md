# FreeShop — Project Status

**Snapshot: 2026-08-25.** Companion to [`plan.md`](plan.md), which remains the specification.
This file answers three questions: what is finished, what is not, and where the build deliberately
departed from or went beyond the plan.

---

## 1. Headline

| | |
| --- | --- |
| **Overall completion** | **~92%** |
| Backend tests | **118** passing |
| Frontend unit tests | **29** passing |
| Interaction checks (Playwright) | **77**, green against the dev server |
| API endpoints | **52** implemented |
| Database migrations | 4, all reversible |
| Quality gates | `ruff` · `ruff format` · `mypy --strict` · `eslint` · `tsc --noEmit` · `prettier` · `i18n:check` · bundle budget — all clean |
| Bundle | 117.8 kB / 120 kB gzip JS · 10.9 kB / 20 kB CSS |
| Translations | 416 keys × 2 languages, parity enforced in CI |

**The whole board works end to end**, in both directions:

- *Taking:* browse → sign in by phone → add to a basket → send a request → the row lands in SQLite
  and the person is shown the contact channels.
- *Giving:* sign in → **/offer** with photos → the listing sits `pending` → the administrator reads
  it in **/admin/queue** → approve, and it is on the board on the next page load. Reject, and the
  giver reads why on their own listings page.

Most listings are free, and a free listing says **Pulsuz** rather than `0,00 ₼`.

> **The product changed shape on 2026-08-25** — from a single-owner catalogue into a community
> give-away board with moderation. Nothing was thrown away: the cart, the request transaction and
> the snapshots do exactly what they did. What changed is who may add a listing, and what has to
> happen before anyone sees it. `plan.md` §13.7 is the record.

---

## 2. What is done

### Fully complete

| Phase | Scope | Notes |
| --- | --- | --- |
| **0 — Scaffold** | Repo layout, tooling, CI, Docker, brand layer | Renaming the project is a one-file edit, enforced by a CI job that renames it and greps the build output |
| **1 — Design system** | OKLCH tokens, glass tiers, components, kitchen sink | Two accents (azure / bronze) × two themes, all four verified in-browser |
| **2 — i18n** | AZ/EN switch, 357 keys, `<html lang>`, profile persistence, parity gate | Hand-written translator rather than i18next — see §4.3 |
| **3 — Database** | 10 tables, migrations, 3-tier seed system | Deterministic and idempotent: two runs produce identical rows |
| **4 — Auth** | Phone/OTP, Google verification, JWT, refresh rotation with reuse detection | 24 tests targeting failure modes, not happy paths |
| **5 — Catalogue backend** | Public read, visitor submissions, admin write: product CRUD, category CRUD, image upload for owners and admins | Uploads are sniffed by magic bytes, re-encoded, EXIF-stripped, content-hash addressed — one pipeline, no relaxed second path |
| **6 — Cart & order requests** | Server cart, the submission transaction, admin management, stats | Prices and titles are snapshotted, so a later reprice or deletion cannot rewrite history |
| **7 — Frontend shell** | Router, glass nav, mobile tab bar, drawer, palette, account menu | |
| **8 — Catalogue frontend** | Home, catalogue, product detail, cart, contact | URL-driven filters, so every view is shareable |
| **9 — Auth & cart frontend** | Invitation sheet, pending-intent replay, cart drawer | A guest's interrupted "add to cart" completes itself after sign-in |
| **10 — Account** | Profile (name, language, avatar, phone verification), request history | |
| **11 — Admin panel** | Dashboard, **review queue**, product table + form, category manager, request queue, users, settings | The owner can run the entire board, including accent, default language and every static string |
| **13 — Give-away board** | Visitor submissions with photos, moderation with reasons, free-by-default pricing, "my listings" | `plan.md` §13.7 / D25–D28 |

### Partially complete

| Phase | Done | Missing |
| --- | --- | --- |
| **12 — Hardening** | §10 security checklist closed (rate limits, body cap, headers, CSP, IDOR, admin guards), §11 budgets enforced in CI, loading/empty/error states on every fetching page, the real error envelope documented in OpenAPI, per-route `<title>` and `robots.txt` | The rest of the metadata pass (per-route OG tags, `hreflang`, `sitemap.xml`, JSON-LD `Product`), a keyboard-navigation audit, and **one actual backup restore** |

### Verified, not assumed

- 77 interaction checks drive the real UI, including both halves of the board: offer an item with a
  photo → confirm it is NOT public → approve it in the queue → confirm it is. Plus the admin path:
  create → see it publicly → soft-delete → still restorable.
- A settings change saved in the panel appears on the public contact page in the same run.
- Admin endpoints return **403** to a normal user and **401** to a stranger — checked against the
  API, not the UI.
- Publishing without a verified phone returns `PHONE_NOT_VERIFIED`, not a generic 403.
- A file that is not an image is refused by its bytes, whatever its name or `Content-Type` claims —
  on the visitor's upload route as well as the administrator's.
- A `pending` listing is invisible in the catalogue, on its own URL, and to the cart. Uploading to
  somebody else's listing is a 404, not a 403.

---

## 3. What is left

| Work | Size | Why it matters |
| --- | --- | --- |
| **Backup restore drill** | Small | The script exists and has never been proven. Until one restore has run into a fresh container, the backup is a hope |
| **Metadata / SEO pass** (§11.1) | Small | Titles and `robots.txt` are done; per-route OG tags, `hreflang`, `sitemap.xml` and JSON-LD `Product` are not |
| **Keyboard-navigation audit** | Small | Individual controls are labelled and reachable; the end-to-end tab order has not been walked |
| **§18 deferred wiring** | Medium | Google client ID, a real OTP channel, and the seller's actual contact details |

### Known gaps, stated honestly

- **Google sign-in is unconfigured.** The code path is complete and tested; it needs a client ID
  (`plan.md` §18/W2). The API starts fine without it and returns `GOOGLE_NOT_CONFIGURED`.
- **Telegram OTP raises `NotImplementedError`** on purpose. It needs a `users.telegram_chat_id`
  populated by a bot-link flow, and a channel that silently fails is worse than one that is
  honestly switched off.
- **Rate-limit counters are in-process.** Correct for one uvicorn worker behind Caddy, which is this
  deployment; the piece to move to Redis before running more than one.
- **Images are stored as JPEG only**, with no AVIF/WebP variants and no blurhash — see §4.2.
- **Product images cannot be reordered by dragging.** Main-image pick and delete are there, and the
  API accepts `sort_order`; the DnD affordance is not built (§4.2).
- **Who a taker contacts is still the site's own contact block**, not the giver's. On a board of
  many givers the natural answer is the giver's number, but publishing somebody's phone to anyone
  who asks is a privacy decision, not a refactor — flagged rather than guessed at (`plan.md` §13.7).

---

## 4. Where the build departed from the plan

### 4.1 Sequencing changed

**Phases 7 and 8 were pulled forward, ahead of the backend.** Phase 1 shipped a design system in
which almost nothing was clickable. That was the wrong order: a catalogue you cannot navigate is not
reviewable, and *"it is scheduled for phase 7"* is a poor answer to *"why doesn't this button
work?"*.

**Phase 4 had to precede phase 6.** Both cart lines and order requests are keyed on `user_id`, so
auth is a hard dependency. Corrected during the build.

**Phase 2 (i18n) came last rather than second.** Extracting strings is mechanical; inventing them
twice is not. Every screen was built and reviewed in Azerbaijani first, then extracted in one pass —
which also meant the EN file was written against final copy instead of drafts.

### 4.2 Decisions taken during the build

| Decision | Reason |
| --- | --- |
| **Hand-written i18n instead of i18next** | i18next + react-i18next + detector ≈ 15 kB gzipped against ~9 kB of budget headroom. Raising a performance budget to fit a library is the trade the budget exists to prevent. The plan's contract — flat keys, parity gate, AZ fallback, ICU plurals, `Intl` formatting — is kept exactly (§13.6/D18) |
| **EN dictionary is a lazy chunk** | AZ is the fallback and must be bundled; an Azerbaijani-speaking visitor has no reason to download the English strings |
| **Site default language beats `navigator.language`** | §7.3 defines `default_lang` as what a first-time visitor sees. Most browsers here report `en-US`, so consulting navigator first would have made that setting a no-op (§13.6/D19) |
| **JPEG-only image pipeline, no blurhash** | The security property that matters — decode and re-encode — is format-independent. Multi-format serving needs `<picture>` plumbing and negotiation for no visible gain on localhost (§13.6/D24) |
| **No drag-and-drop image reorder** | Accessible DnD is a component in its own right; reordering eight images is not where this panel's time goes. Main-image pick and delete cover the real work (§13.6/D20) |
| **`/admin/users` is read-only** | §9.9 says there is no self-service admin. A panel that can widen its own access contradicts that (§13.6/D21) |
| **Settings save only changed keys** | A blanket PATCH would let two admins editing different sections overwrite each other with values neither touched (§13.6/D22) |
| **`/meta/config` carries appearance and language, fetched before first paint** | What makes "change the accent and default language with no rebuild" true rather than aspirational (§13.6/D23) |
| **Toasts hand-rolled instead of `sonner`** | A list, a timer and an `aria-live` region. Errors deliberately do not auto-dismiss: a failure that vanishes before it is read leaves someone believing the opposite of what happened |

### 4.3 Technology choices that changed

| Planned | As built | Reason |
| --- | --- | --- |
| TypeScript 7, ESLint 10 | **TS 5.9.3, ESLint 9.39.5** | `typescript-eslint` caps TS at `<6.1`; `eslint-plugin-jsx-a11y` caps ESLint at 9. Newest-*possible*, not newest |
| `@vitejs/plugin-react-swc` | `@vitejs/plugin-react` | Vite 8 recommends against `-swc` with no SWC plugins |
| `orjson` + `ORJSONResponse` | Native FastAPI serialisation | Deprecated in FastAPI 0.141 and now slower than the built-in path |
| `uv` | `pip` + `venv` | `uv` was not installed. A scaffold requiring a tool the developer lacks is not a scaffold |
| `slowapi` for rate limits | **Hand-written sliding window** | slowapi raises its own exception with its own JSON body, so every 429 would have had a different shape from every other error — and the uniform envelope is what the frontend's error handling is built on |
| `i18next` | **~1 kB in-house translator** | See §4.2 |
| Whole `@fontsource-variable/inter` | Explicit `@font-face`, latin + latin-ext | Cut 218 kB → 133 kB of woff2 |
| SSR / prerendering considered | **Client-rendered SPA** | Evaluated and scoped out with a documented upgrade path (§11.1) |
| Glass via a library | **Hand-written CSS** | The popular library is Chromium-only — fatal for an iOS-inspired design |

### 4.4 Requirements clarified with the owner

- **Guests browse but cannot add to cart.** Implemented as an *invitation*, not a rejection: the
  sign-in sheet shows the product they wanted, and their intent is replayed the moment they sign in.
- **Theme is a two-state toggle**, not a three-state cycle. `system` remains the stored default.
- **EN product content is optional** with AZ fallback, and the EN tab never blocks a save.
- **Both accents ship**, azure default, switchable without a rebuild — now from the admin panel.

---

## 5. Bugs found by running things

Twenty-five defects were found during the build. None of the ones below were catchable by reading
the code, a type-checker, or a unit test.

| Bug | Impact | Found by |
| --- | --- | --- |
| **OTP attempt counter rolled back on failure** | The lockout could never fire; a 6-digit code stayed brute-forceable. Correct in isolation, wrong inside a transaction | A lockout test returning 400 instead of 429 |
| **`contain: paint` clipped every nav dropdown** | Category and account menus were completely dead — present in the DOM, not hit-testable | Smoke-test click timeout, confirmed with `elementFromPoint` |
| **Chromium has no AZN currency pattern** | Prices rendered `AZN 489.00` for every visitor while Node rendered `489,00 ₼`. A unit test would have passed | Reading a rendered screenshot |
| **Chromium renders `az-AZ` short months as `M08`** | *The same bug again, in dates.* Every date in the admin panel read "2026 M08 25"; Node renders it correctly | Reading a screenshot of the request queue |
| **Bundle-budget script counted lazy chunks as initial** | Its rule was a filename regex expecting `*Page-`; the admin chunks are named `Admin*`, so the build failed at 130 kB when the real payload was 110 kB. Now read from the built HTML | The admin panel failing CI on the day it landed |
| **Language detection ran before the config arrived** | A stored `en` preference was rejected as "not enabled", so the switch worked and then forgot itself on reload | Reloading after switching |
| **`create_all` built a half-empty schema** | The test conftest imported `Base` but not the models, so a file run alone got only the tables another file had imported | Running the new rate-limit tests as a single file |
| **A saved refresh token cannot be replayed** | Refresh tokens rotate and a used one revokes the family, so the screenshot script's saved session signed itself out | Reading the second admin screenshot |
| **The upload rate bucket covered the whole `/admin/products` prefix** | It was written for image uploads (expensive) but matched every READ of the product table and the review queue, throttling a working administrator to sixty requests an hour. Now matched by path suffix, so it covers uploads and nothing else | The interaction suite tripping it in under a minute |
| **The sign-in rate bucket also covered `/auth/refresh`** | Every page load calls refresh once, so a 20/min rule on the whole `/auth/` prefix signed the interaction suite out mid-run — and would have done the same to real visitors behind one NAT | The suite going red on the commit that added the limiter |
| **`create_app(settings)` was ignored** | Services read the ambient `.env` instead of the passed configuration | Every auth test failing at once |
| **SQLite drops timezones** | Every `expires_at <= now` raised `TypeError` | The whole suite failing |
| **`google-auth` does not pull in `requests`** | API crashed on boot in Docker while working locally | A clean image build |
| **Caddy never matched hashed assets** | Asset caching silently disabled — Vite emits `name-HASH.ext`, the regex expected `name.HASH.ext` | `curl -I` on a built asset |
| **`content-visibility` with a wrong intrinsic size** | Visible layout shift while scrolling; clicks landing on moved content | Playwright reporting intercepted clicks |

**The lesson, stated once:** every one of these was found by *running* the thing — in a browser, in
a container, against a live server, or by looking at a rendered image. The static gates were green
throughout.

---

## 6. Running it

```bash
docker compose up -d --build
```

Serves `http://localhost:8090`. Keep a `wsl` terminal open first — the WSL VM idles out and takes
the containers with it.

Sign in by phone; the code is shown in the sheet itself. Admin is `+994 50 000 00 01`, and the
account menu then offers **İdarəetmə paneli**. Full details, commands and the rebrand checklist are
in [`README.md`](README.md).

**Never run `docker compose down -v`** — the named volumes hold the database and every uploaded
image.
