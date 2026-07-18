import request from '@/utils/request'

export interface ShootingProfile {
  shooting_level: string
  available_scenes: string[]
  camera_skill: string
  editing_skill: string
  available_time: string
  recommended_mode: 'basic' | 'intermediate' | 'advanced'
}

export interface ShootingShot {
  shot_number: number
  shot_type: string
  start_time: number
  end_time: number
  description: string
  script_content: string
  action: string
  camera_angle: string
  background: string
  priority: 'required' | 'optional' | 'enhancement'
}

export interface AssetRequirement {
  type: string
  role: string
  emotion?: string
  scene?: string
  duration: number
}

export interface ShootingPlan {
  recommended_mode: string
  mode_description: string
  required_shots: ShootingShot[]
  optional_shots: ShootingShot[]
  required_assets: AssetRequirement[]
  optional_assets: AssetRequirement[]
  estimated_time: string
  shooting_profile: ShootingProfile
}

export interface MatchedAsset {
  requirement: AssetRequirement
  asset: {
    id: number
    name: string
    url: string
    emotion: string | null
    scene: string | null
  }
}

export interface MatchResult {
  matched: MatchedAsset[]
  missing: AssetRequirement[]
}

export interface ShootingModeInfo {
  name: string
  description: string
  suitable_for: string
  requirements: string[]
  estimated_time: string
  enhancement: string
}

export function getShootingProfile() {
  return request.get<{
    success: boolean
    data: ShootingProfile
  }>('/shooting-assistant/profile')
}

export function updateShootingProfile(data: ShootingProfile) {
  return request.post<{
    success: boolean
    data: ShootingProfile
  }>('/shooting-assistant/profile', data)
}

export function generateShootingPlan(projectId: number, scriptContent: string) {
  return request.post<{
    success: boolean
    data: ShootingPlan
  }>('/shooting-assistant/plan', {
    project_id: projectId,
    script_content: scriptContent,
  })
}

export function matchAssetsForPlan(projectId: number) {
  return request.post<{
    success: boolean
    data: MatchResult
  }>(`/shooting-assistant/plan/${projectId}/assets`)
}

export function getShootingModes() {
  return request.get<{
    success: boolean
    data: Record<string, ShootingModeInfo>
  }>('/shooting-assistant/modes')
}