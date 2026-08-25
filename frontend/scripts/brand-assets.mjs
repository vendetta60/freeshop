/**
 * Generates the full icon set from the brand SVGs (plan.md 3.0, rule 7).
 *
 *   node scripts/brand-assets.mjs
 *
 * Input : src/brand/assets/logo-mark.svg   (square, currentColor)
 * Output: public/favicon.svg
 *         public/favicon-96.png
 *         public/apple-touch-icon.png      (180x180)
 *         public/og-image.png              (1200x630)
 *         public/manifest.webmanifest
 *
 * There is no manual export step to forget, which is the whole point: a
 * rebrand regenerates every derived asset in one command.
 */

import { existsSync } from 'node:fs';
import { mkdir, readFile, writeFile } from 'node:fs/promises';
import { dirname, join } from 'node:path';
import { fileURLToPath } from 'node:url';

import sharp from 'sharp';

const here = dirname(fileURLToPath(import.meta.url));
const root = join(here, '..');
const publicDir = join(root, 'public');
const markPath = join(root, 'src/brand/assets/logo-mark.svg');

// Palette values mirrored from tokens.css. Rasterised assets cannot use CSS
// variables, so these two are the only place a literal colour is allowed.
const INK = '#38393f';
const PAPER = '#fbfbfc';

/** Fallback mark, matching LogoMark in src/brand/Logo.tsx. */
const FALLBACK_MARK = `<svg xmlns="http://www.w3.org/2000/svg" width="32" height="32" viewBox="0 0 32 32" fill="none">
  <rect x="4.5" y="4.5" width="17" height="17" rx="5.5" stroke="${INK}" stroke-width="2" opacity="0.45"/>
  <rect x="10.5" y="10.5" width="17" height="17" rx="5.5" stroke="${INK}" stroke-width="2"/>
</svg>`;

async function loadBrand() {
  const source = await readFile(join(root, 'src/brand/brand.config.ts'), 'utf8');
  // Single source literal, same regex eslint.config.js uses.
  const name = /BRAND_NAME\s*=\s*'([^']+)'/.exec(source)?.[1] ?? '';
  // shortName derives from BRAND_NAME unless explicitly overridden with a literal.
  const override = /shortName:\s*'([^']+)'/.exec(source)?.[1];
  return { name, shortName: override ?? name };
}

async function main() {
  await mkdir(publicDir, { recursive: true });

  let svg;
  if (existsSync(markPath)) {
    svg = await readFile(markPath, 'utf8');
    console.log(`• using ${markPath}`);
  } else {
    svg = FALLBACK_MARK;
    console.log('• src/brand/assets/logo-mark.svg not found - using the placeholder mark');
  }

  // currentColor has no meaning outside a document; bind it for rasterising.
  const raster = Buffer.from(svg.replaceAll('currentColor', INK));

  await writeFile(join(publicDir, 'favicon.svg'), svg, 'utf8');

  await sharp(raster, { density: 384 })
    .resize(96, 96)
    .png()
    .toFile(join(publicDir, 'favicon-96.png'));

  await sharp(raster, { density: 512 })
    .resize(180, 180)
    .flatten({ background: PAPER })
    .png()
    .toFile(join(publicDir, 'apple-touch-icon.png'));

  const markForOg = await sharp(raster, { density: 512 }).resize(280, 280).png().toBuffer();
  await sharp({
    create: { width: 1200, height: 630, channels: 4, background: PAPER },
  })
    .composite([{ input: markForOg, gravity: 'centre' }])
    .png()
    .toFile(join(publicDir, 'og-image.png'));

  const brand = await loadBrand();
  await writeFile(
    join(publicDir, 'manifest.webmanifest'),
    JSON.stringify(
      {
        name: brand.name,
        short_name: brand.shortName,
        start_url: '/',
        display: 'standalone',
        background_color: PAPER,
        theme_color: PAPER,
        icons: [
          { src: '/favicon.svg', sizes: 'any', type: 'image/svg+xml' },
          { src: '/favicon-96.png', sizes: '96x96', type: 'image/png' },
          { src: '/apple-touch-icon.png', sizes: '180x180', type: 'image/png' },
        ],
      },
      null,
      2,
    ),
    'utf8',
  );

  console.log('✓ brand assets written to public/');
}

main().catch((error) => {
  console.error('brand:assets failed:', error);
  process.exit(1);
});
