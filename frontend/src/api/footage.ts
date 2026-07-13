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
  created_at: string
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
  return request.post('/footage/upload', formData, {
    headers: { 'Content-Type': 'multipart/form-data' },
  })
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
