/**
 * Key parity between az.json and en.json (plan.md 7.1).
 *
 *   node scripts/check-i18n-keys.mjs
 *
 * A key present in one file and not the other is invisible until someone
 * switches language and finds a raw key on screen. This makes it a build
 * failure instead - which is the only reason a two-file translation setup
 * stays honest.
 *
 * Empty values fail too: an empty string renders as a blank label, which is
 * worse than the untranslated fallback it replaced.
 */

import { readFileSync } from 'node:fs';
import { dirname, join } from 'node:path';
import { fileURLToPath } from 'node:url';

const root = join(dirname(fileURLToPath(import.meta.url)), '..');
const dir = join(root, 'src', 'lib', 'i18n', 'locales');

const load = (lang) => JSON.parse(readFileSync(join(dir, `${lang}.json`), 'utf8'));

const az = load('az');
const en = load('en');

const failures = [];

for (const key of Object.keys(az)) {
  if (!(key in en)) failures.push(`missing in en.json: ${key}`);
}
for (const key of Object.keys(en)) {
  if (!(key in az)) failures.push(`missing in az.json: ${key}`);
}
for (const [lang, dict] of [
  ['az', az],
  ['en', en],
]) {
  for (const [key, value] of Object.entries(dict)) {
    if (typeof value !== 'string' || value.trim() === '') {
      failures.push(`empty value in ${lang}.json: ${key}`);
    }
  }
}

// Interpolation placeholders must match, or a translated string silently
// drops the number it was supposed to carry.
for (const key of Object.keys(az)) {
  if (!(key in en)) continue;
  const holders = (text) =>
    [...text.matchAll(/\{(\w+)\}/g)]
      .map((m) => m[1])
      .sort()
      .join(',');
  if (holders(az[key]) !== holders(en[key])) {
    failures.push(
      `placeholder mismatch: ${key} (az: ${holders(az[key])} / en: ${holders(en[key])})`,
    );
  }
}

if (failures.length) {
  console.error(`\ni18n key check FAILED (${failures.length}):\n`);
  for (const failure of failures) console.error(`  - ${failure}`);
  console.error('');
  process.exit(1);
}

console.log(`i18n keys in sync: ${Object.keys(az).length} keys x 2 languages.`);
