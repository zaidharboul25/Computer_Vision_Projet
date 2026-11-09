import React, { useEffect, useState, useCallback } from 'react'
import { Link } from 'react-router-dom'
import {
  History,
  Search,
  Filter,
  RotateCcw,
  PlusCircle,
  ExternalLink,
  ChevronLeft,
  ChevronRight,
  AlertCircle,
  CheckCircle2,
  Clock,
  Layers,
  Sparkles,
} from 'lucide-react'
import { listInspections } from '../services/api'
import type { Inspection } from '../types'
import { LoadingSpinner } from '../components/common/LoadingSpinner'
import { ErrorAlert } from '../components/common/ErrorAlert'
import { useAuth } from '../context/AuthContext'

const PAGE_SIZE = 15

export const InspectionsListPage: React.FC = () => {
  const { hasRole } = useAuth()
  const [inspections, setInspections] = useState<Inspection[]>([])
  const [total, setTotal] = useState(0)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<unknown | null>(null)

  // Filtres
  const [page, setPage] = useState(0)
  const [statusFilter, setStatusFilter] = useState<string>('')
  const [reviewFilter, setReviewFilter] = useState<string>('')
  const [idFilter, setIdFilter] = useState<string>('')
  const [createdByFilter, setCreatedByFilter] = useState<string>('')

  const fetchInspections = useCallback(async () => {
    setLoading(true)
    setError(null)
    try {
      const data = await listInspections({
        skip: page * PAGE_SIZE,
        limit: PAGE_SIZE,
        status: statusFilter || undefined,
        review_status: reviewFilter || undefined,
        id_filter: idFilter.trim() || undefined,
        created_by: createdByFilter.trim() || undefined,
      })
      setInspections(data.items || [])
      setTotal(data.total || 0)
    } catch (err) {
      setError(err)
    } finally {
      setLoading(false)
    }
  }, [page, statusFilter, reviewFilter, idFilter, createdByFilter])

  useEffect(() => {
    fetchInspections()
  }, [fetchInspections])

  const handleResetFilters = () => {
    setStatusFilter('')
    setReviewFilter('')
    setIdFilter('')
    setCreatedByFilter('')
    setPage(0)
  }

  const totalPages = Math.ceil(total / PAGE_SIZE)

  const renderStatusBadge = (status: string) => {
    switch (status) {
      case 'done':
        return (
          <span className="inline-flex items-center gap-1.5 rounded-full bg-emerald-100 px-2.5 py-0.5 text-xs font-medium text-emerald-800 dark:bg-emerald-950/60 dark:text-emerald-300">
            <CheckCircle2 className="h-3.5 w-3.5 text-emerald-600 dark:text-emerald-400" />
            Terminée
          </span>
        )
      case 'running':
        return (
          <span className="inline-flex items-center gap-1.5 rounded-full bg-blue-100 px-2.5 py-0.5 text-xs font-medium text-blue-800 dark:bg-blue-950/60 dark:text-blue-300">
            <Clock className="h-3.5 w-3.5 animate-spin text-blue-600 dark:text-blue-400" />
            En cours
          </span>
        )
      case 'pending':
        return (
          <span className="inline-flex items-center gap-1.5 rounded-full bg-amber-100 px-2.5 py-0.5 text-xs font-medium text-amber-800 dark:bg-amber-950/60 dark:text-amber-300">
            <Clock className="h-3.5 w-3.5 text-amber-600 dark:text-amber-400" />
            En attente
          </span>
        )
      case 'error':
        return (
          <span className="inline-flex items-center gap-1.5 rounded-full bg-rose-100 px-2.5 py-0.5 text-xs font-medium text-rose-800 dark:bg-rose-950/60 dark:text-rose-300">
            <AlertCircle className="h-3.5 w-3.5 text-rose-600 dark:text-rose-400" />
            Erreur
          </span>
        )
      default:
        return (
          <span className="inline-flex items-center rounded-full bg-slate-100 px-2.5 py-0.5 text-xs font-medium text-slate-700 dark:bg-slate-800 dark:text-slate-300">
            {status}
          </span>
        )
    }
  }

  const renderReviewBadge = (insp: Inspection) => {
    const totalRegions = insp.regions_count ?? 0

    if (totalRegions === 0) {
      return (
        <span className="text-xs text-slate-400 dark:text-slate-500">
          Sans région
        </span>
      )
    }

    return (
      <span className="inline-flex items-center rounded-full bg-blue-50 px-2 py-0.5 text-xs font-medium text-blue-700 border border-blue-200 dark:bg-blue-950/40 dark:border-blue-800 dark:text-blue-300">
        {totalRegions} {totalRegions > 1 ? 'régions' : 'région'}
      </span>
    )
  }

  return (
    <div className="space-y-6">
      {/* En-tête */}
      <div className="flex flex-col justify-between gap-4 sm:flex-row sm:items-center">
        <div>
          <div className="flex items-center gap-2">
            <History className="h-6 w-6 text-blue-600 dark:text-blue-400" />
            <h1 className="text-2xl font-bold tracking-tight text-slate-900 dark:text-white">
              Historique des inspections
            </h1>
          </div>
          <p className="mt-1 text-sm text-slate-500 dark:text-slate-400">
            Consultation, recherche et traçabilité de toutes les inspections textiles soumises au système.
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

      {/* Barre de filtres */}
      <div className="rounded-xl border border-slate-200 bg-white p-4 shadow-sm dark:border-slate-800 dark:bg-slate-900">
        <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-5">
          {/* Recherche ID */}
          <div>
            <label htmlFor="filter-id" className="block text-xs font-medium text-slate-700 dark:text-slate-300">
              Identifiant inspection
            </label>
            <div className="relative mt-1">
              <input
                id="filter-id"
                type="text"
                placeholder="Ex: 662f..."
                value={idFilter}
                onChange={(e) => {
                  setIdFilter(e.target.value)
                  setPage(0)
                }}
                className="w-full rounded-lg border border-slate-300 bg-white py-1.5 pl-8 pr-3 text-sm text-slate-900 placeholder-slate-400 focus:border-blue-500 focus:outline-none focus:ring-1 focus:ring-blue-500 dark:border-slate-700 dark:bg-slate-800 dark:text-white"
              />
              <Search className="pointer-events-none absolute left-2.5 top-2.5 h-3.5 w-3.5 text-slate-400" />
            </div>
          </div>

          {/* Recherche Opérateur */}
          <div>
            <label htmlFor="filter-user" className="block text-xs font-medium text-slate-700 dark:text-slate-300">
              Opérateur
            </label>
            <div className="relative mt-1">
              <input
                id="filter-user"
                type="text"
                placeholder="Ex: operator1"
                value={createdByFilter}
                onChange={(e) => {
                  setCreatedByFilter(e.target.value)
                  setPage(0)
                }}
                className="w-full rounded-lg border border-slate-300 bg-white py-1.5 pl-8 pr-3 text-sm text-slate-900 placeholder-slate-400 focus:border-blue-500 focus:outline-none focus:ring-1 focus:ring-blue-500 dark:border-slate-700 dark:bg-slate-800 dark:text-white"
              />
              <Search className="pointer-events-none absolute left-2.5 top-2.5 h-3.5 w-3.5 text-slate-400" />
            </div>
          </div>

          {/* Statut d'inférence */}
          <div>
            <label htmlFor="filter-status" className="block text-xs font-medium text-slate-700 dark:text-slate-300">
              Statut d'inférence
            </label>
            <div className="relative mt-1">
              <select
                id="filter-status"
                value={statusFilter}
                onChange={(e) => {
                  setStatusFilter(e.target.value)
                  setPage(0)
                }}
                className="w-full rounded-lg border border-slate-300 bg-white py-1.5 pl-3 pr-8 text-sm text-slate-900 focus:border-blue-500 focus:outline-none focus:ring-1 focus:ring-blue-500 dark:border-slate-700 dark:bg-slate-800 dark:text-white"
              >
                <option value="">Tous les statuts</option>
                <option value="done">Terminée (done)</option>
                <option value="running">En cours (running)</option>
                <option value="pending">En attente (pending)</option>
                <option value="error">Erreur (error)</option>
              </select>
            </div>
          </div>

          {/* Statut de revue */}
          <div>
            <label htmlFor="filter-review" className="block text-xs font-medium text-slate-700 dark:text-slate-300">
              Statut de revue
            </label>
            <div className="relative mt-1">
              <select
                id="filter-review"
                value={reviewFilter}
                onChange={(e) => {
                  setReviewFilter(e.target.value)
                  setPage(0)
                }}
                className="w-full rounded-lg border border-slate-300 bg-white py-1.5 pl-3 pr-8 text-sm text-slate-900 focus:border-blue-500 focus:outline-none focus:ring-1 focus:ring-blue-500 dark:border-slate-700 dark:bg-slate-800 dark:text-white"
              >
                <option value="">Toutes les revues</option>
                <option value="unreviewed">À réviser</option>
                <option value="reviewed">Complétées</option>
              </select>
            </div>
          </div>

          {/* Bouton Réinitialiser */}
          <div className="flex items-end">
            <button
              type="button"
              onClick={handleResetFilters}
              className="inline-flex w-full items-center justify-center gap-2 rounded-lg border border-slate-300 bg-slate-50 px-3 py-1.5 text-sm font-medium text-slate-700 hover:bg-slate-100 focus:outline-none focus:ring-2 focus:ring-slate-400 dark:border-slate-700 dark:bg-slate-800 dark:text-slate-300 dark:hover:bg-slate-700"
            >
              <RotateCcw className="h-4 w-4" />
              Réinitialiser
            </button>
          </div>
        </div>
      </div>

      {/* Message d'erreur */}
      {error ? <ErrorAlert error={error} /> : null}

      {/* Tableau des inspections */}
      <div className="rounded-xl border border-slate-200 bg-white shadow-sm dark:border-slate-800 dark:bg-slate-900 overflow-hidden">
        {loading ? (
          <div className="py-16">
            <LoadingSpinner label="Chargement de l'historique des inspections..." />
          </div>
        ) : inspections.length === 0 ? (
          <div className="py-16 text-center">
            <Filter className="mx-auto h-10 w-10 text-slate-400" />
            <h3 className="mt-3 text-base font-semibold text-slate-900 dark:text-white">
              Aucune inspection trouvée
            </h3>
            <p className="mt-1 text-sm text-slate-500 dark:text-slate-400">
              Aucune inspection ne correspond aux critères de filtre sélectionnés.
            </p>
            {(statusFilter || reviewFilter || idFilter || createdByFilter) && (
              <button
                type="button"
                onClick={handleResetFilters}
                className="mt-4 inline-flex items-center gap-1.5 text-sm font-medium text-blue-600 hover:text-blue-500 dark:text-blue-400"
              >
                <RotateCcw className="h-3.5 w-3.5" />
                Effacer les filtres
              </button>
            )}
          </div>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full text-left text-sm text-slate-600 dark:text-slate-300">
              <thead className="border-b border-slate-200 bg-slate-50 text-xs uppercase tracking-wider text-slate-500 dark:border-slate-800 dark:bg-slate-800/50 dark:text-slate-400">
                <tr>
                  <th scope="col" className="px-5 py-3.5 font-semibold">Identifiant</th>
                  <th scope="col" className="px-5 py-3.5 font-semibold">Date de soumission</th>
                  <th scope="col" className="px-5 py-3.5 font-semibold">Opérateur</th>
                  <th scope="col" className="px-5 py-3.5 font-semibold">Statut</th>
                  <th scope="col" className="px-5 py-3.5 font-semibold">Moteurs</th>
                  <th scope="col" className="px-5 py-3.5 font-semibold">Régions</th>
                  <th scope="col" className="px-5 py-3.5 font-semibold">Revue</th>
                  <th scope="col" className="px-5 py-3.5 text-right font-semibold">Action</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-200 dark:divide-slate-800">
                {inspections.map((insp) => {
                  const engineNames = Object.keys(insp.engines || {})
                  return (
                    <tr
                      key={insp.id}
                      className="hover:bg-slate-50/80 transition-colors dark:hover:bg-slate-800/40"
                    >
                      {/* ID */}
                      <td className="px-5 py-3.5">
                        <Link
                          to={`/inspections/${insp.id}`}
                          className="font-mono text-xs font-medium text-blue-600 hover:underline dark:text-blue-400"
                          title={insp.id}
                        >
                          {insp.id.length > 12 ? `${insp.id.slice(0, 10)}…` : insp.id}
                        </Link>
                      </td>

                      {/* Date */}
                      <td className="px-5 py-3.5 text-xs text-slate-500 dark:text-slate-400">
                        {new Date(insp.created_at).toLocaleString('fr-FR', {
                          day: '2-digit',
                          month: 'short',
                          year: 'numeric',
                          hour: '2-digit',
                          minute: '2-digit',
                        })}
                      </td>

                      {/* Opérateur */}
                      <td className="px-5 py-3.5 font-medium text-slate-800 dark:text-slate-200">
                        {insp.created_by}
                      </td>

                      {/* Statut */}
                      <td className="px-5 py-3.5">
                        {renderStatusBadge(insp.status)}
                      </td>

                      {/* Moteurs */}
                      <td className="px-5 py-3.5">
                        <div className="flex flex-wrap items-center gap-1">
                          {engineNames.map((eng) => (
                            <span
                              key={eng}
                              className={`inline-flex items-center gap-1 rounded px-1.5 py-0.5 text-[11px] font-medium ${
                                eng === 'yolo'
                                  ? 'bg-blue-50 text-blue-700 dark:bg-blue-950/40 dark:text-blue-300'
                                  : eng === 'patchcore'
                                  ? 'bg-purple-50 text-purple-700 dark:bg-purple-950/40 dark:text-purple-300'
                                  : 'bg-slate-100 text-slate-700 dark:bg-slate-800 dark:text-slate-300'
                              }`}
                            >
                              {eng === 'yolo' ? (
                                <Layers className="h-3 w-3" />
                              ) : eng === 'patchcore' ? (
                                <Sparkles className="h-3 w-3" />
                              ) : null}
                              {eng}
                            </span>
                          ))}
                        </div>
                      </td>

                      {/* Régions */}
                      <td className="px-5 py-3.5 font-medium text-slate-900 dark:text-white">
                        {insp.regions_count ?? 0}
                      </td>

                      {/* Revue */}
                      <td className="px-5 py-3.5">
                        {renderReviewBadge(insp)}
                      </td>

                      {/* Action */}
                      <td className="px-5 py-3.5 text-right">
                        <Link
                          to={`/inspections/${insp.id}`}
                          className="inline-flex items-center gap-1.5 rounded-lg border border-slate-200 bg-white px-2.5 py-1 text-xs font-medium text-slate-700 shadow-sm hover:bg-slate-50 focus:outline-none focus:ring-2 focus:ring-blue-500 dark:border-slate-700 dark:bg-slate-800 dark:text-slate-200 dark:hover:bg-slate-700"
                        >
                          Consulter
                          <ExternalLink className="h-3 w-3" />
                        </Link>
                      </td>
                    </tr>
                  )
                })}
              </tbody>
            </table>
          </div>
        )}

        {/* Pied de tableau / Pagination */}
        {!loading && total > 0 && (
          <div className="flex flex-col items-center justify-between gap-3 border-t border-slate-200 bg-slate-50/50 px-5 py-3 text-sm text-slate-500 sm:flex-row dark:border-slate-800 dark:bg-slate-800/30 dark:text-slate-400">
            <div>
              Affichage de{' '}
              <span className="font-semibold text-slate-800 dark:text-slate-200">
                {page * PAGE_SIZE + 1}
              </span>{' '}
              à{' '}
              <span className="font-semibold text-slate-800 dark:text-slate-200">
                {Math.min((page + 1) * PAGE_SIZE, total)}
              </span>{' '}
              sur{' '}
              <span className="font-semibold text-slate-800 dark:text-slate-200">{total}</span>{' '}
              inspections
            </div>

            <div className="flex items-center gap-2">
              <button
                type="button"
                onClick={() => setPage((p) => Math.max(p - 1, 0))}
                disabled={page === 0}
                className="inline-flex items-center gap-1 rounded-lg border border-slate-200 bg-white px-3 py-1 text-xs font-medium text-slate-700 shadow-sm hover:bg-slate-50 disabled:opacity-40 disabled:cursor-not-allowed dark:border-slate-700 dark:bg-slate-800 dark:text-slate-300 dark:hover:bg-slate-700"
              >
                <ChevronLeft className="h-4 w-4" />
                Précédent
              </button>

              <span className="text-xs font-medium">
                Page {page + 1} sur {totalPages || 1}
              </span>

              <button
                type="button"
                onClick={() => setPage((p) => Math.min(p + 1, totalPages - 1))}
                disabled={page >= totalPages - 1}
                className="inline-flex items-center gap-1 rounded-lg border border-slate-200 bg-white px-3 py-1 text-xs font-medium text-slate-700 shadow-sm hover:bg-slate-50 disabled:opacity-40 disabled:cursor-not-allowed dark:border-slate-700 dark:bg-slate-800 dark:text-slate-300 dark:hover:bg-slate-700"
              >
                Suivant
                <ChevronRight className="h-4 w-4" />
              </button>
            </div>
          </div>
        )}
      </div>
    </div>
  )
}
