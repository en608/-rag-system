"""
初始化测试用户（可选脚本）。
用法（在项目根目录）：
  python -m scripts.seed_user --tenant-id demo --username admin
"""

import argparse
import asyncio

from sqlalchemy import select

from app.core.database import AsyncSessionLocal
from app.models.user import User


async def seed(tenant_id: str, username: str, email: str | None) -> None:
    async with AsyncSessionLocal() as session:
        existing = await session.execute(
            select(User).where(
                User.tenant_id == tenant_id,
                User.username == username,
            )
        )
        if existing.scalar_one_or_none():
            print(f"用户已存在: tenant={tenant_id}, username={username}")
            return

        user = User(tenant_id=tenant_id, username=username, email=email)
        session.add(user)
        await session.commit()
        await session.refresh(user)
        print(f"创建成功: user_id={user.id}, tenant={tenant_id}, username={username}")


def main() -> None:
    parser = argparse.ArgumentParser(description="创建测试用户")
    parser.add_argument("--tenant-id", default="demo", help="租户 ID")
    parser.add_argument("--username", default="admin", help="用户名")
    parser.add_argument("--email", default=None, help="邮箱")
    args = parser.parse_args()
    asyncio.run(seed(args.tenant_id, args.username, args.email))


if __name__ == "__main__":
    main()
