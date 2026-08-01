"""
渠道商管理 API

总部管理员：创建/管理渠道商账号
渠道商：登录、管理子用户
"""

from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.orm import Session
from datetime import timedelta

from app.core.database import get_db
from app.core.security import create_access_token
from app.core.config import settings
from app.schemas import (
    ApiResponse, TenantCreate, TenantUpdate, TenantResponse,
    TenantListResponse, TenantLogin, TenantLoginResponse, TenantUserCreate,
)
from app.services import tenant_service
from app.api.deps import get_current_user, get_current_super_admin
from app.models import User

router = APIRouter(prefix="/tenants", tags=["渠道商管理"])


# ========== 总部管理员：渠道商 CRUD ==========

@router.post("/", response_model=ApiResponse[TenantResponse])
def create_tenant(
    tenant_in: TenantCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_super_admin),
):
    """创建渠道商（仅总部管理员）"""
    try:
        tenant = tenant_service.create_tenant(db, tenant_in)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    return ApiResponse(data=TenantResponse.model_validate(tenant))


@router.get("/", response_model=ApiResponse[TenantListResponse])
def list_tenants(
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=500),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_super_admin),
):
    """获取渠道商列表（仅总部管理员）"""
    items, total = tenant_service.list_tenants(db, skip=skip, limit=limit)
    return ApiResponse(data=TenantListResponse(
        items=[TenantResponse.model_validate(t) for t in items],
        total=total,
    ))


@router.get("/{tenant_id}", response_model=ApiResponse[TenantResponse])
def get_tenant(
    tenant_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_super_admin),
):
    """获取渠道商详情（仅总部管理员）"""
    tenant = tenant_service.get_tenant_by_id(db, tenant_id)
    if not tenant:
        raise HTTPException(status_code=404, detail="渠道商不存在")
    return ApiResponse(data=TenantResponse.model_validate(tenant))


@router.put("/{tenant_id}", response_model=ApiResponse[TenantResponse])
def update_tenant(
    tenant_id: int,
    tenant_in: TenantUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_super_admin),
):
    """更新渠道商（仅总部管理员）"""
    tenant = tenant_service.update_tenant(db, tenant_id, tenant_in)
    if not tenant:
        raise HTTPException(status_code=404, detail="渠道商不存在")
    return ApiResponse(data=TenantResponse.model_validate(tenant))


@router.delete("/{tenant_id}", response_model=ApiResponse[dict])
def delete_tenant(
    tenant_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_super_admin),
):
    """停用渠道商（仅总部管理员）"""
    tenant = tenant_service.get_tenant_by_id(db, tenant_id)
    if not tenant:
        raise HTTPException(status_code=404, detail="渠道商不存在")
    tenant.status = 0
    db.commit()
    return ApiResponse(data={"message": "渠道商已停用"})


# ========== 渠道商登录 ==========

@router.post("/login", response_model=ApiResponse[TenantLoginResponse])
def tenant_login(
    login_in: TenantLogin,
    db: Session = Depends(get_db),
):
    """渠道商登录（使用账号+密码）"""
    tenant = tenant_service.authenticate_tenant(db, login_in.account, login_in.password)
    if not tenant:
        raise HTTPException(
            status_code=401,
            detail="账号或密码错误，或渠道商已停用/过期",
        )
    # 生成渠道商 token（sub=tenant:{id}）
    access_token = create_access_token(
        data={"sub": f"tenant:{tenant.id}", "type": "tenant"},
        expires_delta=timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES),
    )
    return ApiResponse(data=TenantLoginResponse(
        token=access_token,
        tenant=TenantResponse.model_validate(tenant),
    ))


# ========== 渠道商：管理子用户 ==========

@router.post("/{tenant_id}/users", response_model=ApiResponse[dict])
def create_tenant_user(
    tenant_id: int,
    user_in: TenantUserCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """渠道商创建子用户（需渠道管理员或总部管理员）"""
    # 权限检查：总部管理员放行；否则必须是该渠道商下的渠道管理员
    if current_user.role != "super_admin":
        if current_user.role != "tenant_admin":
            raise HTTPException(status_code=403, detail="需要渠道管理员权限")
        if current_user.tenant_id != tenant_id:
            raise HTTPException(status_code=403, detail="无权操作此渠道商")
    # 渠道管理员不得创建总部管理员, 防止提权
    if user_in.role == "super_admin" and current_user.role != "super_admin":
        raise HTTPException(status_code=403, detail="无权创建总部管理员")

    try:
        user = tenant_service.create_tenant_user(
            db, tenant_id, user_in.phone, user_in.password,
            user_in.nickname, user_in.role,
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

    return ApiResponse(data={"message": "用户创建成功", "user_id": user.id})


@router.get("/{tenant_id}/users", response_model=ApiResponse[dict])
def list_tenant_users(
    tenant_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """获取渠道商下的用户列表"""
    # 权限检查
    if current_user.tenant_id != tenant_id and current_user.role != "super_admin":
        raise HTTPException(status_code=403, detail="无权操作此渠道商")

    users = db.query(User).filter(User.tenant_id == tenant_id).all()
    return ApiResponse(data={
        "items": [{"id": u.id, "phone": u.phone, "nickname": u.nickname, "role": u.role, "status": u.status} for u in users],
        "total": len(users),
    })
