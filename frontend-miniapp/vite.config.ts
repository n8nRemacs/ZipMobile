import { defineConfig } from 'vite'
import vue from '@vitejs/plugin-vue'

// https://vite.dev/config/
export default defineConfig({
  plugins: [vue()],
  server: {
    allowedHosts: true,
    proxy: {
      '/auth/v1': {
        target: 'http://localhost:8090',
        changeOrigin: true,
      },
    },
  },
})
