import React from 'react'
import { Navigate, useLocation, Link } from 'react-router-dom'
import { motion } from 'framer-motion'
import { useAuth } from '../../context/AuthContext'
import type { UserRole } from '../../types'
import { AppShellSkeleton } from '../ui/Skeleton'
import { ShieldX, ArrowLeft } from 'lucide-react'

interface ProtectedRouteProps {
  children: React.ReactNode
  allowedRoles?: UserRole[]
}

export const ProtectedRoute: React.FC<ProtectedRouteProps> = ({ children, allowedRoles }) => {
  const { user, isLoading, hasRole } = useAuth()
  const location = useLocation()

  if (isLoading) {
    return <AppShellSkeleton />
  }

  if (!user) {
    return <Navigate to="/login" state={{ from: location }} replace />
  }

  if (allowedRoles && !hasRole(allowedRoles)) {
    return (
      <motion.div
        initial={{ opacity: 0, scale: 0.96 }}
        animate={{ opacity: 1, scale: 1 }}
        transition={{ duration: 0.4 }}
        className="mx-auto flex max-w-lg flex-col items-center justify-center p-12 text-center"
        role="alert"
      >
        <div className="relative">
          <span className="absolute inset-0 animate-pulse-ring rounded-full bg-rose-500/30" aria-hidden="true" />
          <div className="relative flex h-20 w-20 items-center justify-center rounded-full bg-rose-100 text-rose-600 dark:bg-rose-950/60 dark:text-rose-400">
            <ShieldX className="h-9 w-9" />
          </div>
        </div>
        <h2 className="mt-6 text-2xl font-bold tracking-tight text-slate-900 dark:text-white">Accès non autorisé</h2>
        <p className="mt-2 max-w-md text-sm text-slate-600 dark:text-slate-400">
          Votre compte (rôle : <span className="font-semibold">{user.role}</span>) ne dispose pas des privilèges nécessaires pour accéder à cet écran.
        </p>
        <div className="mt-6">
          <Link to="/" className="btn-primary">
            <ArrowLeft className="h-4 w-4" />
            Retourner au tableau de bord
          </Link>
        </div>
      </motion.div>
    )
  }

  return <>{children}</>
}
