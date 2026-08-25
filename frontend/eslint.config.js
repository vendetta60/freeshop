import { readFileSync } from 'node:fs';

import js from '@eslint/js';
import jsxA11y from 'eslint-plugin-jsx-a11y';
import reactHooks from 'eslint-plugin-react-hooks';
import reactRefresh from 'eslint-plugin-react-refresh';
import globals from 'globals';
import tseslint from 'typescript-eslint';

/**
 * The brand name is read out of brand.config.ts at lint time rather than
 * duplicated here, so the ban and the source of truth can never drift apart
 * (plan.md 3.0, rule 1).
 */
function brandName() {
  const source = readFileSync(new URL('./src/brand/brand.config.ts', import.meta.url), 'utf8');
  const match = /BRAND_NAME\s*=\s*'([^']+)'/.exec(source);
  if (!match?.[1]) {
    throw new Error('eslint: could not read `BRAND_NAME` from src/brand/brand.config.ts');
  }
  return match[1];
}

const BRAND = brandName();

export default tseslint.config(
  { ignores: ['dist', 'coverage', 'src/types/api.ts', 'node_modules'] },

  js.configs.recommended,
  ...tseslint.configs.recommendedTypeChecked,
  ...tseslint.configs.stylisticTypeChecked,

  {
    files: ['**/*.{ts,tsx}'],
    languageOptions: {
      ecmaVersion: 2023,
      globals: { ...globals.browser, ...globals.es2023 },
      parserOptions: {
        projectService: true,
        tsconfigRootDir: import.meta.dirname,
      },
    },
    plugins: {
      'react-hooks': reactHooks,
      'react-refresh': reactRefresh,
      'jsx-a11y': jsxA11y,
    },
    rules: {
      ...reactHooks.configs.recommended.rules,
      ...jsxA11y.flatConfigs.recommended.rules,

      'react-refresh/only-export-components': ['warn', { allowConstantExport: true }],

      // Stylistic only. `type` is the dominant React convention for props and
      // unlike `interface` it composes with unions and mapped types.
      '@typescript-eslint/consistent-type-definitions': 'off',

      '@typescript-eslint/consistent-type-imports': [
        'error',
        { prefer: 'type-imports', fixStyle: 'inline-type-imports' },
      ],
      '@typescript-eslint/no-unused-vars': [
        'error',
        { argsIgnorePattern: '^_', varsIgnorePattern: '^_' },
      ],
      '@typescript-eslint/no-floating-promises': 'error',
      '@typescript-eslint/no-misused-promises': 'error',

      // Import hygiene keeps diffs readable and merge conflicts rare.
      'no-restricted-imports': [
        'error',
        {
          patterns: [
            {
              group: ['../../*'],
              message: "Use the '@/' alias instead of deep relative imports.",
            },
          ],
        },
      ],
    },
  },

  /**
   * The brand name may appear ONLY inside src/brand/. Everywhere else it must
   * come from `brand.config.ts`, so renaming the project is a one-file edit.
   */
  {
    files: ['src/**/*.{ts,tsx}'],
    ignores: ['src/brand/**'],
    rules: {
      'no-restricted-syntax': [
        'error',
        {
          selector: `Literal[value=/${BRAND}/i]`,
          message: `Do not hardcode the brand name "${BRAND}". Import { brand } from '@/brand/brand.config' instead (plan.md 3.0).`,
        },
        {
          selector: `TemplateElement[value.raw=/${BRAND}/i]`,
          message: `Do not hardcode the brand name "${BRAND}". Import { brand } from '@/brand/brand.config' instead (plan.md 3.0).`,
        },
      ],
    },
  },

  // Config and build scripts run in Node, not the browser.
  {
    files: ['*.config.{ts,js}', 'scripts/**/*.{mjs,js,ts}'],
    languageOptions: { globals: globals.node },
    rules: { 'no-console': 'off' },
  },

  // The screenshot script is Node, but its page.evaluate() callbacks are
  // serialised and executed inside the browser, so both global sets are real.
  {
    files: ['scripts/screenshots.mjs', 'scripts/smoke.mjs'],
    languageOptions: { globals: { ...globals.node, ...globals.browser } },
  },

  // Plain JS has no type information, so the type-checked rules cannot run
  // on it. Without this, linting a single .mjs script crashes the whole run.
  {
    files: ['**/*.{js,mjs,cjs}'],
    extends: [tseslint.configs.disableTypeChecked],
  },
);
