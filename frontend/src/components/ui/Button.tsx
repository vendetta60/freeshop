import type { ButtonHTMLAttributes, ReactNode } from 'react';

import { cn } from '@/lib/utils/cn';

type Variant = 'primary' | 'secondary' | 'ghost' | 'danger';
type Size = 'sm' | 'md' | 'lg';

type ButtonProps = ButtonHTMLAttributes<HTMLButtonElement> & {
  variant?: Variant;
  size?: Size;
  /** Square icon-only button. Requires `aria-label`. */
  icon?: boolean;
  children?: ReactNode;
};

export function Button({
  variant = 'secondary',
  size = 'md',
  icon = false,
  className,
  type = 'button',
  ...rest
}: ButtonProps) {
  return (
    <button
      type={type}
      className={cn('btn', `btn--${variant}`, `btn--${size}`, icon && 'btn--icon', className)}
      {...rest}
    />
  );
}
