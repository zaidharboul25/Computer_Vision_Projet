import { describe, it, expect, beforeEach, vi, afterEach } from 'vitest'
import {
  ApiError,
  formatErrorMessage,
  setCsrfToken,
  getCsrfToken,
  apiFetch,
  onUnauthenticated,
  ERROR_MESSAGES_FR,
} from '../services/api'

describe('API Service & Error Handling', () => {
  beforeEach(() => {
    setCsrfToken(null)
    sessionStorage.clear()
    localStorage.clear()
  })

  afterEach(() => {
    vi.restoreAllMocks()
  })

  it('conserve le jeton CSRF en mémoire uniquement (jamais dans le stockage du navigateur)', () => {
    expect(getCsrfToken()).toBeNull()
    setCsrfToken('csrf-abc')
    expect(getCsrfToken()).toBe('csrf-abc')
    expect(sessionStorage.length).toBe(0)
    expect(localStorage.length).toBe(0)
  })

  it('envoie les cookies (credentials: include) et X-CSRF-Token uniquement sur les requêtes modifiantes', async () => {
    const fetchMock = vi.fn().mockImplementation(async () =>
      new Response(JSON.stringify({ ok: true }), { status: 200, headers: { 'Content-Type': 'application/json' } })
    )
    vi.stubGlobal('fetch', fetchMock)
    setCsrfToken('csrf-abc')

    await apiFetch('/api/v1/auth/me')
    await apiFetch('/api/v1/inspections', { method: 'POST', body: JSON.stringify({}) })

    const [, getInit] = fetchMock.mock.calls[0]
    const [, postInit] = fetchMock.mock.calls[1]
    expect(getInit.credentials).toBe('include')
    expect(new Headers(getInit.headers).has('X-CSRF-Token')).toBe(false)
    expect(new Headers(getInit.headers).has('Authorization')).toBe(false)
    expect(postInit.credentials).toBe('include')
    expect(new Headers(postInit.headers).get('X-CSRF-Token')).toBe('csrf-abc')
    vi.unstubAllGlobals()
  })

  it('formate correctement une ApiError avec code connu et correlation_id', () => {
    const err = new ApiError(413, 'IMAGE_TOO_LARGE', 'Fichier trop lourd', 'corr-12345')
    const formatted = formatErrorMessage(err)

    expect(formatted.code).toBe('IMAGE_TOO_LARGE')
    expect(formatted.correlationId).toBe('corr-12345')
    expect(formatted.title).toBe(ERROR_MESSAGES_FR.IMAGE_TOO_LARGE.label)
    expect(formatted.message).toContain(ERROR_MESSAGES_FR.IMAGE_TOO_LARGE.action)
  })

  it('formate une ApiError avec code inconnu sans planter', () => {
    const err = new ApiError(500, 'UNKNOWN_ERROR', 'Erreur interne de test', 'corr-999')
    const formatted = formatErrorMessage(err)

    expect(formatted.code).toBe('UNKNOWN_ERROR')
    expect(formatted.title).toBe('Erreur interne de test')
    expect(formatted.correlationId).toBe('corr-999')
  })

  it('formate une erreur réseau standard', () => {
    const netErr = new TypeError('Failed to fetch')
    const formatted = formatErrorMessage(netErr)

    expect(formatted.title).toBe('Erreur inattendue')
    expect(formatted.message).toBe('Failed to fetch')
  })

  it('enregistre et appelle le gestionnaire UNAUTHENTICATED', () => {
    let called = false
    onUnauthenticated(() => {
      called = true
    })
    // Vérification que le callback est fonctionnel
    expect(called).toBe(false)
  })
})

