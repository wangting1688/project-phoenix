import request from '@/utils/request'

export interface ContentProject {
  id: number
  user_id: number
  source_type: string
  topic: string
  category?: string
  status: string
  workflow_status?: string
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
}

export function createProject(source_type: string, topic: string, category?: string) {
  return request.post('/creation/projects', { source_type, topic, category })
}

export function listProjects(page = 1, size = 20) {
  return request.get('/creation/projects', { params: { page, size } })
}

export function getProject(project_id: number) {
  return request.get(`/creation/projects/${project_id}`)
}

export function getProjectScripts(project_id: number) {
  return request.get(`/creation/projects/${project_id}/scripts`)
}

export function getTaskStatus(task_id: number) {
  return request.get(`/tasks/${task_id}`)
}

export function getTaskResult(task_id: number) {
  return request.get(`/tasks/${task_id}/result`)
}

export function getTaskScripts(task_id: number) {
  return request.get(`/tasks/${task_id}/scripts`)
}
