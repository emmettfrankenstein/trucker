import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

export default defineConfig({
  plugins: [react()],
  server: {
    port: 5173,
    proxy: { '/api': 'http://localhost:8000' },
  },
  preview: {
    port: 4173,
    proxy: { '/api': 'http://localhost:8000' },
  },
  build: {
    // MapLibre alone is ~800 kB minified; it is split into its own long-cached chunk.
    chunkSizeWarningLimit: 900,
    rollupOptions: {
      output: {
        // Keep the heavy map engine in its own cacheable chunk.
        manualChunks: { maplibre: ['maplibre-gl', 'react-map-gl/maplibre'], mui: ['@mui/material'] },
      },
    },
  },
  test: {
    environment: 'jsdom',
    globals: true,
    setupFiles: './src/test/setup.js',
    include: ['src/**/*.test.{js,jsx}'],
  },
})
