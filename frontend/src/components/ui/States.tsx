import { AlertTriangle, Inbox } from 'lucide-react';
import type { ReactNode } from 'react';

import { Button } from '@/components/ui/Button';
import { useT } from '@/lib/i18n';

/**
 * Empty and error states (plan.md 13, phase 12).
 *
 * They live together because they are the same component with different
 * intent, and keeping them apart is how a page ends up with a polished empty
 * state and a blank screen for failure - which is exactly the case a visitor
 * is most likely to hit and least able to interpret.
 */

export function EmptyState({
  title,
  description,
  icon,
  action,
}: {
  title: string;
  description?: string;
  icon?: ReactNode;
  action?: ReactNode;
}) {
  return (
    <div className="empty-state">
      <span className="empty-state__icon" aria-hidden="true">
        {icon ?? <Inbox size={22} />}
      </span>
      <p style={{ fontWeight: 500 }}>{title}</p>
      {description && <p className="muted">{description}</p>}
      {action}
    </div>
  );
}

type ErrorStateProps = {
  /** Defaults to a generic "could not load" pair when omitted. */
  title?: string;
  description?: string;
  onRetry: () => void;
};

/**
 * Failure, with a way out.
 *
 * `onRetry` is not optional by accident: an error state that only apologises
 * leaves reloading the whole page as the user's only move.
 */
export function ErrorState({ title, description, onRetry }: ErrorStateProps) {
  const { t } = useT();
  return (
    <div className="empty-state" role="alert">
      <span className="empty-state__icon empty-state__icon--danger" aria-hidden="true">
        <AlertTriangle size={22} />
      </span>
      <p style={{ fontWeight: 500 }}>{title ?? t('state.loadFailed')}</p>
      <p className="muted">{description ?? t('state.loadFailedText')}</p>
      <Button variant="secondary" onClick={onRetry}>
        {t('common.retry')}
      </Button>
    </div>
  );
}
