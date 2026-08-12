#!/usr/bin/env python3
"""
生产环境 AI 卡住任务清理脚本

部署 Phase 2 后执行，清理历史遗留的 running 状态 AI 任务。
这些任务是旧版本服务重启时未被正确标记失败的。

谨慎原则：
1. 只处理 running/pending 且超过 30 分钟的任务
2. 保留原始 error_message（追加而非覆盖）
3. 执行前打印统计，需要用户确认
4. 支持 dry-run

用法：
    python 01-cleanup-stuck-ai-tasks.py --dry-run
    python 01-cleanup-stuck-ai-tasks.py --execute
"""
import argparse
import sys
from datetime import datetime, timedelta
from pathlib import Path

backend_dir = Path(__file__).resolve().parents[2] / "backend"
sys.path.insert(0, str(backend_dir))

from app.core.database import SessionLocal
from app.models.ai_task import AITask


def main():
    parser = argparse.ArgumentParser(description="清理卡住的 AI 任务")
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--dry-run", action="store_true", help="仅预览，不修改")
    group.add_argument("--execute", action="store_true", help="实际执行清理")
    parser.add_argument("--min-stuck-minutes", type=int, default=30,
                        help="最少卡住多少分钟才清理（默认 30）")
    args = parser.parse_args()

    db = SessionLocal()
    try:
        cutoff = datetime.utcnow() - timedelta(minutes=args.min_stuck_minutes)

        stuck = (
            db.query(AITask)
            .filter(AITask.status.in_(["running", "pending"]))
            .filter(AITask.updated_at < cutoff)
            .order_by(AITask.updated_at.asc())
            .all()
        )

        if not stuck:
            print("✅ 没有卡住的 AI 任务")
            return

        print(f"发现 {len(stuck)} 个卡住的 AI 任务（状态 running/pending，更新于 {args.min_stuck_minutes} 分钟前）")
        print()

        # 按状态统计
        by_status = {}
        by_agent = {}
        for t in stuck:
            by_status[t.status] = by_status.get(t.status, 0) + 1
            by_agent[t.agent or 'unknown'] = by_agent.get(t.agent or 'unknown', 0) + 1

        print(f"按状态: {by_status}")
        print(f"按 Agent: {by_agent}")
        print()

        # 前 5 个最老的任务
        print("最老的 5 个任务:")
        for t in stuck[:5]:
            print(f"  #{t.id}  agent={t.agent}  status={t.status}  "
                  f"updated={t.updated_at}  project={t.project_id}")

        if args.dry_run:
            print()
            print("🔍 DRY RUN: 未做任何修改")
            print("   确认无误后执行: python 01-cleanup-stuck-ai-tasks.py --execute")
            return

        # 实际执行
        print()
        response = input(f"⚠️  即将标记 {len(stuck)} 个任务为 failed，确认? [y/N]: ")
        if response.lower() != 'y':
            print("已取消")
            return

        for t in stuck:
            old_error = t.error_message or ""
            new_error = f"[phase2-deploy] stuck task auto-recovered ({datetime.utcnow().isoformat()})"
            if old_error:
                new_error = f"{new_error}; previous: {old_error[:200]}"
            t.status = "failed"
            t.error_message = new_error

        db.commit()
        print(f"✅ 已清理 {len(stuck)} 个卡住的 AI 任务")

    finally:
        db.close()


if __name__ == "__main__":
    main()
