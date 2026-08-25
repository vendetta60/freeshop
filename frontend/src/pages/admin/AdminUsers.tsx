import { useQuery } from '@tanstack/react-query';
import { ShieldCheck } from 'lucide-react';
import { useState } from 'react';

import { Badge } from '@/components/ui/Badge';
import { Pagination } from '@/components/ui/Pagination';
import { Skeleton } from '@/components/ui/Skeleton';
import { EmptyState, ErrorState } from '@/components/ui/States';
import { adminApi, adminKeys } from '@/lib/api/admin';
import { useT } from '@/lib/i18n';
import { useDebounced } from '@/lib/hooks/useDebounced';
import { formatDate } from '@/lib/utils/format';

/**
 * Registered users.
 *
 * Read-only, deliberately. There is no self-service admin registration and no
 * way to promote anyone from the panel (plan.md 9.9): the admin account comes
 * from the environment, so the panel cannot be used to widen its own access.
 */
export default function AdminUsers() {
  const { t, lang } = useT();
  const [search, setSearch] = useState('');
  const [page, setPage] = useState(1);
  const q = useDebounced(search, 250);
  const query = { q: q || undefined, page };

  const users = useQuery({
    queryKey: adminKeys.users(query),
    queryFn: ({ signal }) => adminApi.users(query, signal),
  });

  return (
    <section style={{ display: 'grid', gap: '1rem' }}>
      <header className="section-head">
        <h1 style={{ fontSize: '1.25rem' }}>{t('admin.users')}</h1>
      </header>

      <div className="admin__toolbar">
        <input
          className="input"
          type="search"
          value={search}
          placeholder={t('admin.user.searchPlaceholder')}
          aria-label={t('admin.user.searchLabel')}
          onChange={(e) => {
            setSearch(e.target.value);
            setPage(1);
          }}
        />
      </div>

      {users.isError && <ErrorState onRetry={() => void users.refetch()} />}
      {users.isPending && <Skeleton height={220} radius="var(--r-lg)" />}
      {users.data && users.data.items.length === 0 && (
        <EmptyState title={t('admin.user.empty')} description={t('admin.user.emptyText')} />
      )}

      {users.data && users.data.items.length > 0 && (
        <div className="table-wrap">
          <table className="table">
            <thead>
              <tr>
                <th scope="col">{t('admin.user.name')}</th>
                <th scope="col">{t('admin.user.contact')}</th>
                <th scope="col">{t('admin.user.requests')}</th>
                <th scope="col">{t('admin.user.registered')}</th>
              </tr>
            </thead>
            <tbody>
              {users.data.items.map((user) => (
                <tr key={user.id}>
                  <td>
                    <span style={{ display: 'block' }}>
                      {user.full_name ?? t('account.noName')}
                    </span>
                    {user.role === 'admin' && <Badge tone="accent">{t('admin.user.admin')}</Badge>}
                    {!user.is_active && <Badge tone="danger">{t('admin.user.inactive')}</Badge>}
                  </td>
                  <td>
                    <span className="tabular" style={{ display: 'block' }}>
                      {user.phone ?? '—'}
                      {user.phone_verified && (
                        <ShieldCheck
                          size={13}
                          aria-label={t('account.phoneVerified')}
                          style={{ marginInlineStart: '0.25rem', verticalAlign: 'text-bottom' }}
                        />
                      )}
                    </span>
                    <span
                      className="subtle"
                      style={{ fontSize: '0.75rem', wordBreak: 'break-all' }}
                    >
                      {user.email ?? ''}
                    </span>
                  </td>
                  <td className="tabular">{user.request_count}</td>
                  <td className="muted">{formatDate(user.created_at, lang)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

      {users.data && (
        <Pagination
          page={users.data.page}
          pages={users.data.pages}
          total={users.data.total}
          onChange={setPage}
        />
      )}
    </section>
  );
}
