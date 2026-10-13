import request from '@/utils/request'
import type { LoginResponse, CurrentUserResponse } from '@/types/user'

export function login(phone: string, password: string) {
  return request.post<unknown, LoginResponse>('/auth/login', {
    phone,
    password,
  })
}

export function register(phone: string, password: string, nickname?: string) {
  return request.post<unknown, LoginResponse>('/auth/register', {
    phone,
    password,
    nickname,
  })
}

export function getCurrentUser() {
  return request.get<unknown, CurrentUserResponse>('/auth/me')
}

export function wechatConfig() {
  return request.get<unknown, { enabled: boolean; app_id: string }>('/auth/wechat/config')
}

export function wechatLoginUrl(redirectUri: string) {
  return request.get<unknown, { url: string }>('/auth/wechat/login-url', {
    params: { redirect_uri: redirectUri },
  })
}

export function wechatCallback(code: string) {
  return request.get<unknown, LoginResponse>('/auth/wechat/callback', {
    params: { code },
  })
}
