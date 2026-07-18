import request from '@/utils/request'

export interface ReviewScores {
  health: number
  marketing: number
  viral: number
  conversion: number
  originality: number
  final: number
}

export interface HealthAnalysis {
  score: number
  risk_level: string
  issues: string[]
  warnings: string[]
  suggestions: string[]
  summary: string
}

export interface MarketingAnalysis {
  score: number
  risk_level: string
  hard_sells: string[]
  soft_sells: string[]
  has_consult_guide: boolean
  suggestions: string[]
  summary: string
}

export interface ViralAnalysis {
  score: number
  opening_score: number
  climax_score: number
  interaction_score: number
  length_score: number
  content_length: number
  issues: string[]
  suggestions: string[]
  summary: string
}

export interface ConversionAnalysis {
  score: number
  trust_score: number
  guide_score: number
  has_direct_sales: boolean
  suggestions: string[]
  summary: string
}

export interface ReviewAnalysis {
  health: HealthAnalysis
  marketing: MarketingAnalysis
  viral: ViralAnalysis
  conversion: ConversionAnalysis
}

export interface AutoFix {
  type: string
  old: string
  new: string
  reason: string
}

export interface ReviewResult {
  review_id: number
  content_type: string
  content_id: number
  scores: ReviewScores
  risk_level: string
  analysis: ReviewAnalysis
  suggestions: string[]
  auto_fixes: AutoFix[]
  status: string
  created_at: string
}

export interface OptimizeResult {
  original_text: string
  optimized_text: string
  changes: AutoFix[]
  review: ReviewResult
}

export interface QuickCheckResult {
  is_safe: boolean
  health_score: number
  marketing_score: number
  issues: string[]
  suggestions: string[]
}

export function reviewContent(contentType: string, contentId: number, contentText: string) {
  return request.post<{
    success: boolean
    data: ReviewResult
  }>('/quality/review', {
    content_type: contentType,
    content_id: contentId,
    content_text: contentText,
  })
}

export function getReviewResult(reviewId: number) {
  return request.get<{
    success: boolean
    data: ReviewResult
  }>(`/quality/review/${reviewId}`)
}

export function getContentReview(contentType: string, contentId: number) {
  return request.get<{
    success: boolean
    data: ReviewResult
  }>(`/quality/content/${contentType}/${contentId}`)
}

export function optimizeContent(contentType: string, contentId: number, contentText: string) {
  return request.post<{
    success: boolean
    data: OptimizeResult
  }>('/quality/optimize', {
    content_type: contentType,
    content_id: contentId,
    content_text: contentText,
  })
}

export function quickCheck(contentType: string, contentId: number, contentText: string) {
  return request.post<{
    success: boolean
    data: QuickCheckResult
  }>('/quality/quick-check', {
    content_type: contentType,
    content_id: contentId,
    content_text: contentText,
  })
}