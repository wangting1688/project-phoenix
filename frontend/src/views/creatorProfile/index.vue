<template>
  <div class="creator-profile">
    <div v-if="loading" class="loading">
      <p>加载中...</p>
    </div>

    <div v-else class="profile-container">
      <!-- 头部 -->
      <div class="profile-header">
        <div class="header-content">
          <h1>🧠 AI 主播画像</h1>
          <p class="subtitle">系统对你的账号进行智能分析，生成个性化推荐</p>
        </div>
        <button class="diagnose-btn" @click="runDiagnosis">
          <el-icon><IRefresh /></el-icon>
          重新诊断
        </button>
      </div>

      <!-- 诊断概览 -->
      <div v-if="diagnosis" class="diagnosis-overview card">
        <div class="overview-score">
          <div class="score-circle">
            <span class="score-value">{{ diagnosis.overall_score }}</span>
            <span class="score-label">账号评分</span>
          </div>
        </div>
        <div class="overview-info">
          <div class="info-row">
            <span class="label">账号类型</span>
            <el-tag type="primary">{{ diagnosis.account_type }}</el-tag>
          </div>
          <div class="info-row">
            <span class="label">成长阶段</span>
            <el-tag type="success">{{ diagnosis.growth_stage }}</el-tag>
          </div>
        </div>
      </div>

      <!-- 优势与改进 -->
      <div class="analysis-section">
        <div class="card strengths-card">
          <h3>💪 你的优势</h3>
          <ul>
            <li v-for="(item, index) in diagnosis?.strengths || []" :key="index">
              {{ item }}
            </li>
          </ul>
        </div>
        <div class="card improvements-card">
          <h3>📈 改进建议</h3>
          <ul>
            <li v-for="(item, index) in diagnosis?.improvements || []" :key="index">
              {{ item }}
            </li>
          </ul>
        </div>
      </div>

      <!-- 内容风格 -->
      <div class="card style-section">
        <h3>🎯 内容风格分析</h3>
        <div class="style-grid" v-if="diagnosis">
          <div class="style-item">
            <span class="style-label">主要风格</span>
            <span class="style-value">{{ diagnosis.content_style.primary_style }}</span>
          </div>
          <div class="style-item">
            <span class="style-label">语气调性</span>
            <span class="style-value">{{ diagnosis.content_style.tone }}</span>
          </div>
          <div class="style-item">
            <span class="style-label">语速节奏</span>
            <span class="style-value">{{ diagnosis.content_style.pace }}</span>
          </div>
        </div>
      </div>

      <!-- 分类分布 -->
      <div class="card category-section">
        <h3>📊 内容分类分布</h3>
        <div class="category-bars" v-if="diagnosis">
          <div 
            v-for="(value, key) in diagnosis.category_distribution" 
            :key="key" 
            class="category-bar"
          >
            <span class="category-name">{{ key }}</span>
            <div class="bar-wrapper">
              <div class="bar-fill" :style="{ width: value + '%' }"></div>
            </div>
            <span class="category-value">{{ value }}%</span>
          </div>
        </div>
      </div>

      <!-- 粉丝洞察 -->
      <div class="card audience-section">
        <h3>👥 粉丝画像洞察</h3>
        <div class="audience-grid" v-if="diagnosis">
          <div class="audience-item">
            <span class="audience-label">主力年龄</span>
            <span class="audience-value">{{ diagnosis.audience_insights.primary_age }}</span>
          </div>
          <div class="audience-item">
            <span class="audience-label">性别分布</span>
            <span class="audience-value">{{ diagnosis.audience_insights.primary_gender }}</span>
          </div>
          <div class="audience-item interests">
            <span class="audience-label">兴趣标签</span>
            <div class="tag-list">
              <el-tag 
                v-for="tag in diagnosis.audience_insights.top_interests" 
                :key="tag"
                size="small"
                type="info"
              >
                {{ tag }}
              </el-tag>
            </div>
          </div>
        </div>
      </div>

      <!-- 推荐权重 -->
      <div class="card weights-section">
        <h3>⚖️ 推荐权重配置</h3>
        <p class="section-desc">系统根据你的账号类型自动调整推荐权重</p>
        <div class="weights-grid">
          <div class="weight-item">
            <div class="weight-header">
              <span>🔥 热点指数</span>
              <span class="weight-value">{{ weights.trend }}%</span>
            </div>
            <el-progress :percentage="weights.trend" :color="'#f56c6c'" :show-text="false" />
          </div>
          <div class="weight-item">
            <div class="weight-header">
              <span>💬 咨询潜力</span>
              <span class="weight-value">{{ weights.consult }}%</span>
            </div>
            <el-progress :percentage="weights.consult" :color="'#409eff'" :show-text="false" />
          </div>
          <div class="weight-item">
            <div class="weight-header">
              <span>⭐ 账号匹配</span>
              <span class="weight-value">{{ weights.creator }}%</span>
            </div>
            <el-progress :percentage="weights.creator" :color="'#67c23a'" :show-text="false" />
          </div>
          <div class="weight-item">
            <div class="weight-header">
              <span>✨ 原创度</span>
              <span class="weight-value">{{ weights.original }}%</span>
            </div>
            <el-progress :percentage="weights.original" :color="'#e6a23c'" :show-text="false" />
          </div>
        </div>
        <div class="weight-type">
          当前类型：<el-tag size="small">{{ accountType }}</el-tag>
        </div>
      </div>

      <!-- 优化建议 -->
      <div class="card recommendations-section">
        <h3>💡 AI 优化建议</h3>
        <div class="recommendation-list" v-if="diagnosis">
          <div 
            v-for="(rec, index) in diagnosis.recommendations" 
            :key="index" 
            class="recommendation-item"
          >
            <span class="rec-number">{{ index + 1 }}</span>
            <span class="rec-text">{{ rec }}</span>
          </div>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { ElMessage } from 'element-plus'
import { IRefresh } from '@/utils/icons'
import { 
  getCreatorProfile, 
  diagnoseAccount, 
  type AccountDiagnosis 
} from '@/api/creatorProfile'

const loading = ref(true)
const diagnosis = ref<AccountDiagnosis | null>(null)
const weights = ref({
  trend: 30,
  consult: 35,
  creator: 25,
  original: 10
})
const accountType = ref('咨询型')

const loadProfile = async () => {
  loading.value = true
  try {
    const res = await getCreatorProfile()
    if (res.data.success) {
      if (res.data.data.preference?.score_weights) {
        weights.value = {
          trend: res.data.data.preference.score_weights.trend_weight || 30,
          consult: res.data.data.preference.score_weights.consult_weight || 35,
          creator: res.data.data.preference.score_weights.creator_weight || 25,
          original: res.data.data.preference.score_weights.original_weight || 10,
        }
      }
    }
  } catch (error) {
    console.error('Failed to load profile:', error)
  } finally {
    loading.value = false
  }
}

const runDiagnosis = async () => {
  loading.value = true
  try {
    const res = await diagnoseAccount()
    if (res.data.success) {
      diagnosis.value = res.data.data
      accountType.value = res.data.data.account_type
      ElMessage.success('账号诊断完成！')
    }
  } catch (error) {
    console.error('Diagnosis failed:', error)
    ElMessage.error('诊断失败，请重试')
  } finally {
    loading.value = false
  }
}

onMounted(() => {
  loadProfile()
  runDiagnosis()
})
</script>

<style scoped>
.creator-profile {
  padding: 24px;
  max-width: 1000px;
  margin: 0 auto;
}

.loading {
  text-align: center;
  padding: 60px;
  color: #888;
}

.profile-container {
  display: flex;
  flex-direction: column;
  gap: 24px;
}

.profile-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
}

.profile-header h1 {
  font-size: 28px;
  margin-bottom: 8px;
}

.subtitle {
  color: #666;
  font-size: 14px;
  margin: 0;
}

.diagnose-btn {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 10px 20px;
  background: #409eff;
  color: white;
  border: none;
  border-radius: 8px;
  cursor: pointer;
  font-size: 14px;
}

.diagnose-btn:hover {
  background: #66b1ff;
}

.card {
  background: white;
  border-radius: 12px;
  padding: 24px;
  box-shadow: 0 2px 8px rgba(0, 0, 0, 0.05);
}

.card h3 {
  margin-top: 0;
  margin-bottom: 16px;
  font-size: 18px;
}

.section-desc {
  color: #888;
  font-size: 13px;
  margin: -8px 0 16px 0;
}

/* Overview */
.diagnosis-overview {
  display: flex;
  align-items: center;
  gap: 48px;
}

.overview-score {
  display: flex;
  justify-content: center;
  align-items: center;
}

.score-circle {
  width: 120px;
  height: 120px;
  border-radius: 50%;
  background: linear-gradient(135deg, #667eea, #764ba2);
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  color: white;
}

.score-value {
  font-size: 36px;
  font-weight: bold;
}

.score-label {
  font-size: 12px;
  opacity: 0.9;
}

.overview-info {
  display: flex;
  flex-direction: column;
  gap: 16px;
}

.info-row {
  display: flex;
  align-items: center;
  gap: 16px;
}

.label {
  color: #666;
  min-width: 80px;
}

/* Analysis */
.analysis-section {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 24px;
}

.strengths-card h3 {
  color: #67c23a;
}

.improvements-card h3 {
  color: #e6a23c;
}

.analysis-section ul {
  list-style: none;
  padding: 0;
  margin: 0;
}

.analysis-section li {
  padding: 8px 0;
  border-bottom: 1px solid #f5f5f5;
  font-size: 14px;
  line-height: 1.5;
}

.analysis-section li:last-child {
  border-bottom: none;
}

.strengths-card li::before {
  content: '✓ ';
  color: #67c23a;
  font-weight: bold;
}

.improvements-card li::before {
  content: '→ ';
  color: #e6a23c;
  font-weight: bold;
}

/* Style */
.style-grid {
  display: grid;
  grid-template-columns: repeat(3, 1fr);
  gap: 16px;
}

.style-item {
  padding: 16px;
  background: #f8f9fa;
  border-radius: 8px;
  text-align: center;
}

.style-label {
  display: block;
  font-size: 13px;
  color: #888;
  margin-bottom: 8px;
}

.style-value {
  font-size: 15px;
  font-weight: 500;
  color: #333;
}

/* Category */
.category-bars {
  display: flex;
  flex-direction: column;
  gap: 12px;
}

.category-bar {
  display: flex;
  align-items: center;
  gap: 16px;
}

.category-name {
  min-width: 100px;
  font-size: 14px;
}

.bar-wrapper {
  flex: 1;
  height: 24px;
  background: #f0f0f0;
  border-radius: 12px;
  overflow: hidden;
}

.bar-fill {
  height: 100%;
  background: linear-gradient(90deg, #667eea, #764ba2);
  border-radius: 12px;
  transition: width 0.5s ease;
}

.category-value {
  min-width: 50px;
  text-align: right;
  font-size: 14px;
  font-weight: 500;
}

/* Audience */
.audience-grid {
  display: grid;
  grid-template-columns: repeat(3, 1fr);
  gap: 16px;
}

.audience-item {
  padding: 16px;
  background: #f8f9fa;
  border-radius: 8px;
}

.audience-item.interests {
  grid-column: span 3;
}

.audience-label {
  display: block;
  font-size: 13px;
  color: #888;
  margin-bottom: 8px;
}

.audience-value {
  font-size: 15px;
  font-weight: 500;
  color: #333;
}

.tag-list {
  display: flex;
  gap: 8px;
  flex-wrap: wrap;
}

/* Weights */
.weights-grid {
  display: grid;
  grid-template-columns: repeat(2, 1fr);
  gap: 20px;
  margin-bottom: 16px;
}

.weight-item {
  padding: 16px;
  background: #f8f9fa;
  border-radius: 8px;
}

.weight-header {
  display: flex;
  justify-content: space-between;
  margin-bottom: 8px;
  font-size: 14px;
}

.weight-value {
  font-weight: 600;
}

.weight-type {
  text-align: center;
  font-size: 13px;
  color: #888;
  padding-top: 12px;
  border-top: 1px solid #eee;
}

/* Recommendations */
.recommendation-list {
  display: flex;
  flex-direction: column;
  gap: 12px;
}

.recommendation-item {
  display: flex;
  align-items: flex-start;
  gap: 12px;
  padding: 12px;
  background: #f0f7ff;
  border-radius: 8px;
  border-left: 3px solid #409eff;
}

.rec-number {
  width: 24px;
  height: 24px;
  background: #409eff;
  color: white;
  border-radius: 50%;
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 13px;
  font-weight: 600;
  flex-shrink: 0;
}

.rec-text {
  font-size: 14px;
  line-height: 1.6;
  color: #333;
}
</style>