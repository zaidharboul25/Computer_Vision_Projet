import React from 'react'
import { Link } from 'react-router-dom'
import { FileQuestion, ArrowLeft } from 'lucide-react'

export const NotFoundPage: React.FC = () => {
  return (
    <div className="flex min-h-[60vh] flex-col items-center justify-center text-center">
      <div className="flex h-16 w-16 items-center justify-center rounded-full bg-slate-100 text-slate-500 dark:bg-slate-800 dark:text-slate-400">
        <FileQuestion className="h-8 w-8" />
      </div>
      <h1 className="mt-4 text-2xl font-bold tracking-tight text-slate-900 dark:text-white">Page introuvable</h1>
      <p className="mt-2 text-sm text-slate-600 dark:text-slate-400">
        L'adresse demandée n'existe pas ou la ressource a été déplacée.
      </p>
      <div className="mt-6">
        <Link
          to="/"
          className="inline-flex items-center gap-2 rounded-lg bg-blue-600 px-4 py-2 text-sm font-semibold text-white shadow-sm hover:bg-blue-500"
        >
          <ArrowLeft className="h-4 w-4" />
          Retour au tableau de bord
        </Link>
      </div>
    </div>
  )
}

