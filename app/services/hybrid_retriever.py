"""混合检索服务：结合向量检索和BM25关键词检索。"""

import asyncio
import logging
import re
from collections import Counter
from math import log

from sqlalchemy import select, or_, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.document_chunk import DocumentChunk
from app.services.embedding_service import EmbeddingService

logger = logging.getLogger(__name__)


class BM25Retriever:
    """BM25关键词检索器。"""

    def __init__(self, k1: float = 1.5, b: float = 0.75):
        self.k1 = k1
        self.b = b

    def _tokenize(self, text: str) -> list[str]:
        """简单分词：按空格和标点分割，转小写。"""
        # 支持中英文分词
        text = text.lower()
        # 英文按空格分词，中文按字符分词
        tokens = re.findall(r'[一-鿿]|[a-zA-Z0-9]+', text)
        return tokens

    def _compute_idf(self, doc_count: int, term_freq: int) -> float:
        """计算IDF（逆文档频率）。"""
        return log((doc_count - term_freq + 0.5) / (term_freq + 0.5) + 1)

    def score_documents(
        self,
        query: str,
        documents: list[dict],
    ) -> list[dict]:
        """
        计算查询与文档的BM25分数。

        Args:
            query: 查询文本
            documents: 文档列表，每个文档包含 'content' 字段

        Returns:
            带有bm25_score的文档列表
        """
        query_tokens = self._tokenize(query)
        doc_count = len(documents)

        if doc_count == 0:
            return []

        # 计算每个文档的平均长度
        doc_lengths = [len(self._tokenize(doc["content"])) for doc in documents]
        avg_dl = sum(doc_lengths) / doc_count if doc_count > 0 else 1

        # 计算每个term的文档频率
        df = Counter()
        for doc in documents:
            doc_tokens = set(self._tokenize(doc["content"]))
            for token in query_tokens:
                if token in doc_tokens:
                    df[token] += 1

        # 计算每个文档的BM25分数
        scored_docs = []
        for i, doc in enumerate(documents):
            doc_tokens = self._tokenize(doc["content"])
            doc_token_counts = Counter(doc_tokens)
            doc_len = doc_lengths[i]

            score = 0.0
            for token in query_tokens:
                if token not in doc_token_counts:
                    continue

                tf = doc_token_counts[token]
                idf = self._compute_idf(doc_count, df.get(token, 0))

                # BM25公式
                numerator = tf * (self.k1 + 1)
                denominator = tf + self.k1 * (1 - self.b + self.b * doc_len / avg_dl)
                score += idf * (numerator / denominator)

            doc_with_score = doc.copy()
            doc_with_score["bm25_score"] = score
            scored_docs.append(doc_with_score)

        return scored_docs


class HybridRetriever:
    """混合检索器：结合向量检索和BM25检索。"""

    def __init__(self):
        self.embedding_service = EmbeddingService()
        self.bm25_retriever = BM25Retriever()

    async def retrieve(
        self,
        db: AsyncSession,
        query: str,
        tenant_id: str,
        user_id: int | None = None,
        top_k: int = 5,
        vector_weight: float = 0.7,
        bm25_weight: float = 0.3,
    ) -> list[dict]:
        """
        混合检索：向量检索 + BM25检索，然后融合排序。

        Args:
            db: 数据库会话
            query: 查询文本
            tenant_id: 租户ID
            user_id: 用户ID（可选）
            top_k: 返回Top-K结果
            vector_weight: 向量检索权重
            bm25_weight: BM25检索权重

        Returns:
            混合排序后的文档列表
        """
        # 第一阶段：向量检索召回Top-20
        query_vector = await self.embedding_service.embed_query(query)

        stmt = (
            select(DocumentChunk)
            .where(DocumentChunk.tenant_id == tenant_id)
        )

        if user_id is not None:
            from app.models.document import Document
            stmt = stmt.join(Document).where(
                Document.user_id == user_id,
                Document.tenant_id == tenant_id,
            )

        stmt = (
            stmt.order_by(DocumentChunk.embedding.cosine_distance(query_vector))
            .limit(20)
        )

        result = await db.execute(stmt)
        chunks = result.scalars().all()

        if not chunks:
            return []

        # 转换为dict列表
        docs = [
            {
                "chunk_id": chunk.id,
                "document_id": chunk.document_id,
                "content": chunk.content,
                "chunk_index": chunk.chunk_index,
            }
            for chunk in chunks
        ]

        # 第二阶段：BM25评分
        docs_with_bm25 = self.bm25_retriever.score_documents(query, docs)

        # 第三阶段：归一化分数并融合
        # 向量检索分数（基于排名，越靠前分数越高）
        for i, doc in enumerate(docs_with_bm25):
            doc["vector_score"] = 1.0 / (i + 1)  # 排名倒数作为分数

        # 归一化向量分数
        max_vector_score = max(d["vector_score"] for d in docs_with_bm25)
        min_vector_score = min(d["vector_score"] for d in docs_with_bm25)
        vector_range = max_vector_score - min_vector_score if max_vector_score != min_vector_score else 1

        # 归一化BM25分数
        max_bm25_score = max(d["bm25_score"] for d in docs_with_bm25) if docs_with_bm25 else 1
        min_bm25_score = min(d["bm25_score"] for d in docs_with_bm25) if docs_with_bm25 else 0
        bm25_range = max_bm25_score - min_bm25_score if max_bm25_score != min_bm25_score else 1

        # 计算混合分数
        for doc in docs_with_bm25:
            normalized_vector = (doc["vector_score"] - min_vector_score) / vector_range
            normalized_bm25 = (doc["bm25_score"] - min_bm25_score) / bm25_range

            doc["hybrid_score"] = (
                vector_weight * normalized_vector +
                bm25_weight * normalized_bm25
            )

        # 按混合分数排序
        docs_sorted = sorted(docs_with_bm25, key=lambda x: x["hybrid_score"], reverse=True)

        return docs_sorted[:top_k]
