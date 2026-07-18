import request from '@/utils/request'

export interface ShootingGuide {
  scene: string
  action: string
  emotion: string
  duration_min: number
  duration_max: number
  tips: string[]
}

export interface AssetRecommendation {
  rank: number
  title: string
  priority: 'high' | 'medium' | 'low'
  reason: string
  estimated_minutes: number
  tags: string[]
  emotion: string
  scene: string
  shooting_guide: ShootingGuide
}

export interface DailyRecommendation {
  recommend_date: string
  recommendations: AssetRecommendation[]
  total_recommended: number
  high_priority_count: number
  total_estimated_time: number
}

export interface CollectionTask {
  task_id: number
  title: string
  description: string | null
  priority: 'high' | 'medium' | 'low'
  asset_type: string
  asset_role: string
  shooting_guide: ShootingGuide | null
  tags: string[] | null
  scene: string | null
  emotion: string | null
  status: 'pending' | 'in_progress' | 'completed' | 'skipped'
  progress: number
  estimated_time: number
  created_at: string
}

export interface AssetLibraryStats {
  total_assets: number
  total_duration: number
  by_role: Record<string, number>
  by_scene: Record<string, number>
  by_emotion: Record<string, number>
  tasks_total: number
  tasks_completed: number
  completion_rate: number
}

export function getDailyRecommendation() {
  return request.get<{
    success: boolean
    data: DailyRecommendation
  }>('/asset-collection/daily')
}

export function createCollectionTask(data: {
  title: string
  asset_type?: string
  asset_role?: string
  priority?: string
  description?: string
  shooting_guide?: ShootingGuide
  tags?: string[]
  scene?: string
  emotion?: string
  estimated_time?: number
}) {
  return request.post<{
    success: boolean
    data: {
      task_id: number
      title: string
      priority: string
      status: string
    }
  }>('/asset-collection/tasks', data)
}

export function getCollectionTasks(status?: string, priority?: string) {
  return request.get<{
    success: boolean
    data: CollectionTask[]
  }>('/asset-collection/tasks', {
    params: { status, priority },
  })
}

export function updateTaskStatus(taskId: number, status: string, uploadedAssetId?: number) {
  return request.post<{
    success: boolean
    data: {
      task_id: number
      status: string
      progress: number
    }
  }>(`/asset-collection/tasks/${taskId}/status`, {
    status,
    uploaded_asset_id: uploadedAssetId,
  })
}

export function getAssetLibraryStats() {
  return request.get<{
    success: boolean
    data: AssetLibraryStats
  }>('/asset-collection/stats')
}

export function getAssetCategories(type: string = 'creator') {
  return request.get<{
    success: boolean
    data: Array<{
      id: number
      name: string
      description: string | null
      shooting_tips: string[] | null
      recommended_duration: number
      is_required: number
    }>
  }>('/asset-collection/categories', {
    params: { type },
  })
}