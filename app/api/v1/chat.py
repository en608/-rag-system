"""流式问答 API。"""

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import StreamingResponse
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.core.database import get_db
from app.core.deps import get_current_user_id, get_tenant_id
from app.core.limiter import limiter
from app.schemas.chat import ChatRequest
from app.services.rag_service import RAGService

router = APIRouter(prefix="/chat", tags=["chat"])
settings = get_settings()


@router.post(
    "/retrieve",
    summary="检索 Top-K 相关片段",
)
@limiter.limit(settings.rate_limit_chat)
async def retrieve_chunks(
    request: Request,
    body: ChatRequest,
    user_id: int = Depends(get_current_user_id),
    tenant_id: str = Depends(get_tenant_id),
    db: AsyncSession = Depends(get_db),
):
    """
    仅做向量检索，返回 Top-5 最相关的文档片段，不调用 LLM。
    用于前端展示检索来源。
    """
    rag = RAGService(db=db, tenant_id=tenant_id)
    try:
        chunks = await rag._retrieve_chunks(body.question, user_id=user_id)
    except ValueError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc

    return [
        {
            "chunk_id": chunk.id,
            "document_id": chunk.document_id,
            "chunk_index": chunk.chunk_index,
            "content": chunk.content,
        }
        for chunk in chunks
    ]


@router.post(
    "/stream",
    summary="RAG 流式问答",
    response_class=StreamingResponse,
)
@limiter.limit(settings.rate_limit_chat)
async def chat_stream(
    request: Request,
    body: ChatRequest,
    user_id: int = Depends(get_current_user_id),
    tenant_id: str = Depends(get_tenant_id),
    db: AsyncSession = Depends(get_db),
) -> StreamingResponse:
    """
    向量检索 Top-5（余弦相似度）→ 拼接上下文 → LLM 流式生成。
    响应为 text/event-stream (SSE) 格式。
    支持多轮对话，传入 chat_history 以提供上下文。
    """
    rag = RAGService(db=db, tenant_id=tenant_id)

    # 将 ChatMessage 对象转换为字典列表
    chat_history = [{"role": msg.role, "content": msg.content} for msg in body.chat_history]

    async def event_generator():
        """将 LLM token 包装为 SSE data 行。"""
        try:
            async for token in rag.stream_answer(
                question=body.question,
                user_id=user_id,
                chat_history=chat_history,
            ):
                # SSE 规范：每条消息以 data: 开头，双换行结束
                yield f"data: {token}\n\n"
        except Exception as exc:
            yield f"data: [错误] {exc}\n\n"
        yield "data: [DONE]\n\n"

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )
