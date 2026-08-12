#!/usr/bin/env python3
"""
上线后监控脚本 - 持续观察 30 分钟

每 1 分钟检查一次：
- 健康检查状态
- AI 任务状态分布
- 工作流任务状态分布
- 失败任务增量

输出格式化的观察报告。
"""
import time
import json
import sys
import urllib.request
import urllib.error
from datetime import datetime

BASE_URL = sys.argv[1] if len(sys.argv) > 1 else "http://localhost:8000"
ADMIN_TOKEN = sys.argv[2] if len(sys.argv) > 2 else ""
DURATION_MIN = 30
INTERVAL_SEC = 60

headers = {}
if ADMIN_TOKEN:
    headers["Authorization"] = f"Bearer {ADMIN_TOKEN}"


def api_get(path):
    req = urllib.request.Request(f"{BASE_URL}{path}", headers=headers)
    try:
        with urllib.request.urlopen(req, timeout=10) as resp:
            return resp.status, json.loads(resp.read())
    except urllib.error.HTTPError as e:
        return e.code, {"error": str(e)}
    except Exception as e:
        return 0, {"error": str(e)}


def main():
    print(f"==============================================")
    print(f"  Phase 2 上线后监控")
    print(f"  目标: {BASE_URL}")
    print(f"  时长: {DURATION_MIN} 分钟")
    print(f"  间隔: {INTERVAL_SEC} 秒")
    print(f"==============================================")
    print()

    # 基线数据
    print("【基线采集】")
    code, health = api_get("/health")
    print(f"  健康检查: {code} -> {health.get('status', 'unknown')}")

    baseline_ai_failed = 0
    baseline_wf_failed = 0
    if ADMIN_TOKEN:
        _, ai_data = api_get("/api/v1/admin/monitoring/ai-tasks?limit=1")
        baseline_ai_failed = ai_data.get("status_breakdown", {}).get("failed", 0)
        _, wf_data = api_get("/api/v1/admin/monitoring/workflow-tasks?limit=1")
        baseline_wf_failed = wf_data.get("status_breakdown", {}).get("failed", 0)
        print(f"  AI 任务失败数(基线): {baseline_ai_failed}")
        print(f"  工作流失败数(基线): {baseline_wf_failed}")
    else:
        print("  (无 admin token，跳过任务基线)")

    print()
    print("【开始监控】")
    print(f"  时间            健康     AI失败  工作流失败  状态")
    print(f"  {'─'*60}")

    alerts = []
    checks = 0

    for i in range(DURATION_MIN):
        now = datetime.now().strftime("%H:%M:%S")

        # 健康检查
        code, health = api_get("/health")
        status = health.get("status", "error") if code == 200 else f"HTTP_{code}"

        # 任务计数
        ai_failed = "—"
        wf_failed = "—"
        if ADMIN_TOKEN:
            _, ai_data = api_get("/api/v1/admin/monitoring/ai-tasks?limit=1")
            _, wf_data = api_get("/api/v1/admin/monitoring/workflow-tasks?limit=1")
            ai_failed = ai_data.get("status_breakdown", {}).get("failed", "?")
            wf_failed = wf_data.get("status_breakdown", {}).get("failed", "?")

        # 状态标记
        flag = "✓"
        if status != "healthy":
            flag = "⚠️ "
            alerts.append(f"[{now}] 健康检查异常: {status}")
        if ADMIN_TOKEN and isinstance(ai_failed, int) and ai_failed > baseline_ai_failed + 5:
            flag = "⚠️ "
            alerts.append(f"[{now}] AI 失败任务增加: {baseline_ai_failed} → {ai_failed}")

        print(f"  {now}  {status:<8} {str(ai_failed):<8} {str(wf_failed):<10} {flag}")
        checks += 1

        if i < DURATION_MIN - 1:
            time.sleep(INTERVAL_SEC)

    print()
    print("==============================================")
    print(f"  监控完成 - {checks} 次检查")
    print("==============================================")

    if alerts:
        print(f"\n⚠️  告警 ({len(alerts)} 条):")
        for a in alerts:
            print(f"  - {a}")
    else:
        print("\n✅ 一切正常，无告警")

    print(f"\n结束时间: {datetime.now().isoformat()}")


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n\n已手动停止")
        sys.exit(0)
