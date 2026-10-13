<template>
  <div class="notice-page">
    <div class="page-header">
      <h2>通知中心</h2>
      <p>任务完成、失败与重要提醒</p>
    </div>

    <div class="page-container">
      <div class="notice-toolbar">
        <span class="unread-text" v-if="unread > 0">{{ unread }} 条未读</span>
        <el-button size="small" text type="primary" :disabled="!items.length" @click="readAll">
          全部已读
        </el-button>
      </div>

      <div v-if="items.length" class="notice-list">
        <div
          v-for="n in items"
          :key="n.id"
          class="notice-item card"
          :class="{ unread: !n.is_read }"
          @click="openNotice(n)"
        >
          <div class="notice-dot" v-if="!n.is_read"></div>
          <div class="notice-body">
            <div class="notice-title">{{ n.title }}</div>
            <div class="notice-content">{{ n.content }}</div>
            <div class="notice-time">{{ formatTime(n.created_at) }}</div>
          </div>
        </div>
      </div>
      <el-empty v-else description="暂无通知" />
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { useRouter } from 'vue-router'
import {
  listNotifications,
  getUnreadCount,
  markNotificationRead,
  markAllNotificationsRead,
  type NotificationItem,
} from '@/api/notifications'

const router = useRouter()
const items = ref<NotificationItem[]>([])
const unread = ref(0)

async function load() {
  try {
    items.value = await listNotifications(50) || []
    unread.value = (await getUnreadCount())?.count || 0
  } catch {
    items.value = []
  }
}

function formatTime(iso: string | null) {
  if (!iso) return ''
  const d = new Date(iso)
  return `${d.getMonth() + 1}/${d.getDate()} ${String(d.getHours()).padStart(2, '0')}:${String(d.getMinutes()).padStart(2, '0')}`
}

async function openNotice(n: NotificationItem) {
  if (!n.is_read) {
    await markNotificationRead(n.id).catch(() => null)
    n.is_read = true
    unread.value = Math.max(0, unread.value - 1)
  }
  if (n.link) router.push(n.link)
}

async function readAll() {
  await markAllNotificationsRead().catch(() => null)
  items.value.forEach((n) => { n.is_read = true })
  unread.value = 0
}

onMounted(load)
</script>

<style scoped>
.notice-page {
  min-height: 100vh;
  background: #f5f7fa;
  padding-bottom: 60px;
}

.page-header {
  background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
  padding: 30px 20px 40px;
  color: #fff;
  text-align: center;
}

.page-header h2 {
  font-size: 22px;
  margin-bottom: 6px;
}

.page-header p {
  font-size: 13px;
  opacity: 0.9;
}

.page-container {
  max-width: 768px;
  margin: -20px auto 0;
  padding: 0 12px;
}

.notice-toolbar {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 4px 2px 12px;
}

.unread-text {
  font-size: 13px;
  color: #e6a23c;
}

.notice-item {
  display: flex;
  gap: 10px;
  padding: 14px;
  margin-bottom: 10px;
  cursor: pointer;
}

.notice-item.unread {
  border-left: 3px solid #667eea;
}

.notice-dot {
  width: 8px;
  height: 8px;
  border-radius: 50%;
  background: #f56c6c;
  margin-top: 6px;
  flex-shrink: 0;
}

.notice-title {
  font-size: 15px;
  font-weight: 600;
  margin-bottom: 4px;
}

.notice-content {
  font-size: 13px;
  color: #606266;
  line-height: 1.5;
  word-break: break-word;
}

.notice-time {
  font-size: 12px;
  color: #909399;
  margin-top: 6px;
}
</style>
