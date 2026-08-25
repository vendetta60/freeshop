import { useQuery } from '@tanstack/react-query';
import { ArrowRight } from 'lucide-react';
import { Link, useNavigate } from 'react-router';

import { ProductCard } from '@/components/product/ProductCard';
import { Button } from '@/components/ui/Button';
import { Chip } from '@/components/ui/Chip';
import { ProductCardSkeleton } from '@/components/ui/Skeleton';
import { ErrorState } from '@/components/ui/States';
import { catalogueApi, catalogueKeys } from '@/lib/api/catalogue';
import { useT } from '@/lib/i18n';
import { siteText } from '@/lib/site/config';
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

  const query = { per_page: 8, sort: 'newest' as const };
  const { data, isPending, isError, refetch } = useQuery({
    queryKey: catalogueKeys.products(query, lang),
    queryFn: ({ signal }) => catalogueApi.products(query, lang, signal),
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
    </>
  );
}
