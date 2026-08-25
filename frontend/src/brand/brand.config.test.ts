import { readFileSync } from 'node:fs';

import { describe, expect, it } from 'vitest';

import { brand } from './brand.config';

/**
 * Invariants the brand layer relies on (plan.md 3.0). These are cheap, but
 * each one guards a rule that is easy to break silently during a rebrand.
 */
describe('brand config', () => {
  it('has a non-empty name', () => {
    expect(brand.name.trim()).not.toBe('');
  });

  it('keeps shortName within the 12-character mobile/PWA limit', () => {
    expect(brand.shortName.length).toBeLessThanOrEqual(12);
  });

  it('ships both languages for every translated field', () => {
    for (const field of [brand.tagline, brand.description]) {
      expect(field.az.trim()).not.toBe('');
      expect(field.en.trim()).not.toBe('');
    }
  });

  it('uses a defined accent and theme', () => {
    expect(['azure', 'bronze']).toContain(brand.accent);
    expect(['system', 'light', 'dark']).toContain(brand.defaultTheme);
  });

  it('exposes the name in a shape the ESLint rule can parse', () => {
    // eslint.config.js reads the name with /BRAND_NAME\s*=\s*'([^']+)'/ so the ban and
    // the source of truth cannot drift. If the quoting style here changes,
    // the rule silently stops protecting anything - so assert the shape.
    const source = readFileSync(new URL('./brand.config.ts', import.meta.url), 'utf8');
    const match = /BRAND_NAME\s*=\s*'([^']+)'/.exec(source);
    expect(match?.[1]).toBe(brand.name);
  });
});
