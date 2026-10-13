<template>
  <div class="workbench-page">
    <div class="page-header">
      <h2>AI 工作台</h2>
      <p>把创作流水线之外的工具都收在这里，需要时再进来</p>
    </div>

    <div class="page-container">
      <div v-for="group in groups" :key="group.title" class="group card">
        <h3 class="group-title">{{ group.title }}</h3>
        <div class="tool-grid">
          <div
            v-for="tool in group.tools"
            :key="tool.path"
            class="tool-item"
            @click="$router.push(tool.path)"
          >
            <el-icon :size="22" class="tool-icon" :style="{ color: tool.color }">
              <component :is="tool.icon" />
            </el-icon>
            <span class="tool-name">{{ tool.name }}</span>
            <span class="tool-desc">{{ tool.desc }}</span>
          </div>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import {
  IVideoCamera,
  IPicture,
  IVideoPlay,
  IDocument,
  IDataAnalysis,
  ISparkles,
  IStar,
  IUser,
  IMicrophone,
  ISetting,
} from '@/utils/icons'

const groups = [
  {
    title: '内容增长',
    tools: [
      { name: 'AI内容中心', desc: '选题与内容灵感', path: '/content-hub', icon: IDocument, color: '#667eea' },
      { name: 'AI爆款逆向', desc: '拆解爆款视频', path: '/viral-analysis', icon: IDataAnalysis, color: '#67c23a' },
      { name: '数据登记', desc: '登记发布数据', path: '/data-entry', icon: IDataAnalysis, color: '#409eff' },
      { name: 'AI画像', desc: '主播人设画像', path: '/creator-profile', icon: IUser, color: '#e6a23c' },
    ],
  },
  {
    title: '拍摄制作',
    tools: [
      { name: '拍摄助手', desc: '脚本分镜指导', path: '/shooting-assistant', icon: IVideoCamera, color: '#e6a23c' },
      { name: '素材采集', desc: '采集建议与清单', path: '/asset-collection', icon: IPicture, color: '#409eff' },
      { name: '智能素材库', desc: '素材智能管理', path: '/asset-library', icon: IPicture, color: '#667eea' },
      { name: '视频生产', desc: '生产工厂与任务', path: '/video-production', icon: IVideoPlay, color: '#67c23a' },
      { name: 'AI导演', desc: '编排与分镜', path: '/video-director', icon: IVideoPlay, color: '#667eea' },
      { name: '导演学习', desc: '导演复盘记录', path: '/director-learning', icon: IStar, color: '#f56c6c' },
      { name: '创作工作台', desc: '深度创作工具', path: '/creation-studio', icon: ISetting, color: '#909399' },
    ],
  },
  {
    title: '我的',
    tools: [
      { name: '我的声音', desc: '克隆与管理声音', path: '/voice-profile', icon: IMicrophone, color: '#e6a23c' },
      { name: '我的作品', desc: '查看所有作品', path: '/works', icon: IVideoCamera, color: '#667eea' },
      { name: '通知中心', desc: '任务完成与提醒', path: '/notifications', icon: IDocument, color: '#409eff' },
    ],
  },
]
</script>

<style scoped>
.workbench-page {
  min-height: 100vh;
  background: #f5f7fa;
  padding-bottom: 60px;
}

.page-header {
  background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
  padding: 30px 20px 40px;
  color: #fff;
  text-align: center;
}

.page-header h2 {
  font-size: 22px;
  margin-bottom: 6px;
}

.page-header p {
  font-size: 13px;
  opacity: 0.9;
}

.page-container {
  max-width: 768px;
  margin: -20px auto 0;
  padding: 0 12px;
}

.group {
  padding: 16px;
  margin-bottom: 12px;
}

.group-title {
  font-size: 15px;
  font-weight: 600;
  margin-bottom: 12px;
}

.tool-grid {
  display: grid;
  grid-template-columns: repeat(2, 1fr);
  gap: 10px;
}

.tool-item {
  display: flex;
  flex-direction: column;
  align-items: flex-start;
  gap: 4px;
  padding: 14px 12px;
  border: 1px solid #ebeef5;
  border-radius: 10px;
  cursor: pointer;
  transition: all 0.15s;
}

.tool-item:active {
  transform: scale(0.98);
  background: #f5f7ff;
}

.tool-icon {
  margin-bottom: 6px;
}

.tool-name {
  font-size: 14px;
  font-weight: 600;
  color: #303133;
}

.tool-desc {
  font-size: 11px;
  color: #909399;
}
</style>
