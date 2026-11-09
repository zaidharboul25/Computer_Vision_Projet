import React, { lazy } from 'react'
import { BrowserRouter, Routes, Route, Navigate } from 'react-router-dom'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { AuthProvider } from './context/AuthContext'
import { ThemeProvider } from './context/ThemeContext'
import { ProtectedRoute } from './components/auth/ProtectedRoute'
import { AppLayout } from './components/layout/AppLayout'
import { LoginPage } from './pages/LoginPage'
const DashboardPlaceholder = lazy(() => import('./pages/DashboardPlaceholder').then((m) => ({ default: m.DashboardPlaceholder })))
const NewInspectionPage = lazy(() => import('./pages/NewInspectionPage').then((m) => ({ default: m.NewInspectionPage })))
const InspectionResultPage = lazy(() => import('./pages/InspectionResultPage').then((m) => ({ default: m.InspectionResultPage })))
const InspectionsListPage = lazy(() => import('./pages/InspectionsListPage').then((m) => ({ default: m.InspectionsListPage })))
const SimilaritySearchPage = lazy(() => import('./pages/SimilaritySearchPage').then((m) => ({ default: m.SimilaritySearchPage })))
const ModelEvaluationPage = lazy(() => import('./pages/ModelEvaluationPage').then((m) => ({ default: m.ModelEvaluationPage })))
const AdminAuditPage = lazy(() => import('./pages/AdminAuditPage').then((m) => ({ default: m.AdminAuditPage })))
import { NotFoundPage } from './pages/NotFoundPage'

const queryClient = new QueryClient({
  defaultOptions: {
    queries: {
      retry: 1,
      refetchOnWindowFocus: false,
    },
  },
})

export const App: React.FC = () => {
  return (
    <QueryClientProvider client={queryClient}>
      <ThemeProvider>
        <AuthProvider>
          <BrowserRouter>
            <Routes>
              {/* Route publique */}
              <Route path="/login" element={<LoginPage />} />

              {/* Routes protégées */}
              <Route
                path="/"
                element={
                  <ProtectedRoute>
                    <AppLayout />
                  </ProtectedRoute>
                }
              >
                <Route index element={<DashboardPlaceholder />} />
                <Route
                  path="inspections/new"
                  element={
                    <ProtectedRoute allowedRoles={['operator', 'supervisor', 'admin', 'ml_engineer']}>
                      <NewInspectionPage />
                    </ProtectedRoute>
                  }
                />
                <Route
                  path="inspections/:id"
                  element={<InspectionResultPage />}
                />
                <Route
                  path="inspections"
                  element={<InspectionsListPage />}
                />
                <Route
                  path="similarity"
                  element={<SimilaritySearchPage />}
                />
                <Route
                  path="models"
                  element={<ModelEvaluationPage />}
                />
                <Route
                  path="admin"
                  element={
                    <ProtectedRoute allowedRoles={['admin', 'supervisor', 'auditor']}>
                      <AdminAuditPage />
                    </ProtectedRoute>
                  }
                />
              </Route>

              {/* 404 */}
              <Route path="/404" element={<NotFoundPage />} />
              <Route path="*" element={<Navigate to="/404" replace />} />
            </Routes>
          </BrowserRouter>
        </AuthProvider>
      </ThemeProvider>
    </QueryClientProvider>
  )
}

export default App
