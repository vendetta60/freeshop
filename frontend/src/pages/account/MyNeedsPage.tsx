import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { HandHeart } from 'lucide-react';
import { Link } from 'react-router';

import { PlaceLine } from '@/components/community/PlaceLine';
import { Badge } from '@/components/ui/Badge';
import { Button } from '@/components/ui/Button';
import { Skeleton } from '@/components/ui/Skeleton';
import { EmptyState, ErrorState } from '@/components/ui/States';
import {
  communityKeys,
  needsApi,
  type ModerationStatus,
  type NeedStatus,
} from '@/lib/api/community';
import { useDocumentTitle } from '@/lib/hooks/useDocumentTitle';
import { useT } from '@/lib/i18n';
import { formatDate } from '@/lib/utils/format';
import { useAuthStore } from '@/stores/authStore';
import { toast } from '@/stores/toastStore';
import { useUiStore } from '@/stores/uiStore';

const TONE: Record<ModerationStatus, 'neutral' | 'success' | 'danger'> = {
  pending: 'neutral',
  approved: 'success',
  rejected: 'danger',
};

/**
 * Your own needs, with the moderation state and the reason for a rejection.
 *
 * Same shape and same promise as MyListingsPage: "where did my post go?"
 * gets an answer, and a rejection carries its note verbatim. A rejection
 * with no explanation reads as a rebuke and costs the next post.
 */
export default function MyNeedsPage() {
  const { t, lang } = useT();
  const user = useAuthStore((s) => s.user);
  const loading = useAuthStore((s) => s.loading);
  const openAuth = useUiStore((s) => s.openAuth);
  const queryClient = useQueryClient();

  useDocumentTitle(t('needs.mine'));

  const needs = useQuery({
    queryKey: communityKeys.myNeeds(lang),
    queryFn: ({ signal }) => needsApi.mine(lang, signal),
    enabled: user !== null,
  });

  const setStatus = useMutation({
    mutationFn: ({ id, status }: { id: number; status: NeedStatus }) =>
      needsApi.setStatus(id, status),
    onSuccess: async () => {
      await queryClient.invalidateQueries({ queryKey: communityKeys.myNeeds(lang) });
    },
    onError: () => toast.error(t('needs.statusFailed')),
  });

  if (loading) return null;

  if (!user) {
    return (
      <EmptyState
        title={t('needs.signInTitle')}
        description={t('needs.signInText')}
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
        <h1 style={{ fontSize: '1.25rem' }}>{t('needs.mine')}</h1>
        <Link to="/needs/new" className="btn btn--primary btn--sm">
          {t('needs.post')}
        </Link>
      </header>

      {needs.isError && <ErrorState onRetry={() => void needs.refetch()} />}

      {needs.isPending && (
        <div style={{ display: 'grid', gap: '0.75rem' }}>
          {Array.from({ length: 3 }, (_, i) => (
            <Skeleton key={i} height={96} radius="var(--r-lg)" />
          ))}
        </div>
      )}

      {needs.data?.length === 0 && (
        <EmptyState
          title={t('needs.mineEmpty')}
          description={t('needs.mineEmptyText')}
          icon={<HandHeart size={22} />}
          action={
            <Link to="/needs/new" className="btn btn--primary btn--md">
              {t('needs.post')}
            </Link>
          }
        />
      )}

      {(needs.data ?? []).map((need) => (
        <article key={need.id} className="card listing-row listing-row--need">
          <div style={{ minWidth: 0, display: 'grid', gap: '0.3rem' }}>
            <div className="listing-row__head">
              {need.moderation_status === 'approved' ? (
                <Link to={`/needs/${need.id}`} style={{ fontWeight: 500 }}>
                  {need.title}
                </Link>
              ) : (
                <span style={{ fontWeight: 500 }}>{need.title}</span>
              )}
              <Badge tone={TONE[need.moderation_status]}>
                {t(`moderation.${need.moderation_status}`)}
              </Badge>
              <Badge tone="neutral">{t(`needs.status.${need.status}`)}</Badge>
            </div>

            <p className="subtle" style={{ fontSize: '0.8125rem' }}>
              <PlaceLine location={need.location} showDistance={false} />
              {' · '}
              {formatDate(need.created_at, lang)}
            </p>

            {need.moderation_status === 'pending' && (
              <p className="muted" style={{ fontSize: '0.8125rem' }}>
                {t('needs.pendingNote')}
              </p>
            )}

            {need.moderation_status === 'rejected' && need.moderation_note && (
              <p className="listing-row__note">{need.moderation_note}</p>
            )}
          </div>

          {/* Only the transitions the server will accept, so a button never
              produces a 409 (backend need_service.OWNER_TRANSITIONS). */}
          <div className="row-actions">
            {(need.status === 'open' || need.status === 'partially_fulfilled') && (
              <>
                <Button
                  size="sm"
                  disabled={setStatus.isPending}
                  onClick={() => setStatus.mutate({ id: need.id, status: 'fulfilled' })}
                >
                  {t('needs.markFulfilled')}
                </Button>
                <Button
                  size="sm"
                  variant="ghost"
                  disabled={setStatus.isPending}
                  onClick={() => setStatus.mutate({ id: need.id, status: 'closed' })}
                >
                  {t('needs.close')}
                </Button>
              </>
            )}
            {(need.status === 'closed' ||
              need.status === 'fulfilled' ||
              need.status === 'expired') && (
              <Button
                size="sm"
                disabled={setStatus.isPending}
                onClick={() => setStatus.mutate({ id: need.id, status: 'open' })}
              >
                {t('needs.reopen')}
              </Button>
            )}
          </div>
        </article>
      ))}
    </section>
  );
}
