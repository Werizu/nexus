import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'
import tailwindcss from '@tailwindcss/vite'

export default defineConfig({
  plugins: [react(), tailwindcss()],
  server: {
    port: 3000,
    proxy: {
      '/api': 'http://192.168.178.202:8000',
      '/ws': {
        target: 'ws://192.168.178.202:8000',
        ws: true,
      },
    },
  },
})
