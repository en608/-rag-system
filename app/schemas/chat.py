"""问答 API 的请求/响应模型。"""

from pydantic import BaseModel, Field


class ChatMessage(BaseModel):
    """对话历史中的单条消息。"""
    role: str = Field(..., description="消息角色：user 或 bot")
    content: str = Field(..., description="消息内容")


class ChatRequest(BaseModel):
    """流式问答请求体。"""

    question: str = Field(..., min_length=1, description="用户问题")
    chat_history: list[ChatMessage] = Field(
        default_factory=list,
        description="对话历史，用于多轮对话上下文",
    )


class ChatStreamChunk(BaseModel):
    """SSE 流中单条数据（可选结构化，当前直接返回纯文本 token）。"""

    content: str
