import os
import re
import shutil
import subprocess
import uuid
from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Form, Query
from starlette.concurrency import run_in_threadpool
from sqlalchemy.orm import Session
from typing import List

from app.core.database import get_db
from app.core.config import settings
from app.api.deps import get_current_user
from app.models import User, Footage, FootageCategory
from app.schemas.footage import (
    FootageCategoryCreate,
    FootageCategoryResponse,
    FootageResponse,
    FootageUpdate,
)
from app.schemas.common import ApiResponse
from app.services.footage_quality import inspect_footage

router = APIRouter(prefix="/footage", tags=["素材库"])

UPLOAD_DIR = os.path.join(settings.STORAGE_PATH, "footage")
os.makedirs(UPLOAD_DIR, exist_ok=True)


def _find_bin(name: str):
    """查找 ffmpeg/ffprobe，兼容 systemd 等服务环境下 PATH 不含 /usr/local/bin 的情况。"""
    for p in (shutil.which(name), f"/usr/local/bin/{name}", f"/usr/bin/{name}"):
        if p and os.path.isfile(p) and os.access(p, os.X_OK):
            return p
    return None



def _probe_duration(file_path: str) -> int:
    """提取视频时长（秒）。优先 ffprobe，回退 ffmpeg -i 解析 Duration。"""
    ffprobe = shutil.which("ffprobe")
    if ffprobe:
        try:
            out = subprocess.run(
                [ffprobe, "-v", "error", "-show_entries", "format=duration",
                 "-of", "default=noprint_wrappers=1:nokey=1", file_path],
                stdout=subprocess.PIPE, stderr=subprocess.PIPE, universal_newlines=True, timeout=60,
            )
            val = out.stdout.strip()
            if val:
                return int(float(val))
        except Exception:
            pass
    ffmpeg = shutil.which("ffmpeg")
    if ffmpeg:
        try:
            out = subprocess.run([ffmpeg, "-i", file_path],
                                 stdout=subprocess.PIPE, stderr=subprocess.PIPE, universal_newlines=True, timeout=60)
            m = re.search(r"Duration:\s*(\d+):(\d+):(\d+)", out.stderr)
            if m:
                h, mi, s = map(int, m.groups())
                return h * 3600 + mi * 60 + s
        except Exception:
            pass
    return 0


def _probe_resolution(file_path: str) -> str:
    """提取真实分辨率。生产机没有 ffprobe，故用 ffmpeg -i 解析 stderr。"""
    ffmpeg = _find_bin("ffmpeg")
    if not ffmpeg:
        return ""
    try:
        out = subprocess.run([ffmpeg, "-i", file_path],
                             stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                             universal_newlines=True, timeout=60)
        # 只认 Video 流那一行，避免把封面图/缩略流的尺寸当成主画面
        for line in (out.stderr or "").splitlines():
            if "Video:" not in line:
                continue
            m = re.search(r"(\d{2,5})x(\d{2,5})", line)
            if m:
                return f"{m.group(1)}x{m.group(2)}"
    except Exception:
        pass
    return ""


def _generate_thumbnail(file_path: str, thumb_path: str) -> bool:
    """用 ffmpeg 截取视频第 1 秒的一帧作为缩略图。"""
    ffmpeg = shutil.which("ffmpeg")
    if not ffmpeg:
        return False
    try:
        subprocess.run(
            [ffmpeg, "-y", "-ss", "00:00:01", "-i", file_path,
             "-frames:v", "1", "-q:v", "3", thumb_path],
            stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=60,
        )
        return os.path.exists(thumb_path)
    except Exception:
        return False



@router.get("/categories", response_model=ApiResponse[List[FootageCategoryResponse]])
def list_categories(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    cats = db.query(FootageCategory).filter(
        FootageCategory.user_id == current_user.id
    ).all()
    return ApiResponse(data=[FootageCategoryResponse.model_validate(c) for c in cats])


@router.post("/categories", response_model=ApiResponse[FootageCategoryResponse])
def create_category(
    cat_in: FootageCategoryCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    cat = FootageCategory(
        user_id=current_user.id,
        name=cat_in.name,
        type=cat_in.type,
        icon=cat_in.icon,
    )
    db.add(cat)
    db.commit()
    db.refresh(cat)
    return ApiResponse(data=FootageCategoryResponse.model_validate(cat))


@router.post("/upload", response_model=ApiResponse[dict])
async def upload_footage(
    file: UploadFile = File(...),
    category_id: int = Form(None),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    allowed_types = {"video/mp4", "video/quicktime", "video/x-msvideo", "video/webm"}
    if file.content_type and file.content_type not in allowed_types:
        raise HTTPException(status_code=400, detail="仅支持视频文件(mp4/mov/avi/webm)")

    ext = os.path.splitext(file.filename or "video.mp4")[1] or ".mp4"
    filename = f"{uuid.uuid4().hex}{ext}"
    user_dir = os.path.join(UPLOAD_DIR, str(current_user.id))
    os.makedirs(user_dir, exist_ok=True)
    file_path = os.path.join(user_dir, filename)

    # 流式落盘：整片 read() 会把上百 MB 素材全压进内存，
    # 线上 2 个 worker 并发上传时容易触发 OOM。
    file_size = 0
    with open(file_path, "wb") as f:
        while True:
            chunk = await file.read(1024 * 1024)
            if not chunk:
                break
            file_size += len(chunk)
            f.write(chunk)

    # 以下都是阻塞的 ffmpeg 子进程调用，直接在协程里跑会占住事件循环，
    # 让同一个 worker 上的其他请求（含轮询接口）一起卡住。丢到线程池执行。
    # 提取视频时长 + 生成缩略图
    stem = os.path.splitext(filename)[0]
    thumb_filename = f"{stem}_thumb.jpg"
    thumb_path = os.path.join(user_dir, thumb_filename)

    duration = await run_in_threadpool(_probe_duration, file_path)
    thumb_ok = await run_in_threadpool(_generate_thumbnail, file_path, thumb_path)
    thumb_url = (
        f"/static/footage/{current_user.id}/{thumb_filename}" if thumb_ok else None
    )
    resolution = await run_in_threadpool(_probe_resolution, file_path)

    # 拍摄质量检测：口型合成的效果上限由素材光线决定，模型补不回来。
    # 只提示不拦截——素材也可能只用作 B-roll，不一定要走口型。
    try:
        quality = await run_in_threadpool(inspect_footage, file_path)
    except Exception:
        quality = None

    footage = Footage(
        user_id=current_user.id,
        category_id=category_id,
        filename=file.filename or filename,
        file_path=file_path,
        thumbnail=thumb_url,
        duration=duration,
        file_size=file_size,
        resolution=resolution or "1080x1920",
        status="ready",
    )
    db.add(footage)
    db.commit()
    db.refresh(footage)
    data = FootageResponse.model_validate(footage).model_dump()
    if quality:
        data["quality"] = quality
    return ApiResponse(data=data)


@router.get("/list", response_model=ApiResponse[dict])
def list_footages(
    category_id: int = Query(None),
    scene: str = Query(None),
    page: int = Query(1, ge=1),
    size: int = Query(20, ge=1, le=100),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    query = db.query(Footage).filter(Footage.user_id == current_user.id, Footage.status != "deleted")
    if category_id:
        query = query.filter(Footage.category_id == category_id)
    if scene:
        query = query.filter(Footage.scene == scene)
    total = query.count()
    items = (
        query.order_by(Footage.created_at.desc())
        .offset((page - 1) * size)
        .limit(size)
        .all()
    )
    return ApiResponse(
        data={
            "items": [FootageResponse.model_validate(f) for f in items],
            "total": total,
            "page": page,
            "size": size,
        }
    )


@router.put("/{footage_id}", response_model=ApiResponse[FootageResponse])
def update_footage(
    footage_id: int,
    update_in: FootageUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    footage = (
        db.query(Footage)
        .filter(Footage.id == footage_id, Footage.user_id == current_user.id)
        .first()
    )
    if not footage:
        raise HTTPException(status_code=404, detail="素材不存在")

    if update_in.category_id is not None:
        footage.category_id = update_in.category_id
    if update_in.scene is not None:
        footage.scene = update_in.scene
    if update_in.emotion is not None:
        footage.emotion = update_in.emotion
    if update_in.action is not None:
        footage.action = update_in.action
    if update_in.topics is not None:
        footage.topics = update_in.topics
    db.commit()
    db.refresh(footage)
    return ApiResponse(data=FootageResponse.model_validate(footage))


@router.delete("/{footage_id}", response_model=ApiResponse[dict])
def delete_footage(
    footage_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    footage = (
        db.query(Footage)
        .filter(Footage.id == footage_id, Footage.user_id == current_user.id)
        .first()
    )
    if not footage:
        raise HTTPException(status_code=404, detail="素材不存在")


    # 系统素材只软删除，不删物理文件
    if footage.source_type != "user_upload":
        footage.status = "deleted"
        db.commit()
        return ApiResponse(data={"deleted": True, "type": "soft"})

    if os.path.exists(footage.file_path):
        os.remove(footage.file_path)
    db.delete(footage)
    db.commit()
    return ApiResponse(data={"deleted": True})


@router.get("/{footage_id}/quality", response_model=ApiResponse[dict])
def check_footage_quality(
    footage_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """复检已有素材的拍摄质量（上传于本功能之前的素材也能查）。"""
    footage = (
        db.query(Footage)
        .filter(Footage.id == footage_id, Footage.user_id == current_user.id)
        .first()
    )
    if not footage:
        raise HTTPException(status_code=404, detail="素材不存在")
    if not os.path.exists(footage.file_path):
        raise HTTPException(status_code=404, detail="素材文件已丢失")
    return ApiResponse(data=inspect_footage(footage.file_path))


@router.get("/suggest-shots", response_model=ApiResponse[dict])
def get_suggest_shots(
    current_user: User = Depends(get_current_user),
):
    """获取推荐拍摄素材清单"""
    suggestions = {
        "life": [
            {"scene": "厨房", "action": "做饭", "emotion": "温暖"},
            {"scene": "客厅", "action": "喝水", "emotion": "平静"},
            {"scene": "户外", "action": "散步", "emotion": "轻松"},
            {"scene": "市场", "action": "买菜", "emotion": "生活"},
            {"scene": "书房", "action": "看书", "emotion": "思考"},
        ],
        "health": [
            {"scene": "公园", "action": "运动", "emotion": "活力"},
            {"scene": "厨房", "action": "做早餐", "emotion": "温暖"},
            {"scene": "卫生间", "action": "泡脚", "emotion": "放松"},
            {"scene": "茶室", "action": "喝茶", "emotion": "平静"},
        ],
        "emotion": [
            {"scene": "窗边", "action": "看窗外", "emotion": "思考"},
            {"scene": "沙发", "action": "微笑", "emotion": "温暖"},
            {"scene": "客厅", "action": "与家人聊天", "emotion": "温馨"},
        ],
        "work": [
            {"scene": "书房", "action": "学习", "emotion": "专注"},
            {"scene": "直播间", "action": "直播准备", "emotion": "专业"},
            {"scene": "办公室", "action": "产品整理", "emotion": "认真"},
        ],
    }
    return ApiResponse(data=suggestions)


@router.post("/restore-demo", response_model=ApiResponse[dict])
def restore_demo_footages(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """恢复被删除的演示素材，并补充可能新增的系统素材"""
    from app.services.demo_assets import restore_demo_footages
    count = restore_demo_footages(db, current_user.id)
    return ApiResponse(data={"restored_count": count})


# ===== H3 图生视频：主播照片上传 =====
ANCHOR_DIR = os.path.join(settings.STORAGE_PATH, "anchor_portraits")
os.makedirs(ANCHOR_DIR, exist_ok=True)
ANCHOR_IMG_TYPES = {"image/jpeg", "image/png", "image/webp"}
ANCHOR_EXT = {"image/jpeg": ".jpg", "image/png": ".png", "image/webp": ".webp"}


@router.post("/anchor-portrait", response_model=ApiResponse[dict])
async def upload_anchor_portrait(
    file: UploadFile = File(...),
    current_user: User = Depends(get_current_user),
):
    """上传一张主播正面照，供 H3 图生视频做人像锚点。返回 person_image 路径。"""
    ctype = file.content_type or ""
    if ctype not in ANCHOR_IMG_TYPES:
        raise HTTPException(status_code=400, detail="请上传 jpg/png/webp 格式的照片")
    content = await file.read()
    if not content or len(content) < 1024:
        raise HTTPException(status_code=400, detail="照片内容为空或过小")
    if len(content) > 20 * 1024 * 1024:
        raise HTTPException(status_code=400, detail="照片不能超过 20MB")
    ext = ANCHOR_EXT.get(ctype, ".jpg")
    name = f"anchor_{current_user.id}_{uuid.uuid4().hex[:10]}{ext}"
    user_dir = os.path.join(ANCHOR_DIR, str(current_user.id))
    os.makedirs(user_dir, exist_ok=True)
    fpath = os.path.join(user_dir, name)
    with open(fpath, "wb") as f:
        f.write(content)
    # 返回相对 storage_root(backend/) 的路径：storage/anchor_portraits/<uid>/<file>，
    # 与 video_producer._resolve_storage_path 的相对解析基准一致。
    rel = os.path.relpath(fpath, os.path.dirname(settings.STORAGE_PATH.rstrip("/\\"))).replace("\\", "/")
    if rel == "." or rel.startswith(".."):
        rel = "storage/anchor_portraits/" + os.path.join(str(current_user.id), name).replace("\\", "/")
    static_rel = rel[len("storage/"):] if rel.startswith("storage/") else rel
    return ApiResponse(data={"person_image": rel, "url": f"/static/{static_rel}", "filename": name})


@router.get("/anchor-portraits", response_model=ApiResponse[dict])
def list_anchor_portraits(
    current_user: User = Depends(get_current_user),
):
    """列出当前用户上传的主播照片，供 H3 人物素材库使用。"""
    user_dir = os.path.join(ANCHOR_DIR, str(current_user.id))
    items = []
    if os.path.isdir(user_dir):
        for name in sorted(os.listdir(user_dir)):
            if not os.path.isfile(os.path.join(user_dir, name)):
                continue
            rel = f"storage/anchor_portraits/{current_user.id}/{name}"
            static_rel = f"anchor_portraits/{current_user.id}/{name}"
            items.append({
                "filename": name,
                "person_image": rel,
                "url": f"/static/{static_rel}",
            })
    return ApiResponse(data={"items": items})


@router.delete("/anchor-portraits/{filename}", response_model=ApiResponse[dict])
def delete_anchor_portrait(
    filename: str,
    current_user: User = Depends(get_current_user),
):
    """删除当前用户的一张主播照片。"""
    if not re.fullmatch(r"anchor_\d+_[0-9a-f]{10}\.(jpg|png|webp)", filename):
        raise HTTPException(status_code=400, detail="非法文件名")
    user_dir = os.path.join(ANCHOR_DIR, str(current_user.id))
    fpath = os.path.join(user_dir, filename)
    if not os.path.isfile(fpath):
        raise HTTPException(status_code=404, detail="照片不存在")
    os.remove(fpath)
    return ApiResponse(data={"success": True, "filename": filename})


# ===== H3 自定义场景图（定场图/场景锚点图）=====
ANCHOR_SCENE_DIR = os.path.join(settings.STORAGE_PATH, "anchor_scenes")
os.makedirs(ANCHOR_SCENE_DIR, exist_ok=True)


@router.post("/anchor-scenes", response_model=ApiResponse[dict])
async def upload_anchor_scene(
    file: UploadFile = File(...),
    current_user: User = Depends(get_current_user),
):
    """上传一张自定义讲解场景图，H3 生成时用作场景锚点/定场图。"""
    ctype = file.content_type or ""
    if ctype not in ANCHOR_IMG_TYPES:
        raise HTTPException(status_code=400, detail="请上传 jpg/png/webp 格式的图片")
    content = await file.read()
    if not content or len(content) < 1024:
        raise HTTPException(status_code=400, detail="图片内容为空或过小")
    if len(content) > 20 * 1024 * 1024:
        raise HTTPException(status_code=400, detail="图片不能超过 20MB")
    ext = ANCHOR_EXT.get(ctype, ".jpg")
    name = f"scene_{current_user.id}_{uuid.uuid4().hex[:10]}{ext}"
    user_dir = os.path.join(ANCHOR_SCENE_DIR, str(current_user.id))
    os.makedirs(user_dir, exist_ok=True)
    fpath = os.path.join(user_dir, name)
    with open(fpath, "wb") as f:
        f.write(content)
    rel = "storage/anchor_scenes/" + os.path.join(str(current_user.id), name).replace("\\", "/")
    static_rel = f"anchor_scenes/{current_user.id}/{name}"
    return ApiResponse(data={"scene_image": rel, "url": f"/static/{static_rel}", "filename": name})


@router.get("/anchor-scenes", response_model=ApiResponse[dict])
def list_anchor_scenes(
    current_user: User = Depends(get_current_user),
):
    """列出当前用户上传的自定义场景图。"""
    user_dir = os.path.join(ANCHOR_SCENE_DIR, str(current_user.id))
    items = []
    if os.path.isdir(user_dir):
        for name in sorted(os.listdir(user_dir)):
            if not os.path.isfile(os.path.join(user_dir, name)):
                continue
            items.append({
                "filename": name,
                "scene_image": f"storage/anchor_scenes/{current_user.id}/{name}",
                "url": f"/static/anchor_scenes/{current_user.id}/{name}",
            })
    return ApiResponse(data={"items": items})


@router.delete("/anchor-scenes/{filename}", response_model=ApiResponse[dict])
def delete_anchor_scene(
    filename: str,
    current_user: User = Depends(get_current_user),
):
    """删除当前用户的一张自定义场景图。"""
    if not re.fullmatch(r"scene_\d+_[0-9a-f]{10}\.(jpg|png|webp)", filename):
        raise HTTPException(status_code=400, detail="非法文件名")
    user_dir = os.path.join(ANCHOR_SCENE_DIR, str(current_user.id))
    fpath = os.path.join(user_dir, filename)
    if not os.path.isfile(fpath):
        raise HTTPException(status_code=404, detail="场景图不存在")
    os.remove(fpath)
    return ApiResponse(data={"success": True, "filename": filename})
