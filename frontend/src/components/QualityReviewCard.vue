<template>
  <div class="quality-review-card">
    <!-- 综合评分头部 -->
    <div class="review-header">
      <div class="final-score" :class="scoreClass">
        <span class="score-value">{{ reviewResult.scores.final }}</span>
        <span class="score-label">综合评分</span>
      </div>
      <div class="risk-badge" :class="riskClass">
        <span v-if="reviewResult.risk_level === 'safe'">✅ 安全</span>
        <span v-else-if="reviewResult.risk_level === 'low'">⚠️ 低风险</span>
        <span v-else-if="reviewResult.risk_level === 'medium'">🔶 中风险</span>
        <span v-else>🚨 高风险</span>
      </div>
    </div>

    <!-- 四大维度评分 -->
    <div class="score-grid">
      <div class="score-item" @click="showDetail('health')">
        <div class="score-bar">
          <div class="bar-fill health" :style="{ width: reviewResult.scores.health + '%' }"></div>
        </div>
        <div class="score-info">
          <span class="score-name">🏥 健康合规</span>
          <span class="score-num" :class="{ danger: reviewResult.scores.health < 80 }">
            {{ reviewResult.scores.health }}
          </span>
        </div>
        <p class="score-summary">{{ reviewResult.analysis.health.summary }}</p>
      </div>

      <div class="score-item" @click="showDetail('marketing')">
        <div class="score-bar">
          <div class="bar-fill marketing" :style="{ width: reviewResult.scores.marketing + '%' }"></div>
        </div>
        <div class="score-info">
          <span class="score-name">📢 营销自然度</span>
          <span class="score-num" :class="{ warning: reviewResult.scores.marketing < 85 }">
            {{ reviewResult.scores.marketing }}
          </span>
        </div>
        <p class="score-summary">{{ reviewResult.analysis.marketing.summary }}</p>
      </div>

      <div class="score-item" @click="showDetail('viral')">
        <div class="score-bar">
          <div class="bar-fill viral" :style="{ width: reviewResult.scores.viral + '%' }"></div>
        </div>
        <div class="score-info">
          <span class="score-name">🔥 爆款质量</span>
          <span class="score-num">{{ reviewResult.scores.viral }}</span>
        </div>
        <p class="score-summary">{{ reviewResult.analysis.viral.summary }}</p>
      </div>

      <div class="score-item" @click="showDetail('conversion')">
        <div class="score-bar">
          <div class="bar-fill conversion" :style="{ width: reviewResult.scores.conversion + '%' }"></div>
        </div>
        <div class="score-info">
          <span class="score-name">💬 咨询转化</span>
          <span class="score-num">{{ reviewResult.scores.conversion }}</span>
        </div>
        <p class="score-summary">{{ reviewResult.analysis.conversion.summary }}</p>
      </div>

      <div class="score-item">
        <div class="score-bar">
          <div class="bar-fill originality" :style="{ width: reviewResult.scores.originality + '%' }"></div>
        </div>
        <div class="score-info">
          <span class="score-name">✨ 原创度</span>
          <span class="score-num">{{ reviewResult.scores.originality }}</span>
        </div>
      </div>
    </div>

    <!-- AI建议 -->
    <div v-if="reviewResult.suggestions && reviewResult.suggestions.length > 0" class="suggestions-section">
      <h4>💡 AI优化建议</h4>
      <ul class="suggestions-list">
        <li v-for="(suggestion, index) in reviewResult.suggestions.slice(0, 5)" :key="index">
          {{ suggestion }}
        </li>
      </ul>
    </div>

    <!-- 自动修复按钮 -->
    <div v-if="reviewResult.auto_fixes && reviewResult.auto_fixes.length > 0" class="auto-fix-section">
      <el-button type="primary" size="small" @click="applyAutoFix" :loading="fixing">
        🔧 一键修复 ({{ reviewResult.auto_fixes.length }}处)
      </el-button>
      <p class="fix-desc">AI将自动替换违规表述</p>
    </div>

    <!-- 详情弹窗 -->
    <el-dialog
      v-model="showDetailDialog"
      :title="detailTitle"
      width="90%"
      top="10vh"
    >
      <div v-if="detailType === 'health'" class="detail-content">
        <div class="detail-section">
          <h5>🚨 风险问题</h5>
          <ul v-if="reviewResult.analysis.health.issues.length > 0">
            <li v-for="issue in reviewResult.analysis.health.issues" :key="issue" class="danger-text">
              {{ issue }}
            </li>
          </ul>
          <p v-else class="safe-text">✅ 未发现高风险问题</p>
        </div>
        <div class="detail-section">
          <h5>⚠️ 警告</h5>
          <ul v-if="reviewResult.analysis.health.warnings.length > 0">
            <li v-for="warning in reviewResult.analysis.health.warnings" :key="warning">
              {{ warning }}
            </li>
          </ul>
          <p v-else class="safe-text">✅ 无警告</p>
        </div>
      </div>

      <div v-else-if="detailType === 'marketing'" class="detail-content">
        <div class="detail-section">
          <h5>🚫 硬广词汇</h5>
          <div class="tags">
            <el-tag v-for="word in reviewResult.analysis.marketing.hard_sells" :key="word" type="danger" class="tag">
              {{ word }}
            </el-tag>
          </div>
        </div>
        <div class="detail-section">
          <h5>🔍 软广词汇</h5>
          <div class="tags">
            <el-tag v-for="word in reviewResult.analysis.marketing.soft_sells" :key="word" type="warning" class="tag">
              {{ word }}
            </el-tag>
          </div>
        </div>
        <div class="detail-section">
          <h5>💬 咨询引导</h5>
          <p :class="reviewResult.analysis.marketing.has_consult_guide ? 'safe-text' : 'warning-text'">
            {{ reviewResult.analysis.marketing.has_consult_guide ? '✅ 已包含自然咨询引导' : '⚠️ 缺少自然咨询引导' }}
          </p>
        </div>
      </div>

      <div v-else-if="detailType === 'viral'" class="detail-content">
        <div class="detail-stats">
          <div class="stat-item">
            <span class="stat-label">开头吸引力</span>
            <span class="stat-value">{{ reviewResult.analysis.viral.opening_score }}/30</span>
          </div>
          <div class="stat-item">
            <span class="stat-label">高潮设计</span>
            <span class="stat-value">{{ reviewResult.analysis.viral.climax_score }}/25</span>
          </div>
          <div class="stat-item">
            <span class="stat-label">互动引导</span>
            <span class="stat-value">{{ reviewResult.analysis.viral.interaction_score }}/25</span>
          </div>
          <div class="stat-item">
            <span class="stat-label">内容长度</span>
            <span class="stat-value">{{ reviewResult.analysis.viral.content_length }}字</span>
          </div>
        </div>
      </div>

      <div v-else-if="detailType === 'conversion'" class="detail-content">
        <div class="detail-stats">
          <div class="stat-item">
            <span class="stat-label">信任感建立</span>
            <span class="stat-value">{{ reviewResult.analysis.conversion.trust_score }}/30</span>
          </div>
          <div class="stat-item">
            <span class="stat-label">自然引导</span>
            <span class="stat-value">{{ reviewResult.analysis.conversion.guide_score }}/40</span>
          </div>
        </div>
        <div class="detail-section">
          <h5>⚡ 直接销售词</h5>
          <p :class="reviewResult.analysis.conversion.has_direct_sales ? 'danger-text' : 'safe-text'">
            {{ reviewResult.analysis.conversion.has_direct_sales ? '⚠️ 包含直接销售词，建议移除' : '✅ 无直接销售词' }}
          </p>
        </div>
      </div>
    </el-dialog>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, watch } from 'vue'
import { ElMessage } from 'element-plus'
import type { ReviewResult } from '@/api/contentQuality'

const props = defineProps<{
  reviewResult: ReviewResult
}>()

const emit = defineEmits<{
  (e: 'apply-fix', fixes: any[]): void
}>()

const showDetailDialog = ref(false)
const detailType = ref('')
const fixing = ref(false)

const scoreClass = computed(() => {
  const score = props.reviewResult.scores.final
  if (score >= 90) return 'excellent'
  if (score >= 80) return 'good'
  if (score >= 70) return 'medium'
  return 'poor'
})

const riskClass = computed(() => {
  return `risk-${props.reviewResult.risk_level}`
})

const detailTitle = computed(() => {
  const titles: Record<string, string> = {
    health: '🏥 健康合规详情',
    marketing: '📢 营销自然度详情',
    viral: '🔥 爆款质量详情',
    conversion: '💬 咨询转化详情',
  }
  return titles[detailType.value] || '详情'
})

function showDetail(type: string) {
  detailType.value = type
  showDetailDialog.value = true
}

async function applyAutoFix() {
  fixing.value = true
  try {
    emit('apply-fix', props.reviewResult.auto_fixes)
    ElMessage.success('已应用自动修复')
  } finally {
    fixing.value = false
  }
}
</script>

<style scoped>
.quality-review-card {
  background: white;
  border-radius: 12px;
  padding: 20px;
  box-shadow: 0 2px 8px rgba(0, 0, 0, 0.05);
}

.review-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 20px;
  padding-bottom: 16px;
  border-bottom: 1px solid #f0f0f0;
}

.final-score {
  text-align: center;
}

.final-score .score-value {
  display: block;
  font-size: 42px;
  font-weight: bold;
}

.final-score.excellent .score-value {
  color: #67c23a;
}

.final-score.good .score-value {
  color: #409eff;
}

.final-score.medium .score-value {
  color: #e6a23c;
}

.final-score.poor .score-value {
  color: #f56c6c;
}

.final-score .score-label {
  font-size: 13px;
  color: #888;
}

.risk-badge {
  padding: 6px 12px;
  border-radius: 20px;
  font-size: 14px;
}

.risk-safe {
  background: #f0f9eb;
  color: #67c23a;
}

.risk-low {
  background: #fff7e6;
  color: #e6a23c;
}

.risk-medium {
  background: #fef0f0;
  color: #f56c6c;
}

.risk-high {
  background: #fde2e2;
  color: #c45656;
}

.score-grid {
  display: flex;
  flex-direction: column;
  gap: 16px;
}

.score-item {
  cursor: pointer;
  padding: 12px;
  border-radius: 8px;
  transition: background 0.2s;
}

.score-item:hover {
  background: #f8f9fa;
}

.score-bar {
  height: 6px;
  background: #f0f0f0;
  border-radius: 3px;
  overflow: hidden;
  margin-bottom: 8px;
}

.bar-fill {
  height: 100%;
  transition: width 0.5s ease;
}

.bar-fill.health {
  background: linear-gradient(90deg, #67c23a, #85ce61);
}

.bar-fill.marketing {
  background: linear-gradient(90deg, #409eff, #66b1ff);
}

.bar-fill.viral {
  background: linear-gradient(90deg, #f56c6c, #f89898);
}

.bar-fill.conversion {
  background: linear-gradient(90deg, #e6a23c, #ebb563);
}

.bar-fill.originality {
  background: linear-gradient(90deg, #909399, #b4b4b4);
}

.score-info {
  display: flex;
  justify-content: space-between;
  align-items: center;
}

.score-name {
  font-size: 14px;
  color: #333;
}

.score-num {
  font-size: 18px;
  font-weight: 600;
  color: #333;
}

.score-num.danger {
  color: #f56c6c;
}

.score-num.warning {
  color: #e6a23c;
}

.score-summary {
  font-size: 12px;
  color: #888;
  margin: 4px 0 0;
}

.suggestions-section {
  margin-top: 20px;
  padding-top: 16px;
  border-top: 1px solid #f0f0f0;
}

.suggestions-section h4 {
  font-size: 14px;
  margin-bottom: 12px;
}

.suggestions-list {
  list-style: none;
  padding: 0;
  margin: 0;
}

.suggestions-list li {
  padding: 8px 0;
  font-size: 13px;
  color: #666;
  border-bottom: 1px solid #f5f5f5;
}

.suggestions-list li:last-child {
  border-bottom: none;
}

.auto-fix-section {
  margin-top: 16px;
  text-align: center;
}

.fix-desc {
  font-size: 12px;
  color: #888;
  margin-top: 8px;
}

/* Dialog styles */
.detail-content {
  padding: 0 16px;
}

.detail-section {
  margin-bottom: 20px;
}

.detail-section h5 {
  font-size: 14px;
  margin-bottom: 12px;
}

.detail-section ul {
  list-style: none;
  padding: 0;
  margin: 0;
}

.detail-section li {
  padding: 8px 12px;
  background: #f8f9fa;
  margin-bottom: 8px;
  border-radius: 4px;
  font-size: 13px;
}

.detail-stats {
  display: grid;
  grid-template-columns: repeat(2, 1fr);
  gap: 16px;
}

.stat-item {
  text-align: center;
  padding: 16px;
  background: #f8f9fa;
  border-radius: 8px;
}

.stat-label {
  display: block;
  font-size: 12px;
  color: #888;
  margin-bottom: 8px;
}

.stat-value {
  font-size: 18px;
  font-weight: 600;
  color: #333;
}

.tags {
  display: flex;
  gap: 8px;
  flex-wrap: wrap;
}

.tag {
  margin: 0;
}

.safe-text {
  color: #67c23a;
}

.warning-text {
  color: #e6a23c;
}

.danger-text {
  color: #f56c6c;
}
</style>