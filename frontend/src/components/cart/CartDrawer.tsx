import { Minus, Plus, ShoppingBag, Trash2, X } from 'lucide-react';
import { useEffect, useRef } from 'react';
import { useNavigate } from 'react-router';

import { Button } from '@/components/ui/Button';
import { useCart } from '@/lib/hooks/useCart';
import { useT } from '@/lib/i18n';
import { useUiStore } from '@/stores/uiStore';
import { Price } from '@/components/ui/Price';

/**
 * Cart drawer - one of the seven permitted glass surfaces (plan.md 3.5).
 *
 * Focus is trapped while open and restored on close; Escape dismisses. Radix
 * would give this for free and replaces it in phase 7, but a drawer that
 * traps keyboard users is not acceptable in the meantime.
 */
export function CartDrawer() {
  const { t } = useT();
  const open = useUiStore((s) => s.cartOpen);
  const closeCart = useUiStore((s) => s.closeCart);
  const { cart, setQuantity, remove } = useCart();
  const lines = cart.lines;
  const total = cart.total_minor;
  const navigate = useNavigate();

  const panelRef = useRef<HTMLDivElement>(null);
  const restoreTo = useRef<HTMLElement | null>(null);

  useEffect(() => {
    if (!open) return;
    restoreTo.current = document.activeElement as HTMLElement | null;
    panelRef.current?.focus();

    const onKeyDown = (event: KeyboardEvent) => {
      if (event.key === 'Escape') closeCart();
      if (event.key !== 'Tab') return;
      const focusable = panelRef.current?.querySelectorAll<HTMLElement>(
        'button, a[href], input, [tabindex]:not([tabindex="-1"])',
      );
      if (!focusable?.length) return;
      const first = focusable[0];
      const last = focusable[focusable.length - 1];
      if (!first || !last) return;
      if (event.shiftKey && document.activeElement === first) {
        event.preventDefault();
        last.focus();
      } else if (!event.shiftKey && document.activeElement === last) {
        event.preventDefault();
        first.focus();
      }
    };

    document.addEventListener('keydown', onKeyDown);
    document.body.style.overflow = 'hidden';
    return () => {
      document.removeEventListener('keydown', onKeyDown);
      document.body.style.overflow = '';
      restoreTo.current?.focus();
    };
  }, [open, closeCart]);

  if (!open) return null;

  return (
    <>
      <button type="button" className="scrim" aria-label={t('common.close')} onClick={closeCart} />
      <aside
        ref={panelRef}
        tabIndex={-1}
        role="dialog"
        aria-modal="true"
        aria-label={t('nav.cartShort')}
        className="glass glass--specular glass--deep drawer"
      >
        <header className="drawer__head">
          <h2 style={{ fontSize: '1.0625rem' }}>{t('cart.title')}</h2>
          <Button variant="ghost" size="sm" icon onClick={closeCart} aria-label={t('common.close')}>
            <X size={16} aria-hidden="true" />
          </Button>
        </header>

        {lines.length === 0 ? (
          <div className="drawer__empty">
            <ShoppingBag size={28} aria-hidden="true" className="subtle" />
            <p className="muted">{t('cart.empty')}</p>
            <Button
              variant="secondary"
              onClick={() => {
                closeCart();
                void navigate('/products');
              }}
            >
              Kataloqa bax
            </Button>
          </div>
        ) : (
          <>
            <ul className="drawer__list">
              {lines.map(({ id: lineId, product, quantity }) => (
                <li key={lineId} className="cart-line">
                  <div className="cart-line__media">
                    {product.image ? (
                      <img src={product.image} alt="" loading="lazy" />
                    ) : (
                      <span className="subtle" style={{ fontSize: '0.6875rem' }}>
                        —
                      </span>
                    )}
                  </div>
                  <div style={{ minWidth: 0, flex: 1 }}>
                    <p className="cart-line__title">{product.title}</p>
                    <p className="tabular" style={{ fontWeight: 600, fontSize: '0.9375rem' }}>
                      <Price minor={product.price_minor * quantity} />
                    </p>
                    <div className="stepper">
                      <button
                        type="button"
                        onClick={() => {
                          setQuantity.mutate({ lineId, quantity: quantity - 1 });
                        }}
                        aria-label={t('cart.decrease')}
                      >
                        <Minus size={13} aria-hidden="true" />
                      </button>
                      <span className="tabular" aria-live="polite">
                        {quantity}
                      </span>
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
                </li>
              ))}
            </ul>

            <footer className="drawer__foot">
              <div className="drawer__total">
                <span className="muted">{t('common.total')}</span>
                <strong className="tabular" style={{ fontSize: '1.125rem' }}>
                  <Price minor={total} />
                </strong>
              </div>
              <Button
                variant="primary"
                size="lg"
                onClick={() => {
                  closeCart();
                  void navigate('/cart');
                }}
              >
                {t('cart.viewCart')}
              </Button>
              <p className="subtle" style={{ fontSize: '0.75rem', textAlign: 'center' }}>
                {t('cart.noPaymentNote')}
              </p>
            </footer>
          </>
        )}
      </aside>
    </>
  );
}
