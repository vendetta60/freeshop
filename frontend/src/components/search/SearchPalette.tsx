import { lazy, Suspense, useEffect } from 'react';

import { useUiStore } from '@/stores/uiStore';

/**
 * Command palette search (Ctrl/Cmd + K).
 *
 * Replaces a separate search page (plan.md 3.6): faster to reach, shows
 * thumbnails, and covers categories as well as products.
 *
 * This file is deliberately TINY. It is mounted on every page by RootLayout,
 * so everything it imports is in the entry chunk; the palette body and its
 * `cmdk` dependency are behind `lazy()` and arrive on the first open
 * (components/search/PaletteBody.tsx).
 */
const PaletteBody = lazy(() => import('@/components/search/PaletteBody'));

export function SearchPalette() {
  const open = useUiStore((s) => s.paletteOpen);
  const setOpen = useUiStore((s) => s.setPaletteOpen);

  useEffect(() => {
    const onKey = (event: KeyboardEvent) => {
      if (event.key === 'k' && (event.metaKey || event.ctrlKey)) {
        event.preventDefault();
        setOpen(!open);
      }
    };
    document.addEventListener('keydown', onKey);
    return () => {
      document.removeEventListener('keydown', onKey);
    };
  }, [open, setOpen]);

  // Mounting the body only while open is what resets the query - clearing it
  // from an effect would be a cascading render (react-hooks/set-state-in-effect).
  //
  // No Suspense fallback: the chunk is a few kilobytes and arrives in a
  // frame or two, and a spinner that flashes for 40 ms is worse than the
  // overlay appearing a moment later.
  return open ? (
    <Suspense fallback={null}>
      <PaletteBody
        onClose={() => {
          setOpen(false);
        }}
      />
    </Suspense>
  ) : null;
}
