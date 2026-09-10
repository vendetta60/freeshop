import { useQuery } from '@tanstack/react-query';

import { SelectField } from '@/components/ui/Field';
import { communityKeys, locationApi } from '@/lib/api/community';
import { useT } from '@/lib/i18n';

/**
 * Choose a city, and a district where the city has them.
 *
 * TWO SELECTS, NOT A MAP AND NOT A GEOLOCATION PROMPT. That is the privacy
 * decision made visible: the most precise thing anybody can tell this site is
 * the name of their district, and the server turns that into the district's
 * CENTRE (backend app/services/geo.py). There is no control here capable of
 * expressing a house, so no house is ever stored.
 *
 * The options come from the server (`/meta/places`) rather than a bundled
 * list, so the gazetteer has exactly one home and the two cannot drift.
 */
export function LocationPicker({
  city,
  district,
  onChange,
  required = false,
  hint,
  disabled = false,
}: {
  city: string;
  district: string;
  onChange: (next: { city: string; district: string }) => void;
  required?: boolean;
  hint?: string;
  disabled?: boolean;
}) {
  const { t } = useT();

  const places = useQuery({
    queryKey: communityKeys.places(),
    queryFn: ({ signal }) => locationApi.places(signal),
    // The gazetteer changes on deploy, not on request.
    staleTime: 24 * 60 * 60_000,
  });

  const districts = places.data?.districts[city] ?? [];

  return (
    <div className="location-picker">
      <SelectField
        label={t('location.city')}
        required={required}
        value={city}
        disabled={disabled || places.isPending}
        hint={hint}
        onChange={(e) => {
          // Changing the city clears the district: "Xətai" is a district of
          // Bakı and nowhere else, and carrying it across would submit a
          // place that does not exist.
          onChange({ city: e.target.value, district: '' });
        }}
      >
        <option value="">{t('location.choose')}</option>
        {(places.data?.cities ?? []).map((option) => (
          <option key={option.name} value={option.name}>
            {option.name}
          </option>
        ))}
      </SelectField>

      {/* Rendered only where there is a choice to make. A select with one
          disabled placeholder is a control that does nothing. */}
      {districts.length > 0 && (
        <SelectField
          label={t('location.district')}
          value={district}
          disabled={disabled}
          onChange={(e) => onChange({ city, district: e.target.value })}
        >
          <option value="">{t('location.anyDistrict')}</option>
          {districts.map((name) => (
            <option key={name} value={name}>
              {name}
            </option>
          ))}
        </SelectField>
      )}
    </div>
  );
}
