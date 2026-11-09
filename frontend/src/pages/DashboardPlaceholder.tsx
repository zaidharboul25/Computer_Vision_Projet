import React, { useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import { motion } from 'framer-motion'
import {
  PlusCircle,
  History,
  Sparkles,
  Activity,
  FileCheck,
  Layers,
  ArrowUpRight,
  BarChart3,
  ScanSearch,
} from 'lucide-react'
import { PieChart, Pie, Cell, ResponsiveContainer, BarChart, Bar, XAxis, YAxis, Tooltip, CartesianGrid } from 'recharts'
import { useAuth } from '../context/AuthContext'
import { RoleBadge } from '../components/common/RoleBadge'
import { apiFetch } from '../services/api'
import type { SummaryStats } from '../types'
import { DashboardSkeleton } from '../components/ui/Skeleton'
import { AnimatedNumber, Stagger, StaggerItem, EASE } from '../components/ui/motion'

const greeting = () => {
  const h = new Date().getHours()
  if (h < 6) return 'Bonne nuit'
  if (h < 18) return 'Bonjour'
  return 'Bonsoir'
}

interface StatProps {
  label: string
  value: number
  hint: string
  icon: React.ElementType
  tone: 'brand' | 'blue' | 'violet' | 'emerald'
}

const TONES = {
  brand: 'from-brand-500/15 to-brand-500/0 text-brand-600 dark:text-brand-300',
  blue: 'from-blue-500/15 to-blue-500/0 text-blue-600 dark:text-blue-300',
  violet: 'from-violet-500/15 to-violet-500/0 text-violet-600 dark:text-violet-300',
  emerald: 'from-emerald-500/15 to-emerald-500/0 text-emerald-600 dark:text-emerald-300',
} as const

const StatCard: React.FC<StatProps> = ({ label, value, hint, icon: Icon, tone }) => (
  <motion.div
    whileHover={{ y: -4 }}
    transition={{ type: 'spring', stiffness: 380, damping: 26 }}
    className="card card-hover group overflow-hidden p-5"
  >
    <div className={`pointer-events-none absolute inset-0 bg-gradient-to-br opacity-70 transition-opacity group-hover:opacity-100 ${TONES[tone]}`} />
    <div className="relative flex items-center justify-between">
      <span className="eyebrow">{label}</span>
      <span className={`flex h-10 w-10 items-center justify-center rounded-xl bg-white shadow-sm ring-1 ring-slate-200/70 transition-transform duration-300 group-hover:rotate-6 group-hover:scale-110 dark:bg-white/10 dark:ring-white/10 ${TONES[tone].split(' ').slice(-2).join(' ')}`}>
        <Icon className="h-5 w-5" />
      </span>
    </div>
    <div className="relative mt-4 text-4xl font-extrabold tracking-tight text-slate-900 tabular-nums dark:text-white">
      <AnimatedNumber value={value} />
    </div>
    <div className="relative mt-1.5 text-xs text-slate-500 dark:text-slate-400">{hint}</div>
  </motion.div>
)

const ChartTooltip: React.FC<{ active?: boolean; payload?: Array<{ name: string; value: number }>; label?: string }> = ({ active, payload, label }) => {
  if (!active || !payload?.length) return null
  return (
    <div className="rounded-xl border border-slate-200 bg-white/95 px-3 py-2 text-xs shadow-lg backdrop-blur dark:border-white/10 dark:bg-ink-800/95">
      <div className="font-semibold text-slate-900 dark:text-white">{label ?? payload[0].name}</div>
      <div className="text-slate-600 dark:text-slate-300">{payload[0].value}</div>
    </div>
  )
}

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

  const canCreate = hasRole(['operator', 'supervisor', 'admin'])

  if (loading) return <DashboardSkeleton />

  const reviewData = stats
    ? [
        { name: 'Confirmées', value: stats.reviews.confirmed, color: '#10b981' },
        { name: 'Rejetées', value: stats.reviews.rejected, color: '#f43f5e' },
        { name: 'À réviser', value: stats.reviews.unreviewed, color: '#f59e0b' },
      ]
    : []
  const reviewTotal = reviewData.reduce((a, b) => a + b.value, 0)
  const engineData = stats
    ? [
        { name: 'YOLO', value: stats.regions.yolo, color: '#3b82f6' },
        { name: 'PatchCore', value: stats.regions.patchcore, color: '#8b5cf6' },
      ]
    : []

  return (
    <div className="space-y-6">
      {/* ===== Hero ===== */}
      <motion.section
        initial={{ opacity: 0, y: 20 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ duration: 0.6, ease: EASE }}
        className="relative overflow-hidden rounded-3xl bg-gradient-to-br from-brand-600 via-brand-700 to-violet-800 p-7 text-white shadow-lift sm:p-9"
      >
        <div className="grid-bg absolute inset-0 opacity-60" aria-hidden="true" />
        <div className="absolute -right-16 -top-16 h-64 w-64 animate-drift rounded-full bg-cyan-400/30 blur-3xl" aria-hidden="true" />
        <div className="absolute -bottom-20 left-1/3 h-56 w-56 animate-drift rounded-full bg-violet-400/30 blur-3xl [animation-delay:-8s]" aria-hidden="true" />
        <ScanSearch className="absolute -right-4 bottom-0 hidden h-52 w-52 animate-float text-white/10 md:block" aria-hidden="true" />

        <div className="relative flex flex-col justify-between gap-6 sm:flex-row sm:items-end">
          <div>
            <p className="text-sm font-medium text-brand-100">{greeting()},</p>
            <h1 className="mt-1 text-3xl font-extrabold tracking-tight sm:text-4xl">
              Tableau de bord WeaveGuard AI
            </h1>
            <p className="mt-3 flex flex-wrap items-center gap-2 text-sm text-brand-100">
              Bienvenue, <span className="font-semibold text-white">{user?.username}</span>
              {user && <RoleBadge role={user.role} />}
            </p>
          </div>

          {canCreate && (
            <Link
              to="/inspections/new"
              className="group inline-flex items-center gap-2 self-start rounded-xl bg-white px-5 py-3 text-sm font-bold text-brand-700 shadow-xl shadow-brand-950/30 transition-all duration-200 hover:-translate-y-0.5 hover:shadow-2xl active:scale-[0.97] sm:self-auto"
            >
              <PlusCircle className="h-4 w-4 transition-transform duration-300 group-hover:rotate-90" />
              Nouvelle inspection
            </Link>
          )}
        </div>
      </motion.section>

      {stats && (
        <>
          <Stagger className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-4">
            <StaggerItem>
              <StatCard
                label="Inspections totales"
                value={stats.inspections.total}
                hint={`${stats.inspections.done} terminées · ${stats.inspections.pending} en attente`}
                icon={Activity}
                tone="brand"
              />
            </StaggerItem>
            <StaggerItem>
              <StatCard label="Défauts YOLO" value={stats.regions.yolo} hint="Détections supervisées" icon={Layers} tone="blue" />
            </StaggerItem>
            <StaggerItem>
              <StatCard label="Anomalies PatchCore" value={stats.regions.patchcore} hint="Régions hors distribution" icon={Sparkles} tone="violet" />
            </StaggerItem>
            <StaggerItem>
              <StatCard
                label="Revues confirmées"
                value={stats.reviews.confirmed}
                hint={`${stats.reviews.rejected} rejetées · ${stats.reviews.unreviewed} à réviser`}
                icon={FileCheck}
                tone="emerald"
              />
            </StaggerItem>
          </Stagger>

          <div className="grid gap-6 lg:grid-cols-3">
            <motion.div
              initial={{ opacity: 0, y: 20 }}
              animate={{ opacity: 1, y: 0 }}
              transition={{ duration: 0.55, ease: EASE, delay: 0.25 }}
              className="card p-6 lg:col-span-2"
            >
              <div className="flex items-center justify-between">
                <div>
                  <h2 className="text-base font-bold text-slate-900 dark:text-white">Régions détectées par moteur</h2>
                  <p className="mt-0.5 text-xs text-slate-500 dark:text-slate-400">Répartition supervisé vs. anomalies</p>
                </div>
                <BarChart3 className="h-5 w-5 text-slate-400" />
              </div>
              <div className="mt-5 h-56">
                <ResponsiveContainer width="100%" height="100%">
                  <BarChart data={engineData} barSize={56} margin={{ top: 8, right: 8, left: -16, bottom: 0 }}>
                    <CartesianGrid strokeDasharray="3 3" vertical={false} stroke="currentColor" className="text-slate-200 dark:text-white/10" />
                    <XAxis dataKey="name" tickLine={false} axisLine={false} tick={{ fontSize: 12, fill: '#94a3b8' }} />
                    <YAxis allowDecimals={false} tickLine={false} axisLine={false} tick={{ fontSize: 12, fill: '#94a3b8' }} />
                    <Tooltip content={<ChartTooltip />} cursor={{ fill: 'rgb(99 102 241 / 0.08)' }} />
                    <Bar dataKey="value" radius={[10, 10, 0, 0]} animationDuration={1100}>
                      {engineData.map((d) => (
                        <Cell key={d.name} fill={d.color} />
                      ))}
                    </Bar>
                  </BarChart>
                </ResponsiveContainer>
              </div>
            </motion.div>

            <motion.div
              initial={{ opacity: 0, y: 20 }}
              animate={{ opacity: 1, y: 0 }}
              transition={{ duration: 0.55, ease: EASE, delay: 0.35 }}
              className="card p-6"
            >
              <h2 className="text-base font-bold text-slate-900 dark:text-white">Revues humaines</h2>
              <p className="mt-0.5 text-xs text-slate-500 dark:text-slate-400">Statut des décisions</p>
              <div className="relative mx-auto mt-3 h-40 w-40">
                <ResponsiveContainer width="100%" height="100%">
                  <PieChart>
                    <Pie
                      data={reviewTotal ? reviewData : [{ name: 'Aucune', value: 1, color: '#cbd5e1' }]}
                      dataKey="value"
                      innerRadius={52}
                      outerRadius={72}
                      paddingAngle={reviewTotal ? 3 : 0}
                      stroke="none"
                      animationDuration={1100}
                    >
                      {(reviewTotal ? reviewData : [{ name: 'Aucune', value: 1, color: '#cbd5e1' }]).map((d) => (
                        <Cell key={d.name} fill={d.color} />
                      ))}
                    </Pie>
                  </PieChart>
                </ResponsiveContainer>
                <div className="pointer-events-none absolute inset-0 flex flex-col items-center justify-center">
                  <span className="text-2xl font-extrabold tabular-nums text-slate-900 dark:text-white">
                    <AnimatedNumber value={reviewTotal} />
                  </span>
                  <span className="text-[10px] font-semibold uppercase tracking-wider text-slate-500">régions</span>
                </div>
              </div>
              <ul className="mt-4 space-y-1.5 text-xs">
                {reviewData.map((d) => (
                  <li key={d.name} className="flex items-center justify-between">
                    <span className="flex items-center gap-2 text-slate-600 dark:text-slate-300">
                      <span className="h-2.5 w-2.5 rounded-full" style={{ background: d.color }} />
                      {d.name}
                    </span>
                    <span className="font-semibold tabular-nums text-slate-900 dark:text-white">{d.value}</span>
                  </li>
                ))}
              </ul>
            </motion.div>
          </div>
        </>
      )}

      {/* ===== Accès rapide ===== */}
      <section>
        <h2 className="mb-3 text-base font-bold text-slate-900 dark:text-white">Accès rapide</h2>
        <Stagger className="grid grid-cols-1 gap-4 sm:grid-cols-3">
          {[
            { to: '/inspections', icon: History, color: 'text-blue-600 dark:text-blue-300', bg: 'bg-blue-50 dark:bg-blue-500/15', title: "Consulter l'historique", text: 'Filtrer par statut, utilisateur et date' },
            { to: '/similarity', icon: Sparkles, color: 'text-violet-600 dark:text-violet-300', bg: 'bg-violet-50 dark:bg-violet-500/15', title: 'Recherche de similarité', text: 'Galeries textile et DTD générique' },
            { to: '/models', icon: Activity, color: 'text-emerald-600 dark:text-emerald-300', bg: 'bg-emerald-50 dark:bg-emerald-500/15', title: 'Fiches modèles IA', text: 'Métriques validées et biais de domaine' },
          ].map((q) => (
            <StaggerItem key={q.to}>
              <Link to={q.to} className="card card-hover group flex items-center gap-4 p-4">
                <span className={`flex h-12 w-12 flex-shrink-0 items-center justify-center rounded-xl transition-transform duration-300 group-hover:scale-110 group-hover:-rotate-6 ${q.bg} ${q.color}`}>
                  <q.icon className="h-6 w-6" />
                </span>
                <div className="min-w-0 flex-1">
                  <div className="text-sm font-semibold text-slate-900 dark:text-white">{q.title}</div>
                  <div className="text-xs text-slate-500 dark:text-slate-400">{q.text}</div>
                </div>
                <ArrowUpRight className="h-4 w-4 text-slate-300 transition-all duration-300 group-hover:-translate-y-0.5 group-hover:translate-x-0.5 group-hover:text-brand-500" />
              </Link>
            </StaggerItem>
          ))}
        </Stagger>
      </section>
    </div>
  )
}
