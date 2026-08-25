/**
 * Downloads every remote demo image into public/demo/ and rewrites
 * src/lib/demoData.ts to point at the local copies.
 *
 *   node scripts/demo-fetch.mjs           # localise
 *   node scripts/demo-fetch.mjs --check   # report only, change nothing
 *
 * WHY THIS EXISTS: the demo data hotlinks Unsplash so the catalogue looks
 * real during development. Production is a local Docker stack for a defence,
 * which may have no network - and a grid of broken images on stage is not a
 * recoverable situation. Run this before any demo you cannot guarantee
 * connectivity for, then tighten img-src in the Caddyfile back to 'self'.
 *
 * Re-running is safe: already-downloaded files are skipped.
 */

import { existsSync } from 'node:fs';
import { mkdir, readFile, writeFile } from 'node:fs/promises';
import { dirname, join } from 'node:path';
import { fileURLToPath } from 'node:url';

const here = dirname(fileURLToPath(import.meta.url));
const root = join(here, '..');
const outDir = join(root, 'public', 'demo');
const dataFile = join(root, 'src', 'lib', 'demoData.ts');

const checkOnly = process.argv.includes('--check');

async function main() {
  const source = await readFile(dataFile, 'utf8');

  // photo('photo-1550581190-9c1c48d21d6c', 1200, 800)
  const calls = [...source.matchAll(/photo\('([^']+)',\s*(\d+),\s*(\d+)\)/g)];

  if (calls.length === 0) {
    console.log('No remote images found - demoData.ts is already local.');
    return;
  }

  console.log(`${calls.length} remote images referenced.`);
  if (checkOnly) {
    console.log('--check: nothing written.');
    return;
  }

  await mkdir(outDir, { recursive: true });

  const rewrites = new Map();
  for (const [full, id, w, h] of calls) {
    const file = `${id}-${w}x${h}.jpg`;
    const target = join(outDir, file);

    if (existsSync(target)) {
      console.log(`  cached  ${file}`);
    } else {
      const url = `https://images.unsplash.com/${id}?w=${w}&h=${h}&q=75&auto=format&fit=crop`;
      const response = await fetch(url);
      if (!response.ok) {
        console.error(`  FAILED  ${file} (HTTP ${response.status})`);
        continue;
      }
      await writeFile(target, Buffer.from(await response.arrayBuffer()));
      console.log(`  saved   ${file}`);
    }
    rewrites.set(full, `'/demo/${file}'`);
  }

  let updated = source;
  for (const [call, literal] of rewrites) {
    updated = updated.replaceAll(call, literal);
  }

  await writeFile(dataFile, updated, 'utf8');
  console.log(
    `\n✓ ${rewrites.size} images localised. demoData.ts now uses /demo/ paths.\n` +
      '  Remember to drop https://images.unsplash.com from img-src in the Caddyfile.',
  );
}

main().catch((error) => {
  console.error('demo:fetch failed:', error);
  process.exit(1);
});
