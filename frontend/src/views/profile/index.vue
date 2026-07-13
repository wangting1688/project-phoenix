<template>
  <div class="profile-page">
    <div class="profile-header">
      <div class="user-info">
        <el-avatar :size="72" src="">
          {{ userStore.userInfo?.nickname?.charAt(0) || '主' }}
        </el-avatar>
        <div class="user-detail">
          <h2>{{ userStore.userInfo?.nickname || '主播' }}</h2>
          <p>{{ userStore.userInfo?.phone }}</p>
        </div>
      </div>
      <el-button type="primary" size="small" @click="editProfile">
        编辑资料
      </el-button>
    </div>

    <div class="page-container">
      <div class="stats-card card">
        <div class="stat-item">
          <div class="stat-number">{{ stats.projects }}</div>
          <div class="stat-label">总作品</div>
        </div>
        <div class="stat-divider"></div>
        <div class="stat-item">
          <div class="stat-number">{{ stats.totalViews }}</div>
          <div class="stat-label">总播放</div>
        </div>
        <div class="stat-divider"></div>
        <div class="stat-item">
          <div class="stat-number">{{ stats.consultations }}</div>
          <div class="stat-label">总咨询</div>
        </div>
      </div>

      <div class="menu-list">
        <div class="menu-card card">
          <div class="menu-item" @click="$router.push('/works')">
            <div class="menu-left">
              <el-icon :size="20" class="menu-icon purple"><IVideoCamera /></el-icon>
              <span>我的作品</span>
            </div>
            <el-icon :size="16" class="arrow"><IArrowRight /></el-icon>
          </div>
          <div class="menu-divider"></div>
          <div class="menu-item" @click="showComingSoon">
            <div class="menu-left">
              <el-icon :size="20" class="menu-icon blue"><IDataAnalysis /></el-icon>
              <span>数据分析</span>
            </div>
            <el-icon :size="16" class="arrow"><IArrowRight /></el-icon>
          </div>
          <div class="menu-divider"></div>
          <div class="menu-item" @click="showComingSoon">
            <div class="menu-left">
              <el-icon :size="20" class="menu-icon green"><IUser /></el-icon>
              <span>AI画像</span>
            </div>
            <el-icon :size="16" class="arrow"><IArrowRight /></el-icon>
          </div>
        </div>

        <div class="menu-card card">
          <div class="menu-item" @click="showComingSoon">
            <div class="menu-left">
              <el-icon :size="20" class="menu-icon orange"><ISetting /></el-icon>
              <span>设置</span>
            </div>
            <el-icon :size="16" class="arrow"><IArrowRight /></el-icon>
          </div>
          <div class="menu-divider"></div>
          <div class="menu-item" @click="showComingSoon">
            <div class="menu-left">
              <el-icon :size="20" class="menu-icon red"><IHelp /></el-icon>
              <span>帮助与反馈</span>
            </div>
            <el-icon :size="16" class="arrow"><IArrowRight /></el-icon>
          </div>
        </div>

        <el-button
          type="danger"
          plain
          class="logout-btn"
          @click="handleLogout"
        >
          退出登录
        </el-button>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { useRouter } from 'vue-router'
import { ElMessage, ElMessageBox } from 'element-plus'
import {
  IVideoCamera,
  IArrowRight,
  IDataAnalysis,
  IUser,
  ISetting,
  IHelp,
} from '@/utils/icons'
import { useUserStore } from '@/stores/user'

const router = useRouter()
const userStore = useUserStore()

const stats = ref({
  projects: 0,
  totalViews: 0,
  consultations: 0,
})

onMounted(() => {
  if (!userStore.userInfo) {
    userStore.fetchUserInfo()
  }
})

function editProfile() {
  ElMessage.info('编辑资料功能开发中')
}

function showComingSoon() {
  ElMessage.info('功能开发中，敬请期待')
}

async function handleLogout() {
  try {
    await ElMessageBox.confirm('确定要退出登录吗？', '提示', {
      confirmButtonText: '确定',
      cancelButtonText: '取消',
      type: 'warning',
    })
    userStore.logout()
    router.push('/login')
    ElMessage.success('已退出登录')
  } catch {
  }
}
</script>

<style scoped>
.profile-page {
  min-height: 100vh;
  background: #f5f7fa;
}

.profile-header {
  background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
  padding: 50px 20px 70px;
  color: #fff;
  display: flex;
  justify-content: space-between;
  align-items: center;
}

.user-info {
  display: flex;
  align-items: center;
}

.user-detail {
  margin-left: 16px;
}

.user-detail h2 {
  font-size: 20px;
  margin-bottom: 4px;
}

.user-detail p {
  font-size: 14px;
  opacity: 0.8;
}

.page-container {
  padding: 0 16px;
  max-width: 768px;
  margin: -40px auto 0;
}

.stats-card {
  display: flex;
  justify-content: space-around;
  align-items: center;
  padding: 20px;
  margin-bottom: 16px;
}

.stat-item {
  text-align: center;
  flex: 1;
}

.stat-number {
  font-size: 24px;
  font-weight: bold;
  color: #667eea;
  margin-bottom: 4px;
}

.stat-label {
  font-size: 13px;
  color: #909399;
}

.stat-divider {
  width: 1px;
  height: 40px;
  background: #ebeef5;
}

.menu-list {
  padding-bottom: 20px;
}

.menu-card {
  margin-bottom: 16px;
  padding: 0;
}

.menu-item {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 16px 20px;
  cursor: pointer;
  transition: background 0.2s;
}

.menu-item:active {
  background: #f5f7fa;
}

.menu-left {
  display: flex;
  align-items: center;
}

.menu-icon {
  margin-right: 12px;
}

.menu-icon.purple {
  color: #667eea;
}

.menu-icon.blue {
  color: #409eff;
}

.menu-icon.green {
  color: #67c23a;
}

.menu-icon.orange {
  color: #e6a23c;
}

.menu-icon.red {
  color: #f56c6c;
}

.arrow {
  color: #c0c4cc;
}

.menu-divider {
  height: 1px;
  background: #f2f6fc;
  margin: 0 20px;
}

.logout-btn {
  width: 100%;
  margin-top: 10px;
  padding: 12px 0;
  font-size: 16px;
}
</style>
