import { useQuery } from '@tanstack/react-query';
import { SlidersHorizontal } from 'lucide-react';
import { useSearchParams } from 'react-router';

import { ProductCard } from '@/components/product/ProductCard';
import { Chip } from '@/components/ui/Chip';
import { ProductCardSkeleton } from '@/components/ui/Skeleton';
import { ErrorState } from '@/components/ui/States';
import { catalogueApi, catalogueKeys, type SortKey } from '@/lib/api/catalogue';
import { useDocumentTitle } from '@/lib/hooks/useDocumentTitle';
import { useT } from '@/lib/i18n';
import { useCategories } from '@/lib/hooks/useCategories';

const SORTS: { key: SortKey; labelKey: string }[] = [
  { key: 'newest', labelKey: 'catalogue.sort.newest' },
  { key: 'price_asc', labelKey: 'catalogue.sort.priceAsc' },
  { key: 'price_desc', labelKey: 'catalogue.sort.priceDesc' },
];

/**
 * Catalogue.
 *
 * Filter state lives in the URL, not in a store: every filtered view is then
 * shareable and bookmarkable, and the back button behaves the way people
 * expect. That is worth more than the marginal convenience of local state.
 */
export default function ProductsPage() {
  const [params, setParams] = useSearchParams();
  const { t, lang } = useT();

  const category = params.get('category') ?? '';
  const sort = (params.get('sort') as SortKey | null) ?? 'newest';
  const inStockOnly = params.get('stock') === '1';
  const q = params.get('q') ?? '';

  const { flat: categories } = useCategories();

  const query = {
    q: q || undefined,
    category: category || undefined,
    sort,
    stock: inStockOnly ? ('available' as const) : undefined,
    per_page: 24,
  };

  const { data, isPending, isError, refetch } = useQuery({
    queryKey: catalogueKeys.products(query, lang),
    queryFn: ({ signal }) => catalogueApi.products(query, lang, signal),
  });

  const update = (key: string, value: string | null) => {
    const next = new URLSearchParams(params);
    if (value === null || value === '') next.delete(key);
    else next.set(key, value);
    setParams(next, { replace: true });
  };

  const activeName = categories.find((c) => c.slug === category)?.name;
  useDocumentTitle(activeName ?? t('catalogue.title'));

  return (
    <>
      <div className="hero" style={{ paddingBottom: '1.25rem' }}>
        <h1>{activeName ?? t('catalogue.title')}</h1>
        <p>
          {isPending ? t('common.loading') : t('catalogue.count', { count: data?.total ?? 0 })}
          {q && (
            <>
              {' · '}
              <span className="muted">{t('catalogue.searchFor', { query: q })}</span>
            </>
          )}
        </p>
      </div>

      <div className="filter-rail" role="group" aria-label={t('catalogue.categoryFilter')}>
        <Chip
          active={category === ''}
          onClick={() => {
            update('category', null);
          }}
        >
          {t('common.all')}
        </Chip>
        {categories.map((item) => (
          <Chip
            key={item.slug}
            active={item.slug === category}
            onClick={() => {
              update('category', item.slug);
            }}
          >
            {item.name}
          </Chip>
        ))}
      </div>

      <div className="filter-bar">
        <span
          className="subtle"
          style={{ display: 'inline-flex', alignItems: 'center', gap: '0.4rem' }}
        >
          <SlidersHorizontal size={14} aria-hidden="true" />
          {t('catalogue.sort')}
        </span>
        {SORTS.map(({ key, labelKey }) => (
          <Chip
            key={key}
            active={key === sort}
            onClick={() => {
              update('sort', key);
            }}
          >
            {t(labelKey)}
          </Chip>
        ))}
        <Chip
          active={inStockOnly}
          onClick={() => {
            update('stock', inStockOnly ? null : '1');
          }}
        >
          {t('catalogue.inStockOnly')}
        </Chip>
      </div>

      {isError && (
        <ErrorState
          title={t('catalogue.loadFailed')}
          description={t('home.loadFailedText')}
          onRetry={() => void refetch()}
        />
      )}

      {isPending && (
        <div className="product-grid">
          {Array.from({ length: 8 }, (_, i) => (
            <ProductCardSkeleton key={i} />
          ))}
        </div>
      )}

      {data && data.items.length === 0 && (
        <div className="empty-state">
          <p style={{ fontWeight: 500 }}>{t('catalogue.empty')}</p>
          <p className="muted" style={{ fontSize: '0.9375rem' }}>
            {t('catalogue.emptyText')}
          </p>
          <Chip
            onClick={() => {
              setParams(new URLSearchParams(), { replace: true });
            }}
          >
            {t('catalogue.resetFilters')}
          </Chip>
        </div>
      )}

      {data && data.items.length > 0 && (
        <div className="product-grid">
          {data.items.map((product, index) => (
            <ProductCard key={product.id} product={product} priority={index < 4} />
          ))}
        </div>
      )}
    </>
  );
}
