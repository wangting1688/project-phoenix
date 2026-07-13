import request from '@/utils/request'

export interface RecommendationItem {
  level: string
  title: string
  category: string
  reason: string
  score: number
  topic: string
}

export interface CreatorProfile {
  id: number
  style?: string
  speech_speed?: string
  good_topics?: string[]
  fan_age_range?: string
  overall_score?: number
}

export function getRecommendations() {
  return request.get('/intelligence/recommendations')
}

export function getProfile() {
  return request.get('/intelligence/profile')
}

export function updateProfile(data: Partial<CreatorProfile>) {
  return request.put('/intelligence/profile', data)
}

export function getContentTags() {
  return request.get('/intelligence/tags')
}
