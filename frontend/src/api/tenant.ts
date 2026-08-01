import request from '@/utils/request'
import type { Tenant, TenantListResponse, TenantLoginResponse } from '@/types/user'

// 渠道商登录
export function tenantLogin(account: string, password: string) {
  return request.post<unknown, TenantLoginResponse>('/tenants/login', {
    account,
    password,
  })
}

// 获取渠道商列表（总部管理员）
export function listTenants(skip = 0, limit = 100) {
  return request.get<unknown, TenantListResponse>('/tenants/', {
    params: { skip, limit },
  })
}

// 创建渠道商（总部管理员）
export function createTenant(data: {
  name: string
  code: string
  account: string
  password: string
  contact_name?: string
  contact_phone?: string
  expires_at?: string
  max_users?: number
  max_video_projects?: number
}) {
  return request.post<unknown, Tenant>('/tenants/', data)
}

// 更新渠道商（总部管理员）
export function updateTenant(id: number, data: Partial<{
  name: string
  contact_name: string
  contact_phone: string
  expires_at: string
  max_users: number
  max_video_projects: number
  status: number
}>) {
  return request.put<unknown, Tenant>(`/tenants/${id}`, data)
}

// 停用渠道商
export function deleteTenant(id: number) {
  return request.delete<unknown, { message: string }>(`/tenants/${id}`)
}

// 获取渠道商下的用户列表
export function listTenantUsers(tenantId: number) {
  return request.get<unknown, { items: Array<{ id: number; phone: string; nickname: string; role: string; status: number }>; total: number }>(`/tenants/${tenantId}/users`)
}

// 创建渠道用户
export function createTenantUser(tenantId: number, data: {
  phone: string
  password: string
  nickname?: string
  role?: string
}) {
  return request.post<unknown, { message: string; user_id: number }>(`/tenants/${tenantId}/users`, data)
}
