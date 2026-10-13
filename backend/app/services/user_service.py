from sqlalchemy.orm import Session
from typing import Optional

from app.models import User
from app.schemas import UserCreate
from app.core.security import get_password_hash, verify_password


def get_user_by_id(db: Session, user_id: int) -> Optional[User]:
    return db.query(User).filter(User.id == user_id).first()


def get_user_by_phone(db: Session, phone: str) -> Optional[User]:
    return db.query(User).filter(User.phone == phone).first()


def get_user_by_openid(db: Session, openid: str) -> Optional[User]:
    return db.query(User).filter(User.openid == openid).first()


def create_user(db: Session, user_in: UserCreate) -> User:
    db_user = User(
        phone=user_in.phone,
        password_hash=get_password_hash(user_in.password),
        nickname=user_in.nickname or user_in.phone,
        role="anchor",
        status=1,
    )
    db.add(db_user)
    db.commit()
    db.refresh(db_user)
    return db_user


def authenticate_user(db: Session, phone: str, password: str) -> Optional[User]:
    user = get_user_by_phone(db, phone)
    if not user:
        return None
    if not verify_password(password, user.password_hash):
        return None
    if user.status != 1:
        return None
    return user


def create_wechat_user(
    db: Session,
    openid: str,
    nickname: str = "",
    avatar: str = "",
    unionid: Optional[str] = None,
) -> User:
    """按微信 openid 创建账号（手机号留空，后续可绑定）。"""
    db_user = User(
        phone=None,
        password_hash="",  # 微信登录无需密码，绑定手机号时再设置
        nickname=nickname or "微信用户",
        avatar=avatar or None,
        openid=openid,
        unionid=unionid,
        wechat_nickname=nickname or None,
        wechat_avatar=avatar or None,
        role="anchor",
        status=1,
    )
    db.add(db_user)
    db.commit()
    db.refresh(db_user)
    return db_user


def update_wechat_profile(
    db: Session,
    user: User,
    nickname: str = "",
    avatar: str = "",
    unionid: Optional[str] = None,
) -> User:
    if nickname:
        user.nickname = nickname
        user.wechat_nickname = nickname
    if avatar:
        user.avatar = avatar
        user.wechat_avatar = avatar
    if unionid:
        user.unionid = unionid
    db.commit()
    db.refresh(user)
    return user
