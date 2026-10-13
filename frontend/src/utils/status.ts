/**
 * 作品/项目展示状态的归一与文案映射。
 *
 * 后端 `content_projects.status` 历史上出现过多个枚举：早期 creation_studio
 * 链路（/creation-studio）落的是 "ready"，更早的数据里还有 "ai_plan_ready"、
 * "planned" 这类写法。这些值不在前端任何 map / 分支里，会直接漏到界面上：
 *   - 卡片状态标签原样显示英文（"ready"）
 *   - v-if 分支全不匹配 → 按钮区退化成「只剩一个删除按钮」
 *
 * 后端 `_compute_display_status` 已做同样的归一（第一道防线），这里是第二道：
 * 哪怕后端某天又冒出新的历史值、或前端拿到的是未归一的数据，界面也不会坏掉。
 */

/** 前端认得的展示状态（与后端 _compute_display_status 的返回枚举对齐）。 */
export type DisplayStatus =
  | 'draft'
  | 'processing'
  | 'plan_ready'
  | 'video_ready'
  | 'failed'

/** 历史/同义枚举 → 前端已知枚举。 */
const ALIAS: Record<string, DisplayStatus> = {
  // 早期 creation_studio 链路：文案/方案就绪、待出片
  ready: 'plan_ready',
  ai_plan_ready: 'plan_ready',
  planned: 'plan_ready',
  // 视频渲染中，对用户而言与「生成中」无差别
  rendering: 'processing',
  generating: 'processing',
  // 老写法里 completed 指的是「出片了」
  completed: 'video_ready',
  success: 'video_ready',
  // 草稿类
  new: 'draft',
}

const KNOWN: DisplayStatus[] = ['draft', 'processing', 'plan_ready', 'video_ready', 'failed']

/**
 * 把任意状态值归一到前端已知枚举。
 *
 * 未知值不假装成某个具体状态，统一按 `draft` 处理 —— 这样卡片至少有合理的
 * 文案与操作按钮，不会出现「英文文案 + 无按钮」这种完全不可用的情况。
 */
export function normalizeStatus(raw?: string | null): DisplayStatus {
  const s = String(raw ?? '').trim()
  if (!s) return 'draft'
  if (s in ALIAS) return ALIAS[s]
  if ((KNOWN as string[]).includes(s)) return s as DisplayStatus
  return 'draft'
}

/** 状态标签文案（卡片上的小圆标签）。 */
export function statusText(raw?: string | null): string {
  const map: Record<DisplayStatus, string> = {
    draft: '草稿',
    processing: '生成中',
    plan_ready: '方案完成',
    video_ready: '视频完成',
    failed: '失败',
  }
  return map[normalizeStatus(raw)]
}

/** 无封面时占位区里的提示文案。 */
export function coverHint(raw?: string | null): string {
  const map: Record<DisplayStatus, string> = {
    draft: '草稿',
    processing: 'AI创作中',
    plan_ready: '等待生成视频',
    video_ready: '点击播放',
    failed: '生成失败',
  }
  return map[normalizeStatus(raw)]
}
