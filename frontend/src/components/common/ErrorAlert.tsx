import React from 'react'
import { AlertTriangle, XCircle, RefreshCw } from 'lucide-react'
import { formatErrorMessage } from '../../services/api'

interface ErrorAlertProps {
  error: unknown
  onRetry?: () => void
  onDismiss?: () => void
  className?: string
}

export const ErrorAlert: React.FC<ErrorAlertProps> = ({ error, onRetry, onDismiss, className = '' }) => {
  if (!error) return null

  const { title, message, code, correlationId } = formatErrorMessage(error)

  return (
    <div
      role="alert"
      aria-live="assertive"
      className={`rounded-md border border-rose-300 bg-rose-50 p-4 text-rose-900 dark:border-rose-800 dark:bg-rose-950/50 dark:text-rose-200 ${className}`}
    >
      <div className="flex items-start">
        <div className="flex-shrink-0">
          <AlertTriangle className="h-5 w-5 text-rose-600 dark:text-rose-400" aria-hidden="true" />
        </div>
        <div className="ml-3 flex-1">
          <h3 className="text-sm font-semibold">{title}</h3>
          <div className="mt-1 text-sm opacity-90">{message}</div>

          <div className="mt-2 flex flex-wrap items-center gap-2 text-xs font-mono opacity-80">
            {code && (
              <span className="rounded bg-rose-200/60 px-1.5 py-0.5 dark:bg-rose-900/60">
                Code : {code}
              </span>
            )}
            {correlationId && (
              <span className="rounded bg-rose-200/60 px-1.5 py-0.5 dark:bg-rose-900/60">
                X-Correlation-ID : {correlationId}
              </span>
            )}
          </div>
        </div>

        <div className="ml-4 flex flex-shrink-0 items-center gap-2">
          {onRetry && (
            <button
              type="button"
              onClick={onRetry}
              className="inline-flex items-center gap-1 rounded bg-rose-100 px-2 py-1 text-xs font-medium text-rose-800 hover:bg-rose-200 dark:bg-rose-900 dark:text-rose-200 dark:hover:bg-rose-800"
            >
              <RefreshCw className="h-3 w-3" />
              Réessayer
            </button>
          )}
          {onDismiss && (
            <button
              type="button"
              onClick={onDismiss}
              className="rounded p-1 text-rose-600 hover:bg-rose-100 dark:text-rose-400 dark:hover:bg-rose-900"
              aria-label="Fermer"
            >
              <XCircle className="h-4 w-4" />
            </button>
          )}
        </div>
      </div>
    </div>
  )
}

