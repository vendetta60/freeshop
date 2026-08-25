import { Home, LayoutGrid, Search, ShoppingBag, User } from 'lucide-react';
import { useLocation, useNavigate } from 'react-router';

import { useCartCount } from '@/lib/hooks/useCart';
import { useT } from '@/lib/i18n';
import { useUiStore } from '@/stores/uiStore';

/**
 * Mobile navigation - an iOS-style glass tab bar (plan.md 3.6), fixed to the
 * bottom and honouring env(safe-area-inset-bottom).
 *
 * Search and Cart are actions rather than routes: they open the palette and
 * the drawer respectively, which is what makes them feel native.
 */
const TABS = [
  { key: 'home', labelKey: 'nav.home', Icon: Home, to: '/' },
  { key: 'catalogue', labelKey: 'nav.catalogue', Icon: LayoutGrid, to: '/products' },
  { key: 'search', labelKey: 'nav.searchTab', Icon: Search, action: 'palette' as const },
  { key: 'cart', labelKey: 'nav.cartShort', Icon: ShoppingBag, action: 'cart' as const },
  { key: 'profile', labelKey: 'nav.contact', Icon: User, to: '/contact' },
];

export function TabBar() {
  const { t } = useT();
  const navigate = useNavigate();
  const { pathname } = useLocation();
  const cartCount = useCartCount();
  const setPaletteOpen = useUiStore((s) => s.setPaletteOpen);
  const openCart = useUiStore((s) => s.openCart);

  return (
    <nav className="glass glass--specular glass-tabbar" aria-label={t('nav.main')}>
      <div style={{ display: 'flex' }}>
        {TABS.map(({ key, labelKey, Icon, to, action }) => {
          const current =
            to !== undefined && (to === '/' ? pathname === '/' : pathname.startsWith(to));
          return (
            <button
              key={key}
              type="button"
              className="tab"
              aria-current={current ? 'page' : undefined}
              onClick={() => {
                if (action === 'palette') setPaletteOpen(true);
                else if (action === 'cart') openCart();
                else if (to) void navigate(to);
              }}
            >
              <span style={{ position: 'relative', display: 'grid', placeItems: 'center' }}>
                <Icon size={20} aria-hidden="true" />
                {key === 'cart' && cartCount > 0 && (
                  <span className="cart-dot tabular" aria-hidden="true">
                    {cartCount}
                  </span>
                )}
              </span>
              {t(labelKey)}
            </button>
          );
        })}
      </div>
    </nav>
  );
}
