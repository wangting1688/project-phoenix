<template>
  <div class="production-page">
    <!-- 页面标题 -->
    <div class="page-header">
      <h1>🏭 AI视频生产工厂</h1>
      <p class="subtitle">视频生产执行编排层 - 从导演方案到视频输出</p>
    </div>

    <!-- 统计概览 -->
    <div class="stats-section">
      <div class="stats-grid">
        <div class="stat-card">
          <span class="stat-icon">📋</span>
          <span class="stat-number">{{ stats.total_jobs }}</span>
          <span class="stat-label">生产任务</span>
        </div>
        <div class="stat-card">
          <span class="stat-icon">✅</span>
          <span class="stat-number">{{ stats.completed_jobs }}</span>
          <span class="stat-label">已完成</span>
        </div>
        <div class="stat-card">
          <span class="stat-icon">⚠️</span>
          <span class="stat-number">{{ stats.blocked_jobs }}</span>
          <span class="stat-label">阻塞中</span>
        </div>
        <div class="stat-card">
          <span class="stat-icon">📦</span>
          <span class="stat-number">{{ stats.total_variants }}</span>
          <span class="stat-label">视频版本</span>
        </div>
        <div class="stat-card full-width">
          <span class="stat-label">完成率</span>
          <span class="stat-number large">{{ stats.completion_rate }}%</span>
          <el-progress :percentage="stats.completion_rate" :stroke-width="8" />
        </div>
      </div>
    </div>

    <!-- 标签页 -->
    <el-tabs v-model="activeTab" class="production-tabs">
      <!-- 任务列表 -->
      <el-tab-pane label="生产任务" name="jobs">
        <div class="job-section">
          <div class="job-header">
            <el-button type="primary" @click="showCreateModal = true">创建任务</el-button>
            <el-select v-model="filterStatus" placeholder="状态筛选" style="width: 120px">
              <el-option label="全部" value="" />
              <el-option label="待处理" value="pending" />
              <el-option label="进行中" :value="['timeline_generating', 'material_matching', 'editing', 'subtitle', 'bgm', 'cover', 'rendering']" />
              <el-option label="已阻塞" value="blocked" />
              <el-option label="已完成" value="completed" />
            </el-select>
          </div>

          <div v-if="jobs.length > 0" class="job-list">
            <div
              v-for="job in jobs"
              :key="job.id"
              class="job-card"
              :class="{ blocked: job.status === 'blocked' }"
              @click="selectJob(job)"
            >
              <div class="job-header">
                <h4>{{ job.title }}</h4>
                <el-tag :type="getStatusType(job.status)">{{ getStatusLabel(job.status) }}</el-tag>
              </div>
              <div class="job-progress">
                <el-progress :percentage="job.progress" :stroke-width="6" />
                <span class="progress-text">{{ job.progress }}%</span>
              </div>
              <div class="job-info">
                <span>⏱️ {{ job.total_duration }}秒</span>
                <span>📦 {{ job.variant_count }}个版本</span>
                <span v-if="job.source_plan_id">🎬 方案#{{ job.source_plan_id }}</span>
              </div>
              <div v-if="job.blocked_reasons?.length" class="job-blocked">
                <el-alert type="error" :title="job.blocked_reasons[0]" :closable="false" show-icon />
              </div>
            </div>
          </div>
          <div v-else class="empty-state">
            <el-empty description="暂无生产任务" />
          </div>
        </div>
      </el-tab-pane>

      <!-- 时间线视图 -->
      <el-tab-pane label="时间线编排" name="timeline">
        <div v-if="selectedJob" class="timeline-section">
          <div class="timeline-header">
            <h3>{{ selectedJob.title }}</h3>
            <el-button type="primary" @click="handleGenerateTimeline">生成时间线</el-button>
          </div>

          <div v-if="timelineItems.length > 0" class="timeline-editor">
            <div class="timeline-track">
              <div class="track-label">主视频轨道</div>
              <div class="track-content">
                <div
                  v-for="item in timelineItems"
                  :key="item.id"
                  class="timeline-item"
                  :class="{
                    matched: item.material_found,
                    missing: !item.material_found,
                  }"
                  :style="{
                    left: `${(item.start_time / totalDuration) * 100}%`,
                    width: `${((item.end_time - item.start_time) / totalDuration) * 100}%`,
                  }"
                >
                  <div class="item-header">
                    <span class="item-role">{{ getRoleLabel(item.role) }}</span>
                    <span class="item-time">{{ item.start_time.toFixed(1) }}-{{ item.end_time.toFixed(1) }}s</span>
                  </div>
                  <div class="item-status">
                    <el-tag size="small" :type="item.material_found ? 'success' : 'danger'">
                      {{ item.material_found ? '已匹配' : '待匹配' }}
                    </el-tag>
                  </div>
                  <div v-if="item.material_gap > 0" class="item-gap">
                    缺口: {{ item.material_gap.toFixed(1) }}s
                  </div>
                </div>
              </div>
              <div class="track-markers">
                <span v-for="m in 10" :key="m" :style="{ left: `${m * 10}%` }">{{ (totalDuration * m / 10).toFixed(0) }}s</span>
              </div>
            </div>
          </div>
          <div v-else class="empty-state">
            <el-empty description="暂无时间线数据" />
          </div>
        </div>
        <div v-else class="empty-state">
          <el-empty description="请先选择一个生产任务" />
        </div>
      </el-tab-pane>

      <!-- 版本管理 -->
      <el-tab-pane label="版本管理" name="variants">
        <div v-if="selectedJob" class="variants-section">
          <div class="variants-header">
            <h3>{{ selectedJob.title }} - 版本列表</h3>
            <el-button type="primary" @click="handleGenerateVariants">生成多平台版本</el-button>
          </div>

          <div v-if="variants.length > 0" class="variants-grid">
            <div v-for="v in variants" :key="v.id" class="variant-card">
              <div class="variant-header">
                <span class="platform-icon">{{ getPlatformIcon(v.platform) }}</span>
                <span class="platform-name">{{ getPlatformLabel(v.platform) }}</span>
                <el-tag :type="getStrategyType(v.strategy)" size="small">
                  {{ getStrategyLabel(v.strategy) }}
                </el-tag>
              </div>
              <div class="variant-info">
                <div class="info-item">
                  <span>目标时长</span>
                  <span class="value">{{ v.target_duration }}秒</span>
                </div>
                <div class="info-item">
                  <span>导演评分</span>
                  <span class="value">{{ v.director_score }}分</span>
                </div>
              </div>
              <div class="variant-status">
                <el-tag :type="getStatusType(v.status)">{{ getStatusLabel(v.status) }}</el-tag>
              </div>
            </div>
          </div>
          <div v-else class="empty-state">
            <el-empty description="暂无版本数据" />
          </div>
        </div>
        <div v-else class="empty-state">
          <el-empty description="请先选择一个生产任务" />
        </div>
      </el-tab-pane>

      <!-- 阻塞任务 -->
      <el-tab-pane label="阻塞任务" name="blocks">
        <div v-if="blockTasks.length > 0" class="blocks-section">
          <div
            v-for="task in blockTasks"
            :key="task.id"
            class="block-card"
            :class="{ high: task.priority === 'high' }"
          >
            <div class="block-header">
              <el-tag :type="task.priority === 'high' ? 'danger' : 'warning'" size="small">
                {{ task.priority === 'high' ? '高优先级' : '中优先级' }}
              </el-tag>
              <span class="block-type">{{ task.required_content_type }}</span>
            </div>
            <div class="block-reason">{{ task.reason }}</div>
            <div class="block-action">{{ task.suggested_action }}</div>
            <div class="block-footer">
              <span>缺口时长: {{ task.gap_duration.toFixed(1) }}秒</span>
              <el-button type="success" size="small" @click="handleResolveBlock(task.id)">
                已解决
              </el-button>
            </div>
          </div>
        </div>
        <div v-else class="empty-state">
          <el-empty description="暂无阻塞任务" />
        </div>
      </el-tab-pane>
    </el-tabs>

    <!-- 创建任务弹窗 -->
    <el-dialog v-model="showCreateModal" title="创建生产任务" width="500px">
      <el-form :model="createForm" label-width="100px">
        <el-form-item label="任务标题">
          <el-input v-model="createForm.title" placeholder="输入任务标题" />
        </el-form-item>
        <el-form-item label="导演方案ID">
          <el-input-number v-model="createForm.source_plan_id" :min="0" />
        </el-form-item>
        <el-form-item label="目标平台">
          <el-select v-model="createForm.target_platforms" multiple placeholder="选择平台">
            <el-option label="抖音" value="douyin" />
            <el-option label="视频号" value="wechat_video" />
            <el-option label="小红书" value="xiaohongshu" />
            <el-option label="快手" value="kuaishou" />
          </el-select>
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="showCreateModal = false">取消</el-button>
        <el-button type="primary" @click="handleCreateJob">创建</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, onMounted } from 'vue'
import {
  getProductionJobs,
  getProductionStats,
  getJobTimeline,
  getJobVariants,
  getBlockTasks,
  createProductionJob,
  generateTimeline,
  generateVariants,
  resolveBlockTask,
  STATUS_LABELS,
  PLATFORM_LABELS,
  STRATEGY_LABELS,
  ROLE_LABELS,
  type ProductionJob,
  type VideoTimeline,
  type VideoVariant,
  type ProductionBlockTask,
} from '@/api/videoProduction'

const activeTab = ref('jobs')
const filterStatus = ref('')

const stats = ref({
  total_jobs: 0,
  completed_jobs: 0,
  blocked_jobs: 0,
  total_variants: 0,
  completion_rate: 0,
})

const jobs = ref<ProductionJob[]>([])
const selectedJob = ref<ProductionJob | null>(null)
const timelineItems = ref<VideoTimeline[]>([])
const variants = ref<VideoVariant[]>([])
const blockTasks = ref<ProductionBlockTask[]>([])

const showCreateModal = ref(false)
const createForm = ref({
  title: '',
  source_plan_id: undefined as number | undefined,
  target_platforms: [] as string[],
})

const totalDuration = computed(() => {
  if (!timelineItems.value.length) return 100
  return Math.max(...timelineItems.value.map(t => t.end_time))
})

const getStatusLabel = (status: string) => STATUS_LABELS[status]?.label || status
const getStatusType = (status: string) => STATUS_LABELS[status]?.type || 'info'
const getPlatformLabel = (platform: string) => PLATFORM_LABELS[platform] || platform
const getStrategyLabel = (strategy: string | null) => strategy ? STRATEGY_LABELS[strategy] || strategy : '默认'
const getRoleLabel = (role: string | null) => role ? ROLE_LABELS[role] || role : '普通'

const getStrategyType = (strategy: string | null) => {
  if (!strategy) return 'info'
  const types: Record<string, string> = {
    traffic: 'primary',
    conversion: 'success',
    content: 'warning',
    community: 'info',
    balanced: '',
  }
  return types[strategy] || ''
}

const getPlatformIcon = (platform: string) => {
  const icons: Record<string, string> = {
    douyin: '🎵',
    wechat_video: '💬',
    xiaohongshu: '📕',
    kuaishou: '🎬',
    bilibili: '📺',
  }
  return icons[platform] || '📱'
}

const selectJob = (job: ProductionJob) => {
  selectedJob.value = job
  loadTimeline(job.id)
  loadVariants(job.id)
}

const loadStats = async () => {
  try {
    const res = await getProductionStats()
    if (res.data.success) {
      stats.value = res.data.data
    }
  } catch (e) {
    console.error('Load stats failed:', e)
  }
}

const loadJobs = async () => {
  try {
    const res = await getProductionJobs(undefined, 1, 20)
    if (res.data.success) {
      jobs.value = res.data.data.jobs
    }
  } catch (e) {
    console.error('Load jobs failed:', e)
  }
}

const loadTimeline = async (jobId: number) => {
  try {
    const res = await getJobTimeline(jobId)
    if (res.data.success) {
      timelineItems.value = res.data.data
    }
  } catch (e) {
    console.error('Load timeline failed:', e)
  }
}

const loadVariants = async (jobId: number) => {
  try {
    const res = await getJobVariants(jobId)
    if (res.data.success) {
      variants.value = res.data.data
    }
  } catch (e) {
    console.error('Load variants failed:', e)
  }
}

const loadBlockTasks = async () => {
  try {
    const res = await getBlockTasks('pending')
    if (res.data.success) {
      blockTasks.value = res.data.data
    }
  } catch (e) {
    console.error('Load block tasks failed:', e)
  }
}

const handleCreateJob = async () => {
  try {
    const res = await createProductionJob({
      title: createForm.value.title,
      source_plan_id: createForm.value.source_plan_id,
      target_platforms: createForm.value.target_platforms.length ? createForm.value.target_platforms : undefined,
    })
    if (res.data.success) {
      showCreateModal.value = false
      createForm.value = { title: '', source_plan_id: undefined, target_platforms: [] }
      await loadJobs()
      await loadStats()
    }
  } catch (e) {
    console.error('Create job failed:', e)
  }
}

const handleGenerateTimeline = async () => {
  if (!selectedJob.value) return
  try {
    const res = await generateTimeline(selectedJob.value.id)
    if (res.data.success) {
      await loadTimeline(selectedJob.value.id)
      await loadJobs()
    }
  } catch (e) {
    console.error('Generate timeline failed:', e)
  }
}

const handleGenerateVariants = async () => {
  if (!selectedJob.value) return
  try {
    const res = await generateVariants(selectedJob.value.id, selectedJob.value.target_platforms)
    if (res.data.success) {
      await loadVariants(selectedJob.value.id)
      await loadJobs()
    }
  } catch (e) {
    console.error('Generate variants failed:', e)
  }
}

const handleResolveBlock = async (taskId: number) => {
  try {
    const res = await resolveBlockTask(taskId)
    if (res.data.success) {
      await loadBlockTasks()
    }
  } catch (e) {
    console.error('Resolve block failed:', e)
  }
}

onMounted(() => {
  loadStats()
  loadJobs()
  loadBlockTasks()
})
</script>

<style scoped>
.production-page {
  padding: 16px;
}

.page-header {
  margin-bottom: 20px;
}

.page-header h1 {
  margin: 0 0 4px;
  font-size: 24px;
}

.subtitle {
  margin: 0;
  color: #888;
  font-size: 14px;
}

/* 统计概览 */
.stats-section {
  background: white;
  border-radius: 12px;
  padding: 20px;
  margin-bottom: 16px;
}

.stats-grid {
  display: grid;
  grid-template-columns: repeat(4, 1fr);
  gap: 12px;
}

.stat-card {
  background: #f8f9fa;
  border-radius: 8px;
  padding: 16px;
  text-align: center;
}

.stat-card.full-width {
  grid-column: span 4;
  display: flex;
  align-items: center;
  gap: 16px;
}

.stat-icon {
  font-size: 24px;
  margin-bottom: 4px;
}

.stat-number {
  font-size: 20px;
  font-weight: bold;
  color: #333;
}

.stat-number.large {
  font-size: 28px;
  color: #667eea;
}

.stat-label {
  font-size: 12px;
  color: #888;
}

/* 标签页 */
.production-tabs {
  background: white;
  border-radius: 12px;
  padding: 8px 16px;
}

/* 任务列表 */
.job-section {
  padding: 16px 0;
}

.job-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 16px;
}

.job-list {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(300px, 1fr));
  gap: 12px;
}

.job-card {
  background: #f8f9fa;
  border-radius: 12px;
  padding: 16px;
  cursor: pointer;
  transition: all 0.3s;
}

.job-card:hover {
  transform: translateY(-2px);
  box-shadow: 0 4px 12px rgba(0, 0, 0, 0.1);
}

.job-card.blocked {
  border-left: 4px solid #f56c6c;
}

.job-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 8px;
}

.job-header h4 {
  margin: 0;
  font-size: 14px;
}

.job-progress {
  display: flex;
  align-items: center;
  gap: 8px;
  margin-bottom: 8px;
}

.progress-text {
  font-size: 12px;
  color: #888;
  min-width: 40px;
  text-align: right;
}

.job-info {
  display: flex;
  gap: 12px;
  font-size: 12px;
  color: #666;
}

.job-blocked {
  margin-top: 8px;
}

/* 时间线视图 */
.timeline-section {
  padding: 16px 0;
}

.timeline-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 20px;
}

.timeline-header h3 {
  margin: 0;
}

.timeline-editor {
  background: #f8f9fa;
  border-radius: 12px;
  padding: 20px;
}

.timeline-track {
  position: relative;
  margin-bottom: 20px;
}

.track-label {
  font-size: 12px;
  color: #888;
  margin-bottom: 8px;
}

.track-content {
  position: relative;
  height: 80px;
  background: white;
  border-radius: 8px;
  border: 1px solid #e0e0e0;
  overflow: hidden;
}

.timeline-item {
  position: absolute;
  top: 8px;
  bottom: 8px;
  background: #667eea;
  border-radius: 6px;
  padding: 8px;
  box-sizing: border-box;
  cursor: pointer;
  transition: all 0.3s;
}

.timeline-item.matched {
  background: #67c23a;
}

.timeline-item.missing {
  background: #f56c6c;
  opacity: 0.7;
}

.timeline-item:hover {
  transform: translateY(-2px);
  box-shadow: 0 4px 8px rgba(0, 0, 0, 0.2);
}

.item-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 4px;
}

.item-role {
  font-size: 12px;
  font-weight: 600;
  color: white;
}

.item-time {
  font-size: 10px;
  color: rgba(255, 255, 255, 0.8);
}

.item-status {
  margin-bottom: 2px;
}

.item-gap {
  font-size: 10px;
  color: rgba(255, 255, 255, 0.9);
}

.track-markers {
  position: relative;
  height: 20px;
  display: flex;
  justify-content: space-between;
  padding: 0 8px;
  box-sizing: border-box;
}

.track-markers span {
  font-size: 10px;
  color: #999;
}

/* 版本管理 */
.variants-section {
  padding: 16px 0;
}

.variants-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 20px;
}

.variants-header h3 {
  margin: 0;
}

.variants-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(250px, 1fr));
  gap: 12px;
}

.variant-card {
  background: #f8f9fa;
  border-radius: 12px;
  padding: 16px;
}

.variant-header {
  display: flex;
  align-items: center;
  gap: 8px;
  margin-bottom: 12px;
}

.platform-icon {
  font-size: 20px;
}

.platform-name {
  font-weight: 600;
  color: #333;
}

.variant-info {
  margin-bottom: 12px;
}

.info-item {
  display: flex;
  justify-content: space-between;
  font-size: 13px;
  margin-bottom: 4px;
}

.info-item .value {
  font-weight: 600;
  color: #667eea;
}

/* 阻塞任务 */
.blocks-section {
  padding: 16px 0;
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(300px, 1fr));
  gap: 12px;
}

.block-card {
  background: #fef0f0;
  border-radius: 12px;
  padding: 16px;
  border-left: 4px solid #e6a23c;
}

.block-card.high {
  border-left-color: #f56c6c;
  background: #fef5f5;
}

.block-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 8px;
}

.block-type {
  font-size: 14px;
  font-weight: 600;
  color: #333;
}

.block-reason {
  font-size: 13px;
  color: #666;
  margin-bottom: 8px;
}

.block-action {
  font-size: 12px;
  color: #888;
  margin-bottom: 12px;
}

.block-footer {
  display: flex;
  justify-content: space-between;
  align-items: center;
  font-size: 12px;
  color: #999;
}

.empty-state {
  padding: 40px 0;
}

@media (max-width: 768px) {
  .stats-grid {
    grid-template-columns: repeat(2, 1fr);
  }

  .stat-card.full-width {
    grid-column: span 2;
  }

  .job-list {
    grid-template-columns: 1fr;
  }

  .variants-grid {
    grid-template-columns: 1fr;
  }

  .blocks-section {
    grid-template-columns: 1fr;
  }
}
</style>
