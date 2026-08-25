import { useQuery } from '@tanstack/react-query';
import { ArrowLeft, Mail, MessageCircle, Phone } from 'lucide-react';
import { Link, useParams } from 'react-router';

import { RequestCard } from '@/components/account/RequestCard';
import { Button } from '@/components/ui/Button';
import { Skeleton } from '@/components/ui/Skeleton';
import { EmptyState, ErrorState } from '@/components/ui/States';
import { cartKeys, orderApi } from '@/lib/api/cart';
import { catalogueApi, catalogueKeys } from '@/lib/api/catalogue';
import { ApiError } from '@/lib/api/client';
import { useDocumentTitle } from '@/lib/hooks/useDocumentTitle';
import { useT } from '@/lib/i18n';
import { useAuthStore } from '@/stores/authStore';
import { useUiStore } from '@/stores/uiStore';

/**
 * One request, deep-linkable.
 *
 * The seller's channels are shown here as well as on the confirmation screen:
 * this is the page someone comes back to days later, and "we received it" with
 * no way to reach anyone is the failure the whole flow exists to avoid
 * (plan.md 9.1).
 */
export default function OrderDetailPage() {
  const { t, lang } = useT();
  const params = useParams();
  const id = Number(params.id);
  const user = useAuthStore((s) => s.user);
  const loading = useAuthStore((s) => s.loading);
  const openAuth = useUiStore((s) => s.openAuth);

  const request = useQuery({
    queryKey: cartKeys.myRequest(id),
    queryFn: ({ signal }) => orderApi.byId(id, signal),
    enabled: user !== null && Number.isFinite(id),
    retry: (count, error) => !(error instanceof ApiError && error.status === 404) && count < 2,
  });

  const contact = useQuery({
    queryKey: catalogueKeys.contact(lang),
    queryFn: ({ signal }) => catalogueApi.contact(lang, signal),
    staleTime: 5 * 60_000,
  });

  useDocumentTitle(request.data?.request_no ?? null);

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

  // A request that is not yours is a 404, not a 403 - the server never
  // confirms that someone else's id exists (plan.md 10, IDOR).
  if (request.error instanceof ApiError && request.error.status === 404) {
    return <EmptyState title={t('notFound.title')} description={t('orders.emptyText')} />;
  }

  if (request.isError) {
    return <ErrorState onRetry={() => void request.refetch()} />;
  }

  return (
    <section style={{ display: 'grid', gap: '1rem', maxWidth: '46rem' }}>
      <header className="section-head">
        <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
          <Link
            to="/profile/orders"
            className="btn btn--ghost btn--sm btn--icon"
            aria-label={t('common.back')}
          >
            <ArrowLeft size={16} aria-hidden="true" />
          </Link>
          <h1 style={{ fontSize: '1.25rem' }}>{t('orders.title')}</h1>
        </div>
      </header>

      {request.isPending ? (
        <Skeleton height={200} radius="var(--r-lg)" />
      ) : (
        <RequestCard request={request.data} linked={false} />
      )}

      {contact.data && (
        <div className="card" style={{ display: 'grid', gap: '0.5rem', padding: '1rem' }}>
          <p className="muted">{t('cart.sentText')}</p>
          {contact.data.phone && (
            <a className="contact-row" href={`tel:${contact.data.phone.replace(/\s/g, '')}`}>
              <Phone size={16} aria-hidden="true" />
              <span className="tabular">{contact.data.phone}</span>
            </a>
          )}
          {contact.data.whatsapp && (
            <a className="contact-row" href={`https://wa.me/${contact.data.whatsapp}`}>
              <MessageCircle size={16} aria-hidden="true" />
              {t('contact.whatsapp')}
            </a>
          )}
          {contact.data.email && (
            <a className="contact-row" href={`mailto:${contact.data.email}`}>
              <Mail size={16} aria-hidden="true" />
              {contact.data.email}
            </a>
          )}
        </div>
      )}
    </section>
  );
}
