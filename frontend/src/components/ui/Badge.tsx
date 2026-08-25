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
