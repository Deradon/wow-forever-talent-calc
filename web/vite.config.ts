/// <reference types="vitest/config" />
import { defineConfig, type Plugin } from 'vite'
import react from '@vitejs/plugin-react'
import tailwindcss from '@tailwindcss/vite'
import { generate } from './scripts/gen-data-index.mjs'

/**
 * Regenerates src/data/classes-index.json and src/data/iconCrops.ts from
 * data/talents|examples and web/tests/fixtures before anything is resolved, so
 * dev, build and vitest always see the current data. Both files are committed
 * (tsc runs before vite in `npm run build`); src/data/generated.test.ts fails
 * if a commit forgets to refresh them.
 */
function dataIndexes(): Plugin {
  return {
    name: 'wow-forever-data-indexes',
    config() {
      generate()
    },
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
