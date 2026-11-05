import { defineConfig } from 'vitest/config'
import react from '@vitejs/plugin-react'
import { loadEnv } from 'vite'

export default defineConfig(({ mode }) => {
  const target = loadEnv(mode, '.', 'TESTLAB_VITE_PROXY_TARGET').TESTLAB_VITE_PROXY_TARGET || 'http://127.0.0.1:8000'
  const proxy = { '/api': target, '/health': target }
  return {
    plugins: [react()],
    server: { proxy },
    preview: { proxy },
    test: { environment: 'jsdom', css: false },
  }
})
