import React, { useEffect, useState, useCallback } from 'react'
import {
  Shield,
  Users,
  FileSpreadsheet,
  Settings,
  PlusCircle,
  Search,
  RotateCcw,
  ChevronLeft,
  ChevronRight,
  CheckCircle2,
  AlertCircle,
  UserCheck,
  UserX,
} from 'lucide-react'
import { listAuditLogs, listUsers, createUser, updateUser } from '../services/api'
import type { AuditLogItem, UserResponse, UserRole } from '../types'
import { LoadingSpinner } from '../components/common/LoadingSpinner'
import { SkeletonRegion, TableSkeleton } from '../components/ui/Skeleton'
import { ErrorAlert } from '../components/common/ErrorAlert'
import { RoleBadge } from '../components/common/RoleBadge'
import { useAuth } from '../context/AuthContext'

const PAGE_SIZE = 25

export const AdminAuditPage: React.FC = () => {
  const { user: currentUser, hasRole } = useAuth()
  const [activeTab, setActiveTab] = useState<'audit' | 'users' | 'settings'>('audit')

  // --- Audit State ---
  const [auditLogs, setAuditLogs] = useState<AuditLogItem[]>([])
  const [auditTotal, setAuditTotal] = useState(0)
  const [auditLoading, setAuditLoading] = useState(true)
  const [auditError, setAuditError] = useState<unknown | null>(null)
  const [auditPage, setAuditPage] = useState(0)
  const [auditActionFilter, setAuditActionFilter] = useState('')
  const [auditUserFilter, setAuditUserFilter] = useState('')

  // --- Users State ---
  const [users, setUsers] = useState<UserResponse[]>([])
  const [usersLoading, setUsersLoading] = useState(false)
  const [usersError, setUsersError] = useState<unknown | null>(null)
  const [showCreateModal, setShowCreateModal] = useState(false)
  const [createUsername, setCreateUsername] = useState('')
  const [createPassword, setCreatePassword] = useState('')
  const [createRole, setCreateRole] = useState<UserRole>('operator')
  const [createSubmitting, setCreateSubmitting] = useState(false)
  const [createError, setCreateError] = useState<unknown | null>(null)

  // Fetch Audit Logs
  const fetchAudit = useCallback(async () => {
    setAuditLoading(true)
    setAuditError(null)
    try {
      const res = await listAuditLogs({
        skip: auditPage * PAGE_SIZE,
        limit: PAGE_SIZE,
        action: auditActionFilter || undefined,
        username: auditUserFilter.trim() || undefined,
      })
      setAuditLogs(res.items || [])
      setAuditTotal(res.total || 0)
    } catch (err) {
      setAuditError(err)
    } finally {
      setAuditLoading(false)
    }
  }, [auditPage, auditActionFilter, auditUserFilter])

  // Fetch Users
  const fetchUsers = useCallback(async () => {
    if (!hasRole(['admin'])) return
    setUsersLoading(true)
    setUsersError(null)
    try {
      const data = await listUsers(0, 100)
      setUsers(data || [])
    } catch (err) {
      setUsersError(err)
    } finally {
      setUsersLoading(false)
    }
  }, [hasRole])

  useEffect(() => {
    if (activeTab === 'audit') {
      fetchAudit()
    } else if (activeTab === 'users') {
      fetchUsers()
    }
  }, [activeTab, fetchAudit, fetchUsers])

  const handleCreateUser = async (e: React.FormEvent) => {
    e.preventDefault()
    setCreateSubmitting(true)
    setCreateError(null)
    try {
      await createUser({
        username: createUsername.trim(),
        password: createPassword,
        role: createRole,
      })
      setShowCreateModal(false)
      setCreateUsername('')
      setCreatePassword('')
      setCreateRole('operator')
      await fetchUsers()
    } catch (err) {
      setCreateError(err)
    } finally {
      setCreateSubmitting(false)
    }
  }

  const handleToggleUserActive = async (u: UserResponse) => {
    try {
      await updateUser(u.id, { active: !u.active })
      await fetchUsers()
    } catch (err) {
      setUsersError(err)
    }
  }

  const auditTotalPages = Math.ceil(auditTotal / PAGE_SIZE)

  return (
    <div className="stagger space-y-6">
      {/* En-tête */}
      <div className="flex flex-col justify-between gap-4 sm:flex-row sm:items-center">
        <div>
          <div className="flex items-center gap-2">
            <Shield className="h-6 w-6 text-blue-600 dark:text-blue-400" />
            <h1 className="text-2xl font-bold tracking-tight text-slate-900 dark:text-white">
              Administration & Audit
            </h1>
          </div>
          <p className="mt-1 text-sm text-slate-500 dark:text-slate-400">
            Traçabilité des actions critiques, gestion des accès et paramètres de conformité industrielle.
          </p>
        </div>

        {activeTab === 'users' && hasRole(['admin']) && (
          <button
            type="button"
            onClick={() => setShowCreateModal(true)}
            className="btn-primary !py-2"
          >
            <PlusCircle className="h-4 w-4" />
            Créer un utilisateur
          </button>
        )}
      </div>

      {/* Onglets */}
      <div className="border-b border-slate-200 dark:border-slate-800">
        <nav className="-mb-px flex space-x-8">
          <button
            type="button"
            onClick={() => setActiveTab('audit')}
            className={`flex items-center gap-2 border-b-2 py-3 px-1 text-sm font-medium transition ${
              activeTab === 'audit'
                ? 'border-blue-600 text-blue-600 dark:border-blue-400 dark:text-blue-400'
                : 'border-transparent text-slate-500 hover:border-slate-300 hover:text-slate-700 dark:text-slate-400 dark:hover:text-slate-300'
            }`}
          >
            <FileSpreadsheet className="h-4 w-4" />
            Journal d'audit
          </button>

          <button
            type="button"
            onClick={() => setActiveTab('users')}
            className={`flex items-center gap-2 border-b-2 py-3 px-1 text-sm font-medium transition ${
              activeTab === 'users'
                ? 'border-blue-600 text-blue-600 dark:border-blue-400 dark:text-blue-400'
                : 'border-transparent text-slate-500 hover:border-slate-300 hover:text-slate-700 dark:text-slate-400 dark:hover:text-slate-300'
            }`}
          >
            <Users className="h-4 w-4" />
            Utilisateurs & Rôles
          </button>

          <button
            type="button"
            onClick={() => setActiveTab('settings')}
            className={`flex items-center gap-2 border-b-2 py-3 px-1 text-sm font-medium transition ${
              activeTab === 'settings'
                ? 'border-blue-600 text-blue-600 dark:border-blue-400 dark:text-blue-400'
                : 'border-transparent text-slate-500 hover:border-slate-300 hover:text-slate-700 dark:text-slate-400 dark:hover:text-slate-300'
            }`}
          >
            <Settings className="h-4 w-4" />
            Paramètres & Sécurité
          </button>
        </nav>
      </div>

      {/* --- TAB 1: JOURNAL D'AUDIT --- */}
      {activeTab === 'audit' && (
        <div className="space-y-4">
          {/* Barre de filtres audit */}
          <div className="card p-4">
            <div className="grid grid-cols-1 gap-4 sm:grid-cols-3">
              <div>
                <label htmlFor="audit-user" className="block text-xs font-medium text-slate-700 dark:text-slate-300">
                  Filtrer par utilisateur
                </label>
                <div className="relative mt-1">
                  <input
                    id="audit-user"
                    type="text"
                    placeholder="Ex: admin, operator1..."
                    value={auditUserFilter}
                    onChange={(e) => {
                      setAuditUserFilter(e.target.value)
                      setAuditPage(0)
                    }}
                    className="input !py-2 !pl-9"
                  />
                  <Search className="pointer-events-none absolute left-2.5 top-2.5 h-3.5 w-3.5 text-slate-400" />
                </div>
              </div>

              <div>
                <label htmlFor="audit-action" className="block text-xs font-medium text-slate-700 dark:text-slate-300">
                  Action consignée
                </label>
                <select
                  id="audit-action"
                  value={auditActionFilter}
                  onChange={(e) => {
                    setAuditActionFilter(e.target.value)
                    setAuditPage(0)
                  }}
                  className="input !py-2"
                >
                  <option value="">Toutes les actions</option>
                  <option value="LOGIN">LOGIN (Connexion)</option>
                  <option value="LOGIN_FAILED">LOGIN_FAILED (Échec de connexion)</option>
                  <option value="LOGOUT">LOGOUT (Déconnexion)</option>
                  <option value="INSPECTION_CREATED">INSPECTION_CREATED (Création inspection)</option>
                  <option value="FEEDBACK_SUBMITTED">FEEDBACK_SUBMITTED (Revue soumise)</option>
                  <option value="USER_CREATED">USER_CREATED (Création compte)</option>
                  <option value="USER_UPDATED">USER_UPDATED (Modification compte)</option>
                </select>
              </div>

              <div className="flex items-end">
                <button
                  type="button"
                  onClick={() => {
                    setAuditActionFilter('')
                    setAuditUserFilter('')
                    setAuditPage(0)
                  }}
                  className="btn-secondary w-full !py-1.5 disabled:opacity-40"
                >
                  <RotateCcw className="h-4 w-4" />
                  Réinitialiser
                </button>
              </div>
            </div>
          </div>

          {auditError ? <ErrorAlert error={auditError} /> : null}

          {/* Tableau d'audit */}
          <div className="card overflow-hidden">
            {auditLoading ? (
              <SkeletonRegion label="Chargement des événements d'audit...">
                <TableSkeleton rows={9} cols={5} />
              </SkeletonRegion>
            ) : auditLogs.length === 0 ? (
              <div className="py-16 text-center text-sm text-slate-500 dark:text-slate-400">
                Aucun événement d'audit enregistré correspondant.
              </div>
            ) : (
              <div className="overflow-x-auto">
                <table className="w-full text-left text-sm text-slate-600 dark:text-slate-300">
                  <thead className="table-head">
                    <tr>
                      <th scope="col" className="px-5 py-3 font-semibold">Horodatage</th>
                      <th scope="col" className="px-5 py-3 font-semibold">Utilisateur</th>
                      <th scope="col" className="px-5 py-3 font-semibold">Action</th>
                      <th scope="col" className="px-5 py-3 font-semibold">Détails</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-slate-200 dark:divide-slate-800 font-mono text-xs">
                    {auditLogs.map((log: AuditLogItem) => (
                      <tr key={log._id} className="table-row">
                        <td className="px-5 py-3 whitespace-nowrap text-slate-500 dark:text-slate-400">
                          {new Date(log.at).toLocaleString('fr-FR', {
                            day: '2-digit',
                            month: '2-digit',
                            year: 'numeric',
                            hour: '2-digit',
                            minute: '2-digit',
                            second: '2-digit',
                          })}
                        </td>
                        <td className="px-5 py-3 font-sans font-medium text-slate-900 dark:text-white">
                          {log.username || 'Système'}
                        </td>
                        <td className="px-5 py-3">
                          <span className={`inline-flex items-center rounded px-2 py-0.5 text-[11px] font-semibold ${
                            log.action.includes('FAILED')
                              ? 'bg-rose-50 text-rose-700 dark:bg-rose-950/60 dark:text-rose-300'
                              : log.action.includes('CREATED')
                              ? 'bg-blue-50 text-blue-700 dark:bg-blue-950/60 dark:text-blue-300'
                              : log.action.includes('FEEDBACK')
                              ? 'bg-emerald-50 text-emerald-700 dark:bg-emerald-950/60 dark:text-emerald-300'
                              : 'bg-slate-100 text-slate-700 dark:bg-slate-800 dark:text-slate-300'
                          }`}>
                            {log.action}
                          </span>
                        </td>
                        <td className="px-5 py-3 font-sans text-xs text-slate-600 dark:text-slate-300 max-w-xs truncate" title={JSON.stringify(log.details || {})}>
                          {log.details ? JSON.stringify(log.details) : '—'}
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            )}

            {/* Pagination */}
            {!auditLoading && auditTotal > 0 && (
              <div className="flex items-center justify-between border-t border-slate-200 bg-slate-50/50 px-5 py-3 text-xs text-slate-500 dark:border-slate-800 dark:bg-slate-800/30 dark:text-slate-400">
                <div>Total : {auditTotal} événements</div>
                <div className="flex items-center gap-2">
                  <button
                    type="button"
                    onClick={() => setAuditPage((p) => Math.max(p - 1, 0))}
                    disabled={auditPage === 0}
                    className="rounded border border-slate-200 bg-white px-2 py-1 disabled:opacity-40 dark:border-slate-700 dark:bg-slate-800"
                  >
                    <ChevronLeft className="h-3.5 w-3.5" />
                  </button>
                  <span>Page {auditPage + 1} / {auditTotalPages || 1}</span>
                  <button
                    type="button"
                    onClick={() => setAuditPage((p) => Math.min(p + 1, auditTotalPages - 1))}
                    disabled={auditPage >= auditTotalPages - 1}
                    className="rounded border border-slate-200 bg-white px-2 py-1 disabled:opacity-40 dark:border-slate-700 dark:bg-slate-800"
                  >
                    <ChevronRight className="h-3.5 w-3.5" />
                  </button>
                </div>
              </div>
            )}
          </div>
        </div>
      )}

      {/* --- TAB 2: UTILISATEURS & RÔLES --- */}
      {activeTab === 'users' && (
        <div className="space-y-4">
          {!hasRole(['admin']) ? (
            <div className="rounded-xl border border-slate-200 bg-amber-50/40 p-6 text-sm text-amber-800 dark:border-slate-800 dark:bg-amber-950/20 dark:text-amber-300">
              <h3 className="font-semibold flex items-center gap-2">
                <AlertCircle className="h-4 w-4" />
                Accès restreint en lecture
              </h3>
              <p className="mt-1">
                La gestion et la création de comptes utilisateurs nécessitent les privilèges <strong>Administrateur</strong>.
              </p>
            </div>
          ) : (
            <>
              {usersError ? <ErrorAlert error={usersError} /> : null}

              <div className="card overflow-hidden">
                {usersLoading ? (
                  <SkeletonRegion label="Chargement des utilisateurs...">
                    <TableSkeleton rows={6} cols={5} />
                  </SkeletonRegion>
                ) : (
                  <table className="w-full text-left text-sm text-slate-600 dark:text-slate-300">
                    <thead className="table-head">
                      <tr>
                        <th scope="col" className="px-5 py-3.5 font-semibold">Nom d'utilisateur</th>
                        <th scope="col" className="px-5 py-3.5 font-semibold">Rôle</th>
                        <th scope="col" className="px-5 py-3.5 font-semibold">Statut</th>
                        <th scope="col" className="px-5 py-3.5 font-semibold">Création</th>
                        <th scope="col" className="px-5 py-3.5 text-right font-semibold">Action</th>
                      </tr>
                    </thead>
                    <tbody className="divide-y divide-slate-200 dark:divide-slate-800">
                      {users.map((u) => (
                        <tr key={u.id} className="table-row">
                          <td className="px-5 py-3.5 font-medium text-slate-900 dark:text-white">
                            {u.username}
                            {u.username === currentUser?.username && (
                              <span className="ml-2 text-xs text-blue-600 dark:text-blue-400">(vous)</span>
                            )}
                          </td>
                          <td className="px-5 py-3.5">
                            <RoleBadge role={u.role as UserRole} />
                          </td>
                          <td className="px-5 py-3.5">
                            {u.active ? (
                              <span className="inline-flex items-center gap-1 text-xs font-medium text-emerald-600 dark:text-emerald-400">
                                <CheckCircle2 className="h-3.5 w-3.5" />
                                Actif
                              </span>
                            ) : (
                              <span className="inline-flex items-center gap-1 text-xs font-medium text-rose-600 dark:text-rose-400">
                                <AlertCircle className="h-3.5 w-3.5" />
                                Désactivé
                              </span>
                            )}
                          </td>
                          <td className="px-5 py-3.5 text-xs text-slate-500 dark:text-slate-400">
                            {new Date(u.created_at).toLocaleDateString('fr-FR')}
                          </td>
                          <td className="px-5 py-3.5 text-right">
                            {u.username !== currentUser?.username && (
                              <button
                                type="button"
                                onClick={() => handleToggleUserActive(u)}
                                className={`inline-flex items-center gap-1 rounded-lg border px-2.5 py-1 text-xs font-medium transition ${
                                  u.active
                                    ? 'border-rose-200 text-rose-700 hover:bg-rose-50 dark:border-rose-800 dark:text-rose-300 dark:hover:bg-rose-950/40'
                                    : 'border-emerald-200 text-emerald-700 hover:bg-emerald-50 dark:border-emerald-800 dark:text-emerald-300 dark:hover:bg-emerald-950/40'
                                }`}
                              >
                                {u.active ? (
                                  <>
                                    <UserX className="h-3.5 w-3.5" />
                                    Désactiver
                                  </>
                                ) : (
                                  <>
                                    <UserCheck className="h-3.5 w-3.5" />
                                    Activer
                                  </>
                                )}
                              </button>
                            )}
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                )}
              </div>
            </>
          )}
        </div>
      )}

      {/* --- TAB 3: PARAMÈTRES & SÉCURITÉ --- */}
      {activeTab === 'settings' && (
        <div className="grid grid-cols-1 gap-6 lg:grid-cols-2">
          <div className="card p-6 space-y-4">
            <h3 className="text-base font-bold text-slate-900 dark:text-white flex items-center gap-2">
              <Shield className="h-5 w-5 text-blue-600 dark:text-blue-400" />
              Politique de Sécurité & Sessions
            </h3>
            <div className="space-y-3 text-xs text-slate-600 dark:text-slate-300">
              <div className="flex justify-between py-2 border-b border-slate-100 dark:border-slate-800">
                <span>Durée de validité du jeton JWT</span>
                <strong className="text-slate-800 dark:text-slate-200">8 heures (480 minutes)</strong>
              </div>
              <div className="flex justify-between py-2 border-b border-slate-100 dark:border-slate-800">
                <span>Verrouillage automatique après échecs</span>
                <strong className="text-slate-800 dark:text-slate-200">5 tentatives consécutives</strong>
              </div>
              <div className="flex justify-between py-2 border-b border-slate-100 dark:border-slate-800">
                <span>Algorithme de hachage de mot de passe</span>
                <strong className="font-mono text-slate-800 dark:text-slate-200">bcrypt (rounds=12)</strong>
              </div>
              <div className="flex justify-between py-2">
                <span>Taille maximale des fichiers d'image</span>
                <strong className="text-slate-800 dark:text-slate-200">15 Mo (max_image_size_bytes)</strong>
              </div>
            </div>
          </div>

          <div className="card p-6 space-y-4">
            <h3 className="text-base font-bold text-slate-900 dark:text-white flex items-center gap-2">
              <FileSpreadsheet className="h-5 w-5 text-purple-600 dark:text-purple-400" />
              Conformité & Archivage
            </h3>
            <p className="text-xs text-slate-500 dark:text-slate-400 leading-relaxed">
              Toutes les inspections, modifications de feedback et actions d'authentification sont stockées de façon persistante dans MongoDB avec identifiant de corrélation unique (<code>X-Correlation-ID</code>).
            </p>
            <div className="rounded-xl bg-slate-50 p-3.5 text-xs dark:bg-slate-800/40 space-y-2">
              <div className="font-semibold text-slate-700 dark:text-slate-300">
                Règle de rétention :
              </div>
              <p className="text-slate-500 dark:text-slate-400">
                Les inspections sont conservées pendant toute la durée opérationnelle requise par l'assurance qualité textile. La purge de maintenance peut être exécutée via le script certifié <code>scripts/retention.py</code>.
              </p>
            </div>
          </div>
        </div>
      )}

      {/* Modal Créer Utilisateur */}
      {showCreateModal && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/50 p-4 backdrop-blur-sm">
          <div className="w-full max-w-md rounded-2xl border border-slate-200 bg-white p-6 shadow-xl dark:border-slate-800 dark:bg-slate-900">
            <h3 className="text-lg font-bold text-slate-900 dark:text-white">
              Créer un nouvel utilisateur
            </h3>

            {createError ? <div className="mt-3"><ErrorAlert error={createError} /></div> : null}

            <form onSubmit={handleCreateUser} className="mt-4 space-y-4">
              <div>
                <label className="block text-xs font-semibold text-slate-700 dark:text-slate-300">
                  Nom d'utilisateur
                </label>
                <input
                  type="text"
                  required
                  value={createUsername}
                  onChange={(e) => setCreateUsername(e.target.value)}
                  placeholder="Ex: operator2"
                  className="input !py-2"
                />
              </div>

              <div>
                <label className="block text-xs font-semibold text-slate-700 dark:text-slate-300">
                  Mot de passe (8 car. min, 1 majuscule, 1 chiffre)
                </label>
                <input
                  type="password"
                  required
                  value={createPassword}
                  onChange={(e) => setCreatePassword(e.target.value)}
                  placeholder="••••••••"
                  className="input !py-2"
                />
              </div>

              <div>
                <label className="block text-xs font-semibold text-slate-700 dark:text-slate-300">
                  Rôle WeaveGuard AI
                </label>
                <select
                  value={createRole}
                  onChange={(e) => setCreateRole(e.target.value as UserRole)}
                  className="input !py-2"
                >
                  <option value="operator">Opérateur (Inférences & Revues)</option>
                  <option value="supervisor">Superviseur (Validation qualité)</option>
                  <option value="ml_engineer">Ingénieur ML (Modèles & Évaluation)</option>
                  <option value="auditor">Auditeur (Audit logs en lecture seule)</option>
                  <option value="admin">Administrateur (Gestion complète)</option>
                </select>
              </div>

              <div className="mt-6 flex justify-end gap-3 pt-2">
                <button
                  type="button"
                  onClick={() => setShowCreateModal(false)}
                  className="btn-secondary !py-2 disabled:opacity-40"
                >
                  Annuler
                </button>
                <button
                  type="submit"
                  disabled={createSubmitting}
                  className="btn-primary !py-2"
                >
                  {createSubmitting ? <LoadingSpinner size="sm" /> : 'Créer le compte'}
                </button>
              </div>
            </form>
          </div>
        </div>
      )}
    </div>
  )
}
