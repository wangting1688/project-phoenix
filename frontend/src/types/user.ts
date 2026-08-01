export interface User {
  id: number
  phone: string
  nickname?: string
  avatar?: string
  role: string
  status: number
  tenant_id?: number | null
  created_at: string
}

export interface LoginResponse {
  token: string
  user: User
}

export interface CurrentUserResponse {
  id: number
  nickname?: string
  avatar?: string
  content_profile?: {
    style: string
    category: string
  }
}

// ========== 用户（账号主体 / 租户） ==========
export interface Tenant {
  id: number
  name: string
  code: string
  account: string
  contact_name?: string
  contact_phone?: string
  expires_at?: string | null
  status: number
  max_users: number
  max_video_projects: number
  config?: Record<string, unknown> | null
  created_at: string
  updated_at?: string
}

export interface TenantListResponse {
  items: Tenant[]
  total: number
}

export interface TenantLoginResponse {
  token: string
  tenant: Tenant
}
