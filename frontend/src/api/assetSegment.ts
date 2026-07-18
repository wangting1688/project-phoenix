import request from '@/utils/request'

export interface AssetSegmentItem {
  id: number
  asset_id: number
  segment_number: number
  start_time: number
  end_time: number
  duration: number
  segment_role: string
  emotion: string
  purpose: string
  description: string
  tags: string[]
  quality_score: number
  conversion_score: number
  reuse_score: number
  scene_type: string
  usage_count: number
}

export interface CreatorPerformanceProfile {
  user_id: number
  best_emotion: string
  best_scene: string
  best_segment_roles: string[]
  emotion_scores: Record<string, { count: number; total_score: number }>
  scene_scores: Record<string, { count: number; total_score: number }>
  overall_performance_score: number
  analyzed_segments: number
  total_usage_count: number
  last_updated_at: string
}

export interface SegmentSearchParams {
  segment_role?: string
  emotion?: string
  min_duration?: number
  max_duration?: number
  min_score?: number
  exclude_segment_ids?: number[]
  limit?: number
}

export interface SegmentStats {
  total_segments: number
  avg_quality_score: number
  avg_duration: number
  role_distribution: Record<string, number>
  emotion_distribution: Record<string, number>
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

export function createSegments(assetId: number) {
  return request.post<{
    success: boolean
    message: string
    data: {
      asset_id: number
      segments_count: number
      segments: Array<{
        id: number
        segment_number: number
        segment_role: string
        emotion: string
        duration: number
        quality_score: number
      }>
    }
  }>('/asset-segments', { asset_id: assetId })
}

export function getSegmentsByAsset(assetId: number) {
  return request.get<{
    success: boolean
    data: {
      asset_id: number
      segments: AssetSegmentItem[]
    }
  }>(`/asset-segments/${assetId}`)
}

export function getSegmentDetail(assetId: number, segmentId: number) {
  return request.get<{
    success: boolean
    data: AssetSegmentItem
  }>(`/asset-segments/${assetId}/${segmentId}`)
}

export function searchSegments(params: SegmentSearchParams) {
  return request.post<{
    success: boolean
    data: {
      total: number
      segments: AssetSegmentItem[]
    }
  }>('/asset-segments/search', params)
}

export function getCreatorProfile(userId: number) {
  return request.get<{
    success: boolean
    data: CreatorPerformanceProfile | null
    message?: string
  }>(`/asset-segments/profile/${userId}`)
}

export function refreshCreatorProfile(userId: number) {
  return request.post<{
    success: boolean
    message: string
    data: {
      user_id: number
      best_emotion: string
      best_scene: string
      overall_performance_score: number
      analyzed_segments: number
    }
  }>(`/asset-segments/profile/${userId}/refresh`)
}

export function getSegmentStats(userId: number) {
  return request.get<{
    success: boolean
    data: SegmentStats
  }>(`/asset-segments/stats/${userId}`)
}

export function batchCreateSegments(assetIds: number[]) {
  return request.post<{
    success: boolean
    message: string
    data: Array<{
      asset_id: number
      success: boolean
      segments_count?: number
      error?: string
    }>
  }>('/asset-segments/batch-create', assetIds)
}
