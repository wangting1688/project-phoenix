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
      <!-- 5 步主线: 每步显示真实完成状态 -->
      <div class="pipeline">
        <div class="pipeline-head">
          <h3>创作流水线</h3>
          <span class="pipeline-sub">按顺序走完 5 步，产出一条可发布的视频</span>
        </div>

        <div
          v-for="(s, i) in pipeline"
          :key="s.key"
          class="pipeline-step card"
          :class="{ done: s.done, current: currentStepIndex === i }"
          @click="router.push(s.path)"
        >
          <div class="step-no" :class="{ done: s.done }">
            <el-icon v-if="s.done" :size="16"><ICheck /></el-icon>
            <span v-else>{{ i + 1 }}</span>
          </div>
          <div class="step-body">
            <div class="step-title-row">
              <h4>{{ s.title }}</h4>
              <span class="step-stat" :class="{ ok: s.done }">{{ s.stat }}</span>
            </div>
            <p class="step-desc">{{ s.desc }}</p>
          </div>
          <el-icon :size="18" class="arrow"><IArrowRight /></el-icon>
        </div>
      </div>

      <div class="section">
        <div class="section-header">
          <h3>今日推荐</h3>
          <span class="more" @click="router.push('/content-hub')">查看全部</span>
        </div>

        <div v-if="loadingRec" class="section-tip">加载中...</div>

        <div v-else-if="!recommendations.length" class="section-empty card">
          <p>还没有选题推荐</p>
          <p class="empty-sub">先去「爆款解析」分析同行视频，AI 会在这里给出选题</p>
          <el-button size="small" type="primary" @click="router.push('/viral-analysis')">
            去解析爆款
          </el-button>
        </div>

        <div v-else class="recommend-list">
          <div
            v-for="item in recommendations"
            :key="item.id"
            class="card recommend-item"
            @click="selectRecommend(item)"
          >
            <div class="recommend-level">{{ Math.round(item.final_score) }}</div>
            <div class="recommend-content">
              <h4>{{ item.title }}</h4>
              <p>{{ item.recommend_reason || item.summary }}</p>
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
import { ref, computed, onMounted } from 'vue'
import { useRouter } from 'vue-router'
import {
  IArrowRight,
  IVideoCamera,
  ICheck,
} from '@/utils/icons'
import { useUserStore } from '@/stores/user'
import { getRecommendations, type ContentOpportunity } from '@/api/contentHub'
import { listProjects, type ContentProject } from '@/api/creation'
import { getVoiceProfiles } from '@/api/voiceProfile'
import { getPublishTasks } from '@/api/publishTask'

const router = useRouter()
const userStore = useUserStore()

const recommendations = ref<ContentOpportunity[]>([])
const loadingRec = ref(true)
const recentWorks = ref<ContentProject[]>([])

// 流水线各步真实状态
const opportunityCount = ref(0)
const projectCount = ref(0)
const completedProjectCount = ref(0)
const activeVoiceCount = ref(0)
const publishTaskCount = ref(0)

const pipeline = computed(() => [
  {
    key: 'viral',
    title: '1. 找对标爆款',
    desc: '粘贴同行视频链接并填写真实数据，AI 拆解成功原因',
    path: '/viral-analysis',
    stat: opportunityCount.value ? `已产出 ${opportunityCount.value} 个选题` : '未开始',
    done: opportunityCount.value > 0,
  },
  {
    key: 'topic',
    title: '2. 选题与文案',
    desc: '从 AI 推荐的选题中挑一个，生成口播文案',
    path: '/content-hub',
    stat: projectCount.value ? `已建 ${projectCount.value} 个项目` : '未开始',
    done: projectCount.value > 0,
  },
  {
    key: 'voice',
    title: '3. 我的声音',
    desc: '录一段样本克隆你的音色，用于配音',
    path: '/voice-profile',
    stat: activeVoiceCount.value ? `${activeVoiceCount.value} 个可用音色` : '未克隆',
    done: activeVoiceCount.value > 0,
  },
  {
    key: 'produce',
    title: '4. 生成视频',
    desc: '用真人素材 + 克隆配音 + 字幕合成竖屏成片',
    path: '/video-production',
    stat: completedProjectCount.value ? `${completedProjectCount.value} 条已完成` : '未开始',
    done: completedProjectCount.value > 0,
  },
  {
    key: 'publish',
    title: '5. 发布到平台',
    desc: '绑定平台账号，一键分发并回收数据',
    path: '/publish-center',
    stat: publishTaskCount.value ? `${publishTaskCount.value} 个发布任务` : '未开始',
    done: publishTaskCount.value > 0,
  },
])

// 第一个未完成的步骤即为当前步骤
const currentStepIndex = computed(() => {
  const i = pipeline.value.findIndex((s) => !s.done)
  return i === -1 ? pipeline.value.length - 1 : i
})

onMounted(() => {
  if (!userStore.userInfo) {
    userStore.fetchUserInfo()
  }
  loadRecommendations()
  loadProjects()
  loadPipelineExtras()
})

async function loadRecommendations() {
  loadingRec.value = true
  try {
    const list = (await getRecommendations('E', 20)) || []
    opportunityCount.value = list.length
    recommendations.value = list.slice(0, 3)
  } catch (error) {
    console.error('加载推荐失败:', error)
    recommendations.value = []
  } finally {
    loadingRec.value = false
  }
}

async function loadProjects() {
  try {
    const res = await listProjects(1, 50)
    const items = res?.items || []
    projectCount.value = res?.total ?? items.length
    completedProjectCount.value = items.filter((p) => p.status === 'completed').length
    recentWorks.value = items.slice(0, 4)
  } catch (error) {
    console.error('加载项目失败:', error)
    recentWorks.value = []
  }
}

async function loadPipelineExtras() {
  try {
    const voices = (await getVoiceProfiles()) || []
    activeVoiceCount.value = voices.filter((v) => v.status === 'active').length
  } catch (error) {
    console.error('加载声纹失败:', error)
  }
  try {
    const tasks = await getPublishTasks()
    publishTaskCount.value = tasks?.total || 0
  } catch (error) {
    console.error('加载发布任务失败:', error)
  }
}

function selectRecommend(item: ContentOpportunity) {
  router.push({
    path: '/creation',
    query: { type: 'custom', topic: item.title },
  })
}

function getStatusText(status: string) {
  const map: Record<string, string> = {
    draft: '草稿',
    ready: '待生成',
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

.pipeline {
  margin-bottom: 20px;
}

.pipeline-head {
  margin-bottom: 12px;
}

.pipeline-head h3 {
  font-size: 17px;
  color: #303133;
  margin: 0 0 4px;
}

.pipeline-sub {
  font-size: 13px;
  color: #909399;
}

.pipeline-step {
  display: flex;
  align-items: center;
  margin-bottom: 10px;
  cursor: pointer;
  transition: transform 0.2s;
  border-left: 3px solid transparent;
}

.pipeline-step:active {
  transform: scale(0.99);
}

.pipeline-step.current {
  border-left-color: #667eea;
  background: linear-gradient(135deg, #f5f7ff, #fff);
}

.step-no {
  width: 32px;
  height: 32px;
  border-radius: 50%;
  display: flex;
  align-items: center;
  justify-content: center;
  margin-right: 14px;
  flex-shrink: 0;
  font-size: 14px;
  font-weight: 600;
  background: #f0f2f5;
  color: #909399;
}

.step-no.done {
  background: #67c23a;
  color: #fff;
}

.step-body {
  flex: 1;
  min-width: 0;
}

.step-title-row {
  display: flex;
  align-items: center;
  gap: 8px;
  margin-bottom: 3px;
}

.step-title-row h4 {
  font-size: 15px;
  color: #303133;
  margin: 0;
}

.step-stat {
  font-size: 12px;
  padding: 1px 7px;
  border-radius: 9px;
  background: #f4f4f5;
  color: #909399;
  white-space: nowrap;
}

.step-stat.ok {
  background: #f0f9eb;
  color: #67c23a;
}

.step-desc {
  font-size: 12px;
  color: #909399;
  margin: 0;
  line-height: 1.5;
}

.section-tip {
  padding: 18px;
  text-align: center;
  color: #909399;
  font-size: 13px;
}

.section-empty {
  padding: 22px;
  text-align: center;
}

.section-empty p {
  margin: 0 0 6px;
  font-size: 14px;
  color: #606266;
}

.section-empty .empty-sub {
  font-size: 12px;
  color: #909399;
  margin-bottom: 12px;
  line-height: 1.6;
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
  min-width: 38px;
  height: 30px;
  padding: 0 7px;
  border-radius: 15px;
  display: flex;
  align-items: center;
  justify-content: center;
  font-weight: bold;
  font-size: 14px;
  margin-right: 12px;
  flex-shrink: 0;
  background: linear-gradient(135deg, #667eea, #764ba2);
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
