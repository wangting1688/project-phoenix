<template>
  <div class="platform-account-page">
    <div class="page-header">
      <h2>平台账号管理</h2>
      <el-button type="primary" @click="showAddDialog = true">
        <el-icon><IPlus /></el-icon> 添加账号
      </el-button>
    </div>

    <div class="account-list">
      <div v-for="account in accounts" :key="account.id" class="account-card">
        <div class="account-header">
          <div class="platform-icon" :class="account.platform">
            {{ platformLabel(account.platform) }}
          </div>
          <div class="account-info">
            <h4>{{ account.account_name }}</h4>
            <p class="account-id">ID: {{ account.account_id || '-' }}</p>
          </div>
          <el-tag :type="statusType(account.status)" size="small">
            {{ statusLabel(account.status) }}
          </el-tag>
        </div>

        <div class="account-stats">
          <div class="stat-item">
            <span class="stat-value">{{ formatNumber(account.follower_count) }}</span>
            <span class="stat-label">粉丝</span>
          </div>
          <div class="stat-item">
            <span class="stat-value">{{ formatNumber(account.last_7d_plays) }}</span>
            <span class="stat-label">7日播放</span>
          </div>
          <div class="stat-item">
            <span class="stat-value">{{ account.content_style || '-' }}</span>
            <span class="stat-label">内容风格</span>
          </div>
        </div>

        <div class="account-actions">
          <el-button size="small" @click="editAccount(account)">编辑</el-button>
          <el-button size="small" type="danger" plain @click="deleteAccount(account.id)">删除</el-button>
        </div>
      </div>

      <el-empty v-if="accounts.length === 0" description="暂无平台账号，请先添加" />
    </div>

    <!-- 添加/编辑对话框 -->
    <el-dialog v-model="showAddDialog" :title="isEdit ? '编辑账号' : '添加账号'" width="90%" :close-on-click-modal="false">
      <el-form :model="form" :rules="rules" ref="formRef" label-width="80px">
        <el-form-item label="平台" prop="platform">
          <el-select v-model="form.platform" placeholder="选择平台" style="width: 100%">
            <el-option label="抖音" value="douyin" />
            <el-option label="视频号" value="video_channel" />
            <el-option label="小红书" value="xiaohongshu" />
            <el-option label="快手" value="kuaishou" />
            <el-option label="B站" value="bilibili" />
          </el-select>
        </el-form-item>
        <el-form-item label="账号名称" prop="account_name">
          <el-input v-model="form.account_name" placeholder="账号名称" />
        </el-form-item>
        <el-form-item label="账号ID">
          <el-input v-model="form.account_id" placeholder="可选" />
        </el-form-item>
        <el-form-item label="主页链接">
          <el-input v-model="form.account_url" placeholder="可选" />
        </el-form-item>
        <el-form-item label="内容风格">
          <el-select v-model="form.content_style" placeholder="选择风格" style="width: 100%">
            <el-option label="故事型" value="故事型" />
            <el-option label="知识型" value="知识型" />
            <el-option label="测评型" value="测评型" />
            <el-option label="搞笑型" value="搞笑型" />
            <el-option label="剧情型" value="剧情型" />
          </el-select>
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="showAddDialog = false">取消</el-button>
        <el-button type="primary" @click="submitForm" :loading="submitting">保存</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup lang="ts">
import { ref, reactive, onMounted } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { IPlus } from '@/utils/icons'
import {
  getPlatformAccounts,
  createPlatformAccount,
  updatePlatformAccount,
  deletePlatformAccount,
} from '@/api/platformAccount'

interface PlatformAccount {
  id: number
  platform: string
  account_name: string
  account_id: string | null
  account_url: string | null
  status: string
  follower_count: number
  last_7d_plays: number
  content_style: string | null
}

const accounts = ref<PlatformAccount[]>([])
const loading = ref(false)
const showAddDialog = ref(false)
const isEdit = ref(false)
const editId = ref<number | null>(null)
const submitting = ref(false)
const formRef = ref()

const form = reactive({
  platform: '',
  account_name: '',
  account_id: '',
  account_url: '',
  content_style: '',
})

const rules = {
  platform: [{ required: true, message: '请选择平台', trigger: 'change' }],
  account_name: [{ required: true, message: '请输入账号名称', trigger: 'blur' }],
}

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
    active: 'success',
    expired: 'warning',
    disabled: 'danger',
    error: 'danger',
  }
  return map[status] || 'info'
}

function statusLabel(status: string) {
  const map: Record<string, string> = {
    active: '正常',
    expired: '授权过期',
    disabled: '已禁用',
    error: '异常',
  }
  return map[status] || status
}

function formatNumber(num: number) {
  if (!num) return '0'
  if (num >= 10000) {
    return (num / 10000).toFixed(1) + 'w'
  }
  return num.toString()
}

async function loadAccounts() {
  loading.value = true
  try {
    const res = await getPlatformAccounts()
    accounts.value = res.items || []
  } catch (error) {
    console.error('加载账号失败:', error)
  } finally {
    loading.value = false
  }
}

function editAccount(account: PlatformAccount) {
  isEdit.value = true
  editId.value = account.id
  form.platform = account.platform
  form.account_name = account.account_name
  form.account_id = account.account_id || ''
  form.account_url = account.account_url || ''
  form.content_style = account.content_style || ''
  showAddDialog.value = true
}

function resetForm() {
  isEdit.value = false
  editId.value = null
  form.platform = ''
  form.account_name = ''
  form.account_id = ''
  form.account_url = ''
  form.content_style = ''
}

async function submitForm() {
  if (!formRef.value) return
  try {
    await formRef.value.validate()
    submitting.value = true

    const data = {
      platform: form.platform,
      account_name: form.account_name,
      account_id: form.account_id || undefined,
      account_url: form.account_url || undefined,
      content_style: form.content_style || undefined,
    }

    if (isEdit.value && editId.value) {
      await updatePlatformAccount(editId.value, data)
      ElMessage.success('更新成功')
    } else {
      await createPlatformAccount(data)
      ElMessage.success('添加成功')
    }

    showAddDialog.value = false
    resetForm()
    await loadAccounts()
  } catch (error) {
    console.error('保存失败:', error)
  } finally {
    submitting.value = false
  }
}

async function deleteAccount(id: number) {
  try {
    await ElMessageBox.confirm('确定删除该账号吗？', '提示', { type: 'warning' })
    await deletePlatformAccount(id)
    ElMessage.success('删除成功')
    await loadAccounts()
  } catch (error: any) {
    if (error !== 'cancel') {
      console.error('删除失败:', error)
    }
  }
}

onMounted(() => {
  loadAccounts()
})
</script>

<style scoped>
.platform-account-page {
  padding: 16px;
  max-width: 768px;
  margin: 0 auto;
}

.page-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 20px;
}

.page-header h2 {
  margin: 0;
  font-size: 20px;
}

.account-list {
  display: flex;
  flex-direction: column;
  gap: 12px;
}

.account-card {
  background: #fff;
  border-radius: 12px;
  padding: 16px;
  box-shadow: 0 2px 8px rgba(0, 0, 0, 0.06);
}

.account-header {
  display: flex;
  align-items: center;
  gap: 12px;
  margin-bottom: 12px;
}

.platform-icon {
  width: 48px;
  height: 48px;
  border-radius: 12px;
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 13px;
  font-weight: bold;
  color: #fff;
  flex-shrink: 0;
}

.platform-icon.douyin {
  background: linear-gradient(135deg, #000, #333);
}

.platform-icon.video_channel {
  background: linear-gradient(135deg, #07c160, #05a050);
}

.platform-icon.xiaohongshu {
  background: linear-gradient(135deg, #ff2442, #e01e36);
}

.platform-icon.kuaishou {
  background: linear-gradient(135deg, #ff6600, #e55a00);
}

.platform-icon.bilibili {
  background: linear-gradient(135deg, #00a1d6, #0089b4);
}

.account-info {
  flex: 1;
  min-width: 0;
}

.account-info h4 {
  margin: 0 0 4px;
  font-size: 16px;
}

.account-id {
  margin: 0;
  font-size: 12px;
  color: #909399;
}

.account-stats {
  display: flex;
  justify-content: space-around;
  padding: 12px 0;
  border-top: 1px solid #f0f0f0;
  border-bottom: 1px solid #f0f0f0;
  margin-bottom: 12px;
}

.stat-item {
  text-align: center;
}

.stat-value {
  display: block;
  font-size: 16px;
  font-weight: bold;
  color: #303133;
}

.stat-label {
  display: block;
  font-size: 12px;
  color: #909399;
  margin-top: 2px;
}

.account-actions {
  display: flex;
  gap: 8px;
  justify-content: flex-end;
}
</style>
