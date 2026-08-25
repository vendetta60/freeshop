import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { Check, Inbox, Loader2, Phone, X } from 'lucide-react';
import { useState } from 'react';

import { Badge } from '@/components/ui/Badge';
import { Button } from '@/components/ui/Button';
import { TextAreaField } from '@/components/ui/Field';
import { Price } from '@/components/ui/Price';
import { Skeleton } from '@/components/ui/Skeleton';
import { EmptyState, ErrorState } from '@/components/ui/States';
import { adminApi, adminKeys, type AdminProduct } from '@/lib/api/admin';
import { useDocumentTitle } from '@/lib/hooks/useDocumentTitle';
import { useT } from '@/lib/i18n';
import { formatDate } from '@/lib/utils/format';
import { toast } from '@/stores/toastStore';

/**
 * The review queue.
 *
 * The whole listing is on screen — title, description, category, who offered
 * it and on what number — because approving from a one-line summary is not
 * reviewing, it is rubber-stamping. Rejection asks for a reason before it
 * will submit.
 */
export default function AdminQueue() {
  const { t, lang } = useT();
  const queryClient = useQueryClient();
  const [rejecting, setRejecting] = useState<number | null>(null);
  const [note, setNote] = useState('');

  useDocumentTitle(t('admin.queue.title'));

  const query = { status: 'pending' as const, per_page: 50 };
  const pending = useQuery({
    queryKey: adminKeys.products(query),
    queryFn: ({ signal }) => adminApi.products(query, signal),
  });

  const decide = useMutation({
    mutationFn: ({
      id,
      status,
      reason,
    }: {
      id: number;
      status: 'approved' | 'rejected';
      reason?: string;
    }) => adminApi.moderate(id, reason ? { status, note: reason } : { status }),
    onSuccess: async (_data, variables) => {
      setRejecting(null);
      setNote('');
      await queryClient.invalidateQueries({ queryKey: ['admin'] });
      // The public catalogue changed the moment this resolved.
      await queryClient.invalidateQueries({ queryKey: ['products'] });
      toast.success(
        variables.status === 'approved' ? t('admin.queue.approved') : t('admin.queue.rejected'),
      );
    },
    onError: () => toast.error(t('admin.queue.failed')),
  });

  const items: AdminProduct[] = pending.data?.items ?? [];

  return (
    <section style={{ display: 'grid', gap: '1rem' }}>
      <header className="section-head">
        <h1 style={{ fontSize: '1.25rem' }}>{t('admin.queue.title')}</h1>
      </header>
      <p className="muted" style={{ fontSize: '0.875rem', marginTop: '-0.5rem' }}>
        {t('admin.queue.lead')}
      </p>

      {pending.isError && <ErrorState onRetry={() => void pending.refetch()} />}

      {pending.isPending && (
        <div style={{ display: 'grid', gap: '0.75rem' }}>
          {Array.from({ length: 3 }, (_, i) => (
            <Skeleton key={i} height={150} radius="var(--r-lg)" />
          ))}
        </div>
      )}

      {pending.data && items.length === 0 && (
        <EmptyState
          title={t('admin.queue.empty')}
          description={t('admin.queue.emptyText')}
          icon={<Inbox size={22} />}
        />
      )}

      {items.map((listing) => (
        <article key={listing.id} className="card queue-card">
          <div className="queue-card__body">
            {listing.images[0] ? (
              <img src={listing.images[0].url} alt="" width={96} height={96} loading="lazy" />
            ) : (
              <span className="cell-title__blank queue-card__blank" aria-hidden="true" />
            )}

            <div style={{ minWidth: 0, display: 'grid', gap: '0.4rem' }}>
              <div className="listing-row__head">
                <span style={{ fontWeight: 500 }}>{listing.title_az}</span>
                <Badge tone="neutral">{listing.category_name}</Badge>
                <Price minor={listing.price_minor} currency={listing.currency} />
              </div>

              {listing.description_az && (
                <p className="muted" style={{ fontSize: '0.875rem', whiteSpace: 'pre-line' }}>
                  {listing.description_az}
                </p>
              )}

              <p className="subtle" style={{ fontSize: '0.8125rem' }}>
                {t('admin.queue.offeredBy')}:{' '}
                <span style={{ color: 'var(--text-muted)' }}>
                  {listing.owner_name ?? t('account.noName')}
                </span>
                {listing.owner_phone && (
                  <>
                    {' · '}
                    <a className="tabular" href={`tel:${listing.owner_phone.replace(/\s/g, '')}`}>
                      <Phone size={12} aria-hidden="true" /> {listing.owner_phone}
                    </a>
                  </>
                )}
                {' · '}
                {formatDate(listing.created_at, lang)}
              </p>
            </div>
          </div>

          {rejecting === listing.id ? (
            <div style={{ display: 'grid', gap: '0.5rem' }}>
              <TextAreaField
                label={t('admin.queue.rejectReason')}
                hint={t('admin.queue.rejectReasonHint')}
                rows={2}
                value={note}
                onChange={(e) => setNote(e.target.value)}
              />
              <div className="row-actions">
                <Button
                  variant="danger"
                  size="sm"
                  // A reason is required, not encouraged: the submitter reads it.
                  disabled={note.trim().length < 3 || decide.isPending}
                  onClick={() =>
                    decide.mutate({ id: listing.id, status: 'rejected', reason: note.trim() })
                  }
                >
                  {decide.isPending && <Loader2 size={15} className="spin" aria-hidden="true" />}
                  {t('admin.queue.reject')}
                </Button>
                <Button variant="ghost" size="sm" onClick={() => setRejecting(null)}>
                  {t('common.cancel')}
                </Button>
              </div>
            </div>
          ) : (
            <div className="row-actions">
              <Button
                variant="primary"
                size="sm"
                disabled={decide.isPending}
                onClick={() => decide.mutate({ id: listing.id, status: 'approved' })}
              >
                <Check size={15} aria-hidden="true" />
                {t('admin.queue.approve')}
              </Button>
              <Button
                variant="secondary"
                size="sm"
                disabled={decide.isPending}
                onClick={() => {
                  setRejecting(listing.id);
                  setNote('');
                }}
              >
                <X size={15} aria-hidden="true" />
                {t('admin.queue.reject')}
              </Button>
            </div>
          )}
        </article>
      ))}
    </section>
  );
}
