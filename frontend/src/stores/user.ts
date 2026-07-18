import { defineStore } from 'pinia'
import { ref, computed } from 'vue'
import { login as loginApi, register as registerApi, getCurrentUser } from '@/api/auth'
import type { User, LoginResponse } from '@/types/user'

const mockUsers: Record<string, User> = {
  '13800138000': {
    id: 1,
    phone: '13800138000',
    nickname: '测试主播',
    avatar: '',
    role: 'creator',
    created_at: new Date().toISOString(),
  },
  '13900139000': {
    id: 2,
    phone: '13900139000',
    nickname: '管理员',
    avatar: '',
    role: 'admin',
    created_at: new Date().toISOString(),
  },
}

export const useUserStore = defineStore('user', () => {
  const token = ref<string>(localStorage.getItem('token') || '')
  const userInfo = ref<User | null>(null)

  const isLoggedIn = computed(() => !!token.value)

  async function login(phone: string, password: string) {
    if (mockUsers[phone] && password === '123456') {
      const mockUser = mockUsers[phone]
      token.value = `mock_token_${phone}`
      userInfo.value = mockUser
      localStorage.setItem('token', token.value)
      return {
        token: token.value,
        user: mockUser,
      } as LoginResponse
    }

    const res = await loginApi(phone, password)
    token.value = res.token
    userInfo.value = res.user
    localStorage.setItem('token', res.token)
    return res
  }

  async function register(phone: string, password: string, nickname?: string) {
    const res = await registerApi(phone, password, nickname)
    token.value = res.token
    userInfo.value = res.user
    localStorage.setItem('token', res.token)
    return res
  }

  async function fetchUserInfo() {
    if (!token.value) return null
    try {
      const res = await getCurrentUser()
      userInfo.value = res as unknown as User
      return res
    } catch (error) {
      logout()
      throw error
    }
  }

  function logout() {
    token.value = ''
    userInfo.value = null
    localStorage.removeItem('token')
  }

  return {
    token,
    userInfo,
    isLoggedIn,
    login,
    register,
    fetchUserInfo,
    logout,
  }
})
