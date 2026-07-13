import request from '@/utils/request'

export interface ScriptAnalysis {
  keywords: string[]
  duration_estimate: number
  scene_count: number
}

export interface ScenePlan {
  index: number
  footage_id: number
  footage_path: string
  start: number
  duration: number
  subtitles: Subtitle[]
}

export interface Subtitle {
  text: string
  start: string
  end: string
  start_sec: number
  end_sec: number
}

export interface TTSConfig {
  text: string
  voice: string
  speed: number
  pitch: number
  format: string
  sample_rate: number
}

export interface BgmConfig {
  style: string
  volume: number
}

export interface CoverConfig {
  title: string
  subtitle: string
  bg_color: string
  text_color: string
  font_size: number
  format: string
  size: string
}

export interface OutputFormat {
  resolution: string
  aspect_ratio: string
  video_codec: string
  audio_codec: string
  container: string
  fps: number
}

export interface CompositionPlan {
  script_analysis: ScriptAnalysis
  scene_plan: ScenePlan[]
  subtitles: Subtitle[]
  tts_config: TTSConfig
  bgm_config: BgmConfig
  cover_config: CoverConfig
  total_duration: number
  output_format: OutputFormat
  ffmpeg_commands: string[]
}

export interface QualityScore {
  realism: number
  info_value: number
  rhythm: number
  subtitle_quality: number
  risk_safety: number
  total: number
  pass: boolean
}

export interface ComposeResult {
  plan: CompositionPlan
  quality: QualityScore
  video_id: number
  script_type: string
  footage_count: number
}

export interface VideoPlanInfo {
  scripts: Array<{
    id: number
    type: string
    content: string
    score: number | null
  }>
  footage_count: number
  ready_to_compose: boolean
}

export function composeVideo(projectId: number, scriptId?: number) {
  const params = scriptId ? { script_id: scriptId } : {}
  return request.post(`/video/compose/${projectId}`, null, { params })
}

export function getVideoPlan(projectId: number) {
  return request.get(`/video/plan/${projectId}`)
}
