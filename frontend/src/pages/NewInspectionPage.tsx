import React, { useState, useRef, useEffect } from 'react'
import { useNavigate } from 'react-router-dom'
import { useQuery } from '@tanstack/react-query'
import { createInspection, getHealth } from '../services/api'
import { ErrorAlert } from '../components/common/ErrorAlert'
import { LoadingSpinner } from '../components/common/LoadingSpinner'

export const NewInspectionPage: React.FC = () => {
  const navigate = useNavigate()
  const fileInputRef = useRef<HTMLInputElement>(null)

  const [selectedFile, setSelectedFile] = useState<File | null>(null)
  const [previewUrl, setPreviewUrl] = useState<string | null>(null)
  const [isDragging, setIsDragging] = useState(false)
  const [isSubmitting, setIsSubmitting] = useState(false)
  const [error, setError] = useState<unknown>(null)

  // Moteurs sélectionnés
  const [useYolo, setUseYolo] = useState(true)
  const [usePatchCore, setUsePatchCore] = useState(true)
  const [scaleMode, setScaleMode] = useState<'native' | 'normalized'>('native')

  // Statut des moteurs depuis l'API
  const { data: health } = useQuery({
    queryKey: ['health'],
    queryFn: getHealth,
    staleTime: 10_000,
  })

  // Libérer l'URL de prévisualisation à chaque changement ou démontage
  useEffect(() => {
    if (!selectedFile) {
      setPreviewUrl(null)
      return
    }
    const url = URL.createObjectURL(selectedFile)
    setPreviewUrl(url)
    return () => {
      URL.revokeObjectURL(url)
    }
  }, [selectedFile])

  const handleFileChange = (file: File | undefined) => {
    setError(null)
    if (file) {
      setSelectedFile(file)
    }
  }

  const handleDrop = (e: React.DragEvent<HTMLDivElement>) => {
    e.preventDefault()
    setIsDragging(false)
    if (e.dataTransfer.files && e.dataTransfer.files.length > 0) {
      handleFileChange(e.dataTransfer.files[0])
    }
  }

  const handleDragOver = (e: React.DragEvent<HTMLDivElement>) => {
    e.preventDefault()
    setIsDragging(true)
  }

  const handleDragLeave = (e: React.DragEvent<HTMLDivElement>) => {
    e.preventDefault()
    setIsDragging(false)
  }

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault()
    if (!selectedFile) {
      setError(new Error('Veuillez sélectionner un cliché textile à analyser.'))
      return
    }

    const enabledEngines: string[] = []
    if (useYolo) enabledEngines.push('yolo')
    if (usePatchCore) enabledEngines.push('patchcore')

    if (enabledEngines.length === 0) {
      setError(new Error('Veuillez activer au moins un moteur d\'analyse (YOLO ou PatchCore).'))
      return
    }

    setIsSubmitting(true)
    setError(null)

    try {
      const res = await createInspection(selectedFile, enabledEngines, scaleMode)
      navigate(`/inspections/${res.id}`)
    } catch (err) {
      setError(err)
    } finally {
      setIsSubmitting(false)
    }
  }

  // Vérification de la disponibilité des moteurs déclarés par l'API
  const yoloAvailable = health?.engines?.yolo !== undefined ? Boolean(health.engines.yolo) : true
  const patchcoreAvailable = health?.engines?.patchcore !== undefined ? Boolean(health.engines.patchcore) : true

  return (
    <div className="stagger space-y-6">
      <div>
        <h1 className="text-2xl font-bold tracking-tight text-slate-900 dark:text-slate-100">
          Nouvelle inspection textile
        </h1>
        <p className="mt-1 text-sm text-slate-500 dark:text-slate-400">
          Téléversez un cliché haute résolution pour exécuter l'inférence combinée supervisée (YOLO) et non-supervisée (PatchCore).
        </p>
      </div>

      {Boolean(error) && <ErrorAlert error={error} />}

      <form onSubmit={handleSubmit} className="space-y-6">
        {/* Zone de glisser-déposer / sélection de fichier */}
        <div className="card p-6">
          <label className="block text-sm font-semibold text-slate-900 dark:text-slate-100 mb-3">
            1. Image textile à contrôler
          </label>

          <div
            onDrop={handleDrop}
            onDragOver={handleDragOver}
            onDragLeave={handleDragLeave}
            onClick={() => fileInputRef.current?.click()}
            className={`relative flex min-h-[220px] cursor-pointer flex-col items-center justify-center rounded-xl border-2 border-dashed p-6 text-center transition-colors ${
              isDragging
                ? 'border-indigo-500 bg-indigo-50/50 dark:border-indigo-400 dark:bg-indigo-950/20'
                : 'border-slate-300 hover:border-slate-400 dark:border-slate-700 dark:hover:border-slate-600'
            }`}
          >
            <input
              ref={fileInputRef}
              type="file"
              accept="image/*"
              className="hidden"
              data-testid="file-input"
              onChange={(e) => handleFileChange(e.target.files?.[0])}
            />

            {previewUrl ? (
              <div className="flex flex-col items-center gap-4">
                <div className="relative max-h-56 overflow-hidden rounded-lg border border-slate-200 shadow dark:border-slate-700">
                  <img
                    src={previewUrl}
                    alt="Aperçu textile local"
                    className="max-h-56 max-w-full object-contain"
                  />
                </div>
                <div className="text-center">
                  <p className="font-medium text-slate-800 dark:text-slate-200">{selectedFile?.name}</p>
                  <p className="text-xs text-slate-500 dark:text-slate-400">
                    {selectedFile && `${(selectedFile.size / (1024 * 1024)).toFixed(2)} Mo — Cliquer ou glisser pour remplacer`}
                  </p>
                </div>
              </div>
            ) : (
              <div className="flex flex-col items-center">
                <div className="mb-3 flex h-12 w-12 items-center justify-center rounded-full bg-indigo-50 text-indigo-600 dark:bg-indigo-950 dark:text-indigo-400">
                  <svg className="h-6 w-6" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                    <path
                      strokeLinecap="round"
                      strokeLinejoin="round"
                      strokeWidth={2}
                      d="M7 16a4 4 0 01-.88-7.903A5 5 0 1115.9 6L16 6a5 5 0 011 9.9M15 13l-3-3m0 0l-3 3m3-3v12"
                    />
                  </svg>
                </div>
                <p className="text-sm font-medium text-slate-700 dark:text-slate-200">
                  Glissez-déposez le cliché textile ici, ou{' '}
                  <span className="text-indigo-600 dark:text-indigo-400">parcourez vos fichiers</span>
                </p>
                <p className="mt-1 text-xs text-slate-500 dark:text-slate-400">
                  Formats acceptés par le serveur : PNG, JPEG, WebP. La taille maximale et la géométrie sont validées par le backend.
                </p>
              </div>
            )}
          </div>
        </div>

        {/* Sélection des moteurs d'inférence */}
        <div className="card p-6">
          <label className="block text-sm font-semibold text-slate-900 dark:text-slate-100 mb-3">
            2. Moteurs d'analyse activés
          </label>

          <div className="grid gap-4 sm:grid-cols-2">
            {/* YOLO */}
            <label
              className={`flex cursor-pointer items-start gap-3 rounded-lg border p-4 transition-colors ${
                useYolo
                  ? 'border-indigo-300 bg-indigo-50/40 dark:border-indigo-800 dark:bg-indigo-950/20'
                  : 'border-slate-200 bg-slate-50/50 opacity-70 dark:border-slate-800 dark:bg-slate-900/50'
              }`}
            >
              <input
                type="checkbox"
                checked={useYolo}
                disabled={!yoloAvailable}
                onChange={(e) => setUseYolo(e.target.checked)}
                className="mt-1 h-4 w-4 rounded border-slate-300 text-indigo-600 focus:ring-indigo-500"
              />
              <div>
                <div className="flex items-center gap-2">
                  <span className="font-semibold text-slate-900 dark:text-slate-100">YOLOv11</span>
                  <span className="rounded bg-indigo-100 px-2 py-0.5 text-xs font-medium text-indigo-800 dark:bg-indigo-900 dark:text-indigo-200">
                    Supervisé
                  </span>
                </div>
                <p className="mt-1 text-xs text-slate-500 dark:text-slate-400">
                  Détection supervisée des défauts connus (trou, fil tiré, tache, etc.) avec boîte englobante.
                </p>
                {!yoloAvailable && (
                  <p className="mt-1 text-xs font-medium text-amber-600 dark:text-amber-400">
                    Moteur indisponible sur le serveur
                  </p>
                )}
              </div>
            </label>

            {/* PatchCore */}
            <label
              className={`flex cursor-pointer items-start gap-3 rounded-lg border p-4 transition-colors ${
                usePatchCore
                  ? 'border-emerald-300 bg-emerald-50/40 dark:border-emerald-800 dark:bg-emerald-950/20'
                  : 'border-slate-200 bg-slate-50/50 opacity-70 dark:border-slate-800 dark:bg-slate-900/50'
              }`}
            >
              <input
                type="checkbox"
                checked={usePatchCore}
                disabled={!patchcoreAvailable}
                onChange={(e) => setUsePatchCore(e.target.checked)}
                className="mt-1 h-4 w-4 rounded border-slate-300 text-emerald-600 focus:ring-emerald-500"
              />
              <div>
                <div className="flex items-center gap-2">
                  <span className="font-semibold text-slate-900 dark:text-slate-100">PatchCore</span>
                  <span className="rounded bg-emerald-100 px-2 py-0.5 text-xs font-medium text-emerald-800 dark:bg-emerald-900 dark:text-emerald-200">
                    Non-supervisé
                  </span>
                </div>
                <p className="mt-1 text-xs text-slate-500 dark:text-slate-400">
                  Détection d'anomalies de texture par score de distance locale et génération de carte de chaleur.
                </p>
                {!patchcoreAvailable && (
                  <p className="mt-1 text-xs font-medium text-amber-600 dark:text-amber-400">
                    Moteur indisponible sur le serveur
                  </p>
                )}
              </div>
            </label>
          </div>
        </div>

        {/* 3. Mode d'échelle pour l'inférence */}
        <div className="card p-6">
          <label className="block text-sm font-semibold text-slate-900 dark:text-slate-100 mb-1">
            3. Mode d'échelle de l'image
          </label>
          <p className="mb-4 text-xs text-slate-500 dark:text-slate-400">
            Définit le traitement spatial appliqué avant l'inférence. Les coordonnées des défauts sont systématiquement restituées dans le repère natif.
          </p>

          <div className="grid gap-3 sm:grid-cols-2">
            <label
              className={`flex cursor-pointer items-start gap-3 rounded-lg border p-4 transition-colors ${
                scaleMode === 'native'
                  ? 'border-indigo-300 bg-indigo-50/40 dark:border-indigo-800 dark:bg-indigo-950/20'
                  : 'border-slate-200 bg-slate-50/50 dark:border-slate-800 dark:bg-slate-900/50'
              }`}
            >
              <input
                type="radio"
                name="scale_mode"
                value="native"
                checked={scaleMode === 'native'}
                onChange={() => setScaleMode('native')}
                className="mt-1 h-4 w-4 border-slate-300 text-indigo-600 focus:ring-indigo-500"
              />
              <div>
                <div className="flex items-center gap-2">
                  <span className="font-semibold text-slate-900 dark:text-slate-100">Natif (par défaut)</span>
                  <span className="rounded bg-slate-100 px-2 py-0.5 text-xs font-medium text-slate-700 dark:bg-slate-800 dark:text-slate-300">
                    Standard
                  </span>
                </div>
                <p className="mt-1 text-xs text-slate-500 dark:text-slate-400">
                  L'image conserve sa résolution d'origine (ou est réduite si &gt; 1 448 px). Recommandé pour les clichés industriels haute résolution.
                </p>
              </div>
            </label>

            <label
              className={`flex cursor-pointer items-start gap-3 rounded-lg border p-4 transition-colors ${
                scaleMode === 'normalized'
                  ? 'border-indigo-300 bg-indigo-50/40 dark:border-indigo-800 dark:bg-indigo-950/20'
                  : 'border-slate-200 bg-slate-50/50 dark:border-slate-800 dark:bg-slate-900/50'
              }`}
            >
              <input
                type="radio"
                name="scale_mode"
                value="normalized"
                checked={scaleMode === 'normalized'}
                onChange={() => setScaleMode('normalized')}
                className="mt-1 h-4 w-4 border-slate-300 text-indigo-600 focus:ring-indigo-500"
              />
              <div>
                <div className="flex items-center gap-2">
                  <span className="font-semibold text-slate-900 dark:text-slate-100">Normalisé (agrandi à 1 448 px)</span>
                  <span className="rounded bg-amber-100 px-2 py-0.5 text-xs font-medium text-amber-800 dark:bg-amber-900 dark:text-amber-200">
                    Petites images
                  </span>
                </div>
                <p className="mt-1 text-xs text-slate-500 dark:text-slate-400">
                  Toute image miniature (&lt; 1 448 px) est agrandie (bicubique) à la dimension nominale pour permettre aux moteurs d'analyser les micro-textures.
                </p>
              </div>
            </label>
          </div>
        </div>

        {/* Bouton de soumission */}
        <div className="flex justify-end gap-3">
          <button
            type="button"
            onClick={() => navigate('/')}
            className="btn-secondary !py-2 disabled:opacity-40"
          >
            Annuler
          </button>
          <button
            type="submit"
            disabled={isSubmitting || !selectedFile || (!useYolo && !usePatchCore)}
            className="btn-primary !py-2"
          >
            {isSubmitting ? (
              <>
                <LoadingSpinner size="sm" />
                <span>Téléversement et file d'attente...</span>
              </>
            ) : (
              <>
                <svg className="h-4 w-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M14 5l7 7m0 0l-7 7m7-7H3" />
                </svg>
                <span>Démarrer l'analyse</span>
              </>
            )}
          </button>
        </div>
      </form>
    </div>
  )
}

