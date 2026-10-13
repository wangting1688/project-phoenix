import request from '@/utils/request'

const cache = new Map<string, { url: string; expiresAt: number }>()
/** 同路径的进行中请求，避免同一文件被并发签名两次。 */
const inflight = new Map<string, Promise<string>>()

/**
 * 并发闸门。
 *
 * 作品/结果页会一次性为「每个作品 × (封面 + 视频)」请求签名，作品一多就是几十个请求同时发。
 * 手机浏览器（微信 X5 / 华为 ArkWeb）对同域并发有限制，超出的请求会被内核排队甚至直接取消，
 * 服务端侧表现为 499，前端拿不到 URL，封面就整片空白——用户看到的就是「点了没反应」。
 * 这里限制同时在途的签名请求数，把「一次性几十个」摊平成小批量。
 */
const MAX_CONCURRENT = 5
let running = 0
const waiters: Array<() => void> = []

async function acquire(): Promise<void> {
  if (running < MAX_CONCURRENT) {
    running++
    return
  }
  // 名额已满：排队。release() 会把名额直接转交给队首，因此这里不再 running++，
  // 否则「先减后加」之间新请求会插队抢走名额，实际并发会超过上限。
  await new Promise<void>((resolve) => waiters.push(resolve))
}

function release(): void {
  const next = waiters.shift()
  if (next) {
    next() // 名额转交，running 保持不变
  } else {
    running--
  }
}

/** /static/<path> 或裸文件名 -> storage 相对路径（media/sign 需要的参数）。 */
export function storagePathOf(url?: string | null): string {
  if (!url) return ''
  if (url.startsWith('/static/')) return url.slice('/static/'.length)
  return `output/${url.split('/').pop()}`
}

const sleep = (ms: number) => new Promise((r) => setTimeout(r, ms))

/**
 * 获取 storage 文件的短时签名 URL（带内存缓存 + 并发限流 + 同路径复用）。
 * 失败仍会 reject，需要容错的批量场景请用 resolveMediaUrls。
 */
export async function signedMediaUrl(path: string): Promise<string> {
  if (!path) return ''
  const hit = cache.get(path)
  if (hit && Date.now() < hit.expiresAt - 60_000) return hit.url
  const pending = inflight.get(path)
  if (pending) return pending

  const task = (async () => {
    // 网络抖动重试一次：签名接口很轻，重试成本远低于让整页封面空着
    let lastErr: unknown
    for (let attempt = 0; attempt < 2; attempt++) {
      await acquire()
      try {
        const res = await request.get<unknown, { url: string }>('/media/sign', {
          params: { path },
          timeout: 20000,
        })
        const m = res.url.match(/expires=(\d+)/)
        const expiresAt = m ? Number(m[1]) * 1000 : Date.now() + 30 * 60 * 1000
        cache.set(path, { url: res.url, expiresAt })
        return res.url
      } catch (e) {
        lastErr = e
        if (attempt === 0) await sleep(400)
      } finally {
        release()
      }
    }
    throw lastErr
  })()

  inflight.set(path, task)
  try {
    return await task
  } finally {
    inflight.delete(path)
  }
}

/**
 * 批量解析路径到签名 URL，返回 path -> url 映射。
 *
 * 用 allSettled 语义：个别文件签名失败只让那一张封面留空，
 * 不会像 Promise.all 那样一处失败就拖垮整页（历史事故的根因）。
 * 失败项不会写缓存，下次进入页面会自然重试。
 */
export async function resolveMediaUrls(
  paths: Array<string | null | undefined>,
): Promise<Record<string, string>> {
  const uniq = Array.from(new Set(paths.filter(Boolean) as string[]))
  const results = await Promise.allSettled(uniq.map((p) => signedMediaUrl(p)))
  const out: Record<string, string> = {}
  uniq.forEach((p, i) => {
    const r = results[i]
    out[p] = r.status === 'fulfilled' ? r.value : ''
  })
  return out
}
