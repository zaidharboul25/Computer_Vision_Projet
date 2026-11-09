import React from 'react'
import { cn } from '../../lib/cn'

/** Bloc de base : rectangle animé (shimmer) qui réserve la place du contenu à venir. */
export const Skeleton: React.FC<{ className?: string; style?: React.CSSProperties }> = ({ className, style }) => (
  <div className={cn('skeleton', className)} style={style} aria-hidden="true" />
)

export const SkeletonText: React.FC<{ lines?: number; className?: string }> = ({ lines = 3, className }) => (
  <div className={cn('space-y-2.5', className)} aria-hidden="true">
    {Array.from({ length: lines }).map((_, i) => (
      <Skeleton key={i} className="h-3.5" style={{ width: i === lines - 1 ? '62%' : '100%' }} />
    ))}
  </div>
)

/** Enveloppe d'accessibilité : annonce un chargement aux lecteurs d'écran. */
export const SkeletonRegion: React.FC<{
  label?: string
  className?: string
  children: React.ReactNode
}> = ({ label = 'Chargement en cours', className, children }) => (
  <div role="status" aria-busy="true" aria-live="polite" className={className}>
    <span className="sr-only">{label}</span>
    {children}
  </div>
)

export const PageHeaderSkeleton: React.FC<{ action?: boolean }> = ({ action }) => (
  <div className="flex items-center justify-between gap-4">
    <div className="space-y-3">
      <Skeleton className="h-8 w-72 max-w-full" />
      <Skeleton className="h-4 w-96 max-w-full" />
    </div>
    {action && <Skeleton className="hidden h-11 w-44 rounded-xl sm:block" />}
  </div>
)

export const StatCardSkeleton: React.FC = () => (
  <div className="card p-5">
    <div className="flex items-center justify-between">
      <Skeleton className="h-3 w-28" />
      <Skeleton className="h-9 w-9 rounded-xl" />
    </div>
    <Skeleton className="mt-5 h-9 w-24" />
    <Skeleton className="mt-3 h-3 w-40" />
  </div>
)

export const StatGridSkeleton: React.FC<{ count?: number }> = ({ count = 4 }) => (
  <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-4">
    {Array.from({ length: count }).map((_, i) => (
      <StatCardSkeleton key={i} />
    ))}
  </div>
)

export const TableSkeleton: React.FC<{ rows?: number; cols?: number }> = ({ rows = 8, cols = 6 }) => (
  <div aria-hidden="true">
    <div className="table-head flex gap-6 px-5 py-4">
      {Array.from({ length: cols }).map((_, i) => (
        <Skeleton key={i} className="h-3 flex-1" />
      ))}
    </div>
    {Array.from({ length: rows }).map((_, r) => (
      <div key={r} className="flex items-center gap-6 border-b border-slate-100 px-5 py-4 last:border-0 dark:border-white/[0.05]">
        {Array.from({ length: cols }).map((_, c) => (
          <Skeleton
            key={c}
            className={c === 0 ? 'h-4 flex-1' : 'h-4 flex-1'}
            style={{ opacity: 1 - r * 0.07, maxWidth: c === cols - 1 ? 90 : undefined }}
          />
        ))}
      </div>
    ))}
  </div>
)

export const CardSkeleton: React.FC<{ className?: string; lines?: number }> = ({ className, lines = 4 }) => (
  <div className={cn('card p-6', className)}>
    <div className="flex items-center gap-3">
      <Skeleton className="h-11 w-11 rounded-xl" />
      <div className="flex-1 space-y-2">
        <Skeleton className="h-4 w-40" />
        <Skeleton className="h-3 w-24" />
      </div>
    </div>
    <SkeletonText className="mt-6" lines={lines} />
  </div>
)

export const ImageSkeleton: React.FC<{ className?: string }> = ({ className }) => (
  <div className={cn('relative w-full overflow-hidden rounded-xl', className)} aria-hidden="true">
    <Skeleton className="h-full min-h-[320px] w-full rounded-xl" />
    <div className="absolute inset-x-0 top-0 h-1/3 animate-scan bg-gradient-to-b from-transparent via-brand-500/20 to-transparent" />
  </div>
)

/* ===== Squelettes de pages entières ===== */

export const DashboardSkeleton: React.FC = () => (
  <SkeletonRegion label="Chargement du tableau de bord" className="space-y-6">
    <Skeleton className="h-44 w-full rounded-3xl" />
    <StatGridSkeleton />
    <div className="grid gap-6 lg:grid-cols-3">
      <div className="card p-6 lg:col-span-2">
        <Skeleton className="h-4 w-48" />
        <Skeleton className="mt-6 h-56 w-full" />
      </div>
      <div className="card p-6">
        <Skeleton className="h-4 w-36" />
        <Skeleton className="mx-auto mt-6 h-40 w-40 rounded-full" />
      </div>
    </div>
  </SkeletonRegion>
)

export const ListPageSkeleton: React.FC = () => (
  <SkeletonRegion label="Chargement de la page" className="space-y-6">
    <PageHeaderSkeleton action />
    <div className="card p-5">
      <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-5">
        {Array.from({ length: 5 }).map((_, i) => (
          <div key={i} className="space-y-2">
            <Skeleton className="h-3 w-20" />
            <Skeleton className="h-10 w-full rounded-xl" />
          </div>
        ))}
      </div>
    </div>
    <div className="card overflow-hidden">
      <TableSkeleton />
    </div>
  </SkeletonRegion>
)

export const ModelsPageSkeleton: React.FC = () => (
  <SkeletonRegion label="Chargement des fiches modèles" className="space-y-8">
    <PageHeaderSkeleton />
    <div className="grid gap-6 lg:grid-cols-3">
      <CardSkeleton lines={5} />
      <CardSkeleton lines={5} />
      <CardSkeleton lines={5} />
    </div>
    <div className="card p-6">
      <Skeleton className="h-4 w-64" />
      <Skeleton className="mt-6 h-48 w-full" />
    </div>
  </SkeletonRegion>
)

export const InspectionResultSkeleton: React.FC = () => (
  <SkeletonRegion label="Chargement de l'inspection" className="space-y-6">
    <div className="flex items-center justify-between gap-4">
      <div className="space-y-3">
        <Skeleton className="h-4 w-32" />
        <Skeleton className="h-8 w-80 max-w-full" />
      </div>
      <Skeleton className="h-8 w-28 rounded-full" />
    </div>
    <div className="grid gap-6 lg:grid-cols-3">
      <div className="card p-5 lg:col-span-2">
        <div className="flex gap-2">
          <Skeleton className="h-9 w-24 rounded-lg" />
          <Skeleton className="h-9 w-24 rounded-lg" />
          <Skeleton className="h-9 w-24 rounded-lg" />
        </div>
        <ImageSkeleton className="mt-4" />
      </div>
      <div className="space-y-6">
        <CardSkeleton lines={3} />
        <CardSkeleton lines={4} />
      </div>
    </div>
  </SkeletonRegion>
)

/** Squelette de la coquille applicative (en-tête + menu + contenu) — affiché pendant la vérification de session. */
export const AppShellSkeleton: React.FC = () => (
  <div className="flex min-h-screen flex-col" role="status" aria-busy="true" aria-live="polite">
    <span className="sr-only">Vérification de la session…</span>
    <div className="flex h-16 items-center justify-between border-b border-slate-200 bg-white px-6 dark:border-white/[0.07] dark:bg-ink-900">
      <div className="flex items-center gap-3">
        <div className="h-9 w-9 rounded-xl bg-gradient-to-br from-brand-500 to-brand-700 opacity-90" />
        <Skeleton className="h-5 w-40" />
      </div>
      <div className="flex items-center gap-3">
        <Skeleton className="hidden h-7 w-32 rounded-full md:block" />
        <Skeleton className="h-9 w-9 rounded-xl" />
        <Skeleton className="h-9 w-28 rounded-xl" />
      </div>
    </div>
    <div className="flex flex-1">
      <div className="hidden w-64 flex-shrink-0 space-y-2.5 border-r border-slate-200 bg-white p-4 dark:border-white/[0.07] dark:bg-ink-900 lg:block">
        {Array.from({ length: 5 }).map((_, i) => (
          <Skeleton key={i} className="h-11 w-full rounded-xl" style={{ opacity: 1 - i * 0.14 }} />
        ))}
      </div>
      <div className="flex-1 p-4 sm:p-6 lg:p-8">
        <DashboardSkeleton />
      </div>
    </div>
  </div>
)
