import { MapPin } from 'lucide-react';

import type { Location } from '@/lib/api/community';
import { useT } from '@/lib/i18n';
import { cn } from '@/lib/utils/cn';
import { formatDistance } from '@/lib/utils/format';

/**
 * "📍 Lənkəran · 3,4 km uzaqlıqda" (FreeShop_Prompt 1).
 *
 * ONE component for listings, needs, loans and aid cases. Every located
 * thing on this site renders its place the same way, which is what stops
 * four screens inventing four spellings of the same fact.
 *
 * It renders NOTHING when there is no place to show. An empty pin with no
 * text is worse than silence - it reads as a missing value rather than an
 * absent one, and plenty of rows legitimately have no location (someone who
 * has not set one, or a village the gazetteer does not know).
 */
export function PlaceLine({
  location,
  className,
  showDistance = true,
}: {
  location: Location | null | undefined;
  className?: string;
  showDistance?: boolean;
}) {
  const { t, lang } = useT();
  if (!location?.label) return null;

  const distance = showDistance && location.distance_km !== null ? location.distance_km : null;

  return (
    <span className={cn('place-line', className)}>
      <MapPin size={13} aria-hidden="true" />
      <span>{location.label}</span>
      {distance !== null && (
        <span className="place-line__distance">
          {t('location.away', { distance: formatDistance(distance, lang) })}
        </span>
      )}
    </span>
  );
}

/**
 * The distance on its own, for a card that already names the place.
 *
 * Separate from `PlaceLine` rather than a variant of it: a product card
 * shows the town under the title and the distance next to the price, and
 * threading a `variant` prop through would be more code than a five-line
 * second component.
 */
export function DistanceBadge({ km }: { km: number | null | undefined }) {
  const { t, lang } = useT();
  if (km === null || km === undefined) return null;
  return (
    <span className="distance-badge">
      {t('location.away', { distance: formatDistance(km, lang) })}
    </span>
  );
}
