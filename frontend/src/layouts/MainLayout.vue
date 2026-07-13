<template>
  <div class="main-layout">
    <div class="layout-content">
      <router-view />
    </div>

    <div class="tab-bar">
      <div
        v-for="tab in tabs"
        :key="tab.path"
        class="tab-item"
        :class="{ active: activeTab === tab.path }"
        @click="switchTab(tab.path)"
      >
        <el-icon :size="24">
          <component :is="tab.icon" />
        </el-icon>
        <span class="tab-label">{{ tab.label }}</span>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, computed } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import {
  IHouse,
  IVideoCamera,
  IFiles,
  IUser,
} from '@element-plus/icons-vue'

const route = useRoute()
const router = useRouter()

const tabs = [
  { path: '/home', label: '首页', icon: IHouse },
  { path: '/creation', label: '创作', icon: IVideoCamera },
  { path: '/works', label: '作品', icon: IFiles },
  { path: '/profile', label: '我的', icon: IUser },
]

const activeTab = computed(() => {
  const path = route.path
  return tabs.find(tab => path.startsWith(tab.path))?.path || '/home'
})

function switchTab(path: string) {
  if (activeTab.value !== path) {
    router.push(path)
  }
}
</script>

<style scoped>
.main-layout {
  width: 100%;
  min-height: 100vh;
  background-color: #f5f7fa;
  padding-bottom: 60px;
}

.layout-content {
  width: 100%;
  max-width: 768px;
  margin: 0 auto;
}

.tab-bar {
  position: fixed;
  bottom: 0;
  left: 0;
  right: 0;
  height: 60px;
  background: #fff;
  display: flex;
  justify-content: space-around;
  align-items: center;
  box-shadow: 0 -2px 10px rgba(0, 0, 0, 0.1);
  z-index: 1000;
}

.tab-item {
  flex: 1;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  cursor: pointer;
  color: #909399;
  transition: color 0.3s;
  padding: 5px 0;
}

.tab-item.active {
  color: #667eea;
}

.tab-label {
  font-size: 12px;
  margin-top: 2px;
}
</style>
