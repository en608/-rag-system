"""文本切分工具：封装 LangChain RecursiveCharacterTextSplitter。"""

from langchain_text_splitters import RecursiveCharacterTextSplitter

from app.core.config import get_settings


def split_text(text: str) -> list[str]:
    """
    使用递归字符切分策略将长文本拆分为多个块。
    默认 chunk_size=500, chunk_overlap=50，可在配置中调整。
    """
    settings = get_settings()
    splitter = RecursiveCharacterTextSplitter(
        chunk_size=settings.chunk_size,
        chunk_overlap=settings.chunk_overlap,
        length_function=len,
        is_separator_regex=False,
    )
    return splitter.split_text(text)
