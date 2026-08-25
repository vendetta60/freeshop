/**
 * Shown while a lazy route chunk loads.
 *
 * Deliberately not a spinner: a quiet, correctly-sized placeholder avoids
 * both layout shift and the flicker a spinner causes on a fast connection.
 */
import { useT } from '@/lib/i18n';

export function RouteFallback() {
  const { t } = useT();
  return (
    <div
      aria-busy="true"
      aria-live="polite"
      style={{
        minHeight: '60vh',
        display: 'grid',
        placeItems: 'center',
        color: 'var(--text-subtle)',
        fontSize: '0.875rem',
      }}
    >
      <span className="visually-hidden">{t('common.loading')}</span>
    </div>
  );
}
