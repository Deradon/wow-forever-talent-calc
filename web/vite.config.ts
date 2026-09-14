/// <reference types="vitest/config" />
import { defineConfig, type Plugin } from 'vite'
import react from '@vitejs/plugin-react'
import tailwindcss from '@tailwindcss/vite'
import { generate } from './scripts/gen-data-index.mjs'

/**
 * Regenerates the committed indexes under `src/data/` from `data/` while the
 * dev server is running, so an edit to a talent file shows up on the next
 * reload without a separate command.
 *
 * **Dev only, deliberately.** It used to run from `config()` *and*
 * `buildStart()`, in every mode - which meant `vitest` rewrote the committed
 * files before `generated.test.ts` read them, and the test that is supposed to
 * catch a stale commit compared a file against itself. A `STALE-MARKER`
 * injected into `classes-index.json` passed 11/11 and was silently erased
 * (code review K-2). It also meant `npm run build` built from content it had
 * just regenerated and nobody had reviewed.
 *
 * Now: `npm run gen` regenerates, `git diff --exit-code -- src/data` in CI
 * proves the commit is current, and `generated.test.ts` generates into a
 * temporary directory and compares - a check vitest cannot rescue.
 */
function dataIndexes(): Plugin {
  return {
    name: 'wow-forever-data-indexes',
    apply: (config, env) => env.command === 'serve' && config.mode !== 'test' && !process.env.VITEST,
    buildStart() {
      generate()
    },
  }
}

export default defineConfig({
  base: process.env.VITE_BASE ?? '/', // CI sets '/<repo>/'; custom domain later: '/'
  plugins: [dataIndexes(), react(), tailwindcss()],
  server: { fs: { allow: ['..'] } }, // data/ lives outside web/
  build: {
    // Frame crops (36 px icons are ~4 kB) must stay files, not base64 in the bundle.
    assetsInlineLimit: (filePath) => (filePath.includes('/data/review/') ? false : undefined),
  },
  test: { include: ['src/**/*.test.ts'] },
})
