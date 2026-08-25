import { Link } from 'react-router';

import { StatusPill } from '@/components/ui/StatusPill';
import type { OrderRequest } from '@/lib/api/cart';
import { useT } from '@/lib/i18n';
import { Price } from '@/components/ui/Price';
import { formatDate } from '@/lib/utils/format';

/**
 * One request, as the buyer sees it.
 *
 * Shared by the history list and the single-request route so the two cannot
 * drift into showing different things about the same row.
 */
export function RequestCard({
  request,
  linked = true,
}: {
  request: OrderRequest;
  linked?: boolean;
}) {
  const { t, lang } = useT();

  return (
    <article className="card request-card">
      <header className="request-card__head">
        {linked ? (
          <Link
            to={`/profile/orders/${request.id}`}
            className="tabular"
            style={{ fontWeight: 500 }}
          >
            {request.request_no}
          </Link>
        ) : (
          <span className="tabular" style={{ fontWeight: 500 }}>
            {request.request_no}
          </span>
        )}
        <StatusPill status={request.status} />
        <span className="muted" style={{ fontSize: '0.8125rem' }}>
          {formatDate(request.created_at, lang)}
        </span>
      </header>

      {request.note && (
        <p className="request-panel__note">
          <span className="subtle" style={{ display: 'block', fontSize: '0.75rem' }}>
            {t('cart.note')}
          </span>
          {request.note}
        </p>
      )}

      <ul className="plain-list">
        {request.items.map((item) => (
          <li key={item.id} className="request-line">
            {item.image ? (
              <img src={item.image} alt="" width={36} height={36} loading="lazy" />
            ) : (
              <span className="cell-title__blank" aria-hidden="true" />
            )}
            <span style={{ minWidth: 0 }}>
              {/* Snapshotted at request time, so a later reprice or a deletion
                  cannot rewrite what was asked for. */}
              {item.product_slug ? (
                <Link to={`/products/${item.product_slug}`}>{item.title}</Link>
              ) : (
                item.title
              )}
            </span>
            <span className="muted tabular">×{item.quantity}</span>
            <Price minor={item.line_total_minor} />
          </li>
        ))}
      </ul>

      <footer className="request-card__foot">
        <span className="muted">{t('common.total')}</span>
        <strong>
          <Price minor={request.total_minor} />
        </strong>
      </footer>
    </article>
  );
}
