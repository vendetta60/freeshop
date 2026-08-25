import { useQuery } from '@tanstack/react-query';
import { Link } from 'react-router';

import { Skeleton } from '@/components/ui/Skeleton';
import { ErrorState } from '@/components/ui/States';
import { StatusPill } from '@/components/ui/StatusPill';
import { adminApi, adminKeys } from '@/lib/api/admin';
import { useT } from '@/lib/i18n';
import { formatDate, formatNumber, formatPrice } from '@/lib/utils/format';

/**
 * Counters, a 30-day request series and the latest requests.
 *
 * The chart is inline SVG rather than a charting library: it is one polyline
 * over 30 points, and the smallest chart package costs more gzipped than the
 * entire route (plan.md 11).
 */
function Sparkline({ points }: { points: { date: string; count: number }[] }) {
  const { t, lang } = useT();
  const max = Math.max(1, ...points.map((p) => p.count));
  const step = 100 / Math.max(1, points.length - 1);
  const path = points
    .map((p, i) => `${(i * step).toFixed(2)},${(30 - (p.count / max) * 28).toFixed(2)}`)
    .join(' ');
  const total = points.reduce((sum, p) => sum + p.count, 0);

  return (
    <figure className="card spark">
      <figcaption className="muted" style={{ fontSize: '0.8125rem' }}>
        {t('admin.stats.series', { count: formatNumber(total, lang) })}
      </figcaption>
      <svg
        viewBox="0 0 100 30"
        preserveAspectRatio="none"
        role="img"
        aria-label={t('admin.stats.series', { count: total })}
      >
        {/* Fill under the line, so a flat stretch still reads as a chart
            rather than as a stray rule across the page. */}
        <polygon points={`0,30 ${path} 100,30`} fill="var(--accent-subtle)" />
        <polyline
          points={path}
          fill="none"
          stroke="var(--accent)"
          strokeWidth="1.5"
          vectorEffect="non-scaling-stroke"
        />
      </svg>
    </figure>
  );
}

function Stat({ label, value, hint }: { label: string; value: string; hint?: string }) {
  return (
    <div className="card stat">
      <p className="stat__label">{label}</p>
      <p className="stat__value tabular">{value}</p>
      {hint && (
        <p className="muted" style={{ fontSize: '0.75rem' }}>
          {hint}
        </p>
      )}
    </div>
  );
}

export default function AdminDashboard() {
  const { t, lang } = useT();
  const stats = useQuery({
    queryKey: adminKeys.stats(),
    queryFn: ({ signal }) => adminApi.stats(signal),
  });

  const recent = useQuery({
    queryKey: adminKeys.recent(),
    queryFn: ({ signal }) => adminApi.recentRequests(signal),
  });

  if (stats.isError) return <ErrorState onRetry={() => void stats.refetch()} />;

  return (
    <section style={{ display: 'grid', gap: '1.25rem' }}>
      <header className="section-head">
        <h1 style={{ fontSize: '1.25rem' }}>{t('admin.overview')}</h1>
      </header>

      <div className="stat-grid">
        {stats.isPending
          ? Array.from({ length: 4 }, (_, i) => (
              <Skeleton key={i} height={92} radius="var(--r-lg)" />
            ))
          : [
              {
                label: t('admin.stats.products'),
                value: formatNumber(stats.data.products, lang),
                // What is waiting matters more than what has been removed:
                // one is a queue, the other is history.
                hint: stats.data.products_pending
                  ? t('admin.stats.pending', { count: stats.data.products_pending })
                  : t('admin.stats.deleted', { count: stats.data.products_deleted }),
              },
              {
                label: t('admin.stats.requests'),
                value: formatNumber(stats.data.requests_total, lang),
                hint: t('admin.stats.newRequests', { count: stats.data.requests_new }),
              },
              { label: t('admin.stats.users'), value: formatNumber(stats.data.users, lang) },
              {
                label: t('admin.stats.value'),
                value: formatPrice(stats.data.revenue_requested_minor, lang),
              },
            ].map((item) => <Stat key={item.label} {...item} />)}
      </div>

      {stats.data && <Sparkline points={stats.data.series} />}

      <div className="card" style={{ padding: '1rem' }}>
        <div className="section-head" style={{ marginBottom: '0.75rem' }}>
          <h2 style={{ fontSize: '1rem' }}>{t('admin.stats.recent')}</h2>
          <Link to="/admin/requests" className="subtle" style={{ fontSize: '0.8125rem' }}>
            {t('common.all')}
          </Link>
        </div>

        {recent.isPending && <Skeleton height={80} />}
        {recent.data?.length === 0 && <p className="muted">{t('admin.stats.noRequests')}</p>}

        <ul className="plain-list">
          {(recent.data ?? []).map((item) => (
            <li key={item.id} className="recent-row">
              <span className="tabular" style={{ fontWeight: 500 }}>
                {item.request_no}
              </span>
              <StatusPill status={item.status} />
              <span className="tabular muted">{formatPrice(item.total_minor, lang)}</span>
              <span className="muted" style={{ fontSize: '0.8125rem' }}>
                {formatDate(item.created_at, lang)}
              </span>
            </li>
          ))}
        </ul>
      </div>
    </section>
  );
}
