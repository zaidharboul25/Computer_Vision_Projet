import { useState, useEffect, useRef } from 'react'
import { getAuthToken, API_BASE_URL, ApiError } from '../services/api'

// Cache partagé en mémoire : url -> { objectUrl: string; refCount: number; blob: Blob }
const blobCache = new Map<string, { objectUrl: string; refCount: number; blob: Blob }>()

export function useAuthedBlob(endpoint: string | null | undefined): {
  objectUrl: string | null
  loading: boolean
  error: ApiError | Error | null
  refetch: () => void
} {
  const [objectUrl, setObjectUrl] = useState<string | null>(null)
  const [loading, setLoading] = useState<boolean>(false)
  const [error, setError] = useState<ApiError | Error | null>(null)
  const [trigger, setTrigger] = useState<number>(0)
  const isMounted = useRef<boolean>(true)

  useEffect(() => {
    isMounted.current = true
    return () => {
      isMounted.current = false
    }
  }, [])

  useEffect(() => {
    if (!endpoint) {
      setObjectUrl(null)
      setLoading(false)
      setError(null)
      return
    }

    const fullUrl = endpoint.startsWith('http') ? endpoint : `${API_BASE_URL}${endpoint}`

    // 1. Vérification dans le cache global partagé
    const cached = blobCache.get(fullUrl)
    if (cached) {
      cached.refCount++
      setObjectUrl(cached.objectUrl)
      setLoading(false)
      setError(null)

      return () => {
        cached.refCount--
        if (cached.refCount <= 0) {
          URL.revokeObjectURL(cached.objectUrl)
          blobCache.delete(fullUrl)
        }
      }
    }

    // 2. Téléchargement authentifié
    const controller = new AbortController()
    setLoading(true)
    setError(null)

    const token = getAuthToken()
    const headers: HeadersInit = {}
    if (token) {
      headers['Authorization'] = `Bearer ${token}`
    }

    fetch(fullUrl, { headers, signal: controller.signal })
      .then(async (res) => {
        if (!res.ok) {
          let errorMsg = `Erreur ${res.status}: ${res.statusText}`
          let code = res.status === 404 ? 'RESOURCE_NOT_FOUND' : res.status === 401 ? 'UNAUTHENTICATED' : 'HTTP_ERROR'
          try {
            const body = await res.json()
            if (body?.error) {
              code = body.error.code
              errorMsg = body.error.message
            }
          } catch {
            // Pas du JSON
          }
          throw new ApiError(res.status, code, errorMsg, res.headers.get('X-Correlation-ID'))
        }
        return res.blob()
      })
      .then((blob) => {
        if (!isMounted.current) return
        const createdUrl = URL.createObjectURL(blob)
        blobCache.set(fullUrl, { objectUrl: createdUrl, refCount: 1, blob })
        setObjectUrl(createdUrl)
        setLoading(false)
      })
      .catch((err) => {
        if (controller.signal.aborted) return
        if (isMounted.current) {
          setError(err)
          setLoading(false)
        }
      })

    return () => {
      controller.abort()
      const entry = blobCache.get(fullUrl)
      if (entry) {
        entry.refCount--
        if (entry.refCount <= 0) {
          URL.revokeObjectURL(entry.objectUrl)
          blobCache.delete(fullUrl)
        }
      }
    }
  }, [endpoint, trigger])

  return {
    objectUrl,
    loading,
    error,
    refetch: () => setTrigger((prev) => prev + 1),
  }
}

