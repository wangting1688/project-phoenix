import request from '@/utils/request'

export interface NotificationItem {
  id: number
  type: string
  title: string
  content: string
  link: string
  is_read: boolean
  created_at: string | null
}

export function listNotifications(limit = 50) {
  return request.get<unknown, NotificationItem[]>('/notifications', {
    params: { limit },
  })
}

export function getUnreadCount() {
  return request.get<unknown, { count: number }>('/notifications/unread-count')
}

export function markNotificationRead(id: number) {
  return request.post<unknown, { id: number; is_read: boolean }>(`/notifications/${id}/read`)
}

export function markAllNotificationsRead() {
  return request.post<unknown, { ok: boolean }>('/notifications/read-all')
}
