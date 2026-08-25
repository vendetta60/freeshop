import {
  Gift,
  LayoutDashboard,
  LogIn,
  LogOut,
  Package,
  ShieldCheck,
  Tag,
  User,
  UserPlus,
} from 'lucide-react';
import { useEffect, useRef } from 'react';
import { useNavigate } from 'react-router';

import { Button } from '@/components/ui/Button';
import { useT } from '@/lib/i18n';
import { initialsOf, useAuthStore } from '@/stores/authStore';
import { useUiStore } from '@/stores/uiStore';

/**
 * Account control in the navigation.
 *
 * Signed out -> sign in / sign up.
 * Signed in  -> who you are, your requests, and sign out.
 *
 * A person icon that does nothing is worse than no icon at all, so this is
 * wired to the real auth store rather than left as decoration.
 */
export function AccountMenu() {
  const { t } = useT();
  const user = useAuthStore((s) => s.user);
  const signOut = useAuthStore((s) => s.signOut);
  const open = useUiStore((s) => s.accountMenuOpen);
  const toggle = useUiStore((s) => s.toggleAccountMenu);
  const close = useUiStore((s) => s.closeAccountMenu);
  const openAuth = useUiStore((s) => s.openAuth);
  const navigate = useNavigate();
  const ref = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (!open) return;
    const onKey = (e: KeyboardEvent) => {
      if (e.key === 'Escape') close();
    };
    const onClick = (e: MouseEvent) => {
      if (!ref.current?.contains(e.target as Node)) close();
    };
    document.addEventListener('keydown', onKey);
    const id = setTimeout(() => document.addEventListener('click', onClick), 0);
    return () => {
      document.removeEventListener('keydown', onKey);
      document.removeEventListener('click', onClick);
      clearTimeout(id);
    };
  }, [open, close]);

  return (
    <div ref={ref} style={{ position: 'relative' }}>
      <Button
        variant="ghost"
        size="sm"
        icon
        onClick={toggle}
        aria-expanded={open}
        aria-haspopup="menu"
        aria-label={
          user
            ? t('nav.accountOf', { name: user.full_name ?? t('account.user') })
            : t('nav.account')
        }
      >
        {user ? (
          <span className="avatar" aria-hidden="true">
            {initialsOf(user)}
          </span>
        ) : (
          <User size={16} aria-hidden="true" />
        )}
      </Button>

      {open && (
        <div className="glass glass--specular glass--deep account-menu" role="menu">
          {user ? (
            <>
              <div className="account-menu__id">
                <span className="avatar avatar--lg" aria-hidden="true">
                  {initialsOf(user)}
                </span>
                <span style={{ minWidth: 0 }}>
                  <span style={{ display: 'block', fontWeight: 500 }}>
                    {user.full_name ?? t('account.user')}
                  </span>
                  <span className="subtle" style={{ fontSize: '0.75rem', wordBreak: 'break-all' }}>
                    {user.email ?? user.phone}
                  </span>
                </span>
              </div>

              {user.phone_verified && (
                <p className="account-menu__verified">
                  <ShieldCheck size={13} aria-hidden="true" />
                  {t('account.phoneVerified')}
                </p>
              )}

              <hr className="account-menu__rule" />

              <button
                type="button"
                role="menuitem"
                className="account-menu__item"
                onClick={() => {
                  close();
                  void navigate('/profile');
                }}
              >
                <User size={15} aria-hidden="true" />
                {t('account.profile')}
              </button>

              <button
                type="button"
                role="menuitem"
                className="account-menu__item"
                onClick={() => {
                  close();
                  void navigate('/profile/orders');
                }}
              >
                <Package size={15} aria-hidden="true" />
                {t('account.myRequests')}
              </button>

              <button
                type="button"
                role="menuitem"
                className="account-menu__item"
                onClick={() => {
                  close();
                  void navigate('/profile/listings');
                }}
              >
                <Tag size={15} aria-hidden="true" />
                {t('listings.nav')}
              </button>

              <button
                type="button"
                role="menuitem"
                className="account-menu__item"
                onClick={() => {
                  close();
                  void navigate('/offer');
                }}
              >
                <Gift size={15} aria-hidden="true" />
                {t('offer.nav')}
              </button>

              {/* Shown only to admins. The panel itself re-checks the role on
                  every request, so hiding this is convenience, not a control
                  (plan.md 10). */}
              {user.role === 'admin' && (
                <button
                  type="button"
                  role="menuitem"
                  className="account-menu__item"
                  onClick={() => {
                    close();
                    void navigate('/admin');
                  }}
                >
                  <LayoutDashboard size={15} aria-hidden="true" />
                  {t('account.adminPanel')}
                </button>
              )}

              <button
                type="button"
                role="menuitem"
                className="account-menu__item account-menu__item--danger"
                onClick={() => {
                  void signOut();
                  close();
                }}
              >
                <LogOut size={15} aria-hidden="true" />
                {t('auth.signOut')}
              </button>
            </>
          ) : (
            <>
              <p className="account-menu__lead">{t('auth.menuLead')}</p>
              <button
                type="button"
                role="menuitem"
                className="account-menu__item"
                onClick={() => {
                  close();
                  openAuth();
                }}
              >
                <LogIn size={15} aria-hidden="true" />
                {t('common.signIn')}
              </button>
              <button
                type="button"
                role="menuitem"
                className="account-menu__item"
                onClick={() => {
                  close();
                  openAuth();
                }}
              >
                <UserPlus size={15} aria-hidden="true" />
                {t('auth.signUp')}
              </button>
            </>
          )}
        </div>
      )}
    </div>
  );
}
