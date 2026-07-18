<template>
  <div class="director-page">
    <!-- 页面标题 -->
    <div class="page-header">
      <h1>🎬 AI导演编排</h1>
      <el-button type="primary" @click="showGenerateDialog = true">
        ✨ 生成剪辑方案
      </el-button>
    </div>

    <!-- 统计卡片 -->
    <div class="stats-grid">
      <div class="stat-card">
        <div class="stat-icon">📋</div>
        <div class="stat-info">
          <span class="stat-value">{{ stats.total_plans }}</span>
          <span class="stat-label">剪辑方案</span>
        </div>
      </div>
      <div class="stat-card">
        <div class="stat-icon">✅</div>
        <div class="stat-info">
          <span class="stat-value">{{ stats.matched_plans }}</span>
          <span class="stat-label">完全匹配</span>
        </div>
      </div>
      <div class="stat-card">
        <div class="stat-icon">📊</div>
        <div class="stat-info">
          <span class="stat-value">{{ stats.match_rate }}%</span>
          <span class="stat-label">素材匹配率</span>
        </div>
      </div>
      <div class="stat-card">
        <div class="stat-icon">📈</div>
        <div class="stat-info">
          <span class="stat-value">{{ (stats.avg_predicted_completion * 100).toFixed(0) }}%</span>
          <span class="stat-label">平均预测完播</span>
        </div>
      </div>
    </div>

    <!-- 剪辑方案列表 -->
    <div v-if="plans.length > 0" class="plans-list">
      <div
        v-for="plan in plans"
        :key="plan.id"
        class="plan-card"
        @click="showPlanDetail(plan)"
      >
        <div class="plan-header">
          <h3>{{ plan.title }}</h3>
          <el-tag
            :type="getMatchStatusType(plan.match_status)"
            size="small"
          >
            {{ getMatchStatusLabel(plan.match_status) }}
          </el-tag>
        </div>
        <div class="plan-meta">
          <span>⏱️ {{ plan.total_duration }}秒</span>
          <span>🎬 {{ plan.matched_shots }}/{{ plan.total_shots }}镜头</span>
          <span v-if="plan.missing_shots > 0" class="missing-badge">
            ⚠️ 缺{{ plan.missing_shots }}个
          </span>
        </div>
        <div class="plan-strategy">
          <el-tag size="small" type="info">{{ getStrategyLabel(plan.editing_strategy) }}</el-tag>
        </div>
        <div class="plan-predictions">
          <div class="prediction-item">
            <span class="prediction-label">预测完播</span>
            <el-progress
              :percentage="plan.predicted_completion_rate * 100"
              :stroke-width="6"
              :color="'#67c23a'"
              :show-text="false"
            />
            <span class="prediction-value">{{ (plan.predicted_completion_rate * 100).toFixed(0) }}%</span>
          </div>
          <div class="prediction-item">
            <span class="prediction-label">预测转化</span>
            <el-progress
              :percentage="plan.predicted_conversion_rate * 1000"
              :stroke-width="6"
              :color="'#409eff'"
              :show-text="false"
            />
            <span class="prediction-value">{{ (plan.predicted_conversion_rate * 100).toFixed(1) }}%</span>
          </div>
        </div>
      </div>
    </div>

    <div v-else class="empty-state">
      <el-empty description="还没有剪辑方案，点击上方按钮生成">
        <el-button type="primary" @click="showGenerateDialog = true">生成第一个方案</el-button>
      </el-empty>
    </div>

    <!-- 生成方案弹窗 -->
    <el-dialog v-model="showGenerateDialog" title="AI导演生成剪辑方案" width="600px">
      <el-form :model="generateForm" label-width="100px">
        <el-form-item label="文案内容">
          <el-input
            v-model="generateForm.script_content"
            type="textarea"
            :rows="6"
            placeholder="输入视频文案，AI导演将自动拆分镜头并匹配素材"
          />
        </el-form-item>
        <el-form-item label="视频时长">
          <el-slider
            v-model="generateForm.target_duration"
            :min="15"
            :max="90"
            :step="5"
            show-input
            style="width: 100%"
          />
        </el-form-item>
        <el-form-item label="剪辑策略">
          <el-radio-group v-model="generateForm.strategy">
            <el-radio-button label="standard">标准型</el-radio-button>
            <el-radio-button label="story">故事型</el-radio-button>
            <el-radio-button label="product">产品型</el-radio-button>
            <el-radio-button label="knowledge">知识型</el-radio-button>
          </el-radio-group>
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="showGenerateDialog = false">取消</el-button>
        <el-button type="primary" :loading="generating" @click="handleGenerate">生成方案</el-button>
      </template>
    </el-dialog>

    <!-- 方案详情弹窗 -->
    <el-dialog
      v-model="detailVisible"
      title="AI导演剪辑方案"
      width="90%"
      class="plan-detail-dialog"
    >
      <div v-if="selectedPlan" class="plan-detail">
        <!-- 头部 -->
        <div class="detail-header">
          <div>
            <h2>{{ selectedPlan.title }}</h2>
            <div class="detail-meta">
              <el-tag :type="getMatchStatusType(selectedPlan.match_status)">
                {{ getMatchStatusLabel(selectedPlan.match_status) }}
              </el-tag>
              <el-tag type="info">{{ getStrategyLabel(selectedPlan.editing_strategy) }}</el-tag>
              <span>⏱️ {{ selectedPlan.total_duration }}秒</span>
              <span>🎬 {{ selectedPlan.matched_shots }}/{{ selectedPlan.total_shots }}镜头匹配</span>
            </div>
          </div>
        </div>

        <!-- 导演分析 -->
        <div v-if="selectedPlan.director_analysis" class="analysis-section">
          <h4>🎭 AI导演分析</h4>
          <div class="analysis-grid">
            <div class="analysis-item">
              <span class="label">目标受众</span>
              <span class="value">{{ selectedPlan.director_analysis.target_audience }}</span>
            </div>
            <div class="analysis-item">
              <span class="label">核心信息</span>
              <span class="value">{{ selectedPlan.director_analysis.key_message }}</span>
            </div>
            <div class="analysis-item">
              <span class="label">推荐风格</span>
              <span class="value">{{ selectedPlan.director_analysis.recommended_style }}</span>
            </div>
            <div class="analysis-item">
              <span class="label">情绪流</span>
              <span class="value">{{ selectedPlan.director_analysis.emotion_flow?.join(' → ') }}</span>
            </div>
            <div class="analysis-item" v-if="selectedPlan.director_analysis.matched_template">
              <span class="label">匹配模板</span>
              <span class="value">{{ selectedPlan.director_analysis.matched_template }}</span>
            </div>
          </div>
        </div>

        <!-- 导演评分 -->
        <div v-if="selectedPlan.director_score" class="score-section">
          <h4>⭐ 导演评分：{{ selectedPlan.director_score }}分</h4>
          <div class="score-breakdown" v-if="selectedPlan.score_breakdown">
            <div
              v-for="(item, key) in selectedPlan.score_breakdown"
              :key="key"
              class="score-item"
            >
              <div class="score-item-header">
                <span class="score-label">{{ getScoreLabel(key) }}</span>
                <span class="score-value">{{ item.score }}/{{ item.max }}</span>
              </div>
              <el-progress
                :percentage="Math.round(item.score / item.max * 100)"
                :stroke-width="8"
                :color="item.score / item.max >= 0.8 ? '#67c23a' : item.score / item.max >= 0.6 ? '#e6a23c' : '#f56c6c'"
                :show-text="false"
              />
              <div class="score-reason">{{ item.reason }}</div>
            </div>
          </div>
          <div class="score-reasons-list" v-if="selectedPlan.score_reasons">
            <span v-for="reason in selectedPlan.score_reasons" :key="reason" class="reason-tag">
              {{ reason }}
            </span>
          </div>
        </div>

        <!-- 补拍闭环状态 -->
        <div v-if="selectedPlan.shooting_task_ids && selectedPlan.shooting_task_ids.length > 0" class="shooting-status-section">
          <h4>🔄 补拍任务（闭环）</h4>
          <div class="shooting-tasks">
            <el-button type="primary" size="small" @click="checkShootingStatus(selectedPlan.id)">
              检查补拍状态
            </el-button>
            <el-button
              v-if="shootingStatus?.can_regenerate"
              type="success"
              size="small"
              @click="handleRegenerate(selectedPlan.id)"
            >
              重新生成方案
            </el-button>
          </div>
        </div>

        <!-- 预测效果 -->
        <div class="predictions-section">
          <h4>📊 预测效果</h4>
          <div class="predictions-grid">
            <div class="prediction-card">
              <div class="prediction-icon">📈</div>
              <div class="prediction-info">
                <span class="prediction-number">{{ (selectedPlan.predicted_completion_rate * 100).toFixed(0) }}%</span>
                <span class="prediction-text">预测完播率</span>
              </div>
            </div>
            <div class="prediction-card">
              <div class="prediction-icon">💰</div>
              <div class="prediction-info">
                <span class="prediction-number">{{ (selectedPlan.predicted_conversion_rate * 100).toFixed(1) }}%</span>
                <span class="prediction-text">预测转化率</span>
              </div>
            </div>
          </div>
        </div>

        <!-- 镜头列表 -->
        <div class="shots-section">
          <h4>🎬 镜头编排</h4>
          <div class="shots-timeline">
            <div
              v-for="seg in selectedPlan.segments"
              :key="seg.id"
              class="shot-item"
              :class="{ missing: seg.match_status === 'missing' }"
            >
              <div class="shot-left">
                <span class="shot-seq">{{ seg.sequence }}</span>
                <span
                  class="shot-role-tag"
                  :style="{ background: ROLE_COLORS[seg.role] }"
                >
                  {{ ROLE_LABELS[seg.role] }}
                </span>
              </div>
              <div class="shot-center">
                <div class="shot-time">{{ seg.start_time.toFixed(1) }}s - {{ seg.end_time.toFixed(1) }}s ({{ seg.duration.toFixed(1) }}s)</div>
                <div class="shot-subtitle">{{ seg.subtitle_text }}</div>
                <div class="shot-reason" v-if="seg.reason">{{ seg.reason }}</div>
              </div>
              <div class="shot-right">
                <el-tag
                  :type="seg.match_status === 'matched' ? 'success' : 'danger'"
                  size="small"
                >
                  {{ seg.match_status === 'matched' ? `${seg.match_score.toFixed(0)}分` : '缺失' }}
                </el-tag>
                <div class="shot-transition">{{ getTransitionLabel(seg.transition) }}</div>
              </div>
            </div>
          </div>
        </div>

        <!-- 补拍建议 -->
        <div v-if="selectedPlan.shooting_suggestions && selectedPlan.shooting_suggestions.length > 0" class="suggestions-section">
          <h4>⚠️ 素材不足 - 补拍建议</h4>
          <div class="suggestions-list">
            <div
              v-for="(sug, idx) in selectedPlan.shooting_suggestions"
              :key="idx"
              class="suggestion-item"
            >
              <div class="sug-header">
                <span
                  class="sug-role"
                  :style="{ background: ROLE_COLORS[sug.role] }"
                >
                  {{ ROLE_LABELS[sug.role] }}
                </span>
                <el-tag v-if="sug.required" type="danger" size="small">必须</el-tag>
                <span class="sug-duration">{{ sug.duration }}秒</span>
                <span class="sug-emotion">{{ sug.emotion }}</span>
              </div>
              <div class="sug-desc">{{ sug.description }}</div>
              <div class="sug-tips">
                <span v-for="tip in sug.tips" :key="tip" class="tip-tag">{{ tip }}</span>
              </div>
              <div v-if="sug.note" class="sug-note">{{ sug.note }}</div>
            </div>
          </div>
        </div>
      </div>
    </el-dialog>
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { ElMessage } from 'element-plus'
import {
  generatePlan,
  getPlans,
  getDirectorStats,
  getShootingTasksStatus,
  regeneratePlan,
  STRATEGY_LABELS,
  ROLE_LABELS,
  ROLE_COLORS,
  MATCH_STATUS_MAP,
  type VideoEditPlan,
  type DirectorStats,
  type ShootingTaskStatus,
} from '@/api/videoDirector'

const plans = ref<VideoEditPlan[]>([])
const stats = ref<DirectorStats>({
  total_plans: 0,
  matched_plans: 0,
  partial_plans: 0,
  total_shots: 0,
  matched_shots: 0,
  missing_shots: 0,
  match_rate: 0,
  avg_predicted_completion: 0,
  avg_predicted_conversion: 0,
})

const showGenerateDialog = ref(false)
const generating = ref(false)
const detailVisible = ref(false)
const selectedPlan = ref<VideoEditPlan | null>(null)
const shootingStatus = ref<ShootingTaskStatus | null>(null)

const generateForm = ref({
  script_content: '',
  target_duration: 30,
  strategy: 'standard',
})

const getStrategyLabel = (strategy: string) => STRATEGY_LABELS[strategy] || strategy
const getMatchStatusLabel = (status: string) => MATCH_STATUS_MAP[status]?.label || status
const getMatchStatusType = (status: string) => {
  const map: Record<string, string> = {
    matched: 'success',
    partial: 'warning',
    failed: 'danger',
    pending: 'info',
  }
  return map[status] || 'info'
}

const getTransitionLabel = (transition: string) => {
  const labels: Record<string, string> = {
    cut: '硬切',
    fade: '淡入淡出',
    slide: '滑动',
    zoom: '缩放',
    dissolve: '溶解',
  }
  return labels[transition] || transition
}

const loadPlans = async () => {
  try {
    const res = await getPlans()
    if (res.data.success) {
      plans.value = res.data.data
    }
  } catch (error) {
    console.error('Load plans failed:', error)
  }
}

const loadStats = async () => {
  try {
    const res = await getDirectorStats()
    if (res.data.success) {
      stats.value = res.data.data
    }
  } catch (error) {
    console.error('Load stats failed:', error)
  }
}

const handleGenerate = async () => {
  if (!generateForm.value.script_content.trim()) {
    ElMessage.warning('请输入文案内容')
    return
  }

  generating.value = true
  try {
    const res = await generatePlan({
      script_content: generateForm.value.script_content,
      target_duration: generateForm.value.target_duration,
      strategy: generateForm.value.strategy,
    })
    if (res.data.success) {
      ElMessage.success(res.data.message)
      showGenerateDialog.value = false
      generateForm.value.script_content = ''
      loadPlans()
      loadStats()
    }
  } catch (error) {
    console.error('Generate failed:', error)
    ElMessage.error('生成失败')
  } finally {
    generating.value = false
  }
}

const showPlanDetail = (plan: VideoEditPlan) => {
  selectedPlan.value = plan
  shootingStatus.value = null
  detailVisible.value = true
}

const getScoreLabel = (key: string) => {
  const labels: Record<string, string> = {
    template_match: '爆款结构匹配',
    asset_quality: '素材质量',
    creator_fit: '主播适配度',
    conversion: '商业转化',
    originality: '原创度',
  }
  return labels[key] || key
}

const checkShootingStatus = async (planId: number) => {
  try {
    const res = await getShootingTasksStatus(planId)
    if (res.data.success) {
      shootingStatus.value = res.data.data
      if (res.data.data.all_completed) {
        ElMessage.success('所有补拍任务已完成，可以重新生成方案')
      } else {
        ElMessage.info(`补拍进度：${res.data.data.completed_count}/${res.data.data.total_tasks}已完成`)
      }
    }
  } catch (error) {
    console.error('Check shooting status failed:', error)
  }
}

const handleRegenerate = async (planId: number) => {
  try {
    const res = await regeneratePlan(planId)
    if (res.data.success) {
      ElMessage.success(res.data.message)
      selectedPlan.value = res.data.data as VideoEditPlan
      shootingStatus.value = null
      loadPlans()
      loadStats()
    } else {
      ElMessage.warning(res.data.message)
    }
  } catch (error) {
    console.error('Regenerate failed:', error)
    ElMessage.error('重新生成失败')
  }
}

onMounted(() => {
  loadPlans()
  loadStats()
})
</script>

<style scoped>
.director-page {
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

.plans-list {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(320px, 1fr));
  gap: 16px;
}

.plan-card {
  background: white;
  border-radius: 12px;
  padding: 20px;
  box-shadow: 0 2px 8px rgba(0, 0, 0, 0.05);
  cursor: pointer;
  transition: transform 0.2s, box-shadow 0.2s;
}

.plan-card:hover {
  transform: translateY(-4px);
  box-shadow: 0 8px 24px rgba(0, 0, 0, 0.1);
}

.plan-header {
  display: flex;
  justify-content: space-between;
  align-items: flex-start;
  margin-bottom: 12px;
}

.plan-header h3 {
  margin: 0;
  font-size: 16px;
  flex: 1;
  margin-right: 8px;
}

.plan-meta {
  display: flex;
  gap: 16px;
  font-size: 13px;
  color: #888;
  margin-bottom: 8px;
}

.missing-badge {
  color: #f56c6c;
  font-weight: 500;
}

.plan-strategy {
  margin-bottom: 12px;
}

.plan-predictions {
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.prediction-item {
  display: flex;
  align-items: center;
  gap: 8px;
}

.prediction-item .prediction-label {
  font-size: 12px;
  color: #888;
  min-width: 60px;
}

.prediction-item .el-progress {
  flex: 1;
}

.prediction-item .prediction-value {
  font-size: 13px;
  font-weight: 600;
  min-width: 40px;
  text-align: right;
}

.empty-state {
  padding: 60px 0;
}

/* 导演评分 */
.score-section {
  background: #f0f5ff;
  border-radius: 12px;
  padding: 20px;
  margin-bottom: 20px;
}

.score-section h4 {
  margin: 0 0 16px;
  font-size: 16px;
  color: #1890ff;
}

.score-breakdown {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(200px, 1fr));
  gap: 16px;
  margin-bottom: 16px;
}

.score-item {
  background: white;
  border-radius: 8px;
  padding: 12px;
}

.score-item-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 8px;
}

.score-label {
  font-size: 13px;
  color: #666;
}

.score-value {
  font-size: 14px;
  font-weight: 600;
  color: #333;
}

.score-reason {
  margin-top: 8px;
  font-size: 12px;
  color: #888;
}

.score-reasons-list {
  display: flex;
  flex-wrap: wrap;
  gap: 6px;
}

.reason-tag {
  font-size: 12px;
  padding: 2px 8px;
  background: white;
  border-radius: 4px;
  color: #555;
}

/* 补拍闭环 */
.shooting-status-section {
  background: #f6ffed;
  border-radius: 12px;
  padding: 20px;
  margin-bottom: 20px;
}

.shooting-status-section h4 {
  margin: 0 0 16px;
  font-size: 16px;
  color: #52c41a;
}

.shooting-tasks {
  display: flex;
  gap: 12px;
}

/* 详情弹窗 */
.plan-detail-dialog :deep(.el-dialog__body) {
  padding: 0;
}

.plan-detail {
  padding: 20px;
}

.detail-header {
  margin-bottom: 24px;
}

.detail-header h2 {
  margin: 0 0 8px;
  font-size: 20px;
}

.detail-meta {
  display: flex;
  gap: 12px;
  align-items: center;
  flex-wrap: wrap;
  font-size: 13px;
  color: #888;
}

.analysis-section {
  background: #f8f9fa;
  border-radius: 12px;
  padding: 20px;
  margin-bottom: 20px;
}

.analysis-section h4 {
  margin: 0 0 16px;
  font-size: 16px;
}

.analysis-grid {
  display: grid;
  grid-template-columns: repeat(2, 1fr);
  gap: 16px;
}

.analysis-item {
  display: flex;
  flex-direction: column;
  gap: 4px;
}

.analysis-item .label {
  font-size: 12px;
  color: #888;
}

.analysis-item .value {
  font-size: 14px;
  font-weight: 500;
}

.predictions-section {
  margin-bottom: 20px;
}

.predictions-section h4 {
  margin: 0 0 16px;
  font-size: 16px;
}

.predictions-grid {
  display: grid;
  grid-template-columns: repeat(2, 1fr);
  gap: 16px;
}

.prediction-card {
  background: #f8f9fa;
  border-radius: 12px;
  padding: 20px;
  display: flex;
  align-items: center;
  gap: 16px;
}

.prediction-icon {
  font-size: 32px;
}

.prediction-info {
  display: flex;
  flex-direction: column;
}

.prediction-number {
  font-size: 24px;
  font-weight: bold;
  color: #333;
}

.prediction-text {
  font-size: 12px;
  color: #888;
}

.shots-section {
  margin-bottom: 24px;
}

.shots-section h4 {
  margin: 0 0 16px;
  font-size: 16px;
}

.shots-timeline {
  display: flex;
  flex-direction: column;
  gap: 12px;
}

.shot-item {
  display: flex;
  gap: 16px;
  background: #f8f9fa;
  border-radius: 8px;
  padding: 16px;
  border-left: 4px solid #409eff;
}

.shot-item.missing {
  border-left-color: #f56c6c;
  background: #fef0f0;
}

.shot-left {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 8px;
  min-width: 80px;
}

.shot-seq {
  font-size: 24px;
  font-weight: bold;
  color: #333;
}

.shot-role-tag {
  padding: 4px 12px;
  border-radius: 20px;
  font-size: 12px;
  font-weight: 600;
  color: white;
  white-space: nowrap;
}

.shot-center {
  flex: 1;
  display: flex;
  flex-direction: column;
  gap: 6px;
}

.shot-time {
  font-size: 13px;
  color: #888;
}

.shot-subtitle {
  font-size: 14px;
  color: #333;
}

.shot-reason {
  font-size: 12px;
  color: #667eea;
}

.shot-right {
  display: flex;
  flex-direction: column;
  align-items: flex-end;
  gap: 8px;
  min-width: 80px;
}

.shot-transition {
  font-size: 12px;
  color: #888;
}

.suggestions-section {
  background: #fff8e1;
  border-radius: 12px;
  padding: 20px;
}

.suggestions-section h4 {
  margin: 0 0 16px;
  font-size: 16px;
  color: #e6a23c;
}

.suggestions-list {
  display: flex;
  flex-direction: column;
  gap: 12px;
}

.suggestion-item {
  background: white;
  border-radius: 8px;
  padding: 16px;
}

.sug-header {
  display: flex;
  align-items: center;
  gap: 8px;
  margin-bottom: 8px;
  flex-wrap: wrap;
}

.sug-role {
  padding: 4px 12px;
  border-radius: 20px;
  font-size: 12px;
  font-weight: 600;
  color: white;
}

.sug-duration {
  font-size: 13px;
  color: #888;
}

.sug-emotion {
  font-size: 13px;
  color: #667eea;
}

.sug-desc {
  font-size: 14px;
  color: #333;
  margin-bottom: 8px;
}

.sug-tips {
  display: flex;
  gap: 6px;
  flex-wrap: wrap;
}

.tip-tag {
  font-size: 12px;
  padding: 2px 8px;
  background: #f0f2f5;
  border-radius: 4px;
  color: #666;
}

.sug-note {
  margin-top: 8px;
  font-size: 13px;
  color: #f56c6c;
  font-weight: 500;
}

@media (max-width: 768px) {
  .stats-grid {
    grid-template-columns: repeat(2, 1fr);
  }

  .analysis-grid {
    grid-template-columns: 1fr;
  }

  .predictions-grid {
    grid-template-columns: 1fr;
  }
}
</style>
