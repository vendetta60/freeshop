import { describe, expect, it } from 'vitest';

import az from './locales/az.json';
import { translate } from './index';

/**
 * The translator's contract (plan.md 7.1).
 *
 * EN is a lazily-loaded chunk, so in a bare unit-test process only AZ is
 * present - which is exactly the state these assertions are about: what a
 * caller gets when the dictionary for their language is not there yet.
 */
describe('translate', () => {
  it('returns the Azerbaijani string', () => {
    expect(translate('az', 'common.save')).toBe('Yadda saxla');
  });

  it('falls back to Azerbaijani rather than rendering nothing', () => {
    // The EN dictionary is not loaded here. A blank label would be worse than
    // an untranslated one.
    expect(translate('en', 'common.save')).toBe(az['common.save']);
  });

  it('returns the key itself when nothing matches', () => {
    // An obvious bug report on screen beats a mysterious blank.
    expect(translate('az', 'no.such.key')).toBe('no.such.key');
  });

  it('interpolates named placeholders', () => {
    expect(translate('az', 'nav.cart', { count: 3 })).toContain('3');
    expect(translate('az', 'common.pagePosition', { page: 2, pages: 5, total: 96 })).toBe(
      '2 / 5 · 96 nəticə',
    );
  });

  it('leaves an unknown placeholder in place instead of printing "undefined"', () => {
    expect(translate('az', 'nav.accent', {})).toContain('{accent}');
  });

  it('picks the ICU plural form by count', () => {
    expect(translate('az', 'catalogue.count', { count: 1 })).toBe('1 məhsul');
    expect(translate('az', 'catalogue.count', { count: 12 })).toBe('12 məhsul');
  });

  it('every dictionary value is a non-empty string', () => {
    // The CI parity script enforces this across both files; this catches it
    // in the unit run too, where the failure is quicker to read.
    for (const [key, value] of Object.entries(az)) {
      expect(typeof value, key).toBe('string');
      expect(value.trim().length, key).toBeGreaterThan(0);
    }
  });
});
