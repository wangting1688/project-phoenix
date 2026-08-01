"""
用户服务层

管理用户（账号主体）的创建、查询、认证、状态管理。
"""

from sqlalchemy.orm import Session
from typing import Optional, List
from datetime import datetime

from app.models import Tenant, User
from app.schemas.tenant import TenantCreate, TenantUpdate
from app.core.security import get_password_hash, verify_password


def get_tenant_by_id(db: Session, tenant_id: int) -> Optional[Tenant]:
    return db.query(Tenant).filter(Tenant.id == tenant_id).first()


def get_tenant_by_account(db: Session, account: str) -> Optional[Tenant]:
    return db.query(Tenant).filter(Tenant.account == account).first()


def get_tenant_by_code(db: Session, code: str) -> Optional[Tenant]:
    return db.query(Tenant).filter(Tenant.code == code).first()


def list_tenants(db: Session, skip: int = 0, limit: int = 100) -> tuple[List[Tenant], int]:
    query = db.query(Tenant)
    total = query.count()
    items = query.order_by(Tenant.created_at.desc()).offset(skip).limit(limit).all()
    return items, total


CODE_PREFIX = "U"
CODE_DIGITS = 4


def generate_next_code(db: Session) -> str:
    """按新增顺序生成用户编码: U0001, U0002 ...

    取现有最大序号 +1, 而非用总数, 避免删除后编码重复。
    """
    rows = db.query(Tenant.code).filter(Tenant.code.like(f"{CODE_PREFIX}%")).all()
    max_seq = 0
    for (code,) in rows:
        suffix = (code or "")[len(CODE_PREFIX):]
        if suffix.isdigit():
            max_seq = max(max_seq, int(suffix))
    return f"{CODE_PREFIX}{max_seq + 1:0{CODE_DIGITS}d}"


def create_tenant(db: Session, tenant_in: TenantCreate) -> Tenant:
    # 编码留空则按新增顺序自动生成
    code = (tenant_in.code or "").strip() or generate_next_code(db)
    if get_tenant_by_code(db, code):
        raise ValueError("用户编码已存在")
    if get_tenant_by_account(db, tenant_in.account):
        raise ValueError("登录账号已存在")

    tenant = Tenant(
        name=tenant_in.name,
        code=code,
        account=tenant_in.account,
        password_hash=get_password_hash(tenant_in.password),
        contact_name=tenant_in.contact_name,
        contact_phone=tenant_in.contact_phone,
        expires_at=tenant_in.expires_at,
        max_users=tenant_in.max_users,
        max_video_projects=tenant_in.max_video_projects,
        config=tenant_in.config,
        status=1,
    )
    db.add(tenant)
    db.commit()
    db.refresh(tenant)
    return tenant


def update_tenant(db: Session, tenant_id: int, tenant_in: TenantUpdate) -> Optional[Tenant]:
    tenant = get_tenant_by_id(db, tenant_id)
    if not tenant:
        return None

    update_data = tenant_in.model_dump(exclude_unset=True)
    for key, value in update_data.items():
        setattr(tenant, key, value)

    # 自动更新过期状态
    if tenant.expires_at and datetime.utcnow() > tenant.expires_at:
        tenant.status = -1

    db.commit()
    db.refresh(tenant)
    return tenant


def authenticate_tenant(db: Session, account: str, password: str) -> Optional[Tenant]:
    tenant = get_tenant_by_account(db, account)
    if not tenant:
        return None
    if not verify_password(password, tenant.password_hash):
        return None
    if not tenant.is_active():
        return None
    return tenant


def count_tenant_users(db: Session, tenant_id: int) -> int:
    return db.query(User).filter(User.tenant_id == tenant_id).count()


def create_tenant_user(db: Session, tenant_id: int, phone: str, password: str,
                       nickname: str = None, role: str = "anchor") -> User:
    """创建子账号"""
    tenant = get_tenant_by_id(db, tenant_id)
    if not tenant:
        raise ValueError("用户不存在")

    if not tenant.is_active():
        raise ValueError("用户已停用或过期")

    # 检查用户数限制
    current_count = count_tenant_users(db, tenant_id)
    if current_count >= tenant.max_users:
        raise ValueError(f"已达到最大用户数限制（{tenant.max_users}人）")

    # 检查手机号唯一性
    existing = db.query(User).filter(User.phone == phone).first()
    if existing:
        raise ValueError("手机号已注册")

    user = User(
        tenant_id=tenant_id,
        phone=phone,
        password_hash=get_password_hash(password),
        nickname=nickname or phone,
        role=role,
        status=1,
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


def check_tenant_expired(db: Session, tenant_id: int) -> bool:
    """检查用户是否过期，自动更新状态"""
    tenant = get_tenant_by_id(db, tenant_id)
    if not tenant:
        return True
    if tenant.expires_at and datetime.utcnow() > tenant.expires_at and tenant.status == 1:
        tenant.status = -1
        db.commit()
        return True
    return not tenant.is_active()
