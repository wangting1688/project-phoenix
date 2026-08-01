import { createRouter, createWebHistory, RouteRecordRaw } from 'vue-router'
import { useUserStore } from '@/stores/user'

const routes: RouteRecordRaw[] = [
  {
    path: '/login',
    name: 'Login',
    component: () => import('@/views/login/index.vue'),
    meta: { title: '登录', requiresAuth: false },
  },
  {
    path: '/register',
    name: 'Register',
    component: () => import('@/views/register/index.vue'),
    meta: { title: '注册', requiresAuth: false },
  },
  {
    path: '/',
    name: 'Home',
    component: () => import('@/layouts/MainLayout.vue'),
    redirect: '/home',
    meta: { requiresAuth: true },
    children: [
      {
        path: 'home',
        name: 'HomePage',
        component: () => import('@/views/home/index.vue'),
        meta: { title: '创作中心', requiresAuth: true },
      },
      {
        path: 'content-hub',
        name: 'ContentHub',
        component: () => import('@/views/contentHub/index.vue'),
        meta: { title: 'AI内容中心', requiresAuth: true },
      },
      {
        path: 'creator-profile',
        name: 'CreatorProfile',
        component: () => import('@/views/creatorProfile/index.vue'),
        meta: { title: '主播画像', requiresAuth: true },
      },
      {
        path: 'creation',
        name: 'Creation',
        component: () => import('@/views/creation/index.vue'),
        meta: { title: '开始创作', requiresAuth: true },
      },
      {
        path: 'creation-studio',
        name: 'CreationStudio',
        component: () => import('@/views/creationStudio/index.vue'),
        meta: { title: 'AI创作工作台', requiresAuth: true },
      },
      {
        path: 'result',
        name: 'Result',
        component: () => import('@/views/result/index.vue'),
        meta: { title: '创作结果', requiresAuth: true },
      },
      {
        path: 'works',
        name: 'Works',
        component: () => import('@/views/works/index.vue'),
        meta: { title: '我的作品', requiresAuth: true },
      },
      {
        path: 'data-entry',
        name: 'DataEntry',
        component: () => import('@/views/dataEntry/index.vue'),
        meta: { title: '数据登记', requiresAuth: true },
      },
      {
        path: 'footage',
        name: 'Footage',
        component: () => import('@/views/footage/index.vue'),
        meta: { title: '素材库', requiresAuth: true },
      },
      {
        path: 'voice-profile',
        name: 'VoiceProfile',
        component: () => import('@/views/voiceProfile/index.vue'),
        meta: { title: '我的声音', requiresAuth: true },
      },
      {
        path: 'profile',
        name: 'Profile',
        component: () => import('@/views/profile/index.vue'),
        meta: { title: '我的', requiresAuth: true },
      },
      {
        path: 'viral-analysis',
        name: 'ViralAnalysis',
        component: () => import('@/views/viralAnalysis/index.vue'),
        meta: { title: 'AI爆款逆向工程', requiresAuth: true },
      },
      {
        path: 'shooting-assistant',
        name: 'ShootingAssistant',
        component: () => import('@/views/shootingAssistant/index.vue'),
        meta: { title: 'AI拍摄助手', requiresAuth: true },
      },
      {
        path: 'asset-collection',
        name: 'AssetCollection',
        component: () => import('@/views/assetCollection/index.vue'),
        meta: { title: '素材采集中心', requiresAuth: true },
      },
      {
        path: 'asset-library',
        name: 'AssetLibrary',
        component: () => import('@/views/assetLibrary/index.vue'),
        meta: { title: 'AI智能素材库', requiresAuth: true },
      },
      {
        path: 'video-director',
        name: 'VideoDirector',
        component: () => import('@/views/videoDirector/index.vue'),
        meta: { title: 'AI导演编排', requiresAuth: true },
      },
      {
        path: 'director-learning',
        name: 'DirectorLearning',
        component: () => import('@/views/directorLearning/index.vue'),
        meta: { title: 'AI导演学习中心', requiresAuth: true },
      },
      {
        path: 'video-production',
        name: 'VideoProduction',
        component: () => import('@/views/videoProduction/index.vue'),
        meta: { title: 'AI视频生产工厂', requiresAuth: true },
      },
      {
        path: 'platform-account',
        name: 'PlatformAccount',
        component: () => import('@/views/platformAccount/index.vue'),
        meta: { title: '平台账号管理', requiresAuth: true },
      },
      {
        path: 'publish-center',
        name: 'PublishCenter',
        component: () => import('@/views/publishCenter/index.vue'),
        meta: { title: '发布中心', requiresAuth: true },
      },
      {
        path: 'user-manage',
        name: 'UserManage',
        component: () => import('@/views/tenantManage/index.vue'),
        meta: { title: '用户管理', requiresAuth: true, roles: ['super_admin'] },
      },
    ],
  },
]

const router = createRouter({
  history: createWebHistory(),
  routes,
})

router.beforeEach(async (to, from, next) => {
  const userStore = useUserStore()
  const token = userStore.token

  if (to.meta.requiresAuth && !token) {
    return next({ name: 'Login', query: { redirect: to.fullPath } })
  }
  if ((to.name === 'Login' || to.name === 'Register') && token) {
    return next({ name: 'Home' })
  }

  // 角色限制路由: userInfo 刷新后会丢, 需先拉取再判断
  const roles = to.meta.roles as string[] | undefined
  if (roles?.length && token) {
    if (!userStore.userInfo) {
      try {
        await userStore.fetchUserInfo()
      } catch {
        return next({ name: 'Login', query: { redirect: to.fullPath } })
      }
    }
    if (!roles.includes(userStore.userInfo?.role || '')) {
      return next({ name: 'Home' })
    }
  }

  next()
})

export default router
