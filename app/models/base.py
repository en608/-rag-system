"""ORM 基类与通用 Mixin。"""

from datetime import datetime

from sqlalchemy import DateTime, String, func
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


class Base(DeclarativeBase):
    """SQLAlchemy 声明式基类。"""


class TimestampMixin:
    """创建/更新时间戳，所有业务表复用。"""

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )


class TenantMixin:
    """
    租户 ID Mixin。
    为 V4.0 物理隔离预留：后续可按 tenant_id 拆分 schema 或独立数据库。
    """

    tenant_id: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
