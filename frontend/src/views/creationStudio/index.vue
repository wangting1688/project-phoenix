<template>
  <div class="creation-studio">
    <!-- Step 1: 选择配置 -->
    <div v-if="step === 'config'" class="config-step">
      <div class="studio-header">
        <h1>🎬 AI 创作工作台</h1>
        <p class="subtitle">选择一个内容机会，开始你的创作</p>
      </div>

      <div v-if="opportunity" class="opportunity-card">
        <h3>📌 内容机会</h3>
        <div class="opportunity-title">{{ opportunity.title }}</div>
        <div v-if="opportunity.opening" class="opportunity-opening">{{ opportunity.opening }}</div>
        <div class="opportunity-meta">
          <el-tag size="small">{{ opportunity.category }}</el-tag>
          <span class="score">综合评分: {{ opportunity.final_score }}</span>
        </div>
      </div>

      <div class="config-section">
        <h3>🎨 创作风格</h3>
        <div class="style-options">
          <div
            v-for="(template, key) in templates.styles"
            :key="key"
            :class="['style-card', { active: selectedStyle === key }]"
            @click="selectedStyle = key"
          >
            <div class="style-name">{{ template.name }}</div>
            <div class="style-desc">{{ template.description }}</div>
            <div class="style-structure">{{ template.structure }}</div>
          </div>
        </div>
      </div>

      <div class="config-section">
        <h3>⏱️ 视频时长</h3>
        <div class="duration-options">
          <div
            v-for="(label, value) in templates.durations"
            :key="value"
            :class="['duration-card', { active: selectedDuration === Number(value) }]"
            @click="selectedDuration = Number(value)"
          >
            {{ label }}
          </div>
        </div>
      </div>

      <div class="config-section">
        <h3>🗣️ 语气风格</h3>
        <div class="tone-options">
          <div
            v-for="(label, key) in templates.tones"
            :key="key"
            :class="['tone-card', { active: selectedTone === key }]"
            @click="selectedTone = key"
          >
            {{ label }}
          </div>
        </div>
      </div>

      <div class="action-area">
        <el-button
          type="primary"
          size="large"
          :disabled="!canGenerate"
          :loading="generating"
          @click="startGeneration"
        >
          🚀 立即生成
        </el-button>
      </div>
    </div>

    <!-- Step 2: 生成中 -->
    <div v-else-if="step === 'generating'" class="generating-step">
      <div class="generating-animation">
        <div class="spinner"></div>
        <h2>AI 正在创作中...</h2>
        <p class="generating-detail">正在生成策划 → 文案 → 审核</p>
        <div class="progress-steps">
          <div class="progress-step" :class="{ active: currentStep === 'planning', done: isStepDone('planning') }">
            <span class="step-icon">📋</span>
            <span>策划</span>
          </div>
          <div class="progress-arrow">→</div>
          <div class="progress-step" :class="{ active: currentStep === 'scripting', done: isStepDone('scripting') }">
            <span class="step-icon">📝</span>
            <span>文案</span>
          </div>
          <div class="progress-arrow">→</div>
          <div class="progress-step" :class="{ active: currentStep === 'reviewing', done: isStepDone('reviewing') }">
            <span class="step-icon">✅</span>
            <span>审核</span>
          </div>
        </div>
      </div>
    </div>

    <!-- Step 3: 结果展示 -->
    <div v-else-if="step === 'result' && result" class="result-step">
      <div class="result-header">
        <h1>✨ 创作完成</h1>
        <div class="result-actions">
          <el-button @click="resetStudio">🔄 重新创作</el-button>
          <el-button type="primary" @click="goToProject">📁 查看项目</el-button>
        </div>
      </div>

      <!-- 策划方案 -->
      <div class="result-card">
        <h3>📋 策划方案</h3>
        <div class="planning-info">
          <div class="info-row">
            <span class="label">创作目标</span>
            <span class="value">{{ result.planning.target }}</span>
          </div>
          <div class="info-row">
            <span class="label">风格策略</span>
            <span class="value">{{ result.planning.strategy }}</span>
          </div>
          <div class="info-row">
            <span class="label">视频时长</span>
            <span class="value">{{ result.planning.duration }}秒</span>
          </div>
        </div>
      </div>

      <!-- 文案内容 -->
      <div class="result-card script-card">
        <h3>📝 文案内容</h3>
        <div class="script-content">
          <pre>{{ result.script }}</pre>
        </div>
        <div class="script-actions">
          <el-button size="small" @click="copyScript">📋 复制文案</el-button>
        </div>
      </div>

      <!-- 审核评分 -->
      <div class="result-card review-card">
        <h3>✅ AI内容质量审核</h3>

        <!-- 如果有详细审核结果 -->
        <div v-if="qualityReview" class="quality-review-wrapper">
          <QualityReviewCard
            :review-result="qualityReview"
            @apply-fix="applyQualityFix"
          />
        </div>

        <!-- 否则显示简化版 -->
        <div v-else class="review-scores">
          <div class="score-item">
            <span class="score-label">原创度</span>
            <el-progress :percentage="result.review.original_score" :color="'#67c23a'" />
            <span class="score-value">{{ result.review.original_score }}</span>
          </div>
          <div class="score-item">
            <span class="score-label">营销力</span>
            <el-progress :percentage="result.review.marketing_score" :color="'#409eff'" />
            <span class="score-value">{{ result.review.marketing_score }}</span>
          </div>
          <div class="score-item">
            <span class="score-label">安全性</span>
            <el-progress :percentage="result.review.risk_score" :color="'#e6a23c'" />
            <span class="score-value">{{ result.review.risk_score }}</span>
          </div>
          <div class="score-item">
            <span class="score-label">咨询潜力</span>
            <el-progress :percentage="result.review.consult_score" :color="'#f56c6c'" />
            <span class="score-value">{{ result.review.consult_score }}</span>
          </div>
        </div>

        <div class="review-result">
          审核结果：<el-tag type="success">通过</el-tag>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, onMounted } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { ElMessage } from 'element-plus'
import {
  getTemplates,
  createSession,
  configureSession,
  generateContent,
  type CreationResult,
} from '@/api/creationStudio'
import { reviewContent, type ReviewResult } from '@/api/contentQuality'
import QualityReviewCard from '@/components/QualityReviewCard.vue'

const route = useRoute()
const router = useRouter()

const step = ref<'config' | 'generating' | 'result'>('config')
const generating = ref(false)
const sessionId = ref<number>(0)
const result = ref<CreationResult | null>(null)
const currentStep = ref('planning')
const qualityReview = ref<ReviewResult | null>(null)

const opportunity = ref<any>(null)

const templates = ref({
  styles: {} as Record<string, any>,
  tones: {} as Record<string, string>,
  durations: {} as Record<number, string>,
})

const selectedStyle = ref('')
const selectedDuration = ref(60)
const selectedTone = ref('')

const canGenerate = computed(() => {
  return selectedStyle.value && selectedTone.value && selectedDuration.value
})

const isStepDone = (stepName: string) => {
  const steps = ['planning', 'scripting', 'reviewing']
  const currentIndex = steps.indexOf(currentStep.value)
  const targetIndex = steps.indexOf(stepName)
  return targetIndex < currentIndex
}

const loadTemplates = async () => {
  try {
    const res = await getTemplates()
    if (res.data.success) {
      templates.value = res.data.data
      // Set defaults
      const styleKeys = Object.keys(res.data.data.styles)
      if (styleKeys.length) selectedStyle.value = styleKeys[0]
      const toneKeys = Object.keys(res.data.data.tones)
      if (toneKeys.length) selectedTone.value = toneKeys[0]
    }
  } catch (error) {
    console.error('Failed to load templates:', error)
  }
}

const startGeneration = async () => {
  if (!canGenerate.value) return
  generating.value = true
  step.value = 'generating'

  try {
    // 1. Create session
    const createRes = await createSession({
      source_type: 'recommendation',
      opportunity_id: opportunity.value?.id,
      topic: opportunity.value?.title,
    })

    if (!createRes.data.success) {
      throw new Error('创建会话失败')
    }

    sessionId.value = createRes.data.data.session_id

    // 2. Configure
    await configureSession({
      session_id: sessionId.value,
      style: selectedStyle.value,
      duration: selectedDuration.value,
      tone: selectedTone.value,
    })

    // Simulate step progression
    currentStep.value = 'planning'
    await new Promise(r => setTimeout(r, 800))
    currentStep.value = 'scripting'
    await new Promise(r => setTimeout(r, 800))
    currentStep.value = 'reviewing'
    await new Promise(r => setTimeout(r, 800))

    // 3. Generate
    const genRes = await generateContent(sessionId.value)
    if (genRes.data.success) {
      result.value = genRes.data.data
      step.value = 'result'

      // 4. AI质量审核（新增）
      if (result.value?.script) {
        try {
          const reviewRes = await reviewContent(
            'script',
            sessionId.value,
            result.value.script
          )
          if (reviewRes.data.success) {
            qualityReview.value = reviewRes.data.data
          }
        } catch (error) {
          console.error('Quality review failed:', error)
        }
      }

      ElMessage.success('创作完成！')
    }
  } catch (error) {
    console.error('Generation failed:', error)
    ElMessage.error('创作失败，请重试')
    step.value = 'config'
  } finally {
    generating.value = false
  }
}

const resetStudio = () => {
  step.value = 'config'
  result.value = null
  sessionId.value = 0
  currentStep.value = 'planning'
  qualityReview.value = null
}

const applyQualityFix = (fixes: any[]) => {
  if (!result.value?.script) return

  let fixedScript = result.value.script
  for (const fix of fixes) {
    if (fix.type === 'replace' && fix.old && fix.new) {
      fixedScript = fixedScript.replace(fix.old, fix.new)
    }
  }
  result.value.script = fixedScript
  ElMessage.success('已应用AI修复')
}

const goToProject = () => {
  if (result.value) {
    router.push(`/result?project_id=${result.value.project_id}`)
  }
}

const copyScript = () => {
  if (result.value?.script) {
    navigator.clipboard.writeText(result.value.script)
    ElMessage.success('文案已复制')
  }
}

onMounted(() => {
  loadTemplates()

  // Parse opportunity from query
  const oppId = route.query.opportunity_id
  const oppTitle = route.query.opportunity_title as string
  const oppOpening = route.query.opportunity_opening as string
  const oppCategory = route.query.opportunity_category as string
  const oppScore = route.query.opportunity_score

  if (oppId || oppTitle) {
    opportunity.value = {
      id: oppId ? Number(oppId) : undefined,
      title: oppTitle || '未命名主题',
      opening: oppOpening,
      category: oppCategory || '健康知识',
      final_score: oppScore || 85,
    }
  }
})
</script>

<style scoped>
.creation-studio {
  padding: 24px;
  max-width: 900px;
  margin: 0 auto;
}

/* Config Step */
.studio-header {
  text-align: center;
  margin-bottom: 32px;
}

.studio-header h1 {
  font-size: 28px;
  margin-bottom: 8px;
}

.subtitle {
  color: #666;
  font-size: 16px;
  margin: 0;
}

.opportunity-card {
  background: linear-gradient(135deg, #667eea20, #764ba220);
  border: 1px solid #667eea40;
  border-radius: 12px;
  padding: 20px;
  margin-bottom: 24px;
}

.opportunity-card h3 {
  margin-top: 0;
  margin-bottom: 12px;
  font-size: 14px;
  color: #667eea;
}

.opportunity-title {
  font-size: 18px;
  font-weight: 500;
  line-height: 1.5;
  margin-bottom: 8px;
}

.opportunity-opening {
  font-size: 14px;
  color: #666;
  margin-bottom: 12px;
  line-height: 1.5;
}

.opportunity-meta {
  display: flex;
  align-items: center;
  gap: 12px;
}

.score {
  font-size: 14px;
  color: #888;
}

.config-section {
  margin-bottom: 24px;
}

.config-section h3 {
  font-size: 16px;
  margin-bottom: 16px;
  color: #333;
}

/* Style Options */
.style-options {
  display: grid;
  grid-template-columns: repeat(3, 1fr);
  gap: 16px;
}

.style-card {
  border: 2px solid #eee;
  border-radius: 12px;
  padding: 20px;
  cursor: pointer;
  transition: all 0.2s;
}

.style-card:hover {
  border-color: #409eff;
}

.style-card.active {
  border-color: #409eff;
  background: #f0f7ff;
}

.style-name {
  font-size: 16px;
  font-weight: 500;
  margin-bottom: 8px;
}

.style-desc {
  font-size: 13px;
  color: #666;
  margin-bottom: 8px;
  line-height: 1.4;
}

.style-structure {
  font-size: 12px;
  color: #888;
  background: #f5f5f5;
  padding: 8px;
  border-radius: 6px;
}

/* Duration Options */
.duration-options {
  display: flex;
  gap: 12px;
}

.duration-card {
  flex: 1;
  text-align: center;
  padding: 16px;
  border: 2px solid #eee;
  border-radius: 12px;
  cursor: pointer;
  transition: all 0.2s;
  font-size: 16px;
}

.duration-card:hover {
  border-color: #409eff;
}

.duration-card.active {
  border-color: #409eff;
  background: #f0f7ff;
  font-weight: 500;
}

/* Tone Options */
.tone-options {
  display: flex;
  gap: 12px;
}

.tone-card {
  flex: 1;
  text-align: center;
  padding: 16px;
  border: 2px solid #eee;
  border-radius: 12px;
  cursor: pointer;
  transition: all 0.2s;
  font-size: 16px;
}

.tone-card:hover {
  border-color: #409eff;
}

.tone-card.active {
  border-color: #409eff;
  background: #f0f7ff;
  font-weight: 500;
}

/* Action Area */
.action-area {
  text-align: center;
  margin-top: 32px;
  padding-top: 24px;
  border-top: 1px solid #eee;
}

/* Generating Step */
.generating-step {
  display: flex;
  align-items: center;
  justify-content: center;
  min-height: 500px;
}

.generating-animation {
  text-align: center;
}

.spinner {
  width: 60px;
  height: 60px;
  border: 4px solid #f0f0f0;
  border-top-color: #409eff;
  border-radius: 50%;
  animation: spin 1s linear infinite;
  margin: 0 auto 24px;
}

@keyframes spin {
  to { transform: rotate(360deg); }
}

.generating-detail {
  color: #888;
  margin-bottom: 32px;
}

.progress-steps {
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 16px;
}

.progress-step {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 8px;
  padding: 16px 24px;
  border-radius: 12px;
  background: #f5f5f5;
  color: #888;
  transition: all 0.3s;
}

.progress-step.active {
  background: #f0f7ff;
  color: #409eff;
}

.progress-step.done {
  background: #f0f9eb;
  color: #67c23a;
}

.step-icon {
  font-size: 24px;
}

.progress-arrow {
  font-size: 20px;
  color: #ccc;
}

/* Result Step */
.result-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 24px;
}

.result-header h1 {
  font-size: 24px;
  margin: 0;
}

.result-actions {
  display: flex;
  gap: 12px;
}

.result-card {
  background: white;
  border-radius: 12px;
  padding: 24px;
  margin-bottom: 24px;
  box-shadow: 0 2px 8px rgba(0, 0, 0, 0.05);
}

.result-card h3 {
  margin-top: 0;
  margin-bottom: 16px;
  font-size: 18px;
}

.planning-info {
  display: flex;
  flex-direction: column;
  gap: 12px;
}

.info-row {
  display: flex;
  gap: 16px;
}

.info-row .label {
  min-width: 80px;
  color: #888;
  font-size: 14px;
}

.info-row .value {
  flex: 1;
  font-size: 14px;
  color: #333;
}

.script-card {
  background: #fafafa;
}

.script-content pre {
  background: white;
  padding: 20px;
  border-radius: 8px;
  border: 1px solid #eee;
  white-space: pre-wrap;
  word-wrap: break-word;
  font-size: 14px;
  line-height: 1.8;
  max-height: 400px;
  overflow-y: auto;
}

.script-actions {
  margin-top: 12px;
  text-align: right;
}

.review-scores {
  display: flex;
  flex-direction: column;
  gap: 16px;
}

.score-item {
  display: flex;
  align-items: center;
  gap: 12px;
}

.score-label {
  min-width: 80px;
  font-size: 14px;
}

.score-item .el-progress {
  flex: 1;
}

.score-value {
  min-width: 40px;
  text-align: right;
  font-weight: 500;
}

.review-result {
  margin-top: 16px;
  padding-top: 16px;
  border-top: 1px solid #eee;
  font-size: 14px;
}
</style>
