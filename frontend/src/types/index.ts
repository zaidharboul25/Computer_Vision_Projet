import type { components, paths } from './api'

export type { components, paths }

// Extractions typées depuis le schéma OpenAPI officiel (zéro type écrit à la main)
export type Inspection = components['schemas']['InspectionResponse']
export type InspectionCreate = components['schemas']['InspectionCreateResponse']
export type InspectionList = components['schemas']['InspectionListResponse']
export type EngineProgress = components['schemas']['EngineProgress']
export type ImageMeta = components['schemas']['ImageMeta']
export type HeatmapMeta = components['schemas']['HeatmapMeta']
export type Region = components['schemas']['RegionResponse']
export type RegionDetail = components['schemas']['RegionDetailResponse']
export type RegionList = components['schemas']['RegionListResponse']
export type Feedback = components['schemas']['FeedbackResponse']
export type FeedbackCreateRequest = components['schemas']['FeedbackCreateRequest']
export type Health = components['schemas']['HealthResponse']
export type SummaryStats = components['schemas']['SummaryStatsResponse']
export type ModelsList = components['schemas']['ModelsListResponse']
export type DomainBiasReport = components['schemas']['DomainBiasReportResponse']
export type AuditLogList = components['schemas']['AuditLogListResponse']
export type AuditLogItem = components['schemas']['AuditLogItem']
export type UserResponse = components['schemas']['UserResponse']
export type UserCreateRequest = components['schemas']['UserCreateRequest']
export type UserUpdateRequest = components['schemas']['UserUpdateRequest']
export type SimilaritySearchResponse = components['schemas']['SimilaritySearchResponse']
export type SimilarityIndexResult = components['schemas']['SimilarityIndexResult']
export type SimilarityItem = components['schemas']['SimilarityItem']
export type ActionStatus = components['schemas']['ActionStatusResponse']

export type ErrorResponse = components['schemas']['ErrorResponse']
export type ErrorBody = components['schemas']['ErrorBody']

// Rôles contractuels
export type UserRole = 'operator' | 'supervisor' | 'admin' | 'ml_engineer' | 'auditor'

export interface UserSession {
  username: string
  role: UserRole
  token: string
}
