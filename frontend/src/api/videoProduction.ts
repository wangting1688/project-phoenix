import request from '@/utils/request'

export interface ProductionJob {
  id: number
  title: string
  job_type: string
  status: string
  progress: number
  source_plan_id: number | null
  video_project_id: number | null
  creator_id: number | null
  product_id: number | null
  target_platforms: string[] | null
  total_duration: number
  estimated_duration: number
  variant_count: number
  timeline_generated: boolean
  material_matched: boolean
  subtitle_ready: boolean
  bgm_ready: boolean
  cover_ready: boolean
  rendering_done: boolean
  blocked_reasons: string[] | null
  created_at: string
}

export interface VideoTimeline {
  id: number
  sequence: number
  start_time: number
  end_time: number
  duration: number
  layer: string
  content_type: string
  source_type: string | null
  source_id: number | null
  role: string | null
  segment_type: string | null
  status: string
  material_found: boolean
  material_duration: number
  material_gap: number
  effect_config: Record<string, any> | null
  transition_config: Record<string, any> | null
  subtitle_config: Record<string, any> | null
  audio_config: Record<string, any> | null
}

export interface VideoVariant {
  id: number
  platform: string
  strategy: string | null
  target_duration: number
  actual_duration: number
  status: string
  director_score: number
  variant_config: Record<string, any> | null
  output_video_url: string | null
}

export interface ProductionBlockTask {
  id: number
  production_job_id: number
  block_type: string
  priority: string
  status: string
  required_content_type: string | null
  required_duration: number
  gap_duration: number
  target_role: string | null
  target_emotion: string | null
  reason: string | null
  suggested_action: string | null
}

const STATUS_LABELS: Record<string, { label: string; type: string }> = {
  pending: { label: '待处理', type: 'info' },
  timeline_generating: { label: '时间线生成中', type: 'primary' },
  material_matching: { label: '素材匹配中', type: 'primary' },
  editing: { label: '剪辑中', type: 'primary' },
  subtitle: { label: '字幕处理中', type: 'primary' },
  bgm: { label: 'BGM处理中', type: 'primary' },
  cover: { label: '封面处理中', type: 'primary' },
  rendering: { label: '渲染中', type: 'warning' },
  completed: { label: '已完成', type: 'success' },
  blocked: { label: '已阻塞', type: 'danger' },
  failed: { label: '失败', type: 'danger' },
}

const PLATFORM_LABELS: Record<string, string> = {
  douyin: '抖音',
  wechat_video: '视频号',
  xiaohongshu: '小红书',
  kuaishou: '快手',
  bilibili: 'B站',
}

const STRATEGY_LABELS: Record<string, string> = {
  traffic: '流量版',
  conversion: '成交版',
  content: '种草版',
  community: '社群版',
  balanced: '均衡版',
}

const ROLE_LABELS: Record<string, string> = {
  hook: 'Hook',
  pain_point: '痛点',
  knowledge: '知识',
  product: '产品',
  conversion: '成交',
  social_proof: '信任',
}

export {
  STATUS_LABELS,
  PLATFORM_LABELS,
  STRATEGY_LABELS,
  ROLE_LABELS,
}

export function createProductionJob(data: {
  title: string
  source_plan_id?: number
  video_project_id?: number
  creator_id?: number
  product_id?: number
  target_platforms?: string[]
  job_type?: string
}) {
  return request.post<{
    success: boolean
    data: {
      job_id: number
      title: string
      status: string
      created_at: string
    }
  }>('/video-production/jobs', null, { params: data })
}

export function getProductionJobs(status?: string, page?: number, page_size?: number) {
  return request.get<{
    success: boolean
    data: {
      jobs: ProductionJob[]
      total: number
      page: number
      page_size: number
    }
  }>('/video-production/jobs', { params: { status, page, page_size } })
}

export function getProductionJob(jobId: number) {
  return request.get<{
    success: boolean
    data: ProductionJob
  }>(`/video-production/jobs/${jobId}`)
}

export function updateJobStatus(jobId: number, status: string) {
  return request.put<{
    success: boolean
    data: {
      job_id: number
      status: string
    }
  }>(`/video-production/jobs/${jobId}/status`, null, { params: { status } })
}

export function generateTimeline(jobId: number) {
  return request.post<{
    success: boolean
    message: string
    data: Record<string, any>
  }>(`/video-production/jobs/${jobId}/timeline`)
}

export function getJobTimeline(jobId: number) {
  return request.get<{
    success: boolean
    data: VideoTimeline[]
  }>(`/video-production/jobs/${jobId}/timeline`)
}

export function matchMaterials(jobId: number) {
  return request.post<{
    success: boolean
    message: string
    data: Record<string, any>
  }>(`/video-production/jobs/${jobId}/match-materials`)
}

export function generateClipProject(jobId: number) {
  return request.post<{
    success: boolean
    message: string
    data: Record<string, any>
  }>(`/video-production/jobs/${jobId}/clip-project`)
}

export function generateVariants(jobId: number, platforms?: string[]) {
  return request.post<{
    success: boolean
    message: string
    data: Record<string, any>
  }>(`/video-production/jobs/${jobId}/variants`, null, { params: { platforms } })
}

export function getJobVariants(jobId: number) {
  return request.get<{
    success: boolean
    data: VideoVariant[]
  }>(`/video-production/jobs/${jobId}/variants`)
}

export function checkBlockTasks(jobId: number) {
  return request.post<{
    success: boolean
    data: {
      block_count: number
      tasks: ProductionBlockTask[]
    }
  }>(`/video-production/jobs/${jobId}/check-blocks`)
}

export function getBlockTasks(status?: string) {
  return request.get<{
    success: boolean
    data: ProductionBlockTask[]
  }>('/video-production/block-tasks', { params: { status } })
}

export function resolveBlockTask(taskId: number, collectionTaskId?: number) {
  return request.put<{
    success: boolean
    data: {
      task_id: number
      status: string
    }
  }>(`/video-production/block-tasks/${taskId}/resolve`, null, { params: { collection_task_id: collectionTaskId } })
}

export function getProductionStats() {
  return request.get<{
    success: boolean
    data: {
      total_jobs: number
      completed_jobs: number
      blocked_jobs: number
      total_variants: number
      completion_rate: number
    }
  }>('/video-production/stats')
}
