import { Link } from 'react-router';
import { useDocumentTitle } from '@/lib/hooks/useDocumentTitle';
import { useT } from '@/lib/i18n';

export default function NotFoundPage() {
  const { t } = useT();
  useDocumentTitle(t('notFound.title'));
  return (
    <div style={{ display: 'grid', gap: '1rem', placeItems: 'start', minHeight: '40vh' }}>
      <p className="tabular" style={{ color: 'var(--text-subtle)', fontSize: '0.875rem' }}>
        404
      </p>
      <h1 style={{ fontSize: '1.5rem' }}>{t('notFound.title')}</h1>
      <p style={{ color: 'var(--text-muted)' }}>{t('notFound.text')}</p>
      <Link to="/">{t('notFound.home')}</Link>
    </div>
  );
}
