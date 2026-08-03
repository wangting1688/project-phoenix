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
        <h3>爆款视频解析</h3>
        <p class="method-hint">
          填写对标视频的真实数据，AI 会拆解爆点并生成你的原创选题与文案。
        </p>
      </div>

      <el-button
        type="primary"
        size="large"
        class="start-btn"
        :loading="creating"
        :disabled="!canStart"
        @click="startCreation"
      >
        {{ selectedMethod === 'viral_analysis' ? '去解析爆款视频' : '开始AI创作' }}
      </el-button>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, onMounted } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { ElMessage } from 'element-plus'
import {
  IVideoPlay,
  IEdit,
} from '@/utils/icons'
import { createProject } from '@/api/creation'

const route = useRoute()
const router = useRouter()

const selectedMethod = ref('custom')
const topic = ref('')
const creating = ref(false)

const canStart = computed(() => {
  if (selectedMethod.value === 'viral_analysis') return true
  return topic.value.trim().length > 0
})

onMounted(() => {
  const type = route.query.type as string
  if (type === 'custom' || type === 'viral_analysis') {
    selectedMethod.value = type
  }
  if (route.query.topic) {
    topic.value = route.query.topic as string
  }
})

function selectMethod(method: string) {
  selectedMethod.value = method
}

async function startCreation() {
  if (!canStart.value) return

  // 爆款解析有独立的真实解析流程 (拆解爆点→生成原创选题), 不能只把链接当主题丢给 AI
  if (selectedMethod.value === 'viral_analysis') {
    router.push('/viral-analysis')
    return
  }

  creating.value = true
  try {
    const res = await createProject(selectedMethod.value, topic.value)
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

.method-hint {
  font-size: 13px;
  color: #909399;
  line-height: 1.6;
  margin: 0;
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
