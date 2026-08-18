import { defineConfig, devices } from '@playwright/test'

/**
 * 前端冒烟测试。
 *
 * 刻意不依赖真实后端：所有 /api 请求在测试内用 page.route 拦截并 mock。
 * 这样 CI 里不需要起后端、不需要 GPU、也不会污染线上数据，
 * 同时仍能验证「前端是否正确解析并展示后端返回的字段」——
 * 历史上多次事故正是出在这一层（拦截器已解包却又取 .data、
 * 字段类型标注缺失导致 as any 满天飞）。
 */
export default defineConfig({
  testDir: './e2e',
  timeout: 30_000,
  expect: { timeout: 8_000 },
  fullyParallel: true,
  reporter: process.env.CI ? 'github' : 'list',
  use: {
    baseURL: 'http://127.0.0.1:4173',
    trace: 'on-first-retry',
  },
  projects: [
    { name: 'desktop', use: { ...devices['Desktop Chrome'] } },
    { name: 'mobile', use: { ...devices['Pixel 5'] } },
  ],
  // 用 preview 跑构建产物，贴近线上真实形态（线上也是 dist 静态托管）。
  // ⚠️ 必须 --host 127.0.0.1：默认只绑 localhost，在本机解析到 IPv6 ::1，
  // 而 Playwright 访问 127.0.0.1 会 ERR_CONNECTION_REFUSED。
  webServer: {
    command: 'npx vite preview --port 4173 --strictPort --host 127.0.0.1',
    url: 'http://127.0.0.1:4173/',
    reuseExistingServer: !process.env.CI,
    timeout: 120_000,
  },
})
