from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.security import decode_token
from app.services import user_service, tenant_service
from app.models import User

security = HTTPBearer()


async def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(security),
    db: Session = Depends(get_db),
) -> User:
    token = credentials.credentials
    payload = decode_token(token)
    if not payload:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid authentication credentials",
            headers={"WWW-Authenticate": "Bearer"},
        )
    user_id = payload.get("sub")
    if user_id is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid authentication credentials",
        )

    # 兼容 tenant:{id} 格式的 token
    if isinstance(user_id, str) and user_id.startswith("tenant:"):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="渠道商Token不能用于用户接口，请使用用户登录",
        )

    user = user_service.get_user_by_id(db, user_id=int(user_id))
    if user is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User not found",
        )
    if user.status != 1:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="User account is disabled",
        )

    # SaaS：校验渠道商状态和期限
    if user.tenant_id and user.role != "super_admin":
        if tenant_service.check_tenant_expired(db, user.tenant_id):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="渠道商已停用或已过期",
            )

    return user


async def get_current_active_user(
    current_user: User = Depends(get_current_user),
) -> User:
    return current_user


async def get_current_super_admin(
    current_user: User = Depends(get_current_user),
) -> User:
    """仅总部管理员可访问"""
    if current_user.role != "super_admin":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="仅总部管理员可执行此操作",
        )
    return current_user


async def get_tenant_admin(
    current_user: User = Depends(get_current_user),
) -> User:
    """渠道管理员或总部管理员"""
    if current_user.role not in ("super_admin", "tenant_admin"):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="需要渠道管理员权限",
        )
    return current_user
