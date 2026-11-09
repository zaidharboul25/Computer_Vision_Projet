import { render, screen, fireEvent } from '@testing-library/react'
import { describe, it, expect, vi } from 'vitest'
import { ErrorAlert } from '../components/common/ErrorAlert'
import { ApiError } from '../services/api'

describe('ErrorAlert Component', () => {
  it('affiche le message d’erreur, le code et le correlation_id', () => {
    const error = new ApiError(404, 'INSPECTION_NOT_FOUND', 'Inspection non trouvée', 'req-corr-777')
    render(<ErrorAlert error={error} />)

    expect(screen.getByText('Inspection introuvable ou inaccessible.')).toBeInTheDocument()
    expect(screen.getByText(/Code : INSPECTION_NOT_FOUND/)).toBeInTheDocument()
    expect(screen.getByText(/X-Correlation-ID : req-corr-777/)).toBeInTheDocument()
  })

  it('propose un bouton de réessai lorsque onRetry est fourni', () => {
    const onRetry = vi.fn()
    const error = new ApiError(503, 'SERVER_BUSY', 'Serveur occupé', 'req-123')
    render(<ErrorAlert error={error} onRetry={onRetry} />)

    const retryBtn = screen.getByRole('button', { name: /Réessayer/i })
    expect(retryBtn).toBeInTheDocument()
    fireEvent.click(retryBtn)
    expect(onRetry).toHaveBeenCalledTimes(1)
  })

  it('ne rend rien si l’erreur est nulle', () => {
    const { container } = render(<ErrorAlert error={null} />)
    expect(container.firstChild).toBeNull()
  })
})
