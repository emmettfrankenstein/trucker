import { useQuery, useQueryClient } from '@tanstack/react-query'
import { createContext, useCallback, useContext, useEffect, useMemo, useState } from 'react'

import * as endpoints from '../api/endpoints'
import { tokenStore } from './tokenStore'

const AuthContext = createContext(null)

export function AuthProvider({ children }) {
  const queryClient = useQueryClient()
  const [hasToken, setHasToken] = useState(Boolean(tokenStore.refresh))

  useEffect(() => tokenStore.subscribe((s) => setHasToken(Boolean(s.refresh))), [])

  const { data: user, isLoading } = useQuery({
    queryKey: ['me'],
    queryFn: endpoints.me,
    enabled: hasToken,
    retry: false,
    staleTime: Infinity,
  })

  const login = useCallback(
    async (credentials) => {
      const tokens = await endpoints.login(credentials)
      tokenStore.set(tokens)
      await queryClient.invalidateQueries({ queryKey: ['me'] })
    },
    [queryClient],
  )

  const register = useCallback(
    async (body) => {
      const { access, refresh } = await endpoints.register(body)
      tokenStore.set({ access, refresh })
      await queryClient.invalidateQueries({ queryKey: ['me'] })
    },
    [queryClient],
  )

  const logout = useCallback(async () => {
    const refresh = tokenStore.refresh
    try {
      if (refresh) await endpoints.logout(refresh)
    } finally {
      tokenStore.clear()
      queryClient.removeQueries({ queryKey: ['me'] })
      queryClient.removeQueries({ queryKey: ['trips'] })
    }
  }, [queryClient])

  const value = useMemo(
    () => ({ user: hasToken ? user : null, loading: hasToken && isLoading, login, register, logout }),
    [hasToken, user, isLoading, login, register, logout],
  )
  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>
}

// eslint-disable-next-line react-refresh/only-export-components
export function useAuth() {
  const ctx = useContext(AuthContext)
  if (!ctx) throw new Error('useAuth must be used inside <AuthProvider>')
  return ctx
}
