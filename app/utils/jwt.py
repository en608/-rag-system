"""JWT 认证工具模块。"""

from datetime import datetime, timedelta
from typing import Optional

import jwt
from fastapi import HTTPException, status

from app.core.config import get_settings

# JWT 配置
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 60 * 24  # 24 小时


def create_access_token(data: dict, expires_delta: Optional[timedelta] = None) -> str:
    """
    创建 JWT access token。

    Args:
        data: 要编码到 token 中的数据
        expires_delta: 过期时间增量，默认 24 小时

    Returns:
        编码后的 JWT token 字符串
    """
    settings = get_settings()
    to_encode = data.copy()

    if expires_delta:
        expire = datetime.utcnow() + expires_delta
    else:
        expire = datetime.utcnow() + timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)

    to_encode.update({"exp": expire})
    encoded_jwt = jwt.encode(to_encode, settings.secret_key, algorithm=ALGORITHM)

    return encoded_jwt


def verify_token(token: str) -> dict:
    """
    验证 JWT token 并返回payload。

    Args:
        token: JWT token 字符串

    Returns:
        解码后的 payload 字典

    Raises:
        HTTPException: token 无效或已过期
    """
    settings = get_settings()

    try:
        payload = jwt.decode(token, settings.secret_key, algorithms=[ALGORITHM])
        return payload
    except jwt.ExpiredSignatureError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token 已过期，请重新登录",
        )
    except jwt.InvalidTokenError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="无效的 Token",
        )
