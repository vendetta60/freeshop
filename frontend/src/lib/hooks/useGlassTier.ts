import { useEffect, useState } from 'react';

export type GlassTier = 'full' | 'reduced' | 'none';

/**
 * Picks the glass rendering tier once, at mount (plan.md 3.5).
 *
 *   full     backdrop-filter supported and transparency not reduced
 *   reduced  user prefers reduced transparency, or the device is weak
 *   none     no backdrop-filter support at all
 *
 * The result is written to `data-glass` on <html>, so the decision lives in
 * CSS rather than in every component. Components just use `.glass`.
 */
function detect(): GlassTier {
  if (typeof window === 'undefined' || typeof CSS === 'undefined') return 'none';

  const supported =
    CSS.supports('backdrop-filter', 'blur(1px)') ||
    CSS.supports('-webkit-backdrop-filter', 'blur(1px)');

  if (!supported) return 'none';

  // An explicit accessibility preference always wins.
  if (window.matchMedia('(prefers-reduced-transparency: reduce)').matches) return 'reduced';

  // Weak devices: blurring a full-viewport layer every frame is the single
  // most expensive thing this UI can do. deviceMemory is Chromium-only, so
  // absence is treated as "probably fine" rather than "probably weak".
  const memory = (navigator as Navigator & { deviceMemory?: number }).deviceMemory;
  if (typeof memory === 'number' && memory <= 4) return 'reduced';

  return 'full';
}

export function useGlassTier(): GlassTier {
  const [tier, setTier] = useState<GlassTier>(() => detect());

  useEffect(() => {
    document.documentElement.dataset.glass = tier;
  }, [tier]);

  useEffect(() => {
    const query = window.matchMedia('(prefers-reduced-transparency: reduce)');
    const onChange = () => {
      setTier(detect());
    };
    query.addEventListener('change', onChange);
    return () => {
      query.removeEventListener('change', onChange);
    };
  }, []);

  return tier;
}
