from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from datetime import timedelta

from app.core.database import get_db
from app.core.security import create_access_token
from app.core.config import settings
from app.schemas import UserCreate, UserLogin, UserResponse, LoginResponse, CurrentUserResponse, ApiResponse
from app.services import user_service
from app.api.deps import get_current_user
from app.models import User
from urllib.parse import quote, urlencode

router = APIRouter(prefix="/auth", tags=["认证"])


@router.post("/register", response_model=ApiResponse[LoginResponse])
def register(user_in: UserCreate, db: Session = Depends(get_db)):
    db_user = user_service.get_user_by_phone(db, phone=user_in.phone)
    if db_user:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="手机号已注册",
        )
    user = user_service.create_user(db, user_in=user_in)
    access_token = create_access_token(
        data={"sub": str(user.id)},
        expires_delta=timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES),
    )
    # 注入系统演示素材（如果启用）
    try:
        from app.services.demo_assets import seed_demo_footages, is_demo_footage_enabled
        if is_demo_footage_enabled():
            seed_demo_footages(db, user.id)
    except Exception:
        # 演示素材注入失败不阻塞注册流程
        import logging
        logging.getLogger(__name__).warning("演示素材注入失败", exc_info=True)

    return ApiResponse(
        data=LoginResponse(
            token=access_token,
            user=UserResponse.model_validate(user),
        )
    )


@router.post("/login", response_model=ApiResponse[LoginResponse])
def login(user_in: UserLogin, db: Session = Depends(get_db)):
    user = user_service.authenticate_user(db, phone=user_in.phone, password=user_in.password)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="手机号或密码错误",
            headers={"WWW-Authenticate": "Bearer"},
        )
    access_token = create_access_token(
        data={"sub": str(user.id)},
        expires_delta=timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES),
    )
    # 注入系统演示素材（如果启用）
    try:
        from app.services.demo_assets import seed_demo_footages, is_demo_footage_enabled
        if is_demo_footage_enabled():
            seed_demo_footages(db, user.id)
    except Exception:
        # 演示素材注入失败不阻塞注册流程
        import logging
        logging.getLogger(__name__).warning("演示素材注入失败", exc_info=True)

    return ApiResponse(
        data=LoginResponse(
            token=access_token,
            user=UserResponse.model_validate(user),
        )
    )


@router.get("/me", response_model=ApiResponse[CurrentUserResponse])
def get_me(current_user: User = Depends(get_current_user)):
    return ApiResponse(
        data=CurrentUserResponse(
            id=current_user.id,
            nickname=current_user.nickname,
            avatar=current_user.avatar,
            role=current_user.role,
            tenant_id=current_user.tenant_id,
            content_profile={"style": "故事型", "category": "健康"},
        )
    )


@router.get("/wechat/config", response_model=ApiResponse[dict])
def wechat_config():
    enabled = bool(settings.WECHAT_APP_ID and settings.WECHAT_APP_SECRET)
    return ApiResponse(
        data={
            "enabled": enabled,
            "app_id": settings.WECHAT_APP_ID or "",
        }
    )


@router.get("/wechat/login-url", response_model=ApiResponse[dict])
def wechat_login_url(redirect_uri: str = ""):
    if not settings.WECHAT_APP_ID or not settings.WECHAT_APP_SECRET:
        raise HTTPException(
            status_code=503,
            detail="微信登录未配置，请先配置 WECHAT_APP_ID / WECHAT_APP_SECRET",
        )
    target = redirect_uri or settings.WECHAT_REDIRECT_URI or ""
    if not target:
        raise HTTPException(
            status_code=400,
            detail="缺少 redirect_uri，请传入前端登录页地址",
        )
    params = urlencode({
        "appid": settings.WECHAT_APP_ID,
        "redirect_uri": target,
        "response_type": "code",
        "scope": "snsapi_userinfo",
        "state": "phoenix_wechat",
    })
    return ApiResponse(
        data={"url": f"https://open.weixin.qq.com/connect/oauth2/authorize?{params}#wechat_redirect"}
    )


@router.get("/wechat/callback", response_model=ApiResponse[LoginResponse])
def wechat_callback(code: str, db: Session = Depends(get_db)):
    if not settings.WECHAT_APP_ID or not settings.WECHAT_APP_SECRET:
        raise HTTPException(
            status_code=503,
            detail="微信登录未配置",
        )
    import requests as _rq

    token_resp = _rq.get(
        "https://api.weixin.qq.com/sns/oauth2/access_token",
        params={
            "appid": settings.WECHAT_APP_ID,
            "secret": settings.WECHAT_APP_SECRET,
            "code": code,
            "grant_type": "authorization_code",
        },
        timeout=15,
    ).json()
    if token_resp.get("errcode") or not token_resp.get("openid"):
        raise HTTPException(
            status_code=401,
            detail=f"微信授权失败: {token_resp.get('errmsg') or 'invalid code'}",
        )

    openid = token_resp["openid"]
    unionid = token_resp.get("unionid") or None
    nickname = ""
    avatar = ""
    try:
        userinfo = _rq.get(
            "https://api.weixin.qq.com/sns/userinfo",
            params={
                "access_token": token_resp["access_token"],
                "openid": openid,
                "lang": "zh_CN",
            },
            timeout=15,
        ).json()
        nickname = (userinfo.get("nickname") or "").strip()
        avatar = (userinfo.get("headimgurl") or "").strip()
    except Exception:
        pass

    user = user_service.get_user_by_openid(db, openid)
    if user:
        user_service.update_wechat_profile(db, user, nickname, avatar, unionid)
    else:
        user = user_service.create_wechat_user(
            db, openid, nickname=nickname, avatar=avatar, unionid=unionid
        )

    access_token = create_access_token(
        data={"sub": str(user.id)},
        expires_delta=timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES),
    )
    return ApiResponse(
        data=LoginResponse(
            token=access_token,
            user=UserResponse.model_validate(user),
        )
    )
