<template>
  <div class="result-page">
    <div class="page-header">
      <h2>创作结果</h2>
      <p>{{ project?.topic || 'AI生成的内容' }}</p>
    </div>

    <div class="page-container">
      <!-- 进度展示 -->
      <div v-if="!completed" class="progress-card card">
        <div class="progress-header">
          <el-icon class="loading-icon" :size="24"><ILoading /></el-icon>
          <span>AI正在创作中...</span>
        </div>
        <el-progress :percentage="taskProgress" :color="progressColor" />
        <div class="step-list">
          <div
            v-for="step in workflowSteps"
            :key="step.key"
            class="step-item"
            :class="getStepStatus(step.key)"
          >
            <el-icon :size="16">
              <component :is="getStepIcon(step.key)" />
            </el-icon>
            <span>{{ step.label }}</span>
          </div>
        </div>
      </div>

      <!-- 文案展示 -->
      <div v-if="scripts.length > 0" class="section">
        <div class="section-header">
          <h3>AI文案（{{ scripts.length }}个版本）</h3>
        </div>

        <div class="script-tabs">
          <div
            v-for="(s, i) in scripts"
            :key="s.id"
            class="script-tab"
            :class="{ active: activeScript === i }"
            @click="activeScript = i"
          >
            {{ getTypeName(s.type) }}
          </div>
        </div>

        <div v-if="scripts[activeScript]" class="script-card card">
          <div class="script-meta">
            <span class="score">评分: {{ scripts[activeScript].score }}</span>
          </div>
          <div class="script-content">{{ scripts[activeScript].content }}</div>
          <div class="script-actions">
            <el-button size="small" @click="copyScript(scripts[activeScript].content)">
              <el-icon><ICopyDocument /></el-icon> 复制
            </el-button>
            <el-button size="small" type="primary" @click="goGenerateVideo">
              生成视频
            </el-button>
          </div>
        </div>
      </div>

      <!-- 视频展示 -->
      <div v-if="video" class="section">
        <div class="section-header">
          <h3>视频</h3>
        </div>
        <div class="video-card card">
          <div class="video-preview">
            <el-icon :size="48"><IVideoCamera /></el-icon>
            <span>视频已生成</span>
          </div>
          <div class="video-actions">
            <el-button type="primary" @click="downloadVideo">下载视频</el-button>
            <el-button @click="goPublish">发布方案</el-button>
          </div>
        </div>
      </div>

      <!-- 运营方案 -->
      <div v-if="completed" class="section">
        <div class="section-header">
          <h3>运营方案</h3>
        </div>
        <div class="operation-card card">
          <div class="op-section">
            <h4>推荐标题</h4>
            <div v-for="(t, i) in operationData.titles" :key="i" class="op-item">
              {{ t }}
            </div>
          </div>
          <div class="op-section">
            <h4>推荐标签</h4>
            <div class="hashtag-list">
              <span v-for="(h, i) in operationData.hashtags" :key="i" class="hashtag">{{ h }}</span>
            </div>
          </div>
          <div class="op-section">
            <h4>引导评论</h4>
            <div v-for="(c, i) in operationData.comment_strategy" :key="i" class="op-item">
              {{ c }}
            </div>
          </div>
          <div class="op-section">
            <h4>私信引导</h4>
            <div class="op-item highlight">{{ operationData.private_message_guide }}</div>
          </div>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, onMounted, onUnmounted } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { ElMessage } from 'element-plus'
import {
  ILoading, ICopyDocument, IVideoCamera,
  ICheck, IDocument, IVideoPlay, ISetting,
} from '@element-plus/icons-vue'
import {
  getTaskStatus, getTaskResult, getTaskScripts,
  type TaskStatus, type Script, type VideoInfo,
} from '@/api/creation'

const route = useRoute()
const router = useRouter()

const taskId = Number(route.query.task_id)
const taskStatus = ref<TaskStatus | null>(null)
const scripts = ref<Script[]>([])
const video = ref<VideoInfo | null>(null)
const activeScript = ref(0)
const operationData = ref<any>({
  titles: [], hashtags: [], comment_strategy: [], private_message_guide: '',
})

let pollTimer: number | null = null

const workflowSteps = [
  { key: 'analyzing', label: '内容分析', icon: IDocument },
  { key: 'planning', label: '内容策划', icon: ISetting },
  { key: 'scripting', label: '文案生成', icon: IDocument },
  { key: 'reviewing', label: '合规审核', icon: ICheck },
  { key: 'generating_video', label: '视频生成', icon: IVideoPlay },
  { key: 'optimizing', label: '运营优化', icon: ISetting },
  { key: 'completed', label: '完成', icon: ICheck },
]

const taskProgress = computed(() => taskStatus.value?.progress || 0)
const completed = computed(() => taskStatus.value?.status === 'completed')
const progressColor = computed(() => {
  if (completed.value) return '#67c23a'
  return '#667eea'
})

onMounted(() => {
  if (taskId) {
    pollStatus()
  }
})

onUnmounted(() => {
  if (pollTimer) clearInterval(pollTimer)
})

async function pollStatus() {
  try {
    const status = await getTaskStatus(taskId)
    taskStatus.value = status as any

    const result = await getTaskResult(taskId)
    if (result) {
      scripts.value = (result as any).scripts || []
      video.value = (result as any).video || null
    }

    if (status?.status === 'completed') {
      loadOperationData()
      return
    }

    pollTimer = window.setTimeout(pollStatus, 2000)
  } catch (e) {
    console.error('轮询失败', e)
  }
}

async function loadOperationData() {
  // 这里可以从task的result字段中获取运营方案
  // V1暂时用默认数据
  operationData.value = {
    titles: [
      `${route.query.topic || '健康'}不好？这几个方法一定要试试`,
      '45岁后，这个问题怎么解决？',
      '别再发愁了，这样做效果最好',
    ],
    hashtags: ['健康生活', '女性健康', '养生', '中年女性', '健康知识', '生活方式', '自我提升', '正能量'],
    comment_strategy: [
      '你们有没有类似的困扰？',
      '欢迎在评论区分享你的经验',
      '觉得有用的话记得点赞收藏',
    ],
    private_message_guide: '如果你也有类似困扰，可以私信我交流一下',
  }
}

function getStepStatus(stepKey: string) {
  if (!taskStatus.value) return ''
  const current = taskStatus.value.current_step || ''
  const stepIndex = workflowSteps.findIndex(s => s.key === stepKey)
  const currentIndex = workflowSteps.findIndex(s => s.key === current)

  if (completed.value || stepIndex < currentIndex) return 'done'
  if (stepIndex === currentIndex) return 'active'
  return 'pending'
}

function getStepIcon(stepKey: string) {
  const step = workflowSteps.find(s => s.key === stepKey)
  return step?.icon || IDocument
}

function getTypeName(type: string) {
  const map: Record<string, string> = {
    story: '故事型', knowledge: '知识型', chat: '聊天型',
  }
  return map[type] || type
}

function copyScript(content: string) {
  navigator.clipboard.writeText(content).then(() => {
    ElMessage.success('已复制到剪贴板')
  }).catch(() => {
    ElMessage.error('复制失败')
  })
}

function goGenerateVideo() {
  ElMessage.info('视频生成功能开发中')
}

function downloadVideo() {
  ElMessage.info('视频下载功能开发中')
}

function goPublish() {
  ElMessage.info('发布功能开发中')
}
</script>

<style scoped>
.result-page { min-height: 100vh; background: #f5f7fa; }

.page-header {
  background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
  padding: 40px 20px 50px; color: #fff; text-align: center;
}
.page-header h2 { font-size: 24px; margin-bottom: 8px; }
.page-header p { font-size: 14px; opacity: 0.9; }

.page-container { padding: 0 16px; max-width: 768px; margin: -30px auto 0; }

.progress-card { margin-bottom: 16px; }
.progress-header {
  display: flex; align-items: center; gap: 8px;
  margin-bottom: 16px; font-size: 16px; color: #303133;
}
.loading-icon { animation: spin 1s linear infinite; color: #667eea; }
@keyframes spin { from { transform: rotate(0deg); } to { transform: rotate(360deg); } }

.step-list {
  display: flex; flex-wrap: wrap; gap: 12px; margin-top: 16px;
}
.step-item {
  display: flex; align-items: center; gap: 6px;
  font-size: 13px; color: #c0c4cc; padding: 6px 12px;
  background: #f5f7fa; border-radius: 16px;
}
.step-item.active { color: #667eea; background: #ecf5ff; }
.step-item.done { color: #67c23a; background: #f0f9eb; }

.section { margin-bottom: 20px; }
.section-header {
  display: flex; justify-content: space-between; align-items: center;
  margin-bottom: 12px; padding: 0 4px;
}
.section-header h3 { font-size: 18px; color: #303133; }

.script-tabs {
  display: flex; gap: 8px; margin-bottom: 12px;
}
.script-tab {
  flex: 1; text-align: center; padding: 10px;
  background: #fff; border-radius: 8px; font-size: 14px;
  cursor: pointer; color: #606266; border: 2px solid transparent;
  box-shadow: 0 2px 8px rgba(0,0,0,0.06);
  transition: all 0.2s;
}
.script-tab.active {
  border-color: #667eea; color: #667eea;
  box-shadow: 0 4px 16px rgba(102,126,234,0.2);
}

.script-card { padding: 20px; }
.script-meta { margin-bottom: 12px; }
.score {
  background: #f0f9eb; color: #67c23a; font-size: 13px;
  padding: 2px 10px; border-radius: 10px;
}
.script-content {
  font-size: 15px; line-height: 1.8; color: #303133;
  white-space: pre-wrap; margin-bottom: 16px;
}
.script-actions { display: flex; gap: 10px; }

.video-card { text-align: center; padding: 30px; }
.video-preview {
  aspect-ratio: 9/16; max-width: 250px; margin: 0 auto 20px;
  background: linear-gradient(135deg, #667eea20, #764ba220);
  display: flex; flex-direction: column; align-items: center; justify-content: center;
  color: #667eea; border-radius: 12px;
}
.video-actions { display: flex; gap: 10px; justify-content: center; }

.operation-card { padding: 20px; }
.op-section { margin-bottom: 16px; }
.op-section h4 { font-size: 15px; margin-bottom: 8px; color: #303133; }
.op-item {
  font-size: 14px; color: #606266; padding: 8px 12px;
  background: #f5f7fa; border-radius: 8px; margin-bottom: 6px;
}
.op-item.highlight {
  background: linear-gradient(135deg, #667eea15, #764ba215);
  color: #667eea; font-weight: 500;
}
.hashtag-list { display: flex; flex-wrap: wrap; gap: 6px; }
.hashtag {
  background: #ecf5ff; color: #409eff; font-size: 12px;
  padding: 4px 10px; border-radius: 12px;
}
</style>
