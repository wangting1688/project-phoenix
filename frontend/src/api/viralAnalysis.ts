import request from '@/utils/request'

export interface AnalysisBasicInfo {
  title: string
  platform: string
  duration: number
  like_count: number
  comment_count: number
  share_count: number
  collect_count: number
}

export interface ContentStructure {
  opening: string
  middle?: string
  climax?: string
  ending: string
}

export interface AnalysisResult {
  basic_info: AnalysisBasicInfo
  content_structure: ContentStructure
  hook_type: string
  hook: string
  viral_points: string
  viral_score: number
  emotions: string[]
  category: string
  subcategory: string
  target_audience: string
  pain_point: string
  summary: string
  trend_score: number
  consult_score: number
  commercial_fit: {
    fit_for: string[]
    not_fit_for: string[]
  }
  success_factors: string[]
  creator_match_score: number
}

export interface OpportunityResult {
  session_id: number
  opportunity_id: number
  opportunity: {
    id: number
    title: string
    category: string
    opening: string
    final_score: number
  }
  original_analysis: AnalysisResult
}

export interface AnalysisSession {
  session_id: number
  video_url: string
  platform: string
  status: string
  creator_match_score: number
  original_data: AnalysisBasicInfo
  analysis_result: AnalysisResult
  opportunity_id: number
  created_at: string
}

export function createAnalysis(video_url: string) {
  return request.post<{
    success: boolean
    data: {
      session_id: number
      video_url: string
      platform: string
      status: string
    }
  }>('/viral-analysis/create', { video_url })
}

export function analyzeVideo(session_id: number) {
  return request.post<{
    success: boolean
    data: AnalysisResult
  }>(`/viral-analysis/${session_id}/analyze`)
}

export function getAnalysisResult(session_id: number) {
  return request.get<{
    success: boolean
    data: AnalysisSession
  }>(`/viral-analysis/${session_id}`)
}

export function generateOpportunity(session_id: number) {
  return request.post<{
    success: boolean
    data: OpportunityResult
  }>(`/viral-analysis/${session_id}/generate`)
}