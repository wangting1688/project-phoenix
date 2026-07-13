<template>
  <div class="creation-page">
    <div class="page-header">
      <h2>开始创作</h2>
      <p>选择一种创作方式，让AI帮你生成内容</p>
    </div>

    <div class="page-container">
      <div class="creation-methods">
        <div
          class="method-card"
          :class="{ active: selectedMethod === 'recommend' }"
          @click="selectMethod('recommend')"
        >
          <div class="method-icon recommend">
            <el-icon :size="28"><IFire /></el-icon>
          </div>
          <div class="method-info">
            <h3>AI推荐内容</h3>
            <p>系统根据热点和你的画像推荐</p>
          </div>
          <el-radio :model-value="selectedMethod === 'recommend'" />
        </div>

        <div
          class="method-card"
          :class="{ active: selectedMethod === 'viral_analysis' }"
          @click="selectMethod('viral_analysis')"
        >
          <div class="method-icon viral">
            <el-icon :size="28"><IVideoPlay /></el-icon>
          </div>
          <div class="method-info">
            <h3>爆款视频解析</h3>
            <p>复制链接，生成原创方案</p>
          </div>
          <el-radio :model-value="selectedMethod === 'viral_analysis'" />
        </div>

        <div
          class="method-card"
          :class="{ active: selectedMethod === 'custom' }"
          @click="selectMethod('custom')"
        >
          <div class="method-icon custom">
            <el-icon :size="28"><IEdit /></el-icon>
          </div>
          <div class="method-info">
            <h3>自定义主题</h3>
            <p>输入你想创作的主题</p>
          </div>
          <el-radio :model-value="selectedMethod === 'custom'" />
        </div>
      </div>

      <div v-if="selectedMethod === 'custom'" class="input-section card">
        <h3>输入创作主题</h3>
        <el-input
          v-model="topic"
          type="textarea"
          :rows="3"
          placeholder="例如：睡眠不好怎么办"
          maxlength="100"
          show-word-limit
        />
      </div>

      <div v-if="selectedMethod === 'viral_analysis'" class="input-section card">
        <h3>粘贴视频链接</h3>
        <el-input
          v-model="videoUrl"
          placeholder="粘贴抖音/快手/视频号链接"
          clearable
        />
      </div>

      <div v-if="selectedMethod === 'recommend'" class="recommend-section">
        <h3 class="section-title">选择推荐主题</h3>
        <div
          v-for="(item, index) in recommendations"
          :key="index"
          class="recommend-card card"
          :class="{ selected: selectedRecommend === index }"
          @click="selectRecommend(index)"
        >
          <div class="recommend-header">
            <span class="level-tag" :class="'level-' + item.level">{{ item.level }}</span>
            <span class="recommend-title">{{ item.title }}</span>
          </div>
          <p class="recommend-reason">{{ item.reason }}</p>
        </div>
      </div>

      <el-button
        type="primary"
        size="large"
        class="start-btn"
        :loading="creating"
        :disabled="!canStart"
        @click="startCreation"
      >
        开始AI创作
      </el-button>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, onMounted } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { ElMessage } from 'element-plus'
import {
  IFire,
  IVideoPlay,
  IEdit,
} from '@element-plus/icons-vue'
import { createProject } from '@/api/creation'

const route = useRoute()
const router = useRouter()

const selectedMethod = ref('custom')
const topic = ref('')
const videoUrl = ref('')
const selectedRecommend = ref(-1)
const creating = ref(false)

const recommendations = ref([
  {
    level: 'A',
    title: '睡眠成为近期热门话题',
    reason: '45岁女性对睡眠质量的关注增长明显，你过去情绪类视频咨询率较高',
    topic: '睡眠不好怎么办',
  },
  {
    level: 'B',
    title: '肠道健康咨询潜力高',
    reason: '最近肠道健康相关内容转化率提升，适合你的受众群体',
    topic: '肠胃不好怎么调理',
  },
  {
    level: 'C',
    title: '更年期话题容易涨粉',
    reason: '更年期相关内容互动率高，适合建立专家人设',
    topic: '更年期怎么调理',
  },
])

const canStart = computed(() => {
  if (selectedMethod.value === 'custom') {
    return topic.value.trim().length > 0
  }
  if (selectedMethod.value === 'viral_analysis') {
    return videoUrl.value.trim().length > 0
  }
  if (selectedMethod.value === 'recommend') {
    return selectedRecommend.value >= 0
  }
  return false
})

onMounted(() => {
  const type = route.query.type as string
  if (type) {
    selectedMethod.value = type
  }
  if (route.query.topic) {
    topic.value = route.query.topic as string
  }
})

function selectMethod(method: string) {
  selectedMethod.value = method
  selectedRecommend.value = -1
}

function selectRecommend(index: number) {
  selectedRecommend.value = index
  topic.value = recommendations.value[index].topic
}

async function startCreation() {
  if (!canStart.value) return

  let finalTopic = topic.value
  if (selectedMethod.value === 'recommend' && selectedRecommend.value >= 0) {
    finalTopic = recommendations.value[selectedRecommend.value].topic
  }
  if (selectedMethod.value === 'viral_analysis') {
    finalTopic = '爆款解析：' + videoUrl.value
  }

  creating.value = true
  try {
    const res = await createProject(selectedMethod.value, finalTopic)
    ElMessage.success('创作项目已创建')
    router.push({
      path: '/result',
      query: { task_id: (res as any).task_id },
    })
  } catch (error) {
    console.error('创建失败:', error)
    ElMessage.error('创建失败')
  } finally {
    creating.value = false
  }
}
</script>

<style scoped>
.creation-page {
  min-height: 100vh;
  background: #f5f7fa;
}

.page-header {
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

.page-container {
  padding: 0 16px;
  max-width: 768px;
  margin: -30px auto 0;
}

.creation-methods {
  margin-bottom: 20px;
}

.method-card {
  background: #fff;
  border-radius: 12px;
  padding: 16px;
  margin-bottom: 12px;
  display: flex;
  align-items: center;
  cursor: pointer;
  border: 2px solid transparent;
  transition: all 0.3s;
  box-shadow: 0 2px 12px 0 rgba(0, 0, 0, 0.08);
}

.method-card.active {
  border-color: #667eea;
  box-shadow: 0 4px 20px rgba(102, 126, 234, 0.3);
}

.method-icon {
  width: 48px;
  height: 48px;
  border-radius: 10px;
  display: flex;
  align-items: center;
  justify-content: center;
  margin-right: 14px;
  color: #fff;
  flex-shrink: 0;
}

.method-icon.recommend {
  background: linear-gradient(135deg, #ff6b6b, #feca57);
}

.method-icon.viral {
  background: linear-gradient(135deg, #5f27cd, #341f97);
}

.method-icon.custom {
  background: linear-gradient(135deg, #00d2d3, #01a3a4);
}

.method-info {
  flex: 1;
}

.method-info h3 {
  font-size: 16px;
  margin-bottom: 4px;
  color: #303133;
}

.method-info p {
  font-size: 12px;
  color: #909399;
}

.input-section h3 {
  font-size: 16px;
  margin-bottom: 12px;
  color: #303133;
}

.section-title {
  font-size: 16px;
  margin-bottom: 12px;
  padding: 0 4px;
  color: #303133;
}

.recommend-section {
  margin-bottom: 20px;
}

.recommend-card {
  cursor: pointer;
  margin-bottom: 12px;
  border: 2px solid transparent;
  transition: all 0.3s;
}

.recommend-card.selected {
  border-color: #667eea;
  box-shadow: 0 4px 20px rgba(102, 126, 234, 0.3);
}

.recommend-header {
  display: flex;
  align-items: center;
  margin-bottom: 8px;
}

.level-tag {
  width: 28px;
  height: 28px;
  border-radius: 50%;
  display: flex;
  align-items: center;
  justify-content: center;
  font-weight: bold;
  font-size: 14px;
  margin-right: 10px;
  color: #fff;
}

.level-A {
  background: linear-gradient(135deg, #ff6b6b, #feca57);
}

.level-B {
  background: linear-gradient(135deg, #5f27cd, #a29bfe);
}

.level-C {
  background: linear-gradient(135deg, #00d2d3, #54a0ff);
}

.recommend-title {
  font-size: 15px;
  font-weight: 600;
  color: #303133;
}

.recommend-reason {
  font-size: 13px;
  color: #909399;
  line-height: 1.5;
}

.start-btn {
  width: 100%;
  height: 50px;
  font-size: 16px;
  margin-bottom: 20px;
  background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
  border: none;
}
</style>
