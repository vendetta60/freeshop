# FreeShop — Implementation Plan / İcra Planı

> **Status:** Authoritative build spec. Supersedes the original TZ where they conflict; §2 lists every deviation and why.
> **Audience:** an AI coding agent (Claude Opus 5) or a human dev executing top-to-bottom.
> **Rule of thumb:** if a section says MUST, it is a hard acceptance criterion. SHOULD is strongly recommended. MAY is optional/v2.

---

## 0. One-paragraph product definition

A **community give-away board**. People list things they no longer use — most
of them free — and neighbours ask for what they need. Every listing is read by
an administrator before it appears, so the board stays what it is for rather
than turning into a classifieds site. There is no payment and no checkout: a
request produces a contact, and the two people arrange the rest themselves.

Bilingual AZ (default) / EN, phone or Google sign-in, and a single
administrator appointed from the environment — there are no shops, no vendors
and no store owners. See §13.7 for how this differs from the catalogue this
document originally specified, and why.

## 1. Hard constraints

| Constraint | Decision |
|---|---|
| Cost | **100% free / open-source only.** No paid SaaS in the critical path. Every external dependency must have a working free-tier or self-hosted mode. |
| Dev environment | Local, no Docker required. `npm run dev` + `uvicorn --reload`. SQLite file on disk. |
| Project context | **University final project (diploma work).** Production is a local Docker Compose stack on your own machine — no public domain, no public traffic, no real money or SMS. This is **not** licence to build it sloppily; it *is* licence to skip infrastructure that only pays off under public load (§11.1, §12.3). Optimize for three things: an architecture you can defend, a demo that cannot fail live, and a README an examiner can follow unaided. |
| Prod environment | **Docker Compose, local host.** Two running containers — `caddy` + `api` — plus a build-only `web` stage. Serves `http://localhost`. No Let's Encrypt, no DNS, no public exposure. Caddy's `tls internal` is available if you want a padlock on screen, but plain HTTP is the cleaner demo. |
| Data store | SQLite (WAL). Must be migratable to PostgreSQL without code rewrites → **no SQLite-specific SQL in application code** except the FTS5 search module, which is isolated behind an interface. |
| Runtime targets | Chrome/Edge 120+, Safari 17+, Firefox 128+. Mobile-first. Must degrade gracefully where `backdrop-filter` is unavailable or the user prefers reduced transparency. |
| Performance budget | See §11. Non-negotiable; enforced in CI. |
| Languages | AZ + EN, full parity. No hardcoded user-facing strings anywhere, frontend or backend. |

---

## 2. Deviations from the original TZ (read this before coding)

These are corrections to gaps found in the TZ. Each is a decision already made — implement as written.

| # | TZ said | Plan says | Why |
|---|---|---|---|
| D1 | Email+password registration endpoint exists | **Removed.** Auth = Google OAuth + Phone/OTP only. `password_hash` column dropped. | The TZ's §3.1 lists only Gmail + phone, but §6 exposes `/auth/register/email`. Keeping a password path means bcrypt, reset flows, breach surface, and email deliverability — all for a login method the TZ doesn't want. Admin is seeded, not registered. |
| D2 | Guest cannot add to cart | **Confirmed as written — no guest cart, no `localStorage` cart, no merge endpoint.** The gate is a *product* decision: the catalogue is the invitation, signing up is the RSVP. Implemented as an **invitation**, not a rejection — see §9.8. | Owner-confirmed. The design quality is the conversion mechanism; the wall converts browsers who are already impressed. Implementing it as a disabled button would waste that; implementing it as a glass sign-up sheet at the moment of intent captures it. |
| D3 | SMS OTP via Twilio | **Built code-complete but shipped unwired.** Pluggable `OtpChannel` interface with 4 adapters: `console` (dev), `telegram` (free), `email` (free), `sms` (paid, stub). The entire phone-auth surface sits behind `AUTH_PHONE_ENABLED`, so it can be switched off wholesale. **Decided: run it ON with `OTP_CHANNEL=console`** and demo it through the §9.11 dev OTP inbox. See §18 for the wiring handoff. | Twilio is not free and no free SMS gateway serves +994. Owner's call: write the code now, choose and wire a channel before prod. With the flag off, v1 is Google-only auth and the admin's `phone_verified` is set true by the seed, so the publish gate (§9.3) passes without any OTP traffic. Turning it on later is one env var, zero migrations, zero refactor. |
| D4 | `otp_codes` table has no abuse controls | Added `attempts`, `ip_hash`, `channel`, `consumed_at`; code stored as **hash**, never plaintext. Per-phone and per-IP rate limits. | An OTP table without attempt counting is brute-forceable in seconds. |
| D5 | Refresh tokens "in httpOnly cookie" with no server record | Added **`refresh_tokens` table** with rotation + reuse detection + family revocation. | Stateless refresh tokens cannot be revoked. Logout must actually log out. |
| D6 | No i18n in the data model | Products/categories carry `_az` + `_en` fields with AZ fallback. API returns resolved strings based on `Accept-Language`/`?lang`. | Bilingual is a stated requirement; retrofitting it later means a full migration. |
| D7 | No slugs, no currency, no soft delete | Added `slug` (unique, SEO), `currency` (default `AZN`), `deleted_at` on products. | Hard-deleting a product orphans it from historical order requests. |
| D8 | Search unspecified | **SQLite FTS5** virtual table + trigram fallback, behind a `SearchBackend` protocol. | `LIKE '%x%'` does not scale and cannot rank. FTS5 is built into SQLite — free, zero infra. |
| D9 | `order_requests` minimal | Added `note` (user message), `contact_email`, `admin_note`, `request_no` (human-readable, e.g. `SR-2026-0041`). | Admin needs to reference a request on the phone. |
| D10 | "Sadə statistika — v2" | **Kept in v1**, it's 3 SQL COUNTs. | Cheap; the admin dashboard looks empty without it. |
| D11 | Subcategories "optional" | **Required**, exactly 2 levels (parent → child). No deeper. | The nav design depends on it; unbounded depth is a UX and query trap. |
| D12 | Product owner model ambiguous | **v1 is single-seller.** `products.owner_id` exists and is enforced, but only `role=admin` may create. The phone-verification gate (TZ §3.3) is implemented and enforced now, so flipping to multi-seller in v2 is a one-line permission change. | Building marketplace permissions for one seller is waste; building *no* ownership is a rewrite later. |

---

## 3. Design system — "Quiet Glass"

### 3.0 Brand layer (name & logo are NOT final — build for the rename)

**"FreeShop" is a working title.** The name, logo, domain, and contact details WILL change. Treat branding as **configuration, not content**. A rebrand must be a ~10-minute edit to a handful of files, never a codebase-wide find-and-replace.

**MUST — the single source of truth:**

```
frontend/src/brand/
├── brand.config.ts     # every brand-variable string & flag
├── Logo.tsx            # <Logo/> <LogoMark/> <Wordmark/> — inline SVG, currentColor
└── assets/
    ├── logo.svg  logo-mark.svg
    ├── favicon.svg  favicon-96.png  apple-touch-icon.png (180×180)
    └── og-image.png (1200×630)
```

```ts
// brand.config.ts — the ONLY place these literals may appear
export const brand = {
  name:        'FreeShop',                  // wordmark text / <title> suffix
  shortName:   'FreeShop',                  // PWA, mobile bar, ≤12 chars
  legalName:   '',                          // footer, invoices — fill at launch
  domain:      'example.az',
  tagline:     { az: '', en: '' },          // translated; lives here, not in i18n JSON
  description: { az: '', en: '' },          // <meta description> / OG
  accent:      'azure' as 'azure' | 'bronze',
  defaultTheme:'system' as 'system' | 'light' | 'dark',
  social:      { instagram: '', facebook: '', whatsapp: '', telegram: '' },
} as const
```

**MUST — rules that keep the rename cheap:**

1. **No brand literal outside `brand.config.ts`.** Not in components, not in `index.html`, not in `az.json`/`en.json`, not in page titles. An ESLint `no-restricted-syntax` rule bans the literal string in `src/**` except `src/brand/`. CI enforces it.
2. `index.html` carries **placeholders** (`%BRAND_NAME%`, `%BRAND_DESC%`, `%BRAND_OG%`) filled by a `transformIndexHtml` hook in `vite.config.ts` that imports `brand.config.ts`. Title, description, OG/Twitter tags, theme-color, and manifest name all resolve from one object.
3. **Logo is an inline React SVG using `fill="currentColor"`** — never a raster, never a hardcoded hex. This is what lets it sit on glass in light *and* dark without a second asset, and lets the mobile bar render it at 24px crisply. Two variants: full lockup (mark + wordmark, desktop nav, footer) and mark-only (mobile bar, favicon, avatar fallback, OG watermark). Wordmark may be set in Inter 600 with `-0.02em` tracking until a real logo exists — a typographic wordmark is a legitimate placeholder, a stock icon is not.
4. **Reserve the space now.** Nav slot is a fixed `height: 32px; max-width: 160px` box; the mark slot is `32×32`. A logo swap must never reflow the nav. Design against these boxes from phase 1.
5. **Backend** reads `APP_NAME` and `REQUEST_PREFIX` from env (§12.1). Used in OTP/email templates and the `request_no` format — `SR-2026-0041` becomes `<REQUEST_PREFIX>-2026-0041`. Existing request numbers are **never** rewritten on rebrand; they are historical identifiers.
6. **Internal identifiers are exempt and must NOT be renamed:** the `freeshop/` repo folder, Docker service/volume names, the SQLite filename, `package.json`/`pyproject.toml` `name` fields, Python module paths. Renaming these buys nothing and risks breaking volumes (§12.3) — i.e. the shop's data. Cosmetic only; leave them.
7. **Favicon/OG regeneration** is a documented npm script (`npm run brand:assets`) using `sharp` — one SVG in, the full icon set out. No manual export step to forget.

**Rebrand checklist (put this verbatim in `README.md`):** edit `brand.config.ts` → drop in `logo.svg` + `logo-mark.svg` → run `npm run brand:assets` → set `APP_NAME` / `REQUEST_PREFIX` / `FRONTEND_URL` / `CORS_ORIGINS` in `.env` → point DNS → rebuild. Nothing else.

### 3.1 Design thesis

The failure mode to avoid is the "children's playground" look: many saturated hues, colored category badges, rainbow gradients, neon glass. **The product photos are the color.** Everything else is a near-monochrome, softly-lit surface.

Three rules that produce the whole look:

1. **One accent hue. Ever.** A muted azure. It appears on: primary buttons, active nav item, focus rings, links, the cart badge. Nowhere else.
2. **Chroma ceiling.** No token in the UI chrome exceeds `C = 0.15` in OKLCH. Semantic colors (success/warning/danger) are desaturated variants, not their default web values.
3. **Depth comes from light, not color.** Elevation is expressed by translucency + blur + a 1px specular top edge + a soft ambient shadow — never by a different hue.

### 3.2 Color tokens (OKLCH, CSS custom properties)

Define in `src/styles/tokens.css`. Light is the base; dark overrides only what changes.

```css
:root {
  /* ---- Neutral canvas (hue 265, chroma ≤ 0.012) ---- */
  --bg:            oklch(0.985 0.002 265);
  --bg-elevated:   oklch(1.000 0.000 265);
  --surface:       oklch(1.000 0.000 265);
  --surface-2:     oklch(0.968 0.003 265);
  --surface-3:     oklch(0.940 0.004 265);
  --border:        oklch(0.905 0.004 265);
  --border-strong: oklch(0.840 0.006 265);

  --text:          oklch(0.220 0.012 265);
  --text-muted:    oklch(0.520 0.010 265);
  --text-subtle:   oklch(0.640 0.008 265);
  --text-inverse:  oklch(0.985 0.002 265);

  /* ---- The single accent ---- */
  --accent:         oklch(0.550 0.115 250);
  --accent-hover:   oklch(0.495 0.120 250);
  --accent-active:  oklch(0.445 0.118 250);
  --accent-subtle:  oklch(0.955 0.020 250);  /* tinted backgrounds only */
  --accent-border:  oklch(0.870 0.045 250);
  --on-accent:      oklch(0.995 0.000 250);

  /* ---- Semantics (deliberately desaturated) ---- */
  --success:  oklch(0.560 0.095 155);
  --warning:  oklch(0.700 0.105 78);
  --danger:   oklch(0.545 0.145 25);
  --success-subtle: oklch(0.960 0.022 155);
  --warning-subtle: oklch(0.965 0.030 78);
  --danger-subtle:  oklch(0.960 0.025 25);

  /* ---- Glass ---- */
  --glass-tint:      color-mix(in oklab, var(--surface) 64%, transparent);
  --glass-tint-deep: color-mix(in oklab, var(--surface) 82%, transparent);
  --glass-blur:      20px;
  --glass-saturate:  180%;
  --glass-edge:      color-mix(in oklab, white 55%, transparent); /* specular top */
  --glass-hairline:  color-mix(in oklab, var(--border) 70%, transparent);
  --glass-shadow:    0 1px 2px oklch(0.22 0.012 265 / 0.05),
                     0 8px 24px -6px oklch(0.22 0.012 265 / 0.10),
                     0 24px 48px -16px oklch(0.22 0.012 265 / 0.08);

  /* ---- Radii (iOS continuous-corner feel) ---- */
  --r-xs: 8px;  --r-sm: 12px; --r-md: 16px;
  --r-lg: 22px; --r-xl: 28px; --r-full: 999px;

  /* ---- Motion ---- */
  --ease-out:    cubic-bezier(0.22, 1, 0.36, 1);
  --ease-spring: linear(0,.0067,.0264,.0575,.0989,.1497,.2088,.2751,.3474,.4245,
                        .5052,.5883,.6725,.7565,.8391,.919,.9951,1.066,1.131,
                        1.189,1.239,1.28,1.313,1.336,1.351,1.357,1.356,1.348,
                        1.335,1.317,1.296,1.273,1.248,1.223,1.199,1.176,1.155,
                        1.136,1.12,1.107,1.096,1.088,1.082,1.078,1.076,1.075,1);
  --d-fast: 140ms; --d-base: 220ms; --d-slow: 380ms;
}

:root[data-theme="dark"], /* explicit toggle */
:root:not([data-theme="light"]) { /* system preference — wrap in @media below */
}

@media (prefers-color-scheme: dark) {
  :root:not([data-theme="light"]) { /* ...dark block below... */ }
}
:root[data-theme="dark"] { /* ...same dark block... */ }
```

**Dark block** (apply identically to both selectors above — author once in a `@layer`, or use a Sass/postcss include; do **not** define any color *only* inside a media query):

```css
  --bg:            oklch(0.165 0.008 265);
  --bg-elevated:   oklch(0.205 0.009 265);
  --surface:       oklch(0.212 0.009 265);
  --surface-2:     oklch(0.248 0.010 265);
  --surface-3:     oklch(0.285 0.010 265);
  --border:        oklch(0.320 0.010 265);
  --border-strong: oklch(0.410 0.012 265);

  --text:          oklch(0.960 0.003 265);
  --text-muted:    oklch(0.720 0.008 265);
  --text-subtle:   oklch(0.600 0.008 265);
  --text-inverse:  oklch(0.180 0.010 265);

  --accent:        oklch(0.715 0.115 250);
  --accent-hover:  oklch(0.770 0.110 250);
  --accent-active: oklch(0.660 0.118 250);
  --accent-subtle: oklch(0.290 0.045 250);
  --accent-border: oklch(0.400 0.070 250);
  --on-accent:     oklch(0.155 0.020 250);

  --success: oklch(0.750 0.100 155);
  --warning: oklch(0.805 0.105 78);
  --danger:  oklch(0.690 0.145 25);
  --success-subtle: oklch(0.275 0.038 155);
  --warning-subtle: oklch(0.290 0.045 78);
  --danger-subtle:  oklch(0.280 0.048 25);

  --glass-tint:      color-mix(in oklab, var(--surface) 58%, transparent);
  --glass-tint-deep: color-mix(in oklab, var(--surface) 80%, transparent);
  --glass-edge:      color-mix(in oklab, white 14%, transparent);
  --glass-hairline:  color-mix(in oklab, white 10%, transparent);
  --glass-shadow:    0 1px 2px oklch(0 0 0 / 0.30),
                     0 8px 24px -6px oklch(0 0 0 / 0.40),
                     0 24px 48px -16px oklch(0 0 0 / 0.34);
```

#### Two accents, one at a time

You liked both the azure and the bronze. Because the entire interface derives from **one** hue token, supporting both costs 6 extra custom properties per theme — so ship both and let the brand decide later. `azure` is the **default**: you chose a *mixed/general* catalogue (§3.6), meaning you don't control what colors arrive in the product photos, and azure is the one that never fights them. Bronze is warmer and more premium but clashes with cool/clinical or electronics imagery — switch to it only if the actual inventory turns out to be warm-toned (wood, leather, textile, jewelry).

Swap by setting `data-accent` on `<html>`, driven by `brand.config.ts` (§3.0) with an admin-settings override persisted in the `settings` table:

```css
/* Default is azure — already defined on :root above. Bronze overrides only these 6. */
:root[data-accent="bronze"] {
  --accent:        oklch(0.580 0.100 65);
  --accent-hover:  oklch(0.525 0.105 65);
  --accent-active: oklch(0.475 0.100 65);
  --accent-subtle: oklch(0.960 0.022 65);
  --accent-border: oklch(0.875 0.045 65);
  --on-accent:     oklch(0.995 0.000 65);
}
/* Dark variant — author under all three dark selectors, same pattern as above. */
:root[data-accent="bronze"][data-theme="dark"] {
  --accent:        oklch(0.740 0.095 65);
  --accent-hover:  oklch(0.795 0.090 65);
  --accent-active: oklch(0.685 0.100 65);
  --accent-subtle: oklch(0.295 0.040 65);
  --accent-border: oklch(0.405 0.060 65);
  --on-accent:     oklch(0.165 0.020 65);
}
```

**MUST:** adding an accent means adding **exactly** these 6 tokens and nothing else. If a third accent ever needs a new token, the component using it is wrong — fix the component. The kitchen-sink route (§13 phase 1) renders in all **4** combinations (azure/bronze × light/dark) and all 4 are contrast-audited per §15.



### 3.3 Banned (enforce in code review)

- More than **one accent hue live at a time**. Azure (250) or bronze (65) — never both on screen, never a per-section accent. Beyond the active accent, the only permitted hues in chrome are the semantics: 155 / 78 / 25.
- Per-category colors. Category chips are neutral; the **active** one is accent.
- Multi-stop or multi-hue gradients. The only allowed gradient is the specular glass edge (white → transparent at ≤8% opacity).
- `#000` text on `#fff`. Use `--text` / `--bg`.
- Pure-white glass on white. Glass must always sit over content or a photo, never over flat `--bg`.
- Emoji as UI icons. Use `lucide-react`.
- Drop shadows with color. Shadows are neutral, from `--glass-shadow` only.

### 3.4 Typography

- **Inter Variable**, self-hosted via `@fontsource-variable/inter` (SIL OFL, free). No Google Fonts CDN — it's a third-party RTT, a privacy leak, and it breaks in an air-gapped Docker prod. Inter's Latin Extended-A subset covers **ə ğ ı İ ö ü ç ş** — verify `Ə` (U+018F) and `ə` (U+0259) render before shipping.
- Subset at build time to `latin` + `latin-ext`. Preload the woff2 with `<link rel="preload" as="font" crossorigin>`.
- Numerals: `font-variant-numeric: tabular-nums` on all prices, quantities, and table cells.
- Scale (rem, 16px root): `12 / 13 / 14 / 16 / 18 / 21 / 26 / 32 / 40 / 52`. Line-height 1.5 body, 1.2 display. Letter-spacing `-0.011em` at ≥26px, `0` below.
- Weights used: 400, 500, 600. **Never 700+** — it reads cheap against glass.

### 3.5 Liquid Glass — implementation contract

Three tiers, chosen at runtime by a `useGlassTier()` hook.

**Tier A — full glass** (default when `backdrop-filter` supported, device not low-power, `prefers-reduced-transparency: no-preference`):

```css
.glass {
  background: var(--glass-tint);
  -webkit-backdrop-filter: blur(var(--glass-blur)) saturate(var(--glass-saturate));
  backdrop-filter: blur(var(--glass-blur)) saturate(var(--glass-saturate));
  border: 1px solid var(--glass-hairline);
  box-shadow: var(--glass-shadow), inset 0 1px 0 0 var(--glass-edge);
  border-radius: var(--r-lg);
  isolation: isolate;
  contain: paint;
}
```

**Tier B — reduced** (`prefers-reduced-transparency`, or blur budget exceeded): drop `backdrop-filter`, use `--glass-tint-deep` as an opaque-ish fill, keep the hairline and shadow. Visually identical silhouette, zero compositing cost.

**Tier C — no support**: solid `--surface` + `--border` + shadow.

**Optional Tier A+ — edge refraction.** An inline SVG `feTurbulence` + `feDisplacementMap` filter applied *only* to a 12px inset ring of the surface, producing the lensing at the glass rim. Gate behind: desktop only, ≤2 elements on screen, `matchMedia('(min-width: 1024px)')`, and a `deviceMemory >= 8` check. **If it costs more than 1ms of paint in the profiler, delete it.** It is decoration, not the design.

**Hard perf rules for glass — violating these is what makes glass UIs janky:**

| Rule | Reason |
|---|---|
| Max **3** `backdrop-filter` layers composited simultaneously. Enforce with a small context/counter in dev mode that `console.warn`s on the 4th. | Each blur layer is a full-viewport GPU readback. |
| **Never** put glass on a list item, card, or anything inside a scroll container. | Blur re-samples on every scroll frame → guaranteed dropped frames on mid-range Android. |
| Glass is allowed on exactly: top nav bar, mobile bottom tab bar, cart drawer, modal/sheet, toast, command palette, sticky filter bar. That is the complete list. | |
| Every glass surface gets `contain: paint` and a fixed/sticky position or a transform-only animation. | Prevents layout-triggered re-blur. |
| Animate only `transform` and `opacity`. Never animate `backdrop-filter`, `blur()`, `width`, `height`, `top`. | The former are compositor-only. |
| `will-change: transform` **only** while an element is actively animating; remove it on animation end. | Permanent `will-change` permanently pins a GPU layer. |
| Glass surfaces must render at a stable size — no content-driven resize on scroll. | |

**Reduced motion:** with `prefers-reduced-motion: reduce`, all spring/slide transitions collapse to a 100ms opacity fade. Sheets appear in place. No parallax, ever.

### 3.5.1 Glass libraries — evaluated (Aug 2026), with a recommendation

You asked me to find a working library. I checked the field properly. Short version: **the popular one is broken exactly where our design cannot afford it, and the genuinely good one solves a different problem than ours.**

| Package | Weekly downloads | Technique | Verdict |
|---|---|---|---|
| `liquid-glass-react` (rdev, 6k★) | **~34,800** | `backdrop-filter: url(#svgFilter)` | ❌ **Reject.** Its own README states: *"Safari and Firefox only partially support the effect (displacement will not be visible)."* `backdrop-filter: url()` is Chromium-only. 22 open issues. Adopting it means an **iOS-inspired interface whose signature effect silently dies on iOS Safari** — the worst possible place for this design to fail. |
| `liquid-glass-web-react` (PallavAg) | ~4,300 | Generates a displacement PNG, applies `feDisplacementMap` to the **content itself**; movement only shifts the filter subregion | ✅ **Genuinely good engineering.** Real cross-browser (Chrome/Safari/Firefox, desktop + mobile, no flags), ~5 kB gzip, **zero runtime dependencies**, MIT, imperative `setPosition()` so per-frame movement triggers no React re-renders. Caveats: **v0.1.1, published 2026-06-10** — pre-1.0, young API; Safari caps SVG filter source size on very large containers. |
| `@liquidglass/react` | ~3,500 | backdrop-filter + SVG displacement | ⚠️ Same Chromium-only displacement class, smaller community. No advantage over the above. |
| `@creativoma/liquid-glass` | ~160 | Tailwind glassmorphism wrapper | ❌ Effectively unmaintained, and it is `backdrop-blur` wrapped in a component. Never take a dependency for one CSS property. |

**Recommendation — two layers, and the second is optional:**

**1. The chrome (all seven surfaces in §3.5) stays hand-written CSS.** This is a requirements mismatch, not stubbornness. Our glass surfaces are **responsive and content-sized**: a nav pill at `100% − 32px`, a drawer at `min(420px, 90vw)`, a modal that sizes to its content, a tab bar respecting `env(safe-area-inset-bottom)`. Every lens library on the market wants **fixed pixel dimensions**. Using one for the chrome means bolting a `ResizeObserver` onto each surface, regenerating a displacement map on every resize and orientation change, and still landing somewhere worse than the ~25 lines of CSS in §3.5 that already work in every target browser. Keeping it in CSS also preserves the §11 bundle budget and leaves the Tier A/B/C fallback system entirely under your control.

**2. Optionally add `liquid-glass-web-react` for exactly ONE showcase element.** A fixed-size hero lens on the homepage drifting slowly over the featured-product imagery, or a draggable demo on `/about`. That is precisely the case a px-sized lens is *built for*, and 5 kB with zero dependencies is a fair price for real refraction instead of a blur. For a project defence it is also a legitimate differentiator — you can demonstrate real light refraction and explain exactly why it is used in one place and nowhere else.

```bash
npm i liquid-glass-web-react
```

**MUST if you take step 2:** `React.lazy()` it so it never enters the initial bundle; render it only when `useGlassTier()` reports Tier A+ (desktop, `deviceMemory >= 8`, no `prefers-reduced-transparency`); give it a static fallback everywhere else; and **pin the exact version** — it is pre-1.0 and the API can move under you.

**If you would rather ship zero glass dependencies, delete step 2 and nothing else changes.** That independence is the whole reason the chrome stays on CSS.

### 3.6 Navigation & layout (my call, per your instruction)

**Desktop (≥1024px)**
- A **floating glass top bar**, `position: sticky; top: 12px`, inset from the viewport by 16px, `border-radius: var(--r-full)` — a pill, not a full-bleed band. Contains: wordmark · category menu trigger · search field · language switch · theme switch · account · cart.
- **Category menu**: click the trigger → a glass panel drops with a 2-column layout (parents left, children of the hovered parent right). Not hover-triggered (hover menus are hostile on touch-capable laptops). Closes on `Esc`, outside click, or route change.
- **Search**: the top-bar field is a button that opens a **command palette** (`cmdk`) — `⌘K` / `Ctrl+K`. It searches products and categories with debounced (250ms) server queries and shows thumbnails. This replaces a separate search page.
- Product grid: 4 columns @ ≥1440, 3 @ ≥1024. See §3.6.1 for the card spec.

**Mobile (<768px)**
- Top: a compact glass bar with back/wordmark + search icon.
- Bottom: an **iOS-style glass tab bar**, `position: fixed; bottom: 0`, respecting `env(safe-area-inset-bottom)`. Tabs: **Ana səhifə · Kataloq · Axtarış · Səbət · Profil**. Cart tab carries the badge.
- Filters open as a **bottom sheet** with a drag handle and detents (`~45%` and full). Use `vaul` (free, Radix-based) or a hand-rolled Framer Motion sheet.
- Product grid: 2 columns. Cards are **opaque** (`--surface`), not glass — see §3.5.

**Admin (`/admin`)**
- Separate shell: fixed left sidebar (opaque `--surface-2`, not glass — it's a dense work surface, glass hurts legibility), content area on `--bg`. Data tables with sticky headers, tabular numerals, no glass anywhere except toasts and modals.

**Page transitions:** none between routes except a 120ms opacity fade. Route-level slide transitions are the fastest way to make a web app feel slower than it is.

### 3.6.1 Product card — mixed/general catalogue spec

You chose a mixed catalogue, so the card must survive a 3000×2000 furniture photo and a 400×400 phone-shot accessory sitting side by side in the same row. That constraint dictates everything below.

| Property | Value | Why |
|---|---|---|
| Image aspect | **4:5 portrait**, fixed | The neutral middle. Portrait fits more cards above the fold on mobile and flatters both wide and square source images. |
| Image fit | `object-fit: contain` over a `--surface-2` pad, **not** `cover` | `cover` crops the subject out of a wide product shot. `contain` guarantees the whole product is visible whatever the source ratio — the single most important decision for a mixed catalogue. |
| Backdrop | Flat `--surface-2`, no pattern, no gradient | Unifies inconsistent product photography (different backgrounds, different lighting) into one visual rhythm. |
| Card surface | **Opaque `--surface`**, `--r-lg`, 1px `--border` | Never glass — cards live in a scroll container (§3.5). |
| Content block | Fixed **`min-height`**, 2-line clamped title, price, status chip | Prevents ragged card bottoms when titles differ in length. Reserve the space; don't let text reflow the grid. |
| Price | Always present, `tabular-nums`, `--text` at 16/600 | Per your decision: every product has a price. `old_price_minor` renders struck-through in `--text-subtle` before it. |
| Status | Chip, bottom-right: `available` renders **nothing**, `out_of_stock` / `on_order` render a neutral chip | Only show the exception. A green "In stock" badge on every card is visual noise and pushes toward the playground look. |
| Hover (pointer only) | `transform: translateY(-2px)` + shadow step, 140ms | Compositor-only. No image zoom — it re-rasterizes. |
| Placeholder | BlurHash → fade to image, 200ms | Zero CLS; `width`/`height` always set. |
| Whole card | One `<a>` wrapping everything | One tap target, correct semantics, works with middle-click and keyboard. |

**Filters for a mixed catalogue (§4.1 of the TZ):** category tree · price range · availability · sort. **No brand/spec facets in v1** — with no fixed vertical there is no shared attribute set to facet on, and empty filter panels look broken. Free-text search (FTS5) covers the rest. Product variants and attribute facets are v2 (§19).

### 3.7 Component inventory

Build on **Radix UI primitives** (unstyled, accessible, free) — do not hand-roll dialogs, dropdowns, or popovers.

`GlassSurface` (tier-aware wrapper) · `Button` (variants: primary/secondary/ghost/danger, sizes sm/md/lg) · `Input` · `Select` · `Checkbox` · `RadioGroup` · `Switch` · `Slider` (price range) · `Badge` · `Chip` · `Avatar` · `Skeleton` · `EmptyState` · `Toast` (sonner) · `Dialog` · `Sheet` · `DropdownMenu` · `Tabs` · `Tooltip` · `Pagination` · `ImageGallery` (embla) · `PriceTag` · `QuantityStepper` · `ProductCard` · `ProductGrid` · `CategoryTree` · `FilterPanel` · `SearchPalette` · `CartDrawer` · `AuthInviteSheet` · `PhoneVerifyModal` · `LangSwitch` · `ThemeSwitch` · `ProtectedRoute` · `AdminTable` · `StatusPill`.

---

## 4. Technology stack (all free / OSS)

### 4.1 Frontend

| Concern | Package | Why this one |
|---|---|---|
| Build | `vite` 8 + `@vitejs/plugin-react` | **As built.** Vite 8 ships the Rolldown pipeline and emits an explicit recommendation to use `@vitejs/plugin-react` over `-swc` when no SWC plugins are in use — which is our case. |
| Framework | `react` 19, `react-dom` 19 | |
| Language | `typescript` **5.9.3** (pinned), `strict`, `noUncheckedIndexedAccess`, `exactOptionalPropertyTypes` | **Pinned deliberately.** TypeScript 7 is released, but `typescript-eslint` still declares `typescript <6.1.0`. Taking TS 7 would disable type-aware linting — a phase 0 acceptance criterion — for no gain here. |
| Routing | `react-router` 7 (declarative mode) | Free, route-level `lazy()` code splitting. |
| Server state | `@tanstack/react-query` 5 | Caching, dedup, background refetch, infinite queries. Eliminates ~70% of the `useEffect` glue an Axios-only setup needs. |
| Client state | `zustand` 5 | Cart UI, drawer/modal open state, pending auth intent (§9.8), theme, filters. ~1KB. **Rule: anything that comes from the server lives in React Query, never in Zustand.** |
| HTTP | `ky` (or `axios` 1.x) | `ky` is 4KB, fetch-based, has retry/timeout/hooks built in. Either is fine; pick one and wrap it in `src/lib/api/client.ts` — no bare `fetch` calls in components. |
| Styling | `tailwindcss` 4 (CSS-first `@theme`, no JS config) + the token file in §3.2 | v4's Oxide engine builds in ms and reads CSS variables natively, which is exactly what the OKLCH token system needs. |
| Primitives | `radix-ui` (unified package) | Accessibility for free. |
| Animation | `motion` (Framer Motion 12) | Spring physics, layout animations, `LazyMotion` for a ~5KB core. **Import via `LazyMotion` + `domAnimation`**, never the full bundle. |
| Sheets | `vaul` | Drag-to-dismiss bottom sheets with detents. |
| Command palette | `cmdk` | |
| Icons | `lucide-react` | Tree-shakeable, ISC license. Import individually. |
| Forms | `react-hook-form` 7 + `@hookform/resolvers` + `zod` 4 | Uncontrolled inputs → no re-render per keystroke. |
| i18n | `i18next` + `react-i18next` + `i18next-browser-languagedetector` | See §7. |
| Carousel | `embla-carousel-react` 8 | 5KB, no dependencies. |
| Toasts | `sonner` | |
| Font | `@fontsource-variable/inter` | Self-hosted. |
| Dates | `date-fns` v4 with `az` + `enUS` locales | Tree-shakeable; `Intl` where possible. |
| Testing | `vitest`, `@testing-library/react`, `playwright` (e2e, free) | |
| Quality | `eslint` **9.39.5** flat config, `prettier`, `typescript-eslint`, `eslint-plugin-jsx-a11y` | ESLint 10 is out, but `eslint-plugin-jsx-a11y` peers at `<=9`. Accessibility linting is a graded requirement (§15), so ESLint 9 is the correct trade. | |
| Analysis | `rollup-plugin-visualizer`, `vite-plugin-compression2` (brotli) | |

**Optional — one showcase element only:** `liquid-glass-web-react` (~5 kB, zero deps, MIT, genuinely cross-browser). Lazy-loaded, Tier A+ gated, version-pinned. Full evaluation and rationale in **§3.5.1**. The design does not depend on it.

**Explicitly rejected:** `liquid-glass-react` (34.8k downloads/week, but `backdrop-filter: url()` is Chromium-only — its own README admits displacement is invisible in Safari and Firefox, which is fatal for an iOS-inspired UI), `@liquidglass/react` (same limitation class), `@creativoma/liquid-glass` (unmaintained `backdrop-blur` wrapper). The chrome's glass is ~25 lines of CSS (§3.5) and must stay responsive — see §3.5.1 for why no lens library fits it. Also rejected: any UI kit shipping its own color system (MUI, Chakra, Ant) — it would fight §3.

### 4.2 Backend

| Concern | Package |
|---|---|
| Framework | `fastapi` (latest stable), `uvicorn[standard]` |
| Validation | `pydantic` 2, `pydantic-settings` |
| ORM | `sqlalchemy` 2.0 **async**, `aiosqlite` |
| Migrations | `alembic` |
| JSON | **FastAPI's native serialisation** (no `orjson`). `ORJSONResponse` is deprecated as of FastAPI 0.141: Pydantic now serialises straight to JSON bytes and is faster. Error handlers use `JSONResponse`; errors are not a hot path. |
| Auth | `pyjwt` (not `python-jose` — unmaintained), `argon2-cffi` |
| Google OAuth | `google-auth` (ID-token verification only; no extra SDK) |
| Images | `pillow` + `pillow-avif-plugin` |
| Rate limit | `slowapi` (in-memory backend; single container — no Redis needed) |
| HTTP client | `httpx` (Telegram/SMTP webhooks, tests) |
| Logging | `structlog` → JSON lines to stdout |
| Testing | `pytest`, `pytest-asyncio`, `httpx.ASGITransport`, `factory-boy` |
| Quality | `ruff` (lint + format), `mypy --strict` on `app/` |
| Deps | `pyproject.toml` + `pip` (`pip install -e ".[dev]"`). `uv` works identically if installed but is **not required** — it was absent from the dev machine, and a scaffold that needs a tool you do not have is a bad scaffold. |

### 4.3 Infrastructure

`caddy` 2 (reverse proxy, automatic HTTPS, brotli/zstd compression, static file serving with immutable caching) · `docker` + `docker compose` · GitHub Actions (free tier) for lint/test/build.

---

## 5. Repository layout

**One repository, one root, `backend/` and `frontend/` as sibling folders directly under it** — no nested repos, no submodules, no monorepo tooling (no Nx/Turborepo/workspaces; two runtimes with two package managers gain nothing from them). The root holds only what is shared by both: compose files, `Caddyfile`, `.env.example`, CI, and this plan. Each app owns its own dependency manifest, lockfile, Dockerfile, and lint config, and can be built, tested, and run entirely on its own.

```
freeshop/                          # ← repo root == the working directory
├── plan.md
├── README.md
├── docker-compose.yml            # prod
├── docker-compose.dev.yml        # optional: db-less local convenience
├── .env.example
├── Caddyfile
├── .github/workflows/ci.yml
│
├── backend/
│   ├── pyproject.toml  uv.lock  Dockerfile  alembic.ini
│   ├── alembic/versions/
│   ├── app/
│   │   ├── main.py                # app factory, middleware, routers, lifespan
│   │   ├── config.py              # pydantic-settings, single source of env truth
│   │   ├── db/
│   │   │   ├── session.py         # async engine, WAL pragmas, session dep
│   │   │   ├── base.py            # DeclarativeBase, TimestampMixin
│   │   │   └── models/            # user.py category.py product.py cart.py order.py auth.py
│   │   ├── schemas/               # Pydantic in/out DTOs, mirrors models/
│   │   ├── api/
│   │   │   ├── deps.py            # get_current_user, require_admin, require_phone_verified
│   │   │   ├── v1/                # auth.py users.py categories.py products.py cart.py orders.py admin.py meta.py
│   │   │   └── dev.py             # §9.11 OTP inbox — registered ONLY when ENV=development
│   │   ├── services/              # business logic — routers stay thin
│   │   │   ├── auth_service.py  google_service.py  otp_service.py
│   │   │   ├── product_service.py  cart_service.py  order_service.py
│   │   │   ├── image_service.py    search/{base.py,fts5.py}
│   │   │   └── otp_channels/{base.py,console.py,telegram.py,email.py}
│   │   ├── core/                  # security.py errors.py i18n.py logging.py ratelimit.py pagination.py
│   │   └── locales/{az,en}.json   # backend error/message catalogue
│   ├── static/uploads/            # gitignored; docker volume in prod
│   ├── seeds/                     # §8.1 — seed.py + data/*.json + assets/ (committed images)
│   └── tests/
│
└── frontend/
    ├── package.json  vite.config.ts  tsconfig.json  Dockerfile
    ├── index.html
    └── src/
        ├── main.tsx  App.tsx  routes.tsx
        ├── styles/{tokens.css,glass.css,base.css}
        ├── brand/{brand.config.ts,Logo.tsx,assets/}   # §3.0 — the only place brand literals live
        ├── lib/
        │   ├── api/{client.ts,products.ts,auth.ts,cart.ts,orders.ts,categories.ts}
        │   ├── i18n/{index.ts,az.json,en.json}
        │   ├── hooks/{useGlassTier.ts,useMediaQuery.ts,useDebounce.ts,useAuth.ts}
        │   └── utils/{format.ts,image.ts,cn.ts}
        ├── stores/{authStore.ts,cartStore.ts,uiStore.ts,filterStore.ts}
        ├── components/{ui/,layout/,product/,cart/,auth/,admin/}
        ├── pages/{public/,account/,admin/,dev/}   # dev/ = kitchen-sink + otp-inbox, DEV-only
        └── types/api.ts            # generated from OpenAPI — see §6.4
```

---

## 6. API contract

Base: `/api/v1`. All responses `application/json` via `ORJSONResponse`.

### 6.1 Conventions (MUST)

- **Errors** — every non-2xx returns:
  ```json
  { "error": { "code": "PHONE_NOT_VERIFIED", "message": "Nömrə təsdiqlənməyib", "field": null, "details": {} } }
  ```
  `code` is a stable SCREAMING_SNAKE enum. `message` is localized server-side from `Accept-Language`. **The frontend renders its own translation of `code` and only falls back to `message`.**
- **Lists** — `{ "items": [...], "total": 128, "page": 1, "per_page": 24, "pages": 6 }`.
- **Pagination** — `?page` + `?per_page` (max 60). Product list additionally supports keyset (`?cursor=`) for infinite scroll.
- **Localization** — `Accept-Language: az|en`, overridable with `?lang=`. Default `az`.
- **Caching** — `GET` on products/categories emits `ETag` + `Cache-Control: public, max-age=60, stale-while-revalidate=300`. Mutations return `Cache-Control: no-store`.
- **Idempotency** — `POST /order-requests` accepts an `Idempotency-Key` header; a repeat within 10 minutes returns the original request.
- **Validation** — 422 with `error.field` populated.

### 6.2 Endpoints

```
# --- Auth ---
POST   /auth/google              { credential }          -> tokens + user     # ID token verified server-side
POST   /auth/phone/send-otp      { phone }               -> { expires_in, channel }
POST   /auth/phone/verify-otp    { phone, code }         -> tokens + user
POST   /auth/refresh             (httpOnly cookie)       -> new access token   # rotates refresh
POST   /auth/logout                                      -> 204                # revokes token family

# --- Me ---
GET    /users/me
PATCH  /users/me                 { full_name?, avatar_url?, preferred_lang? }
POST   /users/me/phone/send-otp  { phone }
POST   /users/me/phone/verify-otp{ phone, code }
POST   /users/me/avatar          (multipart)

# --- Catalogue (public) ---
GET    /categories                                        # full 2-level tree, one query, cached
GET    /products        ?q&category_id&min_price&max_price&stock&sort&page&per_page&cursor
                        # sort ∈ price_asc|price_desc|newest|oldest|relevance
GET    /products/{slug_or_id}
GET    /products/{id}/related                             # same category, 8 items

# --- Cart (auth) ---
GET    /cart
POST   /cart/items              { product_id, quantity }
PATCH  /cart/items/{id}         { quantity }              # quantity 0 == delete
DELETE /cart/items/{id}
DELETE /cart                                              # clear
# NOTE: no /cart/merge endpoint — there is no guest cart (§9.8). After the
# invitation sign-up, the frontend replays the single held intent via POST /cart/items.

# --- Order requests ---
POST   /order-requests          { note?, contact_phone, contact_email? }   [auth]
                                # snapshots cart, clears it, returns request_no + seller contacts
GET    /order-requests/me       ?page
GET    /order-requests/me/{id}

# --- Admin (role=admin) ---
POST   /admin/products          [+ phone_verified]
PATCH  /admin/products/{id}
DELETE /admin/products/{id}                               # soft delete
POST   /admin/products/{id}/images       (multipart, ≤8 files)
PATCH  /admin/products/{id}/images/{img_id}   { is_main?, sort_order? }
DELETE /admin/products/{id}/images/{img_id}
POST   /admin/categories        PATCH /admin/categories/{id}   DELETE /admin/categories/{id}
GET    /admin/order-requests    ?status&q&page
PATCH  /admin/order-requests/{id}   { status?, admin_note? }
GET    /admin/users             ?page
GET    /admin/stats                                       # counts + last 30d request series

# --- Meta (public) ---
GET    /meta/contact                                      # seller phone/whatsapp/email/address/socials
GET    /healthz                                           # liveness, no DB

# --- Dev only (router NOT registered unless ENV=development — §9.11) ---
GET    /dev/otp-inbox                                     # last 20 OTPs, masked phones, in-memory
GET    /readyz                                            # DB + uploads writable
```

### 6.3 Auth mechanics (MUST)

- Access token: JWT `HS256`, **15 min**, claims `sub, role, phone_verified, jti, iat, exp`. Sent as `Authorization: Bearer`. Kept **in memory only** on the frontend (a Zustand store, not `localStorage` — XSS-exfiltratable).
- Refresh token: opaque 256-bit random, **hashed (SHA-256)** in `refresh_tokens`, delivered as `HttpOnly; Secure; SameSite=Lax; Path=/api/v1/auth`. TTL 30 days.
- **Rotation + reuse detection:** every `/auth/refresh` issues a new refresh token and marks the old one used. If an already-used token is presented, revoke the entire `family_id` and force re-login.
- On app boot, the frontend calls `/auth/refresh` once to hydrate the session (silent login).
- Google: frontend uses Google Identity Services (free) → posts the `credential` ID token → backend verifies signature, `aud`, `iss`, `exp` with `google-auth` → upsert user by `google_id`, then by verified `email`.
- **`require_phone_verified`** dependency guards `POST /admin/products`. Returns `403 PHONE_NOT_VERIFIED`; the frontend intercepts that code and opens `PhoneVerifyModal`.

### 6.4 Type generation (MUST)

FastAPI emits OpenAPI. Generate `frontend/src/types/api.ts` with `openapi-typescript` as an npm script (`npm run gen:api`). **Never hand-write request/response types.** CI fails if the generated file is stale.

---

## 7. Localization (AZ / EN)

### 7.1 Frontend

- `i18next` + `react-i18next`. Namespaces: `common`, `nav`, `product`, `cart`, `auth`, `profile`, `admin`, `errors`, `validation`.
- Detection order: `?lang=` → `localStorage.lang` → user profile `preferred_lang` → `navigator.language` → `az`.
- **Default and fallback language is `az`.**
- Language is reflected in `<html lang>` and persisted to the profile for logged-in users.
- Numbers/dates/currency via `Intl`, never manual: `Intl.NumberFormat(lang === 'az' ? 'az-AZ' : 'en-US', { style: 'currency', currency: 'AZN', maximumFractionDigits: 2 })`. AZ formats as `12,50 ₼`; EN as `₼12.50`. **CONFIRMED BROKEN, fixed in phase 1:** Chromium's bundled ICU reports `az-AZ` as supported but has **no AZN currency pattern**, so `style:'currency'` renders `AZN 489.00` in a browser while Node renders `489,00 ₼`. A Node-run unit test passes while every visitor sees the wrong format. `formatPrice` therefore formats the number with a runtime-stable locale and applies AZ conventions explicitly. Never reintroduce `style: 'currency'` here.
- Pluralization uses ICU plural rules (`_one` / `_other`) — never `count > 1 ? 's' : ''`.
- Translation files are **flat-ish JSON**, keys namespaced by dot: `"product.addToCart"`. Every key must exist in both files.
- **CI gate:** a script diffs `az.json` and `en.json` key sets and fails on any mismatch or empty value.
- **Lint gate:** `eslint-plugin-i18next/no-literal-string` on `src/components` and `src/pages`. No user-visible literal survives review.

### 7.2 Backend

- Content fields are duplicated: `title_az`/`title_en`, `description_az`/`description_en`, `name_az`/`name_en`.
  - `*_az` is **required**; `*_en` is optional and falls back to `*_az` at serialization time.
  - Serializers resolve to a single `title`/`description`/`name` field based on the request language. Admin endpoints return **both** raw fields for editing.
- Error/message catalogue in `app/locales/{az,en}.json`, keyed by error `code`.
- Emails/OTP messages are templated per language using the user's `preferred_lang`.

### 7.3 What the admin controls (per your instruction)

Language behaviour is **not hardcoded** — it is administered from `/admin/settings`:

| Setting | Effect |
|---|---|
| `default_lang` | The language a first-time visitor sees before any preference exists. Ships as `az`. |
| `enabled_langs` | Which languages appear in the switcher. Removing one hides it everywhere without deleting any data — so a half-finished EN translation can be hidden rather than shipped broken. |
| `accent`, `default_theme` | §3.2 appearance, no rebuild. |
| All `*_az` / `*_en` content keys | Hero copy, about text, contact intro, footer note, working hours — both languages, edited in the panel. |

**Content-translation policy (the decision that keeps this maintainable).** Product and category `*_en` fields are **optional and always fall back to `*_az`**. Nothing anywhere breaks, blanks, or 500s when EN is missing — the AZ text is shown instead. Practically:

- The site is **fully usable in EN from day one** with zero translated product content: every button, label, filter, error, empty state and email is translated, and product titles simply appear in AZ.
- The admin product form has AZ / EN tabs. The **EN tab is never required to save.** It shows a neutral "falls back to AZ" hint, not a validation error — a nag that blocks saving is how bilingual catalogues end up abandoned.
- The admin product table shows a small `EN` marker on rows that *do* have a translation, so coverage is visible at a glance and can be filled in gradually.
- This is why §8 uses nullable `*_en` columns rather than a separate translations table: for exactly two languages, one of which is optional, a join table is pure overhead. **Say this if asked why there is no `translations` table** — the answer is "two fixed languages with fallback, so normalising buys nothing and costs a join on every read."

### 7.4 Copy tone

AZ is the primary voice — write it first, translate to EN second (translating AZ→EN produces better AZ than the reverse). Formal-neutral, no slang, no exclamation marks. Buttons are verbs: "Səbətə at" / "Add to cart", "Sorğu göndər" / "Send request".

---

## 8. Data model (SQLAlchemy 2.0, async)

All tables get `id INTEGER PK`, `created_at`, `updated_at` (UTC, timezone-aware). Money is **`INTEGER` minor units (qəpik)** — never float. Enums are stored as `VARCHAR` with a `CHECK` constraint (portable to Postgres).

```
users
  id, email (nullable, unique, citext-equivalent lower-cased)
  phone (nullable, unique, E.164 normalized: +994XXXXXXXXX)
  phone_verified BOOL default false
  google_id (nullable, unique)
  full_name (nullable), avatar_url (nullable)
  preferred_lang VARCHAR(2) default 'az'
  role VARCHAR CHECK IN ('admin','user') default 'user'
  is_active BOOL default true
  last_login_at (nullable)
  CONSTRAINT: email IS NOT NULL OR phone IS NOT NULL

refresh_tokens
  id, user_id FK, token_hash (unique, sha256 hex)
  family_id (uuid), used_at (nullable), revoked_at (nullable)
  expires_at, user_agent_hash, ip_hash
  INDEX (user_id, expires_at), INDEX (family_id)

otp_codes
  id, phone, code_hash, channel VARCHAR CHECK IN ('console','telegram','email','sms')
  purpose VARCHAR CHECK IN ('login','verify_phone')
  attempts INT default 0, max_attempts INT default 5
  expires_at, consumed_at (nullable), ip_hash
  INDEX (phone, purpose, expires_at)

categories
  id, slug (unique), name_az, name_en (nullable)
  parent_id FK->categories (nullable)      -- max depth 2, enforced in service layer
  icon (nullable, lucide icon name), sort_order INT default 0
  is_active BOOL default true
  INDEX (parent_id, sort_order)

products
  id, slug (unique)
  title_az, title_en (nullable), description_az, description_en (nullable)
  price_minor INT NOT NULL CHECK (price_minor >= 0)     -- every product has a public price
  currency VARCHAR(3) default 'AZN'
  old_price_minor INT (nullable)           -- for a discount ribbon
  category_id FK->categories
  stock_status VARCHAR CHECK IN ('available','out_of_stock','on_order') default 'available'
  owner_id FK->users
  is_featured BOOL default false           -- drives the homepage rail
  view_count INT default 0
  deleted_at (nullable)                    -- soft delete
  INDEX (category_id, deleted_at, created_at DESC)
  INDEX (deleted_at, price_minor)
  INDEX (is_featured, deleted_at)

products_fts  (SQLite FTS5 virtual table, external content)
  title_az, title_en, description_az, description_en  -> rowid = products.id
  kept in sync by AFTER INSERT/UPDATE/DELETE triggers

product_images
  id, product_id FK (ON DELETE CASCADE)
  path            -- relative, e.g. 'products/a3/a3f9c2.jpg'
  width, height, blurhash (nullable)
  is_main BOOL default false, sort_order INT default 0
  UNIQUE partial index (product_id) WHERE is_main = 1
  INDEX (product_id, sort_order)

cart_items
  id, user_id FK, product_id FK, quantity INT CHECK (quantity BETWEEN 1 AND 99)
  UNIQUE (user_id, product_id)             -- add-again increments, never duplicates

order_requests
  id, request_no (unique, 'SR-YYYY-NNNN')
  user_id FK
  status VARCHAR CHECK IN ('new','viewed','completed','cancelled') default 'new'
  contact_phone, contact_email (nullable)
  note TEXT (nullable, ≤1000 chars)
  admin_note TEXT (nullable)
  total_minor INT                          -- denormalized snapshot
  INDEX (status, created_at DESC), INDEX (user_id, created_at DESC)

order_request_items
  id, order_request_id FK (ON DELETE CASCADE), product_id FK (ON DELETE SET NULL)
  title_snapshot, quantity, price_at_request_minor
  -- snapshots survive product deletion/price change

settings                                    -- single-row key/value for seller contacts
  key (PK), value_json
  -- CONTACT : contact_phone, whatsapp, telegram, email,
  --            address_az, address_en, working_hours_az, working_hours_en, socials
  -- APPEARANCE: accent ('azure'|'bronze'), default_theme ('system'|'light'|'dark')
  -- LANGUAGE  : default_lang ('az'|'en'), enabled_langs (['az','en'])
  -- CONTENT   : about_az/about_en, contact_intro_az/contact_intro_en,
  --             hero_title_az/hero_title_en, hero_subtitle_az/hero_subtitle_en,
  --             footer_note_az/footer_note_en
  -- These override brand.config.ts at runtime, so the admin can retune appearance,
  -- default language and all static page copy from the panel with no rebuild
  -- (§3.2, §7.4). Read once at boot, cached in-process, invalidated on write.
  -- MUST: every *_en here is optional and falls back to *_az — same rule as products.
```

**SQLite pragmas on every connection** (`db/session.py`):
```sql
PRAGMA journal_mode=WAL;
PRAGMA synchronous=NORMAL;
PRAGMA foreign_keys=ON;
PRAGMA busy_timeout=5000;
PRAGMA cache_size=-64000;
PRAGMA temp_store=MEMORY;
```

---

## 8.1 Seed & mock data (fixtures)

Seed data is **part of the product**, not a scratch script. It is what you demo, what the perf budgets in §11 are measured against, and what makes layout bugs visible. Treat it as code: reviewed, deterministic, committed.

### 8.1.1 Rules (MUST)

1. **Deterministic.** One `random.Random(1453)` instance, and every timestamp derived from a fixed `SEED_EPOCH = datetime(2026, 3, 1, tzinfo=UTC)` constant — **never `datetime.now()`**. Two runs on two machines produce byte-identical data, so screenshots stay stable and a failing test is reproducible.
2. **Idempotent.** Upsert on natural keys (`slug`, `email`, `settings.key`). Re-running must never duplicate or crash. `python seeds/seed.py` twice in a row is a test case.
3. **Tiered** via `--tier`:
   | Tier | Contents | Use |
   |---|---|---|
   | `minimal` | 1 admin, 2 users, 3 categories, 12 products | Fast dev loop; the default |
   | `demo` | 4 users, 8 parent + 24 child categories, **45 products**, 6 order requests, full settings | The defence. Seeded before every rehearsal |
   | `stress` | 200 users, **5,000 products**, 20k images rows | Proving the §11 budgets (`GET /products` p95 ≤ 80 ms) are real and not measured on 12 rows |
4. **`--reset` flag** drops and recreates rather than upserting. Never the default — a stray `--reset` before a demo is the same class of mistake as `down -v`.
5. **No real personal data.** Emails use the RFC 2606 reserved `@example.com`. Phones use the non-routable `+994 50 000 00 XX` pattern. **Never seed a real person's number** — an order request renders it in the admin panel, and this repo will be read by other people.
6. **Text is real Azerbaijani**, not lorem ipsum. Lorem hides exactly the bugs seeded data exists to expose: `ə ğ ı İ ö ü ç ş` rendering, real word lengths against the 2-line clamp, and AZ collation in sort and search.

### 8.1.2 Layout

```
backend/seeds/
├── seed.py                 # orchestrator: --tier, --reset, --with-images
├── data/
│   ├── categories.json     # the 2-level lookup tree
│   ├── products.json       # 45 curated demo products
│   ├── users.json
│   └── settings.json       # contacts, appearance, all page copy (AZ + EN)
└── assets/                 # committed sample images — see 8.1.6
```

### 8.1.3 Users

| Fixture | Role | Auth | Purpose |
|---|---|---|---|
| `ADMIN_EMAIL` (from env) | `admin` | google | The seller. `phone_verified=true` so §9.3's publish gate passes with `AUTH_PHONE_ENABLED=false` |
| `aysel@example.com` | `user` | google | Has a full profile, avatar, 3 order requests, items in cart. The "happy" account you demo with |
| `rashad@example.com` | `user` | google | No `full_name`, no avatar — proves every fallback (initials avatar, "Adı göstərilməyib") actually works |
| `+994500000042` | `user` | phone | `phone_verified=true`, no email. Exercises the `email IS NULL` branch and the E.164 uniqueness constraint |
| `nigar@example.com` | `user` | google | `preferred_lang='en'`, `is_active=false`. Tests EN default and the deactivated-account path |

### 8.1.4 Lookup data — categories

Eight parents × 3 children each, exactly 2 levels (§2/D11). Chosen to be a genuinely *mixed* catalogue so §3.6.1's `object-fit: contain` decision is visibly justified:

| Parent (AZ / EN) | Children |
|---|---|
| Elektronika / Electronics | Telefonlar · Noutbuklar · Audio |
| Ev və bağça / Home & Garden | Mebel · İşıqlandırma · Mətbəx |
| Geyim / Clothing | Kişi · Qadın · Ayaqqabı |
| Gözəllik / Beauty | Dəri baxımı · Ətir · Saç |
| İdman / Sports | Fitnes · Velosiped · Turizm |
| Uşaq / Kids | Oyuncaqlar · Körpə · Məktəb |
| Avtomobil / Automotive | Ehtiyat hissələri · Aksesuarlar · Baxım |
| Hədiyyə / Gifts | Suvenir · Dekorasiya · Kitab |

Deliberate lookup edge cases: **one empty category** (proves the empty state and §9.5's delete rule), **one category with a 34-character AZ name** (nav truncation), **one inactive category** (`is_active=false`, must vanish from public queries but stay in admin).

### 8.1.5 Products — 45 curated, each earning its place

Distribution: ~5–6 per parent category, `demo` tier. Beyond plausible everyday items, the fixture set **must** include these named edge cases — they are the whole reason to hand-curate instead of generating 45 random rows:

| # | Edge case | What it proves |
|---|---|---|
| 1 | Title at **80 chars** with AZ diacritics | 2-line clamp + fixed card height (§3.6.1) |
| 2 | Title at **9 chars** | Cards stay equal height when text is short |
| 3 | `price_minor = 50` (0.50 ₼) | Currency formatting at the low bound |
| 4 | `price_minor = 1250000` (12,500.00 ₼) | `tabular-nums` alignment; AZ `12 500,00 ₼` vs EN `₼12,500.00` |
| 5 | `old_price_minor` set | Discount ribbon + struck-through price |
| 6 | `stock_status='out_of_stock'` | Neutral chip; the "only show the exception" rule |
| 7 | `stock_status='on_order'` | Third status renders correctly |
| 8 | **Exactly 1 image** | Gallery must not show a broken carousel |
| 9 | **8 images** (the §9.7 max) | Gallery pagination and thumbnail strip |
| 10 | **No image at all** | Placeholder path; must never render a broken `<img>` |
| 11 | Full `*_en` translation | The admin table's `EN` coverage marker |
| 12 | `*_en` completely empty | AZ fallback in EN mode (§7.3) — the most important i18n case |
| 13 | 1,800-character description | Detail-page overflow, "read more" behaviour |
| 14 | `is_featured=true` × 6 | Homepage rail has enough to scroll |
| 15 | **`deleted_at` set, referenced by an order request** | §9.1 `PRODUCT_UNAVAILABLE` + §9.6 snapshot survival. **The single most valuable fixture in the set** — it is the one path that silently breaks in production and never shows up in manual testing |

### 8.1.6 Images — committed, deliberately awkward

`seeds/assets/` holds ~15 sample images, committed to git (a few MB, worth it: the seed must work **offline**, which is the whole point of a local Docker demo).

| File | Dimensions | Purpose |
|---|---|---|
| `wide-*.jpg` | 3000×2000 | Proves `contain` beats `cover` — with `cover` the subject is cropped out |
| `tall-*.jpg` | 800×1600 | Extreme portrait in the same 4:5 grid |
| `square-*.jpg` | 1000×1000 | The common case |
| `tiny-*.jpg` | 320×320 | Must not upscale into mush |
| `huge.jpg` | ~4.9 MB | Just under the §9.7 5 MB cap |
| `oversize.jpg` | ~6 MB | **Must be rejected.** Used by the §14 upload test, not by the seed |
| `fake.jpg` | actually a PNG | **Magic-byte sniffing test** (§9.7) — the extension lies |
| `exif.jpg` | with GPS EXIF | Proves EXIF stripping actually runs |

`--with-images` runs each through the real §9.7 pipeline (re-encode → AVIF/WebP/JPEG at 5 widths + blurhash) rather than copying files in. Seeding must exercise the same code path as an admin upload, or the seed proves nothing about the pipeline.

**Fallback:** if `assets/` is absent, `--fetch-images` pulls deterministic placeholders from `picsum.photos/seed/<slug>`. Convenience only — the committed set is the source of truth, because the demo machine may be offline.

### 8.1.7 Order requests & settings

Six requests spanning every state the admin panel must render: one per `status` (`new` / `viewed` / `completed` / `cancelled`), one containing the **soft-deleted product** from fixture #15, one with a 900-character `note`, and one with **12 line items** (admin detail-drawer scrolling). Request numbers are seeded as `SR-2026-0001…`, contiguous, so §9.1's allocator is demonstrably continuing a real sequence rather than starting from zero on stage.

`settings.json` seeds **every** key from §8 — contacts, appearance, `default_lang`, and all bilingual page copy — with coherent fictional values. A demo where "Bizimlə əlaqə" renders empty is worse than one with obviously invented data.

---

## 9. Business rules (MUST)

1. **Cart → request.** `POST /order-requests` runs in one transaction: read cart with a row lock, reject if empty (`CART_EMPTY`), reject if any product is soft-deleted (`PRODUCT_UNAVAILABLE`, returns the offending ids), snapshot title + price into `order_request_items`, compute `total_minor`, allocate `request_no`, clear the cart, return the request + `GET /meta/contact` payload in one response.
2. **Contact phone.** Defaults to `users.phone`; the user may override per request. If the user has no phone at all, the field is required in the payload. Phone verification is **not** required to *send* a request — only to *publish a product*.
3. **Phone gate on publish.** `POST /admin/products` → `require_admin` **and** `require_phone_verified`. 403 `PHONE_NOT_VERIFIED` otherwise.
4. **OTP.** 6 digits, 5-minute TTL, max 5 verify attempts, one active code per (phone, purpose) — sending a new code invalidates the previous. Rate limits: **3 sends per phone / 15 min**, **10 sends per IP / hour**. Constant-time hash comparison. Codes are never logged in prod (`console` channel is refused when `ENV=production`).
5. **Category delete.** Blocked (409 `CATEGORY_NOT_EMPTY`) if it has children or products. The admin must move or delete them first.
6. **Product delete.** Soft delete. Disappears from all public queries, remains resolvable in historical requests.
7. **Uploads.** Max 5MB per file, max 8 per product, MIME sniffed from **magic bytes** (not the client's `Content-Type` header, not the extension). Accepted in: `jpeg/png/webp/avif/heic`. Re-encoded on the server — the original bytes are never served. EXIF stripped. Filenames are content-hash based, in a 2-char shard directory.
8. **Guest gating — "the invitation".** Guests may browse, search, filter, and open any product detail page with zero friction and **no login prompts, banners, or interstitials while browsing**. The wall appears at exactly one moment: pressing **Səbətə at**. Then:
   - `AuthInviteSheet` opens — a glass sheet (bottom sheet on mobile, centered dialog on desktop) showing the product thumbnail + title, one line of copy ("Səbətə əlavə etmək üçün daxil olun"), the Google button, and the phone option. No feature list, no marketing, no dismissible nag.
   - The clicked `{ product_id, quantity }` is held as a **pending intent** in memory (`sessionStorage` fallback for the OAuth redirect round-trip only). After a successful sign-up/login it is replayed once via `POST /cart/items`, the sheet closes, and the cart drawer opens with the item already in it. The user's action completes; they never re-click.
   - The pending intent holds **exactly one item** and is cleared on use, on sheet dismiss, or on navigation away. It is **not** a cart: nothing accumulates, nothing persists across sessions.
   - The cart icon in the nav is visible to guests but shows no badge; clicking it opens the same invitation sheet.
   - `POST /cart/*` and `POST /order-requests` remain auth-only server-side regardless.
9. **Admin seeding.** `ADMIN_EMAIL` (and optionally `ADMIN_PHONE`) from env; on first boot the matching user is created/promoted to `admin`. No self-service admin registration ever.
10. **Sorting default.** `newest`. `relevance` is only valid when `q` is present; otherwise it silently degrades to `newest`.
11. **Console OTP channel — demoable, and safe by construction.** `OTP_CHANNEL=console` is how phone verification is presented (§18/W1). It must be genuinely watchable, not a `print()` buried in uvicorn noise:
    - The adapter writes a **boxed, high-contrast log line** to stdout (`╔══ OTP ══╗ phone +99450***0042 │ code 483920 │ expires 04:58 ║`) — findable instantly in a scrolling terminal on a projector.
    - It also appends to an in-process **ring buffer (last 20)** exposed at **`GET /api/v1/dev/otp-inbox`**, with a matching dev-only `/dev/otp-inbox` page: a live list of recent codes with copy buttons, polling every 2 s. Conceptually Mailpit, for OTPs — you demo the real flow on one screen without a paid gateway or a second device.
    - **Safety is structural, not conditional.** The dev router is *never registered* when `ENV != development` — the guard lives in the app factory in `main.py`, not in an `if` inside the handler. There is no code path that can leak it, and §14 asserts a 404 in production mode. The frontend route is behind `import.meta.env.DEV`, so it is tree-shaken out of the production bundle entirely.
    - The buffer stores **masked** phone numbers, holds codes only until they expire, and is memory-only — nothing is persisted.
    - Startup **refuses to boot** on `ENV=production` + `OTP_CHANNEL=console` (§12.1). Keep this even though prod here is localhost: it is three lines and it is exactly the kind of detail that reads as competence.

---

## 10. Security checklist (MUST — each is a test)

- [ ] Argon2id for any secret at rest that needs hashing; SHA-256 for refresh-token lookup hashes.
- [ ] JWT secret ≥ 32 bytes from env; app **refuses to start** if it's missing or equals a known default in `ENV=production`.
- [ ] CORS: explicit origin allowlist from env. **Never `allow_origins=["*"]` together with `allow_credentials=True`** (a common FastAPI foot-gun that silently disables the header).
- [ ] Security headers via middleware: `X-Content-Type-Options: nosniff`, `Referrer-Policy: strict-origin-when-cross-origin`, `X-Frame-Options: DENY`, `Permissions-Policy: geolocation=(), camera=(), microphone=()`, HSTS (Caddy), and a real **CSP**: `default-src 'self'; img-src 'self' data: blob:; script-src 'self' https://accounts.google.com; frame-src https://accounts.google.com; style-src 'self' 'unsafe-inline'; connect-src 'self' https://accounts.google.com; object-src 'none'; base-uri 'self'`.
- [ ] Rate limits: `/auth/*` 20/min/IP · OTP send per §9.4 · uploads 30/hour/user · global 300/min/IP.
- [ ] Request body size cap (10MB) at the Caddy layer **and** in FastAPI.
- [ ] `/static/uploads` served with `Content-Disposition: inline`, `X-Content-Type-Options: nosniff`, and **no** script execution. Directory listing off.
- [ ] Path traversal impossible: upload paths are derived from a server-side hash, never from client input.
- [ ] Every admin route asserts `role == 'admin'` server-side. Frontend route guards are UX, not security — assume they're bypassed.
- [ ] IDOR: `cart_items` and `order_requests` are always filtered by `user_id` from the token, never by a client-supplied id alone.
- [ ] Phone normalized to E.164 before uniqueness checks (otherwise `0501234567` and `+994501234567` are two accounts).
- [ ] Logs are structured JSON and **never** contain tokens, OTP codes, full phone numbers (mask to `+99450***4567`), or emails at INFO level.
- [ ] `.env` gitignored; `.env.example` committed with placeholder values only.
- [ ] Dependency audit in CI: `pip-audit` + `npm audit --audit-level=high`.
- [ ] `/api/v1/dev/*` routers are registered **only** when `ENV=development`, gated in the app factory rather than inside handlers. A test boots the app with `ENV=production` and asserts `404` on `/api/v1/dev/otp-inbox` (§9.11).
- [ ] The dev OTP inbox stores masked phones, memory only, expiring entries — never a table, never a file.
- [ ] Seed fixtures contain no real personal data: `@example.com` addresses and non-routable `+994 50 000 00 XX` phones only (§8.1.1).

---

## 11. Performance budget (enforced in CI — build fails on regression)

**Frontend**
| Metric | Budget |
|---|---|
| Initial JS (gzip, `/` route) | **≤ 120 KB** |
| Initial CSS (gzip) | ≤ 20 KB |
| LCP (Moto G4 profile, Slow 4G) | ≤ 2.5 s |
| INP | ≤ 200 ms |
| CLS | ≤ 0.05 |
| Lighthouse Performance | ≥ 90 mobile |
| Lighthouse Accessibility | ≥ 95 |
| Long tasks during scroll | 0 over 50 ms |

**How to actually hit those:**
- Route-level `lazy()` + `Suspense` for every page. `/admin/**` is a **separate chunk tree** — a visitor must never download admin code.
- `LazyMotion` + `domAnimation` (~5KB) instead of importing all of `motion`.
- Icons imported individually (`import { ShoppingBag } from 'lucide-react'`), never `import * as Icons`.
- Images: server generates **AVIF + WebP + JPEG** at widths `320/480/768/1024/1600`; `<img srcset sizes>` with explicit `width`/`height` to reserve layout; `loading="lazy" decoding="async"` below the fold; `fetchpriority="high"` on the LCP image only. A **BlurHash** or dominant-color placeholder prevents CLS.
- React Query: `staleTime: 60_000` for catalogue data, `gcTime: 5 * 60_000`, `refetchOnWindowFocus: false`. Prefetch the product detail on card hover/touchstart.
- `content-visibility: auto` + `contain-intrinsic-size` on off-screen grid rows. Virtualize only if a list can exceed ~200 rows (admin tables) — use `@tanstack/react-virtual`.
- Debounce search input 250ms; abort in-flight requests with `AbortController`.
- Brotli precompression at build (`vite-plugin-compression2`); Caddy serves `.br` directly.
- Hashed asset filenames + `Cache-Control: public, max-age=31536000, immutable`. `index.html` is `no-cache`.
- Re-render discipline: React Compiler if stable, otherwise `memo` on `ProductCard`, stable `useCallback` handlers, and **zero context providers holding rapidly-changing values**.
- Run `rollup-plugin-visualizer` before every release; anything unexpected >15KB gets justified or removed.

**Backend**
| Metric | Budget |
|---|---|
| `GET /products` p95 | ≤ 80 ms |
| `GET /products/{id}` p95 | ≤ 40 ms |
| Any endpoint p99 | ≤ 400 ms |

- All ORM relations loaded with `selectinload` / `joinedload` — **an N+1 in a list endpoint is a build blocker.** Add a dev-mode query counter that fails a test if `GET /products` issues more than 3 queries.
- `COUNT(*)` for pagination is cached per filter-hash for 30s, or skipped entirely when using cursor mode.
- Category tree is loaded once and cached in-process with a version key bumped on mutation.
- Image processing is offloaded to `run_in_threadpool` — Pillow is CPU-bound and will block the event loop otherwise.
- Uvicorn with `--workers $(nproc)` behind Caddy. **Note:** with SQLite, writes serialize; WAL + `busy_timeout` handles this at this scale. If write contention ever appears, that's the signal to move to Postgres (§18).

---

## 11.1 Rendering strategy — SPA, deliberately, and why that is defensible

**Decision: client-rendered SPA. No SSR, no build-time prerendering.** Stated explicitly because it is exactly the kind of choice an examiner probes, and *"we didn't think about it"* is a bad answer where *"we evaluated it and scoped it out"* is a good one.

**What prerendering would have bought us:** crawler-visible HTML for product pages. That matters in two situations — organic Google ranking, and **link-preview cards** (WhatsApp, Telegram, Facebook and Instagram crawlers execute no JavaScript, so a shared SPA link renders as a blank grey card with no image, title, or price).

**Why neither applies here:** the deployment target is `localhost` in Docker. There is no public URL to crawl, no link to share, no search engine that can reach it. A prerender pipeline would add a headless-browser build step, a second CI stage, and a whole class of hydration-mismatch bugs — real, permanent complexity bought for a benefit that is structurally unreachable in this deployment. That is over-engineering by definition, and you asked me not to burn dev time on it.

**What we still do, because it is nearly free and demonstrates the competence regardless:**
- A `useDocumentMeta(title, description, image)` hook setting per-route `<title>`, `<meta name="description">`, and OG/Twitter tags. Client-side, so crawlers miss it — but it is correct for browser tabs, bookmarks and history, and it is the exact hook a prerender step would later consume unchanged.
- `sitemap.xml` and `robots.txt` generated at build from the product list.
- `hreflang` alternates for `az` / `en`, and a correct `<html lang>`.
- JSON-LD `Product` markup per product page.
- Genuinely semantic HTML and a real heading hierarchy — which §15 requires anyway.

**The upgrade path, documented so the trade-off is visibly reversible:** if this ever goes public, add `vite-plugin-ssg` or React Router framework mode and point it at the existing route + meta definitions. No component rewrite — the meta hook and the data-loading boundaries are already the right shape. Say precisely this if you are asked.

---

## 12. Docker & environments

### 12.1 `.env.example`

```env
# --- Core / Brand (§3.0 — these change on rebrand, nothing else does) ---
ENV=development                 # development | production
APP_NAME=FreeShop               # emails, OTP templates, page-title suffix
REQUEST_PREFIX=SR               # request_no format: <PREFIX>-YYYY-NNNN
API_BASE_URL=http://localhost:8000      # docker prod: http://localhost
FRONTEND_URL=http://localhost:5173      # docker prod: http://localhost
CORS_ORIGINS=http://localhost:5173      # docker prod: http://localhost
                                        # Behind Caddy the SPA and API are same-origin, so
                                        # CORS is barely exercised in prod. Keep it strict
                                        # anyway — a permissive prod CORS is a review finding.

# --- Security ---
JWT_SECRET=change-me-min-32-bytes-use-openssl-rand-hex-32
ACCESS_TOKEN_MINUTES=15
REFRESH_TOKEN_DAYS=30

# --- Database ---
DATABASE_URL=sqlite+aiosqlite:///./data/freeshop.db

# --- Google OAuth (free: console.cloud.google.com) ---
GOOGLE_CLIENT_ID=
GOOGLE_CLIENT_SECRET=

# --- Phone auth / OTP (BUILT BUT UNWIRED — see §18 before prod) ---
AUTH_PHONE_ENABLED=true         # master switch. false => Google-only auth, no OTP traffic.
                                # true + console channel is the demo setup (§18/W1)
OTP_CHANNEL=console             # console | telegram | email | sms
                                # 'console' is REFUSED at startup when ENV=production
OTP_TTL_SECONDS=300
TELEGRAM_BOT_TOKEN=
SMTP_HOST=smtp.gmail.com
SMTP_PORT=587
SMTP_USER=
SMTP_PASSWORD=                  # Gmail app password
SMTP_FROM=

# --- Uploads ---
UPLOAD_DIR=./static/uploads
MAX_UPLOAD_MB=5
MAX_IMAGES_PER_PRODUCT=8

# --- Seed ---
ADMIN_EMAIL=
ADMIN_PHONE=

# --- Frontend (VITE_ prefixed = PUBLIC, never put secrets here) ---
VITE_API_URL=http://localhost:8000/api/v1
VITE_GOOGLE_CLIENT_ID=
VITE_DEFAULT_LANG=az
VITE_AUTH_PHONE_ENABLED=true    # MUST mirror AUTH_PHONE_ENABLED; hides the phone tab in the UI
```

### 12.2 Local dev (no Docker)

```bash
cd backend && uv sync && uv run alembic upgrade head && uv run python seeds/seed.py
uv run uvicorn app.main:app --reload --port 8000
```
```bash
cd frontend && npm ci && npm run dev
```
Vite proxies `/api` → `http://localhost:8000` so cookies are same-origin in dev (this is what makes the httpOnly refresh cookie work locally).

### 12.3 Production Docker (local host)

Production here means **`docker compose up` on your own machine**, reachable at `http://localhost`. Everything below is still built to real production standards — multi-stage builds, non-root users, healthchecks, pinned bases — because that is the part an examiner reads and the part that would actually transfer to a server. What we *skip* is public-internet infrastructure (§11.1 logic: no DNS, no ACME, no CDN, no external object storage).

- **`backend/Dockerfile`** — multi-stage: `python:3.13-slim` builder with `uv` → slim runtime stage. **Non-root user.** Only `app/`, `alembic/`, `seeds/` and the venv are copied. `HEALTHCHECK` hits `/healthz`. Entrypoint runs `alembic upgrade head` before starting `uvicorn`, so a fresh clone is one command from working.
- **`frontend/Dockerfile`** — `node:22-alpine` build stage only; the `dist/` output is **copied into the Caddy image**. No Node process exists in production. This is worth pointing out in the defence: the frontend has zero runtime.
- **`caddy`** — serves `/` from the built SPA with fallback to `index.html`, reverse-proxies `/api/*` → `api:8000`, serves `/static/*` from the uploads volume with `Cache-Control: immutable`, and applies `encode zstd br`. **Listens on `:80` as `http://localhost`.** Uncomment `tls internal` for a self-signed padlock — but it triggers a browser warning unless you trust Caddy's local CA, so plain HTTP is the better demo default.
- **Volumes** — `freeshop_data` (the SQLite directory) and `freeshop_uploads` (product images). **Named volumes, never anonymous.** They hold the entire state of the shop: `docker compose down -v` erases the demo you spent a week seeding. Add `-v` to your mental blocklist.
- **Compose** — `api` (`restart: unless-stopped`, healthcheck, memory limit) and `caddy` (`ports: 80:80`, `depends_on: api: condition: service_healthy`). Two services, one file, no orchestrator.
- **Logging** — structured JSON to stdout, `json-file` driver capped at `max-size: 10m, max-file: 3` so a runaway loop cannot fill your disk mid-demo.
- **Backup** — a `backup` compose profile running `sqlite3 .backup` (the safe online-backup API, **not** `cp` on a live WAL database) plus a tar of uploads, writing to a host bind-mount and keeping 7 rotations. Low effort, and it answers the "what happens when the container dies" question directly.
- **`make demo`** (or an equivalent script) — one command that tears down, rebuilds, migrates, seeds, and opens the browser. Rehearse the defence with it. A live demo that begins with debugging a container is a self-inflicted wound.

**Parity note:** the dev and prod stacks differ in exactly three ways — Vite dev server vs static files, `--reload` vs workers, and origin (`:5173` vs `:80`). Everything else, including the database engine and the image pipeline, is identical. State this if asked about dev/prod drift; it is the honest and favourable answer.

---

## 13. Build phases

Each phase ends with a working, demoable state. Do not start N+1 until N's acceptance criteria pass.

| # | Phase | Deliverable | Done when |
|---|---|---|---|
| **0** ✅ | Scaffold | Repo layout (§5), both apps booting, `.env.example`, **brand layer §3.0** (`brand.config.ts`, placeholder `Logo.tsx` wordmark, `transformIndexHtml` hook, `brand:assets` script, the no-brand-literal lint rule), ruff/eslint/prettier/mypy/tsconfig strict, CI skeleton, Docker files. | `npm run dev` and `uvicorn` both start clean; CI green. Changing `brand.name` updates the nav, `<title>`, and OG tags with no other edit. |
| **1** ✅ | Design system | `tokens.css` (azure **+ bronze**), `glass.css`, `useGlassTier`, Tailwind v4 `@theme` wiring, `Button/Input/Badge/Chip/Dialog/Sheet/Toast/Skeleton`, `ProductCard` per §3.6.1, theme switch, Inter self-hosted. A `/dev/kitchen-sink` route rendering everything. | Kitchen sink correct in all **4** accent×theme combos, plus reduced-transparency and reduced-motion. Zero color outside the token set. `ProductCard` renders a 3000×2000 and a 400×400 image in the same row with identical card geometry. |
| **2** ✅ | i18n skeleton | i18next wired, `az.json`/`en.json`, `LangSwitch`, `Intl` formatters, key-parity CI script, `no-literal-string` lint on. | Toggling language changes every string in the kitchen sink. CI fails if a key is added to only one file. |
| **3** ✅ | DB + migrations + fixtures | All models from §8, Alembic initial migration, FTS5 triggers, and the **full §8.1 seed system**: `--tier=minimal\|demo\|stress`, deterministic RNG + fixed `SEED_EPOCH`, `data/*.json` fixtures, committed `assets/` images, `--with-images` running the real §9.7 pipeline. | `alembic upgrade head` on an empty file produces the full schema; `alembic downgrade base` is clean. **`seed.py` run twice in a row produces identical data and no duplicates.** Two machines produce byte-identical rows. `--tier=demo` yields 45 products including all 15 named edge cases (§8.1.5) — verified by a test that asserts each one exists. Seeded admin passes the §9.3 publish gate with `AUTH_PHONE_ENABLED=false`. |
| **4** ✅ (server) | Auth backend | Google verify, JWT issue/refresh/rotate/revoke, `deps.py` guards, rate limits. **OTP service + all 4 channel adapters written and fully tested, but gated behind `AUTH_PHONE_ENABLED=false`** — when off, `/auth/phone/*` and `/users/me/phone/*` return `404` (not 403 — an off feature should not advertise itself) and the UI hides the phone tab. | Google flow green end-to-end. OTP suite passes against the `console` adapter: expired code, wrong code ×6 → lockout, resend invalidates prior code, per-phone and per-IP limits, E.164 normalization, constant-time compare. Flipping the flag to `true` + setting `OTP_CHANNEL=telegram` enables the whole path with **no code change** — proven by a test that runs the suite in both flag states. App refuses to boot with `ENV=production` + `OTP_CHANNEL=console`. **The §9.11 dev OTP inbox works end to end** — boxed stdout line, `/dev/otp-inbox` page live-updating, and a test booting with `ENV=production` gets `404` on the dev router. |
| **5** ✅ | Catalogue backend | Categories tree, product CRUD, filters/sort/pagination/cursor, FTS5 search, image pipeline (resize → AVIF/WebP/JPEG + blurhash). **As built: JPEG only, no blurhash; offset pagination; folded-LIKE search rather than FTS5 — see §13.6/D24 and D8.** | Query-count test passes (≤3 queries for `/products`). p95 under budget with 5k seeded products. |
| **6** ✅ | Cart + requests backend | Cart CRUD, order-request transaction, idempotency, admin request management, stats, settings/contact. | Transaction test: concurrent double-submit produces one request. Deleted-product path returns `PRODUCT_UNAVAILABLE`. |
| **7** ✅ | Frontend shell | Router, API client with token refresh interceptor + request dedup, React Query provider, auth store, layouts, desktop pill nav + mobile tab bar, category menu, footer, 404, error boundary. | Navigation works on both breakpoints; refresh-on-401 retries the original request exactly once. |
| **8** ✅ | Catalogue frontend | Home (featured rail + recent), `/products` with filter panel / bottom sheet, `ProductCard`, grid, `/products/:slug` with embla gallery + related, `cmdk` search palette. | Lighthouse mobile ≥ 90 on `/` and `/products`. No layout shift on image load. |
| **9** ✅ | Auth + cart frontend | Google button, phone/OTP flow with resend timer, `PhoneVerifyModal` triggered by the 403 interceptor, **`AuthInviteSheet` + pending-intent replay (§9.8)**, cart drawer + page, quantity stepper with optimistic updates. | Guest clicks "Səbətə at" → invite sheet → signs up → item is already in the cart, drawer open, zero re-clicks. Intent survives the Google redirect round-trip. Optimistic update rolls back on server error. |
| **10** ✅ | Account + request flow | Profile, phone add/change, request submission screen, success screen with seller contacts + WhatsApp deep link, `/profile/orders` history. | End-to-end Playwright test: browse → add → login → submit → see request in history. |
| **11** ✅ | Admin panel | Admin shell, product table (with an `EN` coverage marker) + create/edit form (multi-image DnD reorder, main-image pick, AZ/EN tabs where **EN never blocks saving**), category manager, requests table with status changes + detail drawer, users list, stats dashboard, and a full **`/admin/settings`** page covering contacts, appearance (accent + theme), language (`default_lang`, `enabled_langs`) and all bilingual page copy per §7.3. | Admin can run the entire shop — including switching accent, default language and every static text — without touching the DB or rebuilding. A product saves with the EN tab completely empty and renders correctly in both languages. Non-admin gets 403 from the API even with a forged frontend route. |
| **12** ◐ | Hardening & defence prep | Security checklist §10 all ticked, perf budgets §11 met, empty/loading/error states everywhere, `prefers-reduced-*` audited, keyboard-nav audit, metadata hygiene per §11.1 (per-route title/OG, `hreflang` az/en, `sitemap.xml`, `robots.txt`, JSON-LD `Product`), full `docker compose up` run from a clean clone, backup verified by an **actual restore**, and the whole of **§18 W1–W10** closed — including 30–50 real seeded products and the written deliverables. | A clean `git clone` → `docker compose up` → working shop at `http://localhost`, with no manual step outside the README. A restore from backup into a fresh container reproduces the shop. No placeholder asset, contact detail, or secret remains. The `make demo` path has been rehearsed end to end at least twice. |

---

### 13.1 Phase 0 — as built (2026-08-21)

Phase 0 is complete and every acceptance criterion passes. Recorded here because the gap between a plan and its execution is where the interesting decisions live — and because §2 promised that deviations get written down rather than absorbed silently.

**Verified green:** `ruff` + `ruff format` + `mypy --strict` + 16 backend tests · `eslint` + `tsc --noEmit` + `prettier` + 10 frontend tests + production build · initial JS **73.4 kB / 120 kB** gzip, CSS **4.5 kB / 20 kB** · Alembic upgrade/downgrade round-trip · uvicorn and Vite both boot clean · SPA reaches the API through the Vite proxy · all four accent×theme combinations verified in a live browser.

**Deviations from the plan as written, and why:**

| # | Planned | As built | Reason |
|---|---|---|---|
| B1 | TypeScript 5.9 / ESLint 9 assumed current | TS **5.9.3**, ESLint **9.39.5**, both pinned | TS 7 and ESLint 10 are released, but `typescript-eslint` caps TS at `<6.1.0` and `eslint-plugin-jsx-a11y` caps ESLint at 9. Taking the newest of each would silently disable type-aware and a11y linting. Newest-possible beats newest. |
| B2 | `@vitejs/plugin-react-swc` | `@vitejs/plugin-react` | Vite 8 emits an explicit recommendation against `-swc` when no SWC plugins are used. |
| B3 | `orjson` + `ORJSONResponse` | native FastAPI serialisation | Deprecated in FastAPI 0.141 and now slower than the built-in path. Removed a dependency and a deprecation warning. |
| B4 | `uv` for Python deps | `pip` + `venv`, `uv` optional | `uv` was not installed. A scaffold requiring a tool the developer lacks is not a scaffold. |
| B5 | `@fontsource-variable/inter` imported wholesale | explicit `@font-face` for latin + latin-ext only | The package's `index.css` pulls Cyrillic, Greek, Greek-ext and Vietnamese: **218 kB → 133 kB** of woff2 for subsets this project will never render. Coverage for `ə ğ ı İ ö ü ç ş` was verified against the unicode ranges before cutting. |
| B6 | `shortName` a separate brand field | derived from one `BRAND_NAME` constant | The CI rebrand check caught it: `shortName` was a **second** independent literal, so a rename needed two edits and forgetting the second left a stale name in the PWA manifest. Exactly the drift §3.0 exists to prevent — found by the test, not by review. |
| B7 | (not anticipated) | `tokens.css` must contain **no `@layer`** | **The most valuable catch of the phase.** The dark and bronze overrides were wrapped in `@layer theme` while the base `:root` was unlayered. Unlayered styles beat layered ones *regardless of specificity*, so dark mode and the bronze accent were silent no-ops — CSS that reads as completely correct and does nothing. Found only by reading computed styles in a live browser. Now guarded by `tokens.test.ts`. |

**Beyond the plan's phase-0 scope, because they were cheap and protect later phases:** the full OKLCH token system with both accents (§3.2) rather than a stub; a bundle-budget script that fails CI on regression, so §11 is enforced rather than aspirational; a CI job that renames the project to a nonsense string, rebuilds and greps the output, so §3.0's rebrand promise is tested rather than asserted; and `tokens.test.ts`, which pins the chroma ceiling, the "exactly six accent tokens" rule and the no-`@layer` rule from B7.

**Not yet built (correctly deferred):** i18next (phase 2), all data models and migrations (phase 3), auth (phase 4), and the glass surfaces themselves (phase 1) — phase 0 ships the token layer they will consume, not the components.

---

### 13.2 Phase 1 — as built (2026-08-21)

Design system complete: glass tier system, component primitives, product card, glass navigation, and a `/dev/kitchen-sink` route rendering everything. **The Docker stack from §12.3 was also built and run end to end** — previously unverified.

**Verified green:** `eslint` + `tsc` + `prettier` + **18** frontend tests · `ruff` + `mypy --strict` + **17** backend tests · initial JS **74.6 kB / 120 kB**, CSS **7.5 kB / 20 kB** · `docker compose up` serving a working shop with the API healthy · nine committed screenshots covering light/dark × desktop/mobile × azure/bronze plus the reduced-transparency fallback.

**Bugs found by actually running things — none would have been caught by review:**

| # | Found by | Bug | Fix |
|---|---|---|---|
| C1 | Rendering the page in Chromium | **Currency formatting was wrong for every visitor.** Chromium's ICU has no AZN pattern, so prices rendered `AZN 489.00` instead of `489,00 ₼`. Node's fuller ICU hid it — a unit test would have passed. | Explicit formatter (§7.1). Exact-string tests now assert the AZ and EN output, including that `AZN` never appears. |
| C2 | Starting the container | The production guard refused to boot on `OTP_CHANNEL=console` **even with `AUTH_PHONE_ENABLED=false`**, blocking a legitimate Google-only deploy over a setting that has no effect. | Guard now fires only when phone auth is actually on. Both branches tested. |
| C3 | `curl -I` on a built asset | **Asset caching was silently disabled.** The Caddy `@hashed` matcher expected `name.HASH.ext`; Vite emits `name-HASH.ext` with a dash, so nothing ever matched and every asset was served uncached. | Corrected the regex. Verified `immutable` on assets and `no-cache` on `index.html`. |
| C4 | Listing the web volume | The build service copied into the volume **without clearing it**, so every past build's content-hashed chunks accumulated forever. | `rm -rf /out/*` before copy. Safe: the volume holds build artefacts, never data. |
| C5 | Binding the host port | Port 80 was held by a Windows system service, and 8080 by another project. | Host port is now `${HTTP_PORT:-8090}`, and the Caddy site block binds `:80` rather than a hostname so any host port works. |

**Design decisions worth recording:**

- **Glass is CSS, exactly as §3.5.1 argued.** The nav pill is `min(100% - 32px, 1440px)` and the drawer is `min(420px, 90vw)`; a px-sized lens library would need a `ResizeObserver` per surface. Tier A/B/C is selected once by `useGlassTier()` and written to `data-glass` on `<html>`, so components never branch on it.
- **Product cards are opaque, deliberately.** They live in a scroll container, where blur re-samples every frame. The kitchen sink renders glass over a deliberately garish gradient so contrast is judged against the worst case, not a flat mock.
- **Demo images are generated, not downloaded** — offline-safe, and their aspect ratios (3000×2000 down to 400×400) exist specifically to prove the `object-fit: contain` decision. With `cover`, the wide shots lose their subject.
- **Screenshots double as the §14 visual baseline.** The harness scrolls each page first, because `loading="lazy"` plus `content-visibility: auto` otherwise capture empty card slots — a false baseline is worse than none.

**Deferred as planned:** i18next wiring (phase 2 — AZ strings are currently inline), all data models (phase 3), auth (phase 4). The command palette, category mega-menu and cart drawer are stubs in the nav; they land with the routes that need them.

---

### 13.3 Interaction pass — as built (2026-08-21)

Phases 7 and 8 were **pulled forward out of order**, because phase 1 shipped a design system in which almost nothing was clickable. That was the wrong sequencing: a catalogue you cannot navigate is not reviewable, and "it's scheduled for phase 7" is a poor answer to "why doesn't this button work". Routes, cart, search and account UI now all function.

**Built:** `/products` (URL-driven filter, sort, in-stock) · `/products/:slug` with related items · `/cart` with the request form and confirmation · `/contact` · cart drawer with focus trap · `cmdk` command palette on Ctrl/Cmd+K · nav category menu · account menu · sign-in / sign-up sheet · the §9.8 guest gate with pending-intent replay · working mobile tab bar.

**Still mocked, and labelled as such in the code:** `authStore` issues no token and calls no server (phase 4 replaces it), and `catalogue.ts` queries fixtures rather than `GET /products` (phase 5). Both mirror the server contract so the swap is a change of implementation, not of surface.

#### The verification gap this exposed

Ten thousand words of types, lint rules and unit tests did not catch a single one of the bugs below, because **none of them are expressible as a unit test**. `scripts/smoke.mjs` now drives the real UI with Playwright — 38 assertions, run against both the dev server and the Docker stack.

| # | Bug | How it was found | Why it mattered |
|---|---|---|---|
| D1 | **Every nav dropdown was unclickable.** `contain: paint` on `.glass` clips descendants to the element's box, so the category and account menus rendered in the DOM but were painted-clipped; `elementFromPoint` on a menu item returned `<main>`. | Smoke test click timeout, confirmed with `elementFromPoint` | Both menus were completely dead for real users. Nothing in the DOM looked wrong — the elements were all there. |
| D2 | **Hero CTAs were inert.** Rendered as buttons with no handler. | Smoke test step 1 | Exactly the complaint that prompted this pass. |
| D3 | **Cards jumped while scrolling.** `content-visibility: auto` with `contain-intrinsic-size: 340px` against a real card height of ~524px. | Playwright reporting clicks intercepted by shifted content | Visible layout shift, and clicks landing on the wrong element. An "optimisation" that was a net loss on a catalogue this size. |
| D4 | **A pale strip down the right edge behind every modal.** `scrollbar-gutter: stable` is painted by `<html>`, but `position: fixed` layers are sized to the viewport *without* the gutter. | Reading a rendered screenshot | Cosmetic, but glaring in dark mode. |

**Rules that came out of this:**

- `contain: paint` is now applied **per surface**, never on the `.glass` base class — only to surfaces with nothing that escapes their box (tab bar, drawer, palette, sheet, toast).
- No `content-visibility` without an intrinsic size measured from a real rendered element, and not before virtualisation is genuinely needed.
- **A control is not "done" until the smoke test clicks it.** Types and lint prove a button compiles, not that it does anything.

#### Two UX corrections

- **Theme is a two-state toggle now, not a three-state cycle.** `system` remains the stored default so a first visit follows the OS, but the button only ever moves between light and dark. Cycling system → light → dark on one icon made the next click unguessable. The icon shows the destination, not the current state.
- **The person icon is an account menu.** Signed out: sign in / sign up. Signed in: identity, phone-verified state, requests, sign out. It previously navigated to `/contact`, which was arbitrary.

---

### 13.4 Database and catalogue API — as built (2026-08-21)

Phase 3 complete and the read half of phase 5. The frontend now runs entirely on the API: `demoData.ts` and the client-side `catalogue.ts` are **deleted**, not bypassed.

**Built:** ten tables with the full §8 schema · two reversible Alembic migrations · the §8.1 seed system (deterministic RNG + fixed `SEED_EPOCH`, idempotent, `--tier minimal|demo|stress`, `--reset`) · `GET /categories` (two-level tree with rolled-up counts) · `GET /products` (filter, search, sort, pagination) · `GET /products/{slug}` · `GET /products/{slug}/related` · `GET /meta/contact` reading the admin `settings` table · TanStack Query on the client with a shared cache.

**Verified:** 28 backend tests · `ruff` + `mypy --strict` clean · migrations round-trip to base and back · seed run twice produces identical counts · **38/38 interaction checks against the Docker stack**, now serving real database rows · initial JS 108.5 kB / 120 kB.

**Bugs found by running it:**

| # | Bug | Found by | Why it mattered |
|---|---|---|---|
| E1 | **`/categories` returned 500.** The serializer recurses into `child.children`, but only one level was eager-loaded — in async SQLAlchemy a lazy load raises `MissingGreenlet` rather than quietly issuing a query. | First curl of the endpoint | The whole category nav was dead. Fixed by loading both levels, which is the complete depth anyway (§D11). |
| E2 | **Diacritic-insensitive search regressed.** The old client-side filter folded `ə`→`e`; SQLite `LIKE` cannot, so "ketan" stopped finding "Kətan". | Smoke test | Azerbaijani is routinely typed without diacritics — this is most real queries, not an edge case. Fixed with a folded `search_text` column (`app/core/text.py`), populated on write and matched against a folded needle. |
| E3 | **Migration failed on a populated table.** SQLite cannot add a `NOT NULL` column without a `server_default`. | Running the migration | Would have broken every existing deployment, not a fresh clone. |
| E4 | **`--reset` failed on the self-referential category FK.** Parents were deleted before children under `ON DELETE RESTRICT`. | Running `--reset` | The reset path is the one people use right before a demo. |
| E5 | Alembic's `ruff` post-write hook aborted revision generation with an entrypoint lookup error. | Generating the first migration | Removed the hook; migrations are formatted by the normal `ruff format` pass and checked in CI. |

**Decisions worth recording:**

- **`ProductImage.path` holds either a relative path or an absolute URL**, with `is_remote` deciding how it serialises. The seed uses hotlinked photography; admin uploads will be local. One column, no special-casing at the call site.
- **A parent category slug includes everything beneath it.** Clicking "Ev və bağça" returning nothing because the products are all in "Mebel" would be indefensible.
- **Filter state keys on slugs, not display names**, so URLs survive a rename or a language switch.
- **The `settings` table is a key/value store, seeded from `DEFAULT_SETTINGS`.** Contacts, appearance, default language and page copy all change without a migration — which is the whole point of letting the admin edit them.
- **`refresh_search_text()` is explicit, not a hook.** An ORM event would be invisible; a method that must be called is greppable, and the seed and future admin writes both call it.

**Still mocked:** `authStore` issues no token (phase 4), and the cart plus order requests are client-side (phase 6). Both mirror the server contract so the swap is a change of implementation, not of surface.

---

### 13.5 Auth backend — as built (2026-08-21)

Phase 4 server-side complete. Phone/OTP login, Google verification, JWT access tokens, and refresh rotation with reuse detection all work against a live server. The frontend still uses the mock store; wiring it is the next step.

**Built:** `POST /auth/google` · `/auth/phone/send-otp` · `/auth/phone/verify-otp` · `/auth/refresh` · `/auth/logout` · `GET|PATCH /users/me` · `/users/me/phone/send-otp|verify-otp` · four OTP channel adapters · `get_current_user` / `require_admin` / `require_phone_verified` guards.

**Verified:** 52 backend tests (24 new, targeting failure modes rather than happy paths) · `ruff` + `mypy --strict` clean · live end-to-end run: send → read code from the dev inbox → verify → `/users/me` → refresh rotates → replaying the old cookie returns `REFRESH_REUSED`.

**Four real bugs, each found by running rather than reading:**

| # | Bug | Severity | Found by |
|---|---|---|---|
| F1 | **`create_app(settings)` was a lie.** Every service reads configuration through `get_settings()`, which returned the cached ambient `.env` — so the settings passed in configured only the FastAPI object. Tests asking for `auth_phone_enabled=True` got 404s from the file on disk. | Structural | Every auth test failing at once |
| F2 | **The OTP attempt counter was rolled back on failure.** `verify_code` flushed the increment, then the endpoint raised, the request transaction unwound, and the count vanished — so the lockout could never fire and a six-digit code stayed brute-forceable indefinitely. The counter now **commits** before comparing. | **Security** | The lockout test returning 400 instead of 429 |
| F3 | **SQLite does not persist timezones.** `DateTime(timezone=True)` hands back a naive datetime, so every `expires_at <= now` comparison raised `TypeError`. That is refresh-token and OTP expiry, not a test artefact. Fixed with a `UtcDateTime` type decorator that rejects naive input on write and attaches UTC on read. | High | Whole suite failing after F1 was fixed |
| F4 | **The boxed OTP banner crashed the request on a Windows console.** cp1252 cannot encode the box-drawing glyphs, so `print()` raised `UnicodeEncodeError` and `/auth/phone/send-otp` returned 500. Tests missed it because pytest captures stdout differently. stdio is now forced to UTF-8 with `errors="replace"`, plus an ASCII fallback. | High | Running the flow with curl against a live server |

F2 is the one worth remembering: the code was correct in isolation and wrong in a transaction. Nothing short of exercising the lockout would have caught it.

**Decisions worth recording:**

- **SHA-256, not argon2, for refresh tokens and OTP codes.** They are high-entropy random values, not user-chosen passwords — there is nothing to brute-force, and a deliberately slow hash would only tax every request.
- **`verify_code` raises; it never returns a boolean.** A caller who forgets to check a boolean silently authenticates everyone.
- **A disabled feature 404s rather than 403s.** With `AUTH_PHONE_ENABLED=false` the phone routes do not advertise their own existence.
- **The user row is re-read on every request** rather than trusting the token's claims, so a deactivated account loses access immediately instead of when its token expires.
- **Phone numbers are normalised to E.164 before any uniqueness check.** `0501234567` and `+994501234567` are the same person; without this the unique constraint means nothing. Seven parametrised cases cover the formats people actually type.

**Still open in phase 4:** the frontend `authStore` remains mocked, so nothing in the browser uses these endpoints yet. Telegram delivery raises `NotImplementedError` until `users.telegram_chat_id` exists — deliberately, because a channel that silently fails is worse than one that is honestly switched off.

---

### 13.6 Catalogue writes, admin panel and i18n — as built (2026-08-25)

Closing phases 2, 5 (write half), 10 and 11, plus the parts of 12 that are code rather than
rehearsal. Written the same way as 13.1-13.5: what was built, what deviated, and what broke.

#### What landed

| Area | Shipped |
| --- | --- |
| **Catalogue writes** | `POST/PATCH/DELETE /admin/products` with soft delete and restore, `POST/PATCH/DELETE` on product images, full category CRUD, `GET /admin/users`, `GET/PATCH /admin/settings`, `GET /admin/stats` extended with a 30-day series |
| **Upload pipeline** | Magic-byte sniff → decode → re-encode to JPEG → EXIF dropped → content-hash sharded path. 5 MB and 8-per-product caps, enforced server-side |
| **Admin panel** | Shell + guard, product table and form (AZ/EN tabs, image manager), category manager, request queue with a detail panel, users list, settings, dashboard |
| **Account** | `/profile` (name, language, avatar, phone verification) and `/profile/orders` |
| **i18n** | 357 keys × 2 languages, a working `AZ`/`EN` switch, `<html lang>`, per-profile persistence, and a CI parity gate |
| **Hardening** | Route rate limits + body-size cap, the real error envelope in OpenAPI, error states on every page that fetches |

#### Deviations, with reasons

**D18 — i18next replaced with a ~1 kB in-house translator.** §7.1 named i18next. i18next +
react-i18next + the language detector cost roughly 15 kB gzipped; the initial-JS budget (§11) had
about 9 kB of headroom. Raising a performance budget to fit a library is the trade the budget exists
to prevent. Everything else in the §7.1 contract is kept exactly: flat dot-namespaced keys, both
files carrying the same key set (enforced by `npm run i18n:check`, which also compares
`{placeholder}` names), AZ as default and fallback, ICU-style `_one`/`_other` plural keys, and `Intl`
for every number and date. The AZ dictionary is bundled because it is the fallback for every missing
key; **EN is a lazy chunk** (4.6 kB), loaded before the switch completes, so an Azerbaijani-speaking
visitor never downloads the English strings.

**D19 — language detection order changed.** §7.1 put `navigator.language` ahead of the site default.
§7.3 defines `default_lang` as "the language a first-time visitor sees before any preference
exists", and since most browsers in this market report `en-US`, consulting navigator first would
have made that admin setting a no-op for nearly everyone. Order as built: `?lang=` → `localStorage`
→ site `default_lang` → `navigator.language` → `az`, every step constrained to `enabled_langs`.

**D20 — no drag-and-drop image reorder.** §13 phase 11 asked for DnD. Shipped instead: pick the main
image (one click), delete, and a server-side `sort_order` the API accepts. DnD that works with a
keyboard and a screen reader is a component in its own right, and reordering eight images is not the
part of this panel anyone spends time in. The endpoint is there when it is.

**D21 — `/admin/users` is read-only.** No promote/demote, no deactivate. §9.9 says the admin account
comes from the environment and there is no self-service admin registration; a panel that can widen
its own access contradicts that, and nothing in the brief needs it.

**D22 — settings are saved as a changed-keys patch**, not the whole map. A blanket PATCH would
rewrite every row on every save, so two people editing different sections would overwrite each
other with values neither had touched.

**D24 — the image pipeline emits JPEG only, and no blurhash.** §13 phase 5 asked for
AVIF/WebP/JPEG plus a blurhash placeholder. As built: every upload is decoded and re-encoded to a
single progressive JPEG capped at a 1600 px long edge. The three reasons, in order of weight: the
security property that matters is *decode and re-encode* (it strips EXIF and neutralises polyglot
files) and that is format-independent; serving three formats needs `<picture>` plumbing and a
content-negotiating proxy, which is a build-out with no visible payoff on a localhost demo; and
`blurhash` is a dependency whose entire job is a placeholder the design already solves with a
fixed-aspect skeleton. The column is nullable and the encoder is one function — adding formats later
touches `image_service.store` and nothing else. **Cursor pagination and FTS5 are likewise not built**
(offset paging, and the folded-LIKE search of D8); both are behind signatures that can absorb them.

**D23 — `GET /meta/config` now carries appearance and language**, and the SPA fetches it once
before the first paint, alongside the session refresh that already blocks render. This is what makes
"the admin can switch accent, default theme and default language with no rebuild" (§7.3, §11) true
rather than aspirational. It costs no extra wall-clock time and removes a duplicate fetch the
sign-in sheet used to make on every open.

#### Bugs found by running it

| Bug | Impact | Found by |
| --- | --- | --- |
| **Chromium renders `month: 'short'` for `az-AZ` as `M08`** | Every date in the panel read "2026 M08 25". Node's fuller ICU renders it correctly, so a unit test passed while the screen was wrong — the *same class of bug* as the AZN currency one in §13.2/C1, found the same way: by reading a rendered page | Reading a screenshot of the request queue |
| **The bundle-budget script counted lazy chunks as initial** | Its rule was a filename regex, `/.*Page-/`. Every admin chunk is named `Admin*`, so the build failed claiming 130 kB when the real initial payload was 110 kB. Now read from the built `index.html` — the entry script plus its `modulepreload` links, which is what the browser actually fetches | The admin panel failing CI on the day it landed |
| **Language detection ran before the config arrived** | `detect()` executed at module-evaluation time, so `enabled_langs` was still unknown and a stored `en` preference was rejected as "not enabled". The switch worked and then forgot itself on the next page load | Reloading the page after switching |
| **`create_all` built a half-empty schema** | The test conftest imported `Base` but not the models, so a test file run *on its own* got only the tables some other file happened to import first. Passed in the full suite, failed alone | Running the new rate-limit tests as a single file |
| **A saved refresh token cannot be replayed** | The screenshot script signed in once and restored the saved state for later shots; refresh tokens rotate and presenting a used one revokes the family (§6.3), so every capture after the first showed the signed-out guard. Fixed by saving the state *after* each shot, when the token in it is fresh | Reading the second admin screenshot |
| **The upload rate bucket covered the whole `/admin/products` prefix** | Written for image uploads, it matched every read of the product table and the review queue too - sixty requests an hour for a working administrator. Matched by path suffix now | The interaction suite tripping it in under a minute |
| **The sign-in rate bucket also covered `/auth/refresh`** | plan.md 10 says "`/auth/*` 20/min/IP". Every page load calls refresh once to restore the session, so the interaction suite - 30 page loads in under a minute - signed itself out mid-run, and behind a carrier NAT real visitors would have too. Split: the credential-taking endpoints keep the tight bucket, refresh falls under the global one | The suite going red on the commit that added the limiter |
| **The smoke suite pinned a translated `aria-label`** | `button[aria-label="Artır"]` stopped matching the moment i18n renamed it. Now targeted structurally | The suite failing on the i18n commit |

#### One operational note

The interaction suite and the screenshot script both sign in as the seeded
administrator, and OTP sends are capped at **three per number per fifteen
minutes** and **ten per IP per hour** (§9.4). Running either three times in a
row exhausts that budget - which is the limiter working. Both scripts now
detect it and report a **skip with the reason** rather than a cascade of
failures, because a suite that cries wolf is a suite nobody reads.

**The lesson, restated:** every one of these was found by *running* the thing — in a browser, against
a live server, or by looking at a rendered image. `ruff`, `mypy`, `eslint` and `tsc` were green
throughout.

---

### 13.7 Give-away board — as built (2026-08-25)

**The product changed shape, and this is the record of it.** What was
specified as a single-owner catalogue with a request flow is a **community
give-away board**: people list things they no longer use, an administrator
reads each listing before it appears, and most items are free.

Nothing in the mechanism was thrown away — the cart, the request transaction,
the snapshots, the contact hand-off all still do exactly what §9 says. What
changed is who may add a listing, and what has to happen before anyone sees it.

**D25 — listings are submitted by visitors and moderated before publication.**

| Piece | As built |
| --- | --- |
| `products.status` | `pending` \| `approved` \| `rejected`, plus `moderation_note` and `reviewed_at`. **The column defaults to `pending`**, so a code path that forgets to set it publishes nothing |
| `Product.public()` | One class method - approved AND not deleted - used by every public query. A gate applied in nine places out of ten is not a gate; it is a leak with good intentions |
| `POST /products` | Any signed-in visitor with a verified phone. Creates a `pending` listing owned by them |
| `POST /products/{id}/images` | The **owner's** photo upload. Same sniff-and-re-encode pipeline as the admin route (§9.7) - a second, more relaxed upload path is the one that gets exploited |
| `GET /products/mine` | Their own listings in every state, including rejected ones and the reason why |
| `POST /admin/products/{id}/moderate` | Approve or reject, with a note. Reversible in both directions |
| `POST /admin/products` | Unchanged, and publishes directly: an administrator posting **is** the review |

**Why `pending` is the default rather than `approved`.** Failing closed costs
one line in the seed and one in each test fixture. Failing open costs a
stranger's advert on the front page. The trade is not close, and the test
suite proved the direction the moment it landed: twenty-one existing tests
went red because their fixtures had never said they were published.

**D26 — zero is a price.** Most listings here are free, so `price_minor = 0`
renders as **"Pulsuz" / "Free"**, never `0,00 ₼`, and the submission form has
the free box ticked before anyone touches it. One `<Price>` component owns
that decision; leaving it to each call site is how half an app says one thing
and half says the other.

**D27 — the phone gate stays, and now earns its keep.** §9.3 required a
verified number to publish. Under the old shape that guarded the shop owner's
own listings, which was close to pointless. Here it guards a promise to meet
a stranger and hand them a chair, which is exactly what it was written for.

**D28 — no store owners, no vendor roles.** Explicitly confirmed with the
owner: there is one administrator, appointed from the environment (§9.9), and
everybody else is a neighbour with something to give away. `/admin/users`
stays read-only - a panel that can widen its own access contradicts §9.9.

#### Still open

**Who does a taker contact?** Today the request confirmation shows the
**site's** contact channels (§9.1), which was right when one seller owned
every item. On a board of many givers the natural answer is the giver's own
number - but publishing somebody's phone to anyone who submits a request is a
decision about their privacy, not a refactor, so it is flagged here rather
than guessed at. The moderation queue already shows the giver's number to the
administrator, which is enough to run the site by hand in the meantime.

---

## 14. Testing

- **Backend unit/integration** (`pytest` + `httpx.ASGITransport`, in-memory SQLite per test): every endpoint's happy path + auth failure + validation failure. Target ≥ 80% on `services/`.
- **Seed tests:** `seed.py` is idempotent (run twice → identical row counts and identical content hashes); `--tier=demo` produces all 15 named edge cases from §8.1.5; the soft-deleted-product fixture makes `POST /order-requests` return `PRODUCT_UNAVAILABLE`; no fixture contains a routable phone or a non-`example.com` email.
- **Security tests** (explicit, named): IDOR on cart/orders, admin escalation attempt, OTP brute force, refresh reuse, upload of a `.php`/`.svg` renamed to `.jpg` (use `seeds/assets/fake.jpg`), the dev router returning 404 under `ENV=production`, oversized upload, path traversal in image ids, CORS preflight from a foreign origin.
- **Frontend unit** (`vitest` + RTL): cart store reducers, pending-intent lifecycle (set → survive redirect → replay once → clear), formatters, `useGlassTier` tier selection, i18n fallback.
- **Interaction smoke** (`npm run smoke`, Playwright): 38 assertions driving every control in the real UI — navigation, filters, sort, cart, drawer, palette, menus, auth gate, theme, mobile tab bar — plus a zero-console-errors check. Run against **both** the dev server and the Docker build; a control that does nothing fails the run. This is the layer that catches "the buttons don't work", which no type-checker or unit test can (§13.3).
- **E2E** (`playwright`, free): the 3 critical journeys — (a) guest browse → search → product detail; (b) login → add to cart → submit request → see contacts; (c) admin login → create product with 3 images → verify it appears publicly in both languages.
- **Visual**: Playwright screenshots of the kitchen sink in 4 modes (light/dark × normal/reduced-transparency) committed as baselines.
- **Perf**: `lighthouse-ci` in GitHub Actions against a preview build, asserting the §11 budgets.

---

## 15. Accessibility (MUST)

- Contrast: **≥ 4.5:1** for body text, **≥ 3:1** for large text and UI borders — verified **against the glass surface's worst-case backdrop** (a bright product photo), not against a flat mock. This is the #1 way glass UIs fail WCAG. Where a glass surface can sit over arbitrary imagery, raise its tint opacity until the worst case passes.
- Every interactive element is keyboard-reachable, in a logical order, with a **visible** focus ring: `outline: 2px solid var(--accent); outline-offset: 2px`. Never `outline: none` without a replacement.
- Radix handles dialog focus trapping, `aria-modal`, and restore-focus — don't reimplement.
- Icon-only buttons get `aria-label` (translated).
- Live regions for cart-add and toast announcements.
- Forms: `<label for>` on every input, `aria-invalid` + `aria-describedby` on errors, errors announced.
- Images: `alt` from the product title; decorative images `alt=""`.
- Touch targets ≥ 44×44 px.
- Test with keyboard only, and with VoiceOver/NVDA on the 3 critical journeys.

---

## 16. Definition of Done (per feature)

A feature is not done until **all** of these are true:

1. Backend endpoint + Pydantic schemas + service logic + tests.
2. Alembic migration written and reversible.
3. OpenAPI types regenerated; frontend consumes generated types.
4. Loading, empty, and error states implemented — not just the happy path.
5. Both `az.json` and `en.json` keys added; no literal strings.
6. Light + dark verified; reduced-transparency + reduced-motion verified.
7. Mobile (375px) + desktop (1440px) verified.
8. Keyboard-navigable, focus visible, contrast checked.
9. `ruff`, `mypy --strict`, `eslint`, `tsc --noEmit` all clean.
10. No new dependency added without a line in the PR body justifying its bundle cost.

---

## 17. Known risks & mitigations

| Risk | Mitigation |
|---|---|
| `backdrop-filter` tanks scroll perf on mid-range Android | Tier system §3.5 + the hard rule that glass never enters a scroll container. Profile on a real device at phase 8, not at phase 12. |
| No truly free SMS provider in Azerbaijan | Phone auth ships **built but off** (`AUTH_PHONE_ENABLED=false`). v1 runs Google-only with zero OTP cost or dependency. Channel choice is deferred to the §18 handoff, not to the build. |
| Rebrand late in the build causes a scattered find-and-replace | §3.0 brand layer + the CI lint rule banning brand literals outside `src/brand/`. Verify the rule works at phase 0 by renaming to a nonsense string and confirming nothing breaks. |
| Placeholder logo never gets replaced and ships | The nav reserves a fixed `160×32` box from phase 1, so a real logo drops in without redesign — but put "replace placeholder wordmark" on the phase 12 checklist explicitly. |
| SQLite write contention if traffic grows | WAL + `busy_timeout` covers this scale. Migration path in §18 is pre-planned; no raw SQL outside the search module. |
| Google OAuth requires a verified domain for production consent | Register the OAuth client early (phase 0), not at launch. Test-user mode covers dev. |
| Bilingual content doubles admin data entry | `*_en` is optional with AZ fallback everywhere; the shop is fully usable AZ-only from day one. |
| Uploads volume growth | Re-encode + strip on upload keeps files small; add a size report to the admin stats page. |
| "Just add one more color" scope creep on the palette | §3.3 is a review checklist. Point at it. |

---

## 18. Deferred wiring — decide before the defence

Everything below is **code-complete but deliberately not connected**. None of it blocks development; all of it blocks a finished demo. Because production is local Docker (§1), several items that would be launch-blockers for a public site collapse to nearly nothing here — that is noted per row so you do not spend time on infrastructure this project does not need.

| # | What | Status | What to do |
|---|---|---|---|
| **W1** | **Phone/OTP channel** | ✅ **Decided: `OTP_CHANNEL=console`** | No wiring, no account, no cost, nothing to fail on stage. Run with `AUTH_PHONE_ENABLED=true` + `OTP_CHANNEL=console` and demo the real flow via the §9.11 dev OTP inbox — boxed code in the terminal *and* a live `/dev/otp-inbox` page beside the app. **This is the honest answer and it is also the better demo:** no dependence on a bot, a network, or a phone with signal in the exam room. Say plainly that delivery is stubbed and the adapter interface is provider-agnostic — that is a design strength, not an apology. If you later want a real channel, `OTP_CHANNEL=telegram` + a @BotFather token (2 min, free) switches it with **zero code change** — which is precisely the point the adapter pattern exists to make. Never imply an SMS gateway exists. |
| **W2** | **Google OAuth credentials** | Needed for the login demo | **Much simpler than a public launch.** No domain verification, no privacy policy, no review. Create an OAuth client in Google Cloud Console, keep the consent screen in **Testing** mode, add your own Gmail as a test user, and register `http://localhost` and `http://localhost:5173` as authorized JavaScript origins. Testing mode allows up to 100 test users indefinitely. ~10 minutes, €0. **Do it at phase 0** — not because verification is slow here, but because auth is the spine of phases 4, 9 and 10. |
| **W3** | **Brand identity** | Placeholder wordmark | Final name, `logo.svg` + `logo-mark.svg`, AZ/EN tagline. Run the §3.0 rebrand checklist. If no real brand ever materialises, the typographic wordmark is a legitimate final answer — just make sure it is *deliberate* and consistent, not obviously a leftover. |
| **W4** | **Accent choice** | Azure default | View the site with 20+ seeded products in both accents and pick. One `settings` row, no rebuild. Worth doing on the projector you will actually present on — accent contrast reads very differently through a beamer than on a laptop panel. |
| **W5** | **Contact details** | Placeholders | The contact payload is the entire payoff of the request flow (§9.1). Even for a demo, fill it with coherent fictional data — a request that resolves to `+994 XX XXX XX XX` undercuts the whole flow in front of an examiner. |
| **W6** | **Domain, DNS, TLS** | ❌ **Not required — skip it** | Caddy serves `http://localhost`. No domain, no A record, no ACME, no certificate. If you want a padlock on screen, uncomment `tls internal`, but it shows a browser warning unless you trust Caddy's local CA — usually worse on a projector than plain HTTP. Mention in the defence that the Caddy config is *ready* for automatic HTTPS on a real domain; that is true and costs no work. |
| **W7** | **Backup** | Scripted, unverified | Public-site advice (offsite copies) does not apply. What does apply: **run the backup, then restore it into a fresh container once.** Two reasons — `docker compose down -v` deleting a week of seeded demo data is a genuinely common way to lose a final project, and "demonstrate your recovery procedure" is a fair examiner question with a satisfying answer. |
| **W8** | **Secrets** | Placeholders | `JWT_SECRET` from `openssl rand -hex 32`, `ADMIN_EMAIL` set, and confirm the real `.env` is gitignored. The app refuses to boot with `ENV=production` and a default or missing secret — keep that check; it is a small thing that reads as competence. |
| **W9** | **Demo data** | 12 seed products | Before the defence, seed **30–50 products across all categories with real photographs and real Azerbaijani titles**. This matters more than it sounds: every layout decision in §3.6.1 — `contain` fitting, clamped titles, fixed card heights — only visibly earns itself against messy real data, and an empty or lorem-ipsum catalogue makes a good build look unfinished. Also seed a few order requests in each status so the admin panel is not empty. |
| **W10** | **Written deliverables** | Not started | Typically required alongside the code: a README with setup and architecture, an ER diagram (generate from the SQLAlchemy models — do not draw it by hand and let it drift), the OpenAPI spec exported to PDF/HTML from `/docs`, and a short architecture diagram. **§2 (deviations) and the Decision Log at the end of this file are already written as defence material** — every row is a decision with a stated justification. Reuse them directly. |

## 19. v2 backlog (do not build now)

Postgres migration (SQLAlchemy models are already portable; swap the FTS5 module for `tsvector`) · multi-seller marketplace (flip the `require_admin` on product create to `require_phone_verified` only) · wishlist · reviews & ratings · email/push notifications on new requests · online payments · PWA + offline catalogue · Telegram bot for admin request notifications · product variants (size/color) · promo codes.

---

## 20. First command to run

From the repo root (`freeshop/`), scaffolding both siblings side by side:

```bash
npm create vite@latest frontend -- --template react-ts && mkdir backend
```

Then execute §13 phase by phase. Phase 0 must end with `brand.config.ts` in place (§3.0) — every later phase depends on nothing hardcoding the project name.

---

### Decision log

| Decision | Chosen | Locked at |
|---|---|---|
| Guest access | **View only.** No guest cart. The wall is an invitation sheet at "Səbətə at" with pending-intent replay (§9.8). | Owner, confirmed |
| Phone/OTP | **Built, tested, shipped off** (`AUTH_PHONE_ENABLED=false`). Wire a channel at §18/W1. | Owner |
| Catalogue type | **Mixed / general.** 4:5 `contain` cards, category+price+availability filters only (§3.6.1). | Owner |
| Pricing | **Always visible.** `price_minor NOT NULL`. | Owner |
| Accent | **Azure default, bronze shipped as a swappable second theme** (§3.2). Final pick deferred to §18/W4. | Owner |
| Branding | **Not final.** Config-driven brand layer, no literals outside `src/brand/` (§3.0). | Owner |
| Repo shape | **Single root, `backend/` + `frontend/` siblings.** No monorepo tooling. | Owner |
| Project context | **University final project.** Prod = local Docker. Pro engineering standards, minus public-internet infrastructure (§1, §11.1, §12.3). | Owner |
| Rendering | **Client-rendered SPA. No SSR, no prerender** — evaluated and scoped out with a documented upgrade path (§11.1). | Owner |
| EN content | **Optional per product with AZ fallback.** Full EN interface from day one; EN product copy never blocks a save (§7.3). | Owner |
| Admin control | **Language, accent, theme, contacts and all static copy are admin settings**, not code (§7.3, §8). | Owner |
| Glass library | **Chrome on hand-written CSS** (responsive; every lens lib needs fixed px). `liquid-glass-web-react` optional for one showcase element only (§3.5.1). | Researched Aug 2026 |
| Build scope | **All 13 phases, no deadline cut.** Phases 7–8 pulled forward (§13.3); order after that is backend → i18n → admin. | Owner |
| Search | **Folded `search_text` column**, not raw `LIKE` — Azerbaijani is typed without diacritics (§13.4/E2). | Found by smoke test |
| Timestamps | **`UtcDateTime` type decorator everywhere.** SQLite drops tzinfo, which breaks every expiry check (§13.5/F3). | Found by tests |
| OTP attempts | **Committed before comparison**, so the lockout survives the failure it is counting (§13.5/F2). | Found by tests |
| Settings | **`create_app` installs its settings globally**; the codebase reads via `get_settings()` (§13.5/F1). | Found by tests |
| Image storage | **`path` is a relative path OR an absolute URL**, `is_remote` decides. Seed hotlinks; uploads are local. | Owner |
| Theme control | **Two-state toggle** (light/dark); `system` is the stored default, not a step in the cycle (§13.3). | Owner |
| `contain: paint` | **Per glass surface, never on the base class** — it clips dropdowns (§13.3/D1). | Verified in-browser |
| Demo imagery | **Real photography hotlinked from Unsplash**, each photo visually checked against its title; `npm run demo:fetch` localises them for an offline demo. | Owner |
| Currency format | **Explicit formatter, never `Intl` `style:'currency'`** — Chromium has no AZN pattern (§13.2/C1). | Verified in-browser |
| Prod host port | **`HTTP_PORT`, default 8090**; Caddy binds `:80` not a hostname (§13.2/C5). | Verified in Docker |
| OTP delivery | **`OTP_CHANNEL=console`**, demoed through the §9.11 dev OTP inbox. Provider adapters remain swappable with no code change. | Owner |
| Seed data | **Committed, deterministic, 3 tiers** (§8.1). 45 curated demo products carrying 15 named edge cases; `stress` tier backs the §11 perf claims. | Owner |

---

## 21. The community layer — location, needs, messaging, lending, aid

> Added after the give-away board was working. This section is authoritative
> for everything below; where it and an earlier section disagree about a
> table or an endpoint, this one is newer.

The board could say *what* was being given away but not *where*, and it had
no way to record what people were **looking for**. Five features close that
gap, and they share one spine: a location abstraction, a conversation, and a
moderation queue that already existed.

### 21.1 The decisions that shaped it

| # | Decision | Why |
|---|---|---|
| **C1** | **Location is a mixin, not a `locations` table.** Seven columns (`country`, `region`, `city`, `district`, `latitude`, `longitude`, `location_precision`) declared once in `app/db/models/location.py` and mixed into `users`, `products`, `need_requests`, `emergency_aid_cases`. | Every located row has exactly one location, never shared. A separate table would add a join to the hottest query in the application to buy a foreign key. Declared once means the four tables cannot drift. |
| **C2** | **Coordinates are city/district CENTROIDS from a static gazetteer** (`app/services/geo_data.py`, 71 towns + 12 Bakı districts), never the user's own position. The API accepts a place NAME and resolves it server-side; `LocationIn` has no latitude field. | The alternatives are all worse: a geocoder is a paid dependency in the critical path (§1), and `navigator.geolocation` hands the server somebody's doorstep. Everyone in Lənkəran shares one coordinate pair — that is not an approximation we tolerate, it is the privacy property. No row can locate a person more precisely than "somewhere in their town", because nothing more precise was ever collected. |
| **C3** | **Proximity = bounding box in SQL, Haversine in Python.** `app/services/geo.py`. | SQLite only has `acos`/`cos`/`radians` when compiled with `SQLITE_ENABLE_MATH_FUNCTIONS`, which is true on some builds and false on others. A nearby sort that raises `no such function: acos` on a colleague's machine is worse than one that is approximate in its first pass. The box is *exact as a filter* — it can only over-include — so correctness lives in the Python step, which is portable. **Ceiling:** ranking is over at most `CANDIDATE_CAP` (2000) boxed rows. **Upgrade path:** PostGIS `ST_DWithin` + `ORDER BY distance` replaces `within_bbox` and `rank_by_distance`, and nothing else. |
| **C4** | **No coordinates ever leave the API.** `LocationOut` carries a place label and a rounded distance; there is no lat/lng field on any public DTO. Distances are rounded to 0.1 km below 10 km and to whole kilometres above. | A distance quoted to the metre, from enough origins, triangulates the thing it measured. Enforced by a test that greps whole response bodies, so a coordinate added to any nested DTO later fails the build. |
| **C5** | **`nearby` degrades, never fails.** With no origin the server sorts by newest and says so in `Page.applied_sort`. | FreeShop_Prompt §2: "do not break the page". The client renders "add your location for better results" from the server's answer, so the note can never contradict the list beneath it. |
| **C6** | **Needs are a separate table, not a direction flag on `products`.** | A need has no price, no photographs, no stock status and no transfer type. Folding it in would mean four more nullable columns and a filter on every existing query — including the ones that already work. |
| **C7** | **Needs reuse the product moderation vocabulary exactly** (`pending`/`approved`/`rejected`, `moderation_note`, `reviewed_at`) and default to `pending`. | The admin panel reuses its table, filters and status pills, and a moderator moving between the two queues does not learn a second interface. Fail-closed: a code path that forgets to set the status publishes nothing. |
| **C8** | **Posting a need needs no verified phone; offering an item still does.** | Publishing a listing is a promise to meet a stranger and hand something over. Admitting you need a pushchair is not, and requiring a verified number to say so would exclude exactly the people this board exists for. Borrowing *does* need one — it is a promise to give property back. |
| **C9** | **Handover is recorded per LINE, not per request.** `order_request_items.outcome` ∈ `pending`/`received`/`not_selected`. | One request may name several items, each decided separately. This column is what makes Rule C possible: the nine people who did not get the ladder are *marked*, not deleted. |
| **C10** | **Converting a lost request into a need is the requester's decision and is deduplicated.** `POST /needs/from-request-item/{id}`, matched on the folded title + category, returns 200 (not 201) when a matching open need already exists. | Aggregate demand is the product of this endpoint, so it has to be trustworthy: somebody who misses out on four ladders in a month is one household, not four. |
| **C11** | **Public demand is a COUNT.** `GET /needs/demand` groups by folded title and returns `{label, count, nearest_km}` with no identities. | Rule F. Who needs a pushchair is not public information; a helper opens a conversation from an individual need, which is an authorised one-to-one act. |
| **C12** | **A conversation's participant row IS the authorisation.** There is no endpoint that adds a participant; `open_thread` resolves the other party from the context object. A thread you are not in is **404**, not 403. | An API where a client names its own recipient is an open channel to every account on the platform. 403 would confirm that two named people are talking. |
| **C13** | **Polling, not WebSockets.** 60 s for the badge, 30 s for the inbox, 15 s for an open thread. | One uvicorn process behind Caddy (§12.3); messages on a give-away board arrive minutes apart. A socket layer adds a connection lifecycle, a reconnect story and a second auth path for something nobody would notice. FreeShop_Prompt §3 permits polling for v1. |
| **C14** | **Message pagination is keyset (`before_id`), not offset. Only the FIRST page marks a thread read.** | A thread is read while it is being written to; an offset shifts under the reader every time the other person types. Paging backwards through history is not "I have seen the newest message". |
| **C15** | **A listing's loan state is DERIVED, never stored.** `Product.transfer_type` says whether it is a loan at all; `available`/`reserved`/`borrowed` is computed from the live `loan_requests` row. | Two copies of the truth means two rows that can disagree, and the stale one is always the one the UI reads. `loan_service.listing_states()` answers for a whole page in one query. |
| **C16** | **Every loan transition goes through one table.** `LOAN_TRANSITIONS` (which moves exist) × `ACTORS` (who may make them). The single-live-loan check is re-run inside the approving transaction. | "Returned" for an item that was never collected is exactly the nonsense an explicit table refuses. Between loading the page and clicking, an owner may already have approved somebody else. |
| **C17** | **Only `api/v1/admin_community.py` can create an emergency aid case, and it is the only module that serves `verification_note_internal`.** The public DTO does not *have* the field. | Rule E. A badge reading "Təcili yardım" is a claim about somebody's life. A missing field is a stronger guarantee than a serializer remembering to exclude one. |
| **C18** | **Aid item counters are derived and recomputed, never incremented.** `emergency_service.recount()` re-aggregates from the commitments after every change. | An increment that runs twice leaves "3 of 2 blankets received" on a public page, which is the kind of wrong that makes people stop trusting the whole thing. |
| **C19** | **An offer is not a delivery.** `offered → accepted → received`, and only an administrator may set the last two. | Marking an item received on a click tells the next visitor the family already has blankets that are still in a stranger's hallway. A donor confirming their own delivery turns the page into a wish list. |
| **C20** | **Notifications store a stable `type` + a JSON payload, never a sentence.** The client owns one translated string per type (`notification.*`). | A row storing "Sizə mesaj var" is frozen into Azerbaijani for a reader who later switches to English. It is also what makes a second transport (a digest email, a Telegram bot) a new consumer of these rows rather than a rewrite. |
| **C21** | **`User.display_name` never falls back to a phone number or an email.** Somebody with no name set is `#41`. Admin views keep their own fallback to the phone. | Two people arranging a handover exchange what they choose to type; the platform does not hand over a number because somebody opened a conversation (§15). Found by a test, not by review. |
| **C22** | **The command palette is now lazy.** `cmdk` moved out of the entry chunk into `PaletteBody`. | Adding this feature set pushed initial JS to 123 kB against the §11 ceiling of 120. Rather than raise the budget, the palette — a modal most visits never open — stopped being in the first paint. Initial JS is now **107.3 kB**, *below* where it started. |

### 21.2 Data model additions

**New tables (9)**

| Table | Purpose | Key columns |
|---|---|---|
| `need_requests` | Things people are looking for | `+ LocationMixin`, `title`, `search_text` (folded), `status` (`open`/`partially_fulfilled`/`fulfilled`/`closed`/`expired`), `moderation_status`, `expires_at`, `source_order_item_id` |
| `conversations` | One thread per subject per pair | `type` (`listing`/`need`/`loan`/`emergency`), four nullable context FKs, `last_message_at` (denormalised for ordering) |
| `conversation_participants` | Membership = authorisation | `uq_participant_once`, `last_read_at` |
| `messages` | Thread contents | `body`, `edited_at`, `deleted_at` (soft) |
| `loan_requests` | The lending lifecycle | `status`, `requested_days`, `approved_at`, `borrowed_at`, `expected_return_at`, `returned_at` |
| `emergency_aid_cases` | Admin-verified aid | `+ LocationMixin`, `slug`, `status`, **`verification_note_internal` (admin-only)**, `created_by_admin_id` |
| `emergency_aid_items` | The shopping list | `quantity_needed`, `quantity_committed`, `quantity_received` (both derived), `priority` |
| `aid_commitments` | "I can bring two blankets" | `quantity`, `status`, `accepted_at`, `received_at` |
| `notifications` | In-app events | `type`, `payload_json`, `link`, `read_at` |

**Changed tables (3)** — all additive, all defaulted:

- `users` — LocationMixin (the saved default location)
- `products` — LocationMixin, `transfer_type` (back-filled `giveaway`), `available_from`, `available_until`, `max_borrow_days`
- `order_request_items` — `outcome` (back-filled `pending`), `decided_at`

**Migration `b7c1d2e3f4a5`.** Nothing dropped, nothing renamed. Server defaults exist only to satisfy NOT NULL for existing rows and are dropped in the same migration, so `alembic revision --autogenerate` reports **zero drift** against the models. Verified: upgrade → downgrade → upgrade on a clean database, with the downgrade removing every added column.

**Indexes added:** `ix_products_geo`, `ix_products_transfer`, `ix_need_requests_public`, `ix_need_requests_geo`, `ix_need_requests_category`, `ix_loan_requests_product_status`, `ix_loan_requests_due`, `ix_messages_thread`, `ix_participants_user`, `ix_commitments_item_status`, `ix_notifications_unread`, `ix_order_items_product_outcome`.

### 21.3 API surface

Existing endpoints changed only additively — new optional query parameters and new response fields; every previous request shape still works.

- `GET /products` — new `sort=nearby|most_requested`, `radius_km`, `transfer_type`, `city`, `lat`, `lng`; responses gain `location`, `transfer_type`, `loan_state`; `Page` gains `applied_sort`
- `GET /products/{slug}` — adds loan terms and `open_request_count`
- `GET|POST /products/{id}/requesters` · `/handover` · `/matching-needs` — the Rule C flow, owner-only
- `GET|PUT /users/me/location` · `GET /meta/places` · `GET /meta/radius-options`
- `/needs` — list, demand, mine, convertible, create, `from-request-item/{id}`, detail, matching-listings, patch, status
- `/conversations` — list, unread, open, thread, send, read
- `/loans` — mine, lent, request, detail, status
- `/aid` — cases, case detail, my commitments, offer, withdraw
- `/notifications` — list, read one, read all
- `/admin/needs`, `/admin/needs/{id}/moderate`, `/admin/aid/**` — moderation and case management

### 21.4 Frontend

Routes: `/needs`, `/needs/new`, `/needs/:id`, `/profile/needs`, `/messages`, `/messages/:id`, `/profile/loans`, `/aid`, `/aid/:slug`, `/profile/aid`, `/admin/needs`, `/admin/aid`, `/admin/aid/:id`. All lazy.

Components: `PlaceLine`/`DistanceBadge`, `LocationPicker` (two selects — there is no control capable of expressing a house), `RadiusSelector`, `NearbyUnavailableNote`, `NeedCard`/`DemandRow`, `HandoverPanel`, `KeepAsNeedPrompt`, `LoanRequestPanel`, `LoanBadge`, `AidCaseCard`. One new stylesheet, `community.css`, consuming the existing tokens — no second design language.

i18n: **256 new keys × 2 languages** (672 total), `npm run i18n:check` green.

### 21.5 Verified green

`ruff` · `ruff format` · `mypy --strict` (78 files) · **206 backend tests** (118 pre-existing, all still passing + 88 new) · `eslint` · `tsc --noEmit` · `prettier` · 34 frontend tests · `i18n:check` (672 × 2) · production build · **initial JS 107.3 kB / 120 kB**, CSS 12.0 kB / 20 kB · Alembic upgrade → downgrade → upgrade with zero autogenerate drift.

### 21.6 Limitations, honestly

1. **The gazetteer is a fixed list.** A village that is not in `geo_data.py` keeps its typed name and gets no coordinates, so it cannot take part in the nearby sort. That is a deliberate trade against a paid geocoder, and adding a place is a one-line edit.
2. **Nearby ranking is capped at 2000 boxed candidates** (C3). Fine for a town; the PostGIS upgrade path is one function.
3. **Needs expire on read, not on a schedule.** There is no job runner in this deployment (§12.3), so `expire_stale()` runs from the needs list endpoint.
4. **Notifications are in-app only.** No push, no SMS, no email digest — the abstraction is there for one.
5. **`loan_due_soon` is queryable but not yet produced**; nothing wakes up to send it. Same reason as (3).
6. **Messages have no edit or delete endpoint** yet, although the columns (`edited_at`, `deleted_at`) and the serializer support both.
7. **No reporting/abuse flow** for conversations. FreeShop_Prompt §11 listed it as conditional ("if reporting is implemented"); it is not.
