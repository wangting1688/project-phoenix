import { test, expect } from '@playwright/test'
import { mockAuth, mockRestApi } from './helpers'

test.describe('登录', () => {
  test('未登录访问受保护页面会跳转登录页', async ({ page }) => {
    await mockRestApi(page)
    await page.goto('/works')
    await expect(page).toHaveURL(/\/login/)
    await expect(page.getByPlaceholder('请输入手机号')).toBeVisible()
  })

  test('登录成功后离开登录页并写入 token', async ({ page }) => {
    // 顺序要紧：通配兜底先注册，具体接口后注册（后注册优先）
    await mockRestApi(page)
    await mockAuth(page)
    await page.goto('/login')
    await page.getByPlaceholder('请输入手机号').fill('13800000000')
    await page.getByPlaceholder('请输入密码').fill('test1234')
    await page.getByRole('button', { name: '登录', exact: true }).click()
    await expect(page).not.toHaveURL(/\/login/)
    const token = await page.evaluate(() => localStorage.getItem('token'))
    expect(token).toBe('e2e-test-token')
  })
})

// ── 已删除：素材上传质量反馈（原 3 例）────────────────────────────────
// 原用例覆盖 /footage 实拍素材库的「上传视频 → 画面质量反馈通知（偏暗 /
// 人脸偏小）→ 是否自动消失」链路，断言 .el-notification 与 .quality-tips。
//
// 该链路已随路线 B（实拍 + 口型同步）整体下线，用例失去被测对象：
//   1. 路由 /footage 已重定向到 /h3-library（src/router/index.ts）
//   2. h3Library 页面不含任何画面质量反馈逻辑（无 el-notification / quality）
//   3. 后端 /footage/* 接口与表结构保留，但前端已无入口调用
//
// 保留的后果是真实的：用例会落到 /h3-library，在那里 `input[type=file]`
// 同时匹配到「人物图上传」和「场景图上传」两个 input，触发 Playwright
// 严格模式报错（strict mode violation: resolved to 2 elements），6 例全红。
// 它测的早已不是产品行为，留着只会给 CI 制造噪音、掩盖真实失败。
//
// 若日后恢复实拍链路，请从 git 历史取回本组用例（本文件在删除前的版本）。
