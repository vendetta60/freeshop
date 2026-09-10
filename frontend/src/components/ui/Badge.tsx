import type { ReactNode } from 'react';

import { cn } from '@/lib/utils/cn';
import { useT } from '@/lib/i18n';

type Tone = 'neutral' | 'success' | 'warning' | 'danger' | 'accent';

export function Badge({
  tone = 'neutral',
  children,
  className,
}: {
  tone?: Tone;
  children: ReactNode;
  className?: string;
}) {
  return <span className={cn('badge', `badge--${tone}`, className)}>{children}</span>;
}

export type StockStatus = 'available' | 'out_of_stock' | 'on_order';

/**
 * Stock indicator.
 *
 * `available` renders NOTHING on purpose (plan.md 3.6.1): only the exception
 * is worth showing. A green "In stock" badge on every card is visual noise
 * and pushes the palette toward the playground look we are avoiding.
 */
export function StockPill({ status }: { status: StockStatus }) {
  const { t } = useT();
  if (status === 'available') return null;
  return <Badge tone="neutral">{t(`stock.${status}`)}</Badge>;
}

export type TransferType = 'giveaway' | 'loan';
export type LoanListingState = 'available' | 'reserved' | 'borrowed';

/**
 * "Müvəqqəti" - this is lent, not given (FreeShop_Prompt 7).
 *
 * Follows the same rule as `StockPill`: a give-away renders NOTHING, because
 * it is the norm on this board and a badge on every card is noise. Only the
 * exception is worth a pixel.
 *
 * When the item is currently out with somebody, the badge says so instead -
 * one slot, the most useful fact in it.
 */
export function LoanBadge({
  transferType,
  state = 'available',
}: {
  transferType: TransferType;
  state?: LoanListingState;
}) {
  const { t } = useT();
  if (transferType !== 'loan') return null;

  if (state === 'borrowed') return <Badge tone="warning">{t('loan.state.borrowed')}</Badge>;
  if (state === 'reserved') return <Badge tone="neutral">{t('loan.state.reserved')}</Badge>;
  return <Badge tone="accent">{t('loan.badge')}</Badge>;
}
