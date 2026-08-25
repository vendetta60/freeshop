import { useQuery } from '@tanstack/react-query';
import { Gift } from 'lucide-react';
import { Link } from 'react-router';

import { Badge } from '@/components/ui/Badge';
import { Button } from '@/components/ui/Button';
import { Price } from '@/components/ui/Price';
import { Skeleton } from '@/components/ui/Skeleton';
import { EmptyState, ErrorState } from '@/components/ui/States';
import { listingApi, listingKeys, type ModerationStatus } from '@/lib/api/catalogue';
import { useDocumentTitle } from '@/lib/hooks/useDocumentTitle';
import { useT } from '@/lib/i18n';
import { formatDate } from '@/lib/utils/format';
import { useAuthStore } from '@/stores/authStore';
import { useUiStore } from '@/stores/uiStore';

const TONE: Record<ModerationStatus, 'neutral' | 'success' | 'danger'> = {
  pending: 'neutral',
  approved: 'success',
  rejected: 'danger',
};

/**
 * What happened to the things you offered.
 *
 * Shows rejected and removed listings too. "Where did my listing go?" is the
 * first question anyone asks of a moderated board, and an answer of silence
 * is what stops them offering a second thing.
 */
export default function MyListingsPage() {
  const { t, lang } = useT();
  const user = useAuthStore((s) => s.user);
  const loading = useAuthStore((s) => s.loading);
  const openAuth = useUiStore((s) => s.openAuth);

  useDocumentTitle(t('listings.title'));

  const listings = useQuery({
    queryKey: listingKeys.mine(lang),
    queryFn: ({ signal }) => listingApi.mine(lang, signal),
    enabled: user !== null,
  });

  if (loading) return null;

  if (!user) {
    return (
      <EmptyState
        title={t('offer.signInTitle')}
        description={t('offer.signInText')}
        action={
          <Button variant="primary" onClick={openAuth}>
            {t('common.signIn')}
          </Button>
        }
      />
    );
  }

  return (
    <section style={{ display: 'grid', gap: '1rem' }}>
      <header className="section-head">
        <h1 style={{ fontSize: '1.25rem' }}>{t('listings.title')}</h1>
        <Link to="/offer" className="btn btn--primary btn--sm">
          {t('offer.nav')}
        </Link>
      </header>

      {listings.isError && <ErrorState onRetry={() => void listings.refetch()} />}

      {listings.isPending && (
        <div style={{ display: 'grid', gap: '0.75rem' }}>
          {Array.from({ length: 3 }, (_, i) => (
            <Skeleton key={i} height={96} radius="var(--r-lg)" />
          ))}
        </div>
      )}

      {listings.data?.length === 0 && (
        <EmptyState
          title={t('listings.empty')}
          description={t('listings.emptyText')}
          icon={<Gift size={22} />}
          action={
            <Link to="/offer" className="btn btn--primary btn--md">
              {t('offer.nav')}
            </Link>
          }
        />
      )}

      {(listings.data ?? []).map((listing) => (
        <article key={listing.id} className="card listing-row">
          {listing.image ? (
            <img src={listing.image} alt="" width={64} height={64} loading="lazy" />
          ) : (
            <span className="cell-title__blank" aria-hidden="true" />
          )}

          <div style={{ minWidth: 0, display: 'grid', gap: '0.3rem' }}>
            <div className="listing-row__head">
              {listing.status === 'approved' && !listing.is_deleted ? (
                <Link to={`/products/${listing.slug}`} style={{ fontWeight: 500 }}>
                  {listing.title}
                </Link>
              ) : (
                <span style={{ fontWeight: 500 }}>{listing.title}</span>
              )}
              <Badge tone={TONE[listing.status]}>{t(`moderation.${listing.status}`)}</Badge>
              {listing.is_deleted && <Badge tone="warning">{t('listings.removed')}</Badge>}
            </div>

            <p className="subtle" style={{ fontSize: '0.8125rem' }}>
              {listing.category_name} · {formatDate(listing.created_at, lang)}
            </p>

            {listing.status === 'pending' && (
              <p className="muted" style={{ fontSize: '0.8125rem' }}>
                {t('listings.pendingNote')}
              </p>
            )}

            {/* The reason, verbatim. A rejection with no explanation reads as
                a rebuke and costs the next donation. */}
            {listing.status === 'rejected' && listing.moderation_note && (
              <p className="listing-row__note">{listing.moderation_note}</p>
            )}
          </div>

          <Price minor={listing.price_minor} currency={listing.currency} />
        </article>
      ))}
    </section>
  );
}
