import {
  BarChart3,
  ClipboardCheck,
  FolderTree,
  HandHeart,
  Inbox,
  LifeBuoy,
  Package,
  Settings,
  Users,
} from 'lucide-react';
import { NavLink, Outlet } from 'react-router';

import { EmptyState } from '@/components/ui/States';
import { useDocumentTitle } from '@/lib/hooks/useDocumentTitle';
import { useT } from '@/lib/i18n';
import { useAuthStore } from '@/stores/authStore';
import { useUiStore } from '@/stores/uiStore';

const LINKS = [
  { to: '/admin', end: true, labelKey: 'admin.overview', icon: BarChart3 },
  { to: '/admin/queue', end: false, labelKey: 'admin.queue', icon: ClipboardCheck },
  { to: '/admin/needs', end: false, labelKey: 'admin.needs.nav', icon: HandHeart },
  { to: '/admin/aid', end: false, labelKey: 'admin.aid.nav', icon: LifeBuoy },
  { to: '/admin/products', end: false, labelKey: 'admin.products', icon: Package },
  { to: '/admin/categories', end: false, labelKey: 'admin.categories', icon: FolderTree },
  { to: '/admin/requests', end: false, labelKey: 'admin.requests', icon: Inbox },
  { to: '/admin/users', end: false, labelKey: 'admin.users', icon: Users },
  { to: '/admin/settings', end: false, labelKey: 'admin.settings', icon: Settings },
] as const;

/**
 * Admin shell and route guard.
 *
 * The guard here is UX only. Every `/admin/*` endpoint re-checks the role
 * server-side on each request (plan.md 10), so a user who edits their way
 * past this component reaches a 403, not data.
 */
export default function AdminLayout() {
  const { t } = useT();
  const user = useAuthStore((s) => s.user);
  const loading = useAuthStore((s) => s.loading);
  const openAuth = useUiStore((s) => s.openAuth);

  useDocumentTitle(t('account.adminPanel'));

  // The boot-time session refresh has not settled yet. Rendering "no access"
  // here would flash a rejection at an admin who is in fact signed in.
  if (loading) return null;

  if (!user) {
    return (
      <EmptyState
        title={t('auth.title')}
        description={t('admin.signInText')}
        action={
          <button type="button" className="btn btn--primary btn--md" onClick={openAuth}>
            {t('common.signIn')}
          </button>
        }
      />
    );
  }

  if (user.role !== 'admin') {
    return <EmptyState title={t('admin.forbiddenTitle')} description={t('admin.forbiddenText')} />;
  }

  return (
    <div className="admin">
      <nav className="admin__nav" aria-label={t('admin.nav')}>
        {LINKS.map(({ to, end, labelKey, icon: Icon }) => (
          <NavLink key={to} to={to} end={end} className="admin__link">
            <Icon size={15} aria-hidden="true" />
            <span>{t(labelKey)}</span>
          </NavLink>
        ))}
      </nav>

      <div className="admin__body">
        <Outlet />
      </div>
    </div>
  );
}
