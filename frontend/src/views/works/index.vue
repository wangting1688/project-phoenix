<template>
  <div class="works-page">
    <div class="page-header">
      <h2>我的作品</h2>
      <p>查看你创作的所有视频</p>
    </div>

    <div class="page-container">
      <div class="filter-tabs">
        <div
          v-for="tab in tabs"
          :key="tab.value"
          class="tab-item"
          :class="{ active: activeTab === tab.value }"
          @click="activeTab = tab.value"
        >
          {{ tab.label }}
        </div>
      </div>

      <div v-if="works.length > 0" class="works-grid">
        <div
          v-for="work in works"
          :key="work.id"
          class="work-card card"
          @click="viewWork(work)"
        >
          <div class="work-cover">
            <div class="cover-placeholder">
              <el-icon :size="40"><IVideoCamera /></el-icon>
            </div>
            <div v-if="work.status === 'processing'" class="processing-overlay">
              <el-icon class="loading-icon" :size="32"><ILoading /></el-icon>
              <span>生成中...</span>
            </div>
            <div v-if="work.status === 'completed'" class="play-btn">
              <el-icon :size="32"><IVideoPlay /></el-icon>
            </div>
          </div>
          <div class="work-info">
            <h4 class="work-title">{{ work.topic }}</h4>
            <div class="work-meta">
              <span class="status" :class="work.status">
                {{ getStatusText(work.status) }}
              </span>
              <span class="date">{{ formatDate(work.created_at) }}</span>
            </div>
          </div>
        </div>
      </div>

      <div v-else class="empty-state">
        <el-empty description="还没有作品，去创作一个吧！">
          <el-button type="primary" @click="$router.push('/creation')">
            开始创作
          </el-button>
        </el-empty>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, computed } from 'vue'
import { useRouter } from 'vue-router'
import {
  IVideoCamera,
  IVideoPlay,
  ILoading,
} from '@element-plus/icons-vue'

const router = useRouter()

const activeTab = ref('all')

const tabs = [
  { label: '全部', value: 'all' },
  { label: '生成中', value: 'processing' },
  { label: '已完成', value: 'completed' },
  { label: '草稿', value: 'draft' },
]

const works = ref<Array<{
  id: number
  topic: string
  status: string
  created_at: string
}>>([])

const filteredWorks = computed(() => {
  if (activeTab.value === 'all') return works.value
  return works.value.filter(w => w.status === activeTab.value)
})

function getStatusText(status: string) {
  const map: Record<string, string> = {
    draft: '草稿',
    processing: '生成中',
    completed: '已完成',
    failed: '失败',
  }
  return map[status] || status
}

function formatDate(dateStr: string) {
  if (!dateStr) return ''
  const date = new Date(dateStr)
  return `${date.getMonth() + 1}/${date.getDate()}`
}

function viewWork(work: { id: number }) {
  console.log('查看作品:', work.id)
}
</script>

<style scoped>
.works-page {
  min-height: 100vh;
  background: #f5f7fa;
}

.page-header {
  background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
  padding: 40px 20px 50px;
  color: #fff;
  text-align: center;
}

.page-header h2 {
  font-size: 24px;
  margin-bottom: 8px;
}

.page-header p {
  font-size: 14px;
  opacity: 0.9;
}

.page-container {
  padding: 0 16px;
  max-width: 768px;
  margin: -30px auto 0;
}

.filter-tabs {
  display: flex;
  background: #fff;
  border-radius: 12px;
  padding: 4px;
  margin-bottom: 16px;
  box-shadow: 0 2px 12px rgba(0, 0, 0, 0.08);
}

.tab-item {
  flex: 1;
  text-align: center;
  padding: 10px 0;
  font-size: 14px;
  color: #606266;
  border-radius: 8px;
  cursor: pointer;
  transition: all 0.3s;
}

.tab-item.active {
  background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
  color: #fff;
  font-weight: 500;
}

.works-grid {
  display: grid;
  grid-template-columns: repeat(2, 1fr);
  gap: 12px;
}

.work-card {
  padding: 0;
  overflow: hidden;
  cursor: pointer;
  transition: transform 0.2s;
}

.work-card:active {
  transform: scale(0.98);
}

.work-cover {
  position: relative;
  width: 100%;
  aspect-ratio: 9 / 16;
  background: linear-gradient(135deg, #667eea20, #764ba220);
  display: flex;
  align-items: center;
  justify-content: center;
  color: #667eea;
}

.cover-placeholder {
  opacity: 0.5;
}

.processing-overlay {
  position: absolute;
  top: 0;
  left: 0;
  right: 0;
  bottom: 0;
  background: rgba(0, 0, 0, 0.5);
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  color: #fff;
  font-size: 12px;
}

.loading-icon {
  animation: spin 1s linear infinite;
  margin-bottom: 6px;
}

@keyframes spin {
  from { transform: rotate(0deg); }
  to { transform: rotate(360deg); }
}

.play-btn {
  position: absolute;
  top: 50%;
  left: 50%;
  transform: translate(-50%, -50%);
  color: #fff;
  opacity: 0.8;
}

.work-info {
  padding: 12px;
}

.work-title {
  font-size: 14px;
  color: #303133;
  margin-bottom: 8px;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.work-meta {
  display: flex;
  justify-content: space-between;
  align-items: center;
  font-size: 12px;
}

.status {
  padding: 2px 8px;
  border-radius: 10px;
  font-size: 11px;
}

.status.completed {
  background: #f0f9eb;
  color: #67c23a;
}

.status.processing {
  background: #ecf5ff;
  color: #409eff;
}

.status.draft {
  background: #f4f4f5;
  color: #909399;
}

.status.failed {
  background: #fef0f0;
  color: #f56c6c;
}

.date {
  color: #c0c4cc;
}

.empty-state {
  background: #fff;
  border-radius: 12px;
  padding: 60px 20px;
  text-align: center;
}
</style>
