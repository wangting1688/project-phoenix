import { test, expect } from '@playwright/test'
import { apiOk, loginAs, mockAuth, mockRestApi } from './helpers'

test.describe('登录', () => {
  test('未登录访问受保护页面会跳转登录页', async ({ page }) => {
    await mockRestApi(page)
    await page.goto('/footage')
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

test.describe('素材上传质量反馈', () => {
  test.beforeEach(async ({ page }) => {
    await loginAs(page)
  })

  test('poor 素材给出重拍建议且提示不自动消失', async ({ page }) => {
    await mockRestApi(page)
    await mockAuth(page)
    await page.route('**/api/v1/footage/upload', route => route.fulfill(apiOk({
      id: 99, filename: 'dark.mp4', duration: 30, status: 'ready',
      source_type: 'user_upload', created_at: '2026-08-18T00:00:00',
      quality: {
        level: 'poor',
        brightness: { avg: 106.2, min: 100.1, max: 110.5 },
        face_ratio: 0.08,
        has_face: true,
        warnings: [
          '画面偏暗（亮度 106.2，建议 140 以上）。口型合成会出现嘴部发黑发暗，建议正面补光后重拍。',
          '人脸偏小（占画面宽度 8%，建议 12% 以上）。人脸太小会让口型区域模糊，建议靠近镜头重拍。',
        ],
        suitable_for_lipsync: false,
      },
    })))

    await page.goto('/footage')
    await page.locator('input[type=file]').setInputFiles({
      name: 'dark.mp4', mimeType: 'video/mp4', buffer: Buffer.from('fake-video'),
    })

    const notice = page.locator('.el-notification')
    await expect(notice).toBeVisible()
    await expect(notice).toContainText('素材可能影响成片效果')
    // 两条建议要分行成列表，而不是挤成一行
    await expect(page.locator('.quality-tips li')).toHaveCount(2)
    await expect(notice).toContainText('建议正面补光后重拍')
    await expect(notice).toContainText('建议靠近镜头重拍')
    // poor 用 duration=0 常驻，等待后仍应可见（否则用户可能没看见就去等渲染）
    await page.waitForTimeout(5000)
    await expect(notice).toBeVisible()
  })

  test('无警告时只提示上传成功', async ({ page }) => {
    await mockRestApi(page)
    await mockAuth(page)
    await page.route('**/api/v1/footage/upload', route => route.fulfill(apiOk({
      id: 100, filename: 'good.mp4', duration: 30, status: 'ready',
      source_type: 'user_upload', created_at: '2026-08-18T00:00:00',
      quality: {
        level: 'good',
        brightness: { avg: 191.7, min: 188.4, max: 196.6 },
        face_ratio: 0.567, has_face: true, warnings: [],
        suitable_for_lipsync: true,
      },
    })))

    await page.goto('/footage')
    await page.locator('input[type=file]').setInputFiles({
      name: 'good.mp4', mimeType: 'video/mp4', buffer: Buffer.from('fake-video'),
    })
    await expect(page.locator('.el-message').filter({ hasText: '上传成功' })).toBeVisible()
    await expect(page.locator('.el-notification')).toHaveCount(0)
  })

  test('检测服务不可达时不阻断上传', async ({ page }) => {
    await mockRestApi(page)
    await mockAuth(page)
    // has_face=null 表示「未检测」而非「不合格」，不该产生警告
    await page.route('**/api/v1/footage/upload', route => route.fulfill(apiOk({
      id: 101, filename: 'x.mp4', duration: 30, status: 'ready',
      source_type: 'user_upload', created_at: '2026-08-18T00:00:00',
      quality: {
        level: 'good',
        brightness: { avg: 180.0, min: 175.0, max: 185.0 },
        face_ratio: null, has_face: null, warnings: [],
        suitable_for_lipsync: true,
      },
    })))

    await page.goto('/footage')
    await page.locator('input[type=file]').setInputFiles({
      name: 'x.mp4', mimeType: 'video/mp4', buffer: Buffer.from('fake-video'),
    })
    await expect(page.locator('.el-message').filter({ hasText: '上传成功' })).toBeVisible()
  })
})
