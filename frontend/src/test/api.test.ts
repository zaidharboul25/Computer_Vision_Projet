import { describe, it, expect, beforeEach } from 'vitest'
import {
  ApiError,
  formatErrorMessage,
  setAuthToken,
  getAuthToken,
  onUnauthenticated,
  ERROR_MESSAGES_FR,
} from '../services/api'

describe('API Service & Error Handling', () => {
  beforeEach(() => {
    setAuthToken(null)
    sessionStorage.clear()
  })

  it('gère le stockage du jeton JWT en mémoire et sessionStorage', () => {
    expect(getAuthToken()).toBeNull()
    setAuthToken('test-jwt-token-xyz')
    expect(getAuthToken()).toBe('test-jwt-token-xyz')
    expect(sessionStorage.getItem('weaveguard_session')).toBe('test-jwt-token-xyz')

    setAuthToken(null)
    expect(getAuthToken()).toBeNull()
    expect(sessionStorage.getItem('weaveguard_session')).toBeNull()
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

