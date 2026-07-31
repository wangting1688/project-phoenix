import request from '@/utils/request'

export function getPlatformAccounts(params?: { platform?: string }) {
  return request.get('/platform-accounts', { params })
}

export function createPlatformAccount(data: {
  platform: string
  account_name: string
  account_id?: string
  account_url?: string
  content_style?: string
  strategy_config?: Record<string, any>
}) {
  return request.post('/platform-accounts', data)
}

export function updatePlatformAccount(id: number, data: Partial<{
  account_name: string
  account_url: string
  content_style: string
  strategy_config: Record<string, any>
  status: string
}>) {
  return request.put(`/platform-accounts/${id}`, data)
}

export function deletePlatformAccount(id: number) {
  return request.delete(`/platform-accounts/${id}`)
}
