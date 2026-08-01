import request from '@/utils/request'

export interface VoiceProfile {
  id: number
  name: string
  custom_speaker_id: string | null
  status: 'training' | 'active' | 'failed' | 'deleted'
  volc_status: number
  available_training_times: number
  sample_duration: number | null
  language: number
  reference_text: string
  demo_text: string
  demo_audio_url: string | null
  error_message: string | null
  created_at: string | null
  updated_at: string | null
}

export function getVoiceProfiles() {
  return request.get('/voice-profiles')
}

export function getVoiceProfile(id: number) {
  return request.get(`/voice-profiles/${id}`)
}

export function uploadVoiceSample(data: FormData) {
  return request.post('/voice-profiles', data, {
    headers: { 'Content-Type': 'multipart/form-data' },
  })
}

export function trainVoiceProfile(id: number) {
  return request.post(`/voice-profiles/${id}/train`)
}

export function testVoiceProfile(id: number, text?: string) {
  return request.post<unknown, { audio_url: string; duration_hint: number }>(`/voice-profiles/${id}/test`, null, {
    params: text ? { text } : undefined,
  })
}

export function deleteVoiceProfile(id: number) {
  return request.delete(`/voice-profiles/${id}`)
}

export interface SampleScript {
  id: string
  title: string
  text: string
}

export function getSampleScripts() {
  return request.get('/voice-profiles/sample-scripts')
}
