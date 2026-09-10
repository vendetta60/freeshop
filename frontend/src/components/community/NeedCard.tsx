import { HandHeart } from 'lucide-react';
import { Link } from 'react-router';

import { PlaceLine } from '@/components/community/PlaceLine';
import { Badge } from '@/components/ui/Badge';
import type { Demand, NeedCard as Need } from '@/lib/api/community';
import { useT } from '@/lib/i18n';
import { formatDistance } from '@/lib/utils/format';

/**
 * One thing somebody is looking for.
 *
 * NO NAME AND NO AVATAR, deliberately (Rule F). Who needs a pushchair is not
 * public information; a visitor who can help opens a conversation from the
 * detail page, which is a one-to-one act the server authorises.
 */
export function NeedCard({ need }: { need: Need }) {
  const { t } = useT();

  return (
    <Link to={`/needs/${need.id}`} className="card need-card">
      <span className="need-card__icon" aria-hidden="true">
        <HandHeart size={18} />
      </span>

      <div className="need-card__body">
        <div className="need-card__head">
          <h3 className="need-card__title">{need.title}</h3>
          {need.quantity_needed > 1 && (
            <Badge tone="neutral">{t('needs.quantity', { count: need.quantity_needed })}</Badge>
          )}
          {need.status === 'partially_fulfilled' && (
            <Badge tone="warning">{t('needs.status.partially_fulfilled')}</Badge>
          )}
        </div>

        {need.description && <p className="need-card__text">{need.description}</p>}

        <div className="need-card__meta">
          <PlaceLine location={need.location} />
          {need.category_name && <span className="subtle">{need.category_name}</span>}
        </div>
      </div>
    </Link>
  );
}

/**
 * "Nərdivan - yaxınlıqda 9 nəfərə lazımdır" (Rule C).
 *
 * Aggregated demand: a label and a count. It links into the needs board
 * filtered by the same words rather than exposing the individual posts,
 * which is the whole point - the community sees that demand exists without
 * seeing who is behind it.
 */
export function DemandRow({ demand }: { demand: Demand }) {
  const { t, lang } = useT();

  return (
    <Link
      to={`/needs?q=${encodeURIComponent(demand.label)}`}
      className="demand-row"
      aria-label={t('needs.demandCount', { count: demand.count, item: demand.label })}
    >
      <span className="demand-row__label">{demand.label}</span>
      <span className="demand-row__count tabular">
        {t('needs.demandCount', { count: demand.count, item: demand.label })}
      </span>
      {demand.nearest_km !== null && (
        <span className="subtle" style={{ fontSize: '0.75rem' }}>
          {t('location.nearest', { distance: formatDistance(demand.nearest_km, lang) })}
        </span>
      )}
    </Link>
  );
}
