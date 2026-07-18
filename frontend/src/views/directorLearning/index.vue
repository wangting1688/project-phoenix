<template>
  <div class="learning-page">
    <!-- 页面标题 -->
    <div class="page-header">
      <h1>🧠 AI导演学习中心</h1>
      <p class="subtitle">Phoenix 的 AI 导演经验大脑 - 从数据中学习，越用越聪明</p>
    </div>

    <!-- 学习进度概览 -->
    <div class="overview-section">
      <div class="progress-card">
        <div class="progress-header">
          <span class="progress-label">AI导演学习进度</span>
          <span class="progress-value">{{ stats.learning_progress }}%</span>
        </div>
        <el-progress
          :percentage="stats.learning_progress"
          :stroke-width="12"
          :color="'#667eea'"
        />
        <div class="progress-tip">
          达到50条经验，AI导演进入成熟阶段
        </div>
      </div>

      <div class="stats-grid">
        <div class="stat-item">
          <span class="stat-icon">📹</span>
          <span class="stat-number">{{ stats.total_videos }}</span>
          <span class="stat-label">视频内容</span>
        </div>
        <div class="stat-item">
          <span class="stat-icon">📱</span>
          <span class="stat-number">{{ stats.total_publish_records }}</span>
          <span class="stat-label">发布记录</span>
        </div>
        <div class="stat-item">
          <span class="stat-icon">💡</span>
          <span class="stat-number">{{ stats.total_memories }}</span>
          <span class="stat-label">经验积累</span>
        </div>
        <div class="stat-item">
          <span class="stat-icon">✅</span>
          <span class="stat-number">{{ stats.verified_memories }}</span>
          <span class="stat-label">已验证经验</span>
        </div>
      </div>
    </div>

    <!-- 标签页 -->
    <el-tabs v-model="activeTab" class="learning-tabs">
      <el-tab-pane label="主播策略画像" name="creator">
        <div v-if="creatorProfile" class="profile-section">
          <div class="profile-grid">
            <div class="profile-card">
              <h4>🎯 最佳内容打法</h4>
              <el-tag type="primary" size="large">{{ creatorProfile.best_content_type || '待积累' }}</el-tag>
              <div class="profile-tags" v-if="creatorProfile.best_content_types?.length">
                <el-tag v-for="t in creatorProfile.best_content_types" :key="t" size="small">
                  {{ t }}
                </el-tag>
              </div>
            </div>
            <div class="profile-card">
              <h4>🎬 最佳开场方式</h4>
              <el-tag type="success" size="large">{{ creatorProfile.best_hook_style || '待积累' }}</el-tag>
              <p class="profile-desc">Hook 风格决定前3秒留存率</p>
            </div>
            <div class="profile-card">
              <h4>📹 最佳镜头形式</h4>
              <el-tag type="warning" size="large">{{ creatorProfile.best_camera_style || '待积累' }}</el-tag>
            </div>
            <div class="profile-card">
              <h4>⏱️ 最佳时长</h4>
              <el-tag type="info" size="large">{{ creatorProfile.best_duration_range || '待积累' }}</el-tag>
            </div>
            <div class="profile-card">
              <h4>💰 成交方式</h4>
              <el-tag type="danger" size="large">{{ creatorProfile.best_conversion_style || '待积累' }}</el-tag>
            </div>
            <div class="profile-card">
              <h4>📊 数据样本</h4>
              <span class="profile-number">{{ creatorProfile.analyzed_videos || 0 }} 个视频</span>
              <p class="profile-desc">越多数据，画像越准</p>
            </div>
          </div>
        </div>
        <div v-else class="empty-state">
          <el-empty description="暂无策略画像，发布视频后自动生成">
            <el-button type="primary" @click="loadCreatorProfile">刷新</el-button>
          </el-empty>
        </div>
      </el-tab-pane>

      <el-tab-pane label="平台策略画像" name="platform">
        <div v-if="platformProfiles.length > 0" class="platform-section">
          <div
            v-for="profile in platformProfiles"
            :key="profile.platform"
            class="platform-card"
          >
            <div class="platform-header">
              <h4>{{ PLATFORM_LABELS[profile.platform] || profile.platform }}</h4>
              <el-tag :type="getPlatformRoleType(profile.platform_role)" size="small">
                {{ PLATFORM_ROLE_LABELS[profile.platform_role] || profile.platform_role }}
              </el-tag>
            </div>
            <div class="platform-stats">
              <div class="stat-row">
                <span>平均播放</span>
                <span class="strong">{{ profile.avg_views?.toLocaleString() || 0 }}</span>
              </div>
              <div class="stat-row">
                <span>平均完播</span>
                <span class="strong">{{ (profile.avg_completion_rate * 100).toFixed(1) }}%</span>
              </div>
              <div class="stat-row">
                <span>平均转化</span>
                <span class="strong">{{ (profile.avg_conversion_rate * 100).toFixed(2) }}%</span>
              </div>
              <div class="stat-row">
                <span>发布数</span>
                <span class="strong">{{ profile.total_published }}</span>
              </div>
            </div>
            <div class="platform-weights" v-if="profile.weight_config">
              <div class="weights-title">平台评价维度</div>
              <div class="weights-grid">
                <div class="weight-item" v-for="(weight, key) in profile.weight_config" :key="key">
                  <span>{{ getWeightLabel(key) }}</span>
                  <span class="weight-value">{{ (weight * 100).toFixed(0) }}%</span>
                </div>
              </div>
            </div>
          </div>
        </div>
        <div v-else class="empty-state">
          <el-empty description="暂无平台数据，发布视频后自动生成" />
        </div>
      </el-tab-pane>

      <el-tab-pane label="导演经验库" name="memories">
        <div v-if="memories.length > 0" class="memories-section">
          <div class="memories-filters">
            <el-radio-group v-model="filterType" size="small">
              <el-radio-button value="">全部</el-radio-button>
              <el-radio-button value="template_success">模板</el-radio-button>
              <el-radio-button value="platform_success">平台</el-radio-button>
              <el-radio-button value="hook_success">开场</el-radio-button>
            </el-radio-group>
          </div>
          <div class="memories-list">
            <div
              v-for="mem in filteredMemories"
              :key="mem.id"
              class="memory-card"
              :class="{ verified: mem.is_verified }"
            >
              <div class="memory-header">
                <el-tag :type="getMemoryType(mem.memory_type).type" size="small">
                  {{ MEMORY_TYPE_LABELS[mem.memory_type] || mem.memory_type }}
                </el-tag>
                <div class="confidence">
                  <span>置信度</span>
                  <el-progress
                    :percentage="Math.round(mem.confidence_score * 100)"
                    :stroke-width="6"
                    :color="mem.confidence_score >= 0.8 ? '#67c23a' : '#e6a23c'"
                    style="width: 80px"
                  />
                </div>
              </div>
              <div class="memory-condition">
                <span class="label">条件</span>
                <span class="value">{{ formatCondition(mem.condition) }}</span>
              </div>
              <div class="memory-recommendation">
                <span class="label">推荐</span>
                <span class="value highlight">{{ formatRecommendation(mem.recommendation) }}</span>
              </div>
              <div class="memory-footer">
                <span class="verified-badge" v-if="mem.is_verified">✓ 已验证</span>
                <span class="data-points">{{ mem.source_data_points }}个数据点</span>
              </div>
            </div>
          </div>
        </div>
        <div v-else class="empty-state">
          <el-empty description="暂无经验数据，视频发布并复盘后自动积累">
            <el-button type="primary" @click="loadMemories">刷新</el-button>
          </el-empty>
        </div>
      </el-tab-pane>

      <el-tab-pane label="商业评分说明" name="weights">
        <div class="weights-section">
          <div class="weights-intro">
            <h3>Phoenix 商业评分体系</h3>
            <p class="intro-text">{{ weightsData?.philosophy }}</p>
          </div>
          <div v-if="weightsData" class="weights-detail">
            <div class="weight-card" v-for="(w, key) in weightsData.weights" :key="key">
              <div class="weight-rank">{{ w.weight }}</div>
              <div class="weight-name">{{ w.name }}</div>
            </div>
          </div>
          <div class="platform-philosophy">
            <h4>平台定位</h4>
            <div class="platform-philo-grid">
              <div v-for="(desc, platform) in weightsData?.core_platforms" :key="platform" class="philo-item">
                <span class="platform-name">{{ PLATFORM_LABELS[platform] || platform }}</span>
                <span class="platform-desc">{{ desc }}</span>
              </div>
            </div>
          </div>
        </div>
      </el-tab-pane>
    </el-tabs>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, onMounted } from 'vue'
import {
  getLearningStats,
  getLearningMemories,
  getCreatorStrategy,
  getPlatformStrategies,
  getPhoenixCommercialWeights,
  MEMORY_TYPE_LABELS,
  PLATFORM_LABELS,
  PLATFORM_ROLE_LABELS,
  type DirectorLearningStats,
  type LearningMemory,
  type CreatorStrategyProfile,
  type PlatformStrategyProfile,
} from '@/api/directorLearning'

const activeTab = ref('creator')
const filterType = ref('')

const stats = ref<DirectorLearningStats>({
  total_videos: 0,
  total_publish_records: 0,
  total_memories: 0,
  verified_memories: 0,
  memory_type_stats: {},
  learning_progress: 0,
})

const memories = ref<LearningMemory[]>([])
const creatorProfile = ref<CreatorStrategyProfile | null>(null)
const platformProfiles = ref<PlatformStrategyProfile[]>([])
const weightsData = ref<{
  description: string
  weights: Record<string, { name: string; weight: string }>
  philosophy: string
  core_platforms: Record<string, string>
} | null>(null)

const filteredMemories = computed(() => {
  if (!filterType.value) return memories.value
  return memories.value.filter(m => m.memory_type === filterType.value)
})

const getMemoryType = (type: string) => {
  const types: Record<string, { type: string; color: string }> = {
    template_success: { type: 'primary', color: 'blue' },
    platform_success: { type: 'success', color: 'green' },
    creator_success: { type: 'warning', color: 'orange' },
    hook_success: { type: 'danger', color: 'red' },
    product_success: { type: 'info', color: 'gray' },
  }
  return types[type] || { type: 'info', color: 'gray' }
}

const getPlatformRoleType = (role: string) => {
  const types: Record<string, string> = {
    traffic: 'primary',
    conversion: 'success',
    content: 'warning',
    community: 'info',
    balanced: '',
  }
  return types[role] || ''
}

const getWeightLabel = (key: string) => {
  const labels: Record<string, string> = {
    traffic: '流量',
    engagement: '互动',
    conversion: '转化',
    customer_value: '客户价值',
  }
  return labels[key] || key
}

const formatCondition = (condition: Record<string, any>) => {
  if (!condition) return '-'
  const parts = Object.entries(condition)
    .filter(([k, v]) => v !== null && v !== undefined && v !== '')
    .map(([k, v]) => `${k}: ${v}`)
  return parts.length > 0 ? parts.join(' / ') : '-'
}

const formatRecommendation = (rec: Record<string, any>) => {
  if (!rec) return '-'
  const keys = ['template_type', 'hook_style', 'best_duration', 'score', 'strength']
  for (const k of keys) {
    if (rec[k]) return `${rec[k]}`
  }
  return JSON.stringify(rec).substring(0, 50)
}

const loadStats = async () => {
  try {
    const res = await getLearningStats()
    if (res.data.success) {
      stats.value = res.data.data
    }
  } catch (e) {
    console.error('Load stats failed:', e)
  }
}

const loadMemories = async () => {
  try {
    const res = await getLearningMemories(undefined, undefined, 50)
    if (res.data.success) {
      memories.value = res.data.data
    }
  } catch (e) {
    console.error('Load memories failed:', e)
  }
}

const loadCreatorProfile = async () => {
  try {
    const res = await getCreatorStrategy()
    if (res.data.success) {
      creatorProfile.value = res.data.data
    }
  } catch (e) {
    console.error('Load creator strategy failed:', e)
  }
}

const loadPlatformProfiles = async () => {
  try {
    const res = await getPlatformStrategies()
    if (res.data.success) {
      platformProfiles.value = res.data.data
    }
  } catch (e) {
    console.error('Load platform strategies failed:', e)
  }
}

const loadWeights = async () => {
  try {
    const res = await getPhoenixCommercialWeights()
    if (res.data.success) {
      weightsData.value = res.data.data
    }
  } catch (e) {
    console.error('Load weights failed:', e)
  }
}

onMounted(() => {
  loadStats()
  loadMemories()
  loadCreatorProfile()
  loadPlatformProfiles()
  loadWeights()
})
</script>

<style scoped>
.learning-page {
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

/* 概览区 */
.overview-section {
  background: white;
  border-radius: 12px;
  padding: 20px;
  margin-bottom: 16px;
}

.progress-card {
  margin-bottom: 16px;
}

.progress-header {
  display: flex;
  justify-content: space-between;
  margin-bottom: 8px;
}

.progress-label {
  font-size: 14px;
  color: #333;
}

.progress-value {
  font-size: 16px;
  font-weight: 600;
  color: #667eea;
}

.progress-tip {
  margin-top: 8px;
  font-size: 12px;
  color: #999;
  text-align: center;
}

.stats-grid {
  display: grid;
  grid-template-columns: repeat(4, 1fr);
  gap: 12px;
}

.stat-item {
  display: flex;
  flex-direction: column;
  align-items: center;
  padding: 16px;
  background: #f8f9fa;
  border-radius: 8px;
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

.stat-label {
  font-size: 12px;
  color: #888;
}

/* 标签页 */
.learning-tabs {
  background: white;
  border-radius: 12px;
  padding: 8px 16px;
}

/* 主播画像 */
.profile-section {
  padding: 16px 0;
}

.profile-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(200px, 1fr));
  gap: 16px;
}

.profile-card {
  background: #f8f9fa;
  border-radius: 12px;
  padding: 20px;
  text-align: center;
}

.profile-card h4 {
  margin: 0 0 12px;
  font-size: 14px;
  color: #666;
}

.profile-number {
  font-size: 24px;
  font-weight: bold;
  color: #333;
}

.profile-desc {
  margin: 8px 0 0;
  font-size: 12px;
  color: #999;
}

.profile-tags {
  margin-top: 12px;
  display: flex;
  gap: 6px;
  flex-wrap: wrap;
  justify-content: center;
}

/* 平台画像 */
.platform-section {
  padding: 16px 0;
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(280px, 1fr));
  gap: 16px;
}

.platform-card {
  background: #f8f9fa;
  border-radius: 12px;
  padding: 20px;
}

.platform-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 16px;
}

.platform-header h4 {
  margin: 0;
  font-size: 16px;
}

.platform-stats {
  display: flex;
  flex-direction: column;
  gap: 8px;
  margin-bottom: 16px;
}

.stat-row {
  display: flex;
  justify-content: space-between;
  font-size: 13px;
}

.stat-row .strong {
  font-weight: 600;
  color: #333;
}

.platform-weights {
  border-top: 1px solid #e0e0e0;
  padding-top: 12px;
}

.weights-title {
  font-size: 12px;
  color: #888;
  margin-bottom: 8px;
}

.weights-grid {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 6px;
  font-size: 12px;
}

.weight-item {
  display: flex;
  justify-content: space-between;
}

.weight-value {
  font-weight: 500;
  color: #667eea;
}

/* 经验库 */
.memories-section {
  padding: 16px 0;
}

.memories-filters {
  margin-bottom: 16px;
}

.memories-list {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(300px, 1fr));
  gap: 12px;
}

.memory-card {
  background: #f8f9fa;
  border-radius: 12px;
  padding: 16px;
  border-left: 4px solid #e0e0e0;
}

.memory-card.verified {
  border-left-color: #67c23a;
  background: #f0f9eb;
}

.memory-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 12px;
}

.confidence {
  display: flex;
  align-items: center;
  gap: 8px;
  font-size: 12px;
  color: #888;
}

.memory-condition,
.memory-recommendation {
  display: flex;
  gap: 8px;
  margin-bottom: 8px;
  font-size: 13px;
}

.memory-condition .label,
.memory-recommendation .label {
  color: #999;
  min-width: 40px;
}

.memory-condition .value {
  color: #666;
  flex: 1;
}

.memory-recommendation .value.highlight {
  color: #667eea;
  font-weight: 500;
  flex: 1;
}

.memory-footer {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-top: 8px;
  padding-top: 8px;
  border-top: 1px solid #e0e0e0;
  font-size: 12px;
}

.verified-badge {
  color: #67c23a;
  font-weight: 500;
}

.data-points {
  color: #999;
}

/* 商业评分说明 */
.weights-section {
  padding: 16px 0;
}

.weights-intro {
  text-align: center;
  margin-bottom: 24px;
}

.weights-intro h3 {
  margin: 0 0 8px;
  font-size: 20px;
}

.intro-text {
  color: #666;
  font-size: 14px;
  margin: 0;
}

.weights-detail {
  display: grid;
  grid-template-columns: repeat(3, 1fr);
  gap: 16px;
  margin-bottom: 32px;
}

.weight-card {
  background: #f8f9fa;
  border-radius: 12px;
  padding: 24px;
  text-align: center;
}

.weight-rank {
  font-size: 28px;
  font-weight: bold;
  color: #667eea;
  margin-bottom: 8px;
}

.weight-name {
  font-size: 14px;
  color: #333;
}

.platform-philosophy {
  background: #f8f9fa;
  border-radius: 12px;
  padding: 20px;
}

.platform-philosophy h4 {
  margin: 0 0 16px;
  font-size: 16px;
}

.platform-philo-grid {
  display: grid;
  grid-template-columns: repeat(3, 1fr);
  gap: 16px;
}

.philo-item {
  display: flex;
  flex-direction: column;
  gap: 6px;
  text-align: center;
  padding: 16px;
  background: white;
  border-radius: 8px;
}

.platform-name {
  font-weight: 600;
  color: #333;
}

.platform-desc {
  font-size: 12px;
  color: #666;
}

.empty-state {
  padding: 40px 0;
}

@media (max-width: 768px) {
  .stats-grid {
    grid-template-columns: repeat(2, 1fr);
  }

  .weights-detail {
    grid-template-columns: 1fr;
  }

  .platform-philo-grid {
    grid-template-columns: 1fr;
  }
}
</style>
