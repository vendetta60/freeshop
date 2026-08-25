/**
 * Generates the demo product imagery used by the phase-1 UI.
 *
 *   node scripts/demo-images.mjs
 *
 * Why generated rather than downloaded:
 *   * the demo must work offline, in a container, on a projector
 *   * the aspect ratios are chosen deliberately - 3:2 landscape, 1:2 tall,
 *     square, tiny - to prove the `object-fit: contain` decision in
 *     plan.md 3.6.1. Random stock photos would not exercise it.
 *   * a muted, palette-derived set stays inside the Quiet Glass colour rules
 *     instead of fighting them.
 *
 * These are placeholders for layout, not pretend products. Real photography
 * arrives with the phase-3 seed (plan.md 8.1.6).
 */

import { mkdir, writeFile } from 'node:fs/promises';
import { dirname, join } from 'node:path';
import { fileURLToPath } from 'node:url';

import sharp from 'sharp';

const here = dirname(fileURLToPath(import.meta.url));
const outDir = join(here, '..', 'public', 'demo');

// Muted, low-chroma pairs. Nothing here breaks the C <= 0.15 ceiling.
const PALETTES = [
  ['#e8eaef', '#b9c0cf'],
  ['#eae6e1', '#cbbfae'],
  ['#e4eaea', '#aec3c4'],
  ['#eee9ee', '#c6b8ca'],
  ['#e9ece6', '#b8c6ae'],
  ['#efe9e6', '#d3b9ae'],
  ['#e6e9ef', '#aab4cc'],
  ['#edece7', '#c4c0ad'],
];

/** Deliberately awkward geometry - the point is that the grid copes. */
const SPECS = [
  { name: 'p1', w: 3000, h: 2000, shape: 'arc' },
  { name: 'p2', w: 800, h: 1600, shape: 'stack' },
  { name: 'p3', w: 1000, h: 1000, shape: 'circle' },
  { name: 'p4', w: 2400, h: 1600, shape: 'grid' },
  { name: 'p5', w: 900, h: 1350, shape: 'arc' },
  { name: 'p6', w: 400, h: 400, shape: 'circle' },
  { name: 'p7', w: 1800, h: 1200, shape: 'stack' },
  { name: 'p8', w: 1200, h: 1600, shape: 'grid' },
];

function shapeMarkup(shape, w, h, ink) {
  const cx = w / 2;
  const cy = h / 2;
  const r = Math.min(w, h) * 0.3;

  switch (shape) {
    case 'circle':
      return `<circle cx="${cx}" cy="${cy}" r="${r}" fill="${ink}" opacity="0.5"/>
              <circle cx="${cx}" cy="${cy}" r="${r * 0.58}" fill="none" stroke="${ink}" stroke-width="${r * 0.06}" opacity="0.75"/>`;
    case 'arc':
      return `<path d="M ${cx - r * 1.3} ${cy + r * 0.7} A ${r * 1.3} ${r * 1.3} 0 0 1 ${cx + r * 1.3} ${cy + r * 0.7} Z" fill="${ink}" opacity="0.45"/>
              <rect x="${cx - r * 1.3}" y="${cy + r * 0.7}" width="${r * 2.6}" height="${r * 0.16}" rx="${r * 0.08}" fill="${ink}" opacity="0.7"/>`;
    case 'stack':
      return `<rect x="${cx - r}" y="${cy - r * 1.1}" width="${r * 2}" height="${r * 0.62}" rx="${r * 0.18}" fill="${ink}" opacity="0.72"/>
              <rect x="${cx - r * 0.82}" y="${cy - r * 0.28}" width="${r * 1.64}" height="${r * 0.62}" rx="${r * 0.18}" fill="${ink}" opacity="0.52"/>
              <rect x="${cx - r * 0.62}" y="${cy + r * 0.54}" width="${r * 1.24}" height="${r * 0.62}" rx="${r * 0.18}" fill="${ink}" opacity="0.34"/>`;
    default:
      return `<rect x="${cx - r}" y="${cy - r}" width="${r * 0.9}" height="${r * 0.9}" rx="${r * 0.16}" fill="${ink}" opacity="0.7"/>
              <rect x="${cx + r * 0.1}" y="${cy - r}" width="${r * 0.9}" height="${r * 0.9}" rx="${r * 0.16}" fill="${ink}" opacity="0.45"/>
              <rect x="${cx - r}" y="${cy + r * 0.1}" width="${r * 0.9}" height="${r * 0.9}" rx="${r * 0.16}" fill="${ink}" opacity="0.45"/>
              <rect x="${cx + r * 0.1}" y="${cy + r * 0.1}" width="${r * 0.9}" height="${r * 0.9}" rx="${r * 0.16}" fill="${ink}" opacity="0.28"/>`;
  }
}

function svgFor({ w, h, shape }, index) {
  const [bg, ink] = PALETTES[index % PALETTES.length];
  return Buffer.from(`<svg xmlns="http://www.w3.org/2000/svg" width="${w}" height="${h}">
    <defs>
      <linearGradient id="g" x1="0" y1="0" x2="1" y2="1">
        <stop offset="0%" stop-color="${bg}"/>
        <stop offset="100%" stop-color="${ink}" stop-opacity="0.55"/>
      </linearGradient>
    </defs>
    <rect width="${w}" height="${h}" fill="url(#g)"/>
    ${shapeMarkup(shape, w, h, ink)}
  </svg>`);
}

async function main() {
  await mkdir(outDir, { recursive: true });

  const manifest = [];
  for (const [index, spec] of SPECS.entries()) {
    const file = `${spec.name}.webp`;
    await sharp(svgFor(spec, index)).webp({ quality: 82 }).toFile(join(outDir, file));
    manifest.push({ src: `/demo/${file}`, width: spec.w, height: spec.h });
    console.log(`  ${file.padEnd(8)} ${spec.w}x${spec.h}`);
  }

  await writeFile(join(outDir, 'manifest.json'), JSON.stringify(manifest, null, 2), 'utf8');
  console.log(`\n✓ ${SPECS.length} demo images written to public/demo/`);
}

main().catch((error) => {
  console.error('demo-images failed:', error);
  process.exit(1);
});
