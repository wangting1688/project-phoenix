<template>
  <div class="works-page">
    <div class="page-header">
      <h2>我的作品</h2>
      <p>查看你创作的所有视频</p>
      <el-button
        class="header-action"
        size="small"
        @click="$router.push('/data-entry')"
      >
        📊 数据登记
      </el-button>
    </div>

    <div class="page-container">
      <div class="filter-tabs">
        <div
          v-for="tab in tabs"
          :key="tab.value"
          class="tab-item"
          :class="{ active: activeTab === tab.value }"
          @click="activeTab = tab.value"
        >
          {{ tab.label }}
        </div>
      </div>

      <div v-if="filteredWorks.length > 0" class="works-grid">
        <div
          v-for="work in filteredWorks"
          :key="work.id"
          class="work-card card"
          @click="viewWork(work)"
        >
          <!-- 封面区域 -->
          <div class="work-cover">
            <img
              v-if="work.cover_url"
              :src="coverSrcMap[work.id]"
              class="cover-image"
              alt="cover"
              @error="coverError = true"
            />
            <div v-else class="cover-placeholder">
              <el-icon :size="40"><IVideoCamera /></el-icon>
              <span class="cover-hint">{{ coverHint(workStatus(work)) }}</span>
            </div>

            <!-- 状态遮罩 -->
            <div v-if="workStatus(work) === 'processing'" class="status-overlay processing">
              <el-icon class="loading-icon" :size="28"><ILoading /></el-icon>
              <span>生成中...</span>
            </div>
            <div v-else-if="workStatus(work) === 'failed'" class="status-overlay failed">
              <el-icon :size="28"><ICircleClose /></el-icon>
              <span>生成失败</span>
            </div>
            <div v-else-if="workStatus(work) === 'plan_ready'" class="status-overlay plan-ready">
              <el-icon :size="28"><IDocument /></el-icon>
              <span>方案已完成</span>
            </div>
            <div v-else-if="workStatus(work) === 'video_ready'" class="play-btn">
              <el-icon :size="36"><IVideoPlay /></el-icon>
            </div>
          </div>

          <!-- 信息区域 -->
          <div class="work-info">
            <h4 class="work-title">{{ work.topic || '未命名作品' }}</h4>
            <div class="work-meta">
              <span class="status" :class="workStatus(work)">
                {{ statusText(workStatus(work)) }}
              </span>
              <span class="date">{{ formatDate(work.created_at) }}</span>
            </div>

            <!-- 操作按钮区域 -->
            <div class="work-actions">
              <template v-if="workStatus(work) === 'video_ready'">
                <a
                  v-if="work.video_url"
                  :href="videoSrcMap[work.id]"
                  target="_blank"
                  class="action-btn download"
                  @click.stop
                >
                  <el-icon><IDownload /></el-icon> 下载
                </a>
                <el-button
                  size="small"
                  type="danger"
                  text
                  class="action-btn delete"
                  @click.stop="handleDelete(work)"
                >
                  <el-icon><IDelete /></el-icon> 删除
                </el-button>
              </template>

              <template v-else-if="workStatus(work) === 'plan_ready'">
                <el-button
                  size="small"
                  type="primary"
                  text
                  class="action-btn"
                  @click.stop="goGenerate(work)"
                >
                  <el-icon><IVideoPlay /></el-icon> 生成视频
                </el-button>
                <el-button
                  size="small"
                  type="danger"
                  text
                  class="action-btn delete"
                  @click.stop="handleDelete(work)"
                >
                  <el-icon><IDelete /></el-icon> 删除
                </el-button>
              </template>

              <template v-else-if="workStatus(work) === 'processing'">
                <el-button
                  size="small"
                  type="primary"
                  text
                  class="action-btn"
                  @click.stop="viewWork(work)"
                >
                  查看进度
                </el-button>
              </template>

              <template v-else-if="workStatus(work) === 'failed'">
                <el-button
                  size="small"
                  type="primary"
                  text
                  class="action-btn"
                  @click.stop="viewWork(work)"
                >
                  查看详情
                </el-button>
                <el-button
                  size="small"
                  type="danger"
                  text
                  class="action-btn delete"
                  @click.stop="handleDelete(work)"
                >
                  <el-icon><IDelete /></el-icon> 删除
                </el-button>
              </template>

              <template v-else>
                <el-button
                  size="small"
                  type="danger"
                  text
                  class="action-btn delete"
                  @click.stop="handleDelete(work)"
                >
                  <el-icon><IDelete /></el-icon> 删除
                </el-button>
              </template>
            </div>
          </div>
        </div>
      </div>

      <div v-else class="empty-state">
        <el-empty description="还没有作品，去创作一个吧！">
          <el-button type="primary" @click="$router.push('/creation')">
            开始创作
          </el-button>
        </el-empty>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, onMounted } from 'vue'
import { useRouter } from 'vue-router'
import { ElMessageBox, ElMessage } from 'element-plus'
import {
  IVideoCamera,
  IVideoPlay,
  ILoading,
  IDownload,
  IDelete,
  IDocument,
  ICircleClose,
} from '@/utils/icons'
import { getProjects, deleteProject, type ContentProject } from '@/api/creation'
import { useUserStore } from '@/stores/user'
import { resolveMediaUrls } from '@/utils/mediaUrl'
import { normalizeStatus, statusText, coverHint } from '@/utils/status'

const router = useRouter()
const userStore = useUserStore()

const activeTab = ref('all')
const coverError = ref(false)
const coverSrcMap = ref<Record<number, string>>({})
const videoSrcMap = ref<Record<number, string>>({})

const tabs = [
  { label: '全部', value: 'all' },
  { label: '生成中', value: 'processing' },
  { label: '方案完成', value: 'plan_ready' },
  { label: '视频完成', value: 'video_ready' },
  { label: '失败', value: 'failed' },
]

const works = ref<ContentProject[]>([])

const filteredWorks = computed(() => {
  if (activeTab.value === 'all') return works.value
  return works.value.filter(w => workStatus(w) === activeTab.value)
})

/**
 * 作品的展示状态：优先 display_status，缺失时回落到 status，并统一归一。
 *
 * 归一很关键 —— 历史数据里存在 "ready" 这类不在前端枚举内的值（早期
 * creation_studio 链路写入）。直接拿去比 v-if 的结果是：状态标签原样显示
 * 英文 "ready"，且所有按钮分支都不匹配，卡片上只剩一个「删除」。
 * 详见 utils/status.ts。
 */
function workStatus(work: ContentProject) {
  return normalizeStatus(work.display_status || work.status)
}

function formatDate(dateStr: string) {
  if (!dateStr) return ''
  const date = new Date(dateStr)
  return `${date.getMonth() + 1}/${date.getDate()}`
}

function viewWork(work: ContentProject) {
  const status = workStatus(work)
  if (status === 'plan_ready') {
    // 只出了方案、还没成片的作品：直接带去创作页，用「照片 + 场景」生成。
    // 原来跳的是老结果页的自动生成（compose → 渲染），那条链路依赖实拍
    // 素材、实测走不通，已经整体下线。
    goCreateVideo(work)
  } else {
    router.push(`/result?project_id=${work.id}`)
  }
}

function goGenerate(work: ContentProject) {
  goCreateVideo(work)
}

/**
 * 接着这个作品往下做视频（作品页「生成视频」按钮 & 点击卡片）。
 *
 * 必须带上 project_id：这个作品的文案早就生成好了（plan_ready = 方案就绪、待出片），
 * 创作页靠 project_id 恢复已有文案并直接落到「声音」步。只带 topic 的话，创作页
 * 会判定成「换了选题的新创作」，把文案清掉让用户重新生成一遍 —— 线上实际反馈就是这个。
 */
function goCreateVideo(work: ContentProject) {
  const topic = (work.topic || '').trim()
  const q: Record<string, string> = { project_id: String(work.id) }
  if (topic) q.topic = topic
  router.push({ path: '/creation', query: q })
}

async function handleDelete(work: ContentProject) {
  try {
    await ElMessageBox.confirm(
      `确定要删除「${work.topic || '该作品'}」吗？删除后无法恢复。`,
      '删除确认',
      {
        confirmButtonText: '删除',
        cancelButtonText: '取消',
        type: 'warning',
      }
    )
  } catch {
    return
  }
  try {
    await deleteProject(work.id)
    works.value = works.value.filter(w => w.id !== work.id)
    ElMessage.success('删除成功')
  } catch (e: any) {
    ElMessage.error(e?.response?.data?.detail || '删除失败')
  }
}

async function loadWorks() {
  try {
    const res = await getProjects(1, 50)
    works.value = res.items || []
    const covers: Record<number, string> = {}
    const videos: Record<number, string> = {}
    const paths = works.value.flatMap((w: any) => {
      const list: string[] = []
      if (w.cover_url) list.push(String(w.cover_url).replace(/^\/static\//, ''))
      if (w.video_url) list.push(String(w.video_url).replace(/^\/static\//, ''))
      return list
    })
    const map = await resolveMediaUrls(paths)
    works.value.forEach((w: any) => {
      if (w.cover_url) covers[w.id] = map[String(w.cover_url).replace(/^\/static\//, '')] || ''
      if (w.video_url) videos[w.id] = map[String(w.video_url).replace(/^\/static\//, '')] || ''
    })
    coverSrcMap.value = covers
    videoSrcMap.value = videos
  } catch (e) {
    console.error('加载作品失败:', e)
  }
}

onMounted(() => {
  loadWorks()
})
</script>

<style scoped>
.works-page {
  min-height: 100vh;
  background: #f5f7fa;
}

.page-header {
  position: relative;
  background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
  padding: 40px 20px 50px;
  color: #fff;
  text-align: center;
}

.page-header h2 {
  font-size: 24px;
  margin-bottom: 8px;
}

.page-header p {
  font-size: 14px;
  opacity: 0.9;
}

.header-action {
  position: absolute;
  top: 16px;
  right: 16px;
}

.page-container {
  padding: 0 16px;
  max-width: 768px;
  margin: -30px auto 0;
}

.filter-tabs {
  display: flex;
  background: #fff;
  border-radius: 12px;
  padding: 4px;
  margin-bottom: 16px;
  box-shadow: 0 2px 12px rgba(0, 0, 0, 0.08);
  overflow-x: auto;
}

.tab-item {
  flex: 1;
  min-width: 70px;
  text-align: center;
  padding: 10px 8px;
  font-size: 13px;
  color: #606266;
  border-radius: 8px;
  cursor: pointer;
  transition: all 0.3s;
  white-space: nowrap;
}

.tab-item.active {
  background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
  color: #fff;
  font-weight: 500;
}

.works-grid {
  display: grid;
  grid-template-columns: repeat(2, 1fr);
  gap: 12px;
}

.work-card {
  padding: 0;
  overflow: hidden;
  cursor: pointer;
  transition: transform 0.2s;
}

.work-card:active {
  transform: scale(0.98);
}

.work-cover {
  position: relative;
  width: 100%;
  aspect-ratio: 9 / 16;
  background: linear-gradient(135deg, #667eea20, #764ba220);
  display: flex;
  align-items: center;
  justify-content: center;
  color: #667eea;
  overflow: hidden;
}

.cover-image {
  width: 100%;
  height: 100%;
  object-fit: cover;
  display: block;
}

.cover-placeholder {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  opacity: 0.6;
  gap: 8px;
}

.cover-hint {
  font-size: 12px;
}

.status-overlay {
  position: absolute;
  top: 0;
  left: 0;
  right: 0;
  bottom: 0;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  color: #fff;
  font-size: 12px;
  gap: 8px;
}

.status-overlay.processing {
  background: rgba(102, 126, 234, 0.7);
}

.status-overlay.failed {
  background: rgba(245, 108, 108, 0.7);
}

.status-overlay.plan-ready {
  background: rgba(103, 194, 58, 0.6);
}

.loading-icon {
  animation: spin 1s linear infinite;
}

@keyframes spin {
  from { transform: rotate(0deg); }
  to { transform: rotate(360deg); }
}

.play-btn {
  position: absolute;
  top: 50%;
  left: 50%;
  transform: translate(-50%, -50%);
  color: #fff;
  opacity: 0.85;
  text-shadow: 0 2px 8px rgba(0, 0, 0, 0.3);
}

.work-info {
  padding: 12px;
}

.work-title {
  font-size: 14px;
  color: #303133;
  margin-bottom: 8px;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.work-meta {
  display: flex;
  justify-content: space-between;
  align-items: center;
  font-size: 12px;
  margin-bottom: 8px;
}

.status {
  padding: 2px 8px;
  border-radius: 10px;
  font-size: 11px;
}

.status.video_ready,
.status.completed {
  background: #f0f9eb;
  color: #67c23a;
}

.status.processing,
.status.rendering {
  background: #ecf5ff;
  color: #409eff;
}

.status.draft {
  background: #f4f4f5;
  color: #909399;
}

.status.failed {
  background: #fef0f0;
  color: #f56c6c;
}

.status.plan_ready {
  background: #fdf6ec;
  color: #e6a23c;
}

.date {
  color: #c0c4cc;
}

.work-actions {
  display: flex;
  gap: 8px;
  margin-top: 4px;
  padding-top: 8px;
  border-top: 1px solid #f0f0f0;
}

.action-btn {
  flex: 1;
  font-size: 12px;
  justify-content: center;
  padding: 4px 0;
}

.action-btn.download {
  color: #667eea;
  text-decoration: none;
  display: flex;
  align-items: center;
  gap: 4px;
}

.action-btn.delete {
  color: #f56c6c;
}

.empty-state {
  background: #fff;
  border-radius: 12px;
  padding: 60px 20px;
  text-align: center;
}
</style>
