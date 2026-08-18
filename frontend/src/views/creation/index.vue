<template>
  <div class="creation-page">
    <!-- 顶部进度条 -->
    <div class="step-header">
      <div class="step-progress">
        <div
          v-for="(s, i) in steps"
          :key="s.key"
          class="step-dot"
          :class="{
            active: currentStep === i,
            done: currentStep > i,
          }"
        >
          <span class="dot-num">{{ i + 1 }}</span>
        </div>
        <div class="step-line" :style="{ width: `${(currentStep / (steps.length - 1)) * 100}%` }"></div>
      </div>
      <div class="step-labels">
        <div v-for="s in steps" :key="s.key" class="step-label-text">{{ s.label }}</div>
      </div>
    </div>

    <div class="step-content">
      <!-- Step 1: 输入选题 -->
      <div v-if="currentStep === 0" class="step-panel">
        <h2 class="step-title">你想做什么主题的视频？</h2>
        <p class="step-desc">输入一个你想讲的话题，AI 会帮你写出口播文案</p>

        <div class="form-card">
          <div class="form-item">
            <label>行业类型</label>
            <el-select v-model="formData.industry" placeholder="请选择行业" size="large">
              <el-option v-for="opt in industryOptions" :key="opt" :label="opt" :value="opt" />
            </el-select>
          </div>

          <div class="form-item">
            <label>视频主题</label>
            <el-input
              v-model="formData.topic"
              type="textarea"
              :rows="3"
              placeholder="例如：肠胃不好怎么调理"
              maxlength="100"
              show-word-limit
              size="large"
            />
          </div>

          <div class="form-item">
            <label>视频目标</label>
            <div class="goal-options">
              <div
                v-for="g in goalOptions"
                :key="g.value"
                class="goal-card"
                :class="{ active: formData.goal === g.value }"
                @click="formData.goal = g.value"
              >
                <div class="goal-icon">{{ g.icon }}</div>
                <div class="goal-text">{{ g.label }}</div>
              </div>
            </div>
          </div>
        </div>
      </div>

      <!-- Step 2: 选择脚本 -->
      <div v-if="currentStep === 1" class="step-panel">
        <h2 class="step-title">选择一个文案版本</h2>
        <p class="step-desc">AI 为你生成了 3 个版本的口播文案</p>

        <div v-if="generatingScripts" class="loading-state">
          <el-icon class="loading-icon" :size="48"><ILoading /></el-icon>
          <p>AI 正在生成你的 3 个文案方案，请稍候...</p>
          <p class="wait-time">已等待 {{ scriptWaitSeconds }} 秒</p>
        </div>

        <div v-else-if="scriptTimeout" class="loading-state timeout-state">
          <el-icon class="loading-icon" :size="48"><IClock /></el-icon>
          <p>生成时间较长</p>
          <el-button
            type="primary"
            class="retry-script-btn"
            :loading="stepLoading"
            @click="regenerateScripts"
          >
            重新生成文案
          </el-button>
        </div>

        <div v-else class="script-list">
          <div
            v-for="(s, i) in scripts"
            :key="s.id"
            class="script-card card"
            :class="{ active: selectedScriptId === s.id }"
            @click="selectedScriptId = s.id"
          >
            <div class="script-header">
              <span class="script-tag">{{ scriptTypeName(s.type) }}</span>
              <span v-if="s.score" class="script-score">评分 {{ s.score }}</span>
            </div>
            <div class="script-content">{{ s.content }}</div>
            <div class="script-check" v-if="selectedScriptId === s.id">
              <el-icon><ICheck /></el-icon> 已选择
            </div>
          </div>
        </div>
      </div>

      <!-- Step 3: 选择声音 -->
      <div v-if="currentStep === 2" class="step-panel">
        <h2 class="step-title">选择主播声音</h2>
        <p class="step-desc">用克隆的声音来生成配音</p>

        <div v-if="loadingVoices" class="loading-state">
          <el-icon class="loading-icon" :size="32"><ILoading /></el-icon>
          <p>加载中...</p>
        </div>

        <div v-else-if="voiceProfiles.length === 0" class="empty-voice">
          <el-empty description="还没有声音模型">
            <el-button type="primary" @click="goToVoicePage">去训练声音</el-button>
          </el-empty>
        </div>

        <div v-else class="voice-list">
          <div
            v-for="v in voiceProfiles"
            :key="v.id"
            class="voice-card card"
            :class="{ active: selectedVoiceId === v.id, disabled: v.status !== 'active' }"
            @click="selectVoice(v)"
          >
            <div class="voice-info">
              <div class="voice-name">{{ v.name || '我的声音' }}</div>
              <div class="voice-status">
                <el-tag :type="v.status === 'active' ? 'success' : 'warning'" size="small">
                  {{ voiceStatusText(v.status) }}
                </el-tag>
              </div>
            </div>
            <el-button
              v-if="v.status === 'active'"
              size="small"
              text
              type="primary"
              :loading="testingVoiceId === v.id"
              @click.stop="playVoice(v)"
            >
              <el-icon v-if="playingVoiceId === v.id"><ICircleClose /></el-icon>
              <el-icon v-else><IVideoPlay /></el-icon>
              {{ playingVoiceId === v.id ? '停止' : '试听' }}
            </el-button>
            <div v-if="selectedVoiceId === v.id" class="voice-check">
              <el-icon><ICheck /></el-icon>
            </div>
          </div>
        </div>
      </div>

      <!-- Step 4: 选择素材 -->
      <div v-if="currentStep === 3" class="step-panel">
        <h2 class="step-title">选择一段视频素材</h2>
        <p class="step-desc">选择一段主播口播视频，AI 会自动对齐口型</p>

        <div v-if="loadingFootages" class="loading-state">
          <el-icon class="loading-icon" :size="32"><ILoading /></el-icon>
          <p>加载中...</p>
        </div>

        <div v-else-if="footages.length === 0" class="empty-state">
          <el-icon :size="48"><IVideoCamera /></el-icon>
          <p class="empty-title">你还没有视频素材</p>
          <p class="empty-sub">请先上传一段主播口播视频，AI 会自动对齐口型</p>
          <el-button type="primary" @click="goToFootagePage">去上传素材</el-button>
        </div>

        <div v-else class="footage-grid">
          <div
            v-for="f in footages"
            :key="f.id"
            class="footage-card"
            :class="{ active: selectedFootageId === f.id }"
            @click="selectedFootageId = f.id"
          >
            <div class="footage-cover">
              <img v-if="f.thumbnail" :src="addTokenToUrl(f.thumbnail)" alt="" />
              <div v-else class="footage-placeholder">
                <el-icon :size="28"><IVideoCamera /></el-icon>
              </div>
              <span class="footage-duration">{{ formatDuration(f.duration) }}</span>
            </div>
            <div class="footage-name">{{ f.filename }}</div>
            <div v-if="selectedFootageId === f.id" class="footage-check">
              <el-icon><ICheck /></el-icon>
            </div>
          </div>
        </div>

        <div v-if="footages.length > 0" class="upload-hint">
          <el-button text type="primary" @click="goToFootagePage">
            + 上传新素材
          </el-button>
        </div>
      </div>

      <!-- Step 5: 生成中 / 失败 -->
      <div v-if="currentStep === 4" class="step-panel generating">
        <template v-if="!generatingFailed">
          <div class="generating-icon">
            <el-icon :size="64" class="loading-icon"><ILoading /></el-icon>
          </div>
          <h2 class="step-title">正在生成视频</h2>
          <p class="step-desc">{{ currentStepText }}</p>

          <el-progress
            :percentage="generateProgress"
            :stroke-width="8"
            :color="progressColor"
          />

          <p v-if="queueHint" class="queue-hint">{{ queueHint }}</p>

          <div class="step-checklist">
            <div v-for="task in generateSteps" :key="task.key" class="check-item">
              <el-icon>
                <component :is="taskIcon(task.status)" />
              </el-icon>
              <span :class="{ done: task.status === 'done', current: task.status === 'doing' }">
                {{ task.label }}
              </span>
            </div>
          </div>
        </template>

        <template v-else>
          <div class="fail-icon">
            <el-icon :size="64"><ICircleClose /></el-icon>
          </div>
          <h2 class="step-title">生成失败</h2>
          <p class="step-desc fail-reason">{{ failReason }}</p>
          <div class="fail-actions">
            <el-button size="large" class="back-btn" @click="backToEdit">
              返回修改
            </el-button>
            <el-button
              type="primary"
              size="large"
              class="retry-btn"
              :loading="stepLoading"
              @click="retryGenerate"
            >
              重新生成
            </el-button>
          </div>
        </template>
      </div>
    </div>

    <!-- 底部操作栏 -->
    <div v-if="currentStep < 4" class="step-footer">
      <el-button
        v-if="currentStep > 0"
        size="large"
        class="prev-btn"
        @click="prevStep"
      >
        上一步
      </el-button>
      <el-button
        type="primary"
        size="large"
        class="next-btn"
        :loading="stepLoading"
        :disabled="!canNext"
        @click="nextStep"
      >
        {{ currentStep === 3 ? '开始生成' : '下一步' }}
      </el-button>
      <p
        v-if="currentStep === 3 && !canNext && selectedFootageId === null"
        class="footer-hint"
      >
        请先选择一段视频素材，再点击「开始生成」
      </p>
      <p
        v-else-if="currentStep === 3 && !canNext"
        class="footer-hint"
      >
        请先返回完成前序步骤（选题 / 文案 / 声音）
      </p>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, onMounted, onUnmounted, watch } from 'vue'
import { useRouter } from 'vue-router'
import { useUserStore } from '@/stores/user'
import { ElMessage } from 'element-plus'
import {
  ILoading,
  ICheck,
  IVideoCamera,
  IVideoPlay,
  ICircleCheck,
  IClock,
  ICircleClose,
} from '@/utils/icons'
import { createProject, getProjectScripts, getTaskStatus } from '@/api/creation'
import { generateVideo } from '@/api/video'
import { getVoiceProfiles, testVoiceProfile, type VoiceProfile } from '@/api/voiceProfile'
import { listFootages, type Footage } from '@/api/footage'

const router = useRouter()

const steps = [
  { key: 'topic', label: '选题' },
  { key: 'script', label: '文案' },
  { key: 'voice', label: '声音' },
  { key: 'footage', label: '素材' },
  { key: 'generate', label: '生成' },
]

const currentStep = ref(0)
const stepLoading = ref(false)

// ===== Step 1: 选题 =====
const industryOptions = [
  '健康养生', '美妆护肤', '美食餐饮', '教育培训',
  '生活情感', '职场成长', '母婴育儿', '家居生活', '其他',
]
const goalOptions = [
  { value: 'followers', label: '涨粉关注', icon: '📈' },
  { value: 'engagement', label: '互动点赞', icon: '👍' },
  { value: 'conversion', label: '种草成交', icon: '🛒' },
]
const formData = ref({
  industry: '健康养生',
  topic: '',
  goal: 'followers',
})

// ===== Step 2: 脚本 =====
const scripts = ref<any[]>([])
const selectedScriptId = ref<number | null>(null)
const generatingScripts = ref(false)
const scriptWaitSeconds = ref(0)      // 文案生成已等待秒数
const scriptTimeout = ref(false)      // 60s 仍无文案时为 true
let projectId: number | null = null
let scriptPollTimer: number | null = null
let scriptWaitTimer: number | null = null
const SCRIPT_POLL_INTERVAL = 3000     // 每 3 秒轮询一次
const SCRIPT_MAX_WAIT = 60000         // 最长等待 60 秒

function scriptTypeName(type: string) {
  const map: Record<string, string> = {
    story: '故事型',
    knowledge: '知识型',
    chat: '聊天型',
  }
  return map[type] || type
}

// ===== 文案生成轮询（P1-1 等待体验）=====
function clearScriptPolling() {
  if (scriptPollTimer) {
    clearInterval(scriptPollTimer)
    scriptPollTimer = null
  }
  if (scriptWaitTimer) {
    clearInterval(scriptWaitTimer)
    scriptWaitTimer = null
  }
}

async function pollScripts() {
  if (projectId == null) return
  // 进入等待态：清空旧状态，启动计时与轮询
  clearScriptPolling()
  scriptWaitSeconds.value = 0
  scriptTimeout.value = false
  generatingScripts.value = true
  let done = false

  const check = async () => {
    if (done) return
    try {
      const list = await getProjectScripts(projectId as number)
      if (list && list.length > 0) {
        scripts.value = list
        selectedScriptId.value = list[0].id
        done = true
        clearScriptPolling()
        generatingScripts.value = false
        scriptTimeout.value = false
      }
    } catch (e) {
      // 单次轮询失败不中断，继续等待后续轮询
      console.error('轮询文案列表失败', e)
    }
  }

  // 计时器：每秒累加等待时间，到 60s 判定超时
  scriptWaitTimer = window.setInterval(() => {
    if (done) return
    scriptWaitSeconds.value += 1
    if (scriptWaitSeconds.value >= SCRIPT_MAX_WAIT / 1000) {
      done = true
      clearScriptPolling()
      generatingScripts.value = false
      scriptTimeout.value = true
    }
  }, 1000)

  // 立即查一次，之后每 3 秒轮询，直到文案出现
  await check()
  if (!done) {
    scriptPollTimer = window.setInterval(check, SCRIPT_POLL_INTERVAL)
  }
}

async function regenerateScripts() {
  // 同一主题重新创建项目并触发文案生成，再继续轮询
  stepLoading.value = true
  try {
    const res = await createProject('custom', formData.value.topic, formData.value.industry)
    projectId = res.project_id
    scripts.value = []
    selectedScriptId.value = null
    await pollScripts()
  } catch (e: any) {
    ElMessage.error(e?.response?.data?.detail || '重新生成失败，请稍后重试')
  } finally {
    stepLoading.value = false
  }
}

// ===== Step 3: 声音 =====
const voiceProfiles = ref<VoiceProfile[]>([])
const selectedVoiceId = ref<number | null>(null)
const loadingVoices = ref(false)
const testingVoiceId = ref<number | null>(null)  // 试听合成中
const playingVoiceId = ref<number | null>(null)   // 正在播放的声音 id
let audioEl: HTMLAudioElement | null = null
const userStore = useUserStore()

function voiceStatusText(status: string) {
  const map: Record<string, string> = {
    active: '可用',
    training: '训练中',
    failed: '训练失败',
    pending: '待训练',
  }
  return map[status] || status
}

function selectVoice(v: VoiceProfile) {
  if (v.status !== 'active') {
    ElMessage.warning('该声音模型还在训练中，请先等待训练完成')
    return
  }
  selectedVoiceId.value = v.id
}

// 静态音频走后端 /static 且带 token 校验，必须拼上用户 token 才能播放
function addTokenToUrl(url: string) {
  if (!url) return ''
  const sep = url.includes('?') ? '&' : '?'
  return `${url}${sep}token=${encodeURIComponent(userStore.token)}`
}

function stopVoice() {
  if (audioEl) {
    audioEl.pause()
    audioEl = null
  }
  playingVoiceId.value = null
}

async function playVoice(v: VoiceProfile) {
  // 正在播放当前声音 -> 再次点击停止
  if (playingVoiceId.value === v.id) {
    stopVoice()
    return
  }
  // 停掉其它正在播放的声音，避免叠播
  if (audioEl) {
    audioEl.pause()
    audioEl = null
  }
  testingVoiceId.value = v.id
  try {
    const res = await testVoiceProfile(v.id, '你好，这是我的声音，很高兴认识你。')
    audioEl = new Audio(addTokenToUrl(res.audio_url))
    audioEl.play().catch(() => {
      ElMessage.warning('试听播放被浏览器拦截，请再点一次')
    })
    playingVoiceId.value = v.id
    audioEl.onended = () => {
      playingVoiceId.value = null
      audioEl = null
    }
  } catch (e: any) {
    ElMessage.error(e?.response?.data?.detail || '试听失败，请稍后再试')
  } finally {
    testingVoiceId.value = null
  }
}

function goToVoicePage() {
  router.push('/voice-profile')
}

// ===== Step 4: 素材 =====
const footages = ref<Footage[]>([])
const selectedFootageId = ref<number | null>(null)
const loadingFootages = ref(false)

function formatDuration(sec: number) {
  if (!sec) return '0:00'
  const m = Math.floor(sec / 60)
  const s = sec % 60
  return `${m}:${s.toString().padStart(2, '0')}`
}

function goToFootagePage() {
  router.push('/footage')
}

// ===== Step 5: 生成中 =====
const generateProgress = ref(0)
const generateSteps = ref([
  { key: 'script', label: '生成文案', status: 'pending' }, // pending / doing / done
  { key: 'tts', label: '生成配音', status: 'pending' },
  { key: 'lipsync', label: '对齐口型', status: 'pending' },
  { key: 'render', label: '合成视频', status: 'pending' },
])

const currentStepText = computed(() => {
  const doing = generateSteps.value.find(s => s.status === 'doing')
  if (doing) {
    if (doing.key === 'lipsync') return '正在对齐口型（约需 1 分钟，请耐心等待，不要刷新页面）...'
    return doing.label + '中...'
  }
  const doneCount = generateSteps.value.filter(s => s.status === 'done').length
  if (doneCount === generateSteps.value.length) return '生成完成！'
  return '准备中...'
})

const progressColor = computed(() => '#667eea')

// 排队信息：GPU 串行执行，多人同时提交时要让用户知道自己排在第几位，
// 否则长时间不动的进度条会被当成卡死。
const queuePosition = ref<number | null>(null)
const queueEta = ref<number | null>(null)

const queueHint = computed(() => {
  const pos = queuePosition.value
  if (pos === null) return ''
  const eta = queueEta.value
  const etaText = eta && eta > 0 ? `，预计还需 ${formatEta(eta)}` : ''
  if (pos > 0) return `前面还有 ${pos} 个任务正在处理${etaText}`
  return eta && eta > 0 ? `正在处理${etaText}` : ''
})

function formatEta(seconds: number) {
  if (seconds < 60) return `${seconds} 秒`
  const m = Math.ceil(seconds / 60)
  return `${m} 分钟`
}

function taskIcon(status: string) {
  if (status === 'done') return ICheck
  if (status === 'doing') return ILoading
  return IClock
}

// ===== 生成失败恢复（P0-1）=====
const generatingFailed = ref(false)
const failReason = ref('')
const generationDone = ref(false)

// 进行中的生成任务（刷新/离开页面后可恢复轮询，避免进度丢失）
const activeTaskId = ref<number | null>(null)
const generationActive = ref(false)

function resetGenerateUI() {
  generatingFailed.value = false
  failReason.value = ''
  generateSteps.value.forEach(s => { s.status = 'pending' })
  generateProgress.value = 0
}

function backToEdit() {
  // 回到素材选择步，可用「上一步」继续修改更早的选项
  resetGenerateUI()
  currentStep.value = 3
}

function retryGenerate() {
  if (!projectId || !selectedScriptId.value || !selectedVoiceId.value || !selectedFootageId.value) {
    ElMessage.warning('信息不完整，请返回修改')
    backToEdit()
    return
  }
  resetGenerateUI()
  doGenerate()
}

// ===== 创建草稿持久化（P0-2）=====
const DRAFT_KEY = 'phoenix_creation_draft'

function saveDraft() {
  try {
    const draft = {
      formData: formData.value,
      // 不恢复到「生成中」状态，最高回到素材步
      currentStep: currentStep.value > 3 ? 3 : currentStep.value,
      scripts: scripts.value,
      selectedScriptId: selectedScriptId.value,
      selectedVoiceId: selectedVoiceId.value,
      selectedFootageId: selectedFootageId.value,
      projectId,
      activeTaskId: activeTaskId.value,
      generationActive: generationActive.value,
    }
    localStorage.setItem(DRAFT_KEY, JSON.stringify(draft))
  } catch (e) {
    // localStorage 不可用（如隐私模式）时静默忽略
  }
}

function loadDraft() {
  try {
    const raw = localStorage.getItem(DRAFT_KEY)
    if (!raw) return false
    const d = JSON.parse(raw)
    if (d.formData) formData.value = { ...formData.value, ...d.formData }
    if (Array.isArray(d.scripts)) scripts.value = d.scripts
    if (typeof d.selectedScriptId === 'number') selectedScriptId.value = d.selectedScriptId
    if (typeof d.selectedVoiceId === 'number') selectedVoiceId.value = d.selectedVoiceId
    if (typeof d.selectedFootageId === 'number') selectedFootageId.value = d.selectedFootageId
    if (typeof d.projectId === 'number') projectId = d.projectId
    if (typeof d.activeTaskId === 'number') activeTaskId.value = d.activeTaskId
    if (typeof d.generationActive === 'boolean') generationActive.value = d.generationActive
    if (typeof d.currentStep === 'number') currentStep.value = Math.min(d.currentStep, 3)
    return true
  } catch (e) {
    return false
  }
}

function clearDraft() {
  try {
    localStorage.removeItem(DRAFT_KEY)
  } catch (e) {
    // 忽略
  }
}

// ===== 导航控制 =====
const canNext = computed(() => {
  switch (currentStep.value) {
    case 0:
      return formData.value.topic.trim().length > 0
    case 1:
      return selectedScriptId.value !== null && !generatingScripts.value
    case 2:
      return selectedVoiceId.value !== null
    case 3:
      // 不仅要选素材，生成还需要 projectId / 文案 / 声音齐全。
      // 否则按钮「亮着但点了会因参数不全静默失败」，表现为点了没反应。
      return (
        projectId !== null &&
        selectedScriptId.value !== null &&
        selectedVoiceId.value !== null &&
        selectedFootageId.value !== null
      )
    default:
      return false
  }
})

function prevStep() {
  if (currentStep.value > 0) {
    currentStep.value--
  }
}

async function nextStep() {
  if (currentStep.value === 0) {
    // 选题 → 文案：创建项目，进入文案等待态并持续轮询生成结果
    stepLoading.value = true
    try {
      const res = await createProject('custom', formData.value.topic, formData.value.industry)
      projectId = res.project_id
      // 立即持久化 projectId：它是普通变量不在 watch 里，不主动存的话刷新后草稿里可能还是 null，
      // 会导致素材步「开始生成」按钮因参数不全灰死无法进行下一步
      saveDraft()
      // 切到文案步，由 pollScripts 驱动等待、加载动画与超时重试
      currentStep.value = 1
      await pollScripts()
    } catch (e: any) {
      ElMessage.error(e?.response?.data?.detail || '创建失败，请重试')
    } finally {
      stepLoading.value = false
    }
  } else if (currentStep.value === 1) {
    // 文案 → 声音
    currentStep.value = 2
    loadVoices()
  } else if (currentStep.value === 2) {
    // 声音 → 素材
    currentStep.value = 3
    loadFootages()
  } else if (currentStep.value === 3) {
    // 素材 → 生成
    startGeneration()
  }
}

// ===== 数据加载 =====
async function loadVoices() {
  loadingVoices.value = true
  try {
    const list = await getVoiceProfiles()
    voiceProfiles.value = list || []
    // 默认选中第一个 active 的
    if (!selectedVoiceId.value) {
      const active = voiceProfiles.value.find(v => v.status === 'active')
      if (active) selectedVoiceId.value = active.id
    }
  } catch (e) {
    console.error('加载声音列表失败', e)
  } finally {
    loadingVoices.value = false
  }
}

async function loadFootages() {
  loadingFootages.value = true
  try {
    const res = await listFootages({ page: 1, size: 20 })
    const payload = (res as any)?.data ?? res
    footages.value = payload?.items || []
  } catch (e) {
    console.error('加载素材失败', e)
  } finally {
    loadingFootages.value = false
  }
}

// ===== 视频生成 =====
let pollTimer: number | null = null

function startGeneration() {
  currentStep.value = 4
  resetGenerateUI()
  doGenerate()
}

function setStepStatus(key: string, status: string) {
  const step = generateSteps.value.find(s => s.key === key)
  if (step) step.status = status
  const done = generateSteps.value.filter(s => s.status === 'done').length
  generateProgress.value = Math.round((done / generateSteps.value.length) * 100)
}

async function doGenerate() {
  if (!projectId || !selectedScriptId.value || !selectedVoiceId.value || !selectedFootageId.value) {
    const missing: string[] = []
    if (!projectId) missing.push('项目')
    if (!selectedScriptId.value) missing.push('文案')
    if (!selectedVoiceId.value) missing.push('声音')
    if (!selectedFootageId.value) missing.push('素材')
    ElMessage.error(`生成所需参数不完整，缺少：${missing.join('、')}`)
    return
  }

  try {
    // 第一步文案已经在 step2 生成过了，标记为完成
    setStepStatus('script', 'done')

    // 调用一键生成接口
    const res = await generateVideo(projectId, {
      script_id: selectedScriptId.value,
      voice_profile_id: selectedVoiceId.value,
      footage_id: selectedFootageId.value,
      with_lipsync: true,
    })
    const taskId = res.task_id

    // 记录进行中的任务，刷新/离开页面后可恢复轮询
    activeTaskId.value = taskId
    generationActive.value = true
    saveDraft()

    // 开始轮询任务状态
    startPolling(taskId)
  } catch (e: any) {
    ElMessage.error(e?.response?.data?.detail || '生成失败，请重试')
    // 回退到上一步
    currentStep.value = 3
  }
}

function startPolling(taskId: number) {
  if (pollTimer) clearInterval(pollTimer)

  pollTimer = window.setInterval(async () => {
    try {
      const status = await getTaskStatus(taskId)

      queuePosition.value = status.queue_position ?? null
      queueEta.value = status.eta_seconds ?? null

      // 根据 progress 和状态映射到步骤
      const p = status.progress || 0
      if (status.status === 'failed') {
        generatingFailed.value = true
        failReason.value = status.error_message || '生成失败，请返回修改后重试'
        setStepStatus('tts', 'pending')
        setStepStatus('lipsync', 'pending')
        setStepStatus('render', 'pending')
        ElMessage.error(status.error_message || '生成失败')
        queuePosition.value = null
        queueEta.value = null
        generationActive.value = false
        saveDraft()
        stopPolling()
        return
      }

      if (p >= 5) setStepStatus('tts', 'doing')
      if (p >= 25) setStepStatus('tts', 'done')
      if (p >= 25) setStepStatus('lipsync', 'doing')
      if (p >= 55) setStepStatus('lipsync', 'done')
      if (p >= 55) setStepStatus('render', 'doing')

      if (status.status === 'completed' || p >= 100) {
        setStepStatus('render', 'done')
        stopPolling()
        queuePosition.value = null
        queueEta.value = null
        ElMessage.success('视频生成完成！')
        generationDone.value = true
        generationActive.value = false
        clearDraft()
        setTimeout(() => {
          if (projectId) {
            router.push(`/result?project_id=${projectId}`)
          }
        }, 1000)
      }
    } catch (e) {
      console.error('轮询失败', e)
    }
  }, 2000)
}

function stopPolling() {
  if (pollTimer) {
    clearInterval(pollTimer)
    pollTimer = null
  }
}

onMounted(() => {
  const restored = loadDraft()
  if (restored) {
    // 恢复后补齐对应步骤的列表数据，使已选声音/素材可见
    if (currentStep.value >= 2) loadVoices()
    if (currentStep.value >= 3) loadFootages()
    // 兜底：恢复后若文案列表已有但未选中（草稿 selectedScriptId 丢失），自动选第一个，
    // 否则「开始生成」按钮会因参数不全一直灰着无法进行下一步
    if (scripts.value.length > 0 && selectedScriptId.value == null) {
      selectedScriptId.value = scripts.value[0].id
    }
    // 若恢复到文案步但文案尚未生成（例如离开时仍在等待），继续轮询以免空白卡死
    if (currentStep.value === 1 && scripts.value.length === 0 && projectId != null) {
      pollScripts()
    }
  }
  // 刷新/离开页面后，若仍有进行中的生成任务，自动恢复轮询并跳结果页
  if (generationActive.value && activeTaskId.value) {
    resumeGeneration(activeTaskId.value)
  }
})

// 刷新/离开页面后恢复生成进度（口型对齐约需 1 分钟，避免用户误以为卡死而刷新丢失进度）
function resumeGeneration(taskId: number) {
  currentStep.value = 4
  resetGenerateUI()
  setStepStatus('script', 'done')
  startPolling(taskId)
}

onUnmounted(() => {
  stopPolling()
  clearScriptPolling()
  stopVoice()
  // 跳转声音训练/素材上传会卸载本页，离开前保存草稿以便返回恢复
  if (!generationDone.value) saveDraft()
})

watch(
  [formData, currentStep, selectedScriptId, selectedVoiceId, selectedFootageId, scripts],
  () => saveDraft(),
  { deep: true },
)
</script>

<style scoped>
.creation-page {
  min-height: 100vh;
  background: #f5f7fa;
  /* 预留底部：创作底栏(~64px) + 全局 Tab 栏(60px) */
  padding-bottom: 140px;
}

/* 顶部步骤条 */
.step-header {
  background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
  padding: 30px 20px 24px;
  color: #fff;
}

.queue-hint {
  margin-top: 12px;
  font-size: 13px;
  color: #8a8f99;
  text-align: center;
}

.step-progress {
  position: relative;
  display: flex;
  justify-content: space-between;
  align-items: center;
  max-width: 400px;
  margin: 0 auto 12px;
  padding: 0 10px;
}

.step-dot {
  width: 28px;
  height: 28px;
  border-radius: 50%;
  background: rgba(255, 255, 255, 0.3);
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 13px;
  font-weight: 600;
  z-index: 1;
  transition: all 0.3s;
}

.step-dot.active {
  background: #fff;
  color: #667eea;
  transform: scale(1.1);
}

.step-dot.done {
  background: #fff;
  color: #67c23a;
}

.step-line {
  position: absolute;
  top: 50%;
  left: 24px;
  height: 3px;
  background: #fff;
  transform: translateY(-50%);
  border-radius: 2px;
  transition: width 0.3s;
  z-index: 0;
  max-width: calc(100% - 48px);
}

.step-labels {
  display: flex;
  justify-content: space-between;
  max-width: 400px;
  margin: 0 auto;
  padding: 0 6px;
  font-size: 12px;
  opacity: 0.9;
}

.step-label-text {
  flex: 1;
  text-align: center;
}

/* 内容区 */
.step-content {
  padding: 20px 16px;
  max-width: 768px;
  margin: 0 auto;
}

.step-title {
  font-size: 22px;
  font-weight: 600;
  color: #303133;
  margin-bottom: 8px;
}

.step-desc {
  font-size: 14px;
  color: #909399;
  margin-bottom: 20px;
}

/* 表单卡片 */
.form-card {
  background: #fff;
  border-radius: 16px;
  padding: 20px;
  box-shadow: 0 2px 12px rgba(0, 0, 0, 0.06);
}

.form-item {
  margin-bottom: 20px;
}

.form-item:last-child {
  margin-bottom: 0;
}

.form-item label {
  display: block;
  font-size: 14px;
  font-weight: 500;
  color: #303133;
  margin-bottom: 8px;
}

.goal-options {
  display: grid;
  grid-template-columns: repeat(3, 1fr);
  gap: 10px;
}

.goal-card {
  background: #f5f7fa;
  border-radius: 12px;
  padding: 16px 8px;
  text-align: center;
  cursor: pointer;
  border: 2px solid transparent;
  transition: all 0.2s;
}

.goal-card.active {
  border-color: #667eea;
  background: #f0f2ff;
}

.goal-icon {
  font-size: 28px;
  margin-bottom: 6px;
}

.goal-text {
  font-size: 13px;
  color: #303133;
}

/* 脚本列表 */
.script-list {
  display: flex;
  flex-direction: column;
  gap: 12px;
}

.script-card {
  position: relative;
  padding: 16px;
  border: 2px solid transparent;
  cursor: pointer;
  transition: all 0.2s;
}

.script-card.active {
  border-color: #667eea;
  background: #fafbff;
}

.script-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 10px;
}

.script-tag {
  background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
  color: #fff;
  font-size: 12px;
  padding: 2px 10px;
  border-radius: 10px;
}

.script-score {
  font-size: 12px;
  color: #e6a23c;
  font-weight: 500;
}

.script-content {
  font-size: 14px;
  color: #606266;
  line-height: 1.7;
  display: -webkit-box;
  -webkit-line-clamp: 4;
  -webkit-box-orient: vertical;
  overflow: hidden;
}

.script-check {
  position: absolute;
  top: 12px;
  right: 12px;
  color: #667eea;
  font-size: 13px;
  display: flex;
  align-items: center;
  gap: 4px;
}

/* 声音列表 */
.voice-list {
  display: flex;
  flex-direction: column;
  gap: 10px;
}

.voice-card {
  position: relative;
  padding: 14px 16px;
  display: flex;
  align-items: center;
  justify-content: space-between;
  border: 2px solid transparent;
  cursor: pointer;
  transition: all 0.2s;
}

.voice-card.active {
  border-color: #667eea;
  background: #fafbff;
}

.voice-card.disabled {
  opacity: 0.6;
}

.voice-info {
  display: flex;
  align-items: center;
  gap: 12px;
}

.voice-name {
  font-size: 15px;
  font-weight: 500;
  color: #303133;
  margin-bottom: 4px;
}

.voice-check {
  color: #667eea;
}

/* 素材空态 */
.empty-state {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  gap: 10px;
  padding: 36px 16px;
  color: #909399;
  text-align: center;
}
.empty-title {
  font-size: 15px;
  font-weight: 600;
  color: #303133;
  margin: 0;
}
.empty-sub {
  font-size: 13px;
  margin: 0 0 6px;
  max-width: 240px;
  line-height: 1.5;
}

/* 素材网格 */
.footage-grid {
  display: grid;
  grid-template-columns: repeat(3, 1fr);
  gap: 10px;
}

.footage-card {
  position: relative;
  border-radius: 10px;
  overflow: hidden;
  cursor: pointer;
  border: 2px solid transparent;
  transition: all 0.2s;
  background: #fff;
}

.footage-card.active {
  border-color: #667eea;
}

.footage-cover {
  position: relative;
  aspect-ratio: 9 / 16;
  background: linear-gradient(135deg, #667eea20, #764ba220);
  display: flex;
  align-items: center;
  justify-content: center;
  color: #667eea;
}

.footage-cover img {
  width: 100%;
  height: 100%;
  object-fit: cover;
}

.footage-placeholder {
  opacity: 0.5;
}

.footage-duration {
  position: absolute;
  bottom: 6px;
  right: 6px;
  background: rgba(0, 0, 0, 0.6);
  color: #fff;
  font-size: 11px;
  padding: 2px 6px;
  border-radius: 4px;
}

.footage-name {
  padding: 6px 8px;
  font-size: 12px;
  color: #606266;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

.footage-check {
  position: absolute;
  top: 6px;
  right: 6px;
  background: #667eea;
  color: #fff;
  border-radius: 50%;
  width: 20px;
  height: 20px;
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 12px;
}

.upload-hint {
  margin-top: 16px;
  text-align: center;
}

/* 生成中 */
.step-panel.generating {
  text-align: center;
  padding-top: 40px;
}

.generating-icon {
  color: #667eea;
  margin-bottom: 24px;
}

.loading-icon {
  animation: spin 1s linear infinite;
}

@keyframes spin {
  from { transform: rotate(0deg); }
  to { transform: rotate(360deg); }
}

.step-checklist {
  margin-top: 24px;
  background: #fff;
  border-radius: 12px;
  padding: 16px;
  text-align: left;
}

.check-item {
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 10px 0;
  font-size: 14px;
  color: #c0c4cc;
  border-bottom: 1px solid #f0f0f0;
}

.check-item:last-child {
  border-bottom: none;
}

.check-item.done span {
  color: #67c23a;
}

.check-item.current span {
  color: #667eea;
  font-weight: 500;
}

.check-item.done {
  color: #67c23a;
}

.check-item.current {
  color: #667eea;
}

/* 生成失败状态 */
.fail-icon {
  color: #f56c6c;
  margin-bottom: 24px;
}

.fail-reason {
  color: #f56c6c;
  font-size: 14px;
  max-width: 480px;
  margin: 0 auto 24px;
  word-break: break-word;
  line-height: 1.6;
}

.fail-actions {
  display: flex;
  gap: 12px;
  justify-content: center;
}

.fail-actions .back-btn,
.fail-actions .retry-btn {
  flex: 1;
  max-width: 160px;
  height: 48px;
  font-size: 16px;
}

/* loading state */
.loading-state {
  text-align: center;
  padding: 60px 20px;
  color: #909399;
}

.loading-state .loading-icon {
  color: #667eea;
  margin-bottom: 16px;
}

.wait-time {
  font-size: 13px;
  color: #909399;
  margin-top: 4px;
}

.timeout-state .loading-icon {
  color: #e6a23c;
  margin-bottom: 16px;
}

.retry-script-btn {
  margin-top: 8px;
  background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
  border: none;
}

.empty-voice {
  background: #fff;
  border-radius: 12px;
  padding: 40px 20px;
}

/* 底部按钮栏 */
.step-footer {
  position: fixed;
  /* 顶到全局底部 Tab 栏(高 60px)上方，避免被其遮挡导致「下一步」不可见/不可点 */
  bottom: calc(60px + env(safe-area-inset-bottom));
  left: 0;
  right: 0;
  background: #fff;
  padding: 12px 16px;
  padding-bottom: calc(12px + env(safe-area-inset-bottom));
  border-top: 1px solid #ebeef5;
  display: flex;
  gap: 12px;
  z-index: 100;
}

.prev-btn {
  flex: 1;
  height: 48px;
  font-size: 16px;
}

.next-btn {
  flex: 2;
  height: 48px;
  font-size: 16px;
  background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
  border: none;
}

.footer-hint {
  position: absolute;
  top: -26px;
  left: 16px;
  right: 16px;
  margin: 0;
  font-size: 12px;
  color: #e6a23c;
  text-align: center;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}
</style>
