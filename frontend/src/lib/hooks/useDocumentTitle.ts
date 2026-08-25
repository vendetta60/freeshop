import { useEffect } from 'react';

import { brand } from '@/brand/brand.config';

/**
 * Per-route `<title>` (plan.md 11.1).
 *
 * A single-page app keeps whatever title `index.html` shipped with unless
 * something changes it, so every tab, every bookmark and every browser-history
 * entry reads the same word. This is the smallest fix: the document title
 * follows the route.
 *
 * `null` while data is loading leaves the previous title in place rather than
 * flashing "undefined" between renders.
 */
export function useDocumentTitle(title: string | null): void {
  useEffect(() => {
    if (!title) return;
    const previous = document.title;
    document.title = `${title} · ${brand.name}`;
    return () => {
      document.title = previous;
    };
  }, [title]);
}
