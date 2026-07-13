import { defineStore } from 'pinia'
import { ref, computed } from 'vue'
import { login as loginApi, register as registerApi, getCurrentUser } from '@/api/auth'
import type { User, LoginResponse } from '@/types/user'

export const useUserStore = defineStore('user', () => {
  const token = ref<string>(localStorage.getItem('token') || '')
  const userInfo = ref<User | null>(null)

  const isLoggedIn = computed(() => !!token.value)

  async function login(phone: string, password: string) {
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
