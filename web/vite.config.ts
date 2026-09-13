/// <reference types="vitest/config" />
import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'
import tailwindcss from '@tailwindcss/vite'

export default defineConfig({
  base: process.env.VITE_BASE ?? '/', // CI sets '/<repo>/'; custom domain later: '/'
  plugins: [react(), tailwindcss()],
  server: { fs: { allow: ['..'] } }, // data/ lives outside web/
  build: {
    // Frame crops (36 px icons are ~4 kB) must stay files, not base64 in the bundle.
    assetsInlineLimit: (filePath) => (filePath.includes('/data/review/') ? false : undefined),
  },
  test: { include: ['src/**/*.test.ts'] },
})
