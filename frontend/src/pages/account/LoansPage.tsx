import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { Repeat } from 'lucide-react';
import { Link } from 'react-router';

import { Badge } from '@/components/ui/Badge';
import { Button } from '@/components/ui/Button';
import { Skeleton } from '@/components/ui/Skeleton';
import { EmptyState, ErrorState } from '@/components/ui/States';
import {
  communityKeys,
  loansApi,
  type Loan,
  type LoanAction,
  type LoanStatus,
} from '@/lib/api/community';
import { useDocumentTitle } from '@/lib/hooks/useDocumentTitle';
import { useT } from '@/lib/i18n';
import { formatDate } from '@/lib/utils/format';
import { useAuthStore } from '@/stores/authStore';
import { toast } from '@/stores/toastStore';
import { useUiStore } from '@/stores/uiStore';

const TONE: Record<LoanStatus, 'neutral' | 'success' | 'warning' | 'danger' | 'accent'> = {
  pending: 'neutral',
  approved: 'accent',
  borrowed: 'warning',
  returned: 'success',
  rejected: 'danger',
  cancelled: 'neutral',
};

/**
 * Which buttons each party gets, per state.
 *
 * A MIRROR of the server's `ACTORS` table (app/services/loan_service.py), so
 * a button never produces a 409 or a 403. The server is still the authority -
 * this only keeps the UI from offering moves it knows will be refused.
 */
const ACTIONS: Record<LoanStatus, { owner: LoanAction[]; borrower: LoanAction[] }> = {
  pending: { owner: ['approved', 'rejected'], borrower: ['cancelled'] },
  approved: { owner: ['borrowed', 'cancelled'], borrower: ['cancelled'] },
  borrowed: { owner: ['returned'], borrower: [] },
  returned: { owner: [], borrower: [] },
  rejected: { owner: [], borrower: [] },
  cancelled: { owner: [], borrower: [] },
};

function LoanRow({
  loan,
  onAct,
  pending,
}: {
  loan: Loan;
  onAct: (id: number, action: LoanAction) => void;
  pending: boolean;
}) {
  const { t, lang } = useT();
  const role = loan.role ?? 'borrower';
  const actions = ACTIONS[loan.status][role];

  return (
    <article className="card listing-row">
      {loan.product_image ? (
        <img src={loan.product_image} alt="" width={64} height={64} loading="lazy" />
      ) : (
        <span className="cell-title__blank" aria-hidden="true" />
      )}

      <div style={{ minWidth: 0, display: 'grid', gap: '0.3rem' }}>
        <div className="listing-row__head">
          <Link to={`/products/${loan.product_slug}`} style={{ fontWeight: 500 }}>
            {loan.product_title}
          </Link>
          <Badge tone={TONE[loan.status]}>{t(`loan.status.${loan.status}`)}</Badge>
        </div>

        <p className="subtle" style={{ fontSize: '0.8125rem' }}>
          {role === 'owner'
            ? t('loan.borrowedBy', { name: loan.borrower_name })
            : t('loan.requestedOn', { date: formatDate(loan.created_at, lang) })}
        </p>

        {loan.expected_return_at && loan.status === 'borrowed' && (
          <p className="muted" style={{ fontSize: '0.8125rem' }}>
            {t('loan.dueBack', { date: formatDate(loan.expected_return_at, lang) })}
          </p>
        )}

        {loan.message && <p className="listing-row__note">{loan.message}</p>}
      </div>

      <div className="row-actions">
        {actions.map((action) => (
          <Button
            key={action}
            size="sm"
            variant={action === 'approved' ? 'primary' : 'secondary'}
            disabled={pending}
            onClick={() => onAct(loan.id, action)}
          >
            {t(`loan.action.${action}`)}
          </Button>
        ))}
        {/* Approved and borrowed loans both need a doorstep arranged, and the
            thread already exists - the server opens it on approval. */}
        {(loan.status === 'approved' || loan.status === 'borrowed') && (
          <Link to="/messages" className="btn btn--ghost btn--sm">
            {t('messages.title')}
          </Link>
        )}
      </div>
    </article>
  );
}

/**
 * "Müvəqqəti götürdüklərim / verdiklərim" (FreeShop_Prompt 7, 10).
 *
 * Both directions on one page: the same person is a borrower on one row and
 * a lender on the next, and two routes for one mental model is one route too
 * many.
 */
export default function LoansPage() {
  const { t, lang } = useT();
  const user = useAuthStore((s) => s.user);
  const loading = useAuthStore((s) => s.loading);
  const openAuth = useUiStore((s) => s.openAuth);
  const queryClient = useQueryClient();

  useDocumentTitle(t('loan.title'));

  const borrowed = useQuery({
    queryKey: communityKeys.borrowed(lang),
    queryFn: ({ signal }) => loansApi.borrowed(lang, signal),
    enabled: user !== null,
  });

  const lent = useQuery({
    queryKey: communityKeys.lent(lang),
    queryFn: ({ signal }) => loansApi.lent(lang, signal),
    enabled: user !== null,
  });

  const act = useMutation({
    mutationFn: ({ id, status }: { id: number; status: LoanAction }) => loansApi.act(id, status),
    onSuccess: async () => {
      await queryClient.invalidateQueries({ queryKey: communityKeys.borrowed(lang) });
      await queryClient.invalidateQueries({ queryKey: communityKeys.lent(lang) });
      await queryClient.invalidateQueries({ queryKey: communityKeys.conversations(lang) });
    },
    onError: () => toast.error(t('loan.actionFailed')),
  });

  if (loading) return null;

  if (!user) {
    return (
      <EmptyState
        title={t('loan.signInTitle')}
        description={t('loan.signInText')}
        icon={<Repeat size={22} />}
        action={
          <Button variant="primary" onClick={openAuth}>
            {t('common.signIn')}
          </Button>
        }
      />
    );
  }

  const onAct = (id: number, status: LoanAction) => act.mutate({ id, status });
  const isPending = borrowed.isPending || lent.isPending;
  const isError = borrowed.isError || lent.isError;

  return (
    <section style={{ display: 'grid', gap: '1.5rem' }}>
      <header className="section-head">
        <h1 style={{ fontSize: '1.25rem' }}>{t('loan.title')}</h1>
        <Link to="/products?transfer_type=loan" className="btn btn--secondary btn--sm">
          {t('loan.browse')}
        </Link>
      </header>

      {isError && (
        <ErrorState
          onRetry={() => {
            void borrowed.refetch();
            void lent.refetch();
          }}
        />
      )}

      {isPending && <Skeleton height={96} radius="var(--r-lg)" />}

      <section aria-labelledby="borrowed" style={{ display: 'grid', gap: '0.75rem' }}>
        <h2 id="borrowed" style={{ fontSize: '1rem' }}>
          {t('loan.borrowedTitle')}
        </h2>
        {borrowed.data?.length === 0 && (
          <EmptyState title={t('loan.borrowedEmpty')} description={t('loan.borrowedEmptyText')} />
        )}
        {(borrowed.data ?? []).map((loan) => (
          <LoanRow key={loan.id} loan={loan} onAct={onAct} pending={act.isPending} />
        ))}
      </section>

      <section aria-labelledby="lent" style={{ display: 'grid', gap: '0.75rem' }}>
        <h2 id="lent" style={{ fontSize: '1rem' }}>
          {t('loan.lentTitle')}
        </h2>
        {lent.data?.length === 0 && (
          <EmptyState title={t('loan.lentEmpty')} description={t('loan.lentEmptyText')} />
        )}
        {(lent.data ?? []).map((loan) => (
          <LoanRow key={loan.id} loan={loan} onAct={onAct} pending={act.isPending} />
        ))}
      </section>
    </section>
  );
}
