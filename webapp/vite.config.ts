import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

// FastAPI runs on 8765; Vite dev server proxies /api/* through to it so
// hot-reloading the SPA does not require restarting the Python server.
// `npm run build` produces dist/ which FastAPI serves directly in prod mode.
export default defineConfig({
  plugins: [react()],
  server: {
    port: 5173,
    strictPort: false,
    proxy: {
      '/api': {
        target: 'http://127.0.0.1:8765',
        changeOrigin: true,
      },
    },
  },
  build: {
    outDir: 'dist',
    sourcemap: false,
    emptyOutDir: true,
  },
})
