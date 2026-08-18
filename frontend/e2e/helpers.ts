import { Page } from '@playwright/test'

/** 后端 ApiResponse 包装。前端拦截器会解包成业务数据。 */
export function apiOk(data: unknown) {
  return {
    status: 200,
    contentType: 'application/json',
    body: JSON.stringify({ code: 200, message: 'success', data }),
  }
}

export const TEST_USER = {
  id: 2,
  phone: '13800000000',
  nickname: '测试用户',
  avatar: '',
  role: 'user',
  status: 'active',
  created_at: '2026-08-18T00:00:00',
}

/** 注入已登录态。路由守卫只看 localStorage 里的 token。 */
export async function loginAs(page: Page) {
  await page.addInitScript(() => {
    localStorage.setItem('token', 'e2e-test-token')
  })
}

/** 拦截登录与当前用户接口。 */
export async function mockAuth(page: Page) {
  await page.route('**/api/v1/auth/login', route =>
    route.fulfill(apiOk({ token: 'e2e-test-token', user: TEST_USER })))
  await page.route('**/api/v1/auth/me', route => route.fulfill(apiOk(TEST_USER)))
}

/**
 * 兜底：未显式 mock 的 /api 请求一律返回空成功响应。
 * 否则页面会因为真实后端不可达而挂在 loading，测试报错原因会很难读。
 *
 * ⚠️ Playwright 的 route 是**后注册优先**（后注册的先匹配）。
 * 所以这个通配兜底必须**先**调用，随后再注册具体接口的 mock，
 * 否则具体 mock 永远不会命中 —— 表现为「接口返回空数据、断言全部失败」。
 */
export async function mockRestApi(page: Page) {
  await page.route('**/api/v1/**', route => {
    const url = route.request().url()
    if (url.includes('/footage/list')) {
      return route.fulfill(apiOk({ items: [], total: 0, page: 1, size: 20 }))
    }
    if (url.includes('/footage/categories')) return route.fulfill(apiOk([]))
    if (url.includes('/footage/suggest-shots')) return route.fulfill(apiOk({}))
    return route.fulfill(apiOk({}))
  })
}
