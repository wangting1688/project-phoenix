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
