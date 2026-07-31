import request from '@/utils/request'

export function getPublishTasks(params?: { status?: string; platform?: string }) {
  return request.get('/publish-tasks', { params })
}

export function createPublishTask(data: {
  content_title: string
  content_description?: string
  platform_account_id: number
  platform: string
  video_project_id?: number
  scheduled_at?: string
  tags?: string[]
  category?: string
  video_url?: string
  cover_url?: string
}) {
  return request.post('/publish-tasks', data)
}

export function updatePublishTask(id: number, data: Partial<{
  content_title: string
  content_description: string
  scheduled_at: string
  tags: string[]
  status: string
  review_status: string
  review_comment: string
}>) {
  return request.put(`/publish-tasks/${id}`, data)
}

export function deletePublishTask(id: number) {
  return request.delete(`/publish-tasks/${id}`)
}

export function triggerPublish(id: number) {
  return request.post(`/publish-tasks/${id}/publish`)
}

export function collectMetrics(id: number, data: {
  play_count?: number
  like_count?: number
  comment_count?: number
  share_count?: number
  collect_count?: number
  follower_gained?: number
  completion_rate?: number
  ctr?: number
}) {
  return request.post(`/publish-tasks/${id}/collect-metrics`, data)
}

export function autoCollectMetrics(id: number) {
  return request.post(`/publish-tasks/${id}/auto-collect`)
}

export function autoReviewTask(id: number) {
  return request.post(`/publish-tasks/${id}/auto-review`)
}

export function runFullPipeline(id: number) {
  return request.post(`/publish-tasks/${id}/full-pipeline`)
}
