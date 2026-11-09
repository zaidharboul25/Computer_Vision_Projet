import React, { createContext, useContext, useState, useEffect, useCallback } from 'react'
import type { UserRole } from '../types'
import { apiFetch, logoutRequest, setCsrfToken, onUnauthenticated } from '../services/api'

interface AuthUser {
  username: string
  role: UserRole
}

interface AuthContextType {
  user: AuthUser | null
  isLoading: boolean
  login: (user: AuthUser, csrfToken: string) => void
  logout: () => void
  hasRole: (roles: UserRole | UserRole[]) => boolean
}

const AuthContext = createContext<AuthContextType | undefined>(undefined)

export const AuthProvider: React.FC<{ children: React.ReactNode }> = ({ children }) => {
  const [user, setUser] = useState<AuthUser | null>(null)
  const [isLoading, setIsLoading] = useState<boolean>(true)

  const clearSession = useCallback(() => {
    setCsrfToken(null)
    setUser(null)
  }, [])

  const logout = useCallback(() => {
    // Le cookie httpOnly ne peut être supprimé que par l'API.
    logoutRequest().catch(() => undefined)
    clearSession()
  }, [clearSession])

  const login = useCallback((newUser: AuthUser, csrfToken: string) => {
    setCsrfToken(csrfToken)
    setUser(newUser)
  }, [])

  // Restauration de session : le cookie httpOnly est envoyé automatiquement à /auth/me.
  useEffect(() => {
    onUnauthenticated(clearSession)

    let cancelled = false
    apiFetch<{ username: string; role: UserRole; csrf_token: string }>('/api/v1/auth/me')
      .then((me) => {
        if (cancelled) return
        setCsrfToken(me.csrf_token)
        setUser({ username: me.username, role: me.role })
      })
      .catch(() => {
        if (!cancelled) clearSession()
      })
      .finally(() => {
        if (!cancelled) setIsLoading(false)
      })
    return () => {
      cancelled = true
    }
  }, [clearSession])

  const hasRole = useCallback(
    (roles: UserRole | UserRole[]) => {
      if (!user) return false
      const allowed = Array.isArray(roles) ? roles : [roles]
      return allowed.includes(user.role)
    },
    [user]
  )

  return <AuthContext.Provider value={{ user, isLoading, login, logout, hasRole }}>{children}</AuthContext.Provider>
}

export function useAuth(): AuthContextType {
  const ctx = useContext(AuthContext)
  if (!ctx) {
    throw new Error('useAuth doit être utilisé au sein de AuthProvider')
  }
  return ctx
}
