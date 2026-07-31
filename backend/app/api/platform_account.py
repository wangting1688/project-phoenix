from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from typing import List

from app.core.database import get_db
from app.api.deps import get_current_user
from app.models import User, PlatformAccount
from app.schemas import (
    ApiResponse,
    PlatformAccountCreate,
    PlatformAccountUpdate,
    PlatformAccountResponse,
    PlatformAccountListResponse,
)

router = APIRouter(prefix="/platform-accounts", tags=["平台账号"])


@router.post("", response_model=ApiResponse[PlatformAccountResponse])
def create_account(
    data: PlatformAccountCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """创建平台账号"""
    account = PlatformAccount(
        user_id=current_user.id,
        platform=data.platform,
        account_name=data.account_name,
        account_id=data.account_id,
        account_url=data.account_url,
        auth_token=data.auth_token,
        refresh_token=data.refresh_token,
        content_style=data.content_style,
        strategy_config=data.strategy_config,
    )
    db.add(account)
    db.commit()
    db.refresh(account)
    return ApiResponse(data=PlatformAccountResponse.model_validate(account))


@router.get("", response_model=ApiResponse[PlatformAccountListResponse])
def list_accounts(
    platform: str = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """获取当前用户的平台账号列表"""
    query = db.query(PlatformAccount).filter(PlatformAccount.user_id == current_user.id)
    if platform:
        query = query.filter(PlatformAccount.platform == platform)
    accounts = query.order_by(PlatformAccount.created_at.desc()).all()
    return ApiResponse(
        data=PlatformAccountListResponse(
            items=[PlatformAccountResponse.model_validate(a) for a in accounts],
            total=len(accounts),
        )
    )


@router.get("/{account_id}", response_model=ApiResponse[PlatformAccountResponse])
def get_account(
    account_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """获取单个平台账号详情"""
    account = db.query(PlatformAccount).filter(
        PlatformAccount.id == account_id,
        PlatformAccount.user_id == current_user.id,
    ).first()
    if not account:
        raise HTTPException(status_code=404, detail="账号不存在")
    return ApiResponse(data=PlatformAccountResponse.model_validate(account))


@router.put("/{account_id}", response_model=ApiResponse[PlatformAccountResponse])
def update_account(
    account_id: int,
    data: PlatformAccountUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """更新平台账号信息"""
    account = db.query(PlatformAccount).filter(
        PlatformAccount.id == account_id,
        PlatformAccount.user_id == current_user.id,
    ).first()
    if not account:
        raise HTTPException(status_code=404, detail="账号不存在")

    update_data = data.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        setattr(account, field, value)

    db.commit()
    db.refresh(account)
    return ApiResponse(data=PlatformAccountResponse.model_validate(account))


@router.delete("/{account_id}", response_model=ApiResponse[dict])
def delete_account(
    account_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """删除平台账号"""
    account = db.query(PlatformAccount).filter(
        PlatformAccount.id == account_id,
        PlatformAccount.user_id == current_user.id,
    ).first()
    if not account:
        raise HTTPException(status_code=404, detail="账号不存在")

    db.delete(account)
    db.commit()
    return ApiResponse(data={"deleted": True})
