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
  return request.get('/footage/categories')
}

export function createCategory(name: string, type: string) {
  return request.post('/footage/categories', { name, type })
}

export function uploadFootage(file: File, categoryId?: number) {
  const formData = new FormData()
  formData.append('file', file)
  if (categoryId) formData.append('category_id', String(categoryId))
  return request.post<unknown, UploadFootageResult>('/footage/upload', formData, {
    headers: { 'Content-Type': 'multipart/form-data' },
  })
}

/** 复检已有素材（上传于检测功能上线前的素材也能查） */
export function checkFootageQuality(id: number) {
  return request.get<unknown, FootageQuality>(`/footage/${id}/quality`)
}

export function listFootages(params?: { category_id?: number; scene?: string; page?: number; size?: number }) {
  return request.get('/footage/list', { params })
}

export function updateFootage(id: number, data: Partial<Footage>) {
  return request.put(`/footage/${id}`, data)
}

export function deleteFootage(id: number) {
  return request.delete(`/footage/${id}`)
}

export function getSuggestShots() {
  return request.get('/footage/suggest-shots')
}


export function restoreDemoFootages() {
  return request.post<unknown, { restored_count: number }>('/footage/restore-demo')
}
