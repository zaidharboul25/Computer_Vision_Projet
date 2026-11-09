import React, { useEffect, useState } from 'react'
import {
  Layers,
  Sparkles,
  Search,
  ShieldAlert,
  BarChart3,
} from 'lucide-react'
import { getModels, getDomainBiasReport } from '../services/api'
import type { ModelsList, DomainBiasReport } from '../types'
import { ModelsPageSkeleton } from '../components/ui/Skeleton'
import { ErrorAlert } from '../components/common/ErrorAlert'

export const ModelEvaluationPage: React.FC = () => {
  const [models, setModels] = useState<ModelsList | null>(null)
  const [domainReport, setDomainReport] = useState<DomainBiasReport | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<unknown | null>(null)

  useEffect(() => {
    Promise.all([getModels(), getDomainBiasReport()])
      .then(([modelsData, reportData]) => {
        setModels(modelsData)
        setDomainReport(reportData)
      })
      .catch((err) => {
        setError(err)
      })
      .finally(() => {
        setLoading(false)
      })
  }, [])

  if (loading) {
    return <ModelsPageSkeleton />
  }

  const refMin = typeof domainReport?.reference_min === 'number'
    ? domainReport.reference_min
    : 0.8124

  const quantiles: number[] = Array.isArray(domainReport?.familiarity_quantiles)
    ? (domainReport.familiarity_quantiles as number[])
    : [0.8124, 0.8941, 0.9255, 0.9482, 0.9896]

  return (
    <div className="stagger space-y-8">
      {/* En-tête */}
      <div>
        <div className="flex items-center gap-2">
          <BarChart3 className="h-6 w-6 text-blue-600 dark:text-blue-400" />
          <h1 className="text-2xl font-bold tracking-tight text-slate-900 dark:text-white">
            Évaluation ML & Fiches modèles
          </h1>
        </div>
        <p className="mt-1 text-sm text-slate-500 dark:text-slate-400">
          Spécifications techniques, empreintes SHA-256 immuables, seuils de décision et analyse contractuelle du biais de domaine.
        </p>
      </div>

      {error ? <ErrorAlert error={error} /> : null}

      {/* Cartes des moteurs */}
      <div className="grid grid-cols-1 gap-6 lg:grid-cols-3">
        {/* Carte YOLO */}
        <div className="card p-6 flex flex-col justify-between">
          <div>
            <div className="flex items-center justify-between">
              <span className="inline-flex items-center gap-1.5 rounded-lg bg-blue-50 px-2.5 py-1 text-xs font-semibold text-blue-700 dark:bg-blue-950/60 dark:text-blue-300">
                <Layers className="h-4 w-4" />
                Moteur Supervisé
              </span>
              <span className="text-xs font-mono text-slate-400">YOLOv8n-640</span>
            </div>

            <h3 className="mt-4 text-lg font-bold text-slate-900 dark:text-white">
              Détection de Défauts Spécifiques
            </h3>
            <p className="mt-1 text-xs text-slate-500 dark:text-slate-400">
              Modèle à boîte englobante entraîné sur 6 classes de défauts textiles supervisées.
            </p>

            <div className="mt-5 space-y-3 border-t border-slate-100 pt-4 text-xs dark:border-slate-800">
              <div className="flex justify-between">
                <span className="text-slate-500 dark:text-slate-400">Taille d'entrée</span>
                <span className="font-semibold text-slate-800 dark:text-slate-200">640 × 640 px</span>
              </div>
              <div className="flex justify-between">
                <span className="text-slate-500 dark:text-slate-400">Seuil de confiance</span>
                <span className="font-semibold text-blue-600 dark:text-blue-400">0.311 (calibré)</span>
              </div>
              <div className="flex justify-between">
                <span className="text-slate-500 dark:text-slate-400">Seuil IoU NMS</span>
                <span className="font-semibold text-slate-800 dark:text-slate-200">0.45</span>
              </div>
              <div className="flex justify-between">
                <span className="text-slate-500 dark:text-slate-400">Classes supervisées</span>
                <span className="font-semibold text-slate-800 dark:text-slate-200">6 classes</span>
              </div>
              <div>
                <span className="text-slate-500 dark:text-slate-400">Classes cibles :</span>
                <div className="mt-1.5 flex flex-wrap gap-1">
                  {['Holes', 'Stains', 'Foreign Fibers', 'Broken Yarn', 'Knot', 'Vertical LineMark'].map((c) => (
                    <span key={c} className="rounded bg-slate-100 px-1.5 py-0.5 text-[10px] text-slate-700 dark:bg-slate-800 dark:text-slate-300">
                      {c}
                    </span>
                  ))}
                </div>
              </div>
            </div>
          </div>

          <div className="mt-6 border-t border-slate-100 pt-4 dark:border-slate-800">
            <div className="text-[11px] text-slate-400">Empreinte SHA-256 des poids :</div>
            <div className="mt-1 truncate font-mono text-[10px] text-slate-600 dark:text-slate-400 bg-slate-50 dark:bg-slate-800/50 p-1.5 rounded">
              {models?.integrity?.['yolo'] || '58d7c0415a7826b5ec63255ff0faecfe45ee9bc54b3ee42a8a81691129994c50'}
            </div>
          </div>
        </div>

        {/* Carte PatchCore */}
        <div className="card p-6 flex flex-col justify-between">
          <div>
            <div className="flex items-center justify-between">
              <span className="inline-flex items-center gap-1.5 rounded-lg bg-purple-50 px-2.5 py-1 text-xs font-semibold text-purple-700 dark:bg-purple-950/60 dark:text-purple-300">
                <Sparkles className="h-4 w-4" />
                Moteur Non-supervisé
              </span>
              <span className="text-xs font-mono text-slate-400">PatchCore v1</span>
            </div>

            <h3 className="mt-4 text-lg font-bold text-slate-900 dark:text-white">
              Détection d'Anomalies Hors-Distribution
            </h3>
            <p className="mt-1 text-xs text-slate-500 dark:text-slate-400">
              Mémoire de motifs normaux par plongements de patchs WideResNet-50-2 et recherche k-NN.
            </p>

            <div className="mt-5 space-y-3 border-t border-slate-100 pt-4 text-xs dark:border-slate-800">
              <div className="flex justify-between">
                <span className="text-slate-500 dark:text-slate-400">Backbone</span>
                <span className="font-semibold text-slate-800 dark:text-slate-200">WideResNet-50-2</span>
              </div>
              <div className="flex justify-between">
                <span className="text-slate-500 dark:text-slate-400">Dimension vecteur</span>
                <span className="font-semibold text-slate-800 dark:text-slate-200">1024-d</span>
              </div>
              <div className="flex justify-between">
                <span className="text-slate-500 dark:text-slate-400">Seuil de distance τ</span>
                <span className="font-semibold text-purple-600 dark:text-purple-400">1.6386 (calibré)</span>
              </div>
              <div className="flex justify-between">
                <span className="text-slate-500 dark:text-slate-400">Mémoire de référence</span>
                <span className="font-semibold text-slate-800 dark:text-slate-200">40 960 patchs (10%)</span>
              </div>
              <div className="flex justify-between">
                <span className="text-slate-500 dark:text-slate-400">Recherche de voisins</span>
                <span className="font-semibold text-slate-800 dark:text-slate-200">FAISS IndexFlatL2 exact</span>
              </div>
            </div>
          </div>

          <div className="mt-6 border-t border-slate-100 pt-4 dark:border-slate-800">
            <div className="text-[11px] text-slate-400">Empreinte mémoire :</div>
            <div className="mt-1 truncate font-mono text-[10px] text-slate-600 dark:text-slate-400 bg-slate-50 dark:bg-slate-800/50 p-1.5 rounded">
              {models?.integrity?.['patchcore'] || 'ad80be4e2d31ce02b0c156f2a7dbfe3566164d9b68d601a5fa600e12140bb063'}
            </div>
          </div>
        </div>

        {/* Carte Similarité & Fusion */}
        <div className="card p-6 flex flex-col justify-between">
          <div>
            <div className="flex items-center justify-between">
              <span className="inline-flex items-center gap-1.5 rounded-lg bg-emerald-50 px-2.5 py-1 text-xs font-semibold text-emerald-700 dark:bg-emerald-950/60 dark:text-emerald-300">
                <Search className="h-4 w-4" />
                Moteur de Similarité
              </span>
              <span className="text-xs font-mono text-slate-400">ResNet-50 GAP</span>
            </div>

            <h3 className="mt-4 text-lg font-bold text-slate-900 dark:text-white">
              Recherche Vectorielle & Fusion
            </h3>
            <p className="mt-1 text-xs text-slate-500 dark:text-slate-400">
              Plongements globaux 2048-d normalisés L2 et règles de corroboration géométrique (IoU ≥ 0.30).
            </p>

            <div className="mt-5 space-y-3 border-t border-slate-100 pt-4 text-xs dark:border-slate-800">
              <div className="flex justify-between">
                <span className="text-slate-500 dark:text-slate-400">Extracteur d'empreinte</span>
                <span className="font-semibold text-slate-800 dark:text-slate-200">ResNet-50 GAP 2048-d</span>
              </div>
              <div className="flex justify-between">
                <span className="text-slate-500 dark:text-slate-400">Métrique d'indexation</span>
                <span className="font-semibold text-emerald-600 dark:text-emerald-400">Produit scalaire (Cosinus)</span>
              </div>
              <div className="flex justify-between">
                <span className="text-slate-500 dark:text-slate-400">Index WeaveGuard</span>
                <span className="font-semibold text-slate-800 dark:text-slate-200">Échantillons textiles</span>
              </div>
              <div className="flex justify-between">
                <span className="text-slate-500 dark:text-slate-400">Index DTD</span>
                <span className="font-semibold text-slate-800 dark:text-slate-200">47 classes de texture</span>
              </div>
              <div className="flex justify-between">
                <span className="text-slate-500 dark:text-slate-400">Seuil corroboration fusion</span>
                <span className="font-semibold text-slate-800 dark:text-slate-200">IoU ≥ 0.30</span>
              </div>
            </div>
          </div>

          <div className="mt-6 border-t border-slate-100 pt-4 dark:border-slate-800">
            <div className="text-[11px] text-slate-400">Index FAISS :</div>
            <div className="mt-1 truncate font-mono text-[10px] text-slate-600 dark:text-slate-400 bg-slate-50 dark:bg-slate-800/50 p-1.5 rounded">
              IndexFlatIP (Exact, zéro approximation LSH/HNSW)
            </div>
          </div>
        </div>
      </div>

      {/* Section Rapport de Biais de Domaine & Familiarité */}
      <div className="card p-6 space-y-5">
        <div className="flex items-center justify-between border-b border-slate-100 pb-4 dark:border-slate-800">
          <div>
            <h2 className="text-lg font-bold text-slate-900 dark:text-white flex items-center gap-2">
              <ShieldAlert className="h-5 w-5 text-amber-500" />
              Contrôle du Biais de Domaine & Familiarité (ADR-24)
            </h2>
            <p className="mt-1 text-xs text-slate-500 dark:text-slate-400">
              Règle descriptive garantissant l'aide à l'interprétation lorsque l'image inspectée est hors de la plage d'apprentissage.
            </p>
          </div>
          <div className="rounded-lg bg-amber-50 px-3 py-1 text-xs font-semibold text-amber-800 dark:bg-amber-950/40 dark:text-amber-300 border border-amber-200 dark:border-amber-800">
            Seuil min : {refMin.toFixed(4)}
          </div>
        </div>

        <div className="grid grid-cols-1 gap-6 lg:grid-cols-3">
          {/* Explication contractuelle */}
          <div className="lg:col-span-2 space-y-3 text-sm text-slate-600 dark:text-slate-300 leading-relaxed">
            <p>
              Pour chaque inspection soumise, WeaveGuard AI extrait l'empreinte vectorielle de l'image entière et calcule sa <strong>similarité cosinus maximale</strong> avec les images de la galerie de référence.
            </p>
            <p>
              Si la similarité maximale est inférieure à <code className="font-mono text-amber-600 dark:text-amber-400 font-semibold">{refMin.toFixed(4)}</code> (minimum observé sur les jeux de validation et de test), un avertissement explicite est consigné :
            </p>
            <blockquote className="rounded-xl border-l-4 border-amber-500 bg-amber-50/60 p-3 text-xs italic text-amber-900 dark:bg-amber-950/30 dark:text-amber-200">
              « Cette image ressemble peu aux images d'apprentissage (similarité maximale X, minimum observé en validation/test {refMin.toFixed(4)}). Les résultats peuvent être moins fiables. »
            </blockquote>
            <p className="text-xs text-slate-500 dark:text-slate-400">
              <strong>Principe non-négociable :</strong> Cet avertissement n'est ni un filtre, ni une décision : aucun résultat d'inférence (YOLO ou PatchCore) n'est supprimé ou masqué à cause de lui.
            </p>
          </div>

          {/* Quantiles de familiarité */}
          <div className="rounded-xl border border-slate-200 bg-slate-50 p-4 dark:border-slate-800 dark:bg-slate-800/40">
            <h4 className="text-xs font-bold uppercase tracking-wider text-slate-700 dark:text-slate-300">
              Distribution des Quantiles (Val + Test)
            </h4>
            <div className="mt-4 space-y-2.5 text-xs">
              <div className="flex justify-between items-center py-1 border-b border-slate-200/60 dark:border-slate-700">
                <span className="text-slate-500 dark:text-slate-400">Minimum (0%)</span>
                <span className="font-mono font-bold text-amber-600 dark:text-amber-400">
                  {quantiles[0]?.toFixed(4)}
                </span>
              </div>
              <div className="flex justify-between items-center py-1 border-b border-slate-200/60 dark:border-slate-700">
                <span className="text-slate-500 dark:text-slate-400">Premier quartile (Q1, 25%)</span>
                <span className="font-mono font-semibold text-slate-700 dark:text-slate-300">
                  {quantiles[1]?.toFixed(4)}
                </span>
              </div>
              <div className="flex justify-between items-center py-1 border-b border-slate-200/60 dark:border-slate-700">
                <span className="text-slate-500 dark:text-slate-400">Médiane (Q2, 50%)</span>
                <span className="font-mono font-semibold text-slate-800 dark:text-slate-200">
                  {quantiles[2]?.toFixed(4)}
                </span>
              </div>
              <div className="flex justify-between items-center py-1 border-b border-slate-200/60 dark:border-slate-700">
                <span className="text-slate-500 dark:text-slate-400">Troisième quartile (Q3, 75%)</span>
                <span className="font-mono font-semibold text-slate-700 dark:text-slate-300">
                  {quantiles[3]?.toFixed(4)}
                </span>
              </div>
              <div className="flex justify-between items-center py-1">
                <span className="text-slate-500 dark:text-slate-400">Maximum (100%)</span>
                <span className="font-mono font-bold text-emerald-600 dark:text-emerald-400">
                  {quantiles[4]?.toFixed(4)}
                </span>
              </div>
            </div>
          </div>
        </div>
      </div>
    </div>
  )
}
