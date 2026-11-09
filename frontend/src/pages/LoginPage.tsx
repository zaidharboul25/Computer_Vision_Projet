import React, { useState } from 'react'
import { useNavigate, useLocation } from 'react-router-dom'
import { motion, AnimatePresence } from 'framer-motion'
import { Lock, User, ArrowRight, Eye, EyeOff, ScanSearch, Layers, ShieldCheck, Moon, Sun } from 'lucide-react'
import { useAuth } from '../context/AuthContext'
import { useTheme } from '../context/ThemeContext'
import { apiFetch } from '../services/api'
import { ErrorAlert } from '../components/common/ErrorAlert'
import { LogoMark, LogoWordmark } from '../components/common/Logo'
import { LoadingSpinner } from '../components/common/LoadingSpinner'
import { EASE } from '../components/ui/motion'
import type { UserRole } from '../types'

const FEATURES = [
  { icon: ScanSearch, title: 'Détection supervisée', text: 'YOLOv11 localise les défauts connus en quelques millisecondes.' },
  { icon: Layers, title: 'Anomalies inédites', text: 'PatchCore repère ce qu’aucun modèle supervisé n’a jamais vu.' },
  { icon: ShieldCheck, title: 'Traçabilité complète', text: 'Chaque décision humaine est auditée et horodatée.' },
]

export const LoginPage: React.FC = () => {
  const [username, setUsername] = useState('')
  const [password, setPassword] = useState('')
  const [showPassword, setShowPassword] = useState(false)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<unknown>(null)

  const { login } = useAuth()
  const { theme, toggleTheme } = useTheme()
  const navigate = useNavigate()
  const location = useLocation()

  const from = (location.state as { from?: { pathname: string } })?.from?.pathname || '/'

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault()
    if (!username.trim() || !password) return

    setLoading(true)
    setError(null)

    try {
      const res = await apiFetch<{
        access_token: string
        token_type: string
        user: { username: string; role: UserRole }
      }>('/api/v1/auth/login', {
        method: 'POST',
        body: JSON.stringify({ username: username.trim(), password }),
      })

      login(res.access_token, res.user)
      navigate(from, { replace: true })
    } catch (err) {
      setError(err)
    } finally {
      setLoading(false)
    }
  }

  const demoAccounts = [
    { name: 'demo_operator', role: 'Opérateur' },
    { name: 'demo_supervisor', role: 'Superviseur' },
    { name: 'demo_ml_engineer', role: 'Ingénieur ML' },
    { name: 'demo_admin', role: 'Administrateur' },
    { name: 'demo_auditor', role: 'Auditeur' },
  ]

  return (
    <div className="relative grid min-h-screen lg:grid-cols-[1.1fr_1fr]">
      {/* ===== Panneau visuel ===== */}
      <div className="relative hidden overflow-hidden bg-ink-950 lg:block">
        <div className="aurora">
          <div className="aurora-blob -left-20 top-0 h-[28rem] w-[28rem] bg-brand-600" />
          <div className="aurora-blob bottom-0 right-0 h-96 w-96 bg-cyan-500/70 [animation-delay:-9s]" />
          <div className="aurora-blob left-1/3 top-1/2 h-72 w-72 bg-violet-600/70 [animation-delay:-16s]" />
        </div>
        <div className="grid-bg absolute inset-0" aria-hidden="true" />

        <div className="relative flex h-full flex-col justify-between p-12 xl:p-16">
          <motion.div initial={{ opacity: 0, y: -12 }} animate={{ opacity: 1, y: 0 }} transition={{ duration: 0.6, ease: EASE }} className="flex items-center gap-3">
            <LogoMark className="h-11 w-11" pulse />
            <span className="text-xl font-bold tracking-tight text-white">
              WeaveGuard <span className="gradient-text">AI</span>
            </span>
          </motion.div>

          <div>
            {/* Tissu scanné */}
            <motion.div
              initial={{ opacity: 0, scale: 0.92 }}
              animate={{ opacity: 1, scale: 1 }}
              transition={{ duration: 0.9, ease: EASE, delay: 0.15 }}
              className="relative mb-10 h-44 w-full max-w-md overflow-hidden rounded-2xl border border-white/15 bg-white/[0.04] shadow-2xl shadow-brand-900/40 backdrop-blur"
              aria-hidden="true"
            >
              <div
                className="absolute inset-0 opacity-60"
                style={{
                  backgroundImage:
                    'repeating-linear-gradient(0deg, rgb(255 255 255 / 0.10) 0 2px, transparent 2px 7px), repeating-linear-gradient(90deg, rgb(129 140 248 / 0.18) 0 2px, transparent 2px 7px)',
                }}
              />
              <div className="absolute inset-x-0 top-0 h-1/2 animate-scan bg-gradient-to-b from-transparent via-cyan-400/30 to-cyan-300/70">
                <div className="absolute inset-x-0 bottom-0 h-px bg-cyan-300 shadow-[0_0_14px_3px_rgb(103_232_249/0.8)]" />
              </div>
              {/* boîtes de détection */}
              <motion.div
                className="absolute left-[18%] top-[28%] h-14 w-20 rounded border-2 border-blue-400"
                initial={{ opacity: 0, scale: 0.6 }}
                animate={{ opacity: [0, 1, 1, 0], scale: [0.6, 1, 1, 1] }}
                transition={{ duration: 3.2, repeat: Infinity, times: [0, 0.2, 0.8, 1], delay: 0.6 }}
              >
                <span className="absolute -top-5 left-0 rounded bg-blue-500 px-1.5 py-0.5 text-[10px] font-semibold text-white">trou · 94%</span>
              </motion.div>
              <motion.div
                className="absolute bottom-[20%] right-[16%] h-12 w-16 rounded border-2 border-violet-400"
                initial={{ opacity: 0 }}
                animate={{ opacity: [0, 1, 1, 0] }}
                transition={{ duration: 3.2, repeat: Infinity, times: [0, 0.3, 0.85, 1], delay: 1.4 }}
              >
                <span className="absolute -top-5 left-0 rounded bg-violet-500 px-1.5 py-0.5 text-[10px] font-semibold text-white">anomalie</span>
              </motion.div>
            </motion.div>

            <motion.h2
              initial={{ opacity: 0, y: 20 }}
              animate={{ opacity: 1, y: 0 }}
              transition={{ duration: 0.7, ease: EASE, delay: 0.25 }}
              className="max-w-lg text-4xl font-extrabold leading-[1.1] tracking-tight text-white xl:text-5xl"
            >
              Aucun défaut ne <span className="gradient-text">passe inaperçu</span>.
            </motion.h2>
            <motion.p
              initial={{ opacity: 0, y: 20 }}
              animate={{ opacity: 1, y: 0 }}
              transition={{ duration: 0.7, ease: EASE, delay: 0.35 }}
              className="mt-4 max-w-md text-base leading-relaxed text-slate-300"
            >
              Plateforme d’inspection textile industrielle par vision par ordinateur.
            </motion.p>

            <ul className="mt-9 space-y-4">
              {FEATURES.map((f, i) => (
                <motion.li
                  key={f.title}
                  initial={{ opacity: 0, x: -18 }}
                  animate={{ opacity: 1, x: 0 }}
                  transition={{ duration: 0.55, ease: EASE, delay: 0.5 + i * 0.12 }}
                  className="flex items-start gap-4"
                >
                  <span className="flex h-10 w-10 flex-shrink-0 items-center justify-center rounded-xl bg-white/10 text-brand-300 ring-1 ring-white/15">
                    <f.icon className="h-5 w-5" />
                  </span>
                  <div>
                    <div className="text-sm font-semibold text-white">{f.title}</div>
                    <div className="text-sm text-slate-400">{f.text}</div>
                  </div>
                </motion.li>
              ))}
            </ul>
          </div>

          <p className="text-xs text-slate-500">© {new Date().getFullYear()} WeaveGuard AI · Projet de vision par ordinateur</p>
        </div>
      </div>

      {/* ===== Formulaire ===== */}
      <div className="relative flex flex-col items-center justify-center overflow-hidden bg-slate-50 px-5 py-12 sm:px-10 dark:bg-ink-950">
        <div className="aurora lg:hidden" aria-hidden="true">
          <div className="aurora-blob -right-24 -top-24 h-72 w-72 bg-brand-400/40" />
          <div className="aurora-blob -bottom-24 -left-24 h-72 w-72 bg-cyan-400/30 [animation-delay:-10s]" />
        </div>

        <button
          type="button"
          onClick={toggleTheme}
          className="btn-ghost absolute right-5 top-5 !p-2.5"
          aria-label={theme === 'dark' ? 'Activer le mode clair' : 'Activer le mode sombre'}
        >
          {theme === 'dark' ? <Sun className="h-5 w-5 text-amber-400" /> : <Moon className="h-5 w-5" />}
        </button>

        <motion.div
          initial={{ opacity: 0, y: 24 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.65, ease: EASE, delay: 0.1 }}
          className="relative w-full max-w-md"
        >
          <div className="mb-8 flex flex-col items-center text-center lg:items-start lg:text-left">
            <div className="lg:hidden">
              <LogoMark className="mx-auto mb-4 h-14 w-14" pulse />
            </div>
            <h1 className="text-3xl font-extrabold tracking-tight text-slate-900 dark:text-white">
              <span className="lg:hidden"><LogoWordmark className="text-3xl font-extrabold" /></span>
              <span className="hidden lg:inline">Bon retour 👋</span>
            </h1>
            <p className="mt-2 text-sm text-slate-600 dark:text-slate-400">
              Plateforme d'inspection textile industrielle par vision par ordinateur
            </p>
          </div>

          <div className="card p-6 sm:p-8">
            <form className="space-y-5" onSubmit={handleSubmit}>
              <AnimatePresence initial={false}>
                {Boolean(error) && (
                  <motion.div
                    key="err"
                    initial={{ opacity: 0, height: 0 }}
                    animate={{ opacity: 1, height: 'auto' }}
                    exit={{ opacity: 0, height: 0 }}
                    className="overflow-hidden"
                  >
                    <ErrorAlert error={error} onDismiss={() => setError(null)} />
                  </motion.div>
                )}
              </AnimatePresence>

              <div>
                <label htmlFor="username" className="mb-1.5 block text-sm font-medium text-slate-700 dark:text-slate-300">
                  Identifiant
                </label>
                <div className="relative">
                  <User className="pointer-events-none absolute left-3.5 top-1/2 h-4 w-4 -translate-y-1/2 text-slate-400" aria-hidden="true" />
                  <input
                    id="username"
                    name="username"
                    type="text"
                    autoComplete="username"
                    required
                    value={username}
                    onChange={(e) => setUsername(e.target.value)}
                    placeholder="ex: demo_operator"
                    className="input pl-10"
                  />
                </div>
              </div>

              <div>
                <label htmlFor="password" className="mb-1.5 block text-sm font-medium text-slate-700 dark:text-slate-300">
                  Mot de passe
                </label>
                <div className="relative">
                  <Lock className="pointer-events-none absolute left-3.5 top-1/2 h-4 w-4 -translate-y-1/2 text-slate-400" aria-hidden="true" />
                  <input
                    id="password"
                    name="password"
                    type={showPassword ? 'text' : 'password'}
                    autoComplete="current-password"
                    required
                    value={password}
                    onChange={(e) => setPassword(e.target.value)}
                    placeholder="••••••••••••"
                    className="input pl-10 pr-11"
                  />
                  <button
                    type="button"
                    onClick={() => setShowPassword((v) => !v)}
                    className="absolute right-2 top-1/2 -translate-y-1/2 rounded-lg p-1.5 text-slate-400 transition-colors hover:text-slate-700 dark:hover:text-slate-200"
                    aria-label={showPassword ? 'Masquer le mot de passe' : 'Afficher le mot de passe'}
                  >
                    {showPassword ? <EyeOff className="h-4 w-4" /> : <Eye className="h-4 w-4" />}
                  </button>
                </div>
              </div>

              <button type="submit" disabled={loading} className="btn-primary group w-full py-3">
                {loading ? (
                  <>
                    <LoadingSpinner size="sm" className="text-white" label="Connexion" />
                    Connexion en cours...
                  </>
                ) : (
                  <>
                    Se connecter
                    <ArrowRight className="h-4 w-4 transition-transform duration-200 group-hover:translate-x-1" />
                  </>
                )}
              </button>
            </form>

            <div className="mt-6 border-t border-slate-200 pt-5 dark:border-white/10">
              <h2 className="eyebrow !text-[11px]">Comptes configurés en démonstration :</h2>
              <div className="mt-3 flex flex-wrap gap-2">
                {demoAccounts.map((acc, i) => (
                  <motion.button
                    key={acc.name}
                    type="button"
                    onClick={() => setUsername(acc.name)}
                    initial={{ opacity: 0, scale: 0.9 }}
                    animate={{ opacity: 1, scale: 1 }}
                    transition={{ delay: 0.5 + i * 0.06 }}
                    whileHover={{ y: -2 }}
                    whileTap={{ scale: 0.95 }}
                    className="rounded-lg border border-slate-200 bg-slate-50 px-2.5 py-1.5 text-xs text-slate-700 transition-colors hover:border-brand-300 hover:bg-brand-50 hover:text-brand-700 dark:border-white/10 dark:bg-white/5 dark:text-slate-300 dark:hover:border-brand-400/40 dark:hover:bg-brand-500/10"
                    title={`Pré-remplir l'identifiant ${acc.name}`}
                  >
                    <span className="font-mono font-medium">{acc.name}</span>{' '}
                    <span className="text-slate-400">({acc.role})</span>
                  </motion.button>
                ))}
              </div>
              <p className="mt-3 text-xs text-slate-400 dark:text-slate-500">
                Les mots de passe initiaux sont générés lors du premier lancement du script d'initialisation.
              </p>
            </div>
          </div>
        </motion.div>
      </div>
    </div>
  )
}
