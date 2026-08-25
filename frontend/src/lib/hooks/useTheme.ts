import { useCallback, useEffect, useState } from 'react';

import type { AccentName, ThemeName } from '@/brand/brand.config';
import { brand } from '@/brand/brand.config';
import { siteConfig } from '@/lib/site/config';

// Brand-neutral on purpose: these are internal identifiers (plan.md 3.0,
// rule 6). Renaming them during a rebrand would silently discard every
// visitor's saved theme.
const THEME_KEY = 'ui:theme';
const ACCENT_KEY = 'ui:accent';

function readStored<T extends string>(key: string, allowed: readonly T[]): T | null {
  try {
    const raw = localStorage.getItem(key);
    return allowed.includes(raw as T) ? (raw as T) : null;
  } catch {
    // Private browsing can throw on access. Falling back to the default is
    // correct here - a theme preference is not worth an error boundary.
    return null;
  }
}

function prefersDark(): boolean {
  return window.matchMedia('(prefers-color-scheme: dark)').matches;
}

/**
 * Theme and accent, persisted and applied as `data-*` on <html>.
 *
 * THREE stored values, but only a TWO-state control.
 *
 * `system` exists so a first-time visitor gets their OS preference without
 * having chosen anything - that is worth keeping. But cycling a single icon
 * through system -> light -> dark makes the next click unpredictable: you
 * cannot tell from the icon what pressing it will do. So `toggleTheme` only
 * ever moves between light and dark, resolving `system` to whatever the OS
 * currently shows. The third state is an initial condition, not a stop on
 * the cycle.
 */
export function useTheme() {
  const [theme, setThemeState] = useState<ThemeName>(
    () =>
      readStored<ThemeName>(THEME_KEY, ['system', 'light', 'dark']) ??
      // The admin's setting, then the compiled default (plan.md 7.3).
      siteConfig()?.default_theme ??
      brand.defaultTheme,
  );
  const [accent, setAccentState] = useState<AccentName>(
    () =>
      readStored<AccentName>(ACCENT_KEY, ['azure', 'bronze']) ??
      siteConfig()?.accent ??
      brand.accent,
  );

  useEffect(() => {
    const root = document.documentElement;
    if (theme === 'system') {
      delete root.dataset.theme;
    } else {
      root.dataset.theme = theme;
    }
    try {
      localStorage.setItem(THEME_KEY, theme);
    } catch {
      /* not persisting is acceptable */
    }
  }, [theme]);

  useEffect(() => {
    const root = document.documentElement;
    if (accent === 'azure') {
      delete root.dataset.accent;
    } else {
      root.dataset.accent = accent;
    }
    try {
      localStorage.setItem(ACCENT_KEY, accent);
    } catch {
      /* not persisting is acceptable */
    }
  }, [accent]);

  /** What the visitor is actually looking at right now. */
  const resolvedTheme: 'light' | 'dark' =
    theme === 'system' ? (prefersDark() ? 'dark' : 'light') : theme;

  const toggleTheme = useCallback(() => {
    setThemeState((current) => {
      const showing = current === 'system' ? (prefersDark() ? 'dark' : 'light') : current;
      return showing === 'dark' ? 'light' : 'dark';
    });
  }, []);

  const toggleAccent = useCallback(() => {
    setAccentState((current) => (current === 'azure' ? 'bronze' : 'azure'));
  }, []);

  return {
    theme,
    resolvedTheme,
    accent,
    setTheme: setThemeState,
    setAccent: setAccentState,
    toggleTheme,
    toggleAccent,
  };
}
