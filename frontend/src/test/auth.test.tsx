import { render, screen } from '@testing-library/react'
import { describe, it, expect, vi } from 'vitest'
import { MemoryRouter, Routes, Route } from 'react-router-dom'
import { ProtectedRoute } from '../components/auth/ProtectedRoute'
import * as AuthContextModule from '../context/AuthContext'

describe('ProtectedRoute Component', () => {
  it('redirige vers /login si l’utilisateur n’est pas authentifié', () => {
    vi.spyOn(AuthContextModule, 'useAuth').mockReturnValue({
      user: null,
      isLoading: false,
      login: vi.fn(),
      logout: vi.fn(),
      hasRole: vi.fn().mockReturnValue(false),
    })

    render(
      <MemoryRouter initialEntries={['/protected']}>
        <Routes>
          <Route path="/login" element={<div>Écran de connexion</div>} />
          <Route
            path="/protected"
            element={
              <ProtectedRoute>
                <div>Contenu secret</div>
              </ProtectedRoute>
            }
          />
        </Routes>
      </MemoryRouter>
    )

    expect(screen.getByText('Écran de connexion')).toBeInTheDocument()
    expect(screen.queryByText('Contenu secret')).not.toBeInTheDocument()
  })

  it('affiche un message 403 d’accès refusé si le rôle est insuffisant', () => {
    vi.spyOn(AuthContextModule, 'useAuth').mockReturnValue({
      user: { username: 'test_operator', role: 'operator' },
      isLoading: false,
      login: vi.fn(),
      logout: vi.fn(),
      hasRole: vi.fn().mockReturnValue(false),
    })

    render(
      <MemoryRouter initialEntries={['/admin']}>
        <Routes>
          <Route
            path="/admin"
            element={
              <ProtectedRoute allowedRoles={['admin']}>
                <div>Zone Administrateur</div>
              </ProtectedRoute>
            }
          />
        </Routes>
      </MemoryRouter>
    )

    expect(screen.getByText('Accès non autorisé')).toBeInTheDocument()
    expect(screen.getByText(/ne dispose pas des privilèges nécessaires/)).toBeInTheDocument()
    expect(screen.queryByText('Zone Administrateur')).not.toBeInTheDocument()
  })

  it('affiche le contenu protégé si le rôle est autorisé', () => {
    vi.spyOn(AuthContextModule, 'useAuth').mockReturnValue({
      user: { username: 'admin_user', role: 'admin' },
      isLoading: false,
      login: vi.fn(),
      logout: vi.fn(),
      hasRole: vi.fn().mockReturnValue(true),
    })

    render(
      <MemoryRouter initialEntries={['/admin']}>
        <Routes>
          <Route
            path="/admin"
            element={
              <ProtectedRoute allowedRoles={['admin']}>
                <div>Zone Administrateur</div>
              </ProtectedRoute>
            }
          />
        </Routes>
      </MemoryRouter>
    )

    expect(screen.getByText('Zone Administrateur')).toBeInTheDocument()
  })
})
