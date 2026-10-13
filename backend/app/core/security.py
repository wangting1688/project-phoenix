from datetime import datetime, timedelta
from typing import Optional
from jose import JWTError, jwt
import hashlib
import hmac
import os
import time

from app.core.config import settings


def _hash_password(password: str, salt: str = None) -> str:
    if salt is None:
        salt = os.urandom(16).hex()
    hash_obj = hashlib.pbkdf2_hmac(
        'sha256',
        password.encode('utf-8'),
        salt.encode('utf-8'),
        100000
    )
    return f"{salt}${hash_obj.hex()}"


def verify_password(plain_password: str, hashed_password: str) -> bool:
    try:
        salt, _ = hashed_password.split('$', 1)
        new_hash = _hash_password(plain_password, salt)
        return new_hash == hashed_password
    except (ValueError, AttributeError):
        return False


def get_password_hash(password: str) -> str:
    return _hash_password(password)


def create_access_token(data: dict, expires_delta: Optional[timedelta] = None) -> str:
    to_encode = data.copy()
    if expires_delta:
        expire = datetime.utcnow() + expires_delta
    else:
        expire = datetime.utcnow() + timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
    to_encode.update({"exp": expire})
    encoded_jwt = jwt.encode(to_encode, settings.SECRET_KEY, algorithm=settings.ALGORITHM)
    return encoded_jwt


def decode_token(token: str) -> Optional[dict]:
    try:
        payload = jwt.decode(token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM])
        return payload
    except JWTError:
        return None


def sign_media_path(path: str, expires_in: int = 3600) -> str:
    """为 storage 相对路径生成短时签名 URL，避免 JWT 出现在分享链接/日志里。"""
    expires = int(time.time()) + expires_in
    msg = f"{path}:{expires}".encode("utf-8")
    sig = hmac.new(settings.SECRET_KEY.encode("utf-8"), msg, hashlib.sha256).hexdigest()
    return f"/static/{path}?expires={expires}&sig={sig}"


def verify_media_signature(path: str, expires, sig: str) -> bool:
    try:
        expires_int = int(expires)
    except (TypeError, ValueError):
        return False
    if expires_int < int(time.time()):
        return False
    if not sig:
        return False
    msg = f"{path}:{expires_int}".encode("utf-8")
    expected = hmac.new(settings.SECRET_KEY.encode("utf-8"), msg, hashlib.sha256).hexdigest()
    return hmac.compare_digest(expected, sig.lower())
