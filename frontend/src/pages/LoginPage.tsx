import React, { useState } from 'react'
import { useNavigate, useLocation } from 'react-router-dom'
import { ShieldCheck, Lock, User, ArrowRight } from 'lucide-react'
import { useAuth } from '../context/AuthContext'
import { apiFetch } from '../services/api'
import { ErrorAlert } from '../components/common/ErrorAlert'
import type { UserRole } from '../types'

export const LoginPage: React.FC = () => {
  const [username, setUsername] = useState('')
  const [password, setPassword] = useState('')
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<unknown>(null)

  const { login } = useAuth()
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
    <div className="flex min-h-screen flex-col justify-center bg-slate-100 py-12 sm:px-6 lg:px-8 dark:bg-slate-950">
      <div className="sm:mx-auto sm:w-full sm:max-w-md">
        <div className="mx-auto flex h-14 w-14 items-center justify-center rounded-xl bg-blue-600 text-white shadow-md">
          <ShieldCheck className="h-8 w-8" />
        </div>
        <h1 className="mt-4 text-center text-2xl font-extrabold tracking-tight text-slate-900 dark:text-white">
          WeaveGuard <span className="text-blue-600 dark:text-blue-400">AI</span>
        </h1>
        <p className="mt-1 text-center text-sm text-slate-600 dark:text-slate-400">
          Plateforme d'inspection textile industrielle par vision par ordinateur
        </p>
      </div>

      <div className="mt-8 sm:mx-auto sm:w-full sm:max-w-md">
        <div className="rounded-xl border border-slate-200 bg-white px-6 py-8 shadow-sm sm:px-10 dark:border-slate-800 dark:bg-slate-900">
          <form className="space-y-5" onSubmit={handleSubmit}>
            {Boolean(error) && <ErrorAlert error={error} onDismiss={() => setError(null)} />}

            <div>
              <label
                htmlFor="username"
                className="block text-sm font-medium text-slate-700 dark:text-slate-300"
              >
                Identifiant
              </label>
              <div className="relative mt-1.5 rounded-md shadow-sm">
                <div className="pointer-events-none absolute inset-y-0 left-0 flex items-center pl-3">
                  <User className="h-4 w-4 text-slate-400" aria-hidden="true" />
                </div>
                <input
                  id="username"
                  name="username"
                  type="text"
                  autoComplete="username"
                  required
                  value={username}
                  onChange={(e) => setUsername(e.target.value)}
                  placeholder="ex: demo_operator"
                  className="block w-full rounded-lg border border-slate-300 bg-white pl-10 pr-3 py-2 text-sm text-slate-900 placeholder-slate-400 focus:border-blue-500 focus:outline-none focus:ring-1 focus:ring-blue-500 dark:border-slate-700 dark:bg-slate-800 dark:text-white dark:placeholder-slate-500"
                />
              </div>
            </div>

            <div>
              <label
                htmlFor="password"
                className="block text-sm font-medium text-slate-700 dark:text-slate-300"
              >
                Mot de passe
              </label>
              <div className="relative mt-1.5 rounded-md shadow-sm">
                <div className="pointer-events-none absolute inset-y-0 left-0 flex items-center pl-3">
                  <Lock className="h-4 w-4 text-slate-400" aria-hidden="true" />
                </div>
                <input
                  id="password"
                  name="password"
                  type="password"
                  autoComplete="current-password"
                  required
                  value={password}
                  onChange={(e) => setPassword(e.target.value)}
                  placeholder="••••••••••••"
                  className="block w-full rounded-lg border border-slate-300 bg-white pl-10 pr-3 py-2 text-sm text-slate-900 placeholder-slate-400 focus:border-blue-500 focus:outline-none focus:ring-1 focus:ring-blue-500 dark:border-slate-700 dark:bg-slate-800 dark:text-white dark:placeholder-slate-500"
                />
              </div>
            </div>

            <div>
              <button
                type="submit"
                disabled={loading}
                className="flex w-full items-center justify-center gap-2 rounded-lg bg-blue-600 px-4 py-2.5 text-sm font-semibold text-white shadow-sm hover:bg-blue-500 focus:outline-none focus:ring-2 focus:ring-blue-500 focus:ring-offset-2 disabled:opacity-50 dark:focus:ring-offset-slate-900"
              >
                {loading ? 'Connexion en cours...' : 'Se connecter'}
                {!loading && <ArrowRight className="h-4 w-4" />}
              </button>
            </div>
          </form>

          {/* Guide des comptes de démonstration */}
          <div className="mt-6 border-t border-slate-200 pt-5 dark:border-slate-800">
            <h2 className="text-xs font-semibold uppercase tracking-wider text-slate-500 dark:text-slate-400">
              Comptes configurés en démonstration :
            </h2>
            <div className="mt-2.5 flex flex-wrap gap-1.5">
              {demoAccounts.map((acc) => (
                <button
                  key={acc.name}
                  type="button"
                  onClick={() => setUsername(acc.name)}
                  className="rounded border border-slate-200 bg-slate-50 px-2 py-1 text-xs text-slate-700 hover:bg-slate-100 hover:text-blue-600 dark:border-slate-700 dark:bg-slate-800 dark:text-slate-300 dark:hover:bg-slate-700"
                  title={`Pré-remplir l'identifiant ${acc.name}`}
                >
                  <span className="font-mono font-medium">{acc.name}</span>{' '}
                  <span className="text-slate-400">({acc.role})</span>
                </button>
              ))}
            </div>
            <p className="mt-2 text-xs text-slate-400 dark:text-slate-500">
              Les mots de passe initiaux sont générés lors du premier lancement du script d'initialisation.
            </p>
          </div>
        </div>
      </div>
    </div>
  )
}
