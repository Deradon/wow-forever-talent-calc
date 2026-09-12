/// <reference types="vitest/config" />
import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'
import tailwindcss from '@tailwindcss/vite'

export default defineConfig({
  base: process.env.VITE_BASE ?? '/', // CI sets '/<repo>/'; custom domain later: '/'
  plugins: [react(), tailwindcss()],
  server: { fs: { allow: ['..'] } }, // data/ lives outside web/
  test: { include: ['src/**/*.test.ts'] },
})
