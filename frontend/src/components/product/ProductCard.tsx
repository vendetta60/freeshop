import { Link } from 'react-router';

import { StockPill } from '@/components/ui/Badge';
import { Price } from '@/components/ui/Price';
import type { ProductCard as ProductSummary } from '@/lib/api/catalogue';
import { useT } from '@/lib/i18n';
import { formatPrice } from '@/lib/utils/format';

export type { ProductSummary };

/**
 * Product card for a mixed/general catalogue (plan.md 3.6.1).
 *
 * Two decisions carry the whole component:
 *   1. `object-fit: contain` over a flat pad, never `cover` - the catalogue
 *      mixes 3000x2000 furniture shots with 400x400 phone snaps, and cover
 *      would crop the subject out of the wide ones.
 *   2. Opaque surface, never glass - cards live in a scroll container.
 *
 * The whole card is one <a>: one tap target, correct semantics, and
 * middle-click and keyboard both behave.
 */
export function ProductCard({
  product,
  priority = false,
}: {
  product: ProductSummary;
  priority?: boolean;
}) {
  // The language comes from the store rather than a prop: every caller was
  // passing the same value, and a card rendering AZ prices inside an EN page
  // is the bug a defaulted prop invites.
  const { t, lang } = useT();
  const { title, image, price_minor, old_price_minor, stock_status, currency } = product;

  return (
    <Link to={`/products/${product.slug}`} className="product-card">
      <div className="product-card__media">
        {image ? (
          <img
            src={image}
            alt={title}
            width={product.image_width ?? undefined}
            height={product.image_height ?? undefined}
            loading={priority ? 'eager' : 'lazy'}
            // Only the LCP candidate gets high priority; everything else
            // competing for bandwidth makes the first paint slower, not faster.
            fetchPriority={priority ? 'high' : 'auto'}
            decoding="async"
          />
        ) : (
          <span className="subtle" style={{ fontSize: '0.75rem' }}>
            {t('product.noImage')}
          </span>
        )}
      </div>

      <div className="product-card__body">
        <h3 className="product-card__title">{title}</h3>
        <div className="product-card__meta">
          <span className="product-card__price">
            {old_price_minor ? (
              <span className="product-card__old-price">
                {formatPrice(old_price_minor, lang, currency)}
              </span>
            ) : null}
            <Price minor={price_minor} currency={currency} />
          </span>
          <StockPill status={stock_status} />
        </div>
      </div>
    </Link>
  );
}
