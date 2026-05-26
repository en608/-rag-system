"""用户表：多租户下的用户实体。"""

from sqlalchemy import String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, TenantMixin, TimestampMixin


class User(Base, TenantMixin, TimestampMixin):
    """用户模型，支持密码认证。"""

    __tablename__ = "users"
    __table_args__ = (
        UniqueConstraint("tenant_id", "username", name="uq_users_tenant_username"),
    )

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    username: Mapped[str] = mapped_column(String(128), nullable=False)
    password_hash: Mapped[str] = mapped_column(String(256), nullable=False)
    email: Mapped[str | None] = mapped_column(String(256), nullable=True)

    documents: Mapped[list["Document"]] = relationship(
        "Document",
        back_populates="user",
        cascade="all, delete-orphan",
    )
