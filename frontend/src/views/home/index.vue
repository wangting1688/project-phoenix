<template>
  <div class="home-page">
    <div class="page-header">
      <div class="header-content">
        <div class="greeting">
          <h2>你好，{{ userStore.userInfo?.nickname || '主播' }} 👋</h2>
          <p>今天想创作什么内容？</p>
        </div>
        <div class="avatar">
          <el-avatar :size="48" src="">
            {{ userStore.userInfo?.nickname?.charAt(0) || '主' }}
          </el-avatar>
        </div>
      </div>
    </div>

    <div class="page-container">
      <div class="quick-actions">
        <div class="card action-card" @click="goToCreation('recommend')">
          <div class="action-icon recommend">
            <el-icon :size="32"><IFire /></el-icon>
          </div>
          <div class="action-info">
            <h3>AI推荐内容</h3>
            <p>根据热点和你的喜好推荐</p>
          </div>
          <el-icon :size="20" class="arrow"><IArrowRight /></el-icon>
        </div>

        <div class="card action-card" @click="goToCreation('viral_analysis')">
          <div class="action-icon viral">
            <el-icon :size="32"><IVideoPlay /></el-icon>
          </div>
          <div class="action-info">
            <h3>爆款视频解析</h3>
            <p>复制链接生成原创方案</p>
          </div>
          <el-icon :size="20" class="arrow"><IArrowRight /></el-icon>
        </div>

        <div class="card action-card" @click="goToCreation('custom')">
          <div class="action-icon custom">
            <el-icon :size="32"><IEdit /></el-icon>
          </div>
          <div class="action-info">
            <h3>自定义主题</h3>
            <p>输入你想创作的主题</p>
          </div>
          <el-icon :size="20" class="arrow"><IArrowRight /></el-icon>
        </div>
      </div>

      <div class="section">
        <div class="section-header">
          <h3>今日推荐</h3>
          <span class="more" @click="goToCreation('recommend')">查看全部</span>
        </div>

        <div class="recommend-list">
          <div
            v-for="(item, index) in recommendations"
            :key="index"
            class="card recommend-item"
            @click="selectRecommend(item)"
          >
            <div class="recommend-level" :class="'level-' + item.level">
              {{ item.level }}
            </div>
            <div class="recommend-content">
              <h4>{{ item.title }}</h4>
              <p>{{ item.reason }}</p>
            </div>
            <el-button type="primary" size="small" class="recommend-btn">
              立即创作
            </el-button>
          </div>
        </div>
      </div>

      <div class="section">
        <div class="section-header">
          <h3>最近作品</h3>
          <span class="more" @click="$router.push('/works')">全部作品</span>
        </div>

        <div v-if="recentWorks.length > 0" class="works-grid">
          <div
            v-for="work in recentWorks"
            :key="work.id"
            class="card work-item"
          >
            <div class="work-cover">
              <el-icon :size="40"><IVideoCamera /></el-icon>
            </div>
            <div class="work-info">
              <p class="work-title">{{ work.topic }}</p>
              <p class="work-status">{{ getStatusText(work.status) }}</p>
            </div>
          </div>
        </div>
        <div v-else class="empty-state">
          <el-empty description="还没有作品，开始创作吧！" />
        </div>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { useRouter } from 'vue-router'
import {
  IFire,
  IVideoPlay,
  IEdit,
  IArrowRight,
  IVideoCamera,
} from '@element-plus/icons-vue'
import { useUserStore } from '@/stores/user'

const router = useRouter()
const userStore = useUserStore()

const recommendations = ref([
  {
    level: 'A',
    title: '睡眠成为近期热门话题',
    reason: '45岁女性对睡眠质量的关注增长明显',
    topic: '睡眠不好怎么办',
  },
  {
    level: 'B',
    title: '肠道健康咨询潜力高',
    reason: '最近肠道健康相关内容转化率提升',
    topic: '肠胃不好怎么调理',
  },
])

const recentWorks = ref<Array<{ id: number; topic: string; status: string }>>([])

onMounted(() => {
  if (!userStore.userInfo) {
    userStore.fetchUserInfo()
  }
  loadRecentWorks()
})

function loadRecentWorks() {
}

function goToCreation(type: string) {
  router.push({ path: '/creation', query: { type } })
}

function selectRecommend(item: { topic: string }) {
  router.push({
    path: '/creation',
    query: { type: 'recommend', topic: item.topic },
  })
}

function getStatusText(status: string) {
  const map: Record<string, string> = {
    draft: '草稿',
    processing: '生成中',
    completed: '已完成',
    failed: '失败',
  }
  return map[status] || status
}
</script>

<style scoped>
.home-page {
  min-height: 100vh;
  background: #f5f7fa;
}

.page-header {
  background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
  padding: 40px 20px 60px;
  color: #fff;
}

.header-content {
  max-width: 768px;
  margin: 0 auto;
  display: flex;
  justify-content: space-between;
  align-items: center;
}

.greeting h2 {
  font-size: 24px;
  margin-bottom: 8px;
}

.greeting p {
  font-size: 14px;
  opacity: 0.9;
}

.page-container {
  padding: 0 16px;
  max-width: 768px;
  margin: -40px auto 0;
}

.quick-actions {
  margin-bottom: 20px;
}

.action-card {
  display: flex;
  align-items: center;
  margin-bottom: 12px;
  cursor: pointer;
  transition: transform 0.2s;
}

.action-card:active {
  transform: scale(0.98);
}

.action-icon {
  width: 56px;
  height: 56px;
  border-radius: 12px;
  display: flex;
  align-items: center;
  justify-content: center;
  margin-right: 16px;
  color: #fff;
}

.action-icon.recommend {
  background: linear-gradient(135deg, #ff6b6b, #feca57);
}

.action-icon.viral {
  background: linear-gradient(135deg, #5f27cd, #341f97);
}

.action-icon.custom {
  background: linear-gradient(135deg, #00d2d3, #01a3a4);
}

.action-info {
  flex: 1;
}

.action-info h3 {
  font-size: 16px;
  margin-bottom: 4px;
  color: #303133;
}

.action-info p {
  font-size: 13px;
  color: #909399;
}

.arrow {
  color: #c0c4cc;
}

.section {
  margin-bottom: 20px;
}

.section-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 12px;
  padding: 0 4px;
}

.section-header h3 {
  font-size: 18px;
  color: #303133;
}

.more {
  font-size: 14px;
  color: #667eea;
  cursor: pointer;
}

.recommend-item {
  display: flex;
  align-items: center;
  margin-bottom: 12px;
  cursor: pointer;
}

.recommend-level {
  width: 36px;
  height: 36px;
  border-radius: 50%;
  display: flex;
  align-items: center;
  justify-content: center;
  font-weight: bold;
  font-size: 16px;
  margin-right: 12px;
  flex-shrink: 0;
}

.level-A {
  background: linear-gradient(135deg, #ff6b6b, #feca57);
  color: #fff;
}

.level-B {
  background: linear-gradient(135deg, #5f27cd, #a29bfe);
  color: #fff;
}

.level-C {
  background: linear-gradient(135deg, #00d2d3, #54a0ff);
  color: #fff;
}

.level-D {
  background: linear-gradient(135deg, #feca57, #ff9f43);
  color: #fff;
}

.level-E {
  background: linear-gradient(135deg, #55efc4, #00b894);
  color: #fff;
}

.recommend-content {
  flex: 1;
}

.recommend-content h4 {
  font-size: 15px;
  margin-bottom: 4px;
  color: #303133;
}

.recommend-content p {
  font-size: 12px;
  color: #909399;
  line-height: 1.4;
}

.recommend-btn {
  flex-shrink: 0;
}

.works-grid {
  display: grid;
  grid-template-columns: repeat(2, 1fr);
  gap: 12px;
}

.work-item {
  padding: 0;
  overflow: hidden;
}

.work-cover {
  width: 100%;
  aspect-ratio: 9 / 16;
  background: linear-gradient(135deg, #667eea20, #764ba220);
  display: flex;
  align-items: center;
  justify-content: center;
  color: #667eea;
}

.work-info {
  padding: 12px;
}

.work-title {
  font-size: 14px;
  color: #303133;
  margin-bottom: 4px;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.work-status {
  font-size: 12px;
  color: #67c23a;
}

.empty-state {
  background: #fff;
  border-radius: 12px;
  padding: 40px 20px;
}
</style>
