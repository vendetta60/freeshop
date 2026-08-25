import { readFileSync } from 'node:fs';

import { describe, expect, it } from 'vitest';

const raw = readFileSync(new URL('./tokens.css', import.meta.url), 'utf8');

/** Comments explain these rules and would otherwise match them. */
const css = raw.replace(/\/\*[\s\S]*?\*\//g, '');

/**
 * Regression guards for the token system (plan.md 3.2).
 *
 * The @layer test below is not hypothetical: an earlier revision wrapped the
 * dark and bronze overrides in `@layer theme` while the base `:root` block
 * was unlayered. Unlayered styles beat layered ones regardless of specificity,
 * so dark mode and the bronze accent were silently no-ops - the CSS looked
 * completely correct and did nothing.
 */
describe('design tokens', () => {
  it('never wraps theme overrides in a cascade layer', () => {
    expect(css).not.toMatch(/@layer/);
  });

  it('defines dark under BOTH an explicit selector and the media query', () => {
    // A colour defined only inside a media query cannot be toggled by the UI;
    // one defined only on the attribute ignores the OS preference.
    expect(css).toMatch(/:root\[data-theme='dark'\]\s*\{/);
    expect(css).toMatch(/:root:not\(\[data-theme='light'\]\)\s*\{/);
  });

  it('changes exactly the six accent tokens for bronze', () => {
    const block = /:root\[data-accent='bronze'\]\s*\{([^}]*)\}/.exec(css)?.[1] ?? '';
    const declared = [...block.matchAll(/(--[\w-]+):/g)].map((m) => m[1]).sort();
    expect(declared).toEqual([
      '--accent',
      '--accent-active',
      '--accent-border',
      '--accent-hover',
      '--accent-subtle',
      '--on-accent',
    ]);
  });

  it('keeps every chrome colour inside the OKLCH chroma ceiling of 0.15', () => {
    // Rule 2 of the design thesis. This is what stops the palette drifting
    // back toward the saturated "playground" look one commit at a time.
    const offenders = [...css.matchAll(/oklch\(\s*[\d.]+\s+([\d.]+)/g)]
      .map((m) => Number(m[1]))
      .filter((chroma) => chroma > 0.15);
    expect(offenders).toEqual([]);
  });

  it('uses no hex or named colours in the palette', () => {
    // Everything must be OKLCH or color-mix so light/dark stay perceptually
    // matched. `white` inside color-mix is the one deliberate exception.
    const withoutMixes = css.replace(/color-mix\([^)]*\)/g, '');
    expect(withoutMixes).not.toMatch(/#[0-9a-fA-F]{3,8}\b/);
  });
});
