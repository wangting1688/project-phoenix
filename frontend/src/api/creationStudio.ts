import request from '@/utils/request'

export interface StyleTemplate {
  name: string
  description: string
  structure: string
}

export interface CreationConfig {
  style: string
  duration: number
  tone: string
  style_name: string
  tone_name: string
}

export interface CreationResult {
  session_id: number
  project_id: number
  topic: string
  config: CreationConfig
  script: string
  planning: {
    target: string
    style: string
    duration: number
    strategy: string
  }
  review: {
    original_score: number
    marketing_score: number
    risk_score: number
    consult_score: number
    result: string
  }
}

export function getTemplates() {
  return request.get<{
    success: boolean
    data: {
      styles: Record<string, StyleTemplate>
      tones: Record<string, string>
      durations: Record<number, string>
    }
  }>('/creation-studio/templates')
}

export function createSession(data: {
  source_type: string
  opportunity_id?: number
  topic?: string
}) {
  return request.post<{
    success: boolean
    data: {
      session_id: number
      status: string
      current_step: string
    }
  }>('/creation-studio/sessions', data)
}

export function configureSession(data: {
  session_id: number
  style: string
  duration: number
  tone: string
}) {
  return request.post<{
    success: boolean
    data: {
      session_id: number
      config: CreationConfig
      current_step: string
    }
  }>('/creation-studio/configure', data)
}

export function generateContent(session_id: number) {
  return request.post<{
    success: boolean
    data: CreationResult
  }>('/creation-studio/generate', { session_id })
}

export function getSession(session_id: number) {
  return request.get<{
    success: boolean
    data: {
      session_id: number
      status: string
      current_step: string
      config: CreationConfig
      result: CreationResult | null
      created_at: string
      updated_at: string
    }
  }>(`/creation-studio/sessions/${session_id}`)
}