export type Lang = 'az' | 'en';

const SYMBOLS: Record<string, string> = {
  AZN: '₼',
  USD: '$',
  EUR: '€',
  TRY: '₺',
};

const NBSP = ' ';

/**
 * Money formatting.
 *
 * Prices are stored as INTEGER minor units (qəpik), never floats (plan.md 8).
 *
 * WHY NOT `Intl.NumberFormat({ style: 'currency' })`:
 * Chromium's bundled ICU has no AZN currency pattern for az-AZ. It reports
 * the locale as supported and then renders `AZN 489.00` instead of
 * `489,00 ₼`. Node ships fuller ICU data and renders it correctly - so a
 * unit test run in Node passes while every real visitor sees the wrong
 * format. Verified in Chromium 2026-08-21; plan.md 7.1 predicted this risk.
 *
 * So: format the NUMBER with a locale whose grouping/decimal data is stable
 * everywhere, then apply Azerbaijani conventions ourselves. Deterministic
 * across every runtime, which is the property that actually matters here.
 *
 *   formatPrice(48900, 'az')   ->  "489,00 ₼"
 *   formatPrice(1250000, 'az') ->  "12 500,00 ₼"   (NBSP group separator)
 *   formatPrice(48900, 'en')   ->  "₼489.00"
 */
function formatAmount(value: number, lang: Lang): string {
  const base = new Intl.NumberFormat('en-US', {
    minimumFractionDigits: 2,
    maximumFractionDigits: 2,
    useGrouping: true,
  }).format(value);

  if (lang === 'en') return base;

  // en-US "12,500.50" -> az "12 500,50". NBSP keeps the number unbreakable.
  return base.replaceAll(',', NBSP).replace('.', ',');
}

export function formatPrice(minor: number, lang: Lang = 'az', currency = 'AZN'): string {
  const symbol = SYMBOLS[currency] ?? currency;
  const amount = formatAmount(minor / 100, lang);
  // AZ writes the symbol after the amount; EN before it.
  return lang === 'az' ? `${amount}${NBSP}${symbol}` : `${symbol}${amount}`;
}

export function formatNumber(value: number, lang: Lang = 'az'): string {
  const base = new Intl.NumberFormat('en-US').format(value);
  return lang === 'az' ? base.replaceAll(',', NBSP) : base;
}

// Azerbaijani month names, written out.
//
// SAME CLASS OF BUG AS THE CURRENCY ONE ABOVE, found the same way - by
// reading a rendered page. Chromium's bundled ICU accepts `az-AZ` and then
// renders `month: 'short'` as the placeholder `M08`, so every date in the
// admin panel read "2026 M08 25". Node's fuller ICU renders "25 avq 2026",
// so a unit test run in Node passes while every visitor sees the placeholder.
//
// Months are a closed set of twelve words. Writing them down is cheaper than
// depending on runtime data that demonstrably is not there.
const AZ_MONTHS = [
  'yanvar',
  'fevral',
  'mart',
  'aprel',
  'may',
  'iyun',
  'iyul',
  'avqust',
  'sentyabr',
  'oktyabr',
  'noyabr',
  'dekabr',
];

/**
 * "25 avqust 2026" in AZ, "Aug 25, 2026" in EN.
 *
 * EN goes through Intl, whose en-US data is complete everywhere.
 */
export function formatDate(iso: string, lang: Lang = 'az'): string {
  const date = new Date(iso);
  if (Number.isNaN(date.getTime())) return '';

  if (lang === 'en') {
    return new Intl.DateTimeFormat('en-US', {
      day: 'numeric',
      month: 'short',
      year: 'numeric',
    }).format(date);
  }

  return `${date.getDate()} ${AZ_MONTHS[date.getMonth()]} ${date.getFullYear()}`;
}

/**
 * "3,4 km" in AZ, "3.4 km" in EN.
 *
 * The server has already rounded (one decimal below 10 km, whole kilometres
 * above) - deliberately, so a distance cannot be used to triangulate the
 * thing it measures. This only puts the local decimal separator on it and
 * never re-rounds, because rounding twice is how 9,96 becomes 10.
 */
export function formatDistance(km: number, lang: Lang = 'az'): string {
  const text = Number.isInteger(km) ? String(km) : km.toFixed(1);
  return `${lang === 'az' ? text.replace('.', ',') : text} km`;
}
