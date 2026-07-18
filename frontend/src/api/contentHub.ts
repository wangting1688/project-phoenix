import request from '@/utils/request'

export interface ContentOpportunity {
  id: number
  title: string
  category: string
  opening: string
  summary: string
  trend_score: number
  consult_score: number
  creator_match: number
  original_score: number
  final_score: number
  created_at: string
}

export interface OpportunityDetail extends ContentOpportunity {
  pain_point: string
  recommend_reason: string
  subcategory: string
  source: string
}

export interface CategoryData {
  title: string
  description: string
  items: ContentOpportunity[]
}

export function getTodayRecommendations() {
  return request.get<{ success: boolean; data: Record<string, CategoryData> }>('/content-hub/today')
}

export function getRecommendations(category: string, count: number = 5) {
  return request.get<{ success: boolean; data: ContentOpportunity[] }>('/content-hub/recommendations', {
    params: { category, count }
  })
}

export function getOpportunityDetail(id: number) {
  return request.get<{ success: boolean; data: OpportunityDetail }>(`/content-hub/opportunities/${id}`)
}

export function refreshRecommendations(category: string) {
  return request.post<{ success: boolean; data: ContentOpportunity[] }>('/content-hub/refresh', {
    category
  })
}