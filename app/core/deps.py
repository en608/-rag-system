"""FastAPI 依赖：租户上下文等。"""

from fastapi import Header, HTTPException, status

from app.utils.jwt import verify_token

DEFAULT_TENANT = "default"


async def get_tenant_id(
    x_tenant_id: str | None = Header(None, alias="X-Tenant-ID"),
) -> str:
    """从请求头解析租户 ID，未提供时使用默认租户。"""
    if x_tenant_id and x_tenant_id.strip():
        return x_tenant_id.strip()
    return DEFAULT_TENANT


async def get_current_user_id(
    authorization: str | None = Header(None, alias="Authorization"),
) -> int:
    """从 JWT token 中获取当前用户 ID，无 token 时返回 401。"""
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="未提供认证 Token",
        )

    token = authorization[7:]
    payload = verify_token(token)
    user_id = payload.get("sub")
    if user_id is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="无效的 Token",
        )
    return int(user_id)
