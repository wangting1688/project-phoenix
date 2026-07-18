<template>
  <div class="shooting-assistant-page">
    <!-- 页面标题 -->
    <div class="page-header">
      <h1>📸 AI拍摄助手</h1>
      <el-button type="primary" @click="generatePlan">
        ✨ 生成拍摄方案
      </el-button>
    </div>

    <!-- 主播能力卡片 -->
    <div class="ability-card">
      <div class="card-header">
        <h3>🎯 你的拍摄能力</h3>
        <el-button size="small" @click="showProfileEdit = true">编辑</el-button>
      </div>
      <div class="ability-grid">
        <div class="ability-item">
          <span class="ability-label">拍摄等级</span>
          <span class="ability-value">{{ profile.shooting_level }}</span>
        </div>
        <div class="ability-item">
          <span class="ability-label">可用场景</span>
          <span class="ability-value">{{ profile.available_scenes.join('、') }}</span>
        </div>
        <div class="ability-item">
          <span class="ability-label">相机技能</span>
          <span class="ability-value">{{ profile.camera_skill }}</span>
        </div>
        <div class="ability-item">
          <span class="ability-label">可用时间</span>
          <span class="ability-value">{{ profile.available_time }}</span>
        </div>
      </div>
      <div class="recommended-mode" :class="profile.recommended_mode">
        <span class="mode-icon">{{ getModeIcon(profile.recommended_mode) }}</span>
        <span class="mode-text">推荐模式：{{ getModeName(profile.recommended_mode) }}</span>
      </div>
    </div>

    <!-- 拍摄方案 -->
    <div v-if="plan" class="plan-section">
      <!-- 模式说明 -->
      <div class="mode-info-card" :class="plan.recommended_mode">
        <div class="mode-header">
          <span class="mode-title">{{ getModeName(plan.recommended_mode) }}</span>
          <span class="mode-time">⏱️ {{ plan.estimated_time }}</span>
        </div>
        <p class="mode-desc">{{ plan.mode_description }}</p>
      </div>

      <!-- 必须拍 -->
      <div class="shots-section">
        <h3>
          <span class="priority-badge required">必须拍</span>
          <span class="section-title">核心镜头</span>
        </h3>
        <div class="shots-list">
          <div
            v-for="shot in plan.required_shots"
            :key="shot.shot_number"
            class="shot-card required"
          >
            <div class="shot-header">
              <span class="shot-num">镜头 {{ shot.shot_number }}</span>
              <span class="shot-type">{{ shot.shot_type }}</span>
              <span class="shot-time">{{ formatTime(shot.start_time) }} - {{ formatTime(shot.end_time) }}</span>
            </div>
            <div class="shot-content">
              <div class="shot-script">{{ shot.script_content }}</div>
              <div class="shot-action">
                <span class="action-label">动作：</span>
                <span>{{ shot.action }}</span>
              </div>
              <div class="shot-details">
                <span>📷 {{ shot.camera_angle }}</span>
                <span>🎬 {{ shot.background }}</span>
              </div>
            </div>
          </div>
        </div>
      </div>

      <!-- 可选增强 -->
      <div v-if="plan.optional_shots.length > 0" class="shots-section">
        <h3>
          <span class="priority-badge optional">可选增强</span>
          <span class="section-title">提升质量（可选）</span>
        </h3>
        <div class="shots-list">
          <div
            v-for="shot in plan.optional_shots"
            :key="shot.shot_number"
            class="shot-card optional"
          >
            <div class="shot-header">
              <span class="shot-num">镜头 {{ shot.shot_number }}</span>
              <span class="shot-type">{{ shot.shot_type }}</span>
              <span class="shot-time">{{ formatTime(shot.start_time) }} - {{ formatTime(shot.end_time) }}</span>
            </div>
            <div class="shot-content">
              <div class="shot-desc">{{ shot.description }}</div>
              <div v-if="shot.script_content" class="shot-script">{{ shot.script_content }}</div>
              <div class="shot-details">
                <span>🎬 {{ shot.background }}</span>
              </div>
            </div>
          </div>
        </div>
      </div>

      <!-- 素材需求清单 -->
      <div class="assets-section">
        <h3>📦 素材需求清单</h3>
        
        <!-- 必须素材 -->
        <div class="assets-list">
          <h4>
            <span class="star">★★★★★</span>
            必须素材
          </h4>
          <div class="asset-items">
            <div
              v-for="(asset, index) in plan.required_assets"
              :key="'req-' + index"
              class="asset-item"
            >
              <span class="asset-icon">🎤</span>
              <span class="asset-info">{{ asset.role }}</span>
              <span class="asset-meta">{{ asset.emotion }} · {{ asset.duration.toFixed(1) }}秒</span>
            </div>
          </div>
        </div>

        <!-- 可选素材 -->
        <div v-if="plan.optional_assets.length > 0" class="assets-list">
          <h4>
            <span class="star optional-star">★★★</span>
            可选素材
          </h4>
          <div class="asset-items">
            <div
              v-for="(asset, index) in plan.optional_assets"
              :key="'opt-' + index"
              class="asset-item optional"
            >
              <span class="asset-icon">🎬</span>
              <span class="asset-info">{{ asset.scene }}</span>
              <span class="asset-meta">生活素材 · {{ asset.duration.toFixed(1) }}秒</span>
            </div>
          </div>
        </div>
      </div>

      <!-- 素材匹配结果 -->
      <div v-if="assetMatch" class="match-section">
        <h3>🔍 素材匹配结果</h3>
        
        <div class="match-grid">
          <!-- 已匹配 -->
          <div class="match-card matched">
            <h4>✅ 已匹配素材</h4>
            <div v-if="assetMatch.matched.length > 0" class="matched-list">
              <div
                v-for="item in assetMatch.matched"
                :key="item.asset.id"
                class="matched-item"
              >
                <div class="asset-preview">
                  <el-icon :size="32"><IVideoPlay /></el-icon>
                </div>
                <div class="asset-info">
                  <span class="asset-name">{{ item.asset.name }}</span>
                  <span class="asset-tags">{{ item.asset.emotion }} · {{ item.asset.scene }}</span>
                </div>
              </div>
            </div>
            <div v-else class="empty">暂无匹配素材</div>
          </div>

          <!-- 缺少的素材 -->
          <div class="match-card missing">
            <h4>📷 需要拍摄</h4>
            <div v-if="assetMatch.missing.length > 0" class="missing-list">
              <div
                v-for="(req, index) in assetMatch.missing"
                :key="index"
                class="missing-item"
              >
                <span class="req-type">{{ req.type === 'creator' ? '🎤' : '🎬' }}</span>
                <span class="req-info">{{ req.role || req.scene }}</span>
                <span class="req-emotion">{{ req.emotion }}</span>
              </div>
            </div>
            <div v-else class="empty">🎉 所有素材已就绪！</div>
          </div>
        </div>
      </div>

      <!-- 操作按钮 -->
      <div class="action-buttons">
        <el-button @click="matchAssets">🔍 匹配素材</el-button>
        <el-button type="primary" @click="goToEditing">🎬 开始剪辑</el-button>
      </div>
    </div>

    <!-- 文案输入 -->
    <div v-else class="input-section">
      <div class="input-card">
        <h3>📝 输入文案，AI帮你制定拍摄方案</h3>
        <el-input
          v-model="scriptContent"
          type="textarea"
          :rows="8"
          placeholder="粘贴你的视频文案..."
        />
        <el-button
          type="primary"
          size="large"
          :disabled="!scriptContent.trim()"
          :loading="generating"
          @click="generatePlan"
        >
          ✨ 生成拍摄方案
        </el-button>
      </div>
    </div>

    <!-- 编辑能力画像弹窗 -->
    <el-dialog
      v-model="showProfileEdit"
      title="编辑拍摄能力"
      width="90%"
    >
      <el-form :model="profile" label-width="100px">
        <el-form-item label="拍摄等级">
          <el-select v-model="profile.shooting_level">
            <el-option label="基础" value="基础" />
            <el-option label="进阶" value="进阶" />
            <el-option label="高级" value="高级" />
          </el-select>
        </el-form-item>
        
        <el-form-item label="可用场景">
          <el-checkbox-group v-model="profile.available_scenes">
            <el-checkbox label="固定背景" />
            <el-checkbox label="客厅" />
            <el-checkbox label="厨房" />
            <el-checkbox label="户外" />
            <el-checkbox label="卧室" />
          </el-checkbox-group>
        </el-form-item>
        
        <el-form-item label="相机技能">
          <el-select v-model="profile.camera_skill">
            <el-option label="低" value="低" />
            <el-option label="中" value="中" />
            <el-option label="高" value="高" />
          </el-select>
        </el-form-item>
        
        <el-form-item label="可用时间">
          <el-select v-model="profile.available_time">
            <el-option label="每天30分钟" value="每天30分钟" />
            <el-option label="每天1小时" value="每天1小时" />
            <el-option label="每周几次" value="每周几次" />
          </el-select>
        </el-form-item>
      </el-form>

      <template #footer>
        <el-button @click="showProfileEdit = false">取消</el-button>
        <el-button type="primary" @click="saveProfile">保存</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { useRouter } from 'vue-router'
import { ElMessage } from 'element-plus'
import { IVideoPlay } from '@/utils/icons'
import {
  getShootingProfile,
  updateShootingProfile,
  generateShootingPlan,
  matchAssetsForPlan,
  type ShootingProfile,
  type ShootingPlan,
  type MatchResult,
} from '@/api/shootingAssistant'

const router = useRouter()

const profile = ref<ShootingProfile>({
  shooting_level: '基础',
  available_scenes: ['固定背景'],
  camera_skill: '低',
  editing_skill: '低',
  available_time: '每天30分钟',
  recommended_mode: 'basic',
})

const plan = ref<ShootingPlan | null>(null)
const assetMatch = ref<MatchResult | null>(null)

const scriptContent = ref('')
const generating = ref(false)
const showProfileEdit = ref(false)

const getModeName = (mode: string) => {
  const names: Record<string, string> = {
    basic: '基础模式',
    intermediate: '进阶模式',
    advanced: '高级模式',
  }
  return names[mode] || '基础模式'
}

const getModeIcon = (mode: string) => {
  const icons: Record<string, string> = {
    basic: '📱',
    intermediate: '🎥',
    advanced: '🎬',
  }
  return icons[mode] || '📱'
}

const formatTime = (seconds: number) => {
  const min = Math.floor(seconds / 60)
  const sec = Math.floor(seconds % 60)
  return `${min}:${sec.toString().padStart(2, '0')}`
}

const loadProfile = async () => {
  try {
    const res = await getShootingProfile()
    if (res.data.success) {
      profile.value = res.data.data
    }
  } catch (error) {
    console.error('Load profile failed:', error)
  }
}

const saveProfile = async () => {
  try {
    const res = await updateShootingProfile(profile.value)
    if (res.data.success) {
      ElMessage.success('更新成功')
      showProfileEdit.value = false
    }
  } catch (error) {
    console.error('Save profile failed:', error)
    ElMessage.error('保存失败')
  }
}

const generatePlan = async () => {
  if (!scriptContent.value.trim()) {
    ElMessage.warning('请输入文案')
    return
  }

  generating.value = true
  try {
    const res = await generateShootingPlan(1, scriptContent.value)
    if (res.data.success) {
      plan.value = res.data.data
      ElMessage.success('拍摄方案已生成')
    }
  } catch (error) {
    console.error('Generate plan failed:', error)
    ElMessage.error('生成失败')
  } finally {
    generating.value = false
  }
}

const matchAssets = async () => {
  if (!plan.value) return

  try {
    const res = await matchAssetsForPlan(1)
    if (res.data.success) {
      assetMatch.value = res.data.data
    }
  } catch (error) {
    console.error('Match assets failed:', error)
  }
}

const goToEditing = () => {
  ElMessage.info('智能剪辑功能即将上线')
}

onMounted(() => {
  loadProfile()
})
</script>

<style scoped>
.shooting-assistant-page {
  padding: 16px;
}

.page-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 20px;
}

.page-header h1 {
  font-size: 24px;
  margin: 0;
}

/* 能力卡片 */
.ability-card {
  background: white;
  border-radius: 12px;
  padding: 20px;
  box-shadow: 0 2px 8px rgba(0, 0, 0, 0.05);
  margin-bottom: 20px;
}

.card-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 16px;
}

.card-header h3 {
  margin: 0;
  font-size: 16px;
}

.ability-grid {
  display: grid;
  grid-template-columns: repeat(2, 1fr);
  gap: 12px;
  margin-bottom: 16px;
}

.ability-item {
  padding: 12px;
  background: #f8f9fa;
  border-radius: 8px;
}

.ability-label {
  display: block;
  font-size: 12px;
  color: #888;
  margin-bottom: 4px;
}

.ability-value {
  font-size: 14px;
  font-weight: 500;
  color: #333;
}

.recommended-mode {
  padding: 12px;
  border-radius: 8px;
  display: flex;
  align-items: center;
  gap: 8px;
}

.recommended-mode.basic {
  background: #e8f5e9;
  color: #388e3c;
}

.recommended-mode.intermediate {
  background: #fff3e0;
  color: #f57c00;
}

.recommended-mode.advanced {
  background: #f3e5f5;
  color: #7b1fa2;
}

.mode-icon {
  font-size: 20px;
}

.mode-text {
  font-size: 14px;
}

/* 模式信息卡 */
.mode-info-card {
  padding: 20px;
  border-radius: 12px;
  margin-bottom: 20px;
}

.mode-info-card.basic {
  background: linear-gradient(135deg, #e8f5e9, #c8e6c9);
}

.mode-info-card.intermediate {
  background: linear-gradient(135deg, #fff3e0, #ffe0b2);
}

.mode-info-card.advanced {
  background: linear-gradient(135deg, #f3e5f5, #e1bee7);
}

.mode-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 8px;
}

.mode-title {
  font-size: 18px;
  font-weight: 600;
}

.mode-time {
  font-size: 14px;
}

.mode-desc {
  margin: 0;
  font-size: 14px;
  opacity: 0.8;
}

/* 镜头列表 */
.shots-section {
  background: white;
  border-radius: 12px;
  padding: 20px;
  box-shadow: 0 2px 8px rgba(0, 0, 0, 0.05);
  margin-bottom: 20px;
}

.shots-section h3 {
  display: flex;
  align-items: center;
  gap: 12px;
  margin: 0 0 16px;
}

.priority-badge {
  padding: 4px 12px;
  border-radius: 20px;
  font-size: 12px;
  font-weight: 500;
}

.priority-badge.required {
  background: #fef0f0;
  color: #f56c6c;
}

.priority-badge.optional {
  background: #fff7e6;
  color: #e6a23c;
}

.section-title {
  font-size: 16px;
}

.shots-list {
  display: flex;
  flex-direction: column;
  gap: 12px;
}

.shot-card {
  padding: 16px;
  border-radius: 8px;
}

.shot-card.required {
  background: #fafafa;
  border-left: 4px solid #67c23a;
}

.shot-card.optional {
  background: #fffcf5;
  border-left: 4px solid #e6a23c;
}

.shot-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 12px;
}

.shot-num {
  font-weight: 600;
}

.shot-type {
  font-size: 12px;
  color: #888;
}

.shot-time {
  font-size: 12px;
  color: #667eea;
}

.shot-script {
  font-size: 14px;
  line-height: 1.6;
  margin-bottom: 8px;
}

.shot-action {
  font-size: 13px;
  color: #666;
  margin-bottom: 8px;
}

.action-label {
  color: #888;
}

.shot-details {
  display: flex;
  gap: 16px;
  font-size: 12px;
  color: #888;
}

/* 素材需求 */
.assets-section {
  background: white;
  border-radius: 12px;
  padding: 20px;
  box-shadow: 0 2px 8px rgba(0, 0, 0, 0.05);
  margin-bottom: 20px;
}

.assets-section h3 {
  margin: 0 0 16px;
  font-size: 16px;
}

.assets-list {
  margin-bottom: 16px;
}

.assets-list:last-child {
  margin-bottom: 0;
}

.assets-list h4 {
  display: flex;
  align-items: center;
  gap: 8px;
  margin: 0 0 12px;
  font-size: 14px;
}

.star {
  color: #f5a623;
}

.optional-star {
  color: #e0e0e0;
}

.optional-star:nth-child(-n+3) {
  color: #f5a623;
}

.asset-items {
  display: flex;
  flex-wrap: wrap;
  gap: 12px;
}

.asset-item {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 8px 16px;
  background: #f8f9fa;
  border-radius: 20px;
  font-size: 13px;
}

.asset-item.optional {
  background: #fffcf5;
}

.asset-icon {
  font-size: 16px;
}

.asset-info {
  font-weight: 500;
}

.asset-meta {
  font-size: 12px;
  color: #888;
}

/* 素材匹配 */
.match-section {
  background: white;
  border-radius: 12px;
  padding: 20px;
  box-shadow: 0 2px 8px rgba(0, 0, 0, 0.05);
  margin-bottom: 20px;
}

.match-section h3 {
  margin: 0 0 16px;
  font-size: 16px;
}

.match-grid {
  display: grid;
  grid-template-columns: repeat(2, 1fr);
  gap: 16px;
}

.match-card {
  padding: 16px;
  border-radius: 8px;
}

.match-card.matched {
  background: #f0f9eb;
}

.match-card.missing {
  background: #fff5f5;
}

.match-card h4 {
  margin: 0 0 12px;
  font-size: 14px;
}

.matched-list,
.missing-list {
  display: flex;
  flex-direction: column;
  gap: 12px;
}

.matched-item {
  display: flex;
  align-items: center;
  gap: 12px;
  padding: 8px;
  background: white;
  border-radius: 6px;
}

.asset-preview {
  width: 48px;
  height: 48px;
  background: #f5f7fa;
  border-radius: 4px;
  display: flex;
  align-items: center;
  justify-content: center;
}

.asset-name {
  display: block;
  font-size: 13px;
  font-weight: 500;
}

.asset-tags {
  font-size: 12px;
  color: #888;
}

.missing-item {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 8px;
  background: rgba(245, 108, 108, 0.1);
  border-radius: 6px;
  font-size: 13px;
}

.empty {
  text-align: center;
  padding: 20px;
  color: #888;
}

/* 操作按钮 */
.action-buttons {
  display: flex;
  gap: 12px;
  justify-content: center;
}

.action-buttons .el-button {
  padding: 12px 32px;
}

/* 输入区域 */
.input-section {
  max-width: 600px;
  margin: 0 auto;
}

.input-card {
  background: white;
  border-radius: 12px;
  padding: 24px;
  box-shadow: 0 2px 8px rgba(0, 0, 0, 0.05);
}

.input-card h3 {
  margin: 0 0 16px;
  font-size: 16px;
}

.input-card textarea {
  margin-bottom: 16px;
}
</style>