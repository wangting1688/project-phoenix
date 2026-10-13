from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.api.deps import get_current_user
from app.models import User, UserNotification
from app.schemas.common import ApiResponse

router = APIRouter(prefix="/notifications", tags=["通知"])


def _to_dict(n: UserNotification) -> dict:
    return {
        "id": n.id,
        "type": n.type,
        "title": n.title,
        "content": n.content or "",
        "link": n.link or "",
        "is_read": bool(n.is_read),
        "created_at": n.created_at.isoformat() if n.created_at else None,
    }


@router.get("", response_model=ApiResponse[list])
def list_notifications(
    limit: int = 50,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    items = (
        db.query(UserNotification)
        .filter(UserNotification.user_id == current_user.id)
        .order_by(UserNotification.created_at.desc(), UserNotification.id.desc())
        .limit(min(max(limit, 1), 100))
        .all()
    )
    return ApiResponse(data=[_to_dict(n) for n in items])


@router.get("/unread-count", response_model=ApiResponse[dict])
def unread_count(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    count = (
        db.query(UserNotification)
        .filter(
            UserNotification.user_id == current_user.id,
            UserNotification.is_read.is_(False),
        )
        .count()
    )
    return ApiResponse(data={"count": count})


@router.post("/{notification_id}/read", response_model=ApiResponse[dict])
def mark_read(
    notification_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    n = db.query(UserNotification).filter(
        UserNotification.id == notification_id,
        UserNotification.user_id == current_user.id,
    ).first()
    if not n:
        raise HTTPException(status_code=404, detail="通知不存在")
    n.is_read = True
    db.commit()
    return ApiResponse(data={"id": n.id, "is_read": True})


@router.post("/read-all", response_model=ApiResponse[dict])
def mark_all_read(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    db.query(UserNotification).filter(
        UserNotification.user_id == current_user.id,
        UserNotification.is_read.is_(False),
    ).update({"is_read": True}, synchronize_session=False)
    db.commit()
    return ApiResponse(data={"ok": True})
