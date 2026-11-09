import React, { useState, useRef } from 'react'
import {
  Sparkles,
  Upload,
  Clock,
  Search,
} from 'lucide-react'
import { searchSimilarity, getSimilarityThumbnailUrl } from '../services/api'
import type { SimilaritySearchResponse, SimilarityIndexResult, SimilarityItem } from '../types'
import { LoadingSpinner } from '../components/common/LoadingSpinner'
import { ErrorAlert } from '../components/common/ErrorAlert'

export const SimilaritySearchPage: React.FC = () => {
  const [file, setFile] = useState<File | null>(null)
  const [previewUrl, setPreviewUrl] = useState<string | null>(null)
  const [indexName, setIndexName] = useState<'weaveguard' | 'dtd' | 'all'>('all')
  const [k, setK] = useState<number>(5)

  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<unknown | null>(null)
  const [response, setResponse] = useState<SimilaritySearchResponse | null>(null)

  const fileInputRef = useRef<HTMLInputElement>(null)

  const handleFileChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    if (e.target.files && e.target.files[0]) {
      const selected = e.target.files[0]
      setFile(selected)
      setPreviewUrl(URL.createObjectURL(selected))
      setResponse(null)
      setError(null)
    }
  }

  const handleDrop = (e: React.DragEvent<HTMLDivElement>) => {
    e.preventDefault()
    if (e.dataTransfer.files && e.dataTransfer.files[0]) {
      const selected = e.dataTransfer.files[0]
      setFile(selected)
      setPreviewUrl(URL.createObjectURL(selected))
      setResponse(null)
      setError(null)
    }
  }

  const handleDragOver = (e: React.DragEvent<HTMLDivElement>) => {
    e.preventDefault()
  }

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault()
    if (!file) return

    setLoading(true)
    setError(null)
    try {
      const res = await searchSimilarity(file, indexName, k)
      setResponse(res)
    } catch (err) {
      setError(err)
    } finally {
      setLoading(false)
    }
  }

  const renderResultSection = (title: string, subtitle: string, resultData?: SimilarityIndexResult | null) => {
    if (!resultData) return null

    return (
      <div className="space-y-4">
        <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-2 border-b border-slate-200 pb-3 dark:border-slate-800">
          <div>
            <h3 className="text-lg font-bold text-slate-900 dark:text-white flex items-center gap-2">
              <Sparkles className="h-5 w-5 text-purple-600 dark:text-purple-400" />
              {title}
            </h3>
            <p className="text-xs text-slate-500 dark:text-slate-400">
              {subtitle} · Index: <code className="font-mono text-purple-600 dark:text-purple-400">{resultData.index}</code>
            </p>
          </div>
          {resultData.latency_ms && (
            <div className="flex items-center gap-3 text-xs text-slate-500 dark:text-slate-400">
              <span className="inline-flex items-center gap-1">
                <Clock className="h-3.5 w-3.5 text-slate-400" />
                Total : <strong className="text-slate-800 dark:text-slate-200">{resultData.latency_ms.total.toFixed(1)} ms</strong>
              </span>
              <span>(Modèle : {resultData.latency_ms.model.toFixed(1)} ms · Recherche : {resultData.latency_ms.search.toFixed(1)} ms)</span>
            </div>
          )}
        </div>

        {resultData.results.length === 0 ? (
          <div className="rounded-xl border border-dashed border-slate-200 p-8 text-center text-sm text-slate-500 dark:border-slate-800 dark:text-slate-400">
            Aucun voisin trouvé pour cet index.
          </div>
        ) : (
          <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 md:grid-cols-3 lg:grid-cols-5">
            {resultData.results.map((item: SimilarityItem) => {
              const scorePct = (item.score * 100).toFixed(1)
              const thumbUrl = getSimilarityThumbnailUrl(item.ref_id)
              const itemLabel = (item.classes && item.classes.length > 0)
                ? item.classes.join(', ')
                : (item.source || item.ref_id)

              return (
                <div
                  key={`${item.ref_id}-${item.rank}`}
                  className="group relative flex flex-col overflow-hidden rounded-xl border border-slate-200 bg-white shadow-sm transition hover:shadow-md dark:border-slate-800 dark:bg-slate-900"
                >
                  {/* Vignette */}
                  <div className="relative aspect-square w-full overflow-hidden bg-slate-100 dark:bg-slate-800">
                    <img
                      src={thumbUrl}
                      alt={itemLabel}
                      className="h-full w-full object-cover transition duration-200 group-hover:scale-105"
                      onError={(e) => {
                        ;(e.target as HTMLElement).style.display = 'none'
                      }}
                    />
                    <div className="absolute top-2 left-2 flex items-center gap-1 rounded bg-black/70 px-1.5 py-0.5 text-[11px] font-bold text-white backdrop-blur">
                      #{item.rank}
                    </div>
                    <div className="absolute top-2 right-2 flex items-center gap-1 rounded bg-blue-600/90 px-1.5 py-0.5 text-[11px] font-semibold text-white backdrop-blur">
                      {scorePct}%
                    </div>
                  </div>

                  {/* Détails */}
                  <div className="flex flex-1 flex-col justify-between p-3">
                    <div>
                      <div className="flex items-center justify-between text-xs font-semibold text-slate-800 dark:text-slate-200">
                        <span className="truncate" title={itemLabel}>
                          {itemLabel}
                        </span>
                      </div>
                      <p className="mt-1 font-mono text-[10px] text-slate-400 truncate" title={item.ref_id}>
                        {item.ref_id}
                      </p>
                    </div>

                    <div className="mt-3 flex items-center justify-between border-t border-slate-100 pt-2 text-[11px] text-slate-500 dark:border-slate-800 dark:text-slate-400">
                      <span>Similarité</span>
                      <span className="font-mono font-medium text-slate-700 dark:text-slate-300">
                        {item.score.toFixed(4)}
                      </span>
                    </div>
                  </div>
                </div>
              )
            })}
          </div>
        )}
      </div>
    )
  }

  return (
    <div className="stagger space-y-6">
      {/* En-tête */}
      <div>
        <div className="flex items-center gap-2">
          <Sparkles className="h-6 w-6 text-purple-600 dark:text-purple-400" />
          <h1 className="text-2xl font-bold tracking-tight text-slate-900 dark:text-white">
            Recherche de textiles similaires
          </h1>
        </div>
        <p className="mt-1 text-sm text-slate-500 dark:text-slate-400">
          Recherche visuelle par plongement vectoriel ResNet-50 GAP 2048 et index FAISS exact (IndexFlatIP) pour retrouver les motifs et anomalies les plus proches.
        </p>
      </div>

      {/* Formulaire de recherche */}
      <form
        aria-label="Formulaire de similarité"
        onSubmit={handleSubmit}
        className="space-y-6"
      >
        <div className="grid grid-cols-1 gap-6 lg:grid-cols-3">
          {/* Zone d'importation d'image */}
          <div className="lg:col-span-2">
            <div
              onDrop={handleDrop}
              onDragOver={handleDragOver}
              onClick={() => fileInputRef.current?.click()}
              className={`relative flex min-h-[220px] cursor-pointer flex-col items-center justify-center rounded-2xl border-2 border-dashed p-6 text-center transition ${
                previewUrl
                  ? 'border-blue-400 bg-blue-50/20 dark:border-blue-600 dark:bg-blue-950/20'
                  : 'border-slate-300 bg-white hover:border-slate-400 dark:border-slate-700 dark:bg-slate-900 dark:hover:border-slate-600'
              }`}
            >
              <input
                ref={fileInputRef}
                type="file"
                accept="image/png, image/jpeg"
                className="hidden"
                onChange={handleFileChange}
              />

              {previewUrl ? (
                <div className="flex flex-col items-center gap-3">
                  <img
                    src={previewUrl}
                    alt="Aperçu requête"
                    className="max-h-48 max-w-full rounded-lg object-contain shadow-sm border border-slate-200 dark:border-slate-800"
                  />
                  <div className="text-xs text-slate-600 dark:text-slate-300">
                    <span className="font-semibold">{file?.name}</span> ({(file!.size / 1024).toFixed(1)} Ko) — Cliquez pour changer
                  </div>
                </div>
              ) : (
                <div className="space-y-2">
                  <div className="mx-auto flex h-12 w-12 items-center justify-center rounded-full bg-purple-50 text-purple-600 dark:bg-purple-950/50 dark:text-purple-400">
                    <Upload className="h-6 w-6" />
                  </div>
                  <div className="text-sm font-semibold text-slate-800 dark:text-slate-200">
                    Déposez une image textile ou un échantillon ici
                  </div>
                  <p className="text-xs text-slate-500 dark:text-slate-400">
                    Formats acceptés : PNG ou JPEG (max 15 Mo).
                  </p>
                </div>
              )}
            </div>
          </div>

          {/* Options de recherche */}
          <div className="card p-5 space-y-4">
            <h3 className="text-sm font-bold uppercase tracking-wider text-slate-500 dark:text-slate-400">
              Paramètres de l'index
            </h3>

            {/* Index Cible */}
            <div>
              <label htmlFor="target-index" className="block text-xs font-semibold text-slate-700 dark:text-slate-300">
                Index cible
              </label>
              <select
                id="target-index"
                value={indexName}
                onChange={(e) => setIndexName(e.target.value as 'weaveguard' | 'dtd' | 'all')}
                className="input !py-2"
              >
                <option value="all">Tous les index (WeaveGuard + DTD)</option>
                <option value="weaveguard">Index WeaveGuard (Textiles d'apprentissage)</option>
                <option value="dtd">Galerie DTD (Textures génériques)</option>
              </select>
              <p className="mt-1 text-[11px] text-slate-500 dark:text-slate-400">
                WeaveGuard contient les tissus du dataset textile ; DTD contient 47 classes de texture générique.
              </p>
            </div>

            {/* Nombre de voisins k */}
            <div>
              <label htmlFor="k-neighbors" className="block text-xs font-semibold text-slate-700 dark:text-slate-300">
                Nombre de voisins (<code className="font-mono text-purple-600 dark:text-purple-400">k = {k}</code>)
              </label>
              <input
                id="k-neighbors"
                type="range"
                min="1"
                max="20"
                step="1"
                value={k}
                onChange={(e) => setK(Number(e.target.value))}
                className="mt-2 w-full accent-purple-600"
              />
              <div className="flex justify-between text-[11px] text-slate-400">
                <span>1</span>
                <span>5</span>
                <span>10</span>
                <span>20</span>
              </div>
            </div>

            {/* Bouton de recherche */}
            <div className="pt-2">
              <button
                type="submit"
                disabled={!file || loading}
                className="btn-primary w-full"
              >
                {loading ? (
                  <>
                    <LoadingSpinner size="sm" />
                    <span>Recherche en cours...</span>
                  </>
                ) : (
                  <>
                    <Search className="h-4 w-4" />
                    <span>Rechercher les voisins</span>
                  </>
                )}
              </button>
            </div>
          </div>
        </div>
      </form>

      {/* Erreurs éventuelles */}
      {error ? <ErrorAlert error={error} /> : null}

      {/* Résultats de recherche */}
      {response && (
        <div className="space-y-8 pt-4">
          {response.weaveguard && renderResultSection(
            'Galerie WeaveGuard (Textiles d\'entraînement)',
            'Voisins textiles les plus proches par similarité cosinus',
            response.weaveguard
          )}

          {response.dtd && renderResultSection(
            'Galerie DTD (Textures génériques de référence)',
            'Comparaison avec la distribution texturale Describable Textures Dataset',
            response.dtd
          )}
        </div>
      )}
    </div>
  )
}
