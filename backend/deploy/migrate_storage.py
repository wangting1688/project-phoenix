#!/usr/bin/env python3
"""
Storage 目录迁移脚本

用途：将 storage 从项目目录迁移到独立数据目录，
      同时更新数据库中的路径引用。

用法：
    python deploy/migrate_storage.py --target /var/lib/phoenix/storage

注意事项：
    1. 执行前请先备份数据库和 storage 目录
    2. 建议先停止后端服务
    3. 迁移后需要更新 .env 中的 STORAGE_PATH
"""
import argparse
import shutil
import sys
import os
from pathlib import Path

backend_dir = Path(__file__).parent.parent.resolve()
sys.path.insert(0, str(backend_dir))

from app.core.config import settings
from app.core.database import SessionLocal
from app.models.footage import Footage
from app.models.voice_profile import UserVoiceProfile


def migrate_storage(target_path: str, dry_run: bool = False) -> None:
    target = Path(target_path).resolve()
    source = Path(settings.STORAGE_PATH).resolve()

    print(f"源目录: {source}")
    print(f"目标目录: {target}")
    print(f"模式: {'DRY RUN' if dry_run else '实际执行'}")

    if source == target:
        print("源目录和目标目录相同，无需迁移")
        return

    if not source.exists():
        print(f"错误: 源目录不存在: {source}")
        sys.exit(1)

    if target.exists() and any(target.iterdir()):
        print(f"警告: 目标目录已存在且非空")
        response = input("是否继续? (y/N): ")
        if response.lower() != 'y':
            sys.exit(0)

    # 1. 复制文件
    print("\n[1/3] 复制文件...")
    if not dry_run:
        target.parent.mkdir(parents=True, exist_ok=True)
        if target.exists():
            shutil.rmtree(target)
        shutil.copytree(source, target)
        print(f"  ✓ 已复制到 {target}")
    else:
        size = sum(f.stat().st_size for f in source.rglob('*') if f.is_file())
        print(f"  DRY RUN: 将复制 {size / 1024 / 1024:.1f} MB")

    # 2. 更新数据库路径
    print("\n[2/3] 更新数据库路径...")
    db = SessionLocal()
    try:
        # footages 表: 相对路径 -> 新绝对路径
        footages = db.query(Footage).all()
        updated_footages = 0
        for f in footages:
            if not f.file_path:
                continue
            old_path = f.file_path
            if old_path.startswith('./storage/'):
                rel = old_path[len('./storage/'):]
                new_path = str(target / rel)
            elif str(source) in old_path:
                new_path = old_path.replace(str(source), str(target))
            else:
                continue
            
            if not dry_run:
                f.file_path = new_path
            updated_footages += 1
        
        if not dry_run:
            db.commit()
        print(f"  footages: 更新 {updated_footages}/{len(footages)} 条")

        # user_voice_profiles 表
        profiles = db.query(UserVoiceProfile).all()
        updated_profiles = 0
        for p in profiles:
            changed = False
            if p.sample_path and str(source) in p.sample_path:
                if not dry_run:
                    p.sample_path = p.sample_path.replace(str(source), str(target))
                changed = True
            if p.demo_audio_path and str(source) in p.demo_audio_path:
                if not dry_run:
                    p.demo_audio_path = p.demo_audio_path.replace(str(source), str(target))
                changed = True
            if changed:
                updated_profiles += 1
        
        if not dry_run:
            db.commit()
        print(f"  user_voice_profiles: 更新 {updated_profiles}/{len(profiles)} 条")

    finally:
        db.close()

    # 3. 完成
    print("\n[3/3] 完成")
    print(f"\n后续步骤:")
    print(f"  1. 修改 .env 中 STORAGE_PATH={target}")
    print(f"  2. 确认文件权限正确")
    print(f"  3. 重启后端服务")
    print(f"  4. 验证后删除旧目录: rm -rf {source}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="迁移 storage 目录")
    parser.add_argument("--target", required=True, help="目标目录路径")
    parser.add_argument("--dry-run", action="store_true", help="仅预览，不实际执行")
    args = parser.parse_args()

    migrate_storage(args.target, args.dry_run)
