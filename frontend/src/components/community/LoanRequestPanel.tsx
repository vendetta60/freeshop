import { useMutation } from '@tanstack/react-query';
import { Loader2, Repeat } from 'lucide-react';
import { useState } from 'react';
import { Link, useNavigate } from 'react-router';

import { Button } from '@/components/ui/Button';
import { TextAreaField, TextField } from '@/components/ui/Field';
import { ApiError } from '@/lib/api/client';
import { loansApi } from '@/lib/api/community';
import type { ProductDetail } from '@/lib/api/catalogue';
import { useT } from '@/lib/i18n';
import { formatDate } from '@/lib/utils/format';
import { useAuthStore } from '@/stores/authStore';
import { toast } from '@/stores/toastStore';
import { useUiStore } from '@/stores/uiStore';

/**
 * "Müvəqqəti götür" - ask to borrow (FreeShop_Prompt 7).
 *
 * Renders nothing for a give-away, which is every listing this board had
 * before lending existed. A borrow form on a permanent gift would be a
 * question with no meaning.
 *
 * When the item is already out with somebody, the panel says so instead of
 * offering a button that will be refused - the server enforces one live loan
 * per listing regardless (loan_service.transition), this just does not waste
 * the visitor's time.
 */
export function LoanRequestPanel({ product }: { product: ProductDetail }) {
  const { t, lang } = useT();
  const navigate = useNavigate();
  const user = useAuthStore((s) => s.user);
  const openAuth = useUiStore((s) => s.openAuth);

  const [days, setDays] = useState(String(product.max_borrow_days ?? 7));
  const [message, setMessage] = useState('');

  const ask = useMutation({
    mutationFn: () =>
      loansApi.requestLoan({
        product_id: product.id,
        requested_days: Number(days) || undefined,
        message: message.trim() || undefined,
      }),
    onSuccess: () => {
      toast.success(t('loan.requested'));
      void navigate('/profile/loans');
    },
    onError: (error) => {
      if (error instanceof ApiError) {
        const reason = typeof error.details.reason === 'string' ? error.details.reason : '';
        if (reason === 'already_requested') return toast.error(t('loan.alreadyRequested'));
        if (reason === 'already_lent') return toast.error(t('loan.alreadyLent'));
        if (reason === 'window_closed') return toast.error(t('loan.windowClosed'));
        if (error.code === 'PHONE_NOT_VERIFIED') return toast.error(t('loan.needsPhone'));
      }
      toast.error(t('loan.requestFailed'));
    },
  });

  if (product.transfer_type !== 'loan') return null;

  return (
    <section className="card loan-panel" aria-labelledby="loan-panel">
      <h2 id="loan-panel" style={{ fontSize: '1rem' }}>
        <Repeat size={16} aria-hidden="true" style={{ verticalAlign: '-3px' }} />{' '}
        {t('loan.panelTitle')}
      </h2>

      <p className="muted" style={{ fontSize: '0.8125rem' }}>
        {t('loan.panelExplain')}
      </p>

      <dl className="loan-terms">
        {product.available_until && (
          <>
            <dt>{t('loan.availableUntil')}</dt>
            <dd>{formatDate(product.available_until, lang)}</dd>
          </>
        )}
        {product.max_borrow_days && (
          <>
            <dt>{t('loan.maxDays')}</dt>
            <dd className="tabular">{t('loan.days', { count: product.max_borrow_days })}</dd>
          </>
        )}
      </dl>

      {product.loan_state !== 'available' ? (
        <p className="nearby-note" role="status">
          {t(`loan.unavailable.${product.loan_state}`)}
        </p>
      ) : !user ? (
        <Button variant="primary" onClick={openAuth}>
          {t('loan.signInToBorrow')}
        </Button>
      ) : !user.phone_verified ? (
        // The gate is enforced server-side; saying so here means nobody
        // fills in the form only to be refused at the end of it.
        <p className="nearby-note" role="status">
          {t('loan.needsPhone')} <Link to="/profile">{t('offer.toProfile')}</Link>
        </p>
      ) : (
        <form
          className="admin__form"
          onSubmit={(e) => {
            e.preventDefault();
            ask.mutate();
          }}
        >
          <TextField
            label={t('loan.howLong')}
            type="number"
            min={1}
            max={product.max_borrow_days ?? 365}
            value={days}
            onChange={(e) => setDays(e.target.value)}
          />
          <TextAreaField
            label={t('loan.message')}
            rows={3}
            value={message}
            maxLength={1000}
            placeholder={t('loan.messagePlaceholder')}
            onChange={(e) => setMessage(e.target.value)}
          />
          <Button variant="primary" type="submit" disabled={ask.isPending}>
            {ask.isPending && <Loader2 size={15} className="spin" aria-hidden="true" />}
            {t('loan.ask')}
          </Button>
        </form>
      )}
    </section>
  );
}
