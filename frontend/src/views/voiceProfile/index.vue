<template>
  <div class="voice-page">
    <div class="page-head">
      <el-icon class="back-btn" :size="20" @click="$router.back()"><IArrowLeft /></el-icon>
      <span class="page-title">我的声音</span>
      <span class="quota">{{ profiles.length }}/3</span>
    </div>

    <!-- 录音主流程 -->
    <div v-if="!showList" class="record-flow">
      <!-- 步骤 1: 选朗读文本 -->
      <div class="step-card">
        <div class="step-head">
          <span class="step-num">1</span>
          <span class="step-title">选一段文字</span>
        </div>
        <div class="script-tabs">
          <div
            v-for="s in scripts"
            :key="s.id"
            :class="['script-tab', { active: currentScript?.id === s.id }]"
            @click="selectScript(s)"
          >
            {{ s.title }}
          </div>
        </div>
        <div class="script-text">{{ currentScript?.text }}</div>
      </div>

      <!-- 步骤 2: 录音 -->
      <div class="step-card">
        <div class="step-head">
          <span class="step-num">2</span>
          <span class="step-title">照着念一遍</span>
        </div>

        <div class="record-tips">
          <span>· 找个安静的地方</span>
          <span>· 语速自然，不用刻意</span>
          <span>· 念完整段（约 15 秒）</span>
        </div>

        <div class="record-area">
          <!-- 未录音 -->
          <template v-if="!audioBlob && !recording">
            <div class="mic-btn" @click="startRecord">
              <el-icon :size="34"><IMicrophone /></el-icon>
            </div>
            <div class="record-hint">点击开始录音</div>
          </template>

          <!-- 录音中 -->
          <template v-else-if="recording">
            <div class="mic-btn recording" @click="stopRecord">
              <el-icon :size="34"><IVideoPause /></el-icon>
            </div>
            <div class="record-timer">{{ formatSec(elapsed) }}</div>
            <div class="record-hint">点击结束录音</div>
            <div class="wave">
              <span v-for="i in 5" :key="i" class="wave-bar" :style="{ animationDelay: `${i * 0.12}s` }" />
            </div>
          </template>

          <!-- 录好了 -->
          <template v-else>
            <audio :src="audioUrl" controls class="playback" />
            <div class="record-meta">时长 {{ formatSec(recordedSec) }}</div>
            <el-button link type="primary" @click="resetRecord">重新录制</el-button>
          </template>
        </div>
      </div>

      <!-- 步骤 3: 命名并提交 -->
      <div v-if="audioBlob" class="step-card">
        <div class="step-head">
          <span class="step-num">3</span>
          <span class="step-title">给声音起个名字</span>
        </div>
        <el-input v-model="voiceName" placeholder="例如：我的声音" maxlength="20" show-word-limit />
        <el-button
          type="primary"
          class="submit-btn"
          :loading="submitting"
          :disabled="profiles.length >= 3"
          @click="handleSubmit"
        >
          {{ profiles.length >= 3 ? '已达上限（最多 3 个）' : '提交训练' }}
        </el-button>
        <div class="submit-tip">训练约需 10 秒，完成后即可用于视频配音</div>
      </div>

      <div class="switch-view">
        <el-button link @click="showList = true">
          查看我的声音（{{ profiles.length }}）
        </el-button>
      </div>
    </div>

    <!-- 声纹列表 -->
    <div v-else class="list-view">
      <el-empty v-if="profiles.length === 0" description="还没有声音，先录一段吧" />
      <div v-for="p in profiles" :key="p.id" class="voice-item">
        <div class="voice-info">
          <div class="voice-name">
            {{ p.name }}
            <el-tag :type="statusType(p.status)" size="small" effect="light">
              {{ statusLabel(p.status) }}
            </el-tag>
          </div>
          <div class="voice-meta">
            {{ formatTime(p.created_at) }}
            <span v-if="p.sample_duration">· {{ p.sample_duration }}秒</span>
          </div>
          <div v-if="p.error_message" class="voice-err">{{ p.error_message }}</div>
        </div>
        <div class="voice-ops">
          <el-button
            v-if="p.status === 'failed'"
            size="small"
            :loading="trainingId === p.id"
            @click="handleTrain(p)"
          >重试</el-button>
          <el-button size="small" :loading="testingId === p.id" @click="handleTest(p)">试听</el-button>
          <el-button size="small" type="danger" plain @click="handleDelete(p)">删除</el-button>
        </div>
        <audio v-if="demoUrls[p.id]" :src="demoUrls[p.id]" controls class="voice-audio" />
      </div>

      <div class="switch-view">
        <el-button type="primary" plain @click="backToRecord">录制新声音</el-button>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, reactive, onMounted, onUnmounted } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { IArrowLeft, IMicrophone, IVideoPause } from '@/utils/icons'
import {
  getVoiceProfiles,
  getSampleScripts,
  uploadVoiceSample,
  trainVoiceProfile,
  testVoiceProfile,
  deleteVoiceProfile,
  type VoiceProfile,
  type SampleScript,
} from '@/api/voiceProfile'

const profiles = ref<VoiceProfile[]>([])
const scripts = ref<SampleScript[]>([])
const currentScript = ref<SampleScript | null>(null)
const showList = ref(false)

const recording = ref(false)
const elapsed = ref(0)
const recordedSec = ref(0)
const audioBlob = ref<Blob | null>(null)
const audioUrl = ref('')
const voiceName = ref('')
const submitting = ref(false)
const trainingId = ref<number | null>(null)
const testingId = ref<number | null>(null)
const demoUrls = reactive<Record<number, string>>({})

let mediaRecorder: MediaRecorder | null = null
let mediaStream: MediaStream | null = null
let chunks: Blob[] = []
let timer: number | null = null

const MAX_SEC = 60

function formatSec(s: number) {
  const m = Math.floor(s / 60)
  const sec = s % 60
  return `${m}:${String(sec).padStart(2, '0')}`
}

function statusLabel(s: string) {
  return ({ training: '训练中', active: '可用', failed: '失败' } as Record<string, string>)[s] || s
}

function statusType(s: string): 'success' | 'warning' | 'danger' | 'info' {
  return ({ active: 'success', training: 'warning', failed: 'danger' } as const)[s] || 'info'
}

function formatTime(t: string | null) {
  if (!t) return ''
  return new Date(t).toLocaleDateString('zh-CN')
}

function selectScript(s: SampleScript) {
  currentScript.value = s
}

function pickMimeType() {
  const prefer = ['audio/webm;codecs=opus', 'audio/webm', 'audio/mp4']
  for (const t of prefer) {
    if (typeof MediaRecorder !== 'undefined' && MediaRecorder.isTypeSupported(t)) return t
  }
  return ''
}

async function startRecord() {
  if (!navigator.mediaDevices?.getUserMedia) {
    return ElMessage.error('当前浏览器不支持录音，请用手机 Safari 或 Chrome 打开')
  }
  try {
    mediaStream = await navigator.mediaDevices.getUserMedia({
      audio: { channelCount: 1, echoCancellation: true, noiseSuppression: true },
    })
  } catch (e: any) {
    if (e?.name === 'NotAllowedError') {
      ElMessage.error('麦克风权限被拒绝，请在浏览器设置里允许后重试')
    } else {
      ElMessage.error('无法访问麦克风：' + (e?.message || '未知错误'))
    }
    return
  }

  const mimeType = pickMimeType()
  try {
    mediaRecorder = new MediaRecorder(mediaStream, mimeType ? { mimeType } : undefined)
  } catch {
    mediaRecorder = new MediaRecorder(mediaStream)
  }

  chunks = []
  mediaRecorder.ondataavailable = (ev) => {
    if (ev.data.size > 0) chunks.push(ev.data)
  }
  mediaRecorder.onstop = () => {
    const type = mediaRecorder?.mimeType || 'audio/webm'
    const blob = new Blob(chunks, { type })
    audioBlob.value = blob
    audioUrl.value = URL.createObjectURL(blob)
    recordedSec.value = elapsed.value
    releaseStream()
  }

  mediaRecorder.start()
  recording.value = true
  elapsed.value = 0
  timer = window.setInterval(() => {
    elapsed.value += 1
    if (elapsed.value >= MAX_SEC) {
      ElMessage.info('已达最长 60 秒，自动结束')
      stopRecord()
    }
  }, 1000)
}

function stopRecord() {
  if (timer) { clearInterval(timer); timer = null }
  recording.value = false
  if (mediaRecorder?.state !== 'inactive') mediaRecorder?.stop()
}

function releaseStream() {
  mediaStream?.getTracks().forEach((t) => t.stop())
  mediaStream = null
}

function resetRecord() {
  if (audioUrl.value) URL.revokeObjectURL(audioUrl.value)
  audioBlob.value = null
  audioUrl.value = ''
  elapsed.value = 0
  recordedSec.value = 0
}

function backToRecord() {
  showList.value = false
  resetRecord()
}

function blobExt(blob: Blob) {
  if (blob.type.includes('mp4')) return 'mp4'
  if (blob.type.includes('webm')) return 'webm'
  if (blob.type.includes('ogg')) return 'ogg'
  return 'webm'
}

async function loadProfiles() {
  try {
    const res = await getVoiceProfiles()
    profiles.value = res.data || []
  } catch {
    profiles.value = []
  }
}

async function loadScripts() {
  try {
    const res = await getSampleScripts()
    scripts.value = res.data || []
    currentScript.value = scripts.value[0] || null
  } catch {
    scripts.value = []
  }
}

async function handleSubmit() {
  if (!audioBlob.value) return ElMessage.warning('请先录音')
  if (!currentScript.value) return ElMessage.warning('请选择朗读文本')
  if (recordedSec.value < 3) return ElMessage.warning('录音太短，至少 3 秒')
  if (!voiceName.value.trim()) return ElMessage.warning('请给声音起个名字')

  const fd = new FormData()
  fd.append('file', audioBlob.value, `recording.${blobExt(audioBlob.value)}`)
  fd.append('name', voiceName.value.trim())
  // 参考文本 = 用户朗读的示例文本, 保证 WER 校验通过
  fd.append('reference_text', currentScript.value.text)
  fd.append('demo_text', '你好，这是我的声音，很高兴认识你。')
  fd.append('language', '0')

  submitting.value = true
  try {
    const res = await uploadVoiceSample(fd)
    const p = res.data
    if (p.status === 'active') {
      ElMessage.success('训练成功！现在可以用你的声音配音了')
    } else if (p.status === 'failed') {
      ElMessage.error(p.error_message || '训练失败，请重新录制')
    } else {
      ElMessage.info('已提交，训练中...')
    }
    await loadProfiles()
    resetRecord()
    voiceName.value = ''
    showList.value = true
  } catch (e: any) {
    ElMessage.error(e?.response?.data?.detail || '提交失败')
  } finally {
    submitting.value = false
  }
}

async function handleTrain(p: VoiceProfile) {
  trainingId.value = p.id
  try {
    await trainVoiceProfile(p.id)
    await loadProfiles()
    ElMessage.success('已重新提交训练')
  } catch (e: any) {
    ElMessage.error(e?.response?.data?.detail || '训练失败')
  } finally {
    trainingId.value = null
  }
}

async function handleTest(p: VoiceProfile) {
  testingId.value = p.id
  try {
    const res = await testVoiceProfile(p.id, '你好，这是我的声音，很高兴认识你。')
    demoUrls[p.id] = `${res.data.audio_url}?t=${Date.now()}`
  } catch (e: any) {
    ElMessage.error(e?.response?.data?.detail || '试听失败')
  } finally {
    testingId.value = null
  }
}

async function handleDelete(p: VoiceProfile) {
  try {
    await ElMessageBox.confirm(`删除「${p.name}」？`, '确认', { type: 'warning' })
  } catch { return }
  try {
    await deleteVoiceProfile(p.id)
    ElMessage.success('已删除')
    await loadProfiles()
  } catch (e: any) {
    ElMessage.error(e?.response?.data?.detail || '删除失败')
  }
}

onMounted(async () => {
  await Promise.all([loadProfiles(), loadScripts()])
  if (profiles.value.length > 0) showList.value = true
})

onUnmounted(() => {
  if (timer) clearInterval(timer)
  releaseStream()
  if (audioUrl.value) URL.revokeObjectURL(audioUrl.value)
})
</script>

<style scoped>
.voice-page { padding: 12px; padding-bottom: 80px; max-width: 560px; margin: 0 auto; }
.page-head {
  display: flex; align-items: center; gap: 10px;
  padding: 4px 0 14px; position: relative;
}
.back-btn { cursor: pointer; color: #606266; }
.page-title { font-size: 17px; font-weight: 600; }
.quota { margin-left: auto; font-size: 13px; color: #909399; }

.step-card {
  background: #fff; border-radius: 12px; padding: 16px;
  margin-bottom: 12px; box-shadow: 0 1px 6px rgba(0,0,0,.05);
}
.step-head { display: flex; align-items: center; gap: 8px; margin-bottom: 12px; }
.step-num {
  width: 20px; height: 20px; border-radius: 50%;
  background: #409eff; color: #fff; font-size: 12px;
  display: flex; align-items: center; justify-content: center; flex-shrink: 0;
}
.step-title { font-size: 15px; font-weight: 600; }

.script-tabs { display: flex; gap: 8px; margin-bottom: 12px; }
.script-tab {
  padding: 5px 12px; border-radius: 14px; font-size: 13px;
  background: #f4f4f5; color: #606266; cursor: pointer; white-space: nowrap;
}
.script-tab.active { background: #409eff; color: #fff; }
.script-text {
  font-size: 16px; line-height: 1.9; color: #303133;
  background: #fafafa; padding: 14px; border-radius: 8px;
  letter-spacing: .5px;
}

.record-tips {
  display: flex; flex-direction: column; gap: 3px;
  font-size: 12px; color: #909399; margin-bottom: 16px;
}
.record-area {
  display: flex; flex-direction: column; align-items: center;
  gap: 10px; padding: 10px 0;
}
.mic-btn {
  width: 74px; height: 74px; border-radius: 50%;
  background: #409eff; color: #fff;
  display: flex; align-items: center; justify-content: center;
  cursor: pointer; transition: transform .15s;
  box-shadow: 0 3px 14px rgba(64,158,255,.35);
}
.mic-btn:active { transform: scale(.94); }
.mic-btn.recording {
  background: #f56c6c; box-shadow: 0 3px 14px rgba(245,108,108,.4);
  animation: pulse 1.4s ease-in-out infinite;
}
@keyframes pulse {
  0%, 100% { box-shadow: 0 3px 14px rgba(245,108,108,.4); }
  50% { box-shadow: 0 3px 22px rgba(245,108,108,.75); }
}
.record-hint { font-size: 13px; color: #909399; }
.record-timer { font-size: 22px; font-weight: 600; color: #f56c6c; font-variant-numeric: tabular-nums; }
.record-meta { font-size: 13px; color: #606266; }
.playback { width: 100%; height: 38px; }

.wave { display: flex; gap: 3px; align-items: flex-end; height: 20px; }
.wave-bar {
  width: 3px; background: #f56c6c; border-radius: 2px;
  animation: wave .9s ease-in-out infinite;
}
@keyframes wave {
  0%, 100% { height: 5px; }
  50% { height: 20px; }
}

.submit-btn { width: 100%; margin-top: 12px; }
.submit-tip { font-size: 12px; color: #909399; text-align: center; margin-top: 8px; }
.switch-view { text-align: center; padding: 8px 0; }

.voice-item {
  background: #fff; border-radius: 12px; padding: 14px; margin-bottom: 10px;
  display: flex; flex-wrap: wrap; gap: 10px; align-items: center;
  box-shadow: 0 1px 6px rgba(0,0,0,.05);
}
.voice-info { flex: 1; min-width: 150px; }
.voice-name { font-weight: 600; display: flex; align-items: center; gap: 7px; margin-bottom: 3px; }
.voice-meta { font-size: 12px; color: #909399; }
.voice-err { font-size: 12px; color: #f56c6c; margin-top: 3px; }
.voice-ops { display: flex; gap: 5px; }
.voice-audio { width: 100%; height: 34px; margin-top: 6px; }
</style>
