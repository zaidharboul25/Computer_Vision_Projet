import React, { createContext, useContext, useState, useEffect, useCallback } from 'react'
import type { UserRole } from '../types'
import { apiFetch, setAuthToken, getAuthToken, onUnauthenticated } from '../services/api'

interface AuthUser {
  username: string
  role: UserRole
}

interface AuthContextType {
  user: AuthUser | null
  token: string | null
  isLoading: boolean
  login: (token: string, user: AuthUser) => void
  logout: () => void
  hasRole: (roles: UserRole | UserRole[]) => boolean
}

const AuthContext = createContext<AuthContextType | undefined>(undefined)

const USER_STORAGE_KEY = 'weaveguard_user'

export const AuthProvider: React.FC<{ children: React.ReactNode }> = ({ children }) => {
  const [user, setUser] = useState<AuthUser | null>(() => {
    const saved = sessionStorage.getItem(USER_STORAGE_KEY)
    if (saved) {
      try {
        return JSON.parse(saved)
      } catch {
        return null
      }
    }
    return null
  })
  const [token, setTokenState] = useState<string | null>(getAuthToken())
  const [isLoading, setIsLoading] = useState<boolean>(true)

  const logout = useCallback(() => {
    setAuthToken(null)
    setTokenState(null)
    setUser(null)
    sessionStorage.removeItem(USER_STORAGE_KEY)
  }, [])

  const login = useCallback((newToken: string, newUser: AuthUser) => {
    setAuthToken(newToken)
    setTokenState(newToken)
    setUser(newUser)
    sessionStorage.setItem(USER_STORAGE_KEY, JSON.stringify(newUser))
  }, [])

  // Rafraîchir les infos de session via /api/v1/auth/me au chargement
  useEffect(() => {
    onUnauthenticated(() => {
      logout()
    })

    const initialToken = getAuthToken()
    if (!initialToken) {
      setIsLoading(false)
      return
    }

    apiFetch<{ username: string; role: UserRole }>('/api/v1/auth/me')
      .then((me) => {
        setUser({ username: me.username, role: me.role })
        sessionStorage.setItem(USER_STORAGE_KEY, JSON.stringify({ username: me.username, role: me.role }))
      })
      .catch(() => {
        logout()
      })
      .finally(() => {
        setIsLoading(false)
      })
  }, [logout])

  const hasRole = useCallback(
    (roles: UserRole | UserRole[]) => {
      if (!user) return false
      const allowed = Array.isArray(roles) ? roles : [roles]
      return allowed.includes(user.role)
    },
    [user]
  )

  return (
    <AuthContext.Provider value={{ user, token, isLoading, login, logout, hasRole }}>
      {children}
    </AuthContext.Provider>
  )
}

export function useAuth(): AuthContextType {
  const ctx = useContext(AuthContext)
  if (!ctx) {
    throw new Error('useAuth doit être utilisé au sein de AuthProvider')
  }
  return ctx
}

