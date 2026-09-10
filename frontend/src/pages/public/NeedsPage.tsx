import { useQuery } from '@tanstack/react-query';
import { HandHeart, Plus } from 'lucide-react';
import { Link, useSearchParams } from 'react-router';

import { NearbyUnavailableNote, RadiusSelector } from '@/components/community/DiscoveryControls';
import { DemandRow, NeedCard } from '@/components/community/NeedCard';
import { Chip } from '@/components/ui/Chip';
import { Skeleton } from '@/components/ui/Skeleton';
import { EmptyState, ErrorState } from '@/components/ui/States';
import { communityKeys, needsApi } from '@/lib/api/community';
import { useCategories } from '@/lib/hooks/useCategories';
import { useDocumentTitle } from '@/lib/hooks/useDocumentTitle';
import { useT } from '@/lib/i18n';

const SORTS = ['nearby', 'newest'] as const;

/**
 * "Ehtiyaclar" - the reverse side of the board (FreeShop_Prompt 4).
 *
 * Two sections, in this order on purpose. Aggregated DEMAND comes first: a
 * visitor with a spare ladder is more likely to act on "9 people near you
 * need one" than on nine individual posts, and the aggregate is the thing
 * that survives when no single post catches their eye (Rule C).
 *
 * Filter state lives in the URL, matching ProductsPage - every filtered view
 * is shareable, and the back button behaves.
 */
export default function NeedsPage() {
  const [params, setParams] = useSearchParams();
  const { t, lang } = useT();

  const q = params.get('q') ?? '';
  const sort = (params.get('sort') as 'newest' | 'nearby' | null) ?? 'nearby';
  const categoryId = params.get('category_id');
  const radiusParam = params.get('radius_km');
  const radiusKm = radiusParam ? Number(radiusParam) : null;

  const { flat: categories } = useCategories();
  useDocumentTitle(t('needs.title'));

  const query = {
    q: q || undefined,
    category_id: categoryId ? Number(categoryId) : undefined,
    sort,
    radius_km: radiusKm ?? undefined,
    per_page: 24,
  };

  const needs = useQuery({
    queryKey: communityKeys.needs(query, lang),
    queryFn: ({ signal }) => needsApi.list(query, lang, signal),
  });

  const demandParams = { radius_km: radiusKm ?? 50, limit: 8 };
  const demand = useQuery({
    queryKey: communityKeys.demand(demandParams),
    queryFn: ({ signal }) => needsApi.demand(demandParams, signal),
  });

  const update = (key: string, value: string | null) => {
    const next = new URLSearchParams(params);
    if (value === null || value === '') next.delete(key);
    else next.set(key, value);
    setParams(next, { replace: true });
  };

  return (
    <>
      <div className="hero" style={{ paddingBottom: '1.25rem' }}>
        <h1>{t('needs.title')}</h1>
        <p>{t('needs.lead')}</p>
        <div className="hero__actions">
          <Link to="/needs/new" className="btn btn--primary btn--md">
            <Plus size={16} aria-hidden="true" />
            {t('needs.post')}
          </Link>
        </div>
      </div>

      {/* Aggregated demand. Rendered only when there is any - an empty
          "what people need nearby" heading is worse than no heading. */}
      {(demand.data?.length ?? 0) > 0 && (
        <section aria-labelledby="demand" style={{ marginBottom: '1.5rem' }}>
          <div className="section-head">
            <h2 id="demand" style={{ fontSize: '1rem' }}>
              {t('needs.demandTitle')}
            </h2>
          </div>
          <div className="demand-list">
            {(demand.data ?? []).map((row) => (
              <DemandRow key={row.key} demand={row} />
            ))}
          </div>
        </section>
      )}

      <div className="filter-rail" role="group" aria-label={t('catalogue.categoryFilter')}>
        <Chip
          active={!categoryId}
          onClick={() => {
            update('category_id', null);
          }}
        >
          {t('common.all')}
        </Chip>
        {categories.map((item) => (
          <Chip
            key={item.id}
            active={String(item.id) === categoryId}
            onClick={() => {
              update('category_id', String(item.id));
            }}
          >
            {item.name}
          </Chip>
        ))}
      </div>

      <div className="filter-bar">
        {SORTS.map((key) => (
          <Chip
            key={key}
            active={key === sort}
            onClick={() => {
              update('sort', key);
            }}
          >
            {t(`sort.${key}`)}
          </Chip>
        ))}
        <RadiusSelector
          value={radiusKm}
          onChange={(next) => {
            update('radius_km', next === null ? null : String(next));
          }}
        />
      </div>

      {sort === 'nearby' && <NearbyUnavailableNote appliedSort={needs.data?.applied_sort} />}

      {needs.isError && <ErrorState onRetry={() => void needs.refetch()} />}

      {needs.isPending && (
        <div style={{ display: 'grid', gap: '0.75rem' }}>
          {Array.from({ length: 4 }, (_, i) => (
            <Skeleton key={i} height={92} radius="var(--r-lg)" />
          ))}
        </div>
      )}

      {needs.data?.items.length === 0 && (
        <EmptyState
          title={t('needs.empty')}
          description={t('needs.emptyText')}
          icon={<HandHeart size={22} />}
          action={
            <Link to="/needs/new" className="btn btn--primary btn--md">
              {t('needs.post')}
            </Link>
          }
        />
      )}

      <div style={{ display: 'grid', gap: '0.75rem' }}>
        {(needs.data?.items ?? []).map((need) => (
          <NeedCard key={need.id} need={need} />
        ))}
      </div>
    </>
  );
}
