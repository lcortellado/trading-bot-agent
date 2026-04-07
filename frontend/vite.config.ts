import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

// Dev: base "/" + proxy to FastAPI. Production build: served under /dashboard on the API server.
export default defineConfig(({ mode }) => ({
  plugins: [react()],
  base: mode === 'production' ? '/dashboard/' : '/',
  server: {
    port: 5173,
    proxy: {
      '/api': { target: 'http://127.0.0.1:8000', changeOrigin: true },
      '/signal': { target: 'http://127.0.0.1:8000', changeOrigin: true },
      '/agent': { target: 'http://127.0.0.1:8000', changeOrigin: true },
      '/strategy': { target: 'http://127.0.0.1:8000', changeOrigin: true },
      '/health': { target: 'http://127.0.0.1:8000', changeOrigin: true },
    },
  },
}))
