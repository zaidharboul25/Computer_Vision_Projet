import React from 'react'
import { ShieldCheck } from 'lucide-react'
import { cn } from '../../lib/cn'

export const LogoMark: React.FC<{ className?: string; pulse?: boolean }> = ({ className, pulse }) => (
  <div className={cn('relative flex h-9 w-9 flex-shrink-0 items-center justify-center', className)}>
    {pulse && <span className="absolute inset-0 animate-pulse-ring rounded-xl bg-brand-500/50" aria-hidden="true" />}
    <div className="relative flex h-full w-full items-center justify-center rounded-xl bg-gradient-to-br from-brand-400 via-brand-600 to-violet-700 text-white shadow-lg shadow-brand-600/30 ring-1 ring-white/20">
      <ShieldCheck className="h-[55%] w-[55%]" strokeWidth={2.2} />
    </div>
  </div>
)

export const LogoWordmark: React.FC<{ className?: string }> = ({ className }) => (
  <span className={cn('text-lg font-bold tracking-tight text-slate-900 dark:text-white', className)}>
    WeaveGuard <span className="gradient-text">AI</span>
  </span>
)
