export interface User {
  id: number
  phone: string
  nickname?: string
  avatar?: string
  role: string
  status: number
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
