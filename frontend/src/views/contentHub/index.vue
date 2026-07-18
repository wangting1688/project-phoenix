<template>
  <div class="content-hub">
    <div class="hub-header">
      <h1>☀️ 今天适合创作什么？</h1>
      <p class="subtitle">AI 已根据你的账号推荐以下内容</p>
    </div>

    <div v-if="loading" class="loading">
      <p>AI 正在为你生成推荐...</p>
    </div>

    <div v-else class="categories">
      <div v-for="(category, key) in recommendations" :key="key" class="category-section">
        <div class="category-header">
          <h2>{{ category.title }}</h2>
          <p class="category-desc">{{ category.description }}</p>
          <button class="refresh-btn" @click="handleRefresh(key as string)">换一批</button>
        </div>

        <div class="opportunities-list">
          <div 
            v-for="item in category.items" 
            :key="item.id" 
            class="opportunity-card"
            @click="showDetail(item)"
          >
            <div class="opportunity-title">{{ item.title }}</div>
            <div class="opportunity-opening" v-if="item.opening">{{ item.opening }}</div>
            
            <div class="scores">
              <div class="score-item">
                <span class="score-label">咨询指数</span>
                <span class="score-value">{{ item.consult_score }}</span>
              </div>
              <div class="score-item">
                <span class="score-label">综合评分</span>
                <span class="score-value final">{{ item.final_score }}</span>
              </div>
              <div class="score-stars">
                <span v-for="i in 5" :key="i" :class="['star', { active: i <= Math.round(item.final_score / 20) }]">⭐</span>
              </div>
            </div>

            <div class="category-tag">{{ item.category }}</div>
            <button class="create-btn" @click.stop="goToStudio(item)">立即创作</button>
          </div>
        </div>
      </div>
    </div>

    <!-- Detail Modal -->
    <div v-if="selectedOpportunity" class="modal-overlay" @click="closeDetail">
      <div class="modal-content" @click.stop>
        <button class="modal-close" @click="closeDetail">×</button>
        
        <h2>{{ selectedOpportunity.title }}</h2>
        
        <div class="detail-section">
          <h3>推荐原因</h3>
          <div class="reason-box">
            <p v-if="selectedOpportunity.recommend_reason">{{ selectedOpportunity.recommend_reason }}</p>
            <p v-else>AI 根据您的账号特征和当前热点综合推荐此内容。</p>
          </div>
        </div>

        <div class="detail-scores">
          <div class="score-detail">
            <span>热点指数</span>
            <span>{{ selectedOpportunity.trend_score }}</span>
          </div>
          <div class="score-detail">
            <span>咨询潜力</span>
            <span>{{ selectedOpportunity.consult_score }}</span>
          </div>
          <div class="score-detail">
            <span>账号匹配</span>
            <span>{{ selectedOpportunity.creator_match }}</span>
          </div>
          <div class="score-detail">
            <span>原创度</span>
            <span>{{ selectedOpportunity.original_score }}</span>
          </div>
        </div>

        <div class="detail-section" v-if="selectedOpportunity.pain_point">
          <h3>痛点分析</h3>
          <p>{{ selectedOpportunity.pain_point }}</p>
        </div>

        <button class="start-create-btn" @click="startCreating">开始创作</button>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { useRouter } from 'vue-router'
import { getTodayRecommendations, refreshRecommendations, type ContentOpportunity, type OpportunityDetail, type CategoryData } from '@/api/contentHub'

const router = useRouter()
const loading = ref(true)
const recommendations = ref<Record<string, CategoryData>>({})
const selectedOpportunity = ref<OpportunityDetail | null>(null)

const loadRecommendations = async () => {
  loading.value = true
  try {
    const res = await getTodayRecommendations()
    if (res.data.success) {
      recommendations.value = res.data.data
    }
  } catch (error) {
    console.error('Failed to load recommendations:', error)
  } finally {
    loading.value = false
  }
}

const handleRefresh = async (category: string) => {
  try {
    const res = await refreshRecommendations(category)
    if (res.data.success && recommendations.value[category]) {
      recommendations.value[category].items = res.data.data
    }
  } catch (error) {
    console.error('Failed to refresh:', error)
  }
}

const showDetail = (item: ContentOpportunity) => {
  selectedOpportunity.value = item as OpportunityDetail
}

const closeDetail = () => {
  selectedOpportunity.value = null
}

const goToStudio = (item: ContentOpportunity) => {
  router.push({
    path: '/creation-studio',
    query: {
      opportunity_id: item.id,
      opportunity_title: item.title,
      opportunity_opening: item.opening,
      opportunity_category: item.category,
      opportunity_score: item.final_score,
    }
  })
}

const startCreating = () => {
  if (selectedOpportunity.value) {
    goToStudio(selectedOpportunity.value)
  }
}

onMounted(() => {
  loadRecommendations()
})
</script>

<style scoped>
.content-hub {
  padding: 24px;
  max-width: 1200px;
  margin: 0 auto;
}

.hub-header {
  text-align: center;
  margin-bottom: 32px;
}

.hub-header h1 {
  font-size: 28px;
  margin-bottom: 8px;
}

.subtitle {
  color: #666;
  font-size: 16px;
}

.loading {
  text-align: center;
  padding: 60px;
  color: #888;
}

.categories {
  display: flex;
  flex-direction: column;
  gap: 32px;
}

.category-section {
  background: #fff;
  border-radius: 12px;
  padding: 24px;
  box-shadow: 0 2px 8px rgba(0, 0, 0, 0.05);
}

.category-header {
  display: flex;
  align-items: center;
  gap: 16px;
  margin-bottom: 16px;
}

.category-header h2 {
  font-size: 20px;
  margin: 0;
}

.category-desc {
  color: #888;
  font-size: 14px;
  margin: 0;
  flex: 1;
}

.refresh-btn {
  padding: 8px 16px;
  background: #f5f5f5;
  border: none;
  border-radius: 6px;
  cursor: pointer;
  font-size: 14px;
}

.refresh-btn:hover {
  background: #e8e8e8;
}

.opportunities-list {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(280px, 1fr));
  gap: 16px;
}

.opportunity-card {
  border: 1px solid #eee;
  border-radius: 8px;
  padding: 16px;
  cursor: pointer;
  transition: all 0.2s;
}

.opportunity-card:hover {
  border-color: #4a90d9;
  box-shadow: 0 4px 12px rgba(74, 144, 217, 0.15);
}

.opportunity-title {
  font-size: 15px;
  font-weight: 500;
  line-height: 1.5;
  margin-bottom: 12px;
  color: #333;
}

.opportunity-opening {
  font-size: 13px;
  color: #666;
  line-height: 1.4;
  margin-bottom: 12px;
  display: -webkit-box;
  -webkit-line-clamp: 2;
  -webkit-box-orient: vertical;
  overflow: hidden;
}

.scores {
  display: flex;
  align-items: center;
  gap: 12px;
  margin-bottom: 12px;
  flex-wrap: wrap;
}

.score-item {
  display: flex;
  align-items: center;
  gap: 4px;
}

.score-label {
  font-size: 12px;
  color: #888;
}

.score-value {
  font-size: 14px;
  font-weight: 600;
  color: #333;
}

.score-value.final {
  color: #4a90d9;
}

.score-stars {
  margin-left: auto;
}

.star {
  font-size: 12px;
  opacity: 0.3;
}

.star.active {
  opacity: 1;
}

.category-tag {
  display: inline-block;
  padding: 4px 8px;
  background: #f0f7ff;
  color: #4a90d9;
  font-size: 12px;
  border-radius: 4px;
  margin-bottom: 12px;
}

.create-btn {
  width: 100%;
  padding: 10px;
  background: #4a90d9;
  color: white;
  border: none;
  border-radius: 6px;
  cursor: pointer;
  font-size: 14px;
}

.create-btn:hover {
  background: #3a7bc8;
}

/* Modal Styles */
.modal-overlay {
  position: fixed;
  top: 0;
  left: 0;
  right: 0;
  bottom: 0;
  background: rgba(0, 0, 0, 0.5);
  display: flex;
  align-items: center;
  justify-content: center;
  z-index: 1000;
}

.modal-content {
  background: white;
  border-radius: 12px;
  padding: 32px;
  max-width: 600px;
  width: 90%;
  max-height: 80vh;
  overflow-y: auto;
  position: relative;
}

.modal-close {
  position: absolute;
  top: 16px;
  right: 16px;
  background: none;
  border: none;
  font-size: 24px;
  cursor: pointer;
  color: #888;
}

.modal-content h2 {
  font-size: 20px;
  margin-bottom: 24px;
  line-height: 1.5;
}

.detail-section {
  margin-bottom: 24px;
}

.detail-section h3 {
  font-size: 16px;
  margin-bottom: 12px;
  color: #333;
}

.reason-box {
  background: #f5f8ff;
  padding: 16px;
  border-radius: 8px;
  border-left: 3px solid #4a90d9;
}

.reason-box p {
  margin: 0;
  font-size: 14px;
  line-height: 1.6;
  color: #555;
}

.detail-scores {
  display: grid;
  grid-template-columns: repeat(2, 1fr);
  gap: 12px;
  margin-bottom: 24px;
}

.score-detail {
  display: flex;
  justify-content: space-between;
  padding: 12px;
  background: #f9f9f9;
  border-radius: 6px;
  font-size: 14px;
}

.start-create-btn {
  width: 100%;
  padding: 14px;
  background: #4a90d9;
  color: white;
  border: none;
  border-radius: 8px;
  font-size: 16px;
  cursor: pointer;
}

.start-create-btn:hover {
  background: #3a7bc8;
}
</style>