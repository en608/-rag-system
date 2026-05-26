"""用户认证 API。"""

import bcrypt
from fastapi import APIRouter, Depends, HTTPException, Request, status
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.core.database import get_db
from app.core.limiter import limiter
from app.models.user import User
from app.utils.jwt import create_access_token

router = APIRouter(prefix="/users", tags=["users"])

DEFAULT_TENANT = "default"
settings = get_settings()


class RegisterRequest(BaseModel):
    """注册请求模型。"""
    username: str = Field(..., min_length=2, max_length=128)
    password: str = Field(..., min_length=6, max_length=128)


class LoginRequest(BaseModel):
    """登录请求模型。"""
    username: str
    password: str


class UserResponse(BaseModel):
    """用户信息响应。"""
    user_id: int
    username: str
    token: str


def _hash_password(password: str) -> str:
    return bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")


def _verify_password(password: str, password_hash: str) -> bool:
    return bcrypt.checkpw(password.encode("utf-8"), password_hash.encode("utf-8"))


@router.post(
    "/register",
    response_model=UserResponse,
    summary="用户注册",
)
@limiter.limit(settings.rate_limit_auth)
async def register(
    request: Request,
    body: RegisterRequest,
    db: AsyncSession = Depends(get_db),
) -> UserResponse:
    result = await db.execute(
        select(User).where(
            User.tenant_id == DEFAULT_TENANT,
            User.username == body.username,
        )
    )
    if result.scalar_one_or_none() is not None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="用户名已存在",
        )

    user = User(
        tenant_id=DEFAULT_TENANT,
        username=body.username,
        password_hash=_hash_password(body.password),
    )
    db.add(user)
    await db.commit()
    await db.refresh(user)

    # 创建 JWT token
    token = create_access_token(
        data={"sub": str(user.id), "username": user.username}
    )

    return UserResponse(user_id=user.id, username=user.username, token=token)


@router.post(
    "/login",
    response_model=UserResponse,
    summary="用户登录",
)
@limiter.limit(settings.rate_limit_auth)
async def login(
    request: Request,
    body: LoginRequest,
    db: AsyncSession = Depends(get_db),
) -> UserResponse:
    result = await db.execute(
        select(User).where(
            User.tenant_id == DEFAULT_TENANT,
            User.username == body.username,
        )
    )
    user = result.scalar_one_or_none()

    if user is None or not _verify_password(body.password, user.password_hash):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="用户名或密码不正确",
        )

    # 创建 JWT token
    token = create_access_token(
        data={"sub": str(user.id), "username": user.username}
    )

    return UserResponse(user_id=user.id, username=user.username, token=token)
