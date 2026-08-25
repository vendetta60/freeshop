import { useQuery } from '@tanstack/react-query';

import { catalogueApi, catalogueKeys, type CategoryNode } from '@/lib/api/catalogue';
import { useLangStore } from '@/lib/i18n';

/**
 * The category tree, plus a flattened view for chip rails.
 *
 * Cached for five minutes: categories change rarely, and the nav, the
 * catalogue page and the command palette all want the same data - without a
 * shared cache that is three requests per navigation.
 */
export function useCategories() {
  const lang = useLangStore((s) => s.lang);

  const { data, isPending, isError } = useQuery({
    queryKey: catalogueKeys.categories(lang),
    queryFn: ({ signal }) => catalogueApi.categories(lang, signal),
    staleTime: 5 * 60_000,
  });

  const tree: CategoryNode[] = data ?? [];

  // Only categories that actually have products: an empty chip is a dead end,
  // and the seed deliberately includes an empty category to prove it.
  const flat = tree
    .flatMap((root) => [root, ...root.children])
    .filter((node) => node.product_count > 0);

  return { tree, flat, isPending, isError };
}
