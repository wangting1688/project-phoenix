<template>
  <div class="h3-library-page">
    <div class="page-header">
      <h2>H3 人物 / 场景素材库</h2>
      <p>管理主播照片与讲解场景，创作时可直接选用</p>
    </div>

    <div class="page-container">
      <div class="section">
        <div class="section-header">
          <h3>主播照片</h3>
          <el-button type="primary" size="small" @click="selectImage">
            <el-icon><IUploadFilled /></el-icon>&nbsp;上传照片
          </el-button>
          <input ref="fileInput" type="file" accept="image/jpeg,image/png,image/webp" hidden @change="onFileChange" />
        </div>

        <div v-if="portraits.length" class="portrait-grid">
          <div v-for="p in portraits" :key="p.filename" class="portrait-card card">
            <img :src="imgSrcMap[p.url]" class="portrait-img" alt="主播照片" />
            <div class="portrait-actions">
              <el-button size="small" type="primary" @click="choosePerson(p)">用于创作</el-button>
              <el-button size="small" type="danger" plain @click="removePortrait(p)">删除</el-button>
            </div>
          </div>
        </div>
        <el-empty v-else description="还没有主播照片，先上传一张正面照" />
      </div>

      <div class="section">
        <div class="section-header">
          <h3>自定义场景图</h3>
          <el-button type="primary" size="small" @click="sceneInput?.click()">
            <el-icon><IUploadFilled /></el-icon>&nbsp;上传场景图
          </el-button>
          <input ref="sceneInput" type="file" accept="image/jpeg,image/png,image/webp" hidden @change="onSceneFileChange" />
        </div>
        <div v-if="scenes.length" class="scene-img-grid">
          <div v-for="sc in scenes" :key="sc.filename" class="scene-img-card card">
            <img :src="imgSrcMap[sc.url]" class="scene-img" alt="场景图" />
            <div class="portrait-actions">
              <el-button size="small" type="primary" @click="chooseSceneImage(sc)">用于创作</el-button>
              <el-button size="small" type="danger" plain @click="removeScene(sc)">删除</el-button>
            </div>
          </div>
        </div>
        <el-empty v-else description="还没有自定义场景图，上传一张你想要的背景图" />
      </div>

      <div class="section">
        <div class="section-header">
          <h3>内置讲解场景</h3>
        </div>
        <div class="scene-grid">
          <div
            v-for="opt in sceneOptions"
            :key="opt.value"
            class="scene-card card"
            @click="chooseScene(opt)"
          >
            <div class="scene-label">{{ opt.label }}</div>
            <div class="scene-desc">{{ opt.desc }}</div>
            <div class="scene-use">用于创作</div>
          </div>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { useRouter } from 'vue-router'
import { ElMessage } from 'element-plus'
import { IUploadFilled } from '@/utils/icons'
import { useUserStore } from '@/stores/user'
import { resolveMediaUrls } from '@/utils/mediaUrl'
import {
  uploadAnchorPortrait,
  listAnchorPortraits,
  deleteAnchorPortrait,
  type AnchorPortrait,
  uploadAnchorScene,
  listAnchorScenes,
  deleteAnchorScene,
  type AnchorScene,
} from '@/api/footage'

const router = useRouter()
const userStore = useUserStore()
const fileInput = ref<HTMLInputElement | null>(null)
const sceneInput = ref<HTMLInputElement | null>(null)
const portraits = ref<AnchorPortrait[]>([])
const scenes = ref<AnchorScene[]>([])

const sceneOptions = [
  { value: 'lecture', label: '会场讲课', desc: '讲台半身口播，专业稳重' },
  { value: 'park_walk', label: '公园散步', desc: '边走边讲，轻松自然' },
  { value: 'teahouse', label: '茶室座谈', desc: '茶室坐着讲，温暖亲切' },
  { value: 'street_walk', label: '商业街', desc: '街头行走讲解，有活力' },
  { value: 'kitchen', label: '厨房演示', desc: '居家厨房场景，生活化演示' },
  { value: 'office', label: '办公室', desc: '办公桌旁专业讲解' },
  { value: 'living_room', label: '客厅居家', desc: '沙发居家口播，亲切自然' },
  { value: 'balcony_garden', label: '阳台花园', desc: '阳台绿植背景，清爽明亮' },
  { value: 'study', label: '书房书柜', desc: '书柜背景，适合知识科普' },
  { value: 'cafe', label: '咖啡店', desc: '咖啡桌边聊天式口播' },
  { value: 'gym', label: '健身房', desc: '运动场景，健康活力' },
]

const imgSrcMap = ref<Record<string, string>>({})

async function resolveImgs(items: Array<{ url?: string }>) {
  const paths = [...new Set(items.map((it) => it.url?.replace(/^\/static\//, '')).filter(Boolean) as string[])]
  const map = await resolveMediaUrls(paths)
  items.forEach((it) => {
    if (it.url) imgSrcMap.value[it.url] = map[it.url.replace(/^\/static\//, '')] || ''
  })
}

async function loadPortraits() {
  try {
    const res = await listAnchorPortraits()
    portraits.value = res.items || []
    await resolveImgs(portraits.value)
  } catch {
    portraits.value = []
  }
}

async function loadScenes() {
  try {
    const res = await listAnchorScenes()
    scenes.value = res.items || []
    await resolveImgs(scenes.value)
  } catch {
    scenes.value = []
  }
}

function selectImage() {
  fileInput.value?.click()
}

async function onFileChange(e: Event) {
  const input = e.target as HTMLInputElement
  const f = input.files?.[0]
  input.value = ''
  if (!f) return
  if (!/image\/(jpeg|png|webp)/.test(f.type)) {
    ElMessage.error('请上传 jpg / png / webp 格式的照片')
    return
  }
  try {
    await uploadAnchorPortrait(f)
    ElMessage.success('照片已上传')
    await loadPortraits()
  } catch (err: any) {
    ElMessage.error(err?.response?.data?.detail || '上传失败')
  }
}

async function removePortrait(p: AnchorPortrait) {
  try {
    await deleteAnchorPortrait(p.filename)
    portraits.value = portraits.value.filter(x => x.filename !== p.filename)
    ElMessage.success('已删除')
  } catch (err: any) {
    ElMessage.error(err?.response?.data?.detail || '删除失败')
  }
}

async function onSceneFileChange(e: Event) {
  const input = e.target as HTMLInputElement
  const f = input.files?.[0]
  input.value = ''
  if (!f) return
  if (!/image\/(jpeg|png|webp)/.test(f.type)) {
    ElMessage.error('请上传 jpg / png / webp 格式的图片')
    return
  }
  try {
    await uploadAnchorScene(f)
    ElMessage.success('场景图已上传')
    await loadScenes()
  } catch (err: any) {
    ElMessage.error(err?.response?.data?.detail || '上传失败')
  }
}

async function removeScene(sc: AnchorScene) {
  try {
    await deleteAnchorScene(sc.filename)
    scenes.value = scenes.value.filter(x => x.filename !== sc.filename)
    ElMessage.success('已删除')
  } catch (err: any) {
    ElMessage.error(err?.response?.data?.detail || '删除失败')
  }
}

function choosePerson(p: AnchorPortrait) {
  localStorage.setItem('h3_person_image', p.person_image)
  ElMessage.success('已选择主播照片，去创作吧')
  router.push('/creation?step=3')
}

function chooseScene(opt: { value: string; label: string }) {
  localStorage.setItem('h3_scene', opt.value)
  localStorage.removeItem('h3_anchor_image')
  ElMessage.success(`已选择场景：${opt.label}`)
  router.push('/creation?step=3')
}

function chooseSceneImage(sc: AnchorScene) {
  localStorage.setItem('h3_anchor_image', sc.scene_image)
  localStorage.removeItem('h3_scene')
  ElMessage.success('已选择自定义场景图，去创作吧')
  router.push('/creation?step=3')
}

onMounted(() => {
  loadPortraits()
  loadScenes()
})
</script>

<style scoped>
.h3-library-page {
  min-height: 100vh;
  padding: 24px;
}
.page-header h2 { margin: 0 0 6px; }
.page-header p { margin: 0 0 20px; color: #909399; }
.page-container { max-width: 1100px; }
.section { margin-bottom: 24px; }
.section-header {
  display: flex; align-items: center; justify-content: space-between;
  margin-bottom: 14px;
}
.section-header h3 { margin: 0; }
.portrait-grid {
  display: grid; grid-template-columns: repeat(auto-fill, minmax(180px, 1fr)); gap: 14px;
}
.portrait-card { overflow: hidden; }
.portrait-img { width: 100%; aspect-ratio: 3 / 4; object-fit: cover; display: block; }
.portrait-actions { display: flex; gap: 8px; padding: 10px; }
.scene-grid {
  display: grid; grid-template-columns: repeat(auto-fill, minmax(220px, 1fr)); gap: 14px;
}
.scene-img-grid {
  display: grid; grid-template-columns: repeat(auto-fill, minmax(180px, 1fr)); gap: 14px;
}
.scene-img-card { overflow: hidden; }
.scene-img { width: 100%; aspect-ratio: 4 / 3; object-fit: cover; display: block; }
.scene-card { cursor: pointer; padding: 16px; transition: border-color .2s; }
.scene-card:hover { border-color: #409eff; }
.scene-label { font-size: 16px; font-weight: 600; margin-bottom: 6px; }
.scene-desc { color: #909399; font-size: 13px; margin-bottom: 10px; }
.scene-use { color: #409eff; font-size: 13px; }
</style>
