import { render, screen } from '@testing-library/react'
import { describe, it, expect } from 'vitest'
import { RoleBadge } from '../components/common/RoleBadge'
import { DemoBadge } from '../components/common/DemoBadge'
import type { UserRole } from '../types'

describe('Badges UI Components', () => {
  it('affiche les libellés contractuels en français pour tous les rôles', () => {
    const roles: Record<UserRole, string> = {
      operator: 'Opérateur',
      supervisor: 'Superviseur',
      admin: 'Administrateur',
      ml_engineer: 'Ingénieur ML',
      auditor: 'Auditeur',
    }

    Object.entries(roles).forEach(([role, label]) => {
      const { unmount } = render(<RoleBadge role={role as UserRole} />)
      expect(screen.getByText(label)).toBeInTheDocument()
      unmount()
    })
  })

  it('affiche le badge DÉMO avec la mention explicite', () => {
    render(<DemoBadge />)
    expect(screen.getByText('DÉMO')).toBeInTheDocument()
  })
})
