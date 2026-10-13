<template>
  <div class="result-page">
    <div class="page-header">
      <h2>创作结果</h2>
      <p>{{ project?.topic || 'AI生成的内容' }}</p>
    </div>

    <div class="page-container">
      <!-- 进度展示 -->
      <div v-if="failed" class="progress-card card">
        <el-alert type="error" :closable="false" show-icon title="创作未完成">
          <div class="fail-reason">{{ failReason }}</div>
        </el-alert>
        <div class="fail-actions">
          <el-button type="primary" @click="router.push('/creation')">重新创作</el-button>
        </div>
      </div>

      <div v-else-if="!completed" class="progress-card card">
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
            <span v-if="editingScript === activeScript" class="editing-tip">编辑中</span>
          </div>
          <el-input
            v-if="editingScript === activeScript"
            v-model="editContent"
            type="textarea"
            :rows="10"
            resize="vertical"
            class="script-textarea"
            placeholder="编辑文案内容"
          />
          <div v-else class="script-content">{{ scripts[activeScript].content }}</div>
          <div v-if="scripts[activeScript].meta?.emphasis?.length" class="emphasis-tags">
            <span class="emphasis-label">重点词</span>
            <span
              v-for="w in scripts[activeScript].meta.emphasis"
              :key="w"
              class="emphasis-tag"
            >{{ w }}</span>
          </div>
          <div class="script-actions">
            <template v-if="editingScript === activeScript">
              <el-button size="small" @click="cancelEdit">取消</el-button>
              <el-button size="small" type="primary" :loading="savingScript" @click="saveScript">
                保存
              </el-button>
            </template>
            <template v-else>
              <el-button size="small" @click="copyScript(scripts[activeScript].content)">
                <el-icon><ICopyDocument /></el-icon> 复制
              </el-button>
              <el-button size="small" @click="startEdit(activeScript)">
                <el-icon><IDocument /></el-icon> 编辑
              </el-button>
              <el-button size="small" type="primary" @click="goCreateVideo">
                用照片生成视频
              </el-button>
              <el-button size="small" type="warning" :loading="reReviewing" @click="reReviewCurrentScript">
                编辑后重新审核
              </el-button>
              <el-button size="small" type="success" plain :loading="markingHot" @click="markHot">
                标记爆款
              </el-button>
            </template>
          </div>
        </div>
      </div>

      <!-- 视频展示 -->
      <div v-if="video || composition || composing || rendering || renderedVideo" class="section">
        <div class="section-header">
          <h3>最终成片 <el-tag v-if="!renderedVideo" size="small" type="info" effect="plain">demo 阶段</el-tag></h3>
        </div>
        <el-alert
          v-if="!renderedVideo && composition"
          type="info"
          :closable="false"
          show-icon
          title="当前显示的是方案内第 1 段原始素材"
          description="完整最终视频 (字幕/配音/转场) 需点击下方『渲染最终视频』按钮生成, 可能需要数秒"
          class="video-alert"
        />
        <div class="video-card card">
          <div class="video-preview">
            <video
              v-if="renderedSrc"
              :src="renderedSrc"
              :poster="coverSrc || undefined"
              controls
              preload="metadata"
              playsinline
              webkit-playsinline
              x5-playsinline
              class="preview-video"
              @error="videoError = true"
            ></video>
            <video
              v-else-if="previewSrc && !videoError"
              :src="previewSrc"
              :poster="coverSrc || undefined"
              controls
              preload="metadata"
              playsinline
              webkit-playsinline
              x5-playsinline
              class="preview-video"
              @error="videoError = true"
            ></video>
            <div v-else class="video-placeholder">
              <el-icon v-if="composing || rendering" :size="48" class="loading-icon"><ILoading /></el-icon>
              <el-icon v-else :size="48"><IVideoCamera /></el-icon>
              <span>
                {{ videoError ? '素材加载失败, 请稍后重试' : 
                   rendering ? '正在渲染最终视频...' :
                   composing ? '正在生成视频方案...' :
                   '视频方案已生成' }}
              </span>
            </div>
            <p v-if="!renderedSrc" class="preview-hint">
              下方为方案内第 1 段原始素材片段, 非最终成片
            </p>
          </div>

          <!-- 视频合成方案 -->
          <div v-if="composition && !renderedVideo" class="composition-info">
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

          <div v-if="!renderedVideo" class="video-actions retire-actions">
            <p class="retire-hint">
              本版本用「主播照片 + 讲解场景」直接生成讲解视频，不再需要实拍素材，
              请到创作页完成。
            </p>
            <el-button type="primary" @click="goCreateVideo">去创作页生成视频</el-button>
          </div>          <div v-else class="video-actions">
            <el-button type="primary" @click="downloadVideo">下载视频</el-button>
            <el-button type="success" plain @click="shareVideo">分享</el-button>
            <el-button plain @click="copyShareText">复制发布文案</el-button>
          </div>
        </div>
      </div>

      <!-- 还没有成片时的出口。
           以前这种项目整块「最终成片」都不渲染 —— 因为 v-if 里没有任何
           可展示对象 —— 用户打开结果页只看到文案，找不到任何"怎么生成视频"
           的入口（线上反馈「点了没反应 / 请提交素材但没有入口」就是这么来的）。
           旧的 compose→渲染 链路已下线，这里统一给出可点的去向。 -->
      <div v-else-if="projectId && !renderedVideo" class="section">
        <div class="section-header">
          <h3>最终成片</h3>
        </div>
        <div class="video-card card retire-actions">
          <p class="retire-hint">
            这个项目还没有视频。本版本用「主播照片 + 讲解场景」直接生成讲解视频，
            不再需要实拍素材，请到创作页完成。
          </p>
          <el-button type="primary" @click="goCreateVideo">去创作页生成视频</el-button>
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
import { ElMessage, ElMessageBox } from 'element-plus'
import {
  ILoading, ICopyDocument, IVideoCamera,
  ICheck, IDocument, IVideoPlay, ISetting,
} from '@/utils/icons'
import {
  getTaskStatus, getTaskResult, getTaskScripts, getProject, getProjectScripts,
  reReviewScript,
  markScriptHot,
  type TaskStatus, type Script, type VideoInfo, type ContentProject,
} from '@/api/creation'
import { composeVideo, renderVideo, type ComposeResult } from '@/api/video'
import { getVoiceProfiles, type VoiceProfile } from '@/api/voiceProfile'
import { useUserStore } from '@/stores/user'
import { resolveMediaUrls, storagePathOf } from '@/utils/mediaUrl'
import { normalizeStatus } from '@/utils/status'

const route = useRoute()
const router = useRouter()
const userStore = useUserStore()

// task_id 有两个来源：URL（?task_id=）与项目详情（作品页「查看进度」跳进来时
// 只带 project_id，项目接口会把它的主任务 id 一并返回）。所以这里必须是 ref。
const taskId = ref(Number(route.query.task_id || 0))
const projectIdQuery = Number(route.query.project_id || 0)
const projectId = ref<number | null>(null)
const project = ref<(ContentProject & { video_url?: string | null; video_duration?: number | null }) | null>(null)
const taskStatus = ref<TaskStatus | null>(null)
const scripts = ref<Script[]>([])
const video = ref<VideoInfo | null>(null)
const activeScript = ref(0)
const composition = ref<ComposeResult | null>(null)
const videoError = ref(false)
const rendering = ref(false)
const voiceProfiles = ref<VoiceProfile[]>([])
const selectedVoiceId = ref<number | null>(null)
const activeVoices = computed(() => voiceProfiles.value.filter((v) => v.status === 'active'))
const renderedVideo = ref<{ video_id: number; output_url: string; duration: number } | null>(null)
const renderedSrc = ref<string | null>(null)
const coverSrc = ref<string | null>(null)
const composing = ref(false)
const editingScript = ref<number | null>(null)

const previewSrc = ref<string | null>(null)

async function refreshMediaUrls() {
  const paths: string[] = []
  if (renderedVideo.value?.output_url) {
    paths.push(storagePathOf(renderedVideo.value.output_url))
  }
  if (video.value?.cover_url) {
    paths.push(storagePathOf(video.value.cover_url))
  }
  let footagePath = ''
  const scene = composition.value?.plan?.scene_plan?.[0]
  if (scene?.footage_path) {
    const m = scene.footage_path.match(/footage\/(\d+)\/([^/]+)$/)
    if (m) {
      footagePath = `footage/${m[1]}/${m[2]}`
      paths.push(footagePath)
    }
  }
  const map = await resolveMediaUrls(paths)
  renderedSrc.value = renderedVideo.value?.output_url
    ? map[storagePathOf(renderedVideo.value.output_url)] || null
    : null
  coverSrc.value = video.value?.cover_url
    ? map[storagePathOf(video.value.cover_url)] || null
    : null
  previewSrc.value = footagePath ? map[footagePath] || null : null
}

/**
 * 把项目详情应用到页面状态（视频字段 + 媒体签名 URL）。
 *
 * 首屏加载与轮询结束时都走这里，避免两处各写一份、日后漂移。
 */
async function applyProjectDetail(proj: any) {
  project.value = proj
  if (!proj?.video_url) return
  renderedVideo.value = {
    video_id: proj.id,
    output_url: proj.video_url,
    duration: proj.video_duration,
  }
  video.value = {
    id: proj.id,
    project_id: proj.id,
    url: proj.video_url,
    cover_url: proj.cover_url,
    duration: proj.video_duration,
    status: proj.video_status || 'rendered',
  }
  await refreshMediaUrls()
}

const editContent = ref('')
const savingScript = ref(false)
const reReviewing = ref(false)
const markingHot = ref(false)
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
  { key: 'analyzing', label: '分析与策划', icon: IDocument },
  { key: 'scripting', label: '文案生成', icon: IDocument },
  { key: 'reviewing', label: '合规审核', icon: ICheck },
  { key: 'generating_video', label: '视频生成', icon: IVideoPlay },
  { key: 'optimizing', label: '运营优化', icon: ISetting },
  { key: 'completed', label: '完成', icon: ICheck },
]

const taskProgress = computed(() => taskStatus.value?.progress || 0)

/**
 * 项目自身的展示状态（已归一）。历史数据里 status 可能是 "ready" 这类不在
 * 枚举内的值，直接拿去比对会被判成「未完成」，页面就一直卡在进度条上。
 */
const projectStatus = computed(() =>
  normalizeStatus(project.value?.display_status || (project.value as any)?.status)
)
const completed = computed(() =>
  taskStatus.value?.status === 'completed' ||
  projectStatus.value === 'plan_ready' ||
  projectStatus.value === 'video_ready'
)
const failed = computed(() => taskStatus.value?.status === 'failed' || projectStatus.value === 'failed')
const failReason = computed(
  () => taskStatus.value?.error_message || '创作流程执行失败，请稍后重试'
)
const progressColor = computed(() => {
  if (completed.value) return '#67c23a'
  return '#667eea'
})

onMounted(async () => {
  if (taskId.value) {
    pollStatus()
  } else if (projectIdQuery) {
    // 从作品列表跳过来的，加载项目详情 + 脚本 + 视频
    try {
      const proj = await getProject(projectIdQuery)
      projectId.value = projectIdQuery
      await applyProjectDetail(proj)
      // 加载文案脚本
      try {
        const scriptList = await getProjectScripts(projectIdQuery)
        scripts.value = scriptList || []
        // 作品页「生成视频」带 ?action=generate 跳进来。旧的 compose → 渲染
        // 链路已下线，这里统一引导到创作页（照片 + 场景图生视频），
        // 并带上选题，用户点一下就能接着做。
        if (route.query.action === 'generate' && !renderedVideo.value) {
          goCreateVideo()
          return
        }
      } catch {
        scripts.value = []
      }
      // 创作完成后填充运营方案：project 分支不会走 pollStatus，必须在此主动加载，
      // 否则「运营方案」区块虽因 completed=true 显示，但标题/标签等内容恒为空（V1 默认数据）。
      loadOperationData()

      // 项目仍在创作中就必须轮询，否则进度条永远停在 0%「AI正在创作中」，
      // 用户从作品页点「查看进度」跳进来看到的就是这样一个死页面。
      if (projectStatus.value === 'processing') {
        const tid = Number((proj as any)?.task_id || 0)
        if (tid) {
          taskId.value = tid
          pollStatus(tid)
        } else {
          // 兜底：历史项目可能没有关联的任务记录，就直接轮询项目本身。
          pollProjectProgress()
        }
      }
    } catch (e) {
      console.error('加载项目失败:', e)
    }
  }
  loadVoiceProfiles()
})

async function loadVoiceProfiles() {
  try {
    const res = await getVoiceProfiles()
    voiceProfiles.value = res || []
  } catch {
    voiceProfiles.value = []
  }
}

onUnmounted(() => {
  if (pollTimer) clearInterval(pollTimer)
})

function pollDelayMs(): number {
  return document.visibilityState === 'hidden' ? 30000 : 5000
}

async function pollStatus(id: number = taskId.value) {
  if (!id) return
  try {
    const status = await getTaskStatus(id)
    taskStatus.value = status as any

    const result = await getTaskResult(id)
    if (result) {
      scripts.value = (result as any).scripts || []
      video.value = (result as any).video || null
      projectId.value = (result as any).project_id || null
      await refreshMediaUrls()
    }

    if (status?.status === 'completed') {
      // 任务结束时回读一次项目：结果接口里没有成片/封面字段，成片要往项目上取。
      await reloadProject()
      loadOperationData()
      return
    }
    // 失败时必须停止轮询, 否则页面永远停在"AI正在创作中"
    if (status?.status === 'failed') {
      await reloadProject()
      return
    }

    pollTimer = window.setTimeout(() => pollStatus(id), pollDelayMs())
  } catch (e) {
    console.error('轮询失败', e)
    pollTimer = window.setTimeout(() => pollStatus(id), pollDelayMs())
  }
}

/** 重新拉一次项目详情（轮询结束时用，让成片/状态及时到位）。 */
async function reloadProject() {
  const pid = projectId.value
  if (!pid) return
  try {
    const proj = await getProject(pid)
    await applyProjectDetail(proj)
    // 任务刚完成时脚本可能刚落库，这里补一次，别让页面停在旧数据上
    if (!scripts.value.length) {
      try {
        scripts.value = (await getProjectScripts(pid)) || []
      } catch { /* 脚本拉取失败不影响进度展示 */ }
    }
  } catch (e) {
    console.error('回读项目失败', e)
  }
}

/**
 * 没有任务记录时的兜底轮询：按固定间隔重取项目详情，直到它不再是「生成中」。
 *
 * 比任务轮询粗糙（拿不到分步进度），但至少能让页面自己走到完成/失败态 ——
 * 而不是永远停在 0%「AI正在创作中」。
 */
async function pollProjectProgress() {
  const pid = projectId.value
  if (!pid) return
  try {
    const proj = await getProject(pid)
    await applyProjectDetail(proj)
    if (projectStatus.value !== 'processing') {
      try {
        scripts.value = (await getProjectScripts(pid)) || []
      } catch { /* 同上 */ }
      loadOperationData()
      return
    }
  } catch (e) {
    console.error('轮询项目进度失败', e)
  }
  pollTimer = window.setTimeout(pollProjectProgress, pollDelayMs())
}

async function loadOperationData() {
  // 这里可以从task的result字段中获取运营方案
  // V1暂时用默认数据（优先取项目真实主题，其次 URL 参数）
  const topic = (project.value as any)?.topic || route.query.topic || '健康'
  operationData.value = {
    titles: [
      `${topic}不好？这几个方法一定要试试`,
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

function startEdit(index: number) {
  editingScript.value = index
  editContent.value = scripts.value[index]?.content || ''
}
function cancelEdit() {
  editingScript.value = null
  editContent.value = ''
}
async function saveScript() {
  const s = scripts.value[editingScript.value ?? -1]
  if (!s) return
  if (!editContent.value.trim()) {
    ElMessage.error('文案不能为空')
    return
  }
  savingScript.value = true
  try {
    const { updateScript } = await import('@/api/creation')
    await updateScript(s.id, editContent.value)
    s.content = editContent.value
    editingScript.value = null
    ElMessage.success('文案已保存')
  } catch (e: any) {
    ElMessage.error(e?.message || '保存失败')
  } finally {
    savingScript.value = false
  }
}

async function reReviewCurrentScript() {
  const s = scripts.value[activeScript.value]
  if (!s || !projectId.value) return
  reReviewing.value = true
  try {
    const res = await reReviewScript(projectId.value, s.id, s.content)
    ElMessage.success('审核通过，可以继续生成视频')
    // 刷新任务/项目状态，让页面退出 failed 态
    try {
      const proj = await getProject(projectId.value)
      project.value = proj
      taskStatus.value = { status: 'completed', progress: 100, error_message: null } as any
    } catch {}
  } catch (e: any) {
    ElMessage.error(extractApiError(e))
  } finally {
    reReviewing.value = false
  }
}

async function markHot() {
  const s = scripts.value[activeScript.value]
  if (!s) return
  markingHot.value = true
  try {
    await markScriptHot(s.id)
    s.meta = { ...(s.meta || {}), is_hot: true }
    ElMessage.success('已标记为爆款，后续生成会参考它')
  } catch (e: any) {
    ElMessage.error(e?.response?.data?.detail || '标记失败')
  } finally {
    markingHot.value = false
  }
}

function copyScript(content: string) {
  navigator.clipboard.writeText(content).then(() => {
    ElMessage.success('已复制到剪贴板')
  }).catch(() => {
    ElMessage.error('复制失败')
  })
}

function extractApiError(err: any): string {
  const detail = err?.response?.data?.detail
  if (typeof detail === 'string') return detail
  if (Array.isArray(detail) && detail.length > 0) {
    return detail.map((d: any) => d?.msg || d?.message || JSON.stringify(d)).join("; ")
  }
  return err?.response?.data?.message || err?.message || '生成失败'
}

/**
 * 生成视频的唯一入口改到创作页（照片 + 场景图生视频）。
 *
 * 这里原来挂的是「生成视频方案（compose）→ 渲染」这条旧链路：它依赖
 * 视频素材库里的实拍片段，实测一直走不通——点下去只会弹「请先上传素材」，
 * 而素材库里的分类区又是空的，用户根本找不到上传入口，卡死在结果页。
 * 那条链路已整体下线，所以这里只做跳转。
 *
 * 跳转必须带 project_id：这个项目的文案已经生成好了，创作页据此恢复它并
 * 直接落到「声音」步；只带 topic 会被当成新创作，用户得重新生成一遍文案。
 */
function goCreateVideo() {
  const pid = projectId.value || projectIdQuery
  const topic = (project.value as any)?.topic || ''
  const q: Record<string, string> = {}
  if (pid) q.project_id = String(pid)
  if (topic) q.topic = String(topic).slice(0, 100)
  router.push({ path: '/creation', query: q })
}

async function autoGenerateAndRender(_scriptId?: number) {
  // 旧的「一键生成」（compose → 渲染）已下线，这里保留一个转发实现，
  // 兜住可能残留的历史调用点：直接引导到创作页。
  ElMessage.info('请到创作页用「主播照片 + 讲解场景」生成视频')
  goCreateVideo()
}

function getQualityColor(score: number) {
  if (score >= 85) return '#67c23a'
  if (score >= 70) return '#409eff'
  if (score >= 60) return '#e6a23c'
  return '#f56c6c'
}

function downloadVideo() {
  if (!renderedSrc.value) {
    ElMessage.warning('请先点击「渲染最终视频」生成成片')
    return
  }
  const a = document.createElement('a')
  a.href = renderedSrc.value
  a.download = `${project.value?.topic || 'video'}.mp4`
  document.body.appendChild(a)
  a.click()
  document.body.removeChild(a)
  ElMessage.success('已开始下载，可保存后上传到抖音/视频号等平台')
}

async function copyShareText() {
  const topic = project.value?.topic || 'AI 短视频'
  const text = `【${topic}】\n${window.location.href}\n刚用 AI 生成的短视频，欢迎看看～`
  try {
    await navigator.clipboard.writeText(text)
    ElMessage.success('已复制发布文案')
  } catch {
    ElMessage.warning('复制失败，请长按链接手动复制')
  }
}

async function shareVideo() {
  const nav = navigator as any
  if (nav.share) {
    try {
      await nav.share({
        title: project.value?.topic || 'AI 短视频',
        text: `刚用 AI 生成的短视频：${project.value?.topic || ''}`,
        url: window.location.href,
      })
    } catch {
      /* 用户取消分享不提示 */
    }
    return
  }
  await copyShareText()
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
.fail-reason { line-height: 1.6; word-break: break-all; }
.fail-actions { margin-top: 12px; text-align: right; }
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
.emphasis-tags { display: flex; flex-wrap: wrap; gap: 8px; margin-bottom: 14px; align-items: center; }
.emphasis-label { color: #909399; font-size: 13px; }
.emphasis-tag {
  background: #f0f2ff; color: #4f46e5; border: 1px solid #c7d2fe;
  border-radius: 6px; padding: 2px 10px; font-size: 13px;
}

.voice-select { width: 150px; margin-right: 8px; }
.video-card { text-align: center; padding: 30px; }
.video-alert { max-width: 480px; margin: 0 auto 16px; }
.video-preview {
  width: 360px; height: 640px; margin: 0 auto 20px;  /* 9:16 竖屏 */
  background: linear-gradient(135deg, #667eea20, #764ba220);
  display: flex; flex-direction: column; align-items: center; justify-content: center;
  color: #667eea; border-radius: 12px; overflow: hidden;
}
.preview-video {
  width: 100%; height: 100%; object-fit: contain;
  display: block; background: #000; border-radius: 8px;
}
.video-placeholder {
  padding: 24px 16px; text-align: center; line-height: 1.6;
}
.video-placeholder span { display: block; margin-top: 8px; font-size: 14px; }
.video-actions { display: flex; gap: 10px; justify-content: center; }
/* 视频生成入口已迁到创作页，这里给出说明 + 可点的跳转，不再放被禁用的按钮 */
.retire-actions { flex-direction: column; align-items: center; gap: 12px; }
.retire-hint {
  margin: 0; color: #909399; font-size: 13px; line-height: 1.6; text-align: center;
}

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
