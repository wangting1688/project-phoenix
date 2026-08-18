import { test, expect } from '@playwright/test'
import { formatEta, queueHintText } from '../src/utils/queue'

/**
 * 排队提示是纯函数逻辑，用单测覆盖边界比走完四步表单更稳。
 * 这些分支都是实际踩过的：position=0 时不能说"前面还有 0 个"，
 * 终态任务三个字段为 null 时不能显示任何提示。
 */
test.describe('排队提示文案', () => {
  test('未排队（终态任务）不显示提示', () => {
    expect(queueHintText(null, null)).toBe('')
    expect(queueHintText(null, 480)).toBe('')
  })

  test('轮到自己时不说"前面还有 0 个"', () => {
    expect(queueHintText(0, 288)).toBe('正在处理，预计还需 5 分钟')
    // 没有 ETA 时不硬凑文案
    expect(queueHintText(0, null)).toBe('')
    expect(queueHintText(0, 0)).toBe('')
  })

  test('排在后面时给出位置与等待', () => {
    expect(queueHintText(1, 768)).toBe('前面还有 1 个任务正在处理，预计还需 13 分钟')
    expect(queueHintText(2, 828)).toBe('前面还有 2 个任务正在处理，预计还需 14 分钟')
  })

  test('缺少 ETA 时仍报位置', () => {
    expect(queueHintText(3, null)).toBe('前面还有 3 个任务正在处理')
  })

  test('不足一分钟按秒显示', () => {
    expect(formatEta(45)).toBe('45 秒')
    expect(formatEta(59)).toBe('59 秒')
    expect(formatEta(60)).toBe('1 分钟')
    // 向上取整，避免显示"还需 0 分钟"
    expect(formatEta(61)).toBe('2 分钟')
  })
})
