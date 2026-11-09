import React from 'react'
import { Loader2 } from 'lucide-react'

interface LoadingSpinnerProps {
  label?: string
  size?: 'sm' | 'md' | 'lg'
  className?: string
}

export const LoadingSpinner: React.FC<LoadingSpinnerProps> = ({
  label = 'Chargement en cours...',
  size = 'md',
  className = '',
}) => {
  const sizeClasses = {
    sm: 'h-4 w-4',
    md: 'h-6 w-6',
    lg: 'h-10 w-10',
  }

  return (
    <div
      role="status"
      aria-live="polite"
      className={`flex flex-col items-center justify-center gap-2 p-6 text-slate-500 dark:text-slate-400 ${className}`}
    >
      <Loader2 className={`animate-spin text-blue-600 dark:text-blue-400 ${sizeClasses[size]}`} aria-hidden="true" />
      <span className="text-sm font-medium">{label}</span>
    </div>
  )
}

