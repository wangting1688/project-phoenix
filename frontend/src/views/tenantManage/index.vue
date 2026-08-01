<template>
  <div class="tenant-manage">
    <div class="page-header">
      <h2>渠道商管理</h2>
      <el-button type="primary" @click="showCreateDialog">
        <el-icon><Plus /></el-icon>
        新增渠道商
      </el-button>
    </div>

    <!-- 渠道商列表 -->
    <el-table :data="tenants" v-loading="loading" border style="width: 100%">
      <el-table-column prop="name" label="渠道商名称" min-width="150" />
      <el-table-column prop="code" label="编码" width="120" />
      <el-table-column prop="account" label="登录账号" width="140" />
      <el-table-column prop="contact_name" label="联系人" width="100" />
      <el-table-column prop="contact_phone" label="联系电话" width="130" />
      <el-table-column label="状态" width="90">
        <template #default="{ row }">
          <el-tag :type="statusType(row.status)" size="small" effect="dark">
            {{ statusLabel(row.status) }}
          </el-tag>
        </template>
      </el-table-column>
      <el-table-column label="到期时间" width="170">
        <template #default="{ row }">
          <span v-if="row.expires_at" :class="{ expired: isExpired(row.expires_at) }">
            {{ formatDate(row.expires_at) }}
          </span>
          <span v-else style="color: #67c23a">永久</span>
        </template>
      </el-table-column>
      <el-table-column prop="max_users" label="用户配额" width="90" />
      <el-table-column label="操作" width="280" fixed="right">
        <template #default="{ row }">
          <el-button size="small" @click="showUsersDialog(row)">用户管理</el-button>
          <el-button size="small" type="warning" @click="showEditDialog(row)">编辑</el-button>
          <el-button size="small" type="danger" plain @click="handleDisable(row)">停用</el-button>
        </template>
      </el-table-column>
    </el-table>

    <!-- 创建/编辑渠道商对话框 -->
    <el-dialog
      v-model="dialogVisible"
      :title="editingId ? '编辑渠道商' : '新增渠道商'"
      width="600px"
    >
      <el-form :model="formData" label-width="120px" ref="formRef" :rules="formRules">
        <el-form-item label="渠道商名称" prop="name">
          <el-input v-model="formData.name" placeholder="如：杭州健康频道" :disabled="!!editingId" />
        </el-form-item>
        <el-form-item label="渠道商编码" prop="code">
          <el-input v-model="formData.code" placeholder="如：HZ001" :disabled="!!editingId" />
        </el-form-item>
        <el-form-item label="登录账号" prop="account">
          <el-input v-model="formData.account" placeholder="渠道商登录账号" :disabled="!!editingId" />
        </el-form-item>
        <el-form-item v-if="!editingId" label="登录密码" prop="password">
          <el-input v-model="formData.password" type="password" placeholder="至少6位" show-password />
        </el-form-item>
        <el-form-item label="联系人">
          <el-input v-model="formData.contact_name" placeholder="联系人姓名" />
        </el-form-item>
        <el-form-item label="联系电话">
          <el-input v-model="formData.contact_phone" placeholder="联系电话" />
        </el-form-item>
        <el-form-item label="使用期限">
          <el-date-picker
            v-model="formData.expires_at"
            type="datetime"
            placeholder="选择到期时间（留空=永久）"
            format="YYYY-MM-DD HH:mm"
            value-format="YYYY-MM-DDTHH:mm:ss"
            style="width: 100%"
          />
        </el-form-item>
        <el-form-item label="用户配额">
          <el-input-number v-model="formData.max_users" :min="1" :max="1000" />
          <span style="margin-left: 10px; color: #909399; font-size: 13px">个</span>
        </el-form-item>
        <el-form-item label="视频项目配额">
          <el-input-number v-model="formData.max_video_projects" :min="1" :max="10000" />
          <span style="margin-left: 10px; color: #909399; font-size: 13px">个</span>
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="dialogVisible = false">取消</el-button>
        <el-button type="primary" @click="handleSave" :loading="saving">保存</el-button>
      </template>
    </el-dialog>

    <!-- 用户管理对话框 -->
    <el-dialog v-model="usersDialogVisible" :title="`用户管理 - ${currentTenant?.name || ''}`" width="700px">
      <div style="margin-bottom: 16px">
        <el-button type="primary" size="small" @click="showCreateUserDialog">
          <el-icon><Plus /></el-icon>
          添加用户
        </el-button>
      </div>
      <el-table :data="tenantUsers" border>
        <el-table-column prop="phone" label="手机号" width="150" />
        <el-table-column prop="nickname" label="昵称" width="150" />
        <el-table-column prop="role" label="角色" width="120">
          <template #default="{ row }">
            <el-tag :type="row.role === 'tenant_admin' ? 'warning' : ''" size="small">
              {{ row.role === 'tenant_admin' ? '渠道管理员' : '主播' }}
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column prop="status" label="状态" width="80">
          <template #default="{ row }">
            <el-tag :type="row.status === 1 ? 'success' : 'danger'" size="small">
              {{ row.status === 1 ? '启用' : '停用' }}
            </el-tag>
          </template>
        </el-table-column>
      </el-table>

      <!-- 添加用户表单 -->
      <div v-if="showCreateUser" style="margin-top: 20px; padding: 16px; background: #f5f7fa; border-radius: 8px">
        <el-form :model="newUser" label-width="80px" inline>
          <el-form-item label="手机号">
            <el-input v-model="newUser.phone" placeholder="手机号" style="width: 150px" />
          </el-form-item>
          <el-form-item label="密码">
            <el-input v-model="newUser.password" type="password" placeholder="密码" style="width: 120px" />
          </el-form-item>
          <el-form-item label="昵称">
            <el-input v-model="newUser.nickname" placeholder="昵称" style="width: 120px" />
          </el-form-item>
          <el-form-item label="角色">
            <el-select v-model="newUser.role" style="width: 120px">
              <el-option label="主播" value="anchor" />
              <el-option label="渠道管理员" value="tenant_admin" />
            </el-select>
          </el-form-item>
          <el-button type="primary" @click="handleCreateUser" :loading="saving">创建</el-button>
          <el-button @click="showCreateUser = false">取消</el-button>
        </el-form>
      </div>
    </el-dialog>
  </div>
</template>

<script setup lang="ts">
import { ref, reactive, onMounted } from 'vue'
import { ElMessage, ElMessageBox, type FormInstance, type FormRules } from 'element-plus'
import { Plus } from '@element-plus/icons-vue'
import { listTenants, createTenant, updateTenant, deleteTenant, listTenantUsers, createTenantUser } from '@/api/tenant'
import type { Tenant } from '@/types/user'

const loading = ref(false)
const saving = ref(false)
const tenants = ref<Tenant[]>([])
const dialogVisible = ref(false)
const editingId = ref<number | null>(null)
const formRef = ref<FormInstance>()

const formData = reactive({
  name: '',
  code: '',
  account: '',
  password: '',
  contact_name: '',
  contact_phone: '',
  expires_at: '',
  max_users: 5,
  max_video_projects: 50,
})

const formRules: FormRules = {
  name: [{ required: true, message: '请输入渠道商名称', trigger: 'blur' }],
  code: [{ required: true, message: '请输入渠道商编码', trigger: 'blur' }],
  account: [{ required: true, message: '请输入登录账号', trigger: 'blur' }],
  password: [{ required: true, message: '请输入密码', trigger: 'blur' }, { min: 6, message: '至少6位', trigger: 'blur' }],
}

// 用户管理
const usersDialogVisible = ref(false)
const currentTenant = ref<Tenant | null>(null)
const tenantUsers = ref<any[]>([])
const showCreateUser = ref(false)
const newUser = reactive({
  phone: '',
  password: '',
  nickname: '',
  role: 'anchor',
})

async function fetchTenants() {
  loading.value = true
  try {
    const res = await listTenants()
    tenants.value = res.items
  } catch (error) {
    ElMessage.error('获取渠道商列表失败')
  } finally {
    loading.value = false
  }
}

function showCreateDialog() {
  editingId.value = null
  Object.assign(formData, {
    name: '', code: '', account: '', password: '',
    contact_name: '', contact_phone: '', expires_at: '',
    max_users: 5, max_video_projects: 50,
  })
  dialogVisible.value = true
}

function showEditDialog(row: Tenant) {
  editingId.value = row.id
  Object.assign(formData, {
    name: row.name,
    code: row.code,
    account: row.account,
    password: '',
    contact_name: row.contact_name || '',
    contact_phone: row.contact_phone || '',
    expires_at: row.expires_at || '',
    max_users: row.max_users,
    max_video_projects: row.max_video_projects,
  })
  dialogVisible.value = true
}

async function handleSave() {
  if (!formRef.value) return
  try {
    await formRef.value.validate()
    saving.value = true
    if (editingId.value) {
      await updateTenant(editingId.value, {
        name: formData.name,
        contact_name: formData.contact_name,
        contact_phone: formData.contact_phone,
        expires_at: formData.expires_at || undefined,
        max_users: formData.max_users,
        max_video_projects: formData.max_video_projects,
      })
      ElMessage.success('更新成功')
    } else {
      await createTenant(formData as any)
      ElMessage.success('创建成功')
    }
    dialogVisible.value = false
    fetchTenants()
  } catch (error: any) {
    ElMessage.error(error?.message || '操作失败')
  } finally {
    saving.value = false
  }
}

async function handleDisable(row: Tenant) {
  try {
    await ElMessageBox.confirm(`确认停用渠道商「${row.name}」？停用后该渠道商下所有用户将无法登录`, '确认停用', {
      type: 'warning',
    })
    await deleteTenant(row.id)
    ElMessage.success('已停用')
    fetchTenants()
  } catch {}
}

async function showUsersDialog(row: Tenant) {
  currentTenant.value = row
  usersDialogVisible.value = true
  showCreateUser.value = false
  await fetchTenantUsers(row.id)
}

async function fetchTenantUsers(tenantId: number) {
  try {
    const res = await listTenantUsers(tenantId)
    tenantUsers.value = res.items
  } catch {
    ElMessage.error('获取用户列表失败')
  }
}

function showCreateUserDialog() {
  Object.assign(newUser, { phone: '', password: '', nickname: '', role: 'anchor' })
  showCreateUser.value = true
}

async function handleCreateUser() {
  if (!currentTenant.value) return
  try {
    saving.value = true
    await createTenantUser(currentTenant.value.id, { ...newUser })
    ElMessage.success('用户创建成功')
    Object.assign(newUser, { phone: '', password: '', nickname: '', role: 'anchor' })
    await fetchTenantUsers(currentTenant.value.id)
  } catch (error: any) {
    ElMessage.error(error?.message || '创建失败')
  } finally {
    saving.value = false
  }
}

function statusType(status: number) {
  if (status === 1) return 'success'
  if (status === 0) return 'info'
  return 'danger'
}

function statusLabel(status: number) {
  if (status === 1) return '启用'
  if (status === 0) return '停用'
  return '过期'
}

function isExpired(dateStr: string) {
  return new Date(dateStr) < new Date()
}

function formatDate(dateStr: string) {
  return new Date(dateStr).toLocaleString('zh-CN')
}

onMounted(() => {
  fetchTenants()
})
</script>

<style scoped>
.tenant-manage {
  padding: 20px;
}

.page-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 20px;
}

.page-header h2 {
  margin: 0;
  font-size: 22px;
}

.expired {
  color: #f56c6c;
  text-decoration: line-through;
}
</style>
