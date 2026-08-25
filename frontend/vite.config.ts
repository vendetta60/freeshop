import { fileURLToPath, URL } from 'node:url';

import tailwindcss from '@tailwindcss/vite';
import react from '@vitejs/plugin-react';
import { defineConfig, type Plugin } from 'vite';

// Explicit .ts extension: required by Vite 8's native config loader.
import { brand } from './src/brand/brand.config.ts';

/**
 * Fills the %BRAND_*% placeholders in index.html from brand.config.ts.
 *
 * This is what makes the brand layer real: <title>, description, OG/Twitter
 * tags and theme-colour all resolve from one object, so a rename touches no
 * HTML at all (plan.md 3.0).
 */
function brandHtmlPlugin(): Plugin {
  return {
    name: 'freeshop:brand-html',
    transformIndexHtml: {
      order: 'pre',
      handler(html) {
        const replacements: Record<string, string> = {
          '%BRAND_NAME%': brand.name,
          '%BRAND_SHORT_NAME%': brand.shortName,
          '%BRAND_DESCRIPTION%': brand.description.az,
          '%BRAND_TAGLINE%': brand.tagline.az,
          '%BRAND_DOMAIN%': brand.domain,
          '%BRAND_LANG%': 'az',
        };
        return Object.entries(replacements).reduce(
          (acc, [token, value]) => acc.replaceAll(token, value),
          html,
        );
      },
    },
  };
}

export default defineConfig({
  plugins: [react(), tailwindcss(), brandHtmlPlugin()],

  resolve: {
    alias: {
      '@': fileURLToPath(new URL('./src', import.meta.url)),
    },
  },

  server: {
    port: 5173,
    strictPort: true,
    proxy: {
      // Same-origin in dev. This is what lets the httpOnly refresh cookie
      // work locally exactly as it will behind Caddy in Docker (plan.md 12.2).
      '/api': {
        target: 'http://127.0.0.1:8000',
        changeOrigin: false,
        // Forward the caller's address as X-Forwarded-For, the way Caddy does
        // in production. Without it every request reaching the API comes from
        // 127.0.0.1, so when the dev server is shared over a LAN all testers
        // land in ONE rate-limit bucket - and the first person to sign in a
        // few times locks everyone else out (plan.md 9.4).
        xfwd: true,
      },
      '/static': {
        target: 'http://127.0.0.1:8000',
        changeOrigin: false,
        xfwd: true,
      },
    },
  },

  build: {
    target: 'es2022',
    sourcemap: false,
    cssCodeSplit: true,
    reportCompressedSize: true,
    // Enforces the plan.md 11 budget: warn well before 120 kB gzip is at risk.
    chunkSizeWarningLimit: 350,
    rollupOptions: {
      output: {
        // React is stable across deploys; keeping it in its own chunk means a
        // product-page change does not invalidate it in the browser cache.
        // Rollup's object form is no longer accepted by Vite 8's types.
        manualChunks(id) {
          if (/node_modules[\\/](react|react-dom|react-router|scheduler)[\\/]/.test(id)) {
            return 'react';
          }
          return undefined;
        },
      },
    },
  },
});
