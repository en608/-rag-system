"""向量化服务：使用本地 SentenceTransformer 模型。"""

import asyncio
import os
from functools import lru_cache

from sentence_transformers import SentenceTransformer

# 中文语义模型，768 维，首次运行会自动下载
_MODEL_NAME = "shibing624/text2vec-base-chinese"

# 使用 HuggingFace 镜像
os.environ.setdefault("HF_ENDPOINT", "https://hf-mirror.com")


@lru_cache(maxsize=1)
def _get_model() -> SentenceTransformer:
    """单例加载模型，避免重复初始化。"""
    return SentenceTransformer(_MODEL_NAME)


class EmbeddingService:
    """本地 Embedding 服务，无需外部 API。"""

    def __init__(self) -> None:
        self._model = _get_model()

    async def embed_texts(self, texts: list[str]) -> list[list[float]]:
        """批量将文本转为向量列表。"""
        if not texts:
            return []
        loop = asyncio.get_event_loop()
        embeddings = await loop.run_in_executor(
            None, lambda: self._model.encode(texts, normalize_embeddings=True)
        )
        return [vec.tolist() for vec in embeddings]

    async def embed_query(self, query: str) -> list[float]:
        """将用户问题转为查询向量。"""
        loop = asyncio.get_event_loop()
        embedding = await loop.run_in_executor(
            None, lambda: self._model.encode([query], normalize_embeddings=True)
        )
        return embedding[0].tolist()
