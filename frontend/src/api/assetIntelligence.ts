import request from '@/utils/request'

export interface AssetSearchParams {
  query?: string
  scene_type?: string
  emotion?: string
  style?: string
  topics?: string[]
  tags?: string[]
  min_score?: number
  asset_role?: string
  limit?: number
}

export interface AssetSegment {
  index: number
  start: number
  end: number
  duration: number
  score: number
  emotion: string
  tags: string[]
  description: string
}

export interface AssetIntelligence {
  asset_id: number
  status: string
  duration: number
  overall_score: number
  quality_score: number
  face_visibility: string
  face_score: number
  eye_contact: string
  emotion_primary: string
  emotion_secondary: string
  emotion_score: number
  scene_type: string
  scene_score: number
  background_cleanliness: string
  speech_detected: boolean
  speech_score: number
  voice_tone: string
  style: string
  topics: string[]
  tags: string[]
  segments: AssetSegment[]
  analysis_result: {
    summary: string
    confidence: number
  }
  usage_count: number
}

export interface SearchResult {
  asset: {
    id: number
    name: string
    type: string
    asset_role: string
    url: string
    duration: number
    scene: string | null
    emotion: string | null
    tags: string[] | null
  }
  intelligence: AssetIntelligence
  match_score: number
  overall_score: number
}

export interface SmartRecommendResult extends SearchResult {
  recommend_reason: string
}

export interface ScoreBreakdown {
  overall: number
  dimensions: {
    visual_quality: { score: number; weight: number; weighted: number }
    person_performance: { score: number; weight: number; weighted: number }
    emotion_power: { score: number; weight: number; weighted: number }
    content_match: { score: number; weight: number; weighted: number }
    originality: { score: number; weight: number; weighted: number }
  }
}

export interface IntelligenceStats {
  total_assets: number
  analyzed_count: number
  pending_count: number
  average_score: number
  high_score_count: number
  analysis_rate: number
}

export function analyzeAsset(assetId: number) {
  return request.post<{
    success: boolean
    data: {
      asset_id: number
      status: string
      overall_score: number
      analysis_result: any
    }
  }>(`/asset-intelligence/analyze/${assetId}`)
}

export function batchAnalyze(assetIds?: number[]) {
  return request.post<{
    success: boolean
    data: {
      total: number
      completed: number
      failed: number
      details: any[]
    }
  }>('/asset-intelligence/analyze/batch', { asset_ids: assetIds })
}

export function getAnalysisResult(assetId: number) {
  return request.get<{
    success: boolean
    data: AssetIntelligence
  }>(`/asset-intelligence/result/${assetId}`)
}

export function searchAssets(params: AssetSearchParams) {
  return request.post<{
    success: boolean
    data: SearchResult[]
    total: number
  }>('/asset-intelligence/search', params)
}

export function smartRecommend(scriptContent: string, shotType?: string) {
  return request.post<{
    success: boolean
    data: SmartRecommendResult[]
    total: number
  }>('/asset-intelligence/smart-recommend', {
    script_content: scriptContent,
    shot_type: shotType,
  })
}

export function findBestSegments(requirements: any[]) {
  return request.post<{
    success: boolean
    data: any[]
  }>('/asset-intelligence/find-segments', { requirements })
}

export function getAssetScore(assetId: number) {
  return request.get<{
    success: boolean
    data: ScoreBreakdown
  }>(`/asset-intelligence/score/${assetId}`)
}

export function getIntelligenceStats() {
  return request.get<{
    success: boolean
    data: IntelligenceStats
  }>('/asset-intelligence/stats')
}
