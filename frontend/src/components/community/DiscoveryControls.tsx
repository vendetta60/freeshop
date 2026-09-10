import { useQuery } from '@tanstack/react-query';
import { MapPin } from 'lucide-react';
import { Link } from 'react-router';

import { locationApi } from '@/lib/api/community';
import { useT } from '@/lib/i18n';
import { useAuthStore } from '@/stores/authStore';

/**
 * Sort and radius, plus the one honest sentence about why nearby is off.
 *
 * The three sorts named in FreeShop_Prompt 2 - Yaxınlıqdakı, Ən yeni, Ən çox
 * tələb olunan - live here alongside the existing price sorts, because a
 * visitor does not think of them as two kinds of ordering.
 */

export function RadiusSelector({
  value,
  onChange,
}: {
  value: number | null;
  onChange: (next: number | null) => void;
}) {
  const { t } = useT();
  const options = useQuery({
    queryKey: ['radius-options'],
    queryFn: ({ signal }) => locationApi.radiusOptions(signal),
    staleTime: 24 * 60 * 60_000,
  });

  return (
    <label className="sort-selector">
      <span className="sr-only">{t('location.radius')}</span>
      <select
        className="input input--select"
        value={value ?? ''}
        onChange={(e) => onChange(e.target.value === '' ? null : Number(e.target.value))}
      >
        {/* "All" is the ABSENCE of a radius, not a magic large number - see
            the backend's /meta/radius-options for the same reasoning. */}
        <option value="">{t('location.radiusAll')}</option>
        {(options.data?.radius_km ?? []).map((km) => (
          <option key={km} value={km}>
            {t('location.radiusKm', { km })}
          </option>
        ))}
      </select>
    </label>
  );
}

/**
 * "Add your location to see what is nearby."
 *
 * Shown when the server tells us it could not honour a `nearby` request
 * (`applied_sort` came back as something else). Driven by the SERVER's
 * answer rather than by guessing from the user object, so the message can
 * never contradict the list the visitor is looking at.
 */
export function NearbyUnavailableNote({
  appliedSort,
}: {
  appliedSort?: string | null | undefined;
}) {
  const { t } = useT();
  const signedIn = useAuthStore((s) => s.user !== null);

  if (appliedSort !== 'newest') return null;

  return (
    <p className="nearby-note" role="status">
      <MapPin size={14} aria-hidden="true" />
      <span>{t('location.nearbyUnavailable')}</span>
      {signedIn ? (
        <Link to="/profile">{t('location.addYours')}</Link>
      ) : (
        <span>{t('location.signInToAdd')}</span>
      )}
    </p>
  );
}
