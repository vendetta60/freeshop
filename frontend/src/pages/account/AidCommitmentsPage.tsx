import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { LifeBuoy } from 'lucide-react';
import { Link } from 'react-router';

import { Badge } from '@/components/ui/Badge';
import { Button } from '@/components/ui/Button';
import { Skeleton } from '@/components/ui/Skeleton';
import { EmptyState, ErrorState } from '@/components/ui/States';
import { aidApi, communityKeys, type CommitmentStatus } from '@/lib/api/community';
import { useDocumentTitle } from '@/lib/hooks/useDocumentTitle';
import { useT } from '@/lib/i18n';
import { formatDate } from '@/lib/utils/format';
import { useAuthStore } from '@/stores/authStore';
import { toast } from '@/stores/toastStore';
import { useUiStore } from '@/stores/uiStore';

const TONE: Record<CommitmentStatus, 'neutral' | 'accent' | 'success'> = {
  offered: 'neutral',
  accepted: 'accent',
  received: 'success',
  cancelled: 'neutral',
};

/**
 * "Yardım təkliflərim" - what you have offered (FreeShop_Prompt 10).
 *
 * Withdrawing is available right up until the item is marked received.
 * Somebody whose circumstances change has to be able to say so without
 * asking permission - and an offer that cannot be withdrawn is one people
 * hesitate to make.
 */
export default function AidCommitmentsPage() {
  const { t, lang } = useT();
  const user = useAuthStore((s) => s.user);
  const loading = useAuthStore((s) => s.loading);
  const openAuth = useUiStore((s) => s.openAuth);
  const queryClient = useQueryClient();

  useDocumentTitle(t('aid.mine'));

  const commitments = useQuery({
    queryKey: communityKeys.myCommitments(lang),
    queryFn: ({ signal }) => aidApi.myCommitments(lang, signal),
    enabled: user !== null,
  });

  const withdraw = useMutation({
    mutationFn: (id: number) => aidApi.withdraw(id),
    onSuccess: async () => {
      await queryClient.invalidateQueries({ queryKey: communityKeys.myCommitments(lang) });
    },
    onError: () => toast.error(t('aid.withdrawFailed')),
  });

  if (loading) return null;

  if (!user) {
    return (
      <EmptyState
        title={t('aid.signInTitle')}
        description={t('aid.signInText')}
        icon={<LifeBuoy size={22} />}
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
        <h1 style={{ fontSize: '1.25rem' }}>{t('aid.mine')}</h1>
        <Link to="/aid" className="btn btn--secondary btn--sm">
          {t('aid.title')}
        </Link>
      </header>

      {commitments.isError && <ErrorState onRetry={() => void commitments.refetch()} />}
      {commitments.isPending && <Skeleton height={88} radius="var(--r-lg)" />}

      {commitments.data?.length === 0 && (
        <EmptyState
          title={t('aid.mineEmpty')}
          description={t('aid.mineEmptyText')}
          icon={<LifeBuoy size={22} />}
          action={
            <Link to="/aid" className="btn btn--primary btn--md">
              {t('aid.title')}
            </Link>
          }
        />
      )}

      {(commitments.data ?? []).map((commitment) => (
        <article key={commitment.id} className="card listing-row listing-row--need">
          <div style={{ minWidth: 0, display: 'grid', gap: '0.3rem' }}>
            <div className="listing-row__head">
              <span style={{ fontWeight: 500 }}>{commitment.item_title}</span>
              <Badge tone={TONE[commitment.status]}>
                {t(`aid.commitment.${commitment.status}`)}
              </Badge>
            </div>
            <p className="subtle" style={{ fontSize: '0.8125rem' }}>
              {commitment.case_title} · {t('aid.quantityOf', { count: commitment.quantity })} ·{' '}
              {formatDate(commitment.created_at, lang)}
            </p>
          </div>

          <div className="row-actions">
            {(commitment.status === 'offered' || commitment.status === 'accepted') && (
              <Button
                size="sm"
                variant="ghost"
                disabled={withdraw.isPending}
                onClick={() => withdraw.mutate(commitment.id)}
              >
                {t('aid.withdraw')}
              </Button>
            )}
          </div>
        </article>
      ))}
    </section>
  );
}
