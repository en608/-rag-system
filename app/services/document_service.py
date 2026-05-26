"""文档处理服务：解析、切分、向量化并写入数据库。"""

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.document import Document
from app.models.document_chunk import DocumentChunk
from app.models.user import User
from app.services.embedding_service import EmbeddingService
from app.utils.file_parser import parse_upload_file
from app.utils.text_splitter import split_text


class DocumentService:
    """文档上传与入库的完整流水线。"""

    def __init__(self, db: AsyncSession, tenant_id: str) -> None:
        self.db = db
        self.tenant_id = tenant_id
        self.embedding_service = EmbeddingService()

    async def _ensure_user_exists(self, user_id: int) -> User:
        """校验用户属于当前租户，防止跨租户写入。"""
        result = await self.db.execute(
            select(User).where(
                User.id == user_id,
                User.tenant_id == self.tenant_id,
            )
        )
        user = result.scalar_one_or_none()
        if user is None:
            raise ValueError(f"用户 id={user_id} 不存在或不属于当前租户")
        return user

    async def upload_and_index(
        self,
        user_id: int,
        filename: str,
        file_content: bytes,
        title: str | None = None,
    ) -> tuple[Document, int]:
        """
        端到端文档处理：
        1. 解析文件为纯文本
        2. RecursiveCharacterTextSplitter 切分
        3. 批量 Embedding
        4. 写入 documents 与 document_chunks 表
        """
        await self._ensure_user_exists(user_id)

        source_type, text = parse_upload_file(filename, file_content)
        if not text:
            raise ValueError("文档内容为空，无法处理")

        chunks_text = split_text(text)
        if not chunks_text:
            raise ValueError("切分后无有效文本块")

        # 批量向量化
        embeddings = await self.embedding_service.embed_texts(chunks_text)

        doc_title = title or filename
        document = Document(
            tenant_id=self.tenant_id,
            user_id=user_id,
            title=doc_title,
            source_type=source_type,
            original_filename=filename,
        )
        self.db.add(document)
        await self.db.flush()  # 获取 document.id

        for idx, (chunk_content, embedding) in enumerate(
            zip(chunks_text, embeddings, strict=True)
        ):
            chunk = DocumentChunk(
                tenant_id=self.tenant_id,
                document_id=document.id,
                chunk_index=idx,
                content=chunk_content,
                embedding=embedding,  # pgvector 直接接受 list[float]
            )
            self.db.add(chunk)

        await self.db.commit()
        await self.db.refresh(document)
        return document, len(chunks_text)
