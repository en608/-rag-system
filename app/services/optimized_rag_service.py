"""优化后的RAG服务：整合混合检索、查询优化、Rerank、上下文压缩。"""

import logging
from collections.abc import AsyncIterator

from langchain_core.output_parsers import StrOutputParser
from langchain_core.prompts import ChatPromptTemplate
from langchain_openai import ChatOpenAI
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.services.embedding_service import EmbeddingService
from app.services.hybrid_retriever import HybridRetriever
from app.services.rerank_service import RerankService
from app.services.query_optimizer import QueryOptimizer
from app.services.context_compressor import ContextCompressor

logger = logging.getLogger(__name__)


class OptimizedRAGService:
    """优化后的RAG服务。"""

    def __init__(self, db: AsyncSession, tenant_id: str) -> None:
        self.db = db
        self.tenant_id = tenant_id
        self.settings = get_settings()

        # 初始化各个组件
        self.embedding_service = EmbeddingService()
        self.hybrid_retriever = HybridRetriever()
        self.rerank_service = RerankService()
        self.query_optimizer = QueryOptimizer()
        self.context_compressor = ContextCompressor()

    async def retrieve(
        self,
        query: str,
        user_id: int | None = None,
        use_hybrid: bool = True,
        use_rerank: bool = True,
        use_query_optimization: bool = True,
        use_context_compression: bool = True,
    ) -> list[dict]:
        """
        优化后的检索流程。

        Args:
            query: 用户查询
            user_id: 用户ID
            use_hybrid: 是否使用混合检索
            use_rerank: 是否使用Rerank
            use_query_optimization: 是否使用查询优化
            use_context_compression: 是否使用上下文压缩

        Returns:
            检索结果列表
        """
        # 第一步：查询优化
        optimized_query = query
        if use_query_optimization:
            optimized_query, _ = await self.query_optimizer.optimize_query(
                query=query,
                use_rewrite=True,
                use_hyde=False,  # HyDE可能增加延迟，可选开启
            )

        # 第二步：检索
        if use_hybrid:
            # 混合检索：向量 + BM25
            chunks = await self.hybrid_retriever.retrieve(
                db=self.db,
                query=optimized_query,
                tenant_id=self.tenant_id,
                user_id=user_id,
                top_k=20,  # 召回更多候选
            )
        else:
            # 纯向量检索
            from app.services.rag_service import RAGService
            basic_rag = RAGService(self.db, self.tenant_id)
            raw_chunks = await basic_rag._retrieve_chunks(
                optimized_query, user_id=user_id, use_rerank=False
            )
            chunks = [
                {
                    "chunk_id": c.id,
                    "document_id": c.document_id,
                    "content": c.content,
                    "chunk_index": c.chunk_index,
                    "hybrid_score": 1.0 / (i + 1),
                }
                for i, c in enumerate(raw_chunks)
            ]

        # 第三步：Rerank重排序
        if use_rerank and len(chunks) > self.settings.retrieval_top_k:
            chunks = await self.rerank_service.rerank(
                query=query,  # 使用原始查询进行rerank
                documents=chunks,
                top_k=self.settings.retrieval_top_k,
            )

        # 第四步：多样性重排序
        chunks = self.context_compressor.rerank_by_diversity(
            chunks, top_k=self.settings.retrieval_top_k
        )

        return chunks

    def _build_context(
        self,
        chunks: list[dict],
        use_compression: bool = True,
    ) -> str:
        """构建上下文。"""
        if not chunks:
            return "（未检索到相关文档片段）"

        if use_compression:
            return self.context_compressor.compress_context(
                chunks,
                max_tokens=2000,
                use_dedup=True,
                use_extraction=True,
            )

        parts = []
        for i, chunk in enumerate(chunks, 1):
            parts.append(f"[片段{i}]\n{chunk['content']}")
        return "\n\n".join(parts)

    def _build_chain(self, chat_history: list[dict] | None = None):
        """构建LLM链。"""
        system_prompt = (
            "你是一个基于给定文档片段回答问题的助手。"
            "请仅根据提供的上下文作答；若上下文中没有相关信息，"
            "请明确说明无法从文档中找到答案。"
            "回答请使用中文，简洁准确。"
        )

        messages = [("system", system_prompt)]

        if chat_history:
            for msg in chat_history[-6:]:
                role = msg.get("role", "user")
                content = msg.get("content", "")
                escaped_content = content.replace("{", "{{").replace("}", "}}")
                if role == "user":
                    messages.append(("human", escaped_content))
                elif role == "bot":
                    messages.append(("ai", escaped_content))

        messages.append(("human", "上下文：\n{context}\n\n问题：{question}\n\n请回答："))

        prompt = ChatPromptTemplate.from_messages(messages)
        llm = ChatOpenAI(
            model=self.settings.openai_llm_model,
            api_key=self.settings.openai_api_key,
            base_url=self.settings.openai_base_url,
            streaming=True,
        )
        return prompt | llm | StrOutputParser()

    async def stream_answer(
        self,
        question: str,
        user_id: int | None = None,
        chat_history: list[dict] | None = None,
    ) -> AsyncIterator[str]:
        """
        优化后的流式问答。

        Args:
            question: 用户问题
            user_id: 用户ID
            chat_history: 对话历史

        Yields:
            流式输出的token
        """
        try:
            # 检索
            chunks = await self.retrieve(
                query=question,
                user_id=user_id,
                use_hybrid=True,
                use_rerank=True,
                use_query_optimization=True,
                use_context_compression=True,
            )

            # 构建上下文
            context = self._build_context(chunks, use_compression=True)

            # 生成回答
            chain = self._build_chain(chat_history)
            async for token in chain.astream({"context": context, "question": question}):
                if token:
                    yield token

        except Exception as e:
            error_msg = str(e)
            logger.error(f"RAG error: {error_msg}")

            if "model_not_found" in error_msg or "503" in error_msg:
                yield "**LLM 服务暂不可用**，以下为检索到的相关文档片段：\n\n"
                try:
                    chunks = await self.retrieve(question, user_id=user_id)
                    for i, chunk in enumerate(chunks, 1):
                        yield f"**[片段 {i}]**\n{chunk['content']}\n\n"
                except Exception:
                    yield "检索服务也出现错误，请检查配置。"
            else:
                yield f"[错误] 服务调用失败: {error_msg[:100]}"
