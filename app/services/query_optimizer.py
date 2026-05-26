"""查询优化服务：查询改写、查询扩展、HyDE。"""

import asyncio
import logging
from functools import lru_cache

from langchain_core.output_parsers import StrOutputParser
from langchain_core.prompts import ChatPromptTemplate
from langchain_openai import ChatOpenAI

from app.core.config import get_settings

logger = logging.getLogger(__name__)


class QueryOptimizer:
    """查询优化器：提升检索效果。"""

    def __init__(self):
        self.settings = get_settings()
        self._llm = None

    @property
    def llm(self):
        """懒加载LLM。"""
        if self._llm is None:
            self._llm = ChatOpenAI(
                model=self.settings.openai_llm_model,
                api_key=self.settings.openai_api_key,
                base_url=self.settings.openai_base_url,
                streaming=False,
                temperature=0,
            )
        return self._llm

    async def rewrite_query(self, query: str, chat_history: list[dict] | None = None) -> str:
        """
        查询改写：将用户查询改写为更适合检索的形式。

        Args:
            query: 原始查询
            chat_history: 对话历史（可选）

        Returns:
            改写后的查询
        """
        # 如果查询很短，不需要改写
        if len(query) < 10:
            return query

        prompt = ChatPromptTemplate.from_messages([
            ("system", """你是一个查询改写专家。你的任务是将用户查询改写为更适合信息检索的形式。

改写规则：
1. 保留原始查询的核心意图
2. 添加可能的同义词或相关术语
3. 使查询更加明确和具体
4. 如果有对话历史，结合上下文改写

只返回改写后的查询，不要添加任何解释。"""),
            ("human", """原始查询：{query}

{history}

改写后的查询："""),
        ])

        # 构建历史上下文
        history_text = ""
        if chat_history:
            history_text = "对话历史：\n"
            for msg in chat_history[-4:]:  # 最近2轮
                role = "用户" if msg.get("role") == "user" else "助手"
                history_text += f"{role}: {msg.get('content', '')}\n"

        chain = prompt | self.llm | StrOutputParser()

        try:
            rewritten = await chain.ainvoke({
                "query": query,
                "history": history_text,
            })
            rewritten = rewritten.strip()

            # 如果改写结果为空或太长，返回原始查询
            if not rewritten or len(rewritten) > len(query) * 3:
                return query

            logger.info(f"Query rewrite: '{query}' -> '{rewritten}'")
            return rewritten
        except Exception as e:
            logger.warning(f"Query rewrite failed: {e}")
            return query

    async def expand_query(self, query: str) -> list[str]:
        """
        查询扩展：生成多个相关查询，用于扩大召回。

        Args:
            query: 原始查询

        Returns:
            扩展查询列表（包含原始查询）
        """
        prompt = ChatPromptTemplate.from_messages([
            ("system", """你是一个查询扩展专家。给定一个用户查询，生成3个相关的查询，用于扩大信息检索的召回率。

要求：
1. 每个查询应该从不同角度表达相同的信息需求
2. 使用不同的词汇和表达方式
3. 每行一个查询
4. 只返回查询，不要添加编号或其他内容"""),
            ("human", "原始查询：{query}\n\n相关查询："),
        ])

        chain = prompt | self.llm | StrOutputParser()

        try:
            result = await chain.ainvoke({"query": query})
            expanded = [q.strip() for q in result.strip().split("\n") if q.strip()]

            # 包含原始查询
            all_queries = [query] + expanded[:3]

            logger.info(f"Query expansion: '{query}' -> {all_queries}")
            return all_queries
        except Exception as e:
            logger.warning(f"Query expansion failed: {e}")
            return [query]

    async def generate_hypothetical_answer(self, query: str) -> str:
        """
        HyDE（Hypothetical Document Embedding）：生成假设性答案。

        原理：生成一个假设的答案，用这个答案去检索，往往比直接用问题检索效果更好。

        Args:
            query: 用户查询

        Returns:
            假设性答案
        """
        prompt = ChatPromptTemplate.from_messages([
            ("system", """你是一个知识库问答助手。根据用户的问题，生成一个简短的、可能的答案。
这个答案不需要完全准确，但应该包含与问题相关的关键词和概念。
答案长度控制在100字以内。"""),
            ("human", "问题：{query}\n\n可能的答案："),
        ])

        chain = prompt | self.llm | StrOutputParser()

        try:
            hypothetical = await chain.ainvoke({"query": query})
            hypothetical = hypothetical.strip()

            logger.info(f"HyDE for '{query}': '{hypothetical[:50]}...'")
            return hypothetical
        except Exception as e:
            logger.warning(f"HyDE failed: {e}")
            return query

    async def optimize_query(
        self,
        query: str,
        chat_history: list[dict] | None = None,
        use_rewrite: bool = True,
        use_hyde: bool = False,
    ) -> tuple[str, str]:
        """
        综合查询优化。

        Args:
            query: 原始查询
            chat_history: 对话历史
            use_rewrite: 是否使用查询改写
            use_hyde: 是否使用HyDE

        Returns:
            (优化后的查询, HyDE答案) 元组
        """
        optimized_query = query
        hyde_answer = ""

        # 并行执行查询改写和HyDE
        tasks = []

        if use_rewrite:
            tasks.append(self.rewrite_query(query, chat_history))
        else:
            tasks.append(asyncio.coroutine(lambda: query)())

        if use_hyde:
            tasks.append(self.generate_hypothetical_answer(query))
        else:
            tasks.append(asyncio.coroutine(lambda: "")())

        results = await asyncio.gather(*tasks, return_exceptions=True)

        if not isinstance(results[0], Exception):
            optimized_query = results[0]
        if len(results) > 1 and not isinstance(results[1], Exception):
            hyde_answer = results[1]

        return optimized_query, hyde_answer
