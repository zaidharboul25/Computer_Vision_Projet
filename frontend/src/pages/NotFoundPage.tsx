import React from 'react'
import { Link } from 'react-router-dom'
import { motion } from 'framer-motion'
import { FileQuestion, ArrowLeft } from 'lucide-react'
import { EASE } from '../components/ui/motion'

export const NotFoundPage: React.FC = () => {
  return (
    <div className="relative flex min-h-screen flex-col items-center justify-center overflow-hidden px-6 text-center">
      <div className="aurora" aria-hidden="true">
        <div className="aurora-blob left-1/4 top-1/4 h-80 w-80 bg-brand-400/40" />
        <div className="aurora-blob bottom-1/4 right-1/4 h-72 w-72 bg-cyan-400/30 [animation-delay:-9s]" />
      </div>
      <motion.div
        initial={{ opacity: 0, y: 24 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ duration: 0.6, ease: EASE }}
        className="relative"
      >
        <div className="animate-float text-[8rem] font-black leading-none tracking-tighter gradient-text sm:text-[11rem]">404</div>
        <div className="mx-auto -mt-4 flex h-14 w-14 items-center justify-center rounded-2xl bg-white text-slate-500 shadow-soft dark:bg-white/10 dark:text-slate-300">
          <FileQuestion className="h-7 w-7" />
        </div>
        <h1 className="mt-5 text-2xl font-bold tracking-tight text-slate-900 dark:text-white">Page introuvable</h1>
        <p className="mt-2 text-sm text-slate-600 dark:text-slate-400">
          L'adresse demandée n'existe pas ou la ressource a été déplacée.
        </p>
        <div className="mt-7">
          <Link to="/" className="btn-primary">
            <ArrowLeft className="h-4 w-4" />
            Retour au tableau de bord
          </Link>
        </div>
      </motion.div>
    </div>
  )
}
