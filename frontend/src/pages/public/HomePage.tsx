import { useQuery } from '@tanstack/react-query';
import { ArrowRight } from 'lucide-react';
import { Link, useNavigate } from 'react-router';

import { NeedCard } from '@/components/community/NeedCard';
import { ProductCard } from '@/components/product/ProductCard';
import { AidCaseCard } from '@/pages/public/AidPage';
import { Button } from '@/components/ui/Button';
import { Chip } from '@/components/ui/Chip';
import { ProductCardSkeleton } from '@/components/ui/Skeleton';
import { ErrorState } from '@/components/ui/States';
import { catalogueApi, catalogueKeys } from '@/lib/api/catalogue';
import { aidApi, communityKeys, needsApi } from '@/lib/api/community';
import { useT } from '@/lib/i18n';
import { siteText } from '@/lib/site/config';
import { useAuthStore } from '@/stores/authStore';
import { useCategories } from '@/lib/hooks/useCategories';

/**
 * Landing page. Every control navigates.
 *
 * Category chips route to /products rather than filtering in place: filter
 * state belongs in the URL, and two different behaviours for the same-looking
 * control is the kind of thing that quietly erodes trust in a UI.
 */
export default function HomePage() {
  const navigate = useNavigate();
  const { t, lang } = useT();
  const { flat: categories } = useCategories();

  // Signed in with a known location -> nearby; otherwise newest. The server
  // falls back on its own if it cannot honour `nearby`, so this only picks
  // the better request rather than guarding against a failure.
  const hasLocation = useAuthStore((s) => s.user?.has_location ?? false);
  const query = {
    per_page: 8,
    sort: hasLocation ? ('nearby' as const) : ('newest' as const),
  };
  const { data, isPending, isError, refetch } = useQuery({
    queryKey: catalogueKeys.products(query, lang),
    queryFn: ({ signal }) => catalogueApi.products(query, lang, signal),
  });

  // The three community sections. Each renders ONLY when it has something to
  // show (FreeShop_Prompt 9: "Do not display every section if empty") - an
  // empty "Təcili yardım" heading on a quiet week reads as a broken page.
  const nearbyNeeds = useQuery({
    queryKey: communityKeys.needs({ sort: 'nearby', per_page: 4 }, lang),
    queryFn: ({ signal }) => needsApi.list({ sort: 'nearby', per_page: 4 }, lang, signal),
  });

  const loans = useQuery({
    queryKey: catalogueKeys.products({ transfer_type: 'loan', per_page: 4 }, lang),
    queryFn: ({ signal }) =>
      catalogueApi.products({ transfer_type: 'loan', per_page: 4 }, lang, signal),
  });

  const aidCases = useQuery({
    queryKey: communityKeys.aidCases(lang, true),
    queryFn: ({ signal }) => aidApi.cases(lang, true, signal),
  });

  return (
    <>
      <section className="hero">
        <h1>{siteText('hero_title', lang, t('home.heroTitle'))}</h1>
        <p>{t('home.heroText')}</p>
        <div className="hero__actions">
          <Button
            variant="primary"
            size="lg"
            onClick={() => {
              void navigate('/products');
            }}
          >
            {t('home.browse')}
            <ArrowRight size={17} aria-hidden="true" />
          </Button>
          <Button
            variant="secondary"
            size="lg"
            onClick={() => {
              void navigate('/contact');
            }}
          >
            {t('home.contact')}
          </Button>
        </div>
      </section>

      <section aria-labelledby="featured">
        <div className="section-head">
          <h2 id="featured">{t('home.featured')}</h2>
          <Link to="/products" style={{ fontSize: '0.875rem' }}>
            {t('home.seeAll')}
          </Link>
        </div>

        <div className="filter-rail" role="group" aria-label={t('catalogue.categoryFilter')}>
          {categories.map((category) => (
            <Chip
              key={category.slug}
              onClick={() => {
                void navigate(`/products?category=${encodeURIComponent(category.slug)}`);
              }}
            >
              {category.name}
            </Chip>
          ))}
        </div>

        {isError && (
          <ErrorState
            title={t('home.loadFailed')}
            description={t('home.loadFailedText')}
            onRetry={() => void refetch()}
          />
        )}

        <div className="product-grid">
          {isPending
            ? Array.from({ length: 8 }, (_, i) => <ProductCardSkeleton key={i} />)
            : (data?.items ?? []).map((product, index) => (
                <ProductCard key={product.id} product={product} priority={index < 4} />
              ))}
        </div>
      </section>

      {/* Emergency aid first when there is any: it is the one section on this
          page with a deadline. Rendered plainly, without a progress bar or a
          countdown - this is community aid, not a fundraising campaign
          (FreeShop_Prompt 8). */}
      {(aidCases.data?.length ?? 0) > 0 && (
        <section aria-labelledby="home-aid" style={{ marginTop: '2.5rem' }}>
          <div className="section-head">
            <h2 id="home-aid">{t('aid.title')}</h2>
            <Link to="/aid" style={{ fontSize: '0.875rem' }}>
              {t('home.seeAll')}
            </Link>
          </div>
          <div style={{ display: 'grid', gap: '0.75rem' }}>
            {(aidCases.data ?? []).slice(0, 2).map((item) => (
              <AidCaseCard key={item.id} aidCase={item} />
            ))}
          </div>
        </section>
      )}

      {(nearbyNeeds.data?.items.length ?? 0) > 0 && (
        <section aria-labelledby="home-needs" style={{ marginTop: '2.5rem' }}>
          <div className="section-head">
            <h2 id="home-needs">{t('home.nearbyNeeds')}</h2>
            <Link to="/needs" style={{ fontSize: '0.875rem' }}>
              {t('home.seeAll')}
            </Link>
          </div>
          <div style={{ display: 'grid', gap: '0.75rem' }}>
            {(nearbyNeeds.data?.items ?? []).map((need) => (
              <NeedCard key={need.id} need={need} />
            ))}
          </div>
        </section>
      )}

      {(loans.data?.items.length ?? 0) > 0 && (
        <section aria-labelledby="home-loans" style={{ marginTop: '2.5rem' }}>
          <div className="section-head">
            <h2 id="home-loans">{t('home.loans')}</h2>
            <Link to="/products?transfer_type=loan" style={{ fontSize: '0.875rem' }}>
              {t('home.seeAll')}
            </Link>
          </div>
          <div className="product-grid">
            {(loans.data?.items ?? []).map((product) => (
              <ProductCard key={product.id} product={product} />
            ))}
          </div>
        </section>
      )}
    </>
  );
}
