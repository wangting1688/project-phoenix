import request from '@/utils/request'

export interface VideoEditSegment {
  id: number
  sequence: number
  role: string
  start_time: number
  end_time: number
  duration: number
  asset_segment_id: number | null
  asset_id: number | null
  source_start_time: number | null
  source_end_time: number | null
  transition: string
  subtitle_style: string
  effect_style: string
  reason: string
  match_status: string
  match_score: number
  subtitle_text: string
  subtitle_highlights: string[]
}

export interface DirectorAnalysis {
  template_name: string
  template_description: string
  target_audience: string
  emotion_flow: string[]
  key_message: string
  conversion_point: string
  recommended_style: string
  creator_best_emotion?: string
  creator_best_scene?: string
  creator_conversion_style?: string
}

export interface ShootingSuggestion {
  role: string
  required: boolean
  description: string
  duration: number
  emotion: string
  tips: string[]
  note?: string
}

export interface VideoEditPlan {
  id: number
  title: string
  total_duration: number
  editing_strategy: string
  match_status: string
  total_shots: number
  matched_shots: number
  missing_shots: number
  director_analysis: DirectorAnalysis
  shooting_suggestions: ShootingSuggestion[]
  predicted_completion_rate: number
  predicted_conversion_rate: number
  director_score: number
  score_breakdown: Record<string, { score: number; max: number; reason: string }>
  score_reasons: string[]
  template_id: number | null
  shooting_task_ids: number[] | null
  status: string
  segments: VideoEditSegment[]
  created_at: string
}

export interface DirectorStats {
  total_plans: number
  matched_plans: number
  partial_plans: number
  total_shots: number
  matched_shots: number
  missing_shots: number
  match_rate: number
  avg_predicted_completion: number
  avg_predicted_conversion: number
}

export const STRATEGY_LABELS: Record<string, string> = {
  standard: '标准型',
  story: '故事型',
  product: '产品型',
  knowledge: '知识型',
}

export const STRATEGY_DESCRIPTIONS: Record<string, string> = {
  standard: '抓人→问题→解释→结尾',
  story: '抓人→问题→情感→信任→结尾',
  product: '抓人→问题→产品→信任→结尾',
  knowledge: '抓人→知识→信任→结尾',
}

export const ROLE_LABELS: Record<string, string> = {
  hook: '开场抓人',
  problem: '提出问题',
  explain: '知识解释',
  trust: '建立信任',
  emotion: '情感共鸣',
  product: '产品关联',
  ending: '结尾互动',
  transition: '过渡转场',
}

export const ROLE_COLORS: Record<string, string> = {
  hook: '#f56c6c',
  problem: '#e6a23c',
  explain: '#409eff',
  trust: '#67c23a',
  emotion: '#909399',
  product: '#f5a623',
  ending: '#667eea',
  transition: '#8e44ad',
}

export const MATCH_STATUS_MAP: Record<string, { label: string; color: string }> = {
  matched: { label: '已匹配', color: '#67c23a' },
  missing: { label: '素材缺失', color: '#f56c6c' },
  partial: { label: '部分匹配', color: '#e6a23c' },
  failed: { label: '匹配失败', color: '#f56c6c' },
  pending: { label: '待匹配', color: '#909399' },
}

export function generatePlan(data: {
  script_content: string
  script_id?: number
  video_project_id?: number
  target_duration?: number
  strategy?: string
}) {
  return request.post<{
    success: boolean
    message: string
    data: VideoEditPlan
  }>('/video-director/generate-plan', data)
}

export function getPlans(status?: string) {
  return request.get<{
    success: boolean
    data: VideoEditPlan[]
  }>('/video-director/plans', { params: { status } })
}

export function getPlanDetail(planId: number) {
  return request.get<{
    success: boolean
    data: VideoEditPlan
  }>(`/video-director/plans/${planId}`)
}

export function updatePlanStatus(planId: number, status: string) {
  return request.put<{
    success: boolean
    data: { plan_id: number; status: string }
  }>(`/video-director/plans/${planId}/status`, { status })
}

export function getShootingSuggestions(planId: number) {
  return request.get<{
    success: boolean
    data: {
      plan_id: number
      title: string
      match_status: string
      total_shots: number
      matched_shots: number
      missing_shots: number
      shooting_suggestions: ShootingSuggestion[]
    }
  }>(`/video-director/plans/${planId}/shooting-suggestions`)
}

export function updateCommercialScores() {
  return request.post<{
    success: boolean
    message: string
    data: { updated_count: number }
  }>('/video-director/update-commercial-scores')
}

export function getDirectorStats() {
  return request.get<{
    success: boolean
    data: DirectorStats
  }>('/video-director/stats')
}

export interface ScriptTemplate {
  id: number
  name: string
  description: string
  template_type: string
  industry: string
  content_type: string
  structure: Array<{
    role: string
    time_range: string
    duration: number
    purpose: string
    emotion: string
    required: boolean
    tips: string
  }>
  best_for: string
  target_audience: string
  conversion_rate: number
  completion_rate: number
  template_score: number
  usage_count: number
  is_preset: boolean
}

export interface ShootingTaskStatus {
  has_tasks: boolean
  total_tasks: number
  completed_count: number
  pending_count: number
  all_completed: boolean
  can_regenerate: boolean
  tasks: Array<{
    id: number
    title: string
    status: string
    uploaded_asset_id: number | null
  }>
}

export function getTemplates(template_type?: string, industry?: string) {
  return request.get<{
    success: boolean
    data: ScriptTemplate[]
  }>('/video-director/templates', { params: { template_type, industry } })
}

export function matchTemplate(script_content: string, target_duration?: number) {
  return request.post<{
    success: boolean
    data: ScriptTemplate | null
    message?: string
  }>('/video-director/match-template', null, { params: { script_content, target_duration } })
}

export function getShootingTasksStatus(planId: number) {
  return request.get<{
    success: boolean
    data: ShootingTaskStatus
  }>(`/video-director/plans/${planId}/shooting-tasks`)
}

export function regeneratePlan(planId: number) {
  return request.post<{
    success: boolean
    message: string
    data: VideoEditPlan | ShootingTaskStatus
  }>(`/video-director/plans/${planId}/regenerate`)
}

export const TEMPLATE_TYPE_LABELS: Record<string, string> = {
  pain_point: '痛点型',
  story: '故事型',
  expert: '专家型',
  product: '产品型',
  knowledge: '知识型',
  emotion: '情感型',
}
