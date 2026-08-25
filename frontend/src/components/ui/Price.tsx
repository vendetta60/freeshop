import { cn } from '@/lib/utils/cn';
import { useT } from '@/lib/i18n';
import { formatPrice } from '@/lib/utils/format';

/**
 * A price, or the word "free".
 *
 * Zero is the normal case on this site, not an edge one — most things here
 * are being given away — and `0,00 ₼` is a worse way of saying that than
 * "Pulsuz". Rendering it through one component rather than at each call site
 * is what stops half the app saying one and half the other.
 */
export function Price({
  minor,
  currency = 'AZN',
  className,
}: {
  minor: number;
  currency?: string;
  className?: string;
}) {
  const { t, lang } = useT();

  if (minor === 0) {
    return <span className={cn('price-free', className)}>{t('product.free')}</span>;
  }

  return <span className={cn('tabular', className)}>{formatPrice(minor, lang, currency)}</span>;
}
