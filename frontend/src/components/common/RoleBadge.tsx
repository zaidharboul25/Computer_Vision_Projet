import React from 'react'
import type { UserRole } from '../../types'
import { Shield, User, Eye, Wrench, FileSearch } from 'lucide-react'

interface RoleBadgeProps {
  role: UserRole
  className?: string
}

const ROLE_CONFIG: Record<UserRole, { label: string; bg: string; text: string; border: string; icon: React.ElementType }> = {
  operator: {
    label: 'Opérateur',
    bg: 'bg-blue-50 dark:bg-blue-950/40',
    text: 'text-blue-700 dark:text-blue-300',
    border: 'border-blue-300 dark:border-blue-800',
    icon: User,
  },
  supervisor: {
    label: 'Superviseur',
    bg: 'bg-emerald-50 dark:bg-emerald-950/40',
    text: 'text-emerald-700 dark:text-emerald-300',
    border: 'border-emerald-300 dark:border-emerald-800',
    icon: Eye,
  },
  admin: {
    label: 'Administrateur',
    bg: 'bg-purple-50 dark:bg-purple-950/40',
    text: 'text-purple-700 dark:text-purple-300',
    border: 'border-purple-300 dark:border-purple-800',
    icon: Shield,
  },
  ml_engineer: {
    label: 'Ingénieur ML',
    bg: 'bg-amber-50 dark:bg-amber-950/40',
    text: 'text-amber-700 dark:text-amber-300',
    border: 'border-amber-300 dark:border-amber-800',
    icon: Wrench,
  },
  auditor: {
    label: 'Auditeur',
    bg: 'bg-slate-100 dark:bg-slate-800/50',
    text: 'text-slate-700 dark:text-slate-300',
    border: 'border-slate-300 dark:border-slate-700',
    icon: FileSearch,
  },
}

export const RoleBadge: React.FC<RoleBadgeProps> = ({ role, className = '' }) => {
  const config = ROLE_CONFIG[role] || {
    label: role,
    bg: 'bg-gray-100 dark:bg-gray-800',
    text: 'text-gray-700 dark:text-gray-300',
    border: 'border-gray-300 dark:border-gray-700',
    icon: User,
  }

  const Icon = config.icon

  return (
    <span
      className={`inline-flex items-center gap-1.5 rounded-full border px-2.5 py-0.5 text-xs font-semibold ${config.bg} ${config.text} ${config.border} ${className}`}
    >
      <Icon className="h-3.5 w-3.5" aria-hidden="true" />
      <span>{config.label}</span>
    </span>
  )
}

