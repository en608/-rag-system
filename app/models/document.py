"""文档表：存储原始文档元信息。"""

from sqlalchemy import ForeignKey, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, TenantMixin, TimestampMixin


class Document(Base, TenantMixin, TimestampMixin):
    """文档元数据：标题、来源类型、原始文件名等。"""

    __tablename__ = "documents"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    title: Mapped[str] = mapped_column(String(512), nullable=False)
    # 来源类型：txt / pdf
    source_type: Mapped[str] = mapped_column(String(32), nullable=False)
    original_filename: Mapped[str | None] = mapped_column(String(512), nullable=True)
    # 可选：保存解析后的全文摘要或备注
    description: Mapped[str | None] = mapped_column(Text, nullable=True)

    user: Mapped["User"] = relationship("User", back_populates="documents")
    chunks: Mapped[list["DocumentChunk"]] = relationship(
        "DocumentChunk",
        back_populates="document",
        cascade="all, delete-orphan",
    )
