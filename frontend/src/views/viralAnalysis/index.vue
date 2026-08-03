<template>
  <div class="viral-analysis">
    <!-- Step 1: 输入页 -->
    <div v-if="step === 'input'" class="input-step">
      <div class="page-header">
        <h1>🔍 AI爆款逆向工程</h1>
        <p class="subtitle">输入一个优秀短视频链接，AI帮你分析为什么它成功</p>
      </div>

      <div class="input-card">
        <div class="input-area">
          <el-input
            v-model="videoUrl"
            type="textarea"
            :rows="3"
            placeholder="粘贴快手/抖音/视频号视频链接..."
            @keyup.enter="startAnalysis"
          />
        </div>

        <div class="platform-tips">
          <span class="tip-item">🔸 快手</span>
          <span class="tip-item">🔹 抖音</span>
          <span class="tip-item">🔸 视频号</span>
        </div>

        <div class="manual-section">
          <div class="manual-head" @click="showManual = !showManual">
            <span class="manual-title">
              填写视频真实信息
              <span class="manual-badge" :class="{ on: hasManualInput }">
                {{ hasManualInput ? '已填写' : '必填' }}
              </span>
            </span>
            <span class="manual-toggle">{{ showManual ? '收起' : '展开' }}</span>
          </div>

          <p class="manual-hint">
            平台未开放视频数据接口，需要你照抄视频信息，AI 才能拆解这条视频。<br />
            标题必填；互动数据填得越全，拆解越准。
          </p>

          <div v-show="showManual" class="manual-form">
            <div class="form-row">
              <label>视频标题 <span class="req">*</span></label>
              <el-input v-model="manual.title" placeholder="照抄视频的标题/首句文案" maxlength="200" />
            </div>
            <div class="form-grid">
              <div class="form-row">
                <label>时长(秒)</label>
                <el-input v-model="manual.duration" type="number" placeholder="如 47" />
              </div>
              <div class="form-row">
                <label>点赞数</label>
                <el-input v-model="manual.like_count" type="number" placeholder="如 286000" />
              </div>
              <div class="form-row">
                <label>评论数</label>
                <el-input v-model="manual.comment_count" type="number" placeholder="如 9400" />
              </div>
              <div class="form-row">
                <label>分享数</label>
                <el-input v-model="manual.share_count" type="number" placeholder="如 15200" />
              </div>
              <div class="form-row">
                <label>收藏数</label>
                <el-input v-model="manual.collect_count" type="number" placeholder="如 31000" />
              </div>
            </div>
            <p class="manual-note">数字带「万」的请换算成完整数字，例如 28.6万 填 286000。</p>
          </div>
        </div>

        <div class="action-area">
          <el-button
            type="primary"
            size="large"
            :disabled="!videoUrl.trim() || !manual.title.trim()"
            :loading="analyzing"
            @click="startAnalysis"
          >
            🚀 开始分析
          </el-button>
        </div>

        <div class="process-info">
          <h3>分析流程</h3>
          <div class="process-steps">
            <div class="process-step">
              <span class="step-num">1</span>
              <span class="step-text">链接分析</span>
            </div>
            <div class="process-arrow">→</div>
            <div class="process-step">
              <span class="step-num">2</span>
              <span class="step-text">内容拆解</span>
            </div>
            <div class="process-arrow">→</div>
            <div class="process-step">
              <span class="step-num">3</span>
              <span class="step-text">爆款因素</span>
            </div>
            <div class="process-arrow">→</div>
            <div class="process-step">
              <span class="step-num">4</span>
              <span class="step-text">生成方案</span>
            </div>
          </div>
        </div>
      </div>
    </div>

    <!-- Step 2: 分析中 -->
    <div v-else-if="step === 'analyzing'" class="analyzing-step">
      <div class="analyzing-animation">
        <div class="spinner"></div>
        <h2>AI 正在分析中...</h2>
        <p class="analyzing-detail">{{ analyzingStep }}</p>
        <div class="progress-bar">
          <div class="progress-fill" :style="{ width: progressPercent + '%' }"></div>
        </div>
      </div>
    </div>

    <!-- Step 3: 分析报告页 -->
    <div v-else-if="step === 'result' && analysisResult" class="result-step">
      <div class="result-header">
        <h1>📊 爆款分析报告</h1>
        <el-button @click="goBack" class="back-btn">← 返回</el-button>
      </div>

      <!-- 基础信息 -->
      <div class="result-card basic-info">
        <h3>📋 基础信息</h3>
        <div class="info-grid">
          <div class="info-item">
            <span class="label">平台</span>
            <el-tag>{{ analysisResult.basic_info.platform }}</el-tag>
          </div>
          <div class="info-item">
            <span class="label">标题</span>
            <span class="value">{{ analysisResult.basic_info.title }}</span>
          </div>
          <div class="info-item">
            <span class="label">时长</span>
            <span class="value">{{ analysisResult.basic_info.duration }}秒</span>
          </div>
        </div>
        <div class="stats-row">
          <div class="stat-item">
            <span class="stat-value">{{ formatNumber(analysisResult.basic_info.like_count) }}</span>
            <span class="stat-label">点赞</span>
          </div>
          <div class="stat-item">
            <span class="stat-value">{{ formatNumber(analysisResult.basic_info.comment_count) }}</span>
            <span class="stat-label">评论</span>
          </div>
          <div class="stat-item">
            <span class="stat-value">{{ formatNumber(analysisResult.basic_info.share_count) }}</span>
            <span class="stat-label">转发</span>
          </div>
          <div class="stat-item">
            <span class="stat-value">{{ formatNumber(analysisResult.basic_info.collect_count) }}</span>
            <span class="stat-label">收藏</span>
          </div>
        </div>
      </div>

      <!-- 爆点分析 -->
      <div class="result-card viral-analysis-card">
        <div class="card-header">
          <h3>💥 爆点分析</h3>
          <div class="viral-score">
            <span class="score-value">{{ analysisResult.viral_score }}</span>
            <span class="score-label">爆点指数</span>
          </div>
        </div>
        <div class="viral-points">
          <p>{{ analysisResult.viral_points }}</p>
        </div>
        <div class="hook-info">
          <span class="hook-label">开头类型：</span>
          <el-tag type="primary">{{ analysisResult.hook_type }}</el-tag>
          <p class="hook-text">"{{ analysisResult.hook }}"</p>
        </div>
      </div>

      <!-- 内容结构 -->
      <div class="result-card structure-card">
        <h3>📝 内容结构</h3>
        <div class="structure-grid">
          <div class="structure-item">
            <span class="structure-label">开头</span>
            <span class="structure-value">{{ analysisResult.content_structure.opening }}</span>
          </div>
          <div class="structure-item" v-if="analysisResult.content_structure.middle">
            <span class="structure-label">中段</span>
            <span class="structure-value">{{ analysisResult.content_structure.middle }}</span>
          </div>
          <div class="structure-item" v-if="analysisResult.content_structure.climax">
            <span class="structure-label">高潮</span>
            <span class="structure-value">{{ analysisResult.content_structure.climax }}</span>
          </div>
          <div class="structure-item">
            <span class="structure-label">结尾</span>
            <span class="structure-value">{{ analysisResult.content_structure.ending }}</span>
          </div>
        </div>
      </div>

      <!-- 用户心理分析 -->
      <div class="result-card emotion-card">
        <h3>🧠 用户心理分析</h3>
        <div class="emotion-tags">
          <el-tag 
            v-for="emotion in analysisResult.emotions" 
            :key="emotion"
            type="info"
          >
            {{ emotion }}
          </el-tag>
        </div>
        <div class="pain-point">
          <span class="label">核心痛点</span>
          <p>{{ analysisResult.pain_point }}</p>
        </div>
      </div>

      <!-- 成功因素 -->
      <div class="result-card success-factors-card">
        <h3>✅ 成功因素</h3>
        <ul>
          <li v-for="(factor, index) in analysisResult.success_factors" :key="index">
            ✓ {{ factor }}
          </li>
        </ul>
      </div>

      <!-- 商业适配分析 -->
      <div class="result-card fit-analysis-card">
        <h3>🎯 商业适配分析</h3>
        <div class="fit-grid">
          <div class="fit-item suitable">
            <span class="fit-label">适合</span>
            <div class="fit-tags">
              <el-tag 
                v-for="fit in analysisResult.commercial_fit.fit_for" 
                :key="fit"
                type="success"
                size="small"
              >
                {{ fit }}
              </el-tag>
            </div>
          </div>
          <div class="fit-item not-suitable">
            <span class="fit-label">不适合</span>
            <div class="fit-tags">
              <el-tag 
                v-for="fit in analysisResult.commercial_fit.not_fit_for" 
                :key="fit"
                type="danger"
                size="small"
              >
                {{ fit }}
              </el-tag>
            </div>
          </div>
        </div>
      </div>

      <!-- 主播匹配度 -->
      <div class="result-card match-card">
        <div class="card-header">
          <h3>👤 你的账号匹配度</h3>
          <div class="match-score" :class="{ high: analysisResult.creator_match_score >= 80, medium: analysisResult.creator_match_score >= 60 && analysisResult.creator_match_score < 80 }">
            <span class="score-value">{{ analysisResult.creator_match_score }}</span>
            <span class="score-label">匹配度</span>
          </div>
        </div>
        <div class="match-bar">
          <div class="match-fill" :style="{ width: analysisResult.creator_match_score + '%' }"></div>
        </div>
        <p class="match-desc">
          {{ analysisResult.creator_match_score >= 80 ? '🎉 高度匹配！这个爆款非常适合你！' : analysisResult.creator_match_score >= 60 ? '👍 比较匹配，可以尝试改编' : '⚠️ 匹配度较低，建议谨慎参考' }}
        </p>
      </div>

      <!-- 生成原创版本 -->
      <div class="action-section">
        <el-button
          type="primary"
          size="large"
          :loading="generating"
          @click="generateOpportunity"
        >
          ✨ 生成我的原创版本
        </el-button>
        <p class="action-desc">AI将基于分析结果，为你生成适合你的原创内容机会</p>
      </div>
    </div>

    <!-- Step 4: 生成完成 -->
    <div v-else-if="step === 'opportunity' && opportunityResult" class="opportunity-step">
      <div class="opportunity-header">
        <h1>✨ 原创方案已生成</h1>
      </div>

      <div class="opportunity-card">
        <div class="opportunity-title">{{ opportunityResult.opportunity.title }}</div>
        <div class="opportunity-meta">
          <el-tag>{{ opportunityResult.opportunity.category }}</el-tag>
          <span class="score">综合评分: {{ opportunityResult.opportunity.final_score }}</span>
        </div>
        <div class="opportunity-opening">{{ opportunityResult.opportunity.opening }}</div>
      </div>

      <div class="action-section">
        <el-button
          type="primary"
          size="large"
          @click="goToCreationStudio"
        >
          🎬 进入创作工作台
        </el-button>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, onUnmounted } from 'vue'
import { useRouter } from 'vue-router'
import { ElMessage } from 'element-plus'
import {
  createAnalysis,
  analyzeVideo,
  generateOpportunity as apiGenerateOpportunity,
  type AnalysisResult,
  type OpportunityResult,
  type VideoInfoInput,
} from '@/api/viralAnalysis'

const router = useRouter()

const step = ref<'input' | 'analyzing' | 'result' | 'opportunity'>('input')
const videoUrl = ref('')
const analyzing = ref(false)

const showManual = ref(true)
const timers: number[] = []

function pushTimer(fn: () => void, delay: number) {
  timers.push(window.setTimeout(fn, delay))
}

function clearTimers() {
  while (timers.length) {
    const t = timers.pop()
    if (t) window.clearTimeout(t)
  }
}

onUnmounted(clearTimers)
const manual = ref({
  title: '',
  duration: '',
  like_count: '',
  comment_count: '',
  share_count: '',
  collect_count: '',
})
const hasManualInput = computed(() => manual.value.title.trim().length > 0)

function buildVideoInfo(): VideoInfoInput | undefined {
  const title = manual.value.title.trim()
  if (!title) return undefined
  const toNum = (v: string) => {
    const n = Number(v)
    return v.trim() !== '' && Number.isFinite(n) && n >= 0 ? Math.floor(n) : null
  }
  return {
    title,
    duration: toNum(manual.value.duration),
    like_count: toNum(manual.value.like_count),
    comment_count: toNum(manual.value.comment_count),
    share_count: toNum(manual.value.share_count),
    collect_count: toNum(manual.value.collect_count),
  }
}
const analyzingStep = ref('正在分析链接...')
const progressPercent = ref(0)
const generating = ref(false)

const analysisResult = ref<AnalysisResult | null>(null)
const opportunityResult = ref<OpportunityResult | null>(null)
const sessionId = ref(0)

const formatNumber = (num: number) => {
  if (num >= 10000) {
    return (num / 10000).toFixed(1) + '万'
  }
  return num.toString()
}

const startAnalysis = async () => {
  if (!videoUrl.value.trim()) return
  if (!manual.value.title.trim()) {
    showManual.value = true
    ElMessage.warning('请先填写对标视频的标题，系统不会编造视频数据')
    return
  }
  
  step.value = 'analyzing'
  analyzing.value = true
  progressPercent.value = 0

  try {
    // 1. 创建分析会话
    analyzingStep.value = '正在创建分析任务...'
    progressPercent.value = 10

    const createRes = await createAnalysis(videoUrl.value.trim(), buildVideoInfo())
    if (!createRes) {
      throw new Error('创建分析任务失败')
    }
    sessionId.value = createRes.session_id

    // 2. 执行分析 (真实 AI 调用, 约 30-60s, 期间按阶段推进提示)
    analyzingStep.value = 'AI正在分析视频内容...'
    progressPercent.value = 30
    const analyzePromise = analyzeVideo(sessionId.value)
    pushTimer(() => { analyzingStep.value = '正在拆解内容结构...'; progressPercent.value = 50 }, 5000)
    pushTimer(() => { analyzingStep.value = '正在分析爆点因素...'; progressPercent.value = 70 }, 15000)
    pushTimer(() => { analyzingStep.value = '正在计算匹配度...'; progressPercent.value = 90 }, 30000)
    const analyzeRes = await analyzePromise
    clearTimers()
    if (analyzeRes) {
      analysisResult.value = analyzeRes
      progressPercent.value = 100
      step.value = 'result'
      ElMessage.success('分析完成！')
    }
  } catch (error: any) {
    console.error('Analysis failed:', error)
    ElMessage.error(error?.message || '分析失败，请重试')
    step.value = 'input'
  } finally {
    clearTimers()
    analyzing.value = false
  }
}

const generateOpportunity = async () => {
  generating.value = true
  try {
    const res = await apiGenerateOpportunity(sessionId.value)
    if (res) {
      opportunityResult.value = res
      step.value = 'opportunity'
      ElMessage.success('原创方案已生成！')
    }
  } catch (error) {
    console.error('Generate failed:', error)
    ElMessage.error('生成失败，请重试')
  } finally {
    generating.value = false
  }
}

const goToCreationStudio = () => {
  if (opportunityResult.value) {
    router.push({
      path: '/creation-studio',
      query: {
        opportunity_id: opportunityResult.value.opportunity.id,
        opportunity_title: opportunityResult.value.opportunity.title,
        opportunity_opening: opportunityResult.value.opportunity.opening,
        opportunity_category: opportunityResult.value.opportunity.category,
        opportunity_score: opportunityResult.value.opportunity.final_score,
      }
    })
  }
}

const goBack = () => {
  step.value = 'input'
  videoUrl.value = ''
  analysisResult.value = null
  opportunityResult.value = null
}
</script>

<style scoped>
.viral-analysis {
  padding: 24px;
  max-width: 900px;
  margin: 0 auto;
}

/* Input Step */
.page-header {
  text-align: center;
  margin-bottom: 32px;
}

.page-header h1 {
  font-size: 28px;
  margin-bottom: 8px;
}

.subtitle {
  color: #666;
  font-size: 16px;
  margin: 0;
}

.input-card {
  background: white;
  border-radius: 16px;
  padding: 32px;
  box-shadow: 0 4px 20px rgba(0, 0, 0, 0.08);
}

.input-area {
  margin-bottom: 20px;
}

.input-area textarea {
  font-size: 16px;
}

.platform-tips {
  display: flex;
  gap: 16px;
  margin-bottom: 24px;
}

.tip-item {
  font-size: 14px;
  color: #888;
}

.manual-section {
  border: 1px solid #ebeef5;
  border-radius: 10px;
  padding: 14px 16px;
  margin-bottom: 22px;
  background: #fafbfc;
}

.manual-head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  cursor: pointer;
}

.manual-title {
  font-size: 15px;
  font-weight: 600;
  color: #303133;
  display: flex;
  align-items: center;
  gap: 8px;
}

.manual-badge {
  font-size: 12px;
  font-weight: 400;
  padding: 2px 8px;
  border-radius: 10px;
  background: #fdf6ec;
  color: #e6a23c;
}

.manual-badge.on {
  background: #f0f9eb;
  color: #67c23a;
}

.manual-toggle {
  font-size: 13px;
  color: #909399;
}

.manual-hint {
  font-size: 12px;
  color: #909399;
  line-height: 1.7;
  margin: 8px 0 0;
}

.manual-form {
  margin-top: 14px;
}

.form-row {
  margin-bottom: 12px;
}

.form-row label {
  display: block;
  font-size: 13px;
  color: #606266;
  margin-bottom: 6px;
}

.form-row .req {
  color: #f56c6c;
}

.form-grid {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(140px, 1fr));
  gap: 0 12px;
}

.manual-note {
  font-size: 12px;
  color: #c0c4cc;
  margin: 2px 0 0;
  line-height: 1.6;
}

.action-area {
  text-align: center;
  margin-bottom: 32px;
}

.process-info {
  border-top: 1px solid #eee;
  padding-top: 24px;
}

.process-info h3 {
  font-size: 14px;
  color: #888;
  margin-bottom: 16px;
}

.process-steps {
  display: flex;
  align-items: center;
  justify-content: center;
  flex-wrap: wrap;
}

.process-step {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 8px;
  padding: 12px 20px;
}

.step-num {
  width: 32px;
  height: 32px;
  background: #667eea;
  color: white;
  border-radius: 50%;
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 14px;
  font-weight: 600;
}

.step-text {
  font-size: 13px;
  color: #666;
}

.process-arrow {
  color: #ccc;
  margin: 0 8px;
}

/* Analyzing Step */
.analyzing-step {
  display: flex;
  align-items: center;
  justify-content: center;
  min-height: 500px;
}

.analyzing-animation {
  text-align: center;
}

.spinner {
  width: 60px;
  height: 60px;
  border: 4px solid #f0f0f0;
  border-top-color: #667eea;
  border-radius: 50%;
  animation: spin 1s linear infinite;
  margin: 0 auto 24px;
}

@keyframes spin {
  to { transform: rotate(360deg); }
}

.analyzing-detail {
  color: #888;
  margin-bottom: 24px;
}

.progress-bar {
  width: 300px;
  height: 8px;
  background: #f0f0f0;
  border-radius: 4px;
  margin: 0 auto;
  overflow: hidden;
}

.progress-fill {
  height: 100%;
  background: linear-gradient(90deg, #667eea, #764ba2);
  transition: width 0.5s ease;
}

/* Result Step */
.result-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 24px;
}

.back-btn {
  padding: 8px 16px;
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

.card-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 16px;
}

/* Basic Info */
.info-grid {
  display: grid;
  grid-template-columns: repeat(3, 1fr);
  gap: 16px;
  margin-bottom: 20px;
}

.info-item {
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.info-item .label {
  font-size: 13px;
  color: #888;
}

.info-item .value {
  font-size: 15px;
  color: #333;
}

.stats-row {
  display: flex;
  justify-content: space-around;
  padding-top: 16px;
  border-top: 1px solid #f0f0f0;
}

.stat-item {
  text-align: center;
}

.stat-value {
  display: block;
  font-size: 20px;
  font-weight: 600;
  color: #667eea;
}

.stat-label {
  font-size: 13px;
  color: #888;
}

/* Viral Analysis */
.viral-score {
  text-align: center;
}

.viral-score .score-value {
  display: block;
  font-size: 32px;
  font-weight: bold;
  color: #f56c6c;
}

.viral-score .score-label {
  font-size: 12px;
  color: #888;
}

.viral-points p {
  font-size: 15px;
  line-height: 1.6;
  color: #333;
  background: #fff5f5;
  padding: 12px;
  border-radius: 8px;
  border-left: 3px solid #f56c6c;
}

.hook-info {
  margin-top: 16px;
}

.hook-label {
  font-size: 13px;
  color: #888;
}

.hook-text {
  font-size: 14px;
  color: #333;
  margin-top: 8px;
  font-style: italic;
}

/* Structure */
.structure-grid {
  display: grid;
  grid-template-columns: repeat(2, 1fr);
  gap: 16px;
}

.structure-item {
  padding: 16px;
  background: #f8f9fa;
  border-radius: 8px;
}

.structure-label {
  display: block;
  font-size: 12px;
  color: #888;
  margin-bottom: 8px;
}

.structure-value {
  font-size: 14px;
  font-weight: 500;
  color: #333;
}

/* Emotion */
.emotion-tags {
  display: flex;
  gap: 8px;
  flex-wrap: wrap;
  margin-bottom: 16px;
}

.pain-point {
  background: #f0f7ff;
  padding: 12px;
  border-radius: 8px;
}

.pain-point .label {
  display: block;
  font-size: 13px;
  color: #409eff;
  margin-bottom: 8px;
}

.pain-point p {
  font-size: 14px;
  color: #333;
  margin: 0;
}

/* Success Factors */
.success-factors-card ul {
  list-style: none;
  padding: 0;
  margin: 0;
}

.success-factors-card li {
  padding: 8px 0;
  font-size: 14px;
  color: #333;
  border-bottom: 1px solid #f5f5f5;
}

.success-factors-card li:last-child {
  border-bottom: none;
}

/* Fit Analysis */
.fit-grid {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 16px;
}

.fit-item {
  padding: 16px;
  border-radius: 8px;
}

.fit-item.suitable {
  background: #f0f9eb;
}

.fit-item.not-suitable {
  background: #fef0f0;
}

.fit-label {
  display: block;
  font-size: 13px;
  margin-bottom: 12px;
}

.fit-item.suitable .fit-label {
  color: #67c23a;
}

.fit-item.not-suitable .fit-label {
  color: #f56c6c;
}

.fit-tags {
  display: flex;
  gap: 8px;
  flex-wrap: wrap;
}

/* Match Card */
.match-score {
  text-align: center;
}

.match-score .score-value {
  display: block;
  font-size: 36px;
  font-weight: bold;
}

.match-score.high .score-value {
  color: #67c23a;
}

.match-score.medium .score-value {
  color: #e6a23c;
}

.match-score .score-label {
  font-size: 12px;
  color: #888;
}

.match-bar {
  height: 12px;
  background: #f0f0f0;
  border-radius: 6px;
  margin: 16px 0;
  overflow: hidden;
}

.match-fill {
  height: 100%;
  background: linear-gradient(90deg, #67c23a, #409eff);
  transition: width 0.5s ease;
}

.match-desc {
  font-size: 14px;
  text-align: center;
  color: #666;
}

/* Action Section */
.action-section {
  text-align: center;
  padding: 32px;
  background: linear-gradient(135deg, #667eea10, #764ba210);
  border-radius: 12px;
  margin-top: 32px;
}

.action-section .el-button {
  padding: 14px 40px;
  font-size: 18px;
}

.action-desc {
  margin-top: 12px;
  font-size: 14px;
  color: #888;
}

/* Opportunity Step */
.opportunity-header {
  text-align: center;
  margin-bottom: 24px;
}

.opportunity-card {
  background: white;
  border-radius: 16px;
  padding: 32px;
  box-shadow: 0 4px 20px rgba(0, 0, 0, 0.08);
  text-align: center;
  margin-bottom: 32px;
}

.opportunity-title {
  font-size: 20px;
  font-weight: 500;
  line-height: 1.5;
  margin-bottom: 16px;
}

.opportunity-meta {
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 16px;
  margin-bottom: 16px;
}

.opportunity-meta .score {
  font-size: 14px;
  color: #888;
}

.opportunity-opening {
  font-size: 14px;
  color: #666;
  line-height: 1.5;
}
</style>
