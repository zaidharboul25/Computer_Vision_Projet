import React, { useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import { motion, AnimatePresence } from 'framer-motion'
import { Moon, Sun, LogOut, Menu } from 'lucide-react'
import { useAuth } from '../../context/AuthContext'
import { useTheme } from '../../context/ThemeContext'
import { RoleBadge } from '../common/RoleBadge'
import { LogoMark, LogoWordmark } from '../common/Logo'
import { apiFetch } from '../../services/api'
import type { Health } from '../../types'
import { cn } from '../../lib/cn'

export const Header: React.FC<{ onMenuClick?: () => void }> = ({ onMenuClick }) => {
  const { user, logout } = useAuth()
  const { theme, toggleTheme } = useTheme()
  const [healthStatus, setHealthStatus] = useState<'ok' | 'degraded' | 'error'>('ok')

  useEffect(() => {
    let isMounted = true
    const checkHealth = () => {
      apiFetch<Health>('/health')
        .then((res) => {
          if (!isMounted) return
          setHealthStatus(res.status === 'ok' ? 'ok' : 'degraded')
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

  const dot = healthStatus === 'ok' ? 'bg-emerald-500' : healthStatus === 'degraded' ? 'bg-amber-500' : 'bg-rose-500'
  const label = healthStatus === 'ok' ? 'Système nominal' : healthStatus === 'degraded' ? 'Mode dégradé' : 'Hors ligne'

  return (
    <header className="sticky top-0 z-40 border-b border-slate-200/80 bg-white/75 backdrop-blur-xl dark:border-white/[0.07] dark:bg-ink-950/70">
      <div className="flex h-16 items-center justify-between px-4 sm:px-6">
        <div className="flex items-center gap-2">
          <button type="button" onClick={onMenuClick} className="btn-ghost !p-2 lg:hidden" aria-label="Ouvrir le menu">
            <Menu className="h-5 w-5" />
          </button>
          <Link to="/" className="flex items-center gap-2.5 rounded-xl">
            <LogoMark />
            <div className="flex flex-col leading-tight">
              <LogoWordmark />
              <span className="hidden text-[11px] font-medium text-slate-500 sm:block dark:text-slate-400">
                Inspection Textile Industrielle
              </span>
            </div>
          </Link>
        </div>

        <div className="flex items-center gap-2 sm:gap-3">
          <div
            className="hidden items-center gap-2 rounded-full border border-slate-200 bg-white/80 px-3 py-1.5 text-xs font-medium md:flex dark:border-white/10 dark:bg-white/5"
            title={`État du système backend : ${healthStatus}`}
          >
            <span className="relative flex h-2 w-2">
              {healthStatus === 'ok' && <span className={cn('absolute inline-flex h-full w-full animate-ping rounded-full opacity-60', dot)} />}
              <span className={cn('relative inline-flex h-2 w-2 rounded-full', dot)} />
            </span>
            <span className="text-slate-600 dark:text-slate-300">{label}</span>
          </div>

          <button
            type="button"
            onClick={toggleTheme}
            className="btn-ghost relative !p-2.5 overflow-hidden"
            aria-label={theme === 'dark' ? 'Activer le mode clair' : 'Activer le mode sombre'}
          >
            <AnimatePresence mode="wait" initial={false}>
              <motion.span
                key={theme}
                initial={{ rotate: -90, scale: 0.4, opacity: 0 }}
                animate={{ rotate: 0, scale: 1, opacity: 1 }}
                exit={{ rotate: 90, scale: 0.4, opacity: 0 }}
                transition={{ duration: 0.22 }}
                className="block"
              >
                {theme === 'dark' ? <Sun className="h-5 w-5 text-amber-400" /> : <Moon className="h-5 w-5" />}
              </motion.span>
            </AnimatePresence>
          </button>

          {user && (
            <div className="flex items-center gap-3 border-l border-slate-200 pl-3 dark:border-white/10">
              <div className="flex h-9 w-9 items-center justify-center rounded-full bg-gradient-to-br from-brand-500 to-violet-600 text-sm font-bold uppercase text-white shadow-md shadow-brand-600/25 sm:hidden">
                {user.username.slice(0, 1)}
              </div>
              <div className="hidden text-right sm:block">
                <div className="text-sm font-semibold leading-none text-slate-900 dark:text-white">{user.username}</div>
                <RoleBadge role={user.role} className="mt-1" />
              </div>
              <button
                type="button"
                onClick={logout}
                className="btn-secondary !px-3 !py-2 text-xs hover:!border-rose-300 hover:!bg-rose-50 hover:!text-rose-600 dark:hover:!bg-rose-950/40 dark:hover:!text-rose-300"
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
