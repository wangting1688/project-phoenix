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
import { computed } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import {
  IVideoCamera,
  IPicture,
  IFiles,
} from '@/utils/icons'

const route = useRoute()
const router = useRouter()

const tabs = [
  { path: '/creation', label: '创建视频', icon: IVideoCamera },
  { path: '/footage', label: '我的素材', icon: IPicture },
  { path: '/works', label: '我的作品', icon: IFiles },
]

const activeTab = computed(() => {
  const path = route.path
  // 结果页、详情页也算在"我的作品"Tab
  if (path.startsWith('/result')) return '/works'
  // 其他非Tab页面高亮第一个
  const match = tabs.find(tab => path.startsWith(tab.path))
  return match?.path || '/creation'
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
  border-top: 1px solid #ebeef5;
  z-index: 100;
  padding-bottom: env(safe-area-inset-bottom);
}

.tab-item {
  flex: 1;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  gap: 4px;
  color: #909399;
  font-size: 11px;
  cursor: pointer;
  transition: color 0.2s;
}

.tab-item.active {
  color: #667eea;
}

.tab-label {
  font-size: 11px;
}
</style>
