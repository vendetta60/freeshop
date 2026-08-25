import { cn } from '@/lib/utils/cn';

export function Skeleton({
  width,
  height,
  radius,
  className,
}: {
  width?: string | number;
  height?: string | number;
  radius?: string;
  className?: string;
}) {
  return (
    <span
      aria-hidden="true"
      className={cn('skeleton', className)}
      style={{ display: 'block', width, height, borderRadius: radius }}
    />
  );
}

/** Card-shaped placeholder matching ProductCard's geometry, so swapping one
 *  for the other causes zero layout shift. */
export function ProductCardSkeleton() {
  return (
    <div className="card" style={{ overflow: 'hidden' }}>
      <Skeleton height={0} className="" width="100%" />
      <div style={{ aspectRatio: '4 / 5' }}>
        <Skeleton width="100%" height="100%" radius="0" />
      </div>
      <div style={{ padding: '0.875rem 1rem 1rem', display: 'grid', gap: '0.5rem' }}>
        <Skeleton width="85%" height={14} />
        <Skeleton width="55%" height={14} />
        <Skeleton width="40%" height={18} />
      </div>
    </div>
  );
}
