import { useEffect } from 'react';
import { Link, Outlet, useLocation } from 'react-router';

import { brand } from '@/brand/brand.config';
import { AuthSheet } from '@/components/auth/AuthSheet';
import { CartDrawer } from '@/components/cart/CartDrawer';
import { Navbar } from '@/components/layout/Navbar';
import { TabBar } from '@/components/layout/TabBar';
import { SearchPalette } from '@/components/search/SearchPalette';
import { ToastHost } from '@/components/ui/Toast';
import { useGlassTier } from '@/lib/hooks/useGlassTier';
import { useT } from '@/lib/i18n';
import { siteText } from '@/lib/site/config';

export function RootLayout() {
  const { t, lang } = useT();
  useGlassTier();
  const { pathname } = useLocation();

  // Restore scroll position on navigation. Without this, moving from a
  // scrolled catalogue into a product page opens it half-way down.
  useEffect(() => {
    window.scrollTo(0, 0);
  }, [pathname]);

  return (
    <>
      <a className="skip-link" href="#main">
        {t('nav.skipToContent')}
      </a>

      <Navbar />

      <main id="main" className="page">
        <Outlet />
      </main>

      <footer className="site-footer">
        <div>
          <p style={{ fontWeight: 500, color: 'var(--text)' }}>{brand.legalName || brand.name}</p>
          <p className="muted" style={{ fontSize: '0.875rem' }}>
            {siteText('footer_note', lang, lang === 'en' ? brand.tagline.en : brand.tagline.az)}
          </p>
        </div>
        <nav aria-label={t('nav.footer')} className="footer-links">
          <Link to="/products">{t('nav.catalogue')}</Link>
          <Link to="/contact">{t('nav.contact')}</Link>
          <Link to="/cart">{t('nav.cartShort')}</Link>
        </nav>
      </footer>

      <TabBar />
      <CartDrawer />
      <SearchPalette />
      <AuthSheet />
      <ToastHost />
    </>
  );
}
