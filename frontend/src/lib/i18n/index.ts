import { create } from 'zustand';

import { enabledLangs, siteConfig } from '@/lib/site/config';

import azStrings from './locales/az.json';

export type Lang = 'az' | 'en';

export const LANGS: Lang[] = ['az', 'en'];

type Dictionary = Record<string, string>;

/**
 * AZ is bundled; EN is fetched on demand.
 *
 * Both dictionaries in the initial chunk cost ~7 kB gzipped and took the
 * budget (plan.md 11) to within a few hundred bytes of its ceiling. AZ has to
 * be present because it is the fallback for every missing key, but an
 * Azerbaijani-speaking visitor has no reason to download the English strings.
 * The EN chunk is loaded before the language actually changes, so nobody ever
 * sees a half-translated screen.
 */
// Typed as a plain map: the imported JSON has a literal key type, which
// would reject any lookup by a computed key.
const az: Dictionary = azStrings;

const DICTIONARIES: Record<Lang, Dictionary | null> = { az, en: null };

export async function ensureLang(lang: Lang): Promise<void> {
  if (DICTIONARIES[lang]) return;
  const loaded = (await import('./locales/en.json')) as { default: Dictionary };
  DICTIONARIES.en = loaded.default;
}

const STORAGE_KEY = 'ui:lang';

/**
 * Translation.
 *
 * WHY NOT i18next (plan.md 7.1 named it):
 * i18next + react-i18next + the browser language detector cost roughly 15 kB
 * gzipped. The initial-JS budget (plan.md 11) has about 9 kB of headroom, and
 * raising a performance budget to fit a library is the trade that budget
 * exists to prevent. What this project actually uses from i18next is: a flat
 * key/value lookup, `{placeholder}` interpolation, one plural rule, an AZ
 * fallback, and persistence. That is the file you are reading, at well under
 * 1 kB.
 *
 * Everything else about the plan's i18n contract is kept exactly:
 * flat dot-namespaced keys, both files carrying the same key set (enforced by
 * `npm run i18n:check`), AZ as the default and the fallback, and `Intl` for
 * every number, price and date.
 */
function detect(): Lang {
  const enabled = enabledLangs();
  const allowed = (value: string | null): value is Lang =>
    (value === 'az' || value === 'en') && enabled.includes(value);

  // ?lang= wins, so a link can force a language for a demo or a screenshot.
  const fromQuery = new URLSearchParams(window.location.search).get('lang');
  if (allowed(fromQuery)) return fromQuery;

  try {
    const stored = localStorage.getItem(STORAGE_KEY);
    if (allowed(stored)) return stored;
  } catch {
    // Private browsing can throw on access; the default is a fine answer.
  }

  // DELIBERATE DEVIATION from plan.md 7.1's ordering, which put
  // `navigator.language` ahead of the site default. Section 7.3 defines
  // `default_lang` as "the language a first-time visitor sees before any
  // preference exists" - and since most browsers in this market report
  // en-US, consulting navigator first would make that admin setting a no-op
  // for nearly everyone. The visitor's own choice still wins the moment they
  // make one; this only decides what they see before that.
  const siteDefault = siteConfig()?.default_lang ?? null;
  if (allowed(siteDefault)) return siteDefault;

  const fromBrowser = navigator.language.toLowerCase().startsWith('en') ? 'en' : 'az';
  return allowed(fromBrowser) ? fromBrowser : 'az';
}

type LangState = {
  lang: Lang;
  setLang: (lang: Lang) => void;
  toggle: () => void;
};

export const useLangStore = create<LangState>()((set, get) => ({
  // Starts at the fallback and is resolved by `initLang()` during boot.
  // Detecting here would run at module-evaluation time - before the site
  // config has arrived - so `enabled_langs` would still be unknown and a
  // stored `en` preference would be rejected as "not enabled".
  lang: 'az',

  setLang: (lang) => {
    // Load first, switch second: setting the language before its dictionary
    // has arrived would render one frame of raw keys.
    void ensureLang(lang).then(() => {
      set({ lang });
      document.documentElement.lang = lang;
    });
    try {
      localStorage.setItem(STORAGE_KEY, lang);
    } catch {
      /* not persisting a language preference is survivable */
    }
  },

  toggle: () => {
    get().setLang(get().lang === 'az' ? 'en' : 'az');
  },
}));

/**
 * Resolve, load and apply the language. Called once from `main.tsx`, after
 * the site config has landed and before the first render.
 */
export async function initLang(): Promise<void> {
  const lang = detect();
  await ensureLang(lang);
  useLangStore.setState({ lang });
  document.documentElement.lang = lang;
}

export type Vars = Record<string, string | number>;

function interpolate(template: string, vars?: Vars): string {
  if (!vars) return template;
  return template.replace(/\{(\w+)\}/g, (whole, name: string) =>
    name in vars ? String(vars[name]) : whole,
  );
}

/**
 * Look up one key.
 *
 * Missing keys resolve through AZ and then to the key itself. Returning the
 * key rather than an empty string is deliberate: a screen reading
 * `cart.checkout` is an obvious bug report, while a blank button is a mystery.
 */
export function translate(lang: Lang, key: string, vars?: Vars): string {
  const count = vars?.count;
  if (typeof count === 'number') {
    // ICU-style plural keys (plan.md 7.1), never `count > 1 ? 's' : ''`.
    const plural = `${key}_${count === 1 ? 'one' : 'other'}`;
    const found = DICTIONARIES[lang]?.[plural] ?? az[plural];
    if (found) return interpolate(found, vars);
  }

  const found = DICTIONARIES[lang]?.[key] ?? az[key] ?? key;
  return interpolate(found, vars);
}

export type TranslateFn = (key: string, vars?: Vars) => string;

/**
 * `const { t, lang } = useT()`.
 *
 * `lang` is returned alongside because nearly every caller also needs it for
 * the API request and for `Intl` formatting - and a component that translates
 * its labels into EN while asking the server for AZ content is the failure
 * mode worth designing out.
 */
export function useT(): { t: TranslateFn; lang: Lang } {
  const lang = useLangStore((s) => s.lang);
  return {
    lang,
    t: (key, vars) => translate(lang, key, vars),
  };
}

/** For non-component code (stores, error mappers). */
export function t(key: string, vars?: Vars): string {
  return translate(useLangStore.getState().lang, key, vars);
}
