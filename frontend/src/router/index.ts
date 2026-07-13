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
        path: 'creation',
        name: 'Creation',
        component: () => import('@/views/creation/index.vue'),
        meta: { title: '开始创作', requiresAuth: true },
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
        path: 'footage',
        name: 'Footage',
        component: () => import('@/views/footage/index.vue'),
        meta: { title: '素材库', requiresAuth: true },
      },
      {
        path: 'profile',
        name: 'Profile',
        component: () => import('@/views/profile/index.vue'),
        meta: { title: '我的', requiresAuth: true },
      },
    ],
  },
]

const router = createRouter({
  history: createWebHistory(),
  routes,
})

router.beforeEach((to, from, next) => {
  const userStore = useUserStore()
  const token = userStore.token

  if (to.meta.requiresAuth && !token) {
    next({ name: 'Login', query: { redirect: to.fullPath } })
  } else if ((to.name === 'Login' || to.name === 'Register') && token) {
    next({ name: 'Home' })
  } else {
    next()
  }
})

export default router
