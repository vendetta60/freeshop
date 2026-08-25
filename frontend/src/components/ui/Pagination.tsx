import { ChevronLeft, ChevronRight } from 'lucide-react';

import { Button } from '@/components/ui/Button';
import { useT } from '@/lib/i18n';

/**
 * Previous / next with a position readout.
 *
 * Deliberately not a numbered pager: admin tables are scanned in order, the
 * page number is never a destination anyone remembers, and the numbers are
 * the part that has to be re-thought at every breakpoint.
 */
export function Pagination({
  page,
  pages,
  total,
  onChange,
}: {
  page: number;
  pages: number;
  total: number;
  onChange: (page: number) => void;
}) {
  const { t } = useT();

  if (pages <= 1) return null;

  return (
    <nav className="pager" aria-label={t('common.pages')}>
      <Button
        variant="secondary"
        size="sm"
        disabled={page <= 1}
        onClick={() => onChange(page - 1)}
        aria-label={t('common.previousPage')}
      >
        <ChevronLeft size={15} aria-hidden="true" />
        {t('common.previous')}
      </Button>
      <span className="muted tabular" style={{ fontSize: '0.8125rem' }}>
        {t('common.pagePosition', { page, pages, total })}
      </span>
      <Button
        variant="secondary"
        size="sm"
        disabled={page >= pages}
        onClick={() => onChange(page + 1)}
        aria-label={t('common.nextPage')}
      >
        {t('common.next')}
        <ChevronRight size={15} aria-hidden="true" />
      </Button>
    </nav>
  );
}
