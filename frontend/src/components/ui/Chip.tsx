import type { ReactNode } from 'react';

import { cn } from '@/lib/utils/cn';

/**
 * Filter / category chip.
 *
 * Neutral by default, accent only when active. Categories never carry their
 * own colour (plan.md 3.3) - that rule is what keeps a catalogue of mixed
 * product photography from turning into a colour riot.
 */
export function Chip({
  active = false,
  onClick,
  children,
  className,
}: {
  active?: boolean;
  onClick?: () => void;
  children: ReactNode;
  className?: string;
}) {
  return (
    <button type="button" className={cn('chip', className)} aria-pressed={active} onClick={onClick}>
      {children}
    </button>
  );
}
