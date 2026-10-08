import { defineConfig, loadEnv } from 'vite'
import react from '@vitejs/plugin-react'
import tailwindcss from '@tailwindcss/vite'

const trimTrailingSlashes = (value: string) => value.replace(/\/+$/, '')

const normalizeApiPrefix = (value: string | undefined) => {
  const trimmed = value?.trim()
  if (!trimmed) {
    return '/api/v1'
  }

  const withLeadingSlash = trimmed.startsWith('/') ? trimmed : `/${trimmed}`
  return trimTrailingSlashes(withLeadingSlash)
}

// https://vite.dev/config/
export default defineConfig(({ mode }) => {
  const env = loadEnv(mode, process.cwd(), '')
  const legacyBaseUrl = env.VITE_API_BASE_URL?.trim()
  const legacyPrefix = legacyBaseUrl?.startsWith('/') ? legacyBaseUrl : undefined
  const apiPrefix = normalizeApiPrefix(env.VITE_API_PREFIX || legacyPrefix)
  const apiProxyTarget = env.VITE_API_PROXY_TARGET || 'http://127.0.0.1:8000'

  return {
    plugins: [react(), tailwindcss()],
    server: {
      proxy: {
        [apiPrefix]: {
          target: apiProxyTarget,
          changeOrigin: true,
        },
      },
    },
  }
})
