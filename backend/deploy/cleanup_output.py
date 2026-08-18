"""清理 storage/output 里不再被引用的历史产物。

背景：每次重跑渲染都会生成新的 render_/tts_ 文件，但 videos 表只保留最新
一条引用，旧文件永久堆积。实测 91 个文件里 70 个已是孤儿，占 364MB（57%）。
磁盘 40G 已用 63%，按峰值日增 280MB 算，放任下去几周就会写满——而磁盘满
在 SQLite+WAL 下会直接损坏事务。

安全策略（宁可留着也不误删）：
- 只删「数据库中无任何引用」且「超过保护期」的文件
- 每个 project 至少保留最近 KEEP_PER_PROJECT 个成片，即使数据库没引用
  （用户可能正等着看，或引用写入尚未提交）
- 默认 --dry-run，必须显式加 --apply 才真删
- 删除前把清单写入日志文件，便于事后核对

用法（backend 目录下）：
    .venv/bin/python deploy/cleanup_output.py                # 干跑
    .venv/bin/python deploy/cleanup_output.py --apply
"""
import argparse
import os
import re
import sys
import time
from collections import defaultdict

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from sqlalchemy import text                        # noqa: E402

from app.core.config import settings                # noqa: E402
from app.core.database import SessionLocal          # noqa: E402

# 新文件的保护期：任务刚跑完、引用可能还没落库，绝不能碰
PROTECT_HOURS = 48
# 每个 project 保底保留的成片数（按时间倒序）
KEEP_PER_PROJECT = 2

# render_25_1787026003.mp4 / tts_25_1787019332.mp3 / render_25_..._cover.jpg
NAME_RE = re.compile(r"^(render|tts)_(\d+)_(\d+)")


def collect_referenced(db, filenames):
    """全库扫描：任何文本列里出现过的文件名都算被引用。

    刻意不只查 videos 表：publish_tasks / viral_analysis_sessions /
    creation_sessions 等表也存 url 或 result JSON，未来还可能新增。
    宁可扫全库多花几秒，也不能因为漏了一张表而误删用户的成片。
    """
    refs = set()
    rows = db.execute(text(
        "select name from sqlite_master where type='table'")).fetchall()
    for (table,) in rows:
        if table.startswith("sqlite_"):
            continue
        try:
            cols = db.execute(text(
                f"select name, type from pragma_table_info('{table}')")).fetchall()
        except Exception:
            continue
        # 只扫文本类列；数值列不可能存文件名
        text_cols = [c[0] for c in cols
                     if c[1] and ("CHAR" in c[1].upper() or "TEXT" in c[1].upper()
                                  or "JSON" in c[1].upper())]
        if not text_cols:
            continue
        for col in text_cols:
            try:
                vals = db.execute(text(
                    f'select "{col}" from "{table}" '
                    f'where "{col}" is not null')).fetchall()
            except Exception:
                continue
            for (val,) in vals:
                if not isinstance(val, str) or not val:
                    continue
                for name in filenames:
                    if name in val:
                        refs.add(name)
    return refs


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--apply", action="store_true", help="真正删除（默认只打印）")
    ap.add_argument("--keep", type=int, default=KEEP_PER_PROJECT,
                    help="每个 project 保底保留的产物组数")
    args = ap.parse_args()

    out_dir = os.path.join(settings.STORAGE_PATH, "output")
    if not os.path.isdir(out_dir):
        print(f"目录不存在: {out_dir}")
        return

    disk_names = {n for n in os.listdir(out_dir)
                  if os.path.isfile(os.path.join(out_dir, n))}
    db = SessionLocal()
    try:
        refs = collect_referenced(db, disk_names)
    finally:
        db.close()

    now = time.time()
    # 按 (类型, project) 分组，组内按时间戳倒序，用于保底保留
    groups = defaultdict(list)
    others = []
    for name in os.listdir(out_dir):
        path = os.path.join(out_dir, name)
        if not os.path.isfile(path):
            continue
        m = NAME_RE.match(name)
        if m:
            groups[(m.group(1), m.group(2))].append((int(m.group(3)), name))
        else:
            others.append(name)

    protected = set(refs)
    for key, items in groups.items():
        for _, name in sorted(items, reverse=True)[:args.keep]:
            protected.add(name)
            # 成片与它的封面成对保留
            stem = os.path.splitext(name)[0]
            protected.add(stem + "_cover.jpg")

    deletable, freed = [], 0
    for name in os.listdir(out_dir):
        path = os.path.join(out_dir, name)
        if not os.path.isfile(path) or name in protected:
            continue
        age_h = (now - os.path.getmtime(path)) / 3600.0
        if age_h < PROTECT_HOURS:
            continue
        deletable.append((os.path.getsize(path), name))
        freed += os.path.getsize(path)

    deletable.sort(reverse=True)
    print(f"目录: {out_dir}")
    print(f"全库引用 {len(refs)} 个；保护（引用+每 project 最近 {args.keep} 组）"
          f"{len(protected)} 个；未识别命名 {len(others)} 个（一律保留）")
    print(f"可清理 {len(deletable)} 个，释放 {freed / 1048576:.1f} MB\n")
    for sz, name in deletable[:20]:
        print(f"  {sz / 1048576:8.1f} MB  {name}")
    if len(deletable) > 20:
        print(f"  ... 其余 {len(deletable) - 20} 个")

    if not args.apply:
        print("\n[dry-run] 未删除任何文件；确认无误后加 --apply")
        return

    log_path = os.path.join(settings.STORAGE_PATH,
                            f"cleanup_output_{time.strftime('%Y%m%d_%H%M%S')}.log")
    removed = 0
    with open(log_path, "w", encoding="utf-8") as log:
        for sz, name in deletable:
            path = os.path.join(out_dir, name)
            try:
                os.remove(path)
                log.write(f"{sz}\t{name}\n")
                removed += 1
            except OSError as e:
                print(f"[warn] 删除失败 {name}: {e}")
    print(f"\n[done] 已删除 {removed} 个，释放约 {freed / 1048576:.1f} MB")
    print(f"清单: {log_path}")


if __name__ == "__main__":
    main()
