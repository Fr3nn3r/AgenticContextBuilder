import { defineConfig, loadEnv } from 'vite'
import react from '@vitejs/plugin-react'
import path from 'path'

export default defineConfig(({ mode }) => {
  // Load env file based on mode (development, production, etc.)
  // This reads from .env, .env.local, .env.[mode], etc.
  const env = loadEnv(mode, process.cwd(), '')

  // Port configuration with fallback defaults
  // Each worktree should have its own .env file with VITE_PORT and VITE_API_PORT
  const frontendPort = parseInt(env.VITE_PORT || '5173')
  const backendPort = env.VITE_API_PORT || '8000'

  return {
    plugins: [react()],
    resolve: {
      alias: {
        '@': path.resolve(__dirname, './src'),
      },
    },
    test: {
      environment: 'jsdom',
      setupFiles: ['./src/test/setup.ts'],
      include: ['src/**/*.{test,spec}.ts', 'src/**/*.{test,spec}.tsx'],
    },
    server: {
      port: frontendPort,
      proxy: {
        '/api': {
          target: `http://localhost:${backendPort}`,
          changeOrigin: true,
          ws: true,
        },
      },
    },
  }
})
