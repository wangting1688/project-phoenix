<template>
  <div class="asset-collection-page">
    <!-- 页面标题 -->
    <div class="page-header">
      <h1>📸 素材采集中心</h1>
    </div>

    <!-- 统计卡片 -->
    <div class="stats-grid">
      <div class="stat-card">
        <div class="stat-icon">🎬</div>
        <div class="stat-info">
          <span class="stat-value">{{ stats.total_assets }}</span>
          <span class="stat-label">素材总数</span>
        </div>
      </div>
      <div class="stat-card">
        <div class="stat-icon">⏱️</div>
        <div class="stat-info">
          <span class="stat-value">{{ formatDuration(stats.total_duration) }}</span>
          <span class="stat-label">总时长</span>
        </div>
      </div>
      <div class="stat-card">
        <div class="stat-icon">✅</div>
        <div class="stat-info">
          <span class="stat-value">{{ stats.tasks_completed }}/{{ stats.tasks_total }}</span>
          <span class="stat-label">完成任务</span>
        </div>
      </div>
      <div class="stat-card">
        <div class="stat-icon">📊</div>
        <div class="stat-info">
          <span class="stat-value">{{ stats.completion_rate }}%</span>
          <span class="stat-label">完成率</span>
        </div>
      </div>
    </div>

    <!-- 今日推荐 -->
    <div class="daily-section">
      <div class="section-header">
        <h2>🌟 今日建议补充素材</h2>
        <div class="daily-meta">
          <span>共 {{ dailyRec.total_recommended }} 个</span>
          <span>预计 {{ dailyRec.total_estimated_time }} 分钟</span>
        </div>
      </div>

      <div class="recommendations-list">
        <div
          v-for="rec in dailyRec.recommendations"
          :key="rec.rank"
          class="rec-card"
          :class="rec.priority"
        >
          <div class="rec-header">
            <div class="rec-rank">
              <span class="rank-num">{{ rec.rank }}</span>
            </div>
            <div class="rec-info">
              <h3 class="rec-title">{{ rec.title }}</h3>
              <p class="rec-reason">{{ rec.reason }}</p>
            </div>
            <div class="rec-priority">
              <el-tag v-if="rec.priority === 'high'" type="danger" size="small">必须</el-tag>
              <el-tag v-else-if="rec.priority === 'medium'" type="warning" size="small">建议</el-tag>
              <el-tag v-else type="info" size="small">可选</el-tag>
            </div>
          </div>

          <div class="rec-meta">
            <span v-if="rec.estimated_minutes > 0">⏱️ {{ rec.estimated_minutes }}分钟</span>
            <span v-for="tag in rec.tags" :key="tag" class="rec-tag">#{{ tag }}</span>
          </div>

          <!-- 拍摄指导 -->
          <div v-if="rec.shooting_guide && rec.shooting_guide.tips" class="shooting-guide">
            <div class="guide-header" @click="toggleGuide(rec.rank)">
              <span>📷 拍摄指导</span>
              <el-icon class="arrow"><IArrowDown /></el-icon>
            </div>
            <div v-if="expandedGuides.includes(rec.rank)" class="guide-content">
              <div class="guide-grid">
                <div class="guide-item">
                  <span class="guide-label">场景</span>
                  <span class="guide-value">{{ rec.shooting_guide.scene }}</span>
                </div>
                <div class="guide-item">
                  <span class="guide-label">动作</span>
                  <span class="guide-value">{{ rec.shooting_guide.action }}</span>
                </div>
                <div class="guide-item">
                  <span class="guide-label">情绪</span>
                  <span class="guide-value">{{ rec.shooting_guide.emotion }}</span>
                </div>
                <div class="guide-item">
                  <span class="guide-label">时长</span>
                  <span class="guide-value">{{ rec.shooting_guide.duration_min }}-{{ rec.shooting_guide.duration_max }}秒</span>
                </div>
              </div>
              <div class="guide-tips">
                <h5>拍摄要点：</h5>
                <ul>
                  <li v-for="(tip, index) in rec.shooting_guide.tips" :key="index">{{ tip }}</li>
                </ul>
              </div>
            </div>
          </div>

          <div class="rec-actions">
            <el-button size="small" @click="uploadAsset(rec)">
              📤 上传素材
            </el-button>
            <el-button size="small" type="primary" @click="startTask(rec)">
              ▶️ 开始拍摄
            </el-button>
          </div>
        </div>
      </div>
    </div>

    <!-- 任务列表 -->
    <div class="tasks-section">
      <div class="section-header">
        <h2>📋 采集任务</h2>
        <div class="task-tabs">
          <div
            v-for="tab in taskTabs"
            :key="tab.value"
            :class="['tab-item', { active: activeTaskTab === tab.value }]"
            @click="activeTaskTab = tab.value"
          >
            {{ tab.label }}
          </div>
        </div>
      </div>

      <div v-if="filteredTasks.length > 0" class="tasks-list">
        <div
          v-for="task in filteredTasks"
          :key="task.task_id"
          class="task-item"
        >
          <div class="task-info">
            <h4 class="task-title">{{ task.title }}</h4>
            <div class="task-meta">
              <el-tag size="small" :type="getPriorityType(task.priority)">
                {{ getPriorityLabel(task.priority) }}
              </el-tag>
              <span>⏱️ {{ task.estimated_time }}分钟</span>
            </div>
          </div>
          <div class="task-status">
            <el-progress
              :percentage="task.progress"
              :stroke-width="8"
              :color="task.status === 'completed' ? '#67c23a' : '#409eff'"
            />
            <span class="status-text">{{ getStatusLabel(task.status) }}</span>
          </div>
        </div>
      </div>
      <div v-else class="empty-tasks">
        <el-empty description="暂无任务" />
      </div>
    </div>

    <!-- 素材库分类 -->
    <div class="library-section">
      <div class="section-header">
        <h2>🗂️ 素材分类</h2>
      </div>

      <div class="category-stats">
        <div class="stat-row">
          <span class="stat-label">按角色：</span>
          <div class="stat-tags">
            <el-tag v-for="(count, role) in stats.by_role" :key="role" class="stat-tag">
              {{ getRoleLabel(role) }}: {{ count }}
            </el-tag>
          </div>
        </div>
        <div class="stat-row">
          <span class="stat-label">按场景：</span>
          <div class="stat-tags">
            <el-tag v-for="(count, scene) in stats.by_scene" :key="scene" class="stat-tag">
              {{ scene }}: {{ count }}
            </el-tag>
          </div>
        </div>
        <div class="stat-row">
          <span class="stat-label">按情绪：</span>
          <div class="stat-tags">
            <el-tag v-for="(count, emotion) in stats.by_emotion" :key="emotion" class="stat-tag">
              {{ emotion }}: {{ count }}
            </el-tag>
          </div>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, onMounted } from 'vue'
import { ElMessage } from 'element-plus'
import { IArrowDown } from '@/utils/icons'
import {
  getDailyRecommendation,
  getCollectionTasks,
  getAssetLibraryStats,
  type DailyRecommendation,
  type CollectionTask,
  type AssetLibraryStats,
} from '@/api/assetCollection'

const dailyRec = ref<DailyRecommendation>({
  recommend_date: '',
  recommendations: [],
  total_recommended: 0,
  high_priority_count: 0,
  total_estimated_time: 0,
})

const tasks = ref<CollectionTask[]>([])
const stats = ref<AssetLibraryStats>({
  total_assets: 0,
  total_duration: 0,
  by_role: {},
  by_scene: {},
  by_emotion: {},
  tasks_total: 0,
  tasks_completed: 0,
  completion_rate: 0,
})

const activeTaskTab = ref('pending')
const expandedGuides = ref<number[]>([])

const taskTabs = [
  { label: '待完成', value: 'pending' },
  { label: '进行中', value: 'in_progress' },
  { label: '已完成', value: 'completed' },
]

const filteredTasks = computed(() => {
  return tasks.value.filter(t => t.status === activeTaskTab.value)
})

const formatDuration = (seconds: number) => {
  if (seconds < 60) return `${seconds}秒`
  return `${(seconds / 60).toFixed(1)}分钟`
}

const getPriorityType = (priority: string) => {
  const types: Record<string, string> = {
    high: 'danger',
    medium: 'warning',
    low: 'info',
  }
  return types[priority] || 'info'
}

const getPriorityLabel = (priority: string) => {
  const labels: Record<string, string> = {
    high: '必须',
    medium: '建议',
    low: '可选',
  }
  return labels[priority] || priority
}

const getStatusLabel = (status: string) => {
  const labels: Record<string, string> = {
    pending: '待完成',
    in_progress: '进行中',
    completed: '已完成',
    skipped: '已跳过',
  }
  return labels[status] || status
}

const getRoleLabel = (role: string) => {
  const labels: Record<string, string> = {
    creator: '主播素材',
    b_roll: '辅助素材',
    background: '背景素材',
  }
  return labels[role] || role
}

const toggleGuide = (rank: number) => {
  const index = expandedGuides.value.indexOf(rank)
  if (index > -1) {
    expandedGuides.value.splice(index, 1)
  } else {
    expandedGuides.value.push(rank)
  }
}

const loadData = async () => {
  try {
    const [dailyRes, tasksRes, statsRes] = await Promise.all([
      getDailyRecommendation(),
      getCollectionTasks(),
      getAssetLibraryStats(),
    ])

    if (dailyRes.data.success) {
      dailyRec.value = dailyRes.data.data
    }
    if (tasksRes.data.success) {
      tasks.value = tasksRes.data.data
    }
    if (statsRes.data.success) {
      stats.value = statsRes.data.data
    }
  } catch (error) {
    console.error('Load data failed:', error)
  }
}

const uploadAsset = (rec: any) => {
  ElMessage.info('素材上传功能即将上线')
}

const startTask = (rec: any) => {
  ElMessage.success(`开始拍摄：${rec.title}`)
}

onMounted(() => {
  loadData()
})
</script>

<style scoped>
.asset-collection-page {
  padding: 16px;
}

.page-header {
  margin-bottom: 20px;
}

.page-header h1 {
  font-size: 24px;
  margin: 0;
}

/* 统计卡片 */
.stats-grid {
  display: grid;
  grid-template-columns: repeat(2, 1fr);
  gap: 12px;
  margin-bottom: 20px;
}

.stat-card {
  background: white;
  border-radius: 12px;
  padding: 16px;
  box-shadow: 0 2px 8px rgba(0, 0, 0, 0.05);
  display: flex;
  align-items: center;
  gap: 12px;
}

.stat-icon {
  font-size: 32px;
}

.stat-info {
  display: flex;
  flex-direction: column;
}

.stat-value {
  font-size: 20px;
  font-weight: 600;
  color: #333;
}

.stat-label {
  font-size: 12px;
  color: #888;
}

/* 每日推荐 */
.daily-section {
  margin-bottom: 24px;
}

.section-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 16px;
}

.section-header h2 {
  font-size: 18px;
  margin: 0;
}

.daily-meta {
  display: flex;
  gap: 12px;
  font-size: 12px;
  color: #888;
}

.recommendations-list {
  display: flex;
  flex-direction: column;
  gap: 12px;
}

.rec-card {
  background: white;
  border-radius: 12px;
  padding: 16px;
  box-shadow: 0 2px 8px rgba(0, 0, 0, 0.05);
  border-left: 4px solid #e0e0e0;
}

.rec-card.high {
  border-left-color: #f56c6c;
  background: linear-gradient(90deg, #fef0f020, #fff 30%);
}

.rec-card.medium {
  border-left-color: #e6a23c;
}

.rec-card.low {
  border-left-color: #909399;
}

.rec-header {
  display: flex;
  gap: 12px;
  margin-bottom: 12px;
}

.rec-rank {
  width: 36px;
  height: 36px;
  background: #667eea;
  color: white;
  border-radius: 50%;
  display: flex;
  align-items: center;
  justify-content: center;
  flex-shrink: 0;
}

.rank-num {
  font-size: 16px;
  font-weight: 600;
}

.rec-info {
  flex: 1;
}

.rec-title {
  margin: 0 0 4px;
  font-size: 15px;
  font-weight: 500;
}

.rec-reason {
  margin: 0;
  font-size: 13px;
  color: #888;
}

.rec-meta {
  display: flex;
  gap: 8px;
  flex-wrap: wrap;
  margin-bottom: 12px;
  font-size: 12px;
  color: #666;
}

.rec-tag {
  color: #667eea;
}

/* 拍摄指导 */
.shooting-guide {
  background: #f8f9fa;
  border-radius: 8px;
  margin-bottom: 12px;
  overflow: hidden;
}

.guide-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 10px 12px;
  cursor: pointer;
  font-size: 13px;
  font-weight: 500;
}

.guide-header .arrow {
  transition: transform 0.2s;
}

.guide-content {
  padding: 0 12px 12px;
}

.guide-grid {
  display: grid;
  grid-template-columns: repeat(2, 1fr);
  gap: 8px;
  margin-bottom: 12px;
}

.guide-item {
  background: white;
  padding: 8px 10px;
  border-radius: 4px;
}

.guide-label {
  display: block;
  font-size: 11px;
  color: #888;
  margin-bottom: 2px;
}

.guide-value {
  font-size: 13px;
  color: #333;
}

.guide-tips h5 {
  font-size: 12px;
  margin: 0 0 8px;
  color: #666;
}

.guide-tips ul {
  list-style: none;
  padding: 0;
  margin: 0;
}

.guide-tips li {
  padding: 4px 0;
  font-size: 12px;
  color: #555;
  padding-left: 16px;
  position: relative;
}

.guide-tips li::before {
  content: '•';
  position: absolute;
  left: 4px;
  color: #667eea;
}

.rec-actions {
  display: flex;
  gap: 8px;
  justify-content: flex-end;
}

/* 任务列表 */
.tasks-section {
  background: white;
  border-radius: 12px;
  padding: 20px;
  box-shadow: 0 2px 8px rgba(0, 0, 0, 0.05);
  margin-bottom: 24px;
}

.task-tabs {
  display: flex;
  gap: 16px;
}

.tab-item {
  font-size: 14px;
  color: #888;
  cursor: pointer;
  padding-bottom: 4px;
}

.tab-item.active {
  color: #667eea;
  border-bottom: 2px solid #667eea;
}

.tasks-list {
  display: flex;
  flex-direction: column;
  gap: 12px;
}

.task-item {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 12px;
  background: #f8f9fa;
  border-radius: 8px;
}

.task-title {
  margin: 0 0 6px;
  font-size: 14px;
}

.task-meta {
  display: flex;
  gap: 8px;
  font-size: 12px;
  color: #888;
  align-items: center;
}

.task-status {
  width: 120px;
  text-align: center;
}

.task-status .el-progress {
  margin-bottom: 4px;
}

.status-text {
  font-size: 12px;
  color: #888;
}

.empty-tasks {
  padding: 30px 0;
}

/* 素材库分类 */
.library-section {
  background: white;
  border-radius: 12px;
  padding: 20px;
  box-shadow: 0 2px 8px rgba(0, 0, 0, 0.05);
}

.category-stats {
  display: flex;
  flex-direction: column;
  gap: 16px;
}

.stat-row {
  display: flex;
  align-items: flex-start;
  gap: 12px;
}

.stat-label {
  font-size: 13px;
  color: #888;
  min-width: 60px;
  flex-shrink: 0;
}

.stat-tags {
  display: flex;
  gap: 8px;
  flex-wrap: wrap;
}

.stat-tag {
  margin: 0;
}
</style>