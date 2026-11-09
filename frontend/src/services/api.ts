import type {
  ErrorResponse,
  ErrorBody,
  Inspection,
  InspectionCreate,
  InspectionList,
  RegionList,
  Health,
  ModelsList,
  DomainBiasReport,
  SimilaritySearchResponse,
  AuditLogList,
  UserResponse,
  UserCreateRequest,
  UserUpdateRequest,
} from '../types'

// En dev, l'API est jointe sur le MÊME nom d'hôte que la page (localhost ↔ localhost) :
// le cookie de session est ainsi « same-site » et accepté par le navigateur.
export const API_BASE_URL =
  import.meta.env.VITE_API_URL ??
  (import.meta.env.DEV ? `${window.location.protocol}//${window.location.hostname}:8000` : '')

// Le jeton de session vit dans un cookie httpOnly posé par l'API : JavaScript ne peut pas le lire,
// donc un XSS ne peut pas le voler. Seul le jeton CSRF (dérivé de la session, inutile seul) reste en mémoire.
let csrfToken: string | null = null
const UNSAFE_METHODS = new Set(['POST', 'PUT', 'PATCH', 'DELETE'])

export function setCsrfToken(token: string | null) {
  csrfToken = token
}

export function getCsrfToken(): string | null {
  return csrfToken
}

function withSessionHeaders(headers: Headers, method?: string) {
  if (csrfToken && UNSAFE_METHODS.has((method || 'GET').toUpperCase()) && !headers.has('X-CSRF-Token')) {
    headers.set('X-CSRF-Token', csrfToken)
  }
}

// Enregistrement d'un callback sur 401 UNAUTHENTICATED
let unauthenticatedHandler: (() => void) | null = null
export function onUnauthenticated(handler: () => void) {
  unauthenticatedHandler = handler
}

export class ApiError extends Error {
  status: number
  code: string
  correlationId: string | null
  details?: Record<string, unknown>

  constructor(status: number, code: string, message: string, correlationId: string | null, details?: Record<string, unknown>) {
    super(message)
    this.name = 'ApiError'
    this.status = status
    this.code = code
    this.correlationId = correlationId
    this.details = details
  }
}

export const ERROR_MESSAGES_FR: Record<string, { label: string; action?: string }> = {
  INVALID_IMAGE: {
    label: "L'image fournie est invalide, corrompue ou dans un format non supporté.",
    action: "Vérifiez que le fichier est une image valide (PNG ou JPEG non corrompue).",
  },
  IMAGE_TOO_LARGE: {
    label: "L'image dépasse la taille maximale autorisée par le serveur.",
    action: "Veuillez compresser ou redimensionner l'image avant de réessayer.",
  },
  MODEL_UNAVAILABLE: {
    label: "Le moteur d'intelligence artificielle demandé est indisponible ou non chargé.",
    action: "Consultez l'état de santé du système ou contactez l'administrateur.",
  },
  INFERENCE_FAILED: {
    label: "L'exécution du modèle d'inspection a échoué pendant le calcul.",
    action: "L'erreur a été consignée. Vous pouvez relancer l'inspection.",
  },
  INSPECTION_NOT_FOUND: {
    label: "Inspection introuvable ou inaccessible.",
    action: "Vérifiez l'identifiant ou assurez-vous d'avoir les droits de consultation.",
  },
  REGION_NOT_FOUND: {
    label: "Région d'anomalie introuvable ou inaccessible.",
  },
  FORBIDDEN: {
    label: "Action non autorisée pour votre rôle utilisateur.",
    action: "Connectez-vous avec un compte disposant des privilèges adéquats.",
  },
  INVALID_FEEDBACK: {
    label: "La décision ou le motif de rejet soumis est non conforme.",
    action: "Sélectionnez un motif valide fourni par le système.",
  },
  DATABASE_UNAVAILABLE: {
    label: "La base de données MongoDB locale est temporairement inaccessible.",
    action: "Vérifiez que le service MongoDB est démarré sur la machine.",
  },
  UNAUTHENTICATED: {
    label: "Session expirée ou informations d'authentification invalides.",
    action: "Veuillez vous reconnecter pour poursuivre.",
  },
  VALIDATION_ERROR: {
    label: "Les paramètres transmis sont incomplets ou invalides.",
  },
  SERVER_BUSY: {
    label: "La file d'attente d'inférence est temporairement saturée.",
    action: "Veuillez patienter quelques instants avant de relancer votre demande.",
  },
  SECURITY_ERROR: {
    label: "La requête a été rejetée pour des motifs de sécurité.",
  },
  TOO_MANY_REQUESTS: {
    label: "Trop de tentatives de connexion depuis cette adresse.",
    action: "Patientez quelques minutes avant de réessayer.",
  },
  REFERENCE_NOT_FOUND: {
    label: "L'image de référence de texture DTD est introuvable.",
  },
}

export function formatErrorMessage(err: unknown): { title: string; message: string; code?: string; correlationId?: string } {
  if (err instanceof ApiError) {
    const known = ERROR_MESSAGES_FR[err.code]
    return {
      title: known?.label || err.message,
      message: known?.action ? `${err.message} — ${known.action}` : err.message,
      code: err.code,
      correlationId: err.correlationId || undefined,
    }
  }
  if (err instanceof Error) {
    return {
      title: 'Erreur inattendue',
      message: err.message,
    }
  }
  return {
    title: 'Erreur réseau',
    message: 'Impossible de contacter le serveur WeaveGuard AI.',
  }
}

export async function apiFetch<T>(endpoint: string, options: RequestInit = {}): Promise<T> {
  const headers = new Headers(options.headers || {})
  withSessionHeaders(headers, options.method)

  // Ne pas forcer Content-Type si c'est du FormData (multipart/form-data)
  if (!(options.body instanceof FormData) && !headers.has('Content-Type')) {
    headers.set('Content-Type', 'application/json')
  }

  const url = endpoint.startsWith('http') ? endpoint : `${API_BASE_URL}${endpoint}`
  let res: Response
  try {
    res = await fetch(url, { ...options, headers, credentials: 'include' })
  } catch {
    throw new ApiError(0, 'NETWORK_ERROR', 'Impossible de joindre le serveur FastAPI.', null)
  }

  const correlationId = res.headers.get('X-Correlation-ID')

  if (!res.ok) {
    let errorBody: ErrorBody | null = null
    try {
      const data = (await res.json()) as ErrorResponse
      if (data && data.error) {
        errorBody = data.error
      }
    } catch {
      // Réponse non-JSON
    }

    const code = errorBody?.code || (res.status === 413 ? 'IMAGE_TOO_LARGE' : res.status === 401 ? 'UNAUTHENTICATED' : 'HTTP_ERROR')
    const message = errorBody?.message || res.statusText || 'Erreur serveur'

    if (res.status === 401 || code === 'UNAUTHENTICATED') {
      if (unauthenticatedHandler) {
        unauthenticatedHandler()
      }
    }

    throw new ApiError(res.status, code, message, errorBody?.correlation_id || correlationId, errorBody?.details)
  }

  if (res.status === 204) {
    return {} as T
  }

  const contentType = res.headers.get('Content-Type') || ''
  if (contentType.includes('application/json')) {
    return (await res.json()) as T
  }
  return (await res.text()) as unknown as T
}

export async function apiFetchBlob(endpoint: string, options: RequestInit = {}): Promise<Blob> {
  const headers = new Headers(options.headers || {})
  withSessionHeaders(headers, options.method)

  const url = endpoint.startsWith('http') ? endpoint : `${API_BASE_URL}${endpoint}`
  let res: Response
  try {
    res = await fetch(url, { ...options, headers, credentials: 'include' })
  } catch {
    throw new ApiError(0, 'NETWORK_ERROR', 'Impossible de joindre le serveur FastAPI.', null)
  }

  const correlationId = res.headers.get('X-Correlation-ID')

  if (!res.ok) {
    let errorBody: ErrorBody | null = null
    try {
      const data = (await res.json()) as ErrorResponse
      if (data && data.error) {
        errorBody = data.error
      }
    } catch {
      // Réponse non-JSON
    }

    const code = errorBody?.code || (res.status === 401 ? 'UNAUTHENTICATED' : 'HTTP_ERROR')
    const message = errorBody?.message || res.statusText || 'Erreur lors du téléchargement'
    if (res.status === 401 || code === 'UNAUTHENTICATED') {
      if (unauthenticatedHandler) unauthenticatedHandler()
    }
    throw new ApiError(res.status, code, message, errorBody?.correlation_id || correlationId, errorBody?.details)
  }

  return await res.blob()
}

export async function logoutRequest(): Promise<void> {
  await apiFetch('/api/v1/auth/logout', { method: 'POST' })
}

export async function createInspection(
  file: File,
  engines?: string[],
  scaleMode: 'native' | 'normalized' = 'native'
): Promise<InspectionCreate> {
  const formData = new FormData()
  formData.append('file', file)
  if (engines && engines.length > 0) {
    formData.append('engines', engines.join(','))
  }
  formData.append('scale_mode', scaleMode)
  return apiFetch<InspectionCreate>('/api/v1/inspections', {
    method: 'POST',
    body: formData,
  })
}

export async function getInspection(id: string): Promise<Inspection> {
  return apiFetch<Inspection>(`/api/v1/inspections/${id}`)
}

export async function getInspectionRegions(id: string): Promise<RegionList> {
  return apiFetch<RegionList>(`/api/v1/inspections/${id}/regions`)
}

export async function listInspections(params: {
  skip?: number
  limit?: number
  status?: string
  created_by?: string
  id_filter?: string
  review_status?: string
} = {}): Promise<InspectionList> {
  const query = new URLSearchParams()
  if (params.skip !== undefined) query.set('skip', String(params.skip))
  if (params.limit !== undefined) query.set('limit', String(params.limit))
  if (params.status) query.set('status', params.status)
  if (params.created_by) query.set('created_by', params.created_by)
  if (params.id_filter) query.set('id_filter', params.id_filter)
  if (params.review_status) query.set('review_status', params.review_status)

  const qs = query.toString()
  return apiFetch<InspectionList>(`/api/v1/inspections${qs ? `?${qs}` : ''}`)
}

export async function searchSimilarity(
  file: File,
  indexName: 'weaveguard' | 'dtd' | 'all' = 'all',
  k: number = 5
): Promise<SimilaritySearchResponse> {
  const formData = new FormData()
  formData.append('file', file)
  formData.append('index_name', indexName)
  formData.append('k', String(k))
  return apiFetch<SimilaritySearchResponse>('/api/v1/similarity/search', {
    method: 'POST',
    body: formData,
  })
}

export function getSimilarityThumbnailUrl(refId: string): string {
  const base = API_BASE_URL.startsWith('http') ? API_BASE_URL : ''
  return `${base}/api/v1/similarity/ref/${encodeURIComponent(refId)}/thumbnail`
}

export async function getModels(): Promise<ModelsList> {
  return apiFetch<ModelsList>('/api/v1/models')
}

export async function getDomainBiasReport(): Promise<DomainBiasReport> {
  return apiFetch<DomainBiasReport>('/api/v1/models/domain-bias-report')
}

export async function listUsers(skip = 0, limit = 50): Promise<UserResponse[]> {
  return apiFetch<UserResponse[]>(`/api/v1/users?skip=${skip}&limit=${limit}`)
}

export async function createUser(payload: UserCreateRequest): Promise<UserResponse> {
  return apiFetch<UserResponse>('/api/v1/users', {
    method: 'POST',
    body: JSON.stringify(payload),
  })
}

export async function updateUser(userId: string, payload: UserUpdateRequest): Promise<UserResponse> {
  return apiFetch<UserResponse>(`/api/v1/users/${userId}`, {
    method: 'PATCH',
    body: JSON.stringify(payload),
  })
}

export async function listAuditLogs(params: {
  skip?: number
  limit?: number
  action?: string
  username?: string
} = {}): Promise<AuditLogList> {
  const query = new URLSearchParams()
  if (params.skip !== undefined) query.set('skip', String(params.skip))
  if (params.limit !== undefined) query.set('limit', String(params.limit))
  if (params.action) query.set('action', params.action)
  if (params.username) query.set('username', params.username)

  const qs = query.toString()
  return apiFetch<AuditLogList>(`/api/v1/audit${qs ? `?${qs}` : ''}`)
}

export async function getHealth(): Promise<Health> {
  return apiFetch<Health>('/health')
}

export function triggerBlobDownload(blob: Blob, filename: string): void {
  const url = URL.createObjectURL(blob)
  const a = document.createElement('a')
  a.href = url
  a.download = filename
  document.body.appendChild(a)
  a.click()
  document.body.removeChild(a)
  URL.revokeObjectURL(url)
}
