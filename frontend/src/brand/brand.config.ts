/**
 * THE ONLY PLACE BRAND LITERALS MAY APPEAR.
 *
 * The project name, logo and domain are NOT final (plan.md 3.0). Everything
 * downstream - the nav, <title>, OG tags, the PWA manifest, the footer -
 * reads from this object, so a rebrand is an edit here plus two SVG files.
 *
 * An ESLint rule (`no-restricted-syntax` in eslint.config.js) bans the brand
 * name as a string literal anywhere else under src/. It reads the name from
 * THIS file at lint time, so the two can never drift apart.
 *
 * Rebrand checklist:
 *   1. edit this file
 *   2. drop in assets/logo.svg + assets/logo-mark.svg
 *   3. npm run brand:assets
 *   4. update APP_NAME / REQUEST_PREFIX / FRONTEND_URL / CORS_ORIGINS in .env
 *   5. rebuild
 */

export type AccentName = 'azure' | 'bronze';
export type ThemeName = 'system' | 'light' | 'dark';

/**
 * THE brand-name literal. Exactly one, on purpose.
 *
 * An earlier draft also spelled the name out in `shortName`, which meant a
 * rename needed two edits and forgetting the second left a stale name in the
 * PWA manifest. Everything now derives from this constant, and the ESLint
 * rule reads it from here at lint time.
 */
const BRAND_NAME = 'FreeShop';

export const brand = {
  /** Wordmark text and <title> suffix. */
  name: BRAND_NAME,

  /**
   * PWA / mobile bar. Must be <= 12 characters (asserted in the unit test).
   * Only replace the derived value if BRAND_NAME is longer than that.
   */
  shortName: BRAND_NAME,

  /** Shown in the footer. Fill in at launch. */
  legalName: '',

  domain: 'example.az',

  /** Translated, but lives here rather than in the i18n JSON - it is brand copy. */
  tagline: {
    az: 'Seçilmiş məhsullar, birbaşa satıcıdan',
    en: 'Curated products, straight from the seller',
  },

  /** <meta name="description"> and OG description. */
  description: {
    az: 'Məhsullara baxın, səbətə əlavə edin və satıcı ilə birbaşa əlaqə saxlayın.',
    en: 'Browse the catalogue, build a basket, and contact the seller directly.',
  },

  /** Default appearance. The admin settings row overrides this at runtime. */
  accent: 'azure' as AccentName,
  defaultTheme: 'system' as ThemeName,

  social: {
    instagram: '',
    facebook: '',
    whatsapp: '',
    telegram: '',
  },
} as const;

export type Brand = typeof brand;
