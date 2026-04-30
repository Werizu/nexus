import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'
import tailwindcss from '@tailwindcss/vite'

export default defineConfig({
  plugins: [react(), tailwindcss()],
  server: {
    port: 3000,
    proxy: {
      '/api': 'http://100.122.236.58:8000',
      '/ws': {
        target: 'ws://100.122.236.58:8000',
        ws: true,
      },
    },
  },
})
