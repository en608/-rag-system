"""RAG 检索与生成服务：向量召回 + Rerank + LCEL 链 + 流式输出。"""

from collections.abc import AsyncIterator

from langchain_core.output_parsers import StrOutputParser
from langchain_core.prompts import ChatPromptTemplate
from langchain_openai import ChatOpenAI
from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.models.document import Document
from app.models.document_chunk import DocumentChunk
from app.services.embedding_service import EmbeddingService
from app.services.rerank_service import RerankService


class RAGService:
    """检索增强生成核心逻辑。"""

    def __init__(self, db: AsyncSession, tenant_id: str) -> None:
        self.db = db
        self.tenant_id = tenant_id
        self.settings = get_settings()
        self.embedding_service = EmbeddingService()
        self.rerank_service = RerankService()

    async def _retrieve_chunks(
        self,
        query: str,
        user_id: int | None = None,
        use_rerank: bool = True,
    ) -> list[DocumentChunk]:
        """
        向量相似度检索 + Rerank重排序。
        第一阶段：向量检索召回Top-20
        第二阶段：Rerank重排序返回Top-5
        可选 user_id 限定只检索该用户上传的文档。
        """
        query_vector = await self.embedding_service.embed_query(query)

        # 第一阶段：向量检索召回更多候选（Top-20）
        recall_top_k = 20 if use_rerank else self.settings.retrieval_top_k

        # 使用 pgvector 的余弦距离运算符 <=> 进行数据库级向量检索
        if user_id is not None:
            stmt = (
                select(DocumentChunk)
                .join(Document)
                .where(
                    DocumentChunk.tenant_id == self.tenant_id,
                    Document.user_id == user_id,
                    Document.tenant_id == self.tenant_id,
                )
                .order_by(DocumentChunk.embedding.cosine_distance(query_vector))
                .limit(recall_top_k)
            )
        else:
            stmt = (
                select(DocumentChunk)
                .where(DocumentChunk.tenant_id == self.tenant_id)
                .order_by(DocumentChunk.embedding.cosine_distance(query_vector))
                .limit(recall_top_k)
            )

        result = await self.db.execute(stmt)
        chunks = list(result.scalars().all())

        # 第二阶段：Rerank重排序
        if use_rerank and len(chunks) > self.settings.retrieval_top_k:
            # 将chunks转换为dict列表
            chunks_dict = [
                {
                    "chunk_id": chunk.id,
                    "document_id": chunk.document_id,
                    "content": chunk.content,
                    "chunk_index": chunk.chunk_index,
                    "original_chunk": chunk,
                }
                for chunk in chunks
            ]

            # Rerank
            reranked = await self.rerank_service.rerank(
                query=query,
                documents=chunks_dict,
                top_k=self.settings.retrieval_top_k,
            )

            # 返回原始chunk对象
            return [doc["original_chunk"] for doc in reranked]

        return chunks[:self.settings.retrieval_top_k]

    def _build_context(self, chunks: list[DocumentChunk]) -> str:
        """将召回的文档块拼接为上下文文本。"""
        if not chunks:
            return "（未检索到相关文档片段）"
        parts = []
        for i, chunk in enumerate(chunks, start=1):
            parts.append(f"[片段{i}]\n{chunk.content}")
        return "\n\n".join(parts)

    def _build_chain(self, chat_history: list[dict] | None = None):
        """
        构建 LCEL 链：Prompt | LLM | StrOutputParser。
        使用基础 RAG 提示模板，将 context 与 question 注入。
        支持多轮对话，将历史对话加入 Prompt。
        """
        # 构建系统提示
        system_prompt = (
            "你是一个基于给定文档片段回答问题的助手。"
            "请仅根据提供的上下文作答；若上下文中没有相关信息，请明确说明无法从文档中找到答案。"
            "回答请使用中文，简洁准确。"
            "如果用户之前问过相关问题，你可以参考之前的对话内容来提供更连贯的回答。"
        )

        # 构建完整的消息列表
        messages = [("system", system_prompt)]

        # 添加对话历史（如果有的话）
        if chat_history:
            for msg in chat_history[-6:]:  # 只保留最近3轮对话（6条消息）
                role = msg.get("role", "user")
                content = msg.get("content", "")
                # 转义花括号，避免被 LangChain 模板解析器误解
                escaped_content = content.replace("{", "{{").replace("}", "}}")
                if role == "user":
                    messages.append(("human", escaped_content))
                elif role == "bot":
                    messages.append(("ai", escaped_content))

        # 添加当前问题（保留模板变量）
        messages.append(
            (
                "human",
                "上下文：\n{context}\n\n问题：{question}\n\n请回答：",
            )
        )

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
        流式问答：向量检索 → 拼接上下文 → LCEL 流式生成。
        逐 token yield，供 SSE 接口消费。
        支持多轮对话，传入 chat_history 以提供上下文。
        """
        try:
            chunks = await self._retrieve_chunks(question, user_id=user_id, use_rerank=False)
            context = self._build_context(chunks)
            chain = self._build_chain(chat_history)

            async for token in chain.astream({"context": context, "question": question}):
                if token:
                    yield token
        except Exception as e:
            error_msg = str(e)
            # LLM 不可用时，返回基于检索的摘要
            if "model_not_found" in error_msg or "503" in error_msg or "无可用渠道" in error_msg:
                yield "**LLM 服务暂不可用**，以下为检索到的相关文档片段：\n\n"
                try:
                    chunks = await self._retrieve_chunks(question, user_id=user_id)
                    if chunks:
                        for i, chunk in enumerate(chunks, 1):
                            yield f"**[片段 {i}]**\n{chunk.content}\n\n"
                    else:
                        yield "未检索到相关文档片段。"
                except Exception:
                    yield "检索服务也出现错误，请检查配置。"
            elif "Internal Server Error" in error_msg or "500" in error_msg:
                yield f"[错误]API服务内部错误，请稍后重试。错误详情: {error_msg[:100]}"
            elif "401" in error_msg or "Unauthorized" in error_msg:
                yield "[错误]API密钥无效，请检查API Key配置。"
            elif "429" in error_msg or "rate limit" in error_msg.lower():
                yield "[错误]API调用频率超限，请稍后重试。"
            else:
                yield f"[错误]服务调用失败: {error_msg[:100]}"
