import request from '@/utils/request'

export interface DirectorLearningStats {
  total_videos: number
  total_publish_records: number
  total_memories: number
  verified_memories: number
  memory_type_stats: Record<string, number>
  learning_progress: number
}

export interface LearningMemory {
  id: number
  memory_type: string
  condition: Record<string, any>
  recommendation: Record<string, any>
  confidence_score: number
  usage_count: number
  success_count: number
  source_data_points: number
  is_verified: boolean
  created_at: string
}

export interface CreatorStrategyProfile {
  best_content_type: string
  best_content_types: string[]
  best_hook_style: string
  best_camera_style: string
  best_duration_range: string
  best_conversion_style: string
  weak_styles: string[]
  platform_performance: Record<string, any>
  strategy_recommendation: string
  analyzed_videos: number
  last_updated: string
}

export interface PlatformStrategyProfile {
  platform: string
  platform_role: string
  best_content_types: string[]
  best_duration_range: string
  best_publish_times: string[]
  avg_views: number
  avg_completion_rate: number
  avg_conversion_rate: number
  total_published: number
  weight_config: Record<string, number>
}

export interface PlatformScore {
  platform: string
  overall_score: number
  traffic_score: number
  engagement_score: number
  conversion_score: number
  customer_value_score: number
  score_breakdown: Record<string, { score: number; weight: number }>
  platform_specific: Record<string, number>
}

const MEMORY_TYPE_LABELS: Record<string, string> = {
  template_success: '模板成功经验',
  segment_success: '片段成功经验',
  creator_success: '主播成功经验',
  product_success: '产品成功经验',
  platform_success: '平台成功经验',
  hook_success: '开场成功经验',
  strategy_pattern: '策略模式',
}

const PLATFORM_LABELS: Record<string, string> = {
  douyin: '抖音',
  wechat_video: '视频号',
  xiaohongshu: '小红书',
  kuaishou: '快手',
  bilibili: 'B站',
}

const PLATFORM_ROLE_LABELS: Record<string, string> = {
  traffic: '流量增长主阵地',
  conversion: '转化成交主阵地',
  content: '内容资产沉淀',
  community: '粉丝社群运营',
  balanced: '均衡发展',
}

export {
  MEMORY_TYPE_LABELS,
  PLATFORM_LABELS,
  PLATFORM_ROLE_LABELS,
}

export function getLearningStats() {
  return request.get<{
    success: boolean
    data: DirectorLearningStats
  }>('/director-learning/stats')
}

export function getLearningMemories(memory_type?: string, min_confidence?: number, limit?: number) {
  return request.get<{
    success: boolean
    data: LearningMemory[]
  }>('/director-learning/memories', { params: { memory_type, min_confidence, limit } })
}

export function getCreatorStrategy() {
  return request.get<{
    success: boolean
    data: CreatorStrategyProfile | null
    message?: string
  }>('/director-learning/creator-strategy')
}

export function getPlatformStrategies() {
  return request.get<{
    success: boolean
    data: PlatformStrategyProfile[]
  }>('/director-learning/platform-strategies')
}

export function getVideoPlatformScores(videoId: number) {
  return request.get<{
    success: boolean
    data: PlatformScore[]
  }>(`/director-learning/videos/${videoId}/platform-scores`)
}

export function runDirectorReview(videoId: number) {
  return request.post<{
    success: boolean
    message: string
    data: Record<string, any>
  }>(`/director-learning/videos/${videoId}/review`)
}

export function calculateDirectorScore(planId: number, targetPlatform: string = 'wechat_video') {
  return request.post<{
    success: boolean
    data: {
      plan_id: number
      target_platform: string
      director_score: number
      score_breakdown: Record<string, { score: number; max: number; reason: string }>
      score_reasons: string[]
    }
  }>('/director-learning/calculate-score', null, { params: { plan_id: planId, target_platform: targetPlatform } })
}

export function getPhoenixCommercialWeights() {
  return request.get<{
    success: boolean
    data: {
      description: string
      weights: Record<string, { name: string; weight: string }>
      philosophy: string
      core_platforms: Record<string, string>
    }
  }>('/director-learning/weights/phoenix-commercial')
}
