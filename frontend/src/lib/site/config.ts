import type { AccentName, ThemeName } from '@/brand/brand.config';

/**
 * Runtime site configuration from `GET /meta/config`.
 *
 * This is what makes the admin panel's appearance and language settings real
 * (plan.md 7.3, 11): accent, starting theme and default language come from the
 * database at boot rather than from the build, so changing them is a save in
 * the panel and not a redeploy.
 *
 * Fetched ONCE, before the first render, alongside the session refresh that
 * already blocks paint - so it costs no additional round trip in wall-clock
 * terms and there is no flash of the wrong accent.
 */
export type SiteConfig = {
  app_name: string;
  default_lang: string;
  supported_langs: string[];
  accent: AccentName;
  default_theme: ThemeName;
  google_enabled: boolean;
  phone_auth_enabled: boolean;
  demo_mode: boolean;
  currency: string;
  /** Page copy the admin edits, both languages, unresolved. */
  content?: Record<string, { az: string; en: string }>;
};

let cached: SiteConfig | null = null;

export function siteConfig(): SiteConfig | null {
  return cached;
}

export async function loadSiteConfig(): Promise<void> {
  const base: string = (import.meta.env.VITE_API_URL as string | undefined) ?? '/api/v1';
  try {
    const response = await fetch(`${base}/meta/config`);
    if (!response.ok) return;
    cached = (await response.json()) as SiteConfig;
  } catch {
    // The API being unreachable at boot is survivable: every consumer falls
    // back to the compiled brand defaults. A shop that renders in the wrong
    // accent beats a shop that does not render.
  }
}

/** Languages the admin has switched on, always including the AZ fallback. */
export function enabledLangs(): string[] {
  const langs = cached?.supported_langs?.filter((l) => l === 'az' || l === 'en') ?? [];
  return langs.length ? langs : ['az'];
}

/**
 * Admin-edited page copy, falling back to the bundled translation.
 *
 * The AZ text is the fallback for a missing EN one (plan.md 7.3), and an
 * untouched setting falls through to the compiled string - so the site reads
 * correctly before anyone has opened the panel, and follows it afterwards.
 */
export function siteText(key: string, lang: string, fallback: string): string {
  const entry = cached?.content?.[key];
  if (!entry) return fallback;
  const chosen = (lang === 'en' ? entry.en : entry.az) || entry.az;
  return chosen.trim() || fallback;
}
