"""回填 footages.resolution。

背景：上传接口曾把 resolution 写死为 1080x1920（见 HANDOFF 坑 #35），
存量记录的分辨率不可信（线上素材 7 实为 2336x1088 却记成 1080x1920）。
本脚本用 ffmpeg -i 解析真实尺寸并更新（生产机没有 ffprobe）。

用法（在 backend 目录下）：
    .venv/bin/python deploy/backfill_footage_resolution.py --dry-run
    .venv/bin/python deploy/backfill_footage_resolution.py
"""
import argparse
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.core.database import SessionLocal          # noqa: E402
from app.models import Footage                      # noqa: E402
from app.api.footage import _probe_resolution       # noqa: E402


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry-run", action="store_true", help="只打印不写库")
    args = ap.parse_args()

    db = SessionLocal()
    try:
        rows = db.query(Footage).filter(Footage.status != "deleted").all()
        changed = missing = same = 0
        for f in rows:
            path = f.file_path or ""
            # 历史数据混用相对/绝对路径，两种都试一下
            cands = [path, os.path.join(os.path.dirname(os.path.dirname(
                os.path.abspath(__file__))), path.lstrip("./"))]
            real = next((c for c in cands if c and os.path.isfile(c)), None)
            if not real:
                missing += 1
                print(f"[skip] id={f.id} 文件不存在: {path}")
                continue
            res = _probe_resolution(real)
            if not res:
                missing += 1
                print(f"[skip] id={f.id} 无法解析分辨率: {real}")
                continue
            if res == f.resolution:
                same += 1
                continue
            print(f"[fix ] id={f.id} {f.resolution or '(空)'} -> {res}")
            if not args.dry_run:
                f.resolution = res
            changed += 1
        if args.dry_run:
            print(f"\n[dry-run] 待更新 {changed}，已正确 {same}，跳过 {missing}")
        else:
            db.commit()
            print(f"\n[done] 已更新 {changed}，已正确 {same}，跳过 {missing}")
    finally:
        db.close()


if __name__ == "__main__":
    main()
