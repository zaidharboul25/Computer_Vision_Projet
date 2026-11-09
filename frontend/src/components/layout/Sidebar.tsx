import React from 'react'
import { NavLink } from 'react-router-dom'
import {
  LayoutDashboard,
  PlusCircle,
  History,
  Sparkles,
  BarChart3,
  ShieldAlert,
} from 'lucide-react'
import { useAuth } from '../../context/AuthContext'
import type { UserRole } from '../../types'

interface NavItem {
  to: string
  label: string
  icon: React.ElementType
  roles?: UserRole[]
  badge?: string
}

const NAV_ITEMS: NavItem[] = [
  {
    to: '/',
    label: 'Tableau de bord',
    icon: LayoutDashboard,
  },
  {
    to: '/inspections/new',
    label: 'Nouvelle inspection',
    icon: PlusCircle,
    roles: ['operator', 'supervisor', 'admin'],
  },
  {
    to: '/inspections',
    label: 'Historique des inspections',
    icon: History,
  },
  {
    to: '/similarity',
    label: 'Textiles similaires',
    icon: Sparkles,
  },
  {
    to: '/models',
    label: 'Évaluation ML & Fiches',
    icon: BarChart3,
  },
  {
    to: '/admin',
    label: 'Administration & Audit',
    icon: ShieldAlert,
    roles: ['admin', 'supervisor', 'auditor'],
  },
]

export const Sidebar: React.FC = () => {
  const { hasRole } = useAuth()

  return (
    <aside className="w-64 flex-shrink-0 border-r border-slate-200 bg-white dark:border-slate-800 dark:bg-slate-900">
      <nav className="flex flex-col gap-1 p-4" aria-label="Navigation principale">
        {NAV_ITEMS.map((item) => {
          if (item.roles && !hasRole(item.roles)) {
            return null
          }

          const Icon = item.icon

          return (
            <NavLink
              key={item.to}
              to={item.to}
              end={item.to === '/'}
              className={({ isActive }) =>
                `flex items-center gap-3 rounded-lg px-3 py-2.5 text-sm font-semibold transition-colors focus:outline-none focus:ring-2 focus:ring-blue-500 ${
                  isActive
                    ? 'bg-blue-50 text-blue-700 dark:bg-blue-950/60 dark:text-blue-300'
                    : 'text-slate-700 hover:bg-slate-100 dark:text-slate-300 dark:hover:bg-slate-800'
                }`
              }
            >
              <Icon className="h-5 w-5 flex-shrink-0" aria-hidden="true" />
              <span className="flex-1">{item.label}</span>
              {item.badge && (
                <span className="rounded bg-slate-200 px-1.5 py-0.5 text-xs font-bold text-slate-700 dark:bg-slate-800 dark:text-slate-300">
                  {item.badge}
                </span>
              )}
            </NavLink>
          )
        })}
      </nav>
    </aside>
  )
}

