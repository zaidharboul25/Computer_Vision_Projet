import { render, screen, fireEvent, waitFor, act } from '@testing-library/react'
import { describe, it, expect, vi, beforeEach } from 'vitest'
import { MemoryRouter, Routes, Route } from 'react-router-dom'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { InspectionsListPage } from '../pages/InspectionsListPage'
import { SimilaritySearchPage } from '../pages/SimilaritySearchPage'
import { ModelEvaluationPage } from '../pages/ModelEvaluationPage'
import { AdminAuditPage } from '../pages/AdminAuditPage'
import * as apiModule from '../services/api'
import * as AuthContextModule from '../context/AuthContext'
import type { UserRole } from '../types'

function renderWithProviders(
  ui: React.ReactElement,
  user: { username: string; role: UserRole } | null = { username: 'admin', role: 'admin' },
  initialRoute = '/'
) {
  vi.spyOn(AuthContextModule, 'useAuth').mockReturnValue({
    user,
    isLoading: false,
    login: vi.fn(),
    logout: vi.fn(),
    hasRole: (roles: UserRole | UserRole[]) => {
      if (!user) return false
      const allowed = Array.isArray(roles) ? roles : [roles]
      return allowed.includes(user.role)
    },
  })

  const testQueryClient = new QueryClient({
    defaultOptions: {
      queries: { retry: false },
    },
  })

  return render(
    <QueryClientProvider client={testQueryClient}>
      <MemoryRouter initialEntries={[initialRoute]}>
        <Routes>
          <Route path="*" element={ui} />
        </Routes>
      </MemoryRouter>
    </QueryClientProvider>
  )
}

describe('Completed Modules & Pages UI Tests', () => {
  beforeEach(() => {
    vi.restoreAllMocks()
    if (!global.URL.createObjectURL) {
      global.URL.createObjectURL = vi.fn(() => 'blob:http://localhost/mock')
    } else {
      vi.spyOn(global.URL, 'createObjectURL').mockReturnValue('blob:http://localhost/mock')
    }
    if (!global.URL.revokeObjectURL) {
      global.URL.revokeObjectURL = vi.fn()
    } else {
      vi.spyOn(global.URL, 'revokeObjectURL').mockReturnValue()
    }
  })

  // 1. InspectionsListPage
  describe('InspectionsListPage', () => {
    it('affiche la liste des inspections avec leurs badges et identifiants', async () => {
      vi.spyOn(apiModule, 'listInspections').mockResolvedValue({
        items: [
          {
            id: 'insp-662f0123456789',
            status: 'done',
            created_by: 'operator1',
            created_at: '2026-11-03T10:00:00Z',
            engines: { yolo: { status: 'ok' }, patchcore: { status: 'ok' } },
            regions_count: 3,
          } as any,
        ],
        total: 1,
        skip: 0,
        limit: 15,
      })

      renderWithProviders(<InspectionsListPage />)

      expect(screen.getByRole('heading', { name: /Historique des inspections/i })).toBeInTheDocument()

      await waitFor(() => {
        expect(screen.getByText('operator1')).toBeInTheDocument()
        expect(screen.getByText('Terminée')).toBeInTheDocument()
        expect(screen.getByText(/3 régions/i)).toBeInTheDocument()
      })
    })
  })

  // 2. SimilaritySearchPage
  describe('SimilaritySearchPage', () => {
    it('affiche le formulaire et permet de rechercher des textiles similaires', async () => {
      vi.spyOn(apiModule, 'searchSimilarity').mockResolvedValue({
        weaveguard: {
          engine: 'similarity',
          extractor: 'resnet50_gap',
          index: 'weaveguard_v1',
          metric: 'cosine_similarity',
          higher_is_better: true,
          note: 'Similarité cosinus',
          latency_ms: { preprocess: 2.1, model: 15.3, search: 1.2, total: 18.6 },
          results: [
            {
              rank: 1,
              score: 0.9542,
              ref_id: 'ref-textile-001',
              label: 'Textile Sergé Coton',
              category: 'cotton',
              split: 'train',
            },
          ],
        },
      } as any)

      renderWithProviders(<SimilaritySearchPage />)

      expect(screen.getByText(/Recherche de textiles similaires/i)).toBeInTheDocument()
      expect(screen.getByLabelText(/Index cible/i)).toBeInTheDocument()

      // Création d'un faux fichier
      const file = new File(['fake-image'], 'fabric.png', { type: 'image/png' })
      const input = document.querySelector('input[type="file"]') as HTMLInputElement
      fireEvent.change(input, { target: { files: [file] } })

      // Soumission du formulaire
      const form = screen.getByRole('form', { name: /Formulaire de similarité/i })
      await act(async () => {
        fireEvent.submit(form)
      })

      await waitFor(() => {
        expect(screen.getByText(/Galerie WeaveGuard/i)).toBeInTheDocument()
        expect(screen.getByText(/95.4%/i)).toBeInTheDocument()
        expect(screen.getAllByText(/ref-textile-001/i).length).toBeGreaterThan(0)
      })
    })
  })

  // 3. ModelEvaluationPage
  describe('ModelEvaluationPage', () => {
    it('affiche les fiches techniques des modèles et le rapport de biais de domaine', async () => {
      vi.spyOn(apiModule, 'getModels').mockResolvedValue({
        engines: {
          yolo: {
            name: 'YOLOv8',
            version: 'yolo11n_best_weights',
            weights_sha256: '58d7c0415a7826b5ec63255ff0faecfe45ee9bc54b3ee42a8a81691129994c50',
          },
          patchcore: {
            name: 'PatchCore',
            version: 'v1',
            memory_sha256: 'ad80be4e2d31ce02b0c156f2a7dbfe3566164d9b68d601a5fa600e12140bb063',
          },
        },
      } as any)

      vi.spyOn(apiModule, 'getDomainBiasReport').mockResolvedValue({
        reference_min: 0.8124,
        reference_source: 'train_gallery_only',
        familiarity_quantiles: [0.8124, 0.8941, 0.9255, 0.9482, 0.9896],
        dataset: 'weaveguard_v1',
      } as any)

      renderWithProviders(<ModelEvaluationPage />)

      await waitFor(() => {
        expect(screen.getByText(/Évaluation ML & Fiches modèles/i)).toBeInTheDocument()
        expect(screen.getByText(/0\.311/i)).toBeInTheDocument()
        expect(screen.getByText(/1\.6386/i)).toBeInTheDocument()
        expect(screen.getAllByText(/0\.8124/i).length).toBeGreaterThan(0)
        expect(screen.getByText(/Contrôle du Biais de Domaine & Familiarité/i)).toBeInTheDocument()
      })
    })
  })

  // 4. AdminAuditPage
  describe('AdminAuditPage', () => {
    it('affiche le journal d’audit et permet de naviguer entre onglets', async () => {
      vi.spyOn(apiModule, 'listAuditLogs').mockResolvedValue({
        items: [
          {
            _id: 'audit-001',
            at: '2026-11-03T11:00:00Z',
            username: 'operator1',
            action: 'INSPECTION_CREATED',
            details: { inspection_id: 'insp-123' },
          },
        ],
        total: 1,
        skip: 0,
        limit: 25,
      })

      vi.spyOn(apiModule, 'listUsers').mockResolvedValue([
        {
          id: 'user-001',
          username: 'operator1',
          role: 'operator',
          active: true,
          created_at: '2026-11-01T10:00:00Z',
        },
      ])

      renderWithProviders(<AdminAuditPage />)

      // Onglet Audit actif par défaut
      await waitFor(() => {
        expect(screen.getByText('INSPECTION_CREATED')).toBeInTheDocument()
      })

      // Clic sur l'onglet Utilisateurs
      const usersTab = screen.getByRole('button', { name: /Utilisateurs & Rôles/i })
      fireEvent.click(usersTab)

      await waitFor(() => {
        expect(screen.getByText('operator1')).toBeInTheDocument()
        expect(screen.getByText('Actif')).toBeInTheDocument()
      })

      // Clic sur Paramètres
      const settingsTab = screen.getByRole('button', { name: /Paramètres & Sécurité/i })
      fireEvent.click(settingsTab)

      expect(screen.getByText(/Politique de Sécurité & Sessions/i)).toBeInTheDocument()
      expect(screen.getByText(/8 heures \(480 minutes\)/i)).toBeInTheDocument()
    })
  })
})
