import React from 'react'
import { BrowserRouter, Routes, Route, Navigate } from 'react-router-dom'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { AuthProvider } from './context/AuthContext'
import { ThemeProvider } from './context/ThemeContext'
import { ProtectedRoute } from './components/auth/ProtectedRoute'
import { AppLayout } from './components/layout/AppLayout'
import { LoginPage } from './pages/LoginPage'
import { DashboardPlaceholder } from './pages/DashboardPlaceholder'
import { NewInspectionPage } from './pages/NewInspectionPage'
import { InspectionResultPage } from './pages/InspectionResultPage'
import { InspectionsListPage } from './pages/InspectionsListPage'
import { SimilaritySearchPage } from './pages/SimilaritySearchPage'
import { ModelEvaluationPage } from './pages/ModelEvaluationPage'
import { AdminAuditPage } from './pages/AdminAuditPage'
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
