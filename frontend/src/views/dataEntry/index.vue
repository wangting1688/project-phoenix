<template>
  <div class="data-entry-page">
    <div class="page-header">
      <h2>数据登记</h2>
      <p>手工上报视频真实播放数据，为增长分析提供数据源</p>
    </div>

    <div class="page-container">
      <!-- 顶部：视频列表 -->
      <div class="card section">
        <div class="section-title">
          <span>我的视频</span>
          <el-button type="primary" size="small" @click="showRegisterDialog = true">
            + 登记新视频
          </el-button>
        </div>
        <el-empty v-if="!loading && videos.length === 0" description="还没有登记的视频" :image-size="80" />
        <div v-else class="video-list">
          <div
            v-for="v in videos"
            :key="v.publish_record_id"
            class="video-item"
            :class="{ active: selectedId === v.publish_record_id }"
            @click="selectVideo(v.publish_record_id)"
          >
            <div class="video-title">{{ v.title }}</div>
            <div class="video-meta">
              <span class="platform-tag" :class="v.platform">{{ platformLabel(v.platform) }}</span>
              <span class="metric">👁 {{ formatNum(v.views) }}</span>
              <span class="metric">❤ {{ formatNum(v.likes) }}</span>
              <span class="metric">💬 {{ formatNum(v.comments) }}</span>
              <span class="update-time">{{ v.data_updated_at ? formatDate(v.data_updated_at) : '未上报' }}</span>
            </div>
          </div>
        </div>
      </div>

      <!-- 中部：快照录入 -->
      <div v-if="selected" class="card section">
        <div class="section-title">
          <span>录入日快照 · {{ selected.title }}</span>
          <span class="section-sub">{{ platformLabel(selected.platform) }}</span>
        </div>
        <el-form :model="snapForm" label-position="top" size="default">
          <div class="grid-3">
            <el-form-item label="快照日期">
              <el-input v-model="snapForm.snapshot_date" placeholder="YYYY-MM-DD" />
            </el-form-item>
            <el-form-item label="播放量 *">
              <el-input-number v-model="snapForm.views" :min="0" style="width:100%" />
            </el-form-item>
            <el-form-item label="点赞 *">
              <el-input-number v-model="snapForm.likes" :min="0" style="width:100%" />
            </el-form-item>
            <el-form-item label="评论 *">
              <el-input-number v-model="snapForm.comments" :min="0" style="width:100%" />
            </el-form-item>
            <el-form-item label="收藏 *">
              <el-input-number v-model="snapForm.favorites" :min="0" style="width:100%" />
            </el-form-item>
            <el-form-item label="分享 *">
              <el-input-number v-model="snapForm.shares" :min="0" style="width:100%" />
            </el-form-item>
            <el-form-item label="私信数">
              <el-input-number v-model="snapForm.private_message_count" :min="0" style="width:100%" />
            </el-form-item>
            <el-form-item label="完播率(0-1)">
              <el-input-number v-model="snapForm.completion_rate" :min="0" :max="1" :step="0.05" :precision="2" style="width:100%" />
            </el-form-item>
            <el-form-item label="涨粉">
              <el-input-number v-model="snapForm.follows" :min="0" style="width:100%" />
            </el-form-item>
          </div>
          <el-form-item label="热门评论（每行一条，供AI提取用户痛点）">
            <el-input v-model="topCommentsText" type="textarea" :rows="3" placeholder="真的有用&#10;多少钱&#10;敏感肌可以用吗" />
          </el-form-item>
          <div class="form-actions">
            <el-button type="primary" :loading="submitting" @click="submitSnapshot">提交快照</el-button>
            <span class="hint">同日同渠道再报会 upsert 覆盖</span>
          </div>
        </el-form>
      </div>

      <!-- 底部：7 日趋势 -->
      <div v-if="selected" class="card section">
        <div class="section-title">
          <span>最近 7 日趋势</span>
          <span class="section-sub">共 {{ snapshots.length }} 条快照</span>
        </div>
        <el-empty v-if="snapshots.length === 0" description="暂无快照" :image-size="80" />
        <div v-else class="trend-wrap">
          <div class="metric-tabs">
            <span
              v-for="m in metricOptions"
              :key="m.key"
              class="metric-tab"
              :class="{ active: activeMetric === m.key }"
              @click="activeMetric = m.key"
            >{{ m.label }}</span>
          </div>
          <svg :viewBox="`0 0 ${chartW} ${chartH}`" class="chart" preserveAspectRatio="xMidYMid meet">
            <line v-for="(y, i) in gridY" :key="'g'+i" :x1="padL" :x2="chartW-padR" :y1="y" :y2="y" stroke="#eee" />
            <polyline :points="polyPoints" fill="none" stroke="#409eff" stroke-width="2" />
            <g v-for="(pt, i) in points" :key="'p'+i">
              <circle :cx="pt.x" :cy="pt.y" r="4" fill="#409eff" />
              <text :x="pt.x" :y="pt.y - 8" text-anchor="middle" font-size="11" fill="#606266">{{ formatNum(pt.value) }}</text>
              <text :x="pt.x" :y="chartH - 8" text-anchor="middle" font-size="10" fill="#909399">{{ pt.date }}</text>
            </g>
          </svg>
        </div>
      </div>
    </div>

    <!-- 登记视频弹窗 -->
    <el-dialog v-model="showRegisterDialog" title="登记新视频" width="90%" style="max-width:520px">
      <el-form :model="regForm" label-position="top">
        <el-form-item label="视频标题 *">
          <el-input v-model="regForm.title" placeholder="例：40岁后皮肤松弛怎么办" />
        </el-form-item>
        <el-form-item label="平台 *">
          <el-select v-model="regForm.platform" style="width:100%">
            <el-option label="抖音" value="douyin" />
            <el-option label="视频号" value="wechat_video" />
            <el-option label="小红书" value="xiaohongshu" />
            <el-option label="快手" value="kuaishou" />
            <el-option label="B站" value="bilibili" />
          </el-select>
        </el-form-item>
        <el-form-item label="视频链接">
          <el-input v-model="regForm.publish_url" placeholder="https://..." />
        </el-form-item>
        <el-form-item label="时长（秒）">
          <el-input-number v-model="regForm.duration" :min="0" style="width:100%" />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="showRegisterDialog = false">取消</el-button>
        <el-button type="primary" :loading="registering" @click="submitRegister">确认登记</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, onMounted, watch, reactive } from 'vue'
import { ElMessage } from 'element-plus'
import {
  listVideos,
  registerVideo,
  reportDailySnapshot,
  listSnapshots,
  type VideoRecord,
  type SnapshotItem,
} from '@/api/ingest'

const loading = ref(false)
const videos = ref<VideoRecord[]>([])
const selectedId = ref<number | null>(null)
const selected = computed(() => videos.value.find(v => v.publish_record_id === selectedId.value) || null)

const snapshots = ref<SnapshotItem[]>([])
const activeMetric = ref<'views' | 'likes' | 'comments' | 'favorites' | 'shares'>('views')
const metricOptions = [
  { key: 'views' as const, label: '播放' },
  { key: 'likes' as const, label: '点赞' },
  { key: 'comments' as const, label: '评论' },
  { key: 'favorites' as const, label: '收藏' },
  { key: 'shares' as const, label: '分享' },
]

// 登记
const showRegisterDialog = ref(false)
const registering = ref(false)
const regForm = reactive({ title: '', platform: 'douyin', publish_url: '', duration: 30 })

// 录入
const submitting = ref(false)
const snapForm = reactive({
  snapshot_date: todayStr(),
  views: 0, likes: 0, comments: 0, favorites: 0, shares: 0,
  private_message_count: 0, completion_rate: 0, follows: 0,
})
const topCommentsText = ref('')

function todayStr() {
  const d = new Date()
  return `${d.getFullYear()}-${String(d.getMonth()+1).padStart(2,'0')}-${String(d.getDate()).padStart(2,'0')}`
}

function platformLabel(p: string) {
  return { douyin:'抖音', wechat_video:'视频号', xiaohongshu:'小红书', kuaishou:'快手', bilibili:'B站' }[p] || p
}

function formatNum(n: number) {
  if (n >= 10000) return (n/10000).toFixed(1)+'w'
  if (n >= 1000) return (n/1000).toFixed(1)+'k'
  return String(n ?? 0)
}

function formatDate(iso: string) {
  const d = new Date(iso)
  return `${d.getMonth()+1}/${d.getDate()} ${String(d.getHours()).padStart(2,'0')}:${String(d.getMinutes()).padStart(2,'0')}`
}

async function loadVideos() {
  loading.value = true
  try {
    videos.value = await listVideos(50)
    if (videos.value.length > 0 && selectedId.value == null) {
      selectedId.value = videos.value[0].publish_record_id
    }
  } finally {
    loading.value = false
  }
}

async function loadSnapshots(recordId: number) {
  snapshots.value = await listSnapshots(recordId, 30)
}

function selectVideo(id: number) {
  selectedId.value = id
}

watch(selectedId, async (id) => {
  if (id != null) await loadSnapshots(id)
  else snapshots.value = []
})

async function submitRegister() {
  if (!regForm.title.trim()) { ElMessage.warning('请填写标题'); return }
  registering.value = true
  try {
    const res = await registerVideo({
      title: regForm.title,
      platform: regForm.platform,
      publish_url: regForm.publish_url || null,
      duration: regForm.duration || null,
    })
    ElMessage.success('登记成功')
    showRegisterDialog.value = false
    Object.assign(regForm, { title: '', publish_url: '', duration: 30 })
    await loadVideos()
    selectedId.value = res.publish_record_id
  } finally {
    registering.value = false
  }
}

async function submitSnapshot() {
  if (selectedId.value == null) return
  const core = ['views','likes','comments','favorites','shares'] as const
  if (!core.some(k => (snapForm as any)[k] > 0)) {
    ElMessage.warning('请至少填写一项核心指标')
    return
  }
  const payload: Record<string, unknown> = {}
  core.forEach(k => { if ((snapForm as any)[k] > 0) payload[k] = (snapForm as any)[k] })
  if (snapForm.private_message_count > 0) payload.private_message_count = snapForm.private_message_count
  if (snapForm.follows > 0) payload.follows = snapForm.follows
  if (snapForm.completion_rate > 0) payload.completion_rate = snapForm.completion_rate

  const topComments = topCommentsText.value.split('\n').map(s => s.trim()).filter(Boolean)
  if (topComments.length > 0) payload.top_comments = topComments

  submitting.value = true
  try {
    await reportDailySnapshot({
      publish_record_id: selectedId.value,
      mode: 'manual',
      snapshot_date: snapForm.snapshot_date,
      payload,
    })
    ElMessage.success('快照已提交')
    await Promise.all([loadVideos(), loadSnapshots(selectedId.value)])
  } finally {
    submitting.value = false
  }
}

// ==================== 折线图 ====================
const chartW = 640
const chartH = 220
const padL = 40
const padR = 20
const padT = 30
const padB = 30

const trendData = computed(() => {
  const src = [...snapshots.value].slice(0, 7).reverse()
  return src.map(s => ({ date: s.snapshot_date.slice(5), value: Number((s as any)[activeMetric.value] || 0) }))
})

const points = computed(() => {
  const data = trendData.value
  if (data.length === 0) return []
  const maxV = Math.max(1, ...data.map(d => d.value))
  const stepX = (chartW - padL - padR) / Math.max(1, data.length - 1)
  return data.map((d, i) => ({
    x: padL + stepX * i,
    y: padT + (chartH - padT - padB) * (1 - d.value / maxV),
    value: d.value,
    date: d.date,
  }))
})

const polyPoints = computed(() =>
  points.value.map(p => `${p.x},${p.y}`).join(' ')
)

const gridY = computed(() => {
  const rows = 4
  const step = (chartH - padT - padB) / rows
  return Array.from({ length: rows + 1 }, (_, i) => padT + step * i)
})

onMounted(loadVideos)
</script>

<style scoped>
.data-entry-page { min-height: 100vh; background: #f5f7fa; padding-bottom: 80px; }

.page-header {
  background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
  padding: 30px 20px 40px;
  color: #fff;
  text-align: center;
}
.page-header h2 { font-size: 22px; margin-bottom: 6px; }
.page-header p { font-size: 13px; opacity: 0.9; }

.page-container { padding: 0 16px; max-width: 900px; margin: -24px auto 0; }

.card {
  background: #fff;
  border-radius: 12px;
  padding: 16px;
  margin-bottom: 16px;
  box-shadow: 0 2px 12px rgba(0, 0, 0, 0.06);
}

.section-title {
  display: flex; justify-content: space-between; align-items: center;
  font-size: 15px; font-weight: 600; color: #303133;
  margin-bottom: 12px;
}
.section-sub { font-size: 12px; color: #909399; font-weight: normal; }

.video-list { display: flex; flex-direction: column; gap: 8px; }
.video-item {
  border: 1px solid #ebeef5;
  border-radius: 8px;
  padding: 12px;
  cursor: pointer;
  transition: all 0.2s;
}
.video-item:hover { border-color: #409eff; }
.video-item.active { border-color: #409eff; background: #ecf5ff; }
.video-title { font-size: 14px; color: #303133; margin-bottom: 6px; line-height: 1.4; }
.video-meta {
  display: flex; align-items: center; gap: 10px; flex-wrap: wrap;
  font-size: 12px; color: #909399;
}
.platform-tag {
  padding: 2px 8px; border-radius: 4px;
  background: #e6f7ff; color: #1890ff; font-size: 11px;
}
.platform-tag.douyin { background: #fff0f6; color: #eb2f96; }
.platform-tag.xiaohongshu { background: #fff1f0; color: #f5222d; }
.metric { color: #606266; }
.update-time { margin-left: auto; }

.grid-3 {
  display: grid;
  grid-template-columns: repeat(3, 1fr);
  gap: 12px;
}
@media (max-width: 600px) {
  .grid-3 { grid-template-columns: repeat(2, 1fr); }
}

.form-actions { display: flex; align-items: center; gap: 12px; margin-top: 8px; }
.hint { color: #909399; font-size: 12px; }

.trend-wrap { padding: 8px 0; }
.metric-tabs { display: flex; gap: 8px; margin-bottom: 8px; }
.metric-tab {
  padding: 4px 12px; border-radius: 12px; font-size: 12px;
  background: #f5f7fa; color: #606266; cursor: pointer;
}
.metric-tab.active { background: #409eff; color: #fff; }
.chart { width: 100%; max-height: 260px; }
</style>
