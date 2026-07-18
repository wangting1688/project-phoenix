import request from '@/utils/request'

export interface VideoRecord {
  publish_record_id: number
  video_master_id: number
  title: string
  platform: string
  publish_url: string | null
  publish_status: string
  views: number
  likes: number
  comments: number
  favorites: number
  shares: number
  private_message_count: number
  data_updated_at: string | null
  created_at: string | null
}

export interface RegisterVideoParams {
  platform: string
  title: string
  publish_url?: string | null
  video_master_id?: number | null
  script_content?: string | null
  duration?: number | null
}

export interface RegisterVideoResult {
  publish_record_id: number
  video_master_id: number
  platform: string
  publish_url: string | null
  publish_status: string
}

export interface DailySnapshotPayload {
  views?: number
  likes?: number
  comments?: number
  favorites?: number
  shares?: number
  private_message_count?: number
  top_comments?: string[]
  completion_rate?: number
  first_3_second_retention?: number
  first_5_second_retention?: number
  avg_watch_time?: number
  follows?: number
  exposures?: number
  reach?: number
}

export interface DailySnapshotParams {
  publish_record_id: number
  mode?: 'manual' | 'browser' | 'official_api'
  source_client?: string | null
  snapshot_date?: string | null
  payload: DailySnapshotPayload
}

export interface DailySnapshotResult {
  snapshot_id: number
  publish_record_id: number
  snapshot_date: string
  source_mode: string
  views: number
  likes: number
  comments: number
  favorites: number
  shares: number
  private_message_count: number
}

export interface SnapshotItem {
  id: number
  snapshot_date: string
  source_mode: string
  views: number
  likes: number
  comments: number
  favorites: number
  shares: number
  private_message_count: number
  created_at: string | null
}

export function listVideos(limit = 50) {
  return request.get<unknown, VideoRecord[]>('/ingest/videos', { params: { limit } })
}

export function registerVideo(params: RegisterVideoParams) {
  return request.post<unknown, RegisterVideoResult>('/ingest/videos', params)
}

export function reportDailySnapshot(params: DailySnapshotParams) {
  return request.post<unknown, DailySnapshotResult>('/ingest/daily', params)
}

export function listSnapshots(publishRecordId: number, limit = 30) {
  return request.get<unknown, SnapshotItem[]>(
    `/ingest/videos/${publishRecordId}/snapshots`,
    { params: { limit } },
  )
}
