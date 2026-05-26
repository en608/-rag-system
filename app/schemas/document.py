"""文档相关 API 的请求/响应模型。"""

from datetime import datetime

from pydantic import BaseModel, Field


class DocumentUploadResponse(BaseModel):
    """文档上传成功后的响应。"""

    document_id: int
    title: str
    source_type: str
    chunk_count: int
    message: str = "文档处理完成，已向量化入库"


class DocumentInfo(BaseModel):
    """文档简要信息。"""

    id: int
    title: str
    source_type: str
    original_filename: str | None
    created_at: datetime

    model_config = {"from_attributes": True}


class DocumentUploadForm(BaseModel):
    """上传时的可选表单字段（通过 Form 传入）。"""

    user_id: int = Field(..., description="关联用户 ID")
    title: str | None = Field(None, description="文档标题，默认使用文件名")


class DocumentListItem(BaseModel):
    """文档列表项。"""

    document_id: int
    title: str
    source_type: str
    original_filename: str | None
    chunk_count: int
    created_at: str | None
