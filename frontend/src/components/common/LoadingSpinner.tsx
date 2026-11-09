import React from 'react'
import { cn } from '../../lib/cn'

interface LoadingSpinnerProps {
  label?: string
  size?: 'sm' | 'md' | 'lg'
  className?: string
}

/** Petit indicateur d'activité (boutons, badges). Pour les chargements de pages, utiliser les Skeletons. */
export const LoadingSpinner: React.FC<LoadingSpinnerProps> = ({
  label = 'Chargement en cours...',
  size = 'md',
  className = '',
}) => {
  const dims = { sm: 'h-4 w-4', md: 'h-7 w-7', lg: 'h-11 w-11' }[size]
  const stroke = size === 'sm' ? 3.5 : 3

  return (
    <div
      role="status"
      aria-live="polite"
      className={cn(
        size === 'sm'
          ? 'inline-flex items-center gap-2'
          : 'flex flex-col items-center justify-center gap-3 p-6 text-slate-500 dark:text-slate-400',
        className,
      )}
    >
      <svg className={cn('animate-spin', dims)} viewBox="0 0 24 24" fill="none" aria-hidden="true">
        <circle cx="12" cy="12" r="9" stroke="currentColor" strokeOpacity="0.18" strokeWidth={stroke} />
        <path d="M21 12a9 9 0 0 0-9-9" stroke="url(#wg-spin)" strokeWidth={stroke} strokeLinecap="round" />
        <defs>
          <linearGradient id="wg-spin" x1="0" y1="0" x2="1" y2="1">
            <stop stopColor="#6366f1" />
            <stop offset="1" stopColor="#06b6d4" />
          </linearGradient>
        </defs>
      </svg>
      {size === 'sm' ? <span className="sr-only">{label}</span> : <span className="text-sm font-medium">{label}</span>}
    </div>
  )
}
