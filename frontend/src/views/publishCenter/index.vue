<template>
  <div class="publish-center-page">
    <div class="page-header">
      <h2>发布中心</h2>
      <el-button type="primary" @click="showCreateDialog = true">
        <el-icon><IPlus /></el-icon> 新建发布
      </el-button>
    </div>

    <!-- 状态筛选 -->
    <div class="status-filter">
      <el-radio-group v-model="filterStatus" size="small" @change="loadTasks">
        <el-radio-button label="">全部</el-radio-button>
        <el-radio-button label="draft">草稿</el-radio-button>
        <el-radio-button label="pending">待发布</el-radio-button>
        <el-radio-button label="published">已发布</el-radio-button>
        <el-radio-button label="reviewed">已复盘</el-radio-button>
      </el-radio-group>
    </div>

    <!-- 任务列表 -->
    <div class="task-list">
      <div v-for="task in tasks" :key="task.id" class="task-card">
        <div class="task-header">
          <div class="task-platform">
            <span class="platform-badge" :class="task.platform">
              {{ platformLabel(task.platform) }}
            </span>
            <span class="account-name">{{ getAccountName(task.platform_account_id) }}</span>
          </div>
          <el-tag :type="statusType(task.status)" size="small">
            {{ statusLabel(task.status) }}
          </el-tag>
        </div>

        <div class="task-content">
          <h4>{{ task.content_title }}</h4>
          <p v-if="task.content_description" class="desc">{{ task.content_description }}</p>
          <div class="task-tags">
            <el-tag v-for="tag in task.tags" :key="tag" size="small" effect="plain">{{ tag }}</el-tag>
          </div>
        </div>

        <!-- 数据展示 -->
        <div v-if="task.status === 'published' || task.status === 'reviewed'" class="task-metrics">
          <div class="metric-item">
            <el-icon><IView /></el-icon>
            <span>{{ formatNumber(task.play_count) }}</span>
          </div>
          <div class="metric-item">
            <el-icon><ILike /></el-icon>
            <span>{{ formatNumber(task.like_count) }}</span>
          </div>
          <div class="metric-item">
            <el-icon><IChatDotRound /></el-icon>
            <span>{{ formatNumber(task.comment_count) }}</span>
          </div>
          <div class="metric-item">
            <el-icon><IShare /></el-icon>
            <span>{{ formatNumber(task.share_count) }}</span>
          </div>
        </div>

        <!-- 增长洞察展示 -->
        <div v-if="task.growth_insight" class="growth-insight">
          <div class="insight-header">
            <el-tag :type="insightType(task.growth_insight.performance_level)" size="small" effect="dark">
              {{ task.growth_insight.performance_label }} · {{ task.growth_insight.score }}分
            </el-tag>
            <span class="insight-factor">归因: {{ factorLabel(task.growth_insight.primary_factor) }}</span>
          </div>
          <div class="insight-list">
            <div v-for="(insight, idx) in task.growth_insight.insights" :key="idx" class="insight-item" :class="insight.type">
              <el-icon :size="14"><IInfoFilled /></el-icon>
              <div>
                <strong>{{ insight.title }}</strong>
                <p>{{ insight.content }}</p>
              </div>
            </div>
          </div>
        </div>

        <div class="task-actions">
          <el-button
            v-if="task.status === 'draft' || task.status === 'pending'"
            size="small"
            type="primary"
            @click="handlePublish(task.id)"
          >
            立即发布
          </el-button>
          <el-button
            v-if="task.status === 'published'"
            size="small"
            type="success"
            @click="handleAutoCollect(task.id)"
          >
            自动采集
          </el-button>
          <el-button
            v-if="task.status === 'collecting'"
            size="small"
            type="warning"
            @click="handleAutoReview(task.id)"
          >
            自动复盘
          </el-button>
          <el-button
            v-if="task.status === 'published'"
            size="small"
            type="primary"
            @click="handleFullPipeline(task.id)"
          >
            一键闭环
          </el-button>
          <el-button
            v-if="task.status === 'published'"
            size="small"
            @click="showMetricsDialog(task)"
          >
            录入数据
          </el-button>
          <el-button size="small" @click="editTask(task)">编辑</el-button>
          <el-button size="small" type="danger" plain @click="deleteTask(task.id)">删除</el-button>
        </div>
      </div>

      <el-empty v-if="tasks.length === 0" description="暂无发布任务" />
    </div>

    <!-- 创建/编辑对话框 -->
    <el-dialog v-model="showCreateDialog" :title="isEdit ? '编辑发布任务' : '新建发布任务'" width="90%">
      <el-form :model="form" :rules="rules" ref="formRef" label-width="90px">
        <el-form-item label="内容标题" prop="content_title">
          <el-input v-model="form.content_title" placeholder="视频标题" />
        </el-form-item>
        <el-form-item label="内容描述">
          <el-input v-model="form.content_description" type="textarea" :rows="2" placeholder="可选" />
        </el-form-item>
        <el-form-item label="发布平台" prop="platform_account_id">
          <el-select v-model="form.platform_account_id" placeholder="选择平台账号" style="width: 100%">
            <el-option
              v-for="account in accounts"
              :key="account.id"
              :label="`${platformLabel(account.platform)} - ${account.account_name}`"
              :value="account.id"
            />
          </el-select>
        </el-form-item>
        <el-form-item label="标签">
          <el-select-v2
            v-model="form.tags"
            :options="tagOptions"
            placeholder="输入或选择标签"
            multiple
            filterable
            allow-create
            clearable
            style="width: 100%"
          />
        </el-form-item>
        <el-form-item label="分类">
          <el-select v-model="form.category" placeholder="选择分类" style="width: 100%">
            <el-option label="健康" value="健康" />
            <el-option label="养生" value="养生" />
            <el-option label="生活" value="生活" />
            <el-option label="科普" value="科普" />
          </el-select>
        </el-form-item>
        <el-form-item label="计划时间">
          <el-date-picker
            v-model="form.scheduled_at"
            type="datetime"
            placeholder="立即发布可不选"
            style="width: 100%"
          />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="showCreateDialog = false">取消</el-button>
        <el-button type="primary" @click="submitForm" :loading="submitting">保存</el-button>
      </template>
    </el-dialog>

    <!-- 录入数据对话框 -->
    <el-dialog v-model="showMetricsDialogVisible" title="录入回流数据" width="90%">
      <el-form :model="metricsForm" label-width="100px">
        <el-form-item label="播放量">
          <el-input-number v-model="metricsForm.play_count" :min="0" style="width: 100%" />
        </el-form-item>
        <el-form-item label="点赞数">
          <el-input-number v-model="metricsForm.like_count" :min="0" style="width: 100%" />
        </el-form-item>
        <el-form-item label="评论数">
          <el-input-number v-model="metricsForm.comment_count" :min="0" style="width: 100%" />
        </el-form-item>
        <el-form-item label="分享数">
          <el-input-number v-model="metricsForm.share_count" :min="0" style="width: 100%" />
        </el-form-item>
        <el-form-item label="收藏数">
          <el-input-number v-model="metricsForm.collect_count" :min="0" style="width: 100%" />
        </el-form-item>
        <el-form-item label="新增粉丝">
          <el-input-number v-model="metricsForm.follower_gained" :min="0" style="width: 100%" />
        </el-form-item>
        <el-form-item label="完播率(%)">
          <el-input-number v-model="metricsForm.completion_rate" :min="0" :max="100" :precision="2" style="width: 100%" />
        </el-form-item>
        <el-form-item label="点击率(%)">
          <el-input-number v-model="metricsForm.ctr" :min="0" :max="100" :precision="2" style="width: 100%" />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="showMetricsDialogVisible = false">取消</el-button>
        <el-button type="primary" @click="submitMetrics" :loading="metricsSubmitting">保存</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup lang="ts">
import { ref, reactive, onMounted } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { IPlus, IView, ILike, IChatDotRound, IShare, IInfoFilled } from '@/utils/icons'
import {
  getPublishTasks,
  createPublishTask,
  updatePublishTask,
  deletePublishTask,
  triggerPublish,
  collectMetrics,
  autoCollectMetrics,
  autoReviewTask,
  runFullPipeline,
} from '@/api/publishTask'
import { getPlatformAccounts } from '@/api/platformAccount'

interface PlatformAccount {
  id: number
  platform: string
  account_name: string
}

interface PublishTask {
  id: number
  content_title: string
  content_description: string | null
  platform: string
  platform_account_id: number
  status: string
  tags: string[] | null
  play_count: number
  like_count: number
  comment_count: number
  share_count: number
  collect_count: number
  follower_gained: number
  completion_rate: number | null
  ctr: number | null
}

const tasks = ref<PublishTask[]>([])
const accounts = ref<PlatformAccount[]>([])
const filterStatus = ref('')
const loading = ref(false)

const showCreateDialog = ref(false)
const isEdit = ref(false)
const editId = ref<number | null>(null)
const submitting = ref(false)
const formRef = ref()

const form = reactive({
  content_title: '',
  content_description: '',
  platform_account_id: null as number | null,
  tags: [] as string[],
  category: '',
  scheduled_at: null as Date | null,
})

const rules = {
  content_title: [{ required: true, message: '请输入内容标题', trigger: 'blur' }],
  platform_account_id: [{ required: true, message: '请选择平台账号', trigger: 'change' }],
}

const tagOptions = [
  { label: '健康', value: '健康' },
  { label: '养生', value: '养生' },
  { label: '青汁', value: '青汁' },
  { label: '睡眠', value: '睡眠' },
  { label: '肠道', value: '肠道' },
  { label: '减肥', value: '减肥' },
  { label: '日常', value: '日常' },
]

const showMetricsDialogVisible = ref(false)
const metricsTaskId = ref<number | null>(null)
const metricsSubmitting = ref(false)
const metricsForm = reactive({
  play_count: 0,
  like_count: 0,
  comment_count: 0,
  share_count: 0,
  collect_count: 0,
  follower_gained: 0,
  completion_rate: null as number | null,
  ctr: null as number | null,
})

function platformLabel(platform: string) {
  const map: Record<string, string> = {
    douyin: '抖音',
    video_channel: '视频号',
    xiaohongshu: '小红书',
    kuaishou: '快手',
    bilibili: 'B站',
  }
  return map[platform] || platform
}

function statusType(status: string) {
  const map: Record<string, string> = {
    draft: 'info',
    pending: 'warning',
    queued: 'warning',
    publishing: 'primary',
    published: 'success',
    failed: 'danger',
    cancelled: 'info',
    collecting: 'primary',
    reviewed: 'success',
  }
  return map[status] || 'info'
}

function statusLabel(status: string) {
  const map: Record<string, string> = {
    draft: '草稿',
    pending: '待发布',
    queued: '队列中',
    publishing: '发布中',
    published: '已发布',
    failed: '失败',
    cancelled: '已取消',
    collecting: '采集中',
    reviewed: '已复盘',
  }
  return map[status] || status
}

function insightType(level: string) {
  const map: Record<string, string> = {
    excellent: 'success',
    good: 'primary',
    average: 'warning',
    poor: 'danger',
  }
  return map[level] || 'info'
}

function factorLabel(factor: string) {
  const map: Record<string, string> = {
    content_style: '内容风格',
    platform_match: '平台适配',
    tags_precision: '标签精准',
    publish_timing: '发布时间',
    hook_pattern: '开场钩子',
    audience_fit: '受众匹配',
  }
  return map[factor] || factor
}

function getAccountName(accountId: number) {
  const account = accounts.value.find(a => a.id === accountId)
  return account ? account.account_name : '未知账号'
}

function formatNumber(num: number) {
  if (!num) return '0'
  if (num >= 10000) {
    return (num / 10000).toFixed(1) + 'w'
  }
  return num.toString()
}

async function loadAccounts() {
  try {
    const res = await getPlatformAccounts()
    accounts.value = res.items || []
  } catch (error) {
    console.error('加载账号失败:', error)
  }
}

async function loadTasks() {
  loading.value = true
  try {
    const params: { status?: string } = {}
    if (filterStatus.value) {
      params.status = filterStatus.value
    }
    const res = await getPublishTasks(params)
    tasks.value = res.items || []
  } catch (error) {
    console.error('加载任务失败:', error)
  } finally {
    loading.value = false
  }
}

function editTask(task: PublishTask) {
  isEdit.value = true
  editId.value = task.id
  form.content_title = task.content_title
  form.content_description = task.content_description || ''
  form.platform_account_id = task.platform_account_id
  form.tags = task.tags || []
  form.category = ''
  form.scheduled_at = null
  showCreateDialog.value = true
}

function resetForm() {
  isEdit.value = false
  editId.value = null
  form.content_title = ''
  form.content_description = ''
  form.platform_account_id = null
  form.tags = []
  form.category = ''
  form.scheduled_at = null
}

async function submitForm() {
  if (!formRef.value) return
  try {
    await formRef.value.validate()
    if (!form.platform_account_id) return
    submitting.value = true

    const account = accounts.value.find(a => a.id === form.platform_account_id)
    const data = {
      content_title: form.content_title,
      content_description: form.content_description || undefined,
      platform_account_id: form.platform_account_id,
      platform: account?.platform || '',
      tags: form.tags.length > 0 ? form.tags : undefined,
      category: form.category || undefined,
      scheduled_at: form.scheduled_at ? form.scheduled_at.toISOString() : undefined,
    }

    if (isEdit.value && editId.value) {
      await updatePublishTask(editId.value, data)
      ElMessage.success('更新成功')
    } else {
      await createPublishTask(data)
      ElMessage.success('创建成功')
    }

    showCreateDialog.value = false
    resetForm()
    await loadTasks()
  } catch (error) {
    console.error('保存失败:', error)
  } finally {
    submitting.value = false
  }
}

async function handlePublish(taskId: number) {
  try {
    await ElMessageBox.confirm('确定立即发布该内容吗？', '确认发布', { type: 'warning' })
    await triggerPublish(taskId)
    ElMessage.success('发布成功')
    await loadTasks()
  } catch (error: any) {
    if (error !== 'cancel') {
      console.error('发布失败:', error)
    }
  }
}

async function handleAutoCollect(taskId: number) {
  try {
    const res = await autoCollectMetrics(taskId)
    ElMessage.success(`自动采集完成：播放量 ${formatNumber(res.metrics.play_count)}`)
    await loadTasks()
  } catch (error) {
    console.error('自动采集失败:', error)
  }
}

async function handleAutoReview(taskId: number) {
  try {
    const res = await autoReviewTask(taskId)
    ElMessage.success(`自动复盘完成：${res.performance.label} · ${res.performance.score}分`)
    await loadTasks()
  } catch (error) {
    console.error('自动复盘失败:', error)
  }
}

async function handleFullPipeline(taskId: number) {
  try {
    await ElMessageBox.confirm('将执行：自动采集 → 自动复盘 → 更新 Growth Graph，确定继续？', '一键闭环', { type: 'info' })
    const res = await runFullPipeline(taskId)
    ElMessage.success(res.message)
    await loadTasks()
  } catch (error: any) {
    if (error !== 'cancel') {
      console.error('闭环执行失败:', error)
    }
  }
}

function showMetricsDialog(task: PublishTask) {
  metricsTaskId.value = task.id
  metricsForm.play_count = task.play_count || 0
  metricsForm.like_count = task.like_count || 0
  metricsForm.comment_count = task.comment_count || 0
  metricsForm.share_count = task.share_count || 0
  metricsForm.collect_count = task.collect_count || 0
  metricsForm.follower_gained = task.follower_gained || 0
  metricsForm.completion_rate = task.completion_rate
  metricsForm.ctr = task.ctr
  showMetricsDialogVisible.value = true
}

async function submitMetrics() {
  if (!metricsTaskId.value) return
  metricsSubmitting.value = true
  try {
    await collectMetrics(metricsTaskId.value, {
      play_count: metricsForm.play_count,
      like_count: metricsForm.like_count,
      comment_count: metricsForm.comment_count,
      share_count: metricsForm.share_count,
      collect_count: metricsForm.collect_count,
      follower_gained: metricsForm.follower_gained,
      completion_rate: metricsForm.completion_rate ?? undefined,
      ctr: metricsForm.ctr ?? undefined,
    })
    ElMessage.success('数据录入成功')
    showMetricsDialogVisible.value = false
    await loadTasks()
  } catch (error) {
    console.error('录入失败:', error)
  } finally {
    metricsSubmitting.value = false
  }
}

async function deleteTask(id: number) {
  try {
    await ElMessageBox.confirm('确定删除该发布任务吗？', '提示', { type: 'warning' })
    await deletePublishTask(id)
    ElMessage.success('删除成功')
    await loadTasks()
  } catch (error: any) {
    if (error !== 'cancel') {
      console.error('删除失败:', error)
    }
  }
}

onMounted(() => {
  loadAccounts()
  loadTasks()
})
</script>

<style scoped>
.publish-center-page {
  padding: 16px;
  max-width: 768px;
  margin: 0 auto;
}

.page-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 16px;
}

.page-header h2 {
  margin: 0;
  font-size: 20px;
}

.status-filter {
  margin-bottom: 16px;
  overflow-x: auto;
}

.task-list {
  display: flex;
  flex-direction: column;
  gap: 12px;
}

.task-card {
  background: #fff;
  border-radius: 12px;
  padding: 16px;
  box-shadow: 0 2px 8px rgba(0, 0, 0, 0.06);
}

.task-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 12px;
}

.task-platform {
  display: flex;
  align-items: center;
  gap: 8px;
}

.platform-badge {
  padding: 2px 8px;
  border-radius: 4px;
  font-size: 12px;
  font-weight: bold;
  color: #fff;
}

.platform-badge.douyin {
  background: #000;
}

.platform-badge.video_channel {
  background: #07c160;
}

.platform-badge.xiaohongshu {
  background: #ff2442;
}

.platform-badge.kuaishou {
  background: #ff6600;
}

.platform-badge.bilibili {
  background: #00a1d6;
}

.account-name {
  font-size: 13px;
  color: #606266;
}

.task-content h4 {
  margin: 0 0 6px;
  font-size: 16px;
}

.task-content .desc {
  margin: 0 0 8px;
  font-size: 13px;
  color: #606266;
}

.task-tags {
  display: flex;
  flex-wrap: wrap;
  gap: 6px;
  margin-bottom: 12px;
}

.task-metrics {
  display: flex;
  gap: 16px;
  padding: 10px 0;
  border-top: 1px solid #f0f0f0;
  margin-bottom: 12px;
}

.metric-item {
  display: flex;
  align-items: center;
  gap: 4px;
  font-size: 13px;
  color: #606266;
}

.task-actions {
  display: flex;
  gap: 8px;
  justify-content: flex-end;
  flex-wrap: wrap;
}

.growth-insight {
  background: #f8f9fa;
  border-radius: 8px;
  padding: 12px;
  margin-bottom: 12px;
}

.insight-header {
  display: flex;
  align-items: center;
  gap: 10px;
  margin-bottom: 10px;
}

.insight-factor {
  font-size: 12px;
  color: #606266;
}

.insight-list {
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.insight-item {
  display: flex;
  gap: 8px;
  align-items: flex-start;
  font-size: 13px;
  padding: 8px;
  border-radius: 6px;
}

.insight-item.success {
  background: #f0f9eb;
  color: #67c23a;
}

.insight-item.suggestion {
  background: #ecf5ff;
  color: #409eff;
}

.insight-item.warning {
  background: #fdf6ec;
  color: #e6a23c;
}

.insight-item.alert {
  background: #fef0f0;
  color: #f56c6c;
}

.insight-item strong {
  display: block;
  margin-bottom: 2px;
}

.insight-item p {
  margin: 0;
  line-height: 1.4;
  opacity: 0.9;
}
</style>
