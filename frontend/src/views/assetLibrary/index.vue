<template>
  <div class="asset-library-page">
    <!-- 页面标题 -->
    <div class="page-header">
      <h1>🧠 AI智能素材库</h1>
      <el-button type="primary" @click="batchAnalyze">
        🔍 AI分析全部素材
      </el-button>
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
        <div class="stat-icon">🧠</div>
        <div class="stat-info">
          <span class="stat-value">{{ stats.analyzed_count }}</span>
          <span class="stat-label">AI已分析</span>
        </div>
      </div>
      <div class="stat-card">
        <div class="stat-icon">⏳</div>
        <div class="stat-info">
          <span class="stat-value">{{ stats.pending_count }}</span>
          <span class="stat-label">待分析</span>
        </div>
      </div>
      <div class="stat-card">
        <div class="stat-icon">⭐</div>
        <div class="stat-info">
          <span class="stat-value">{{ stats.average_score }}</span>
          <span class="stat-label">平均评分</span>
        </div>
      </div>
    </div>

    <!-- 搜索区域 -->
    <div class="search-section">
      <div class="search-box">
        <el-input
          v-model="searchQuery"
          placeholder="搜索素材：情绪、场景、标签..."
          size="large"
          clearable
          @keyup.enter="handleSearch"
        >
          <template #append>
            <el-button @click="handleSearch">
              🔍 搜索
            </el-button>
          </template>
        </el-input>
      </div>

      <!-- 筛选标签 -->
      <div class="filter-tags">
        <el-tag
          v-for="filter in activeFilters"
          :key="filter.key"
          closable
          @close="removeFilter(filter.key)"
        >
          {{ filter.label }}: {{ filter.value }}
        </el-tag>
      </div>
    </div>

    <!-- 快速筛选 -->
    <div class="quick-filters">
      <div class="filter-group">
        <span class="filter-label">场景：</span>
        <el-radio-group v-model="filterScene" size="small" @change="handleSearch">
          <el-radio-button label="">全部</el-radio-button>
          <el-radio-button label="固定背景">固定背景</el-radio-button>
          <el-radio-button label="客厅">客厅</el-radio-button>
          <el-radio-button label="厨房">厨房</el-radio-button>
          <el-radio-button label="户外">户外</el-radio-button>
        </el-radio-group>
      </div>

      <div class="filter-group">
        <span class="filter-label">情绪：</span>
        <el-radio-group v-model="filterEmotion" size="small" @change="handleSearch">
          <el-radio-button label="">全部</el-radio-button>
          <el-radio-button label="亲切">亲切</el-radio-button>
          <el-radio-button label="认真">认真</el-radio-button>
          <el-radio-button label="开心">开心</el-radio-button>
          <el-radio-button label="自然">自然</el-radio-button>
        </el-radio-group>
      </div>

      <div class="filter-group">
        <span class="filter-label">质量：</span>
        <el-radio-group v-model="filterMinScore" size="small" @change="handleSearch">
          <el-radio-button :label="0">全部</el-radio-button>
          <el-radio-button :label="80">优质(80+)</el-radio-button>
          <el-radio-button :label="90">精品(90+)</el-radio-button>
        </el-radio-group>
      </div>
    </div>

    <!-- 素材列表 -->
    <div v-if="searchResults.length > 0" class="assets-grid">
      <div
        v-for="result in searchResults"
        :key="result.asset.id"
        class="asset-card"
        @click="showAssetDetail(result)"
      >
        <!-- 缩略图 -->
        <div class="asset-thumbnail">
          <div class="thumbnail-placeholder">
            <el-icon :size="48"><IVideoPlay /></el-icon>
          </div>
          <div class="asset-duration">{{ formatDuration(result.asset.duration) }}</div>
          <div class="asset-score-badge" :class="getScoreClass(result.overall_score)">
            {{ result.overall_score }}分
          </div>
        </div>

        <!-- 信息 -->
        <div class="asset-info">
          <h4 class="asset-name">{{ result.asset.name }}</h4>

          <!-- AI标签 -->
          <div class="asset-tags">
            <el-tag size="small" type="success">{{ result.intelligence.emotion_primary }}</el-tag>
            <el-tag size="small">{{ result.intelligence.scene_type }}</el-tag>
            <el-tag size="small" type="info">{{ result.intelligence.style }}</el-tag>
          </div>

          <!-- 主题 -->
          <div class="asset-topics">
            <span v-for="topic in result.intelligence.topics" :key="topic" class="topic-tag">
              #{{ topic }}
            </span>
          </div>

          <!-- 评分条 -->
          <div class="score-bar">
            <div class="score-label">质量</div>
            <el-progress
              :percentage="result.intelligence.quality_score"
              :stroke-width="6"
              :color="getProgressColor(result.intelligence.quality_score)"
              :show-text="false"
            />
          </div>

          <!-- 片段数 -->
          <div class="asset-meta">
            <span>🎬 {{ result.intelligence.segments?.length || 0 }} 个片段</span>
            <span>👁️ {{ result.intelligence.usage_count }} 次使用</span>
          </div>
        </div>
      </div>
    </div>

    <div v-else class="empty-state">
      <el-empty description="暂无素材，请先上传并分析" />
    </div>

    <!-- 素材详情弹窗 -->
    <el-dialog
      v-model="detailVisible"
      title="素材AI分析报告"
      width="90%"
      class="asset-detail-dialog"
    >
      <div v-if="selectedAsset" class="asset-detail">
        <!-- 头部信息 -->
        <div class="detail-header">
          <div class="detail-score">
            <div class="score-circle" :class="getScoreClass(selectedAsset.overall_score)">
              <span class="score-number">{{ selectedAsset.overall_score }}</span>
              <span class="score-label">综合评分</span>
            </div>
          </div>
          <div class="detail-summary">
            <h3>{{ selectedAsset.asset.name }}</h3>
            <p class="summary-text">{{ selectedAsset.intelligence.analysis_result?.summary }}</p>
            <div class="detail-tags">
              <el-tag v-for="tag in selectedAsset.intelligence.tags" :key="tag" size="small">
                {{ tag }}
              </el-tag>
            </div>
          </div>
        </div>

        <!-- 五维评分 -->
        <div class="dimension-scores">
          <h4>📊 五维评分</h4>
          <div class="dimension-grid">
            <div class="dimension-item">
              <div class="dimension-label">画面质量</div>
              <el-progress :percentage="scoreBreakdown?.dimensions.visual_quality.score || 0" :stroke-width="8" />
              <span class="dimension-value">{{ scoreBreakdown?.dimensions.visual_quality.score || 0 }}</span>
            </div>
            <div class="dimension-item">
              <div class="dimension-label">人物表现</div>
              <el-progress :percentage="scoreBreakdown?.dimensions.person_performance.score || 0" :stroke-width="8" />
              <span class="dimension-value">{{ scoreBreakdown?.dimensions.person_performance.score || 0 }}</span>
            </div>
            <div class="dimension-item">
              <div class="dimension-label">情绪感染力</div>
              <el-progress :percentage="scoreBreakdown?.dimensions.emotion_power.score || 0" :stroke-width="8" />
              <span class="dimension-value">{{ scoreBreakdown?.dimensions.emotion_power.score || 0 }}</span>
            </div>
            <div class="dimension-item">
              <div class="dimension-label">内容适配度</div>
              <el-progress :percentage="scoreBreakdown?.dimensions.content_match.score || 0" :stroke-width="8" />
              <span class="dimension-value">{{ scoreBreakdown?.dimensions.content_match.score || 0 }}</span>
            </div>
            <div class="dimension-item">
              <div class="dimension-label">原创价值</div>
              <el-progress :percentage="scoreBreakdown?.dimensions.originality.score || 0" :stroke-width="8" />
              <span class="dimension-value">{{ scoreBreakdown?.dimensions.originality.score || 0 }}</span>
            </div>
          </div>
        </div>

        <!-- 片段列表 -->
        <div class="segments-section">
          <div class="section-header">
            <h4>🎬 素材片段（商业角色标签）</h4>
            <el-button
              type="primary"
              size="small"
              :loading="creatingSegments"
              @click="handleCreateSegments"
              v-if="assetSegments.length === 0"
            >
              <el-icon :size="16"><IScissors /></el-icon>
              AI生成片段
            </el-button>
          </div>
          
          <div v-if="assetSegments.length > 0" class="segments-list">
            <div
              v-for="segment in assetSegments"
              :key="segment.id"
              class="segment-item"
            >
              <div class="segment-header">
                <span class="segment-index">片段 {{ segment.segment_number }}</span>
                <span
                  class="segment-role"
                  :style="{ background: ROLE_COLORS[segment.segment_role] }"
                >
                  {{ ROLE_LABELS[segment.segment_role] }}
                </span>
                <span class="segment-time">{{ segment.start_time.toFixed(1) }}s - {{ segment.end_time.toFixed(1) }}s</span>
                <span class="segment-score" :class="getScoreClass(segment.quality_score)">
                  {{ segment.quality_score }}分
                </span>
              </div>
              <div class="segment-content">
                <div class="segment-emotion">
                  <span class="emotion-tag">{{ segment.emotion }}</span>
                  <span class="reuse-badge" v-if="segment.reuse_score >= 80">
                    🔄 高复用
                  </span>
                </div>
                <span class="segment-desc">{{ segment.description }}</span>
                <div class="segment-scores">
                  <span class="score-item">质量: {{ segment.quality_score }}</span>
                  <span class="score-item">转化: {{ segment.conversion_score }}</span>
                  <span class="score-item">复用: {{ segment.reuse_score }}</span>
                </div>
                <div class="segment-tags">
                  <el-tag v-for="tag in segment.tags" :key="tag" size="small" type="info">
                    {{ tag }}
                  </el-tag>
                </div>
              </div>
            </div>
          </div>
          <div v-else-if="!creatingSegments" class="empty-segments">
            <p>还没有片段数据</p>
            <p class="empty-hint">点击上方按钮让AI自动生成可被剪辑调用的片段</p>
          </div>
        </div>
      </div>
    </el-dialog>
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { ElMessage } from 'element-plus'
import { IVideoPlay, IScissors } from '@/utils/icons'
import {
  searchAssets,
  batchAnalyze,
  getIntelligenceStats,
  getAssetScore,
  type SearchResult,
  type IntelligenceStats,
  type ScoreBreakdown,
} from '@/api/assetIntelligence'
import {
  getSegmentsByAsset,
  createSegments,
  type AssetSegmentItem,
  ROLE_LABELS,
  ROLE_COLORS,
} from '@/api/assetSegment'

const stats = ref<IntelligenceStats>({
  total_assets: 0,
  analyzed_count: 0,
  pending_count: 0,
  average_score: 0,
  high_score_count: 0,
  analysis_rate: 0,
})

const searchResults = ref<SearchResult[]>([])
const searchQuery = ref('')
const filterScene = ref('')
const filterEmotion = ref('')
const filterMinScore = ref(0)

const detailVisible = ref(false)
const selectedAsset = ref<SearchResult | null>(null)
const scoreBreakdown = ref<ScoreBreakdown | null>(null)
const assetSegments = ref<AssetSegmentItem[]>([])
const creatingSegments = ref(false)

const activeFilters = ref<{ key: string; label: string; value: string }[]>([])

const formatDuration = (seconds: number) => {
  if (!seconds) return '0:00'
  const min = Math.floor(seconds / 60)
  const sec = Math.floor(seconds % 60)
  return `${min}:${sec.toString().padStart(2, '0')}`
}

const getScoreClass = (score: number) => {
  if (score >= 90) return 'excellent'
  if (score >= 80) return 'good'
  if (score >= 60) return 'average'
  return 'poor'
}

const getProgressColor = (score: number) => {
  if (score >= 90) return '#67c23a'
  if (score >= 80) return '#409eff'
  if (score >= 60) return '#e6a23c'
  return '#f56c6c'
}

const loadStats = async () => {
  try {
    const res = await getIntelligenceStats()
    if (res.data.success) {
      stats.value = res.data.data
    }
  } catch (error) {
    console.error('Load stats failed:', error)
  }
}

const handleSearch = async () => {
  try {
    const res = await searchAssets({
      query: searchQuery.value || undefined,
      scene_type: filterScene.value || undefined,
      emotion: filterEmotion.value || undefined,
      min_score: filterMinScore.value,
      limit: 50,
    })
    if (res.data.success) {
      searchResults.value = res.data.data
    }
  } catch (error) {
    console.error('Search failed:', error)
  }
}

const batchAnalyzeAssets = async () => {
  try {
    ElMessage.info('开始批量分析素材...')
    const res = await batchAnalyze()
    if (res.data.success) {
      ElMessage.success(`分析完成：${res.data.data.completed} 成功，${res.data.data.failed} 失败`)
      loadStats()
      handleSearch()
    }
  } catch (error) {
    console.error('Batch analyze failed:', error)
  }
}

const showAssetDetail = async (result: SearchResult) => {
  selectedAsset.value = result
  detailVisible.value = true
  assetSegments.value = []

  try {
    const res = await getAssetScore(result.asset.id)
    if (res.data.success) {
      scoreBreakdown.value = res.data.data
    }
  } catch (error) {
    console.error('Load score failed:', error)
  }

  try {
    const res = await getSegmentsByAsset(result.asset.id)
    if (res.data.success) {
      assetSegments.value = res.data.data.segments
    }
  } catch (error) {
    console.error('Load segments failed:', error)
  }
}

const handleCreateSegments = async () => {
  if (!selectedAsset.value) return
  
  creatingSegments.value = true
  try {
    const res = await createSegments(selectedAsset.value.asset.id)
    if (res.data.success) {
      ElMessage.success(res.data.message)
      try {
        const segRes = await getSegmentsByAsset(selectedAsset.value!.asset.id)
        if (segRes.data.success) {
          assetSegments.value = segRes.data.data.segments
        }
      } catch (error) {
        console.error('Refresh segments failed:', error)
      }
    }
  } catch (error) {
    console.error('Create segments failed:', error)
    ElMessage.error('创建片段失败')
  } finally {
    creatingSegments.value = false
  }
}

const removeFilter = (key: string) => {
  if (key === 'scene') filterScene.value = ''
  if (key === 'emotion') filterEmotion.value = ''
  if (key === 'minScore') filterMinScore.value = 0
  handleSearch()
}

onMounted(() => {
  loadStats()
  handleSearch()
})
</script>

<style scoped>
.asset-library-page {
  padding: 16px;
}

.page-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 20px;
}

.page-header h1 {
  font-size: 24px;
  margin: 0;
}

/* 统计卡片 */
.stats-grid {
  display: grid;
  grid-template-columns: repeat(4, 1fr);
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

/* 搜索区域 */
.search-section {
  margin-bottom: 16px;
}

.search-box {
  margin-bottom: 12px;
}

.filter-tags {
  display: flex;
  gap: 8px;
  flex-wrap: wrap;
}

/* 快速筛选 */
.quick-filters {
  background: white;
  border-radius: 12px;
  padding: 16px;
  box-shadow: 0 2px 8px rgba(0, 0, 0, 0.05);
  margin-bottom: 20px;
}

.filter-group {
  display: flex;
  align-items: center;
  gap: 12px;
  margin-bottom: 12px;
}

.filter-group:last-child {
  margin-bottom: 0;
}

.filter-label {
  font-size: 13px;
  color: #666;
  min-width: 50px;
}

/* 素材网格 */
.assets-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(280px, 1fr));
  gap: 16px;
}

.asset-card {
  background: white;
  border-radius: 12px;
  overflow: hidden;
  box-shadow: 0 2px 8px rgba(0, 0, 0, 0.05);
  cursor: pointer;
  transition: transform 0.2s, box-shadow 0.2s;
}

.asset-card:hover {
  transform: translateY(-4px);
  box-shadow: 0 8px 24px rgba(0, 0, 0, 0.1);
}

.asset-thumbnail {
  position: relative;
  height: 160px;
  background: #f5f7fa;
  display: flex;
  align-items: center;
  justify-content: center;
}

.thumbnail-placeholder {
  color: #c0c4cc;
}

.asset-duration {
  position: absolute;
  bottom: 8px;
  right: 8px;
  background: rgba(0, 0, 0, 0.7);
  color: white;
  padding: 2px 8px;
  border-radius: 4px;
  font-size: 12px;
}

.asset-score-badge {
  position: absolute;
  top: 8px;
  right: 8px;
  padding: 4px 12px;
  border-radius: 20px;
  font-size: 14px;
  font-weight: 600;
  color: white;
}

.asset-score-badge.excellent {
  background: #67c23a;
}

.asset-score-badge.good {
  background: #409eff;
}

.asset-score-badge.average {
  background: #e6a23c;
}

.asset-score-badge.poor {
  background: #f56c6c;
}

.asset-info {
  padding: 16px;
}

.asset-name {
  margin: 0 0 10px;
  font-size: 15px;
  font-weight: 500;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

.asset-tags {
  display: flex;
  gap: 6px;
  margin-bottom: 8px;
  flex-wrap: wrap;
}

.asset-topics {
  display: flex;
  gap: 6px;
  margin-bottom: 10px;
  flex-wrap: wrap;
}

.topic-tag {
  font-size: 12px;
  color: #667eea;
}

.score-bar {
  display: flex;
  align-items: center;
  gap: 8px;
  margin-bottom: 8px;
}

.score-bar .score-label {
  font-size: 12px;
  color: #888;
  min-width: 30px;
}

.score-bar .el-progress {
  flex: 1;
}

.asset-meta {
  display: flex;
  justify-content: space-between;
  font-size: 12px;
  color: #888;
}

/* 详情弹窗 */
.asset-detail-dialog :deep(.el-dialog__body) {
  padding: 0;
}

.asset-detail {
  padding: 20px;
}

.detail-header {
  display: flex;
  gap: 20px;
  margin-bottom: 24px;
}

.detail-score {
  flex-shrink: 0;
}

.score-circle {
  width: 100px;
  height: 100px;
  border-radius: 50%;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  color: white;
}

.score-circle.excellent {
  background: linear-gradient(135deg, #67c23a, #85ce61);
}

.score-circle.good {
  background: linear-gradient(135deg, #409eff, #66b1ff);
}

.score-circle.average {
  background: linear-gradient(135deg, #e6a23c, #ebb563);
}

.score-number {
  font-size: 32px;
  font-weight: bold;
}

.score-label {
  font-size: 12px;
}

.detail-summary {
  flex: 1;
}

.detail-summary h3 {
  margin: 0 0 8px;
  font-size: 18px;
}

.summary-text {
  margin: 0 0 12px;
  font-size: 14px;
  color: #666;
  line-height: 1.6;
}

.detail-tags {
  display: flex;
  gap: 8px;
  flex-wrap: wrap;
}

/* 五维评分 */
.dimension-scores {
  background: #f8f9fa;
  border-radius: 12px;
  padding: 20px;
  margin-bottom: 24px;
}

.dimension-scores h4 {
  margin: 0 0 16px;
  font-size: 16px;
}

.dimension-grid {
  display: grid;
  grid-template-columns: repeat(2, 1fr);
  gap: 16px;
}

.dimension-item {
  display: flex;
  align-items: center;
  gap: 12px;
}

.dimension-label {
  font-size: 13px;
  color: #666;
  min-width: 70px;
}

.dimension-item .el-progress {
  flex: 1;
}

.dimension-value {
  font-size: 14px;
  font-weight: 600;
  color: #333;
  min-width: 30px;
  text-align: right;
}

/* 片段列表 */
.segments-section {
  margin-top: 24px;
}

.segments-section .section-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 16px;
}

.segments-section h4 {
  margin: 0;
  font-size: 16px;
}

.segments-list {
  display: flex;
  flex-direction: column;
  gap: 12px;
}

.segment-item {
  background: #f8f9fa;
  border-radius: 8px;
  padding: 16px;
  border-left: 4px solid #e0e0e0;
}

.segment-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 10px;
  flex-wrap: wrap;
  gap: 8px;
}

.segment-index {
  font-weight: 600;
  font-size: 14px;
}

.segment-role {
  padding: 4px 12px;
  border-radius: 20px;
  font-size: 12px;
  font-weight: 600;
  color: white;
}

.segment-time {
  font-size: 13px;
  color: #888;
}

.segment-score {
  padding: 2px 10px;
  border-radius: 12px;
  font-size: 12px;
  font-weight: 600;
  color: white;
}

.segment-content {
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.segment-emotion {
  display: flex;
  align-items: center;
  gap: 8px;
}

.emotion-tag {
  font-size: 14px;
  color: #667eea;
  font-weight: 500;
}

.reuse-badge {
  font-size: 12px;
  padding: 2px 8px;
  background: #f5f7fa;
  border-radius: 4px;
  color: #67c23a;
}

.segment-desc {
  font-size: 13px;
  color: #666;
}

.segment-scores {
  display: flex;
  gap: 16px;
  font-size: 12px;
}

.score-item {
  color: #888;
}

.score-item::before {
  content: '•';
  margin-right: 4px;
}

.segment-tags {
  display: flex;
  gap: 6px;
}

.empty-segments {
  text-align: center;
  padding: 40px;
  background: #f8f9fa;
  border-radius: 8px;
}

.empty-segments p {
  margin: 0 0 8px;
  color: #666;
}

.empty-segments .empty-hint {
  font-size: 12px;
  color: #999;
}

.empty-state {
  padding: 60px 0;
}

@media (max-width: 768px) {
  .stats-grid {
    grid-template-columns: repeat(2, 1fr);
  }

  .dimension-grid {
    grid-template-columns: 1fr;
  }

  .detail-header {
    flex-direction: column;
    align-items: center;
    text-align: center;
  }
}
</style>
