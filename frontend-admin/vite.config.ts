import { defineConfig } from 'vite'
import vue from '@vitejs/plugin-vue'

export default defineConfig({
  plugins: [vue()],
  server: {
    port: 3000,
    host: true,
    allowedHosts: true,
    proxy: {
      '/auth/v1': {
        target: 'http://localhost:8090',
        changeOrigin: true,
      },
    },
  },
})
