"""异步数据库引擎与会话管理。"""

from collections.abc import AsyncGenerator

from sqlalchemy.ext.asyncio import (
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from app.core.config import get_settings

settings = get_settings()

# 创建异步引擎，配置连接池参数
engine = create_async_engine(
    settings.database_url,
    echo=settings.debug,
    pool_pre_ping=True,
    pool_size=settings.db_pool_size,
    max_overflow=settings.db_max_overflow,
    pool_timeout=settings.db_pool_timeout,
    pool_recycle=settings.db_pool_recycle,
)

# 会话工厂：每个请求独立 Session，由依赖注入管理生命周期
AsyncSessionLocal = async_sessionmaker(
    bind=engine,
    class_=AsyncSession,
    expire_on_commit=False,
    autocommit=False,
    autoflush=False,
)


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    """
    FastAPI 依赖：提供数据库会话并在请求结束后自动关闭。
    不在此处 commit，由 Service 层显式提交事务。
    """
    async with AsyncSessionLocal() as session:
        try:
            yield session
        finally:
            await session.close()
