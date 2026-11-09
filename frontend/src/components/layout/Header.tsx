import React, { useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import { ShieldCheck, Moon, Sun, LogOut, Activity } from 'lucide-react'
import { useAuth } from '../../context/AuthContext'
import { useTheme } from '../../context/ThemeContext'
import { RoleBadge } from '../common/RoleBadge'
import { apiFetch } from '../../services/api'
import type { Health } from '../../types'

export const Header: React.FC = () => {
  const { user, logout } = useAuth()
  const { theme, toggleTheme } = useTheme()
  const [healthStatus, setHealthStatus] = useState<'ok' | 'degraded' | 'error'>('ok')

  useEffect(() => {
    let isMounted = true
    const checkHealth = () => {
      apiFetch<Health>('/health')
        .then((res) => {
          if (!isMounted) return
          if (res.status === 'ok') setHealthStatus('ok')
          else setHealthStatus('degraded')
        })
        .catch(() => {
          if (!isMounted) return
          setHealthStatus('error')
        })
    }

    checkHealth()
    const interval = setInterval(checkHealth, 30000)
    return () => {
      isMounted = false
      clearInterval(interval)
    }
  }, [])

  return (
    <header className="sticky top-0 z-40 border-b border-slate-200 bg-white/95 backdrop-blur dark:border-slate-800 dark:bg-slate-900/95">
      <div className="flex h-16 items-center justify-between px-4 sm:px-6">
        <div className="flex items-center gap-3">
          <Link to="/" className="flex items-center gap-2.5 focus:outline-none focus:ring-2 focus:ring-blue-500 rounded-md">
            <div className="flex h-9 w-9 items-center justify-center rounded-lg bg-blue-600 text-white shadow-sm">
              <ShieldCheck className="h-5 w-5" />
            </div>
            <div>
              <span className="text-lg font-bold tracking-tight text-slate-900 dark:text-white">
                WeaveGuard <span className="text-blue-600 dark:text-blue-400">AI</span>
              </span>
              <span className="ml-2 hidden text-xs font-medium text-slate-500 sm:inline dark:text-slate-400">
                Inspection Textile Industrielle
              </span>
            </div>
          </Link>
        </div>

        <div className="flex items-center gap-3">
          {/* Indicateur de santé système */}
          <div
            className="hidden items-center gap-1.5 rounded-full bg-slate-100 px-2.5 py-1 text-xs md:flex dark:bg-slate-800"
            title={`État du système backend : ${healthStatus}`}
          >
            <Activity
              className={`h-3.5 w-3.5 ${
                healthStatus === 'ok'
                  ? 'text-emerald-500'
                  : healthStatus === 'degraded'
                  ? 'text-amber-500'
                  : 'text-rose-500'
              }`}
            />
            <span className="text-slate-600 dark:text-slate-300">
              {healthStatus === 'ok' ? 'Système nominal' : healthStatus === 'degraded' ? 'Mode dégradé' : 'Hors ligne'}
            </span>
          </div>

          {/* Sélecteur de thème */}
          <button
            type="button"
            onClick={toggleTheme}
            className="rounded-lg p-2 text-slate-500 hover:bg-slate-100 focus:outline-none focus:ring-2 focus:ring-blue-500 dark:text-slate-400 dark:hover:bg-slate-800"
            aria-label={theme === 'dark' ? 'Activer le mode clair' : 'Activer le mode sombre'}
          >
            {theme === 'dark' ? <Sun className="h-5 w-5 text-amber-400" /> : <Moon className="h-5 w-5" />}
          </button>

          {/* Profil utilisateur & Déconnexion */}
          {user && (
            <div className="flex items-center gap-2 border-l border-slate-200 pl-3 dark:border-slate-800">
              <div className="hidden text-right sm:block">
                <div className="text-sm font-semibold text-slate-900 dark:text-white">{user.username}</div>
                <RoleBadge role={user.role} className="mt-0.5" />
              </div>

              <button
                type="button"
                onClick={logout}
                className="flex items-center gap-1.5 rounded-lg border border-slate-200 px-3 py-1.5 text-xs font-semibold text-slate-700 hover:bg-rose-50 hover:text-rose-600 focus:outline-none focus:ring-2 focus:ring-rose-500 dark:border-slate-700 dark:text-slate-300 dark:hover:bg-rose-950/40 dark:hover:text-rose-300"
                title="Se déconnecter"
              >
                <LogOut className="h-4 w-4" />
                <span className="hidden md:inline">Déconnexion</span>
              </button>
            </div>
          )}
        </div>
      </div>
    </header>
  )
}

