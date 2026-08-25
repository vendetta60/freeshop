/**
 * Enforces the performance budget from plan.md 11.
 *
 *   node scripts/check-bundle-budget.mjs
 *
 * A budget nobody measures is a wish. This runs in CI after `npm run build`
 * and fails the job on regression, so the 120 kB ceiling is a fact rather
 * than an intention.
 *
 * "Initial JS" = everything the browser must fetch to render the first route:
 * the entry module plus the chunks Vite statically preloads alongside it.
 * Lazily-imported route chunks are excluded, which is exactly why route-level
 * splitting is mandatory.
 *
 * The initial set is read from the built `index.html` - the entry `<script>`
 * plus every `<link rel="modulepreload">` - rather than inferred from chunk
 * names. An earlier version matched names against /.*Page-/ and therefore
 * counted every lazy route that was not called `SomethingPage` as initial;
 * the admin panel tripped it on the day it landed. The HTML is what the
 * browser actually fetches, so the HTML is what the budget measures.
 */

import { gzipSync } from 'node:zlib';
import { readdirSync, readFileSync, statSync } from 'node:fs';
import { dirname, extname, join } from 'node:path';
import { fileURLToPath } from 'node:url';

const root = join(dirname(fileURLToPath(import.meta.url)), '..');
const distDir = join(root, 'dist');
const assetsDir = join(distDir, 'assets');

const BUDGET = {
  js: 120 * 1024,
  css: 20 * 1024,
};

function gzipBytes(path) {
  return gzipSync(readFileSync(path), { level: 9 }).length;
}

/** Asset filenames the entry HTML pulls in before the app can render. */
function initialAssets() {
  const html = readFileSync(join(distDir, 'index.html'), 'utf8');
  const names = new Set();
  for (const match of html.matchAll(/(?:src|href)="\/assets\/([^"]+)"/g)) {
    names.add(match[1]);
  }
  return names;
}

function kb(bytes) {
  return `${(bytes / 1024).toFixed(1)} kB`;
}

const initial = initialAssets();
let js = 0;
let css = 0;
const rows = [];

for (const name of readdirSync(assetsDir)) {
  const full = join(assetsDir, name);
  if (!statSync(full).isFile()) continue;

  const ext = extname(name);
  if (ext !== '.js' && ext !== '.css') continue;

  const size = gzipBytes(full);
  const isInitial = initial.has(name);

  if (isInitial) {
    if (ext === '.js') js += size;
    else css += size;
  }
  rows.push({ name, size, lazy: !isInitial });
}

console.log('\nBundle budget (gzip)\n');
for (const row of rows.sort((a, b) => b.size - a.size)) {
  console.log(`  ${row.lazy ? 'lazy   ' : 'initial'}  ${kb(row.size).padStart(9)}  ${row.name}`);
}

const failures = [];
if (js > BUDGET.js) failures.push(`initial JS ${kb(js)} exceeds ${kb(BUDGET.js)}`);
if (css > BUDGET.css) failures.push(`CSS ${kb(css)} exceeds ${kb(BUDGET.css)}`);

console.log(
  `\n  initial JS : ${kb(js).padStart(9)} / ${kb(BUDGET.js)}` +
    `\n  CSS        : ${kb(css).padStart(9)} / ${kb(BUDGET.css)}\n`,
);

if (failures.length) {
  console.error('BUDGET EXCEEDED:');
  for (const failure of failures) console.error(`  - ${failure}`);
  console.error('\nSee plan.md 11 before raising the limit.\n');
  process.exit(1);
}

console.log('Within budget.\n');
