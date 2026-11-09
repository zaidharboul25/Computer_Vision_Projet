import React, { useState } from 'react'
import { useParams, Link } from 'react-router-dom'
import { useQuery } from '@tanstack/react-query'
import { getInspection, getInspectionRegions, apiFetchBlob, triggerBlobDownload } from '../services/api'
import { useAuthedBlob } from '../hooks/useAuthedBlob'
import { ErrorAlert } from '../components/common/ErrorAlert'
import { LoadingSpinner } from '../components/common/LoadingSpinner'
import { DemoBadge } from '../components/common/DemoBadge'
import type { EngineProgress } from '../types'

export const InspectionResultPage: React.FC = () => {
  const { id } = useParams<{ id: string }>()
  const inspectionId = id || ''

  const [activeTab, setActiveTab] = useState<'overlay' | 'image' | 'heatmap'>('overlay')
  const [downloadingExport, setDownloadingExport] = useState(false)
  const [downloadingOverlay, setDownloadingOverlay] = useState(false)
  const [actionError, setActionError] = useState<unknown>(null)

  // Polling tant que l'inspection n'est pas achevée (pending ou running)
  const {
    data: inspection,
    isLoading: inspectionLoading,
    error: inspectionError,
  } = useQuery({
    queryKey: ['inspection', inspectionId],
    queryFn: () => getInspection(inspectionId),
    enabled: Boolean(inspectionId),
    refetchInterval: (query) => {
      const status = query.state.data?.status
      return status === 'pending' || status === 'running' ? 1000 : false
    },
  })

  // Récupération des régions si l'inspection est terminée
  const isDone = inspection?.status === 'done'
  const {
    data: regionsData,
    isLoading: regionsLoading,
  } = useQuery({
    queryKey: ['inspection-regions', inspectionId],
    queryFn: () => getInspectionRegions(inspectionId),
    enabled: isDone && Boolean(inspectionId),
  })

  // Chargement des blobs sécurisés (Authorization: Bearer) pour l'affichage
  const imageUrl = inspectionId ? `/api/v1/inspections/${inspectionId}/image` : ''
  const heatmapUrl = inspection?.heatmap_meta && inspectionId ? `/api/v1/inspections/${inspectionId}/heatmap` : ''
  const overlayUrl = inspectionId ? `/api/v1/inspections/${inspectionId}/overlay?format=png` : ''

  const imageBlob = useAuthedBlob(activeTab === 'image' ? imageUrl : '')
  const heatmapBlob = useAuthedBlob(activeTab === 'heatmap' ? heatmapUrl : '')
  const overlayBlob = useAuthedBlob(activeTab === 'overlay' && isDone ? overlayUrl : '')

  const handleDownloadExport = async () => {
    if (!inspectionId) return
    setDownloadingExport(true)
    setActionError(null)
    try {
      const blob = await apiFetchBlob(`/api/v1/inspections/${inspectionId}/export`)
      triggerBlobDownload(blob, `weaveguard_inspection_${inspectionId}.json`)
    } catch (err) {
      setActionError(err)
    } finally {
      setDownloadingExport(false)
    }
  }

  const handleDownloadOverlay = async () => {
    if (!inspectionId) return
    setDownloadingOverlay(true)
    setActionError(null)
    try {
      const blob = await apiFetchBlob(`/api/v1/inspections/${inspectionId}/overlay?format=png`)
      triggerBlobDownload(blob, `weaveguard_overlay_${inspectionId}.png`)
    } catch (err) {
      setActionError(err)
    } finally {
      setDownloadingOverlay(false)
    }
  }

  if (inspectionLoading) {
    return (
      <div className="flex min-h-[300px] flex-col items-center justify-center gap-3">
        <LoadingSpinner size="lg" />
        <p className="text-sm text-slate-500 dark:text-slate-400">Chargement de l'inspection...</p>
      </div>
    )
  }

  if (inspectionError || !inspection) {
    return (
      <div className="space-y-4">
        <ErrorAlert error={inspectionError || new Error("Impossible de charger l'inspection demandée.")} />
        <Link
          to="/"
          className="inline-flex items-center gap-2 rounded-lg border border-slate-300 px-4 py-2 text-sm font-medium hover:bg-slate-50 dark:border-slate-700"
        >
          Retour au tableau de bord
        </Link>
      </div>
    )
  }

  const isPendingOrRunning = inspection.status === 'pending' || inspection.status === 'running'
  const isFailed = inspection.status === 'error'
  const regions = regionsData?.items || []
  const yoloCount = regions.filter((r) => r.engine === 'yolo').length
  const patchcoreCount = regions.filter((r) => r.engine === 'patchcore').length

  const getStatusBadge = () => {
    switch (inspection.status) {
      case 'pending':
        return <span className="rounded-full bg-amber-100 px-3 py-1 text-xs font-semibold text-amber-800 dark:bg-amber-900/50 dark:text-amber-200">En attente</span>
      case 'running':
        return (
          <span className="flex items-center gap-1.5 rounded-full bg-blue-100 px-3 py-1 text-xs font-semibold text-blue-800 dark:bg-blue-900/50 dark:text-blue-200">
            <LoadingSpinner size="sm" /> Traitement en cours...
          </span>
        )
      case 'done':
        return <span className="rounded-full bg-emerald-100 px-3 py-1 text-xs font-semibold text-emerald-800 dark:bg-emerald-900/50 dark:text-emerald-200">Terminé</span>
      case 'error':
        return <span className="rounded-full bg-rose-100 px-3 py-1 text-xs font-semibold text-rose-800 dark:bg-rose-900/50 dark:text-rose-200">Échec</span>
    }
  }

  return (
    <div className="space-y-6">
      {/* En-tête de l'inspection */}
      <div className="flex flex-col gap-4 sm:flex-row sm:items-center sm:justify-between">
        <div>
          <div className="flex flex-wrap items-center gap-3">
            <h1 className="text-2xl font-bold tracking-tight text-slate-900 dark:text-slate-100">
              Inspection #{inspection.id.substring(0, 8)}
            </h1>
            {getStatusBadge()}
            {inspection.is_demo && <DemoBadge />}
          </div>
          <p className="mt-1 text-sm text-slate-500 dark:text-slate-400">
            Cliché {inspection.image_meta.filename} ({inspection.image_meta.stored_width} × {inspection.image_meta.stored_height} px) • Soumis par {inspection.created_by} le {new Date(inspection.created_at).toLocaleString('fr-FR')}
          </p>
        </div>

        {/* Actions d'export */}
        <div className="flex flex-wrap items-center gap-2">
          {isDone && (
            <>
              <button
                type="button"
                onClick={handleDownloadExport}
                disabled={downloadingExport}
                className="inline-flex items-center gap-1.5 rounded-lg border border-slate-300 bg-white px-3 py-1.5 text-xs font-medium text-slate-700 shadow-sm hover:bg-slate-50 disabled:opacity-50 dark:border-slate-700 dark:bg-slate-800 dark:text-slate-200"
              >
                {downloadingExport ? <LoadingSpinner size="sm" /> : (
                  <svg className="h-4 w-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M4 16v1a3 3 0 003 3h10a3 3 0 003-3v-1m-4-4l-4 4m0 0l-4-4m4 4V4" />
                  </svg>
                )}
                Export JSON (AC-04)
              </button>
              <button
                type="button"
                onClick={handleDownloadOverlay}
                disabled={downloadingOverlay}
                className="inline-flex items-center gap-1.5 rounded-lg border border-slate-300 bg-white px-3 py-1.5 text-xs font-medium text-slate-700 shadow-sm hover:bg-slate-50 disabled:opacity-50 dark:border-slate-700 dark:bg-slate-800 dark:text-slate-200"
              >
                {downloadingOverlay ? <LoadingSpinner size="sm" /> : (
                  <svg className="h-4 w-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M4 16v1a3 3 0 003 3h10a3 3 0 003-3v-1m-4-4l-4 4m0 0l-4-4m4 4V4" />
                  </svg>
                )}
                Overlay PNG
              </button>
            </>
          )}
          <Link
            to="/inspections/new"
            className="inline-flex items-center gap-1.5 rounded-lg bg-indigo-600 px-3.5 py-1.5 text-xs font-semibold text-white shadow-sm hover:bg-indigo-700"
          >
            Nouvelle analyse
          </Link>
        </div>
      </div>

      {Boolean(actionError) && <ErrorAlert error={actionError} />}

      {/* Avertissement résultat partiel */}
      {inspection.partial && (
        <div
          role="alert"
          className="flex items-start gap-3 rounded-xl border border-amber-300 bg-amber-50 p-4 text-amber-900 shadow-sm dark:border-amber-900/60 dark:bg-amber-950/40 dark:text-amber-200"
        >
          <svg className="mt-0.5 h-5 w-5 flex-shrink-0 text-amber-600 dark:text-amber-400" fill="none" viewBox="0 0 24 24" stroke="currentColor">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-3L13.732 4c-.77-1.333-2.694-1.333-3.464 0L3.34 16c-.77 1.333.192 3 1.732 3z" />
          </svg>
          <div>
            <h3 className="text-sm font-semibold">Résultat partiel</h3>
            <p className="mt-0.5 text-xs">
              Un ou plusieurs moteurs d'analyse ont échoué lors de cette exécution. Les résultats produits par les moteurs restants sont affichés ci-dessous.
            </p>
          </div>
        </div>
      )}

      {/* Échec global */}
      {isFailed && (
        <div
          role="alert"
          className="rounded-xl border border-rose-300 bg-rose-50 p-6 text-rose-900 shadow-sm dark:border-rose-900 dark:bg-rose-950/40 dark:text-rose-200"
        >
          <div className="flex items-center gap-3">
            <svg className="h-6 w-6 text-rose-600 dark:text-rose-400" fill="none" viewBox="0 0 24 24" stroke="currentColor">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M10 14l2-2m0 0l2-2m-2 2l-2-2m2 2l2 2m7-2a9 9 0 11-18 0 9 9 0 0118 0z" />
            </svg>
            <div>
              <h3 className="font-semibold">L'inspection a échoué</h3>
              <p className="mt-1 text-sm text-rose-700 dark:text-rose-300">
                {inspection.error_message || "Une erreur inattendue est survenue pendant le traitement de l'image."}
              </p>
            </div>
          </div>
        </div>
      )}

      {/* Avertissements d'analyse et Biais de Domaine (ADR-24) */}
      {((inspection.warnings && inspection.warnings.length > 0) || inspection.domain_check?.status === 'below_range') && (
        <div
          role="region"
          aria-label="Avertissements de fiabilité et représentativité"
          className="rounded-xl border border-amber-300 bg-amber-50/90 p-4 shadow-sm dark:border-amber-700/60 dark:bg-amber-950/30"
        >
          <div className="flex items-start gap-3">
            <div className="mt-0.5 rounded-lg bg-amber-100 p-1.5 text-amber-800 dark:bg-amber-900/60 dark:text-amber-300">
              <svg className="h-5 w-5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-3L13.732 4c-.77-1.333-2.694-1.333-3.464 0L3.34 16c-.77 1.333.192 3 1.732 3z" />
              </svg>
            </div>
            <div className="flex-1">
              <div className="flex flex-wrap items-center gap-2">
                <h3 className="text-sm font-semibold text-amber-950 dark:text-amber-200">
                  Avertissement de fiabilité (Image hors domaine ou atypique)
                </h3>
                {inspection.domain_check && (
                  <span className="rounded bg-amber-200/80 px-2 py-0.5 text-xs font-medium text-amber-900 dark:bg-amber-900 dark:text-amber-200">
                    Similarité max : {inspection.domain_check.max_similarity ?? 'N/A'} (seuil min : {inspection.domain_check.reference_min})
                  </span>
                )}
                {inspection.image_meta?.scale_mode && (
                  <span className="rounded bg-slate-200/80 px-2 py-0.5 text-xs font-medium text-slate-800 dark:bg-slate-800 dark:text-slate-200">
                    Mode d'échelle : {inspection.image_meta.scale_mode}
                  </span>
                )}
              </div>

              <ul className="mt-2 space-y-1 text-xs text-amber-900 dark:text-amber-300">
                {(inspection.warnings || []).map((w, idx) => (
                  <li key={idx} className="flex items-start gap-1.5">
                    <span className="text-amber-600 dark:text-amber-400">•</span>
                    <span>{w}</span>
                  </li>
                ))}
              </ul>

              <p className="mt-2 text-xs italic text-amber-800/80 dark:text-amber-400/80">
                Aide à l'interprétation : ces avertissements signalent un textile éloigné de la distribution d'apprentissage (ex : tricot, maille lâche, faible résolution). La décision finale revient à l'opérateur.
              </p>
            </div>
          </div>
        </div>
      )}

      {/* Progression et statut des moteurs (aria-live) */}
      <div
        aria-live="polite"
        className="rounded-xl border border-slate-200 bg-white p-5 shadow-sm dark:border-slate-800 dark:bg-slate-900"
      >
        <h2 className="text-sm font-semibold text-slate-900 dark:text-slate-100 mb-3">
          Progression et télémétrie des moteurs
        </h2>

        <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
          {Object.entries(inspection.engines).map(([engineName, progressRaw]) => {
            const progress = progressRaw as EngineProgress
            const displayName =
              engineName === 'yolo'
                ? 'YOLOv11 (Supervisé)'
                : engineName === 'patchcore'
                ? 'PatchCore (Anomalies)'
                : engineName === 'similarity'
                ? 'Similarité DTD'
                : engineName

            const latencyDict = progress.latency_ms as Record<string, number> | undefined
            const totalLatency = latencyDict ? Math.round(latencyDict.total ?? latencyDict.total_ms ?? 0) : null

            return (
              <div
                key={engineName}
                data-testid={`engine-card-${engineName}`}
                className="flex flex-col justify-between rounded-lg border border-slate-200 p-3.5 dark:border-slate-800 dark:bg-slate-950/50"
              >
                <div className="flex items-center justify-between">
                  <span className="font-medium text-slate-800 dark:text-slate-200">{displayName}</span>
                  {progress.status === 'ok' && (
                    <span className="inline-flex items-center gap-1 rounded bg-emerald-100 px-2 py-0.5 text-xs font-semibold text-emerald-800 dark:bg-emerald-950 dark:text-emerald-300">
                      ✓ Terminé
                    </span>
                  )}
                  {progress.status === 'running' && (
                    <span className="inline-flex items-center gap-1 rounded bg-blue-100 px-2 py-0.5 text-xs font-semibold text-blue-800 dark:bg-blue-950 dark:text-blue-300">
                      <LoadingSpinner size="sm" /> Inférence
                    </span>
                  )}
                  {progress.status === 'pending' && (
                    <span className="rounded bg-slate-100 px-2 py-0.5 text-xs font-medium text-slate-600 dark:bg-slate-800 dark:text-slate-400">
                      En attente
                    </span>
                  )}
                  {progress.status === 'error' && (
                    <span className="rounded bg-rose-100 px-2 py-0.5 text-xs font-semibold text-rose-800 dark:bg-rose-950 dark:text-rose-300">
                      ✕ Échec
                    </span>
                  )}
                  {progress.status === 'skipped' && (
                    <span className="rounded bg-slate-100 px-2 py-0.5 text-xs font-medium text-slate-500 dark:bg-slate-800 dark:text-slate-400">
                      Ignoré
                    </span>
                  )}
                </div>

                <div className="mt-3 text-xs text-slate-500 dark:text-slate-400">
                  {totalLatency !== null && (
                    <p>
                      Latence totale : <strong className="text-slate-700 dark:text-slate-300">{totalLatency} ms</strong>
                    </p>
                  )}
                  {progress.version && (
                    <p className="mt-0.5 font-mono text-[11px] text-slate-400">
                      Artefact : {progress.version.substring(0, 12)}
                    </p>
                  )}
                  {progress.error && (
                    <p className="mt-1 font-semibold text-rose-600 dark:text-rose-400">
                      {progress.error}
                    </p>
                  )}
                </div>
              </div>
            )
          })}
        </div>
      </div>

      {/* Traitement en cours : indicateur global */}
      {isPendingOrRunning && (
        <div className="rounded-xl border border-blue-200 bg-blue-50/50 p-8 text-center dark:border-blue-950 dark:bg-blue-950/20">
          <div className="flex flex-col items-center gap-3">
            <LoadingSpinner size="lg" />
            <h3 className="text-base font-semibold text-slate-800 dark:text-slate-200">
              Analyse automatique en cours
            </h3>
            <p className="max-w-md text-xs text-slate-500 dark:text-slate-400">
              L'inférence s'exécute de façon séquentielle sur le serveur. Cette page se met à jour automatiquement dès l'achèvement.
            </p>
          </div>
        </div>
      )}

      {/* État "Aucune région" (Spécification contractuelle stricte) */}
      {isDone && inspection.regions_count === 0 && (
        <div
          data-testid="no-regions-card"
          className="rounded-xl border border-slate-200 bg-white p-8 text-center shadow-sm dark:border-slate-800 dark:bg-slate-900"
        >
          <div className="mx-auto flex h-14 w-14 items-center justify-center rounded-full bg-emerald-100 text-emerald-600 dark:bg-emerald-950 dark:text-emerald-400">
            <svg className="h-7 w-7" fill="none" viewBox="0 0 24 24" stroke="currentColor">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M5 13l4 4L19 7" />
            </svg>
          </div>
          <h2 className="mt-4 text-lg font-bold text-slate-900 dark:text-slate-100">
            Aucune région détectée par les moteurs exécutés
          </h2>
          <p className="mt-1 text-sm text-slate-500 dark:text-slate-400">
            Ce résultat n'est pas une garantie d'absence de défaut
          </p>

          <div className="mt-6 flex justify-center gap-3">
            <Link
              to="/inspections/new"
              className="rounded-lg bg-indigo-600 px-4 py-2 text-sm font-semibold text-white shadow hover:bg-indigo-700"
            >
              Lancer une autre analyse
            </Link>
          </div>
        </div>
      )}

      {/* Régions détectées : Synthèse et visualisations */}
      {isDone && inspection.regions_count > 0 && (
        <div className="space-y-6">
          {/* Métriques de synthèse */}
          <div className="grid gap-4 sm:grid-cols-3">
            <div className="rounded-xl border border-slate-200 bg-white p-4 shadow-sm dark:border-slate-800 dark:bg-slate-900">
              <p className="text-xs font-medium uppercase tracking-wider text-slate-400">Régions détectées</p>
              <p className="mt-1 text-2xl font-bold text-slate-900 dark:text-slate-100">{inspection.regions_count}</p>
            </div>
            <div className="rounded-xl border border-slate-200 bg-white p-4 shadow-sm dark:border-slate-800 dark:bg-slate-900">
              <p className="text-xs font-medium uppercase tracking-wider text-slate-400">YOLOv11 (Supervisé)</p>
              <p className="mt-1 text-2xl font-bold text-indigo-600 dark:text-indigo-400">{yoloCount}</p>
            </div>
            <div className="rounded-xl border border-slate-200 bg-white p-4 shadow-sm dark:border-slate-800 dark:bg-slate-900">
              <p className="text-xs font-medium uppercase tracking-wider text-slate-400">PatchCore (Anomalies)</p>
              <p className="mt-1 text-2xl font-bold text-emerald-600 dark:text-emerald-400">{patchcoreCount}</p>
            </div>
          </div>

          {/* Sélecteur de couche visuelle */}
          <div className="rounded-xl border border-slate-200 bg-white p-5 shadow-sm dark:border-slate-800 dark:bg-slate-900">
            <div className="flex flex-wrap items-center justify-between border-b border-slate-200 pb-4 dark:border-slate-800">
              <h2 className="text-sm font-semibold text-slate-900 dark:text-slate-100">
                Visualisation des couches
              </h2>
              <div className="flex gap-2">
                <button
                  type="button"
                  onClick={() => setActiveTab('overlay')}
                  className={`rounded-lg px-3 py-1.5 text-xs font-medium transition-colors ${
                    activeTab === 'overlay'
                      ? 'bg-indigo-600 text-white'
                      : 'bg-slate-100 text-slate-700 hover:bg-slate-200 dark:bg-slate-800 dark:text-slate-300'
                  }`}
                >
                  Overlay annoté (AC-03)
                </button>
                <button
                  type="button"
                  onClick={() => setActiveTab('image')}
                  className={`rounded-lg px-3 py-1.5 text-xs font-medium transition-colors ${
                    activeTab === 'image'
                      ? 'bg-indigo-600 text-white'
                      : 'bg-slate-100 text-slate-700 hover:bg-slate-200 dark:bg-slate-800 dark:text-slate-300'
                  }`}
                >
                  Image originale
                </button>
                {inspection.heatmap_meta && (
                  <button
                    type="button"
                    onClick={() => setActiveTab('heatmap')}
                    className={`rounded-lg px-3 py-1.5 text-xs font-medium transition-colors ${
                      activeTab === 'heatmap'
                        ? 'bg-indigo-600 text-white'
                        : 'bg-slate-100 text-slate-700 hover:bg-slate-200 dark:bg-slate-800 dark:text-slate-300'
                    }`}
                  >
                    Carte de chaleur PatchCore
                  </button>
                )}
              </div>
            </div>

            {/* Zone d'affichage de l'image sécurisée */}
            <div className="mt-4 flex min-h-[350px] items-center justify-center rounded-lg bg-slate-100 p-2 dark:bg-slate-950">
              {activeTab === 'overlay' && (
                overlayBlob.loading ? <LoadingSpinner size="lg" /> :
                overlayBlob.error ? <p className="text-xs text-rose-500">Erreur lors du chargement de l'overlay.</p> :
                overlayBlob.objectUrl ? (
                  <img
                    src={overlayBlob.objectUrl}
                    alt="Overlay annoté"
                    className="max-h-[600px] max-w-full rounded object-contain shadow"
                  />
                ) : null
              )}

              {activeTab === 'image' && (
                imageBlob.loading ? <LoadingSpinner size="lg" /> :
                imageBlob.error ? <p className="text-xs text-rose-500">Erreur lors du chargement de l'image.</p> :
                imageBlob.objectUrl ? (
                  <img
                    src={imageBlob.objectUrl}
                    alt="Image originale"
                    className="max-h-[600px] max-w-full rounded object-contain shadow"
                  />
                ) : null
              )}

              {activeTab === 'heatmap' && (
                heatmapBlob.loading ? <LoadingSpinner size="lg" /> :
                heatmapBlob.error ? <p className="text-xs text-rose-500">Erreur lors du chargement de la heatmap.</p> :
                heatmapBlob.objectUrl ? (
                  <div className="flex flex-col items-center gap-3">
                    <img
                      src={heatmapBlob.objectUrl}
                      alt="Carte de chaleur PatchCore"
                      className="max-h-[550px] max-w-full rounded object-contain shadow"
                    />
                    {inspection.heatmap_meta && (
                      <p className="text-xs text-slate-500 dark:text-slate-400">
                        Échelle : [min: {inspection.heatmap_meta.min.toFixed(2)}, max: {inspection.heatmap_meta.max.toFixed(2)}] • Seuil τ : {inspection.heatmap_meta.tau.toFixed(2)} • vmax : {inspection.heatmap_meta.vmax.toFixed(2)}
                      </p>
                    )}
                  </div>
                ) : null
              )}
            </div>
          </div>

          {/* Liste détaillée des régions candidates */}
          <div className="rounded-xl border border-slate-200 bg-white p-5 shadow-sm dark:border-slate-800 dark:bg-slate-900">
            <h2 className="text-sm font-semibold text-slate-900 dark:text-slate-100 mb-4">
              Détail des régions candidates détectées
            </h2>

            {regionsLoading ? (
              <div className="flex justify-center p-6">
                <LoadingSpinner size="md" />
              </div>
            ) : (
              <div className="divide-y divide-slate-200 dark:divide-slate-800">
                {regions.map((region) => (
                  <div key={region.id} className="flex flex-wrap items-center justify-between gap-4 py-3">
                    <div className="space-y-1">
                      <div className="flex items-center gap-2">
                        {region.engine === 'yolo' ? (
                          <span className="rounded border border-indigo-300 bg-indigo-50 px-2 py-0.5 text-xs font-semibold text-indigo-700 dark:border-indigo-800 dark:bg-indigo-950 dark:text-indigo-300">
                            {region.display_id ? `${region.display_id} • ` : ''}YOLO : {region.classification || 'Défaut'}
                          </span>
                        ) : (
                          <span className="rounded border border-dashed border-emerald-400 bg-emerald-50 px-2 py-0.5 text-xs font-semibold text-emerald-700 dark:border-emerald-800 dark:bg-emerald-950 dark:text-emerald-300">
                            {region.display_id ? `${region.display_id} • ` : ''}PatchCore : Anomalie
                          </span>
                        )}
                        <span className="text-xs font-medium text-slate-700 dark:text-slate-300">
                          {region.label}
                        </span>
                      </div>
                      <p className="text-xs text-slate-500 dark:text-slate-400">
                        Boîte : [{Math.round(region.bbox[0])}, {Math.round(region.bbox[1])}, {Math.round(region.bbox[2])}, {Math.round(region.bbox[3])}] px • Surface : {Math.round(region.area)} px²
                        {region.corroboration?.detected && (
                          <span className="ml-2 font-medium text-emerald-600 dark:text-emerald-400">
                            (Corroboré par PatchCore)
                          </span>
                        )}
                      </p>
                    </div>

                    <div className="text-right">
                      {region.latest_decision ? (
                        <span className="rounded-full bg-slate-100 px-2.5 py-1 text-xs font-medium text-slate-800 dark:bg-slate-800 dark:text-slate-200">
                          Décision : {region.latest_decision}
                        </span>
                      ) : (
                        <span className="rounded-full bg-amber-50 px-2.5 py-1 text-xs font-medium text-amber-700 dark:bg-amber-950 dark:text-amber-300">
                          En attente de revue
                        </span>
                      )}
                    </div>
                  </div>
                ))}
              </div>
            )}
          </div>
        </div>
      )}
    </div>
  )
}
