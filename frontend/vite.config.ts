import react from '@vitejs/plugin-react'
import { defineConfig } from 'vite'

// https://vite.dev/config/
export default defineConfig({
  plugins: [react()],
  server: {
    port: 5173,
    proxy: {
      '/health': 'http://127.0.0.1:8008',
      '/decisions': {
        target: 'http://127.0.0.1:8008',
        changeOrigin: true,
      },
      '/gate': {
        target: 'http://127.0.0.1:8008',
        changeOrigin: true,
      },
      '/orders': {
        target: 'http://127.0.0.1:8008',
        changeOrigin: true,
      },
      '/demo': {
        target: 'http://127.0.0.1:8008',
        changeOrigin: true,
      },
      '/metrics': {
        target: 'http://127.0.0.1:8008',
        changeOrigin: true,
      },
    },
  },
})
