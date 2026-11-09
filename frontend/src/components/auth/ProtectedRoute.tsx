import React from 'react'
import { Navigate, useLocation } from 'react-router-dom'
import { useAuth } from '../../context/AuthContext'
import type { UserRole } from '../../types'
import { LoadingSpinner } from '../common/LoadingSpinner'
import { ShieldX } from 'lucide-react'

interface ProtectedRouteProps {
  children: React.ReactNode
  allowedRoles?: UserRole[]
}

export const ProtectedRoute: React.FC<ProtectedRouteProps> = ({ children, allowedRoles }) => {
  const { user, isLoading, hasRole } = useAuth()
  const location = useLocation()

  if (isLoading) {
    return (
      <div className="flex h-screen items-center justify-center">
        <LoadingSpinner label="Vérification de la session..." size="lg" />
      </div>
    )
  }

  if (!user) {
    return <Navigate to="/login" state={{ from: location }} replace />
  }

  if (allowedRoles && !hasRole(allowedRoles)) {
    return (
      <div className="flex flex-col items-center justify-center p-12 text-center" role="alert">
        <div className="flex h-16 w-16 items-center justify-center rounded-full bg-rose-100 text-rose-600 dark:bg-rose-950/60 dark:text-rose-400">
          <ShieldX className="h-8 w-8" />
        </div>
        <h2 className="mt-4 text-xl font-bold tracking-tight text-slate-900 dark:text-white">
          Accès non autorisé
        </h2>
        <p className="mt-2 max-w-md text-sm text-slate-600 dark:text-slate-400">
          Votre compte (rôle : <span className="font-semibold">{user.role}</span>) ne dispose pas des privilèges nécessaires pour accéder à cet écran.
        </p>
        <div className="mt-6">
          <a
            href="/"
            className="rounded-lg bg-blue-600 px-4 py-2 text-sm font-semibold text-white shadow-sm hover:bg-blue-500 focus:outline-none focus:ring-2 focus:ring-blue-500"
          >
            Retourner au tableau de bord
          </a>
        </div>
      </div>
    )
  }

  return <>{children}</>
}

