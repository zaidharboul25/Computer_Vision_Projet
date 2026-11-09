import React, { useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import { useAuth } from '../context/AuthContext'
import { RoleBadge } from '../components/common/RoleBadge'
import { PlusCircle, History, Sparkles, Activity, FileCheck, Layers } from 'lucide-react'
import { apiFetch } from '../services/api'
import type { SummaryStats } from '../types'
import { LoadingSpinner } from '../components/common/LoadingSpinner'

export const DashboardPlaceholder: React.FC = () => {
  const { user, hasRole } = useAuth()
  const [stats, setStats] = useState<SummaryStats | null>(null)
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    apiFetch<SummaryStats>('/api/v1/stats/summary')
      .then((data) => setStats(data))
      .catch(() => setStats(null))
      .finally(() => setLoading(false))
  }, [])

  return (
    <div className="space-y-6">
      <div className="flex flex-col justify-between gap-4 sm:flex-row sm:items-center">
        <div>
          <h1 className="text-2xl font-bold tracking-tight text-slate-900 dark:text-white">
            Tableau de bord WeaveGuard AI
          </h1>
          <p className="mt-1 text-sm text-slate-500 dark:text-slate-400">
            Bienvenue, <span className="font-semibold text-slate-800 dark:text-slate-200">{user?.username}</span>{' '}
            {user && <RoleBadge role={user.role} className="ml-1" />}
          </p>
        </div>

        {hasRole(['operator', 'supervisor', 'admin']) && (
          <Link
            to="/inspections/new"
            className="inline-flex items-center gap-2 rounded-lg bg-blue-600 px-4 py-2.5 text-sm font-semibold text-white shadow-sm hover:bg-blue-500 focus:outline-none focus:ring-2 focus:ring-blue-500"
          >
            <PlusCircle className="h-4 w-4" />
            Nouvelle inspection
          </Link>
        )}
      </div>

      {loading ? (
        <LoadingSpinner label="Chargement des indicateurs..." />
      ) : stats ? (
        <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-4">
          <div className="rounded-xl border border-slate-200 bg-white p-5 shadow-sm dark:border-slate-800 dark:bg-slate-900">
            <div className="flex items-center justify-between">
              <span className="text-xs font-semibold uppercase tracking-wider text-slate-500 dark:text-slate-400">
                Inspections totales
              </span>
              <Activity className="h-5 w-5 text-blue-600 dark:text-blue-400" />
            </div>
            <div className="mt-3 text-3xl font-extrabold text-slate-900 dark:text-white">
              {stats.inspections.total}
            </div>
            <div className="mt-1 text-xs text-slate-500 dark:text-slate-400">
              {stats.inspections.done} terminées · {stats.inspections.pending} en attente
            </div>
          </div>

          <div className="rounded-xl border border-slate-200 bg-white p-5 shadow-sm dark:border-slate-800 dark:bg-slate-900">
            <div className="flex items-center justify-between">
              <span className="text-xs font-semibold uppercase tracking-wider text-slate-500 dark:text-slate-400">
                Défauts YOLO
              </span>
              <Layers className="h-5 w-5 text-blue-600 dark:text-blue-400" />
            </div>
            <div className="mt-3 text-3xl font-extrabold text-slate-900 dark:text-white">
              {stats.regions.yolo}
            </div>
            <div className="mt-1 text-xs text-slate-500 dark:text-slate-400">
              Détections supervisées
            </div>
          </div>

          <div className="rounded-xl border border-slate-200 bg-white p-5 shadow-sm dark:border-slate-800 dark:bg-slate-900">
            <div className="flex items-center justify-between">
              <span className="text-xs font-semibold uppercase tracking-wider text-slate-500 dark:text-slate-400">
                Anomalies PatchCore
              </span>
              <Sparkles className="h-5 w-5 text-purple-600 dark:text-purple-400" />
            </div>
            <div className="mt-3 text-3xl font-extrabold text-slate-900 dark:text-white">
              {stats.regions.patchcore}
            </div>
            <div className="mt-1 text-xs text-slate-500 dark:text-slate-400">
              Régions hors distribution
            </div>
          </div>

          <div className="rounded-xl border border-slate-200 bg-white p-5 shadow-sm dark:border-slate-800 dark:bg-slate-900">
            <div className="flex items-center justify-between">
              <span className="text-xs font-semibold uppercase tracking-wider text-slate-500 dark:text-slate-400">
                Revues confirmées
              </span>
              <FileCheck className="h-5 w-5 text-emerald-600 dark:text-emerald-400" />
            </div>
            <div className="mt-3 text-3xl font-extrabold text-slate-900 dark:text-white">
              {stats.reviews.confirmed}
            </div>
            <div className="mt-1 text-xs text-slate-500 dark:text-slate-400">
              {stats.reviews.rejected} rejetées · {stats.reviews.unreviewed} à réviser
            </div>
          </div>
        </div>
      ) : null}

      <div className="rounded-xl border border-slate-200 bg-white p-6 shadow-sm dark:border-slate-800 dark:bg-slate-900">
        <h2 className="text-base font-bold text-slate-900 dark:text-white">Accès rapide</h2>
        <div className="mt-4 grid grid-cols-1 gap-3 sm:grid-cols-3">
          <Link
            to="/inspections"
            className="flex items-center gap-3 rounded-lg border border-slate-200 p-3 hover:bg-slate-50 dark:border-slate-800 dark:hover:bg-slate-800/60"
          >
            <History className="h-5 w-5 text-blue-600" />
            <div>
              <div className="text-sm font-semibold text-slate-800 dark:text-slate-200">Consulter l'historique</div>
              <div className="text-xs text-slate-500">Filtrer par statut, utilisateur et date</div>
            </div>
          </Link>
          <Link
            to="/similarity"
            className="flex items-center gap-3 rounded-lg border border-slate-200 p-3 hover:bg-slate-50 dark:border-slate-800 dark:hover:bg-slate-800/60"
          >
            <Sparkles className="h-5 w-5 text-purple-600" />
            <div>
              <div className="text-sm font-semibold text-slate-800 dark:text-slate-200">Recherche de similarité</div>
              <div className="text-xs text-slate-500">Galeries textile et DTD générique</div>
            </div>
          </Link>
          <Link
            to="/models"
            className="flex items-center gap-3 rounded-lg border border-slate-200 p-3 hover:bg-slate-50 dark:border-slate-800 dark:hover:bg-slate-800/60"
          >
            <Activity className="h-5 w-5 text-emerald-600" />
            <div>
              <div className="text-sm font-semibold text-slate-800 dark:text-slate-200">Fiches modèles IA</div>
              <div className="text-xs text-slate-500">Métriques validées et biais de domaine</div>
            </div>
          </Link>
        </div>
      </div>
    </div>
  )
}
