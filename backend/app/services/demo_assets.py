"""
演示素材服务

负责新用户注册时注入系统演示素材，以及演示素材的恢复、检查等操作。
"""
import os
import shutil
import uuid
from pathlib import Path
from typing import List, Dict

from sqlalchemy.orm import Session

from app.core.config import settings
from app.models import Footage


# 演示素材元数据定义
# 每个素材包含: source_ref, scene, emotion, action, topics, filename
DEMO_ASSETS: List[Dict[str, str]] = [
    {
        "source_ref": "demo_bedroom_01",
        "filename": "demo_bedroom_01.mp4",
        "scene": "卧室",
        "emotion": "温暖",
        "action": "休息",
        "topics": ["睡眠", "卧室", "休息"],
    },
    {
        "source_ref": "demo_livingroom_02",
        "filename": "demo_livingroom_02.mp4",
        "scene": "客厅",
        "emotion": "平静",
        "action": "生活",
        "topics": ["家庭", "生活", "客厅"],
    },
    {
        "source_ref": "demo_kitchen_03",
        "filename": "demo_kitchen_03.mp4",
        "scene": "厨房",
        "emotion": "日常",
        "action": "做饭",
        "topics": ["健康", "饮食", "厨房"],
    },
    {
        "source_ref": "demo_nature_sunset_04",
        "filename": "demo_nature_sunset_04.mp4",
        "scene": "户外",
        "emotion": "治愈",
        "action": "散步",
        "topics": ["自然", "放松", "日落"],
    },
    {
        "source_ref": "demo_nature_plant_05",
        "filename": "demo_nature_plant_05.mp4",
        "scene": "自然",
        "emotion": "清新",
        "action": "生长",
        "topics": ["植物", "健康", "自然"],
    },
    {
        "source_ref": "demo_nature_sky_06",
        "filename": "demo_nature_sky_06.mp4",
        "scene": "天空",
        "emotion": "开阔",
        "action": "展望",
        "topics": ["天空", "自由", "开阔"],
    },
]


def _get_demo_source_dir() -> Path:
    """获取演示素材源目录的绝对路径"""
    storage_dir = Path(settings.STORAGE_PATH).resolve()
    return storage_dir / settings.DEMO_FOOTAGE_SOURCE_DIR


def _get_user_footage_dir(user_id: int) -> Path:
    """获取用户素材目录的绝对路径"""
    storage_dir = Path(settings.STORAGE_PATH).resolve()
    return storage_dir / "footage" / str(user_id)


def _get_footage_rel_path(user_id: int, filename: str) -> str:
    """构造素材的相对路径（与用户上传格式一致）"""
    return f"./storage/footage/{user_id}/{filename}"


def is_demo_footage_enabled() -> bool:
    """检查演示素材功能是否开启"""
    return settings.DEMO_FOOTAGE_ENABLED


def get_demo_assets_count() -> int:
    """获取可用的演示素材总数"""
    return min(len(DEMO_ASSETS), settings.DEMO_FOOTAGE_MAX_COUNT)


def has_seeded_demo_footages(db: Session, user_id: int) -> bool:
    """检查用户是否已经注入过演示素材"""
    count = (
        db.query(Footage)
        .filter(
            Footage.user_id == user_id,
            Footage.source_type == "system_demo",
        )
        .count()
    )
    return count > 0


def seed_demo_footages(db: Session, user_id: int) -> int:
    """
    为指定用户注入演示素材。

    幂等操作：如果已经注入过，则只恢复被软删除的，不再重复注入。

    Returns:
        实际注入/恢复的素材数量
    """
    if not settings.DEMO_FOOTAGE_ENABLED:
        return 0

    # 检查用户已有的系统素材（包括已删除的）
    existing = (
        db.query(Footage)
        .filter(
            Footage.user_id == user_id,
            Footage.source_type == "system_demo",
        )
        .all()
    )
    existing_refs = {f.source_ref for f in existing if f.source_ref}

    source_dir = _get_demo_source_dir()
    user_dir = _get_user_footage_dir(user_id)
    user_dir.mkdir(parents=True, exist_ok=True)

    assets_to_seed = DEMO_ASSETS[: settings.DEMO_FOOTAGE_MAX_COUNT]
    seeded_count = 0

    for asset in assets_to_seed:
        source_ref = asset["source_ref"]
        src_file = source_dir / asset["filename"]

        if not src_file.exists():
            continue

        if source_ref in existing_refs:
            # 已存在，检查是否被软删除，如果是则恢复
            for f in existing:
                if f.source_ref == source_ref and f.status == "deleted":
                    f.status = "ready"
                    seeded_count += 1
                    break
            continue

        # 复制文件到用户目录（用 uuid 重命名，保持与上传逻辑一致）
        ext = Path(asset["filename"]).suffix
        new_filename = f"{uuid.uuid4().hex}{ext}"
        dst_file = user_dir / new_filename
        shutil.copy2(src_file, dst_file)

        # 获取文件大小
        file_size = dst_file.stat().st_size

        # 用 ffmpeg 获取时长
        duration = 0
        try:
            import subprocess
            result = subprocess.run(
                [
                    "ffprobe", "-v", "error",
                    "-show_entries", "format=duration",
                    "-of", "default=noprint_wrappers=1:nokey=1",
                    str(dst_file),
                ],
                capture_output=True, text=True, timeout=5,
            )
            if result.returncode == 0 and result.stdout.strip():
                duration = int(float(result.stdout.strip()))
        except Exception:
            pass

        # 插入 DB 记录
        footage = Footage(
            user_id=user_id,
            category_id=None,
            filename=asset["filename"],
            file_path=_get_footage_rel_path(user_id, new_filename),
            thumbnail=None,
            duration=duration,
            resolution="1080x1920",
            file_size=file_size,
            scene=asset["scene"],
            emotion=asset["emotion"],
            action=asset["action"],
            topics=asset["topics"],
            status="ready",
            source_type="system_demo",
            source_ref=source_ref,
        )
        db.add(footage)
        seeded_count += 1

    if seeded_count > 0:
        db.commit()

    return seeded_count


def restore_demo_footages(db: Session, user_id: int) -> int:
    """
    恢复用户所有被软删除的演示素材，
    同时补充系统新增的演示素材（如果有）。

    Returns:
        恢复/新增的素材数量
    """
    if not settings.DEMO_FOOTAGE_ENABLED:
        return 0

    # 先把已有的被删除的恢复
    deleted = (
        db.query(Footage)
        .filter(
            Footage.user_id == user_id,
            Footage.source_type == "system_demo",
            Footage.status == "deleted",
        )
        .all()
    )
    for f in deleted:
        f.status = "ready"

    db.commit()

    # 再调用 seed 补充可能新增的素材（幂等）
    newly_added = seed_demo_footages(db, user_id)

    return len(deleted) + newly_added
