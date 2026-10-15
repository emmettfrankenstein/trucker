import axios from 'axios'

import { tokenStore } from '../auth/tokenStore'

export const api = axios.create({
  baseURL: `${import.meta.env.VITE_API_URL ?? ''}/api`,
  timeout: 60_000,
})

api.interceptors.request.use((config) => {
  const access = tokenStore.access
  if (access) config.headers.Authorization = `Bearer ${access}`
  return config
})

// One refresh in flight at a time; concurrent 401s wait for it, then retry once.
let refreshing = null

async function refreshAccess() {
  const refresh = tokenStore.refresh
  if (!refresh) throw new Error('no refresh token')
  const { data } = await axios.post(`${api.defaults.baseURL}/auth/token/refresh/`, { refresh })
  tokenStore.set({ access: data.access, refresh: data.refresh ?? refresh })
  return data.access
}

api.interceptors.response.use(
  (response) => response,
  async (error) => {
    const original = error.config
    const isAuthCall = original?.url?.startsWith('/auth/token')
    if (error.response?.status === 401 && tokenStore.refresh && !original._retried && !isAuthCall) {
      original._retried = true
      try {
        refreshing ??= refreshAccess().finally(() => (refreshing = null))
        await refreshing
        return api(original)
      } catch {
        tokenStore.clear()
      }
    }
    return Promise.reject(error)
  },
)

/** Human-readable message from our API's error envelope (or a network failure). */
export function errorMessage(error) {
  const body = error?.response?.data?.error
  if (body?.details && typeof body.details === 'object') {
    const [field, msgs] = Object.entries(body.details)[0] ?? []
    const first = Array.isArray(msgs) ? msgs[0] : typeof msgs === 'object' ? Object.values(msgs)[0] : msgs
    if (field && first)
      return field === 'non_field_errors' ? String(first) : `${field.replaceAll('_', ' ')}: ${first}`
  }
  if (body?.message) return body.message
  if (error?.code === 'ECONNABORTED') return 'The request timed out. Please try again.'
  if (!error?.response) return 'Cannot reach the server. Check your connection.'
  return 'Something went wrong. Please try again.'
}
