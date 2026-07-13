<template>
  <div class="footage-page">
    <div class="page-header">
      <h2>素材库</h2>
      <p>管理你的真人素材，AI会自动匹配使用</p>
    </div>

    <div class="page-container">
      <div class="upload-section">
        <el-upload
          class="upload-area"
          drag
          :show-file-list="false"
          :http-request="handleUpload"
          accept="video/*"
        >
          <el-icon class="upload-icon" :size="40"><IUploadFilled /></el-icon>
          <div class="upload-text">点击或拖拽上传视频素材</div>
          <div class="upload-hint">支持 mp4 / mov / avi 格式</div>
        </el-upload>
      </div>

      <div class="section">
        <div class="section-header">
          <h3>素材分类</h3>
          <el-button type="primary" size="small" @click="showCategoryDialog = true">
            新建分类
          </el-button>
        </div>

        <div class="category-list">
          <div
            v-for="cat in categories"
            :key="cat.id"
            class="category-tag"
            :class="{ active: selectedCategory === cat.id }"
            @click="selectCategory(cat.id)"
          >
            <el-icon :size="16"><IFolder /></el-icon>
            <span>{{ cat.name }}</span>
          </div>
        </div>
      </div>

      <div class="section">
        <div class="section-header">
          <h3>我的素材 ({{ footages.length }})</h3>
        </div>

        <div v-if="footages.length > 0" class="footage-grid">
          <div v-for="f in footages" :key="f.id" class="footage-card">
            <div class="footage-thumb">
              <el-icon :size="32"><IVideoCamera /></el-icon>
              <span class="duration">{{ formatDuration(f.duration) }}</span>
            </div>
            <div class="footage-info">
              <p class="filename">{{ f.filename }}</p>
              <div class="tags">
                <el-tag v-if="f.scene" size="small" type="info">{{ f.scene }}</el-tag>
                <el-tag v-if="f.emotion" size="small">{{ f.emotion }}</el-tag>
              </div>
            </div>
            <div class="footage-actions">
              <el-button size="small" @click="editFootage(f)">编辑</el-button>
              <el-button size="small" type="danger" plain @click="handleDelete(f.id)">删除</el-button>
            </div>
          </div>
        </div>

        <div v-else class="empty-state">
          <el-empty description="还没有素材，上传第一个吧！">
            <el-button type="primary" @click="showGuide = true">查看拍摄指南</el-button>
          </el-empty>
        </div>
      </div>

      <div v-if="showGuide" class="guide-section section">
        <h3>推荐拍摄清单</h3>
        <p class="guide-hint">按照以下清单拍摄素材，AI会自动匹配使用</p>

        <div v-for="(shots, type) in suggestShots" :key="type" class="guide-category">
          <h4>{{ getTypeName(type) }}</h4>
          <div class="guide-shots">
            <div v-for="(s, i) in shots" :key="i" class="guide-shot">
              <span class="shot-scene">{{ s.scene }}</span>
              <span class="shot-action">{{ s.action }}</span>
              <span class="shot-emotion">{{ s.emotion }}</span>
            </div>
          </div>
        </div>
      </div>
    </div>

    <el-dialog v-model="showCategoryDialog" title="新建分类" width="90%">
      <el-form :model="categoryForm">
        <el-form-item label="分类名称">
          <el-input v-model="categoryForm.name" placeholder="如：生活类、健康类" />
        </el-form-item>
        <el-form-item label="分类类型">
          <el-select v-model="categoryForm.type" style="width: 100%">
            <el-option label="生活类" value="life" />
            <el-option label="健康类" value="health" />
            <el-option label="情感类" value="emotion" />
            <el-option label="工作类" value="work" />
          </el-select>
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="showCategoryDialog = false">取消</el-button>
        <el-button type="primary" @click="handleCreateCategory">确定</el-button>
      </template>
    </el-dialog>

    <el-dialog v-model="showEditDialog" title="编辑素材标签" width="90%">
      <el-form :model="editForm" label-position="top">
        <el-form-item label="场景">
          <el-input v-model="editForm.scene" placeholder="如：厨房、卧室" />
        </el-form-item>
        <el-form-item label="动作">
          <el-input v-model="editForm.action" placeholder="如：做饭、喝水" />
        </el-form-item>
        <el-form-item label="情绪">
          <el-input v-model="editForm.emotion" placeholder="如：温暖、思考" />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="showEditDialog = false">取消</el-button>
        <el-button type="primary" @click="handleUpdateFootage">保存</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup lang="ts">
import { ref, reactive, onMounted } from 'vue'
import { ElMessage } from 'element-plus'
import { IUploadFilled, IFolder, IVideoCamera } from '@element-plus/icons-vue'
import {
  getCategories, createCategory, uploadFootage,
  listFootages, updateFootage, deleteFootage, getSuggestShots,
  type FootageCategory, type Footage, type SuggestShot,
} from '@/api/footage'

const categories = ref<FootageCategory[]>([])
const footages = ref<Footage[]>([])
const selectedCategory = ref<number | null>(null)
const showCategoryDialog = ref(false)
const showEditDialog = ref(false)
const showGuide = ref(false)
const suggestShots = ref<Record<string, SuggestShot[]>>({})

const categoryForm = reactive({ name: '', type: 'life' })
const editForm = reactive({ id: 0, scene: '', action: '', emotion: '' })

onMounted(() => {
  loadData()
  loadSuggestShots()
})

async function loadData() {
  try {
    const [cats, foots] = await Promise.all([
      getCategories(),
      listFootages(),
    ])
    categories.value = cats || []
    footages.value = (foots as any)?.items || []
  } catch (e) {
    console.error('加载失败', e)
  }
}

async function loadSuggestShots() {
  try {
    suggestShots.value = await getSuggestShots() || {}
  } catch (e) {
    console.error('加载指南失败', e)
  }
}

async function handleUpload(options: any) {
  try {
    ElMessage.info('正在上传...')
    await uploadFootage(options.file, selectedCategory.value || undefined)
    ElMessage.success('上传成功')
    loadData()
  } catch (e) {
    ElMessage.error('上传失败')
  }
}

async function handleCreateCategory() {
  if (!categoryForm.name) {
    ElMessage.warning('请输入分类名称')
    return
  }
  try {
    await createCategory(categoryForm.name, categoryForm.type)
    ElMessage.success('创建成功')
    showCategoryDialog.value = false
    categoryForm.name = ''
    loadData()
  } catch (e) {
    ElMessage.error('创建失败')
  }
}

function selectCategory(id: number) {
  selectedCategory.value = selectedCategory.value === id ? null : id
  loadFootages()
}

async function loadFootages() {
  const params: any = {}
  if (selectedCategory.value) params.category_id = selectedCategory.value
  const res = await listFootages(params)
  footages.value = (res as any)?.items || []
}

function editFootage(f: Footage) {
  editForm.id = f.id
  editForm.scene = f.scene || ''
  editForm.action = f.action || ''
  editForm.emotion = f.emotion || ''
  showEditDialog.value = true
}

async function handleUpdateFootage() {
  try {
    await updateFootage(editForm.id, {
      scene: editForm.scene,
      action: editForm.action,
      emotion: editForm.emotion,
    })
    ElMessage.success('更新成功')
    showEditDialog.value = false
    loadFootages()
  } catch (e) {
    ElMessage.error('更新失败')
  }
}

async function handleDelete(id: number) {
  try {
    await deleteFootage(id)
    ElMessage.success('删除成功')
    loadFootages()
  } catch (e) {
    ElMessage.error('删除失败')
  }
}

function formatDuration(sec: number) {
  if (!sec) return '0:00'
  const m = Math.floor(sec / 60)
  const s = sec % 60
  return `${m}:${String(s).padStart(2, '0')}`
}

function getTypeName(type: string) {
  const map: Record<string, string> = {
    life: '生活类', health: '健康类', emotion: '情感类', work: '工作类',
  }
  return map[type] || type
}
</script>

<style scoped>
.footage-page { min-height: 100vh; background: #f5f7fa; }

.page-header {
  background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
  padding: 40px 20px 50px; color: #fff; text-align: center;
}
.page-header h2 { font-size: 24px; margin-bottom: 8px; }
.page-header p { font-size: 14px; opacity: 0.9; }

.page-container { padding: 0 16px; max-width: 768px; margin: -30px auto 0; }

.upload-section { margin-bottom: 20px; }
.upload-area {
  width: 100%; background: #fff; border-radius: 12px;
  border: 2px dashed #d0d7de; padding: 30px; text-align: center;
}
.upload-area:hover { border-color: #667eea; }
.upload-icon { color: #667eea; margin-bottom: 10px; }
.upload-text { font-size: 16px; color: #303133; margin-bottom: 4px; }
.upload-hint { font-size: 12px; color: #909399; }

.section { margin-bottom: 20px; }
.section-header {
  display: flex; justify-content: space-between; align-items: center;
  margin-bottom: 12px; padding: 0 4px;
}
.section-header h3 { font-size: 18px; color: #303133; }

.category-list { display: flex; flex-wrap: wrap; gap: 10px; }
.category-tag {
  display: flex; align-items: center; gap: 6px;
  background: #fff; border: 1px solid #e4e7ed; border-radius: 20px;
  padding: 8px 16px; font-size: 14px; cursor: pointer; transition: all 0.2s;
}
.category-tag.active {
  background: linear-gradient(135deg, #667eea, #764ba2);
  color: #fff; border-color: transparent;
}

.footage-grid { display: grid; grid-template-columns: repeat(2, 1fr); gap: 12px; }
.footage-card {
  background: #fff; border-radius: 12px; overflow: hidden;
  box-shadow: 0 2px 12px rgba(0,0,0,0.08);
}
.footage-thumb {
  position: relative; aspect-ratio: 9/16;
  background: linear-gradient(135deg, #667eea20, #764ba220);
  display: flex; align-items: center; justify-content: center; color: #667eea;
}
.duration {
  position: absolute; bottom: 6px; right: 6px;
  background: rgba(0,0,0,0.6); color: #fff; font-size: 11px;
  padding: 2px 6px; border-radius: 4px;
}
.footage-info { padding: 10px; }
.filename { font-size: 13px; margin-bottom: 6px; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.tags { display: flex; gap: 4px; flex-wrap: wrap; }
.footage-actions { display: flex; gap: 6px; padding: 0 10px 10px; }

.empty-state {
  background: #fff; border-radius: 12px; padding: 40px 20px; text-align: center;
}

.guide-section {
  background: #fff; border-radius: 12px; padding: 20px;
  box-shadow: 0 2px 12px rgba(0,0,0,0.08);
}
.guide-hint { font-size: 13px; color: #909399; margin-bottom: 16px; }
.guide-category { margin-bottom: 16px; }
.guide-category h4 { font-size: 15px; margin-bottom: 8px; color: #303133; }
.guide-shots { display: flex; flex-wrap: wrap; gap: 8px; }
.guide-shot {
  display: flex; gap: 6px; background: #f5f7fa; border-radius: 8px;
  padding: 6px 12px; font-size: 13px;
}
.shot-scene { font-weight: 600; color: #303133; }
.shot-action { color: #606266; }
.shot-emotion { color: #667eea; }
</style>
