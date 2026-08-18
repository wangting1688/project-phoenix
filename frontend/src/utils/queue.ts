/** 任务排队提示文案。
 *
 * GPU worker 串行执行，多人同时提交要让用户知道自己排第几位，
 * 否则长时间不动的进度条会被当成卡死。
 */
export function formatEta(seconds: number): string {
  if (seconds < 60) return `${seconds} 秒`
  return `${Math.ceil(seconds / 60)} 分钟`
}

export function queueHintText(
  position: number | null,
  etaSeconds: number | null,
): string {
  if (position === null) return ''
  const etaText = etaSeconds && etaSeconds > 0
    ? `，预计还需 ${formatEta(etaSeconds)}`
    : ''
  // position 0 表示轮到自己了，此时说"前面还有 0 个"会很奇怪
  if (position > 0) return `前面还有 ${position} 个任务正在处理${etaText}`
  return etaSeconds && etaSeconds > 0 ? `正在处理${etaText}` : ''
}
