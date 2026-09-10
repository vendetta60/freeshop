import { useQuery } from '@tanstack/react-query';
import { Package } from 'lucide-react';
import { useState } from 'react';
import { Link } from 'react-router';

import { RequestCard } from '@/components/account/RequestCard';
import { KeepAsNeedPrompt } from '@/components/community/KeepAsNeedPrompt';
import { Button } from '@/components/ui/Button';
import { Skeleton } from '@/components/ui/Skeleton';
import { EmptyState, ErrorState } from '@/components/ui/States';
import { cartKeys, orderApi } from '@/lib/api/cart';
import { useDocumentTitle } from '@/lib/hooks/useDocumentTitle';
import { useT } from '@/lib/i18n';
import { useAuthStore } from '@/stores/authStore';
import { useUiStore } from '@/stores/uiStore';

/**
 * The buyer's own request history (plan.md 13, phase 10).
 *
 * Every request is server-side filtered by the user id in the token, never by
 * an id from the URL (plan.md 10, IDOR), so this page cannot be turned into
 * someone else's history by editing the address bar.
 */
export default function OrdersPage() {
  const { t } = useT();
  const user = useAuthStore((s) => s.user);
  const loading = useAuthStore((s) => s.loading);
  const openAuth = useUiStore((s) => s.openAuth);

  const requests = useQuery({
    queryKey: cartKeys.myRequests(),
    queryFn: ({ signal }) => orderApi.mine(signal),
    enabled: user !== null,
  });

  // Dismissals are per session on purpose: remembering "no thanks" forever
  // would be a column and a migration to avoid asking a question that costs
  // nothing to ask again (components/community/KeepAsNeedPrompt.tsx).
  const [dismissed, setDismissed] = useState<number[]>([]);

  useDocumentTitle(t('orders.title'));
  if (loading) return null;

  if (!user) {
    return (
      <EmptyState
        title={t('orders.signInTitle')}
        description={t('orders.signInText')}
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
        <h1 style={{ fontSize: '1.25rem' }}>{t('orders.title')}</h1>
      </header>

      {/* "Bu əşyanı ala bilmədiniz" - the consent step that turns an
          unsuccessful request into visible local demand (Rule C). Above the
          history, because it is the only thing on this page that asks for a
          decision. */}
      <KeepAsNeedPrompt
        dismissed={dismissed}
        onDismiss={(id) => setDismissed((current) => [...current, id])}
      />

      {requests.isError && <ErrorState onRetry={() => void requests.refetch()} />}

      {requests.isPending && (
        <div style={{ display: 'grid', gap: '0.75rem' }}>
          {Array.from({ length: 3 }, (_, i) => (
            <Skeleton key={i} height={132} radius="var(--r-lg)" />
          ))}
        </div>
      )}

      {requests.data?.length === 0 && (
        <EmptyState
          title={t('orders.empty')}
          description={t('orders.emptyText')}
          icon={<Package size={22} />}
          action={
            <Link to="/products" className="btn btn--primary btn--md">
              {t('home.browse')}
            </Link>
          }
        />
      )}

      {(requests.data ?? []).map((request) => (
        <RequestCard key={request.id} request={request} />
      ))}
    </section>
  );
}
