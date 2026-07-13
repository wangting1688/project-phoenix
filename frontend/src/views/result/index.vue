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
            <el-button size="small" type="primary" @click="goGenerateVideo(scripts[activeScript].id)">
              生成视频方案
            </el-button>
          </div>
        </div>
      </div>

      <!-- 视频展示 -->
      <div v-if="video || composition" class="section">
        <div class="section-header">
          <h3>视频</h3>
        </div>
        <div class="video-card card">
          <div class="video-preview">
            <el-icon :size="48"><IVideoCamera /></el-icon>
            <span>{{ composition ? '视频方案已生成' : '视频已生成' }}</span>
          </div>

          <!-- 视频合成方案 -->
          <div v-if="composition" class="composition-info">
            <div class="info-row">
              <span class="label">时长</span>
              <span class="value">{{ composition.plan.total_duration }}秒</span>
            </div>
            <div class="info-row">
              <span class="label">分辨率</span>
              <span class="value">{{ composition.plan.output_format.resolution }} ({{ composition.plan.output_format.aspect_ratio }})</span>
            </div>
            <div class="info-row">
              <span class="label">场景数</span>
              <span class="value">{{ composition.plan.scene_plan.length }}个</span>
            </div>
            <div class="info-row">
              <span class="label">素材数</span>
              <span class="value">{{ composition.footage_count }}条</span>
            </div>

            <!-- 质量评分 -->
            <div class="quality-section">
              <div class="quality-header">
                <span>质量评分</span>
                <span class="quality-score" :class="{ pass: composition.quality.pass }">
                  {{ composition.quality.total }}
                </span>
              </div>
              <div class="quality-bars">
                <div v-for="(label, key) in qualityLabels" :key="key" class="quality-bar">
                  <span class="bar-label">{{ label }}</span>
                  <el-progress
                    :percentage="composition.quality[key]"
                    :show-text="true"
                    :stroke-width="8"
                    :color="getQualityColor(composition.quality[key])"
                  />
                </div>
              </div>
            </div>

            <!-- TTS配置 -->
            <div class="info-block">
              <h4>语音配置</h4>
              <div class="info-row">
                <span class="label">音色</span>
                <span class="value">{{ composition.plan.tts_config.voice }}</span>
              </div>
              <div class="info-row">
                <span class="label">语速</span>
                <span class="value">{{ composition.plan.tts_config.speed }}x</span>
              </div>
            </div>

            <!-- BGM -->
            <div class="info-block">
              <h4>背景音乐</h4>
              <div class="info-row">
                <span class="label">风格</span>
                <span class="value">{{ composition.plan.bgm_config.style }}</span>
              </div>
              <div class="info-row">
                <span class="label">音量</span>
                <span class="value">{{ Math.round(composition.plan.bgm_config.volume * 100) }}%</span>
              </div>
            </div>

            <!-- 字幕预览 -->
            <div v-if="composition.plan.subtitles.length" class="info-block">
              <h4>字幕预览（前3条）</h4>
              <div v-for="(s, i) in composition.plan.subtitles.slice(0, 3)" :key="i" class="subtitle-item">
                <span class="time">{{ s.start }}-{{ s.end }}</span>
                <span class="text">{{ s.text }}</span>
              </div>
            </div>

            <!-- FFmpeg命令 -->
            <details class="ffmpeg-block">
              <summary>FFmpeg命令链（{{ composition.plan.ffmpeg_commands.length }}步）</summary>
              <pre v-for="(cmd, i) in composition.plan.ffmpeg_commands" :key="i" class="cmd">{{ cmd }}</pre>
            </details>
          </div>

          <div class="video-actions">
            <el-button type="primary" :loading="composing" @click="goGenerateVideo">
              {{ composition ? '重新生成方案' : '生成视频方案' }}
            </el-button>
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
} from '@/utils/icons'
import {
  getTaskStatus, getTaskResult, getTaskScripts,
  type TaskStatus, type Script, type VideoInfo,
} from '@/api/creation'
import { composeVideo, type ComposeResult } from '@/api/video'

const route = useRoute()
const router = useRouter()

const taskId = Number(route.query.task_id)
const projectId = ref<number | null>(null)
const taskStatus = ref<TaskStatus | null>(null)
const scripts = ref<Script[]>([])
const video = ref<VideoInfo | null>(null)
const activeScript = ref(0)
const composition = ref<ComposeResult | null>(null)
const composing = ref(false)
const operationData = ref<any>({
  titles: [], hashtags: [], comment_strategy: [], private_message_guide: '',
})

const qualityLabels: Record<string, string> = {
  realism: '真人感',
  info_value: '信息价值',
  rhythm: '节奏',
  subtitle_quality: '字幕质量',
  risk_safety: '商业风险',
}

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
      projectId.value = (result as any).project_id || null
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

function goGenerateVideo(scriptId?: number) {
  if (!taskId) return
  if (!projectId.value) {
    ElMessage.error('项目ID未加载，请稍候再试')
    return
  }
  composing.value = true
  composeVideo(projectId.value, scriptId)
    .then((res: any) => {
      composition.value = res as ComposeResult
      ElMessage.success(`视频方案已生成，质量评分 ${res.quality.total}`)
    })
    .catch((err: any) => {
      const msg = err?.response?.data?.message || err?.detail || '生成失败'
      ElMessage.error(msg)
    })
    .finally(() => {
      composing.value = false
    })
}

function getQualityColor(score: number) {
  if (score >= 85) return '#67c23a'
  if (score >= 70) return '#409eff'
  if (score >= 60) return '#e6a23c'
  return '#f56c6c'
}

function downloadVideo() {
  if (!composition.value) {
    ElMessage.info('请先生成视频方案')
    return
  }
  ElMessage.info('V1版本：FFmpeg命令已生成，可在后端执行合成')
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

/* 视频合成方案展示 */
.composition-info {
  text-align: left;
  margin-bottom: 20px;
  padding: 16px;
  background: #fafbfc;
  border-radius: 10px;
}
.info-row {
  display: flex; justify-content: space-between;
  font-size: 14px; padding: 6px 0;
  border-bottom: 1px dashed #ebeef5;
}
.info-row:last-child { border-bottom: none; }
.info-row .label { color: #909399; }
.info-row .value { color: #303133; font-weight: 500; }

.quality-section {
  margin-top: 16px; padding: 12px;
  background: #fff; border-radius: 8px;
  border: 1px solid #ebeef5;
}
.quality-header {
  display: flex; justify-content: space-between; align-items: center;
  margin-bottom: 12px;
}
.quality-header span:first-child {
  font-size: 14px; color: #303133; font-weight: 500;
}
.quality-score {
  font-size: 22px; font-weight: bold; color: #f56c6c;
  padding: 2px 14px; border-radius: 16px;
  background: #fef0f0;
}
.quality-score.pass {
  color: #67c23a; background: #f0f9eb;
}
.quality-bars { display: flex; flex-direction: column; gap: 8px; }
.quality-bar {
  display: flex; align-items: center; gap: 12px;
}
.quality-bar .bar-label {
  font-size: 13px; color: #606266;
  width: 80px; flex-shrink: 0;
}
.quality-bar :deep(.el-progress) { flex: 1; }
.quality-bar :deep(.el-progress-bar__innerText) { font-size: 11px; }

.info-block {
  margin-top: 14px; padding: 12px;
  background: #fff; border-radius: 8px;
  border: 1px solid #ebeef5;
}
.info-block h4 {
  font-size: 14px; color: #303133; margin-bottom: 8px;
}
.subtitle-item {
  display: flex; gap: 10px; padding: 6px 0;
  font-size: 13px; color: #606266;
  border-bottom: 1px dashed #ebeef5;
}
.subtitle-item:last-child { border-bottom: none; }
.subtitle-item .time {
  color: #909399; font-family: monospace; font-size: 12px;
  flex-shrink: 0;
}

.ffmpeg-block {
  margin-top: 14px; padding: 10px;
  background: #2d2d2d; border-radius: 8px;
}
.ffmpeg-block summary {
  cursor: pointer; color: #ddd; font-size: 13px;
  padding: 4px 0;
}
.ffmpeg-block summary:hover { color: #fff; }
.ffmpeg-block .cmd {
  color: #0f0; font-family: monospace; font-size: 11px;
  padding: 8px 6px; margin: 4px 0;
  background: #1a1a1a; border-radius: 4px;
  white-space: pre-wrap; word-break: break-all;
}

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
