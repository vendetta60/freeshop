import { useQueryClient } from '@tanstack/react-query';
import { Check, Loader2, Mail, MessageCircle, Minus, Phone, Plus, Trash2 } from 'lucide-react';
import { useState } from 'react';
import { Link } from 'react-router';

import { Button } from '@/components/ui/Button';
import { type Contact, type OrderRequest, cartKeys, orderApi } from '@/lib/api/cart';
import { ApiError } from '@/lib/api/client';
import { useDocumentTitle } from '@/lib/hooks/useDocumentTitle';
import { useT } from '@/lib/i18n';
import { randomId } from '@/lib/utils/id';
import { useCart } from '@/lib/hooks/useCart';
import { Price } from '@/components/ui/Price';
import { useAuthStore } from '@/stores/authStore';
import { useUiStore } from '@/stores/uiStore';

/**
 * Basket and request submission.
 *
 * There is no checkout: submitting produces an order REQUEST on the server,
 * which clears the cart and returns the seller's contact channels
 * (plan.md 9.1). The request number comes from the server, not from here.
 */
export default function CartPage() {
  const { t } = useT();
  const { cart, setQuantity, remove } = useCart();
  const user = useAuthStore((s) => s.user);
  const openAuth = useUiStore((s) => s.openAuth);
  const queryClient = useQueryClient();

  const [note, setNote] = useState('');
  const [phone, setPhone] = useState(user?.phone ?? '');
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [done, setDone] = useState<{ request: OrderRequest; contact: Contact } | null>(null);

  // Stable for the life of this page, so a double-tapped submit or a retry
  // after a dropped response returns the original request rather than a
  // second one (plan.md 6.1).
  const [idempotencyKey] = useState(randomId);
  useDocumentTitle(t('cart.title'));

  const submit = async () => {
    setBusy(true);
    setError(null);
    try {
      const payload: { contact_phone: string; note?: string } = { contact_phone: phone.trim() };
      if (note.trim()) payload.note = note.trim();

      const result = await orderApi.submit(payload, idempotencyKey);
      setDone(result);
      await queryClient.invalidateQueries({ queryKey: cartKeys.cart() });
    } catch (err) {
      if (err instanceof ApiError && err.code === 'PRODUCT_UNAVAILABLE') {
        setError(t('cart.errorUnavailable'));
      } else if (err instanceof ApiError && err.code === 'CART_EMPTY') {
        setError(t('cart.errorEmpty'));
      } else {
        setError(t('cart.errorGeneric'));
      }
    } finally {
      setBusy(false);
    }
  };

  if (!user) {
    return (
      <div className="empty-state">
        <h1 style={{ fontSize: '1.375rem' }}>{t('cart.signInTitle')}</h1>
        <p className="muted">{t('cart.signInText')}</p>
        <Button variant="primary" onClick={openAuth}>
          {t('common.signIn')}
        </Button>
      </div>
    );
  }

  if (done) {
    return (
      <div className="card success-panel">
        <span className="success-panel__tick">
          <Check size={22} aria-hidden="true" />
        </span>
        <h1 style={{ fontSize: '1.375rem' }}>{t('cart.sentTitle')}</h1>
        <p className="muted">
          {t('cart.requestNo')} <strong className="tabular">{done.request.request_no}</strong>
        </p>
        <p className="muted">{t('cart.sentText')}</p>

        <div style={{ display: 'grid', gap: '0.5rem' }}>
          {done.contact.phone && (
            <a className="contact-row" href={`tel:${done.contact.phone.replace(/\s/g, '')}`}>
              <Phone size={16} aria-hidden="true" />
              <span className="tabular">{done.contact.phone}</span>
            </a>
          )}
          {done.contact.whatsapp && (
            <a className="contact-row" href={`https://wa.me/${done.contact.whatsapp}`}>
              <MessageCircle size={16} aria-hidden="true" />
              WhatsApp
            </a>
          )}
          {done.contact.email && (
            <a className="contact-row" href={`mailto:${done.contact.email}`}>
              <Mail size={16} aria-hidden="true" />
              {done.contact.email}
            </a>
          )}
        </div>

        <Button variant="secondary">
          <Link to="/products" style={{ color: 'inherit', textDecoration: 'none' }}>
            {t('cart.backToCatalogue')}
          </Link>
        </Button>
      </div>
    );
  }

  if (cart.lines.length === 0) {
    return (
      <div className="empty-state">
        <h1 style={{ fontSize: '1.375rem' }}>{t('cart.empty')}</h1>
        <p className="muted">{t('cart.emptyText')}</p>
        <Button variant="primary">
          <Link to="/products" style={{ color: 'inherit', textDecoration: 'none' }}>
            Kataloqa bax
          </Link>
        </Button>
      </div>
    );
  }

  const phoneValid = phone.replace(/\D/g, '').length >= 9;

  return (
    <>
      <div className="hero" style={{ paddingBottom: '1.25rem' }}>
        <h1>{t('cart.title')}</h1>
        <p>{t('cart.lead')}</p>
      </div>

      <div className="cart-layout">
        <ul className="cart-list">
          {cart.lines.map(({ id: lineId, product, quantity, line_total_minor }) => (
            <li key={lineId} className="card cart-row">
              <div className="cart-line__media cart-line__media--lg">
                {product.image ? <img src={product.image} alt="" loading="lazy" /> : null}
              </div>
              <div style={{ flex: 1, minWidth: 0 }}>
                <Link to={`/products/${product.slug}`} className="cart-row__title">
                  {product.title}
                </Link>
                <p className="muted tabular" style={{ fontSize: '0.875rem' }}>
                  <Price minor={product.price_minor} /> × {quantity}
                </p>
                <div className="stepper">
                  <button
                    type="button"
                    onClick={() => {
                      setQuantity.mutate({ lineId, quantity: quantity - 1 });
                    }}
                    aria-label="Azalt"
                  >
                    <Minus size={13} aria-hidden="true" />
                  </button>
                  <span className="tabular">{quantity}</span>
                  <button
                    type="button"
                    onClick={() => {
                      setQuantity.mutate({ lineId, quantity: quantity + 1 });
                    }}
                    aria-label={t('cart.increase')}
                  >
                    <Plus size={13} aria-hidden="true" />
                  </button>
                  <button
                    type="button"
                    className="stepper__remove"
                    onClick={() => {
                      remove.mutate(lineId);
                    }}
                    aria-label={t('cart.remove')}
                  >
                    <Trash2 size={13} aria-hidden="true" />
                  </button>
                </div>
              </div>
              <strong className="tabular" style={{ whiteSpace: 'nowrap' }}>
                <Price minor={line_total_minor} />
              </strong>
            </li>
          ))}
        </ul>

        <aside className="card cart-summary">
          <h2 style={{ fontSize: '1rem' }}>{t('cart.requestDetails')}</h2>

          <label htmlFor="cart-phone" className="ks-label" style={{ marginBottom: 0 }}>
            {t('cart.phone')}
          </label>
          <input
            id="cart-phone"
            className="input"
            inputMode="tel"
            placeholder="+994 50 000 00 00"
            value={phone}
            onChange={(e) => {
              setPhone(e.target.value);
            }}
          />

          <label htmlFor="cart-note" className="ks-label" style={{ marginBottom: 0 }}>
            {t('cart.note')}
          </label>
          <textarea
            id="cart-note"
            className="input"
            style={{ height: 84, padding: '0.6rem 0.875rem', resize: 'vertical' }}
            maxLength={1000}
            placeholder={t('cart.notePlaceholder')}
            value={note}
            onChange={(e) => {
              setNote(e.target.value);
            }}
          />

          <div className="drawer__total">
            <span className="muted">{t('common.total')}</span>
            <strong className="tabular" style={{ fontSize: '1.25rem' }}>
              <Price minor={cart.total_minor} />
            </strong>
          </div>

          {error && <p style={{ color: 'var(--danger)', fontSize: '0.8125rem' }}>{error}</p>}

          <Button
            variant="primary"
            size="lg"
            onClick={() => void submit()}
            disabled={!phoneValid || busy}
          >
            {busy ? <Loader2 size={16} className="spin" aria-hidden="true" /> : null}
            {t('cart.submit')}
          </Button>
          <p className="subtle" style={{ fontSize: '0.75rem' }}>
            {!phoneValid ? t('cart.needPhone') : t('cart.noCharge')}
          </p>
        </aside>
      </div>
    </>
  );
}
