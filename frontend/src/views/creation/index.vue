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
              :placeholder="topicHint.placeholder"
              maxlength="100"
              show-word-limit
              size="large"
            />
            <div class="persona-tags">
              <span
                v-for="t in topicHint.topics"
                :key="t"
                class="persona-tag"
                :class="{ active: formData.topic === t }"
                @click="formData.topic = t"
              >{{ t }}</span>
            </div>
          </div>

          <div class="form-item">
            <label>目标平台</label>
            <el-select v-model="formData.platform" size="large">
              <el-option v-for="p in platformOptions" :key="p.value" :label="p.label" :value="p.value" />
            </el-select>
          </div>

          <div class="form-item">
            <label>主播人设（可选）</label>
            <el-input
              v-model="formData.persona"
              placeholder="例如：温暖亲切的40+姐姐 / 专业营养师 / 幽默老铁"
              maxlength="50"
              size="large"
            />
            <div class="persona-tags">
              <span
                v-for="p in personaOptions"
                :key="p"
                class="persona-tag"
                :class="{ active: personaList.includes(p) }"
                @click="togglePersona(p)"
              >{{ p }}</span>
            </div>
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
              <el-tooltip v-if="editingScriptId !== s.id" content="编辑文案" placement="top">
                <button class="script-edit-btn" @click.stop="startEditScript(s)">
                  <el-icon><IEdit /></el-icon>
                </button>
              </el-tooltip>
            </div>

            <template v-if="editingScriptId === s.id">
              <textarea
                ref="scriptEditor"
                v-model="editingContent"
                class="script-editor"
                rows="10"
                @click.stop
                @keydown.stop
              ></textarea>
              <div class="script-edit-actions" @click.stop>
                <span class="script-edit-count">{{ editingContent.length }} 字</span>
                <button class="script-edit-cancel" @click="cancelEditScript">取消</button>
                <button
                  class="script-edit-save"
                  :disabled="savingScript || !editingContent.trim()"
                  @click="saveEditScript(s)"
                >
                  {{ savingScript ? '保存中...' : '保存' }}
                </button>
              </div>
            </template>
            <template v-else>
              <div class="script-content">{{ s.content }}</div>
              <div class="script-check" v-if="selectedScriptId === s.id">
                <el-icon><ICheck /></el-icon> 已选择
              </div>
            </template>
          </div>
        </div>
      </div>

      <!-- Step 3: 选择声音 -->
      <div v-if="currentStep === 2" class="step-panel">
        <div class="voice-step-header">
          <div>
            <h2 class="step-title">选择主播声音</h2>
            <p class="step-desc">用克隆的声音来生成配音</p>
          </div>
          <el-button type="primary" plain @click="goToVoicePage">克隆新声音</el-button>
        </div>

        <div v-if="loadingVoices" class="loading-state">
          <el-icon class="loading-icon" :size="32"><ILoading /></el-icon>
          <p>加载中...</p>
        </div>

        <div v-else-if="voiceProfiles.length === 0" class="empty-voice">
          <el-empty description="还没有声音模型">
            <el-button type="primary" @click="goToVoicePage">去克隆声音</el-button>
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

      <!-- Step 4: 主播照片 + 场景（H3 图生视频） -->
      <div v-if="currentStep === 3" class="step-panel">
        <h2 class="step-title">上传主播照片</h2>
        <p class="step-desc">上传一张主播正面清晰照片，AI 将以照片为人像直接图生视频（脸和发型由照片锁定）</p>

        <el-upload
          class="portrait-uploader"
          :show-file-list="false"
          :before-upload="() => false"
          :on-change="handlePortraitChange"
          accept="image/jpeg,image/png,image/webp"
        >
          <div class="portrait-box" :class="{ active: !!personImage }">
            <img v-if="personPreview" :src="personPreview" alt="主播照片" class="portrait-img" />
            <div v-else class="portrait-empty">
              <el-icon :size="40"><IVideoCamera /></el-icon>
              <p class="empty-title" style="margin-top:10px">点击上传主播照片</p>
              <p class="empty-sub">正面、光线清晰的半身照，jpg / png</p>
            </div>
            <div v-if="uploadingPortrait" class="portrait-mask">
              <el-icon class="loading-icon" :size="28"><ILoading /></el-icon>
            </div>
          </div>
        </el-upload>

        <p class="library-link">
          <el-button link type="primary" size="small" @click="goToH3Library">
            从「人物 / 场景素材库」选已有照片与场景 →
          </el-button>
        </p>

        <h3 class="scene-title">选择讲解场景</h3>
        <div class="scene-grid">
          <div
            v-for="opt in sceneOptions"
            :key="opt.value"
            class="scene-card"
            :class="{ active: selectedScene === opt.value }"
            @click="selectedScene = opt.value"
          >
            <div class="scene-label">{{ opt.label }}</div>
            <div class="scene-desc">{{ opt.desc }}</div>
            <div v-if="selectedScene === opt.value" class="footage-check">
              <el-icon><ICheck /></el-icon>
            </div>
          </div>
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
      <p v-if="nextHint" class="footer-hint">{{ nextHint }}</p>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, onMounted, onUnmounted, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { useUserStore } from '@/stores/user'
import { queueHintText } from '@/utils/queue'
import { ElMessage } from 'element-plus'
import {
  ILoading,
  ICheck,
  IEdit,
  IVideoCamera,
  IVideoPlay,
  ICircleCheck,
  IClock,
  ICircleClose,
} from '@/utils/icons'
import { createProject, getProjectScripts, getTaskStatus, updateScript } from '@/api/creation'
import { generateVideo } from '@/api/video'
import { getVoiceProfiles, testVoiceProfile, type VoiceProfile } from '@/api/voiceProfile'
import { uploadAnchorPortrait } from '@/api/footage'
import { signedMediaUrl, storagePathOf } from '@/utils/mediaUrl'

const route = useRoute()
const router = useRouter()

const steps = [
  { key: 'topic', label: '选题' },
  { key: 'script', label: '文案' },
  { key: 'voice', label: '声音' },
  { key: 'footage', label: '形象' },
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
const platformOptions = [
  { value: '抖音', label: '抖音' },
  { value: '视频号', label: '视频号' },
  { value: '小红书', label: '小红书' },
  { value: '快手', label: '快手' },
]
const industryTopicHints: Record<string, { placeholder: string; topics: string[] }> = {
  '健康养生': { placeholder: '例如：肠胃不好怎么调理、更年期失眠怎么改善', topics: ['肠胃不好怎么调理', '更年期失眠怎么改善', '湿气重怎么调理', '血脂高怎么降'] },
  '美妆护肤': { placeholder: '例如：敏感肌怎么修护、30+精简护肤步骤', topics: ['敏感肌怎么修护', '30+精简护肤', '防晒到底怎么选', '秋冬皮肤干燥怎么办'] },
  '美食餐饮': { placeholder: '例如：早餐怎么吃更健康、低脂家常菜做法', topics: ['早餐怎么吃更健康', '低脂家常菜做法', '外卖怎么点更健康', '养生汤怎么煲'] },
  '教育培训': { placeholder: '例如：孩子专注力怎么练、英语启蒙怎么做', topics: ['孩子专注力怎么练', '英语启蒙怎么做', '家长如何高效辅导', '学习方法怎么选'] },
  '生活情感': { placeholder: '例如：夫妻关系怎么经营、焦虑怎么缓解', topics: ['夫妻关系怎么经营', '焦虑怎么缓解', '独居生活怎么过', '情绪内耗怎么办'] },
  '职场成长': { placeholder: '例如：职场晋升怎么准备、如何和领导沟通', topics: ['职场晋升怎么准备', '如何和领导沟通', '副业怎么选', '时间管理怎么做'] },
  '母婴育儿': { placeholder: '例如：宝宝辅食怎么做、断夜奶怎么戒', topics: ['宝宝辅食怎么做', '断夜奶怎么戒', '哄睡技巧分享', '宝宝免疫力怎么养'] },
  '家居生活': { placeholder: '例如：小户型收纳技巧、厨房清洁妙招', topics: ['小户型收纳技巧', '厨房清洁妙招', '绿植怎么养', '清洁收纳好物'] },
  '其他': { placeholder: '例如：生活小妙招、实用技巧分享', topics: ['生活小妙招', '实用技巧分享', '日常经验总结', '新手入门指南'] },
}
const personaOptions = [
  '温暖亲切的40+姐姐', '专业营养师', '中医养生顾问', '知心大姐',
  '高知健康专家', '邻家阿姨', '元气活力姐姐', '职场女强人',
  '宝妈营养师', '时尚健康博主', '严谨老干部', '懂生活的老闺蜜',
  '治愈系声音主播', '靠谱生活顾问',
]
const formData = ref({
  industry: '健康养生',
  topic: '',
  goal: 'followers',
  platform: '抖音',
  persona: '',
})
const topicHint = computed(() => {
  const h = industryTopicHints[formData.value.industry] || industryTopicHints['其他']
  return h
})
const personaList = computed(() =>
  formData.value.persona.split(/[、，,/\s]+/).filter(Boolean))

function togglePersona(p: string) {
  const current = personaList.value
  const next = current.includes(p)
    ? current.filter(x => x !== p)
    : [...current, p]
  formData.value.persona = next.join('、')
}

// ===== Step 2: 脚本 =====
const scripts = ref<any[]>([])
const selectedScriptId = ref<number | null>(null)

// 文案就地编辑。AI 写出来的文案常带镜头备注或个别措辞要改，
// 之前只能整条重新生成，改一个词也要等一轮 AI。
const editingScriptId = ref<number | null>(null)
const editingContent = ref('')
const savingScript = ref(false)

function startEditScript(s: any) {
  // 编辑的同时选中它，避免出现"编辑了 A 却生成 B"的错位
  selectedScriptId.value = s.id
  editingScriptId.value = s.id
  editingContent.value = s.content || ''
}

function cancelEditScript() {
  editingScriptId.value = null
  editingContent.value = ''
}

async function saveEditScript(s: any) {
  const text = editingContent.value.trim()
  if (!text) {
    ElMessage.warning('文案不能为空')
    return
  }
  savingScript.value = true
  try {
    const updated = await updateScript(s.id, text)
    // 就地更新本地列表，避免整页刷新丢掉当前步骤
    s.content = updated?.content ?? text
    editingScriptId.value = null
    editingContent.value = ''
    ElMessage.success('文案已保存')
  } catch (e: any) {
    ElMessage.error(e?.response?.data?.detail || '保存失败，请稍后重试')
  } finally {
    savingScript.value = false
  }
}
const generatingScripts = ref(false)
const scriptWaitSeconds = ref(0)      // 文案生成已等待秒数
const scriptTimeout = ref(false)      // 5分钟仍无文案时为 true
let projectId: number | null = null
let scriptPollTimer: number | null = null
let scriptWaitTimer: number | null = null
const SCRIPT_POLL_INTERVAL = 3000     // 每 3 秒轮询一次
const SCRIPT_MAX_WAIT = 300000        // 最长等待 5 分钟（云端文案多次调用较慢）

function pollDelayMs(baseMs: number): number {
  return document.visibilityState === 'hidden' ? baseMs * 5 : baseMs
}

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

  // 立即查一次，之后每 3 秒轮询；切到后台自动降频，直到文案出现
  const schedule = async () => {
    if (done) return
    await check()
    if (!done) {
      scriptPollTimer = window.setTimeout(schedule, pollDelayMs(SCRIPT_POLL_INTERVAL))
    }
  }
  await schedule()
}

async function regenerateScripts() {
  // 同一主题重新创建项目并触发文案生成，再继续轮询
  stepLoading.value = true
  try {
    const res = await createProject(
      'custom',
      formData.value.topic,
      formData.value.industry,
      formData.value.platform,
      formData.value.persona,
    )
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
    if (v.status === 'failed') {
      ElMessage.warning('该声音克隆失败，请重新录制后使用')
    } else {
      ElMessage.warning('该声音模型还在克隆中，请稍后刷新')
    }
    return
  }
  selectedVoiceId.value = v.id
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
    audioEl = new Audio(await signedMediaUrl(storagePathOf(res.audio_url)))
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

// ===== Step 4: 主播照片 + 场景（H3 图生视频）=====
// 说明：视频素材（footage）链路已下线。那条链路要求先上传实拍视频再做口型同步，
// 实测一直走不通，且「生成视频」按钮会因缺素材直接报错、用户找不到上传入口。
// 现在唯一的成片链路是「照片 + 场景」图生视频，所以这里不再维护素材选择状态。
const personImage = ref<string>('')
const personPreview = ref<string>('')
const uploadingPortrait = ref(false)
const sceneOptions = [
  { value: 'lecture', label: '会场讲课', desc: '讲台半身口播，专业稳重' },
  { value: 'park_walk', label: '公园散步', desc: '边走边讲，轻松自然' },
  { value: 'teahouse', label: '茶室座谈', desc: '茶室坐着讲，温暖亲切' },
  { value: 'street_walk', label: '商业街', desc: '街头行走讲解，有活力' },
  { value: 'kitchen', label: '厨房演示', desc: '居家厨房场景，生活化演示' },
  { value: 'office', label: '办公室', desc: '办公桌旁专业讲解' },
  { value: 'living_room', label: '客厅居家', desc: '沙发居家口播，亲切自然' },
  { value: 'balcony_garden', label: '阳台花园', desc: '阳台绿植背景，清爽明亮' },
  { value: 'study', label: '书房书柜', desc: '书柜背景，适合知识科普' },
  { value: 'cafe', label: '咖啡店', desc: '咖啡桌边聊天式口播' },
  { value: 'gym', label: '健身房', desc: '运动场景，健康活力' },
]
const selectedScene = ref<string>('lecture')

// 从 H3 人物/场景素材库读取已选的主播照片与场景
async function applyH3LibraryPreselect() {
  const storedPerson = localStorage.getItem('h3_person_image')
  if (!personImage.value && storedPerson) {
    personImage.value = storedPerson
    const rel = storedPerson.replace(/^storage\//, '')
    personPreview.value = await signedMediaUrl(rel)
  }
  const storedScene = localStorage.getItem('h3_scene')
  if (storedScene && sceneOptions.some(o => o.value === storedScene)) {
    selectedScene.value = storedScene
  }
}

async function handlePortraitChange(file: any) {
  const f = file?.raw || file
  if (!f) return
  if (!/image\/(jpeg|png|webp)/.test(f.type)) {
    ElMessage.error('请上传 jpg / png / webp 格式的照片')
    return
  }
  uploadingPortrait.value = true
  try {
    // 本地预览
    personPreview.value = URL.createObjectURL(f)
    const res = await uploadAnchorPortrait(f)
    personImage.value = res.person_image
    ElMessage.success('主播照片已上传')
  } catch (e: any) {
    ElMessage.error(e?.response?.data?.detail || '照片上传失败')
    personImage.value = ''
    personPreview.value = ''
  } finally {
    uploadingPortrait.value = false
  }
}

function goToH3Library() {
  saveDraft()
  router.push('/h3-library')
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

const queueHint = computed(() =>
  queueHintText(queuePosition.value, queueEta.value))

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
  if (!projectId || !selectedScriptId.value || !selectedVoiceId.value || !personImage.value) {
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

// ===== 外部入口带参跳入 =====
// 两处入口会往 /creation 传 query，但本页此前没有 useRoute，参数全被丢弃：
//   · 首页「今日推荐」→ /creation?type=custom&topic=xxx  → 主题框空白，用户以为跳错了
//   · H3 素材库    → /creation?step=3                     → 仍停在选题步
// 这里统一消费这两个参数。
const TOPIC_MAX = 100 // 与模板 textarea 的 maxlength 保持一致

// 推荐选题自带的分类 → 本页行业类型。
// 只有默认值「健康养生」时，美妆/母婴等选题会带着错误的行业上下文去生成文案。
// 匹配不到就保持原值，不猜。
const CATEGORY_TO_INDUSTRY: Array<[RegExp, string]> = [
  [/养生|健康|中医|营养|医药/, '健康养生'],
  [/美妆|护肤|彩妆|美容/, '美妆护肤'],
  [/美食|餐饮|菜谱|烘焙/, '美食餐饮'],
  [/教育|培训|学习|升学|英语/, '教育培训'],
  [/情感|心理|两性|夫妻|生活/, '生活情感'],
  [/职场|成长|副业|管理/, '职场成长'],
  [/母婴|育儿|宝宝|亲子/, '母婴育儿'],
  [/家居|收纳|装修|清洁/, '家居生活'],
]

function matchIndustry(category: string): string {
  for (const [re, industry] of CATEGORY_TO_INDUSTRY) {
    if (re.test(category)) return industry
  }
  return ''
}

function applyRouteQuery() {
  const topic = String(route.query.topic || '').trim()
  let resetForNewTopic = false

  if (topic) {
    const draftTopic = (formData.value.topic || '').trim()
    // 超长标题（推荐选题常是一整句话）按输入框上限截断，避免计数器爆表
    formData.value.topic = topic.length > TOPIC_MAX ? topic.slice(0, TOPIC_MAX) : topic

    // 行业随选题一起带过来，保证 AI 拿到正确的行业上下文
    const industry = matchIndustry(String(route.query.category || ''))
    if (industry) formData.value.industry = industry

    if (draftTopic !== topic) {
      // 换了选题 ⇒ 这是一次新的创作。
      // 旧项目的文案与 projectId 必须清掉，否则会出现「主题是新的、文案是旧的」错位。
      // 声音与形象的选择和主题无关，保留下来免得用户重选。
      scripts.value = []
      selectedScriptId.value = null
      projectId = null
      activeTaskId.value = null
      generationActive.value = false
      currentStep.value = 0
      clearDraft()
      resetForNewTopic = true
    }
  }

  // step=N 直达指定步骤。生成中的任务优先级更高（onMounted 末尾的 resumeGeneration 会覆盖），
  // 所以这里跳过，避免把用户从进度页拽回来
  const stepRaw = Number(route.query.step)
  let jumpedToStep = false
  if (!resetForNewTopic && !generationActive.value &&
      Number.isInteger(stepRaw) && stepRaw > 0) {
    // 最多跳到素材步（3）；「生成」步（4）只能由流程驱动
    currentStep.value = Math.min(stepRaw, 3)
    jumpedToStep = true
  }

  return { hasQuery: !!(route.query.topic || route.query.step), resetForNewTopic, jumpedToStep }
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
        !!personImage.value
      )
    default:
      return false
  }
})

// 按钮为什么点不动 —— 不能只把按钮置灰就完事，否则用户看到的就是「点了没反应」。
// 每一步说清当前缺什么，用户才知道该做什么。
const nextHint = computed(() => {
  if (canNext.value) return ''
  switch (currentStep.value) {
    case 0:
      return '请先填写视频主题，再点「下一步」'
    case 1:
      return generatingScripts.value ? 'AI 正在生成文案，请稍候…' : '请先选择一个文案版本'
    case 2:
      return '请先选择或克隆一个声音'
    case 3:
      return !personImage.value
        ? '请先上传一张主播照片，再点击「开始生成」'
        : '请先返回完成前序步骤（选题 / 文案 / 声音）'
    default:
      return ''
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
      const res = await createProject(
        'custom',
        formData.value.topic,
        formData.value.industry,
        formData.value.platform,
        formData.value.persona,
      )
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
    // 声音 → 照片/场景
    currentStep.value = 3
    applyH3LibraryPreselect()
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
  if (!projectId || !selectedScriptId.value || !selectedVoiceId.value || !personImage.value) {
    const missing: string[] = []
    if (!projectId) missing.push('项目')
    if (!selectedScriptId.value) missing.push('文案')
    if (!selectedVoiceId.value) missing.push('声音')
    if (!personImage.value) missing.push('主播照片')
    ElMessage.error(`生成所需参数不完整，缺少：${missing.join('、')}`)
    return
  }

  try {
    // H3 主链路没有独立配音/口型步骤，进度按 文案→画面→字幕 展示
    generateSteps.value = personImage.value ? [
      { key: 'script', label: '生成文案', status: 'pending' },
      { key: 'h3', label: '生成画面', status: 'pending' },
      { key: 'subtitle', label: '合成字幕', status: 'pending' },
    ] : [
      { key: 'script', label: '生成文案', status: 'pending' },
      { key: 'tts', label: '生成配音', status: 'pending' },
      { key: 'lipsync', label: '对齐口型', status: 'pending' },
      { key: 'render', label: '合成视频', status: 'pending' },
    ]
    // 第一步文案已经在 step2 生成过了，标记为完成
    setStepStatus('script', 'done')

    // 调用一键生成接口
    const res = await generateVideo(projectId, {
      script_id: selectedScriptId.value,
      voice_profile_id: selectedVoiceId.value,
      with_lipsync: false,
      person_image: personImage.value,
      scene: selectedScene.value,
      anchor_image: localStorage.getItem('h3_anchor_image') || undefined,
      width: 512,
      height: 960,
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
  if (pollTimer) clearTimeout(pollTimer)

  const tick = async () => {
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

      if (personImage.value) {
        // H3: 5% 准备文案 -> 15% 生成画面 -> 90% 合成字幕 -> 100% 完成
        if (p >= 15) setStepStatus('script', 'done')
        if (p >= 15) setStepStatus('h3', 'doing')
        if (p >= 90) {
          setStepStatus('h3', 'done')
          setStepStatus('subtitle', 'doing')
        }
      } else {
        if (p >= 5) setStepStatus('tts', 'doing')
        if (p >= 25) setStepStatus('tts', 'done')
        if (p >= 25) setStepStatus('lipsync', 'doing')
        if (p >= 55) setStepStatus('lipsync', 'done')
        if (p >= 55) setStepStatus('render', 'doing')
      }

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
    if (pollTimer !== null) {
      pollTimer = window.setTimeout(tick, pollDelayMs(5000))
    }
  }
  pollTimer = window.setTimeout(tick, pollDelayMs(5000))
}

function stopPolling() {
  if (pollTimer) {
    clearInterval(pollTimer)
    pollTimer = null
  }
}

onMounted(() => {
  const restored = loadDraft()

  // 外部带参跳入必须放在草稿恢复之后：同一选题延续进度，换了选题则开一次新的创作
  const nav = applyRouteQuery()

  // 按最终所在步骤补齐列表数据，使已选声音可见
  if (currentStep.value >= 2) loadVoices()

  if (nav.resetForNewTopic) {
    ElMessage.success('已填入推荐选题，确认后点「下一步」')
  } else if (restored) {
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
  applyH3LibraryPreselect()

  // 一次性跳转参数消费完即清，避免刷新时重复触发
  if (nav.hasQuery) {
    router.replace({ path: '/creation' })
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
  [formData, currentStep, selectedScriptId, selectedVoiceId, scripts],
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
.voice-step-header {
  display: flex; align-items: flex-start; justify-content: space-between; gap: 12px;
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
.persona-tags {
  display: flex; flex-wrap: wrap; gap: 8px; margin-top: 10px;
}
.persona-tag {
  background: #f5f7fa; color: #606266; border: 1px solid #dcdfe6;
  border-radius: 14px; padding: 4px 12px; font-size: 13px;
  cursor: pointer; transition: all .15s;
}
.persona-tag:hover { border-color: #409eff; color: #409eff; background: #ecf5ff; }
.persona-tag.active { border-color: #409eff; color: #fff; background: #409eff; }

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

/* 文案就地编辑 */
.script-edit-btn {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  width: 26px;
  height: 26px;
  padding: 0;
  border: 1px solid #dcdfe6;
  border-radius: 6px;
  background: #fff;
  color: #909399;
  cursor: pointer;
  transition: color 0.15s, border-color 0.15s;
}

.script-edit-btn:hover {
  color: #667eea;
  border-color: #667eea;
}

.script-editor {
  width: 100%;
  box-sizing: border-box;
  font-family: inherit;
  font-size: 14px;
  line-height: 1.7;
  color: #303133;
  padding: 10px 12px;
  border: 1px solid #667eea;
  border-radius: 6px;
  resize: vertical;
  outline: none;
}

.script-edit-actions {
  display: flex;
  align-items: center;
  justify-content: flex-end;
  gap: 10px;
  margin-top: 10px;
}

.script-edit-count {
  margin-right: auto;
  font-size: 12px;
  color: #909399;
}

.script-edit-cancel,
.script-edit-save {
  padding: 6px 16px;
  font-size: 13px;
  border-radius: 6px;
  cursor: pointer;
  border: 1px solid #dcdfe6;
  background: #fff;
  color: #606266;
}

.script-edit-save {
  border-color: #667eea;
  background: #667eea;
  color: #fff;
}

.script-edit-save:disabled {
  opacity: 0.6;
  cursor: not-allowed;
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

/* 人物/场景素材库入口 */
.library-link {
  text-align: center;
  margin: 10px 0 0;
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

.portrait-uploader { display:flex; justify-content:center; margin-bottom:24px; }
.portrait-box {
  width: 220px; height: 300px; border-radius: 16px; border: 2px dashed #c0c4cc;
  display:flex; align-items:center; justify-content:center; overflow:hidden;
  position:relative; cursor:pointer; background:#fafafa; transition:border-color .2s;
}
.portrait-box:hover, .portrait-box.active { border-color:#667eea; }
.portrait-img { width:100%; height:100%; object-fit:cover; }
.portrait-empty { text-align:center; color:#909399; padding:0 12px; }
.portrait-mask { position:absolute; inset:0; background:rgba(255,255,255,.7); display:flex; align-items:center; justify-content:center; }
.scene-title { font-size:16px; font-weight:600; margin:8px 0 12px; text-align:center; }
.scene-grid { display:grid; grid-template-columns:1fr 1fr; gap:12px; }
.scene-card {
  position:relative; border:2px solid #e4e7ed; border-radius:12px; padding:16px; cursor:pointer;
  transition:all .2s; background:#fff;
}
.scene-card:hover { border-color:#a3aef5; }
.scene-card.active { border-color:#667eea; background:#f5f7ff; }
.scene-label { font-weight:600; font-size:15px; margin-bottom:4px; }
.scene-desc { font-size:12px; color:#909399; }

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
