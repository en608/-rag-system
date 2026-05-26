"""文档上传 API。"""

from fastapi import APIRouter, Depends, File, Form, HTTPException, Request, UploadFile, status
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.core.database import get_db
from app.core.deps import get_current_user_id, get_tenant_id
from app.core.limiter import limiter
from app.models.document import Document
from app.models.document_chunk import DocumentChunk
from app.schemas.document import DocumentListItem, DocumentUploadResponse
from app.services.document_service import DocumentService

router = APIRouter(prefix="/documents", tags=["documents"])
settings = get_settings()


@router.post(
    "/upload",
    response_model=DocumentUploadResponse,
    summary="上传文档并向量化入库",
)
@limiter.limit(settings.rate_limit_upload)
async def upload_document(
    request: Request,
    file: UploadFile = File(..., description="支持 .txt / .pdf"),
    title: str | None = Form(None, description="文档标题，默认使用文件名"),
    user_id: int = Depends(get_current_user_id),
    tenant_id: str = Depends(get_tenant_id),
    db: AsyncSession = Depends(get_db),
) -> DocumentUploadResponse:
    """
    文档处理管道入口：
    解析 → 切分 (500/50) → Embedding → 写入 PostgreSQL。
    请求头必须携带 X-Tenant-ID。
    """
    if not file.filename:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="文件名不能为空",
        )

    content = await file.read()
    if not content:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="文件内容为空",
        )

    service = DocumentService(db=db, tenant_id=tenant_id)
    try:
        document, chunk_count = await service.upload_and_index(
            user_id=user_id,
            filename=file.filename,
            file_content=content,
            title=title,
        )
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(exc),
        ) from exc

    return DocumentUploadResponse(
        document_id=document.id,
        title=document.title,
        source_type=document.source_type,
        chunk_count=chunk_count,
    )


@router.get(
    "/list",
    summary="获取文档列表",
)
@limiter.limit(settings.rate_limit_default)
async def list_documents(
    request: Request,
    user_id: int = Depends(get_current_user_id),
    tenant_id: str = Depends(get_tenant_id),
    db: AsyncSession = Depends(get_db),
):
    """获取当前用户上传的文档及其片段数量。"""
    stmt = (
        select(
            Document.id,
            Document.title,
            Document.source_type,
            Document.original_filename,
            Document.created_at,
            func.count(DocumentChunk.id).label("chunk_count"),
        )
        .outerjoin(DocumentChunk, Document.id == DocumentChunk.document_id)
        .where(Document.tenant_id == tenant_id, Document.user_id == user_id)
        .group_by(Document.id)
        .order_by(Document.created_at.desc())
    )
    result = await db.execute(stmt)
    rows = result.all()

    return [
        {
            "document_id": row.id,
            "title": row.title,
            "source_type": row.source_type,
            "original_filename": row.original_filename,
            "chunk_count": row.chunk_count,
            "created_at": row.created_at.isoformat() if row.created_at else None,
        }
        for row in rows
    ]


@router.delete(
    "/{document_id}",
    summary="删除文档",
)
@limiter.limit(settings.rate_limit_default)
async def delete_document(
    request: Request,
    document_id: int,
    user_id: int = Depends(get_current_user_id),
    tenant_id: str = Depends(get_tenant_id),
    db: AsyncSession = Depends(get_db),
):
    """
    删除指定文档及其所有关联的 chunks。
    只能删除自己上传的文档。
    """
    # 查找文档
    stmt = select(Document).where(
        Document.id == document_id,
        Document.tenant_id == tenant_id,
        Document.user_id == user_id,
    )
    result = await db.execute(stmt)
    document = result.scalar_one_or_none()

    if document is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="文档不存在或无权删除",
        )

    # 删除文档（级联删除 chunks）
    await db.delete(document)
    await db.commit()

    return {"message": "文档删除成功", "document_id": document_id}


@router.get(
    "/{document_id}/preview",
    summary="预览文档内容",
)
@limiter.limit(settings.rate_limit_default)
async def preview_document(
    request: Request,
    document_id: int,
    user_id: int = Depends(get_current_user_id),
    tenant_id: str = Depends(get_tenant_id),
    db: AsyncSession = Depends(get_db),
):
    """
    预览文档内容，返回前5个 chunk 的内容。
    """
    # 查找文档
    stmt = select(Document).where(
        Document.id == document_id,
        Document.tenant_id == tenant_id,
        Document.user_id == user_id,
    )
    result = await db.execute(stmt)
    document = result.scalar_one_or_none()

    if document is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="文档不存在或无权访问",
        )

    # 获取前5个 chunk
    chunks_stmt = (
        select(DocumentChunk)
        .where(
            DocumentChunk.document_id == document_id,
            DocumentChunk.tenant_id == tenant_id,
        )
        .order_by(DocumentChunk.chunk_index)
        .limit(5)
    )
    chunks_result = await db.execute(chunks_stmt)
    chunks = chunks_result.scalars().all()

    return {
        "document_id": document.id,
        "title": document.title,
        "source_type": document.source_type,
        "chunks": [
            {
                "chunk_index": chunk.chunk_index,
                "content": chunk.content,
            }
            for chunk in chunks
        ],
    }
