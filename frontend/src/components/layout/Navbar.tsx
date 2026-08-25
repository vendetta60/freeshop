import { LayoutGrid, Moon, Palette, Search, ShoppingBag, Sun } from 'lucide-react';
import { Link } from 'react-router';

import { brand } from '@/brand/brand.config';
import { Logo } from '@/brand/Logo';
import { AccountMenu } from '@/components/layout/AccountMenu';
import { CategoryMenu } from '@/components/layout/CategoryMenu';
import { Button } from '@/components/ui/Button';
import { useT, useLangStore } from '@/lib/i18n';
import { enabledLangs } from '@/lib/site/config';
import { authApi } from '@/lib/api/auth';
import { useTheme } from '@/lib/hooks/useTheme';
import { useCartCount } from '@/lib/hooks/useCart';
import { useAuthStore } from '@/stores/authStore';
import { useUiStore } from '@/stores/uiStore';

/**
 * Desktop navigation - a floating glass pill, inset from the viewport
 * (plan.md 3.6). One of the seven surfaces permitted to use glass.
 */
export function Navbar() {
  const { t, lang } = useT();
  const toggleLang = useLangStore((s) => s.toggle);
  const signedIn = useAuthStore((s) => s.user !== null);
  const { resolvedTheme, accent, toggleTheme, toggleAccent } = useTheme();
  const cartCount = useCartCount();

  const toggleCategoryMenu = useUiStore((s) => s.toggleCategoryMenu);
  const setPaletteOpen = useUiStore((s) => s.setPaletteOpen);
  const openCart = useUiStore((s) => s.openCart);

  // Two states only. The icon shows what you will GET, not what you have -
  // a moon means "switch to dark", which is the convention people expect.
  const ThemeIcon = resolvedTheme === 'dark' ? Sun : Moon;
  const themeLabel = resolvedTheme === 'dark' ? t('nav.toLight') : t('nav.toDark');

  const switchLanguage = () => {
    toggleLang();
    // Signed-in visitors carry their choice to their next device. Fire and
    // forget: a failed profile write must not undo the switch they just made.
    if (signedIn) {
      const next = useLangStore.getState().lang;
      void authApi.updateMe({ preferred_lang: next }).catch(() => null);
    }
  };

  return (
    <header className="glass glass--specular glass-navbar">
      <div className="nav-inner">
        <Link to="/" aria-label={brand.name} style={{ textDecoration: 'none' }}>
          <Logo />
        </Link>

        <div style={{ position: 'relative' }} className="nav-only-desktop">
          <Button variant="ghost" size="sm" onClick={toggleCategoryMenu}>
            <LayoutGrid size={16} aria-hidden="true" />
            {t('nav.categories')}
          </Button>
          <CategoryMenu />
        </div>

        {/* A button, not an input: it opens the command palette (plan.md 3.6). */}
        <button
          type="button"
          className="nav-search nav-only-desktop"
          onClick={() => {
            setPaletteOpen(true);
          }}
        >
          <Search size={15} aria-hidden="true" />
          <span>{t('nav.searchPlaceholder')}</span>
          <kbd>Ctrl K</kbd>
        </button>

        <div style={{ marginLeft: 'auto', display: 'flex', alignItems: 'center', gap: '0.375rem' }}>
          <Button
            variant="ghost"
            size="sm"
            icon
            className="nav-only-mobile"
            onClick={() => {
              setPaletteOpen(true);
            }}
            aria-label={t('nav.searchLabel')}
          >
            <Search size={16} aria-hidden="true" />
          </Button>

          {/* The language switch. Two languages, so a toggle rather than a
              menu: a dropdown for a binary choice is one click too many.
              Hidden entirely when the admin has switched EN off, because a
              control with one destination is worse than no control. */}
          {enabledLangs().length > 1 && (
            <Button
              variant="ghost"
              size="sm"
              onClick={switchLanguage}
              aria-label={t('nav.language')}
            >
              {lang.toUpperCase()}
            </Button>
          )}

          <Button
            variant="ghost"
            size="sm"
            icon
            onClick={toggleAccent}
            aria-label={t('nav.accent', { accent })}
          >
            <Palette size={16} aria-hidden="true" />
          </Button>

          <Button variant="ghost" size="sm" icon onClick={toggleTheme} aria-label={themeLabel}>
            <ThemeIcon size={16} aria-hidden="true" />
          </Button>

          <AccountMenu />

          <div style={{ position: 'relative' }}>
            <Button
              variant="primary"
              size="sm"
              icon
              onClick={openCart}
              aria-label={t('nav.cart', { count: cartCount })}
            >
              <ShoppingBag size={16} aria-hidden="true" />
            </Button>
            {cartCount > 0 && (
              <span className="cart-dot tabular" aria-hidden="true">
                {cartCount}
              </span>
            )}
          </div>
        </div>
      </div>
    </header>
  );
}
