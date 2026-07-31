<template>
  <div class="voice-profile-page">
    <div class="page-header">
      <el-page-header @back="$router.back()">
        <template #content>
          <span class="page-title">🎙️ 我的声音</span>
        </template>
      </el-page-header>
    </div>

    <el-alert
      v-if="notConfigured"
      type="warning"
      :closable="false"
      show-icon
      class="tip-alert"
    >
      <template #title>声纹克隆服务未就绪</template>
      当前使用系统兜底配音。声纹训练需要火山方舟音色资源授权完成后生效。
    </el-alert>

    <el-card class="upload-card" shadow="never">
      <template #header>
        <div class="card-header">
          <span>上传声音样本</span>
          <span class="quota">{{ profiles.length }} / 3</span>
        </div>
      </template>

      <el-form :model="form" label-width="90px" label-position="top">
        <el-form-item label="声音名称" required>
          <el-input v-model="form.name" placeholder="例如：我的标准女声" maxlength="100" />
        </el-form-item>

        <el-form-item label="音频样本" required>
          <el-upload
            ref="uploadRef"
            :auto-upload="false"
            :limit="1"
            accept=".mp3,.wav,.m4a,.ogg,.aac"
            :on-change="onFileChange"
            :on-remove="onFileRemove"
            drag
          >
            <el-icon class="upload-icon"><IUploadFilled /></el-icon>
            <div class="upload-text">点击或拖拽上传音频</div>
            <template #tip>
              <div class="upload-tip">
                支持 mp3 / wav / m4a / ogg / aac，最大 10MB<br />
                建议 10-30 秒清晰朗读，环境安静无杂音
              </div>
            </template>
          </el-upload>
        </el-form-item>

        <el-form-item label="参考文本">
          <el-input
            v-model="form.reference_text"
            type="textarea"
            :rows="2"
            placeholder="选填。样本中实际朗读的文字，可提升克隆准确度"
          />
        </el-form-item>

        <el-form-item label="试听文本" required>
          <el-input
            v-model="form.demo_text"
            type="textarea"
            :rows="2"
            maxlength="300"
            show-word-limit
            placeholder="训练完成后用这段文字生成试听音频（4-300 字）"
          />
        </el-form-item>

        <el-button
          type="primary"
          :loading="uploading"
          :disabled="profiles.length >= 3"
          @click="handleUpload"
        >
          {{ profiles.length >= 3 ? '已达上限（最多 3 个）' : '上传并开始训练' }}
        </el-button>
      </el-form>
    </el-card>

    <el-card class="list-card" shadow="never">
      <template #header>
        <div class="card-header">
          <span>我的声纹</span>
          <el-button link :icon="IRefresh" @click="loadProfiles">刷新</el-button>
        </div>
      </template>

      <el-empty v-if="!loading && profiles.length === 0" description="还没有声纹，上传一段录音开始" />

      <div v-else class="profile-list">
        <div v-for="p in profiles" :key="p.id" class="profile-item">
          <div class="profile-main">
            <div class="profile-name">
              {{ p.name }}
              <el-tag :type="statusType(p.status)" size="small" effect="light">
                {{ statusLabel(p.status) }}
              </el-tag>
            </div>
            <div class="profile-meta">
              创建于 {{ formatTime(p.created_at) }}
              <span v-if="p.available_training_times > 0">
                · 剩余训练 {{ p.available_training_times }} 次
              </span>
            </div>
            <div v-if="p.error_message" class="profile-error">{{ p.error_message }}</div>
          </div>

          <div class="profile-actions">
            <el-button
              v-if="p.status !== 'active'"
              size="small"
              :loading="trainingId === p.id"
              @click="handleTrain(p)"
            >
              {{ p.status === 'failed' ? '重新训练' : '训练' }}
            </el-button>
            <el-button size="small" :loading="testingId === p.id" @click="handleTest(p)">
              试听
            </el-button>
            <el-button size="small" type="danger" plain @click="handleDelete(p)">删除</el-button>
          </div>

          <audio
            v-if="audioUrls[p.id]"
            :src="audioUrls[p.id]"
            controls
            class="profile-audio"
          />
        </div>
      </div>
    </el-card>
  </div>
</template>

<script setup lang="ts">
import { ref, reactive, onMounted, computed } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import type { UploadInstance, UploadFile } from 'element-plus'
import { IUploadFilled, IRefresh } from '@/utils/icons'
import {
  getVoiceProfiles,
  uploadVoiceSample,
  trainVoiceProfile,
  testVoiceProfile,
  deleteVoiceProfile,
  type VoiceProfile,
} from '@/api/voiceProfile'

const profiles = ref<VoiceProfile[]>([])
const loading = ref(false)
const uploading = ref(false)
const trainingId = ref<number | null>(null)
const testingId = ref<number | null>(null)
const audioUrls = reactive<Record<number, string>>({})
const uploadRef = ref<UploadInstance>()
const selectedFile = ref<File | null>(null)

const form = reactive({
  name: '',
  reference_text: '',
  demo_text: '你好，这是我的专属声音，希望你喜欢。',
})

const notConfigured = computed(() =>
  profiles.value.some((p) => p.error_message?.includes('未配置') || p.error_message?.includes('not granted'))
)

function statusLabel(s: string) {
  return { training: '训练中', active: '可用', failed: '失败', deleted: '已删除' }[s] || s
}

function statusType(s: string): 'success' | 'warning' | 'danger' | 'info' {
  return ({ active: 'success', training: 'warning', failed: 'danger' } as const)[s] || 'info'
}

function formatTime(t: string | null) {
  if (!t) return '-'
  return new Date(t).toLocaleString('zh-CN', { hour12: false })
}

function onFileChange(file: UploadFile) {
  selectedFile.value = (file.raw as File) || null
}

function onFileRemove() {
  selectedFile.value = null
}

async function loadProfiles() {
  loading.value = true
  try {
    const res = await getVoiceProfiles()
    profiles.value = res.data || []
  } catch (e: any) {
    ElMessage.error(e?.response?.data?.detail || '加载声纹列表失败')
  } finally {
    loading.value = false
  }
}

async function handleUpload() {
  if (!form.name.trim()) return ElMessage.warning('请填写声音名称')
  if (!selectedFile.value) return ElMessage.warning('请选择音频样本')
  if (form.demo_text.trim().length < 4) return ElMessage.warning('试听文本至少 4 个字')

  const fd = new FormData()
  fd.append('file', selectedFile.value)
  fd.append('name', form.name.trim())
  fd.append('demo_text', form.demo_text.trim())
  fd.append('reference_text', form.reference_text.trim())
  fd.append('language', '0')

  uploading.value = true
  try {
    await uploadVoiceSample(fd)
    ElMessage.success('上传成功，已提交训练')
    form.name = ''
    form.reference_text = ''
    selectedFile.value = null
    uploadRef.value?.clearFiles()
    await loadProfiles()
  } catch (e: any) {
    ElMessage.error(e?.response?.data?.detail || '上传失败')
  } finally {
    uploading.value = false
  }
}

async function handleTrain(p: VoiceProfile) {
  trainingId.value = p.id
  try {
    await trainVoiceProfile(p.id)
    await loadProfiles()
    ElMessage.success('已触发训练')
  } catch (e: any) {
    ElMessage.error(e?.response?.data?.detail || '训练失败')
  } finally {
    trainingId.value = null
  }
}

async function handleTest(p: VoiceProfile) {
  testingId.value = p.id
  try {
    const res = await testVoiceProfile(p.id, p.demo_text)
    audioUrls[p.id] = `${res.data.audio_url}?t=${Date.now()}`
    ElMessage.success('试听音频已生成')
  } catch (e: any) {
    ElMessage.error(e?.response?.data?.detail || '试听生成失败')
  } finally {
    testingId.value = null
  }
}

async function handleDelete(p: VoiceProfile) {
  try {
    await ElMessageBox.confirm(`确定删除声纹「${p.name}」吗？`, '删除确认', {
      type: 'warning',
    })
  } catch {
    return
  }
  try {
    await deleteVoiceProfile(p.id)
    ElMessage.success('已删除')
    await loadProfiles()
  } catch (e: any) {
    ElMessage.error(e?.response?.data?.detail || '删除失败')
  }
}

onMounted(loadProfiles)
</script>

<style scoped>
.voice-profile-page { padding: 16px; padding-bottom: 80px; }
.page-header { margin-bottom: 16px; }
.page-title { font-size: 18px; font-weight: 600; }
.tip-alert { margin-bottom: 16px; }
.upload-card, .list-card { margin-bottom: 16px; }
.card-header { display: flex; justify-content: space-between; align-items: center; font-weight: 600; }
.quota { font-size: 13px; color: #909399; font-weight: normal; }
.upload-icon { font-size: 32px; color: #c0c4cc; margin-bottom: 8px; }
.upload-text { font-size: 14px; color: #606266; }
.upload-tip { font-size: 12px; color: #909399; line-height: 1.6; margin-top: 6px; }
.profile-list { display: flex; flex-direction: column; gap: 12px; }
.profile-item {
  padding: 12px; border: 1px solid #ebeef5; border-radius: 8px;
  display: flex; flex-wrap: wrap; gap: 10px; align-items: center;
}
.profile-main { flex: 1; min-width: 180px; }
.profile-name { font-weight: 600; display: flex; align-items: center; gap: 8px; margin-bottom: 4px; }
.profile-meta { font-size: 12px; color: #909399; }
.profile-error { font-size: 12px; color: #f56c6c; margin-top: 4px; }
.profile-actions { display: flex; gap: 6px; flex-wrap: wrap; }
.profile-audio { width: 100%; margin-top: 8px; height: 36px; }
</style>
