"""文档块表：切分后的文本片段及向量 embedding。"""

from pgvector.sqlalchemy import Vector
from sqlalchemy import ForeignKey, Integer, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, TenantMixin, TimestampMixin


class DocumentChunk(Base, TenantMixin, TimestampMixin):
    """
    文档块 + 向量字段。
    embedding 使用 pgvector 原生 vector 类型存储，支持数据库级向量检索。
    """

    __tablename__ = "document_chunks"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    document_id: Mapped[int] = mapped_column(
        ForeignKey("documents.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    # 块在文档内的顺序索引
    chunk_index: Mapped[int] = mapped_column(Integer, nullable=False)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    # 向量存储为 pgvector 原生类型
    embedding = mapped_column(Vector(768), nullable=False)

    document: Mapped["Document"] = relationship("Document", back_populates="chunks")
