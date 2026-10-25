import { fileURLToPath, URL } from 'node:url'
import { defineConfig } from 'vitest/config'
import { loadEnv, type PluginOption } from 'vite'
import vue from '@vitejs/plugin-vue'
import tailwindcss from '@tailwindcss/vite'
import { mockApiPlugin } from './mock/mockApi.ts'

export default defineConfig(({ mode }) => {
  const env = loadEnv(mode, process.cwd(), '')
  const useMock = env.VITE_MOCK === '1' && mode !== 'production'
  const plugins: PluginOption[] = [vue(), tailwindcss()]
  if (useMock) plugins.push(mockApiPlugin())

  return {
    plugins,
    resolve: {
      alias: { '@': fileURLToPath(new URL('./src', import.meta.url)) },
    },
    build: {
      chunkSizeWarningLimit: 1500,
      rollupOptions: {
        output: {
          manualChunks(id: string) {
            if (id.includes('opensheetmusicdisplay') || id.includes('vexflow'))
              return 'osmd'
            if (id.includes('node_modules/tone')) return 'tone'
          },
        },
      },
    },
    test: {
      environment: 'node',
      include: ['tests/**/*.test.ts'],
    },
  }
})
