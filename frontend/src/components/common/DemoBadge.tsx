import React from 'react'
import { Sparkles } from 'lucide-react'

interface DemoBadgeProps {
  className?: string
  showText?: boolean
}

export const DemoBadge: React.FC<DemoBadgeProps> = ({ className = '', showText = true }) => {
  return (
    <span
      title="Donnée de démonstration — validation réelle sans impact sur la production"
      className={`inline-flex items-center gap-1 rounded border border-amber-400 bg-amber-100 px-2 py-0.5 text-xs font-bold uppercase tracking-wider text-amber-900 shadow-sm dark:border-amber-600 dark:bg-amber-950/70 dark:text-amber-200 ${className}`}
    >
      <Sparkles className="h-3 w-3 text-amber-600 dark:text-amber-400" aria-hidden="true" />
      {showText && <span>DÉMO</span>}
    </span>
  )
}

