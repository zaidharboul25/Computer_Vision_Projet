import React from 'react'
import { NavLink } from 'react-router-dom'
import { motion, AnimatePresence } from 'framer-motion'
import { LayoutDashboard, PlusCircle, History, Sparkles, BarChart3, ShieldAlert, X } from 'lucide-react'
import { useAuth } from '../../context/AuthContext'
import type { UserRole } from '../../types'
import { LogoMark, LogoWordmark } from '../common/Logo'
import { cn } from '../../lib/cn'

interface NavItem {
  to: string
  label: string
  icon: React.ElementType
  roles?: UserRole[]
  badge?: string
}

const NAV_ITEMS: NavItem[] = [
  { to: '/', label: 'Tableau de bord', icon: LayoutDashboard },
  { to: '/inspections/new', label: 'Nouvelle inspection', icon: PlusCircle, roles: ['operator', 'supervisor', 'admin'] },
  { to: '/inspections', label: 'Historique des inspections', icon: History },
  { to: '/similarity', label: 'Textiles similaires', icon: Sparkles },
  { to: '/models', label: 'Évaluation ML & Fiches', icon: BarChart3 },
  { to: '/admin', label: 'Administration & Audit', icon: ShieldAlert, roles: ['admin', 'supervisor', 'auditor'] },
]

const NavList: React.FC<{ onNavigate?: () => void }> = ({ onNavigate }) => {
  const { hasRole } = useAuth()
  return (
    <nav className="flex flex-col gap-1 p-3" aria-label="Navigation principale">
      <p className="eyebrow px-3 pb-2 pt-2">Navigation</p>
      {NAV_ITEMS.map((item) => {
        if (item.roles && !hasRole(item.roles)) return null
        const Icon = item.icon
        return (
          <NavLink
            key={item.to}
            to={item.to}
            end={item.to === '/' || item.to === '/inspections'}
            onClick={onNavigate}
            className={({ isActive }) =>
              cn(
                'group relative flex items-center gap-3 rounded-xl px-3 py-2.5 text-sm font-semibold transition-colors',
                isActive
                  ? 'text-brand-700 dark:text-white'
                  : 'text-slate-600 hover:text-slate-900 dark:text-slate-400 dark:hover:text-white',
              )
            }
          >
            {({ isActive }) => (
              <>
                {isActive && (
                  <motion.span
                    layoutId="sidebar-active"
                    className="absolute inset-0 rounded-xl bg-brand-50 ring-1 ring-brand-200/70 dark:bg-brand-500/15 dark:ring-brand-400/25"
                    transition={{ type: 'spring', stiffness: 420, damping: 34 }}
                  />
                )}
                {isActive && (
                  <motion.span
                    layoutId="sidebar-bar"
                    className="absolute -left-3 top-2.5 bottom-2.5 w-1 rounded-r-full bg-gradient-to-b from-brand-500 to-cyan-500"
                    transition={{ type: 'spring', stiffness: 420, damping: 34 }}
                  />
                )}
                {!isActive && (
                  <span className="absolute inset-0 rounded-xl bg-slate-100 opacity-0 transition-opacity group-hover:opacity-100 dark:bg-white/5" />
                )}
                <Icon
                  className={cn(
                    'relative h-5 w-5 flex-shrink-0 transition-transform duration-300 group-hover:scale-110',
                    isActive && 'text-brand-600 dark:text-brand-300',
                  )}
                  aria-hidden="true"
                />
                <span className="relative flex-1">{item.label}</span>
                {item.badge && (
                  <span className="relative rounded bg-slate-200 px-1.5 py-0.5 text-xs font-bold text-slate-700 dark:bg-slate-800 dark:text-slate-300">
                    {item.badge}
                  </span>
                )}
              </>
            )}
          </NavLink>
        )
      })}
    </nav>
  )
}

const SidebarFooter: React.FC = () => (
  <div className="m-3 mt-auto rounded-2xl border border-brand-200/60 bg-gradient-to-br from-brand-50 to-cyan-50 p-4 dark:border-brand-400/20 dark:from-brand-500/10 dark:to-cyan-500/10">
    <div className="flex items-center gap-2 text-xs font-semibold text-brand-700 dark:text-brand-300">
      <Sparkles className="h-4 w-4" />
      Double moteur IA
    </div>
    <p className="mt-1.5 text-xs leading-relaxed text-slate-600 dark:text-slate-400">
      YOLOv11 pour les défauts connus, PatchCore pour les anomalies inédites.
    </p>
  </div>
)

interface SidebarProps {
  open: boolean
  onClose: () => void
}

export const Sidebar: React.FC<SidebarProps> = ({ open, onClose }) => {
  return (
    <>
      {/* Desktop */}
      <aside className="sticky top-16 hidden h-[calc(100vh-4rem)] w-64 flex-shrink-0 flex-col overflow-y-auto border-r border-slate-200/80 bg-white/70 backdrop-blur-xl lg:flex dark:border-white/[0.07] dark:bg-ink-900/60">
        <NavList />
        <SidebarFooter />
      </aside>

      {/* Mobile drawer */}
      <AnimatePresence>
        {open && (
          <>
            <motion.div
              key="overlay"
              className="fixed inset-0 z-50 bg-slate-950/50 backdrop-blur-sm lg:hidden"
              initial={{ opacity: 0 }}
              animate={{ opacity: 1 }}
              exit={{ opacity: 0 }}
              onClick={onClose}
            />
            <motion.aside
              key="drawer"
              className="fixed inset-y-0 left-0 z-50 flex w-72 flex-col overflow-y-auto bg-white shadow-2xl lg:hidden dark:bg-ink-900"
              initial={{ x: '-100%' }}
              animate={{ x: 0 }}
              exit={{ x: '-100%' }}
              transition={{ type: 'spring', stiffness: 380, damping: 36 }}
            >
              <div className="flex h-16 items-center justify-between border-b border-slate-200 px-4 dark:border-white/[0.07]">
                <div className="flex items-center gap-2.5">
                  <LogoMark />
                  <LogoWordmark />
                </div>
                <button type="button" onClick={onClose} className="btn-ghost !p-2" aria-label="Fermer le menu">
                  <X className="h-5 w-5" />
                </button>
              </div>
              <NavList onNavigate={onClose} />
              <SidebarFooter />
            </motion.aside>
          </>
        )}
      </AnimatePresence>
    </>
  )
}
