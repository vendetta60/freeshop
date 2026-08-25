import { useQuery } from '@tanstack/react-query';
import { ArrowLeft, Check, ShoppingBag } from 'lucide-react';
import { useState } from 'react';
import { Link, useParams } from 'react-router';

import { ProductCard } from '@/components/product/ProductCard';
import { Badge, StockPill } from '@/components/ui/Badge';
import { Button } from '@/components/ui/Button';
import { Price } from '@/components/ui/Price';
import { Skeleton } from '@/components/ui/Skeleton';
import { ErrorState } from '@/components/ui/States';
import { catalogueApi, catalogueKeys } from '@/lib/api/catalogue';
import { useDocumentTitle } from '@/lib/hooks/useDocumentTitle';
import { useT } from '@/lib/i18n';
import { ApiError } from '@/lib/api/client';
import { formatPrice } from '@/lib/utils/format';
import NotFoundPage from '@/pages/public/NotFoundPage';
import { useAuthStore } from '@/stores/authStore';
import { useCart } from '@/lib/hooks/useCart';
import { useUiStore } from '@/stores/uiStore';

export default function ProductDetailPage() {
  const { slug = '' } = useParams();
  const { t, lang } = useT();

  const { add } = useCart();
  const openCart = useUiStore((s) => s.openCart);
  const requestSignIn = useUiStore((s) => s.requestSignIn);
  const signedIn = useAuthStore((s) => s.user !== null);
  const [justAdded, setJustAdded] = useState(false);

  const {
    data: product,
    isPending,
    error,
    refetch,
  } = useQuery({
    queryKey: catalogueKeys.product(slug, lang),
    queryFn: ({ signal }) => catalogueApi.product(slug, lang, signal),
    // A missing product is an answer, not a transient failure; retrying a 404
    // four times just makes the 404 page take two seconds to appear.
    retry: (count, err) => !(err instanceof ApiError && err.status === 404) && count < 2,
  });

  const { data: related = [] } = useQuery({
    queryKey: catalogueKeys.related(slug, lang),
    queryFn: ({ signal }) => catalogueApi.related(slug, lang, signal),
    enabled: Boolean(product),
  });

  // The product name, once it has arrived. Until then the previous
  // title stays rather than flashing a placeholder.
  useDocumentTitle(product?.title ?? null);
  if (error instanceof ApiError && error.status === 404) return <NotFoundPage />;

  // Anything that is NOT a 404 is a failure, not an absence. Falling through
  // to the 404 page would tell the visitor this product does not exist when
  // in fact the server is unreachable.
  if (error) {
    return (
      <ErrorState
        title={t('product.loadFailed')}
        description={t('product.loadFailedText')}
        onRetry={() => void refetch()}
      />
    );
  }

  if (isPending) {
    return (
      <div className="detail">
        <Skeleton width="100%" height={420} radius="var(--r-lg)" />
        <div style={{ display: 'grid', gap: '0.75rem', alignContent: 'start' }}>
          <Skeleton width="40%" height={20} />
          <Skeleton width="90%" height={28} />
          <Skeleton width="30%" height={30} />
          <Skeleton width="100%" height={64} />
        </div>
      </div>
    );
  }

  if (!product) return <NotFoundPage />;

  const soldOut = product.stock_status === 'out_of_stock';

  const handleAdd = () => {
    // Guests may browse everything but not build a basket (plan.md D2). The
    // wall is an invitation, not a rejection: the intent is remembered and
    // replayed the instant they sign in, so the action completes for them.
    if (!signedIn) {
      requestSignIn(product);
      return;
    }
    add.mutate({ productId: product.id });
    setJustAdded(true);
    openCart();
    window.setTimeout(() => {
      setJustAdded(false);
    }, 1600);
  };

  return (
    <>
      <Link to="/products" className="back-link">
        <ArrowLeft size={15} aria-hidden="true" />
        {t('cart.backToCatalogue')}
      </Link>

      <div className="detail">
        <div className="detail__media">
          {product.image ? (
            <img
              src={product.image}
              alt={product.title}
              width={product.image_width ?? undefined}
              height={product.image_height ?? undefined}
              fetchPriority="high"
              decoding="async"
            />
          ) : (
            <span className="subtle">{t('product.noImage')}</span>
          )}
        </div>

        <div className="detail__info">
          <Badge tone="neutral">{product.category_name}</Badge>
          <h1>{product.title}</h1>

          <p className="detail__price tabular">
            {product.old_price_minor ? (
              <span className="product-card__old-price">
                {formatPrice(product.old_price_minor, lang, product.currency)}
              </span>
            ) : null}
            <Price minor={product.price_minor} currency={product.currency} />
          </p>

          <StockPill status={product.stock_status} />

          <p className="muted">{product.description}</p>

          <div style={{ display: 'flex', gap: '0.625rem', flexWrap: 'wrap' }}>
            <Button variant="primary" size="lg" onClick={handleAdd} disabled={soldOut}>
              {justAdded ? (
                <>
                  <Check size={17} aria-hidden="true" />
                  {t('product.added')}
                </>
              ) : (
                <>
                  <ShoppingBag size={17} aria-hidden="true" />
                  {soldOut ? t('product.soldOut') : t('product.addToCart')}
                </>
              )}
            </Button>
            <Button variant="secondary" size="lg">
              <Link to="/contact" style={{ color: 'inherit', textDecoration: 'none' }}>
                {t('product.contactSeller')}
              </Link>
            </Button>
          </div>

          <p aria-live="polite" className="visually-hidden">
            {justAdded ? t('product.added') : ''}
          </p>
        </div>
      </div>

      {product.images.length > 1 && (
        <div className="thumb-strip" aria-label={t('product.gallery')}>
          {product.images.map((image) => (
            <span key={image.id} className="thumb">
              <img src={image.url} alt="" loading="lazy" />
            </span>
          ))}
        </div>
      )}

      {related.length > 0 && (
        <section style={{ marginTop: '3rem' }}>
          <div className="section-head">
            <h2>{t('product.related')}</h2>
          </div>
          <div className="product-grid">
            {related.map((item) => (
              <ProductCard key={item.id} product={item} />
            ))}
          </div>
        </section>
      )}
    </>
  );
}
