import request from '@/utils/request'


export interface PaginatedResponse<T> {
  items: T[]
  total: number
  page: number
  size: number
}

export interface ContentProject {
  id: number
  user_id: number
  source_type: string
  topic: string
  category?: string
  status: string
  workflow_status?: string
  video_url?: string | null
  video_duration?: number | null
  video_status?: string | null
  cover_url?: string | null
  display_status?: string
  error_message?: string | null
  created_at: string
  updated_at: string
}

export interface Script {
  id: number
  project_id: number
  type: string
  content: string
  version: number
  score?: string
}

export interface VideoInfo {
  id: number
  project_id: number
  url?: string
  cover_url?: string
  duration?: number
  status: string
}

export interface TaskStatus {
  task_id: number
  status: string
  progress: number
  current_step?: string
  error_message?: string
  /** 0 = 正在执行，>0 = 前面还有几个任务在排队 */
  queue_position?: number | null
  queue_total?: number | null
  /** 预计还需等待的秒数 */
  eta_seconds?: number | null
}

export function createProject(source_type: string, topic: string, category?: string) {
  return request.post<unknown, { project_id: number; task_id: number; status: string }>('/creation/projects', { source_type, topic, category })
}

export function listProjects(page = 1, size = 20) {
  return request.get<unknown, PaginatedResponse<ContentProject>>(
    '/creation/projects',
    { params: { page, size } }
  )
}

export function getProjects(page = 1, size = 50) {
  return request.get<unknown, PaginatedResponse<ContentProject>>(`/creation/projects`, { params: { page, size } })
}

export function deleteProject(project_id: number) {
  return request.delete<unknown, { success: boolean }>(`/creation/projects/${project_id}`)
}

export function getProject(project_id: number) {
  return request.get<unknown, ContentProject & { video_url?: string | null; video_duration?: number | null }>(`/creation/projects/${project_id}`)
}

export function getProjectScripts(project_id: number) {
  return request.get<unknown, Script[]>(`/creation/projects/${project_id}/scripts`)
}

export function getTaskStatus(task_id: number) {
  return request.get<unknown, TaskStatus>(`/tasks/${task_id}`)
}

export function getTaskResult(task_id: number) {
  return request.get<unknown, { scripts: Script[]; video: VideoInfo | null; project_id: number }>(`/tasks/${task_id}/result`)
}

export function getTaskScripts(task_id: number) {
  return request.get<unknown, Script[]>(`/tasks/${task_id}/scripts`)
}

export function updateScript(script_id: number, content: string) {
  return request.patch<unknown, Script>(`/creation/scripts/${script_id}`, { content })
}
