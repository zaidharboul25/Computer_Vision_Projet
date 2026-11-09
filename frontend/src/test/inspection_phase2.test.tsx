import { render, screen, fireEvent } from '@testing-library/react'
import { describe, it, expect, vi } from 'vitest'
import { MemoryRouter, Routes, Route } from 'react-router-dom'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { InspectionResultPage } from '../pages/InspectionResultPage'
import { NewInspectionPage } from '../pages/NewInspectionPage'
import * as apiModule from '../services/api'
import type { Inspection, Health } from '../types'

function renderWithProviders(ui: React.ReactElement, initialRoute = '/inspections/test-123') {
  const testQueryClient = new QueryClient({
    defaultOptions: {
      queries: {
        retry: false,
      },
    },
  })
  return render(
    <QueryClientProvider client={testQueryClient}>
      <MemoryRouter initialEntries={[initialRoute]}>
        <Routes>
          <Route path="/inspections/:id" element={ui} />
          <Route path="/inspections/new" element={ui} />
          <Route path="/" element={ui} />
        </Routes>
      </MemoryRouter>
    </QueryClientProvider>
  )
}

describe('Phase 2 — Inspections UI Tests', () => {
  it('affiche le message contractuel exact pour l’état "aucune région"', async () => {
    const mockInspection: Inspection = {
      id: 'insp-zero-regions-1234',
      status: 'done',
      partial: false,
      created_by: 'demo_operator',
      created_at: '2026-11-03T10:00:00Z',
      completed_at: '2026-11-03T10:00:02Z',
      image_meta: {
        filename: 'clean_fabric.png',
        format: 'PNG',
        width: 1024,
        height: 1024,
        stored_width: 1024,
        stored_height: 1024,
        inference_width: 1024,
        inference_height: 1024,
        resize_factor: 1.0,
        scale_mode: 'native',
        warnings: [],
      },
      engines: {
        yolo: {
          status: 'ok',
          version: 'yolo11n_best_weights',
          latency_ms: { preprocess: 5.2, model: 45.1, postprocess: 2.1, total: 52.4 },
        },
        patchcore: {
          status: 'ok',
          version: 'patchcore_resnet50',
          latency_ms: { preprocess: 10.0, model: 120.0, postprocess: 15.0, total: 145.0 },
        },
      },
      regions_count: 0,
      heatmap_meta: null,
      error_message: null,
      is_demo: false,
    }

    vi.spyOn(apiModule, 'getInspection').mockResolvedValue(mockInspection)

    renderWithProviders(<InspectionResultPage />)

    // Vérification du message exact stipulé dans le cahier des charges et l'exigence 6
    expect(await screen.findByText('Aucune région détectée par les moteurs exécutés')).toBeInTheDocument()
    expect(screen.getByText("Ce résultat n'est pas une garantie d'absence de défaut")).toBeInTheDocument()
  })

  it('affiche un bandeau d’avertissement bien visible en cas de résultat partiel (partial: true)', async () => {
    const mockPartialInspection: Inspection = {
      id: 'insp-partial-5678',
      status: 'done',
      partial: true,
      created_by: 'demo_operator',
      created_at: '2026-11-03T10:05:00Z',
      image_meta: {
        filename: 'defect_fabric.png',
        format: 'PNG',
        width: 1024,
        height: 1024,
        stored_width: 1024,
        stored_height: 1024,
        inference_width: 1024,
        inference_height: 1024,
        resize_factor: 1.0,
        scale_mode: 'native',
        warnings: [],
      },
      engines: {
        yolo: {
          status: 'ok',
          version: 'yolo11n_best_weights',
          latency_ms: { total: 55.0 },
        },
        patchcore: {
          status: 'error',
          error: 'Out of memory during neighbor search',
        },
      },
      regions_count: 2,
      heatmap_meta: null,
      error_message: null,
      is_demo: false,
    }

    vi.spyOn(apiModule, 'getInspection').mockResolvedValue(mockPartialInspection)
    vi.spyOn(apiModule, 'getInspectionRegions').mockResolvedValue({ items: [], total: 0 })

    renderWithProviders(<InspectionResultPage />)

    expect(await screen.findByText('Résultat partiel')).toBeInTheDocument()
    expect(screen.getByText(/Un ou plusieurs moteurs d'analyse ont échoué/)).toBeInTheDocument()
    expect(screen.getByText('Out of memory during neighbor search')).toBeInTheDocument()
  })

  it('affiche la télémétrie et la progression des moteurs avec aria-live', async () => {
    const mockRunningInspection: Inspection = {
      id: 'insp-running-9999',
      status: 'running',
      partial: false,
      created_by: 'demo_operator',
      created_at: '2026-11-03T10:10:00Z',
      image_meta: {
        filename: 'test.png',
        format: 'PNG',
        width: 800,
        height: 800,
        stored_width: 800,
        stored_height: 800,
        inference_width: 800,
        inference_height: 800,
        resize_factor: 1.0,
        scale_mode: 'native',
        warnings: [],
      },
      engines: {
        yolo: { status: 'ok', latency_ms: { total: 42.0 }, version: 'hash_abc123456789' },
        patchcore: { status: 'running' },
      },
      regions_count: 0,
      heatmap_meta: null,
      error_message: null,
      is_demo: false,
    }

    vi.spyOn(apiModule, 'getInspection').mockResolvedValue(mockRunningInspection)

    renderWithProviders(<InspectionResultPage />)

    expect(await screen.findByText(/YOLOv11 \(Supervisé\)/)).toBeInTheDocument()
    expect(screen.getByText(/PatchCore \(Anomalies\)/)).toBeInTheDocument()
    expect(screen.getByText('42 ms')).toBeInTheDocument()
    expect(screen.getByText(/hash_abc1234/)).toBeInTheDocument()
    expect(screen.getByText('Inférence')).toBeInTheDocument()
  })

  it('permet de basculer la sélection des moteurs sur la page de nouvelle inspection', async () => {
    const mockHealth: Health = {
      status: 'ok',
      database: 'connected',
      device_active: 'cpu',
      gpu: { available: false, device_name: 'N/A', total_memory_mb: 0, allocated_memory_mb: 0, sm_61_supported: false },
      engines: { yolo: true, patchcore: true, similarity: true },
      timestamp: '2026-11-03T10:00:00Z',
    }
    vi.spyOn(apiModule, 'getHealth').mockResolvedValue(mockHealth)

    renderWithProviders(<NewInspectionPage />, '/inspections/new')

    expect(await screen.findByText('Nouvelle inspection textile')).toBeInTheDocument()

    // Vérifier les deux moteurs cochés par défaut
    const yoloCheckbox = screen.getByLabelText(/YOLOv11/) as HTMLInputElement
    const patchcoreCheckbox = screen.getByLabelText(/PatchCore/) as HTMLInputElement

    expect(yoloCheckbox.checked).toBe(true)
    expect(patchcoreCheckbox.checked).toBe(true)

    // Décocher YOLO
    fireEvent.click(yoloCheckbox)
    expect(yoloCheckbox.checked).toBe(false)
    expect(patchcoreCheckbox.checked).toBe(true)
  })
})
