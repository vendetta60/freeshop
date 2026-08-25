import { describe, expect, it, vi } from 'vitest';

import { randomId } from './id';

describe('randomId', () => {
  it('produces a v4 UUID', () => {
    expect(randomId()).toMatch(
      /^[0-9a-f]{8}-[0-9a-f]{4}-4[0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$/,
    );
  });

  it('still works where crypto.randomUUID does not exist', () => {
    // Exactly the insecure-context case that broke the cart page when the dev
    // server was opened over a LAN address instead of localhost.
    const spy = vi.spyOn(crypto, 'randomUUID').mockImplementation(() => {
      throw new TypeError('crypto.randomUUID is not a function');
    });
    // @ts-expect-error - emulating a runtime where the method is absent.
    crypto.randomUUID = undefined;

    expect(randomId()).toMatch(
      /^[0-9a-f]{8}-[0-9a-f]{4}-4[0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$/,
    );

    spy.mockRestore();
  });

  it('does not repeat itself', () => {
    const ids = new Set(Array.from({ length: 500 }, () => randomId()));
    expect(ids.size).toBe(500);
  });
});
