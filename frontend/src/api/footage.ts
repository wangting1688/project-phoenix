import request from '@/utils/request'

export interface FootageCategory {
  id: number
  name: string
  type: string
  icon?: string
}

export interface Footage {
  id: number
  category_id?: number
  filename: string
  thumbnail?: string
  duration: number
  scene?: string
  emotion?: string
  action?: string
  topics?: string[]
  status: string
  source_type: string
  source_ref?: string
  created_at: string
}

/** 素材拍摄质量检测结果。口型合成的效果上限由素材光线决定，
 *  上传时即给出反馈，避免用户等 8 分钟渲染完才发现是废片。 */
export interface FootageQuality {
  level: 'good' | 'fair' | 'poor'
  brightness: { avg: number | null; min: number | null; max: number | null }
  face_ratio: number | null
  /** null 表示未检测（检测服务不可达），不等于不合格 */
  has_face: boolean | null
  warnings: string[]
  suitable_for_lipsync: boolean
}

export interface UploadFootageResult extends Footage {
  quality?: FootageQuality
}

export interface SuggestShot {
  scene: string
  action: string
  emotion: string
}

export function getCategories() {
  return request.get<unknown, FootageCategory[]>('/footage/categories')
}

export function createCategory(name: string, type: string) {
  return request.post<unknown, FootageCategory>('/footage/categories', { name, type })
}

export function uploadFootage(
  file: File,
  categoryId?: number,
  onProgress?: (percent: number) => void,
) {
  const formData = new FormData()
  formData.append('file', file)
  if (categoryId) formData.append('category_id', String(categoryId))
  return request.post<unknown, UploadFootageResult>('/footage/upload', formData, {
    headers: { 'Content-Type': 'multipart/form-data' },
    // 大素材上传要几十秒，默认 3 分钟超时不够；单独放宽到 30 分钟
    timeout: 30 * 60 * 1000,
    onUploadProgress: (e) => {
      if (!onProgress || !e.total) return
      onProgress(Math.round((e.loaded * 100) / e.total))
    },
  })
}

/** 复检已有素材（上传于检测功能上线前的素材也能查） */
export function checkFootageQuality(id: number) {
  return request.get<unknown, FootageQuality>(`/footage/${id}/quality`)
}

export interface FootageListResult {
  items: Footage[]
  total: number
  page: number
  size: number
}

export function listFootages(params?: { category_id?: number; scene?: string; page?: number; size?: number }) {
  return request.get<unknown, FootageListResult>('/footage/list', { params })
}

export function updateFootage(id: number, data: Partial<Footage>) {
  return request.put(`/footage/${id}`, data)
}

export function deleteFootage(id: number) {
  return request.delete(`/footage/${id}`)
}

export function getSuggestShots() {
  return request.get<unknown, Record<string, SuggestShot[]>>('/footage/suggest-shots')
}


export function restoreDemoFootages() {
  return request.post<unknown, { restored_count: number }>('/footage/restore-demo')
}


/** 上传 H3 图生视频的主播照片，返回 person_image 路径 */
export function uploadAnchorPortrait(file: File) {
  const formData = new FormData()
  formData.append('file', file)
  return request.post<unknown, { person_image: string; url: string; filename: string }>(
    '/footage/anchor-portrait', formData,
    { headers: { 'Content-Type': 'multipart/form-data' }, timeout: 120000 },
  )
}

export interface AnchorPortrait {
  filename: string
  person_image: string
  url: string
}

export function listAnchorPortraits() {
  return request.get<unknown, { items: AnchorPortrait[] }>('/footage/anchor-portraits')
}

export function deleteAnchorPortrait(filename: string) {
  return request.delete<unknown, { success: boolean }>(`/footage/anchor-portraits/${filename}`)
}

export interface AnchorScene {
  filename: string
  scene_image: string
  url: string
}

export function uploadAnchorScene(file: File) {
  const formData = new FormData()
  formData.append('file', file)
  return request.post<unknown, { scene_image: string; url: string; filename: string }>(
    '/footage/anchor-scenes', formData,
    { headers: { 'Content-Type': 'multipart/form-data' }, timeout: 120000 },
  )
}

export function listAnchorScenes() {
  return request.get<unknown, { items: AnchorScene[] }>('/footage/anchor-scenes')
}

export function deleteAnchorScene(filename: string) {
  return request.delete<unknown, { success: boolean }>(`/footage/anchor-scenes/${filename}`)
}
