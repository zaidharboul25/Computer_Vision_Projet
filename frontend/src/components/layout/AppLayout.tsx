import React, { Suspense, useEffect, useState } from 'react'
import { Outlet, useLocation } from 'react-router-dom'
import { Header } from './Header'
import { Sidebar } from './Sidebar'
import { PageTransition } from '../ui/motion'
import { ListPageSkeleton } from '../ui/Skeleton'

export const AppLayout: React.FC = () => {
  const location = useLocation()
  const [menuOpen, setMenuOpen] = useState(false)

  useEffect(() => {
    setMenuOpen(false)
  }, [location.pathname])

  return (
    <div className="relative flex min-h-screen flex-col bg-slate-50 text-slate-900 dark:bg-ink-950 dark:text-slate-100">
      {/* Fond décoratif */}
      <div className="aurora" aria-hidden="true">
        <div className="aurora-blob -left-32 -top-32 h-96 w-96 bg-brand-400/40" />
        <div className="aurora-blob right-0 top-1/3 h-80 w-80 bg-cyan-400/25 [animation-delay:-8s]" />
        <div className="aurora-blob -bottom-24 left-1/3 h-72 w-72 bg-violet-400/25 [animation-delay:-15s]" />
      </div>

      <Header onMenuClick={() => setMenuOpen(true)} />
      <div className="relative flex flex-1">
        <Sidebar open={menuOpen} onClose={() => setMenuOpen(false)} />
        <main className="min-w-0 flex-1 p-4 sm:p-6 lg:p-8" id="main-content">
          <div className="mx-auto max-w-7xl">
            <PageTransition key={location.pathname}>
              <Suspense fallback={<ListPageSkeleton />}>
                <Outlet />
              </Suspense>
            </PageTransition>
          </div>
        </main>
      </div>
    </div>
  )
}
