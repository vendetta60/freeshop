import { describe, expect, it } from 'vitest';

import { formatDate, formatDistance, formatNumber, formatPrice } from './format';

const NBSP = ' ';

/**
 * These assertions are exact on purpose.
 *
 * The bug they guard against: Chromium's ICU has no AZN currency pattern, so
 * `Intl.NumberFormat({style:'currency'})` renders "AZN 489.00" in a browser
 * while rendering "489,00 ₼" in Node. A loose test would have passed in CI
 * and shipped the wrong format to every visitor.
 */
describe('formatPrice', () => {
  it('formats AZ with a comma decimal and a trailing manat symbol', () => {
    expect(formatPrice(48900, 'az')).toBe(`489,00${NBSP}₼`);
  });

  it('formats EN with a leading symbol and a dot decimal', () => {
    expect(formatPrice(48900, 'en')).toBe('₼489.00');
  });

  it('groups thousands with a non-breaking space in AZ', () => {
    expect(formatPrice(1250000, 'az')).toBe(`12${NBSP}500,00${NBSP}₼`);
  });

  it('groups thousands with a comma in EN', () => {
    expect(formatPrice(1250000, 'en')).toBe('₼12,500.00');
  });

  it('always shows two decimals, including at the low bound', () => {
    expect(formatPrice(50, 'az')).toBe(`0,50${NBSP}₼`);
    expect(formatPrice(0, 'az')).toBe(`0,00${NBSP}₼`);
  });

  it('falls back to the currency code when no symbol is known', () => {
    expect(formatPrice(10000, 'en', 'GBP')).toBe('GBP100.00');
  });

  it('never emits the ICU fallback pattern', () => {
    // "AZN 489.00" is exactly what the broken path produced.
    expect(formatPrice(48900, 'az')).not.toContain('AZN');
  });
});

describe('formatNumber', () => {
  it('groups by locale convention', () => {
    expect(formatNumber(12500, 'az')).toBe(`12${NBSP}500`);
    expect(formatNumber(12500, 'en')).toBe('12,500');
  });
});

describe('formatDate', () => {
  it('writes Azerbaijani months out in full', () => {
    // Chromium renders `month: 'short'` for az-AZ as the placeholder "M08".
    // This is the assertion that would have caught it - if it had been
    // written against the rendered string rather than against Intl.
    expect(formatDate('2026-08-25T10:00:00Z', 'az')).toBe('25 avqust 2026');
    expect(formatDate('2026-01-01T00:00:00Z', 'az')).toBe('1 yanvar 2026');
  });

  it('never emits the ICU placeholder pattern', () => {
    expect(formatDate('2026-08-25T10:00:00Z', 'az')).not.toMatch(/M\d\d/);
  });

  it('uses Intl for English, whose data is complete', () => {
    expect(formatDate('2026-08-25T10:00:00Z', 'en')).toBe('Aug 25, 2026');
  });

  it('returns an empty string rather than "Invalid Date"', () => {
    expect(formatDate('not-a-date')).toBe('');
  });
});

describe('formatDistance', () => {
  it('uses a comma in AZ and a point in EN', () => {
    expect(formatDistance(3.4, 'az')).toBe('3,4 km');
    expect(formatDistance(3.4, 'en')).toBe('3.4 km');
  });

  it('does not invent a decimal for a whole number', () => {
    // The server sends whole kilometres above 10; showing "204,0 km" would
    // claim a precision it deliberately withheld.
    expect(formatDistance(204, 'az')).toBe('204 km');
  });
});
