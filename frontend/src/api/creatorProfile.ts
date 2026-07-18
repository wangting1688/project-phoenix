import request from '@/utils/request'

export interface CreatorProfileData {
  id: number
  user_id: number
  age?: number
  gender?: string
  region?: string
  background?: string
  style?: string
  speech_speed: string
  emotion_level: string
  content_style?: Record<string, any>
  speaking_style?: Record<string, any>
  camera_style?: string
  editing_level: string
  good_topics: string[]
  category_distribution: Record<string, number>
  fan_age_range?: string
  fan_gender_ratio?: string
  fan_interests: string[]
  audience_profile: Record<string, any>
  account_type: string
  growth_stage: string
  overall_score: number
  created_at?: string
}

export interface CreatorPreference {
  id: number
  user_id: number
  category_weights: Record<string, number>
  style_weights: Record<string, number>
  score_weights: Record<string, number>
  preferred_tags: string[]
  avoided_tags: string[]
  updated_at?: string
}

export interface AccountDiagnosis {
  account_type: string
  growth_stage: string
  overall_score: number
  strengths: string[]
  improvements: string[]
  content_style: {
    primary_style: string
    tone: string
    pace: string
  }
  category_distribution: Record<string, number>
  audience_insights: {
    primary_age: string
    primary_gender: string
    top_interests: string[]
  }
  recommendations: string[]
}

export function getCreatorProfile() {
  return request.get<{ success: boolean; data: { profile: CreatorProfileData; preference: CreatorPreference | null } }>('/creator-profile')
}

export function updateCreatorProfile(data: Partial<CreatorProfileData>) {
  return request.put<{ success: boolean; data: CreatorProfileData }>('/creator-profile', data)
}

export function getCreatorPreference() {
  return request.get<{ success: boolean; data: CreatorPreference | null }>('/creator-profile/preference')
}

export function updateCreatorPreference(data: Partial<CreatorPreference>) {
  return request.put<{ success: boolean; data: CreatorPreference }>('/creator-profile/preference', data)
}

export function diagnoseAccount() {
  return request.post<{ success: boolean; data: AccountDiagnosis }>('/creator-profile/diagnose')
}