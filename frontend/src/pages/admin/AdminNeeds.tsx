import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { Check, HandHeart, Loader2, X } from 'lucide-react';
import { useState } from 'react';

import { PlaceLine } from '@/components/community/PlaceLine';
import { Badge } from '@/components/ui/Badge';
import { Button } from '@/components/ui/Button';
import { TextAreaField } from '@/components/ui/Field';
import { Skeleton } from '@/components/ui/Skeleton';
import { EmptyState, ErrorState } from '@/components/ui/States';
import { adminCommunityApi, adminCommunityKeys } from '@/lib/api/admin';
import { useDocumentTitle } from '@/lib/hooks/useDocumentTitle';
import { useT } from '@/lib/i18n';
import { formatDate } from '@/lib/utils/format';
import { toast } from '@/stores/toastStore';

const FILTERS = ['pending', 'approved', 'rejected'] as const;

/**
 * The needs moderation queue (FreeShop_Prompt 11).
 *
 * Deliberately the SAME shape as AdminQueue: same filters, same status pills,
 * same "a rejection requires a reason" rule. A moderator moving between the
 * two queues should not have to learn a second interface, and the server
 * returns the same page envelope for both.
 */
export default function AdminNeeds() {
  const { t, lang } = useT();
  const queryClient = useQueryClient();
  const [filter, setFilter] = useState<(typeof FILTERS)[number]>('pending');
  const [rejecting, setRejecting] = useState<number | null>(null);
  const [note, setNote] = useState('');

  useDocumentTitle(t('admin.needs.title'));

  const params = { status: filter, per_page: 50 };
  const needs = useQuery({
    queryKey: adminCommunityKeys.needs(params),
    queryFn: ({ signal }) => adminCommunityApi.needs(params, signal),
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
    }) => adminCommunityApi.moderateNeed(id, reason ? { status, note: reason } : { status }),
    onSuccess: async (_data, variables) => {
      setRejecting(null);
      setNote('');
      await queryClient.invalidateQueries({ queryKey: ['admin', 'needs'] });
      // The public board changed the moment this resolved.
      await queryClient.invalidateQueries({ queryKey: ['needs'] });
      await queryClient.invalidateQueries({ queryKey: ['demand'] });
      toast.success(
        variables.status === 'approved' ? t('admin.needs.approved') : t('admin.needs.rejected'),
      );
    },
    onError: () => toast.error(t('admin.needs.failed')),
  });

  const items = needs.data?.items ?? [];

  return (
    <section style={{ display: 'grid', gap: '1rem' }}>
      <header className="section-head">
        <h1 style={{ fontSize: '1.25rem' }}>{t('admin.needs.title')}</h1>
      </header>
      <p className="muted" style={{ fontSize: '0.875rem', marginTop: '-0.5rem' }}>
        {t('admin.needs.lead')}
      </p>

      <div className="filter-bar">
        {FILTERS.map((key) => (
          <Button
            key={key}
            size="sm"
            variant={filter === key ? 'primary' : 'ghost'}
            onClick={() => setFilter(key)}
          >
            {t(`moderation.${key}`)}
          </Button>
        ))}
      </div>

      {needs.isError && <ErrorState onRetry={() => void needs.refetch()} />}

      {needs.isPending && (
        <div style={{ display: 'grid', gap: '0.75rem' }}>
          {Array.from({ length: 3 }, (_, i) => (
            <Skeleton key={i} height={120} radius="var(--r-lg)" />
          ))}
        </div>
      )}

      {needs.data && items.length === 0 && (
        <EmptyState
          title={t('admin.needs.empty')}
          description={t('admin.needs.emptyText')}
          icon={<HandHeart size={22} />}
        />
      )}

      {items.map((need) => (
        <article key={need.id} className="card queue-card">
          <div style={{ minWidth: 0, display: 'grid', gap: '0.4rem' }}>
            <div className="listing-row__head">
              <span style={{ fontWeight: 500 }}>{need.title}</span>
              {need.category_name && <Badge tone="neutral">{need.category_name}</Badge>}
              {need.quantity_needed > 1 && (
                <Badge tone="neutral">{t('needs.quantity', { count: need.quantity_needed })}</Badge>
              )}
            </div>

            {need.description && (
              <p className="muted" style={{ fontSize: '0.875rem', whiteSpace: 'pre-line' }}>
                {need.description}
              </p>
            )}

            <p className="subtle" style={{ fontSize: '0.8125rem' }}>
              {/* The queue names the poster; the public board never does. */}
              {need.user_label}
              {' · '}
              <PlaceLine location={need.location} showDistance={false} />
              {' · '}
              {formatDate(need.created_at, lang)}
            </p>
          </div>

          {rejecting === need.id ? (
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
                  disabled={note.trim().length < 3 || decide.isPending}
                  onClick={() =>
                    decide.mutate({ id: need.id, status: 'rejected', reason: note.trim() })
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
            filter === 'pending' && (
              <div className="row-actions">
                <Button
                  variant="primary"
                  size="sm"
                  disabled={decide.isPending}
                  onClick={() => decide.mutate({ id: need.id, status: 'approved' })}
                >
                  <Check size={15} aria-hidden="true" />
                  {t('admin.queue.approve')}
                </Button>
                <Button
                  variant="secondary"
                  size="sm"
                  disabled={decide.isPending}
                  onClick={() => {
                    setRejecting(need.id);
                    setNote('');
                  }}
                >
                  <X size={15} aria-hidden="true" />
                  {t('admin.queue.reject')}
                </Button>
              </div>
            )
          )}
        </article>
      ))}
    </section>
  );
}
