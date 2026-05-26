"""Rerank服务：使用Cross-Encoder对检索结果重排序，支持异步推理。"""

import asyncio
import logging
import time
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass
from functools import lru_cache
from queue import Queue
from threading import Thread

from sentence_transformers import CrossEncoder

from app.core.config import get_settings

logger = logging.getLogger(__name__)


@dataclass
class RerankRequest:
    """Rerank请求"""
    query: str
    documents: list[dict]
    top_k: int
    future: asyncio.Future


class RerankWorker:
    """Rerank异步工作线程"""

    def __init__(self, model: CrossEncoder, request_queue: Queue):
        self.model = model
        self.queue = request_queue
        self._running = True

    def start(self):
        """启动工作线程"""
        thread = Thread(target=self._process_loop, daemon=True)
        thread.start()

    def _process_loop(self):
        """处理循环"""
        while self._running:
            try:
                request = self.queue.get(timeout=1)
                if request is None:
                    break

                self._process_request(request)
            except Exception:
                continue

    def _process_request(self, request: RerankRequest):
        """处理单个rerank请求"""
        try:
            start_time = time.time()

            # 构建query-document对
            pairs = [[request.query, doc["content"]] for doc in request.documents]

            # 计算相关性分数
            scores = self.model.predict(pairs, batch_size=32)

            # 将分数添加到文档中
            for doc, score in zip(request.documents, scores):
                doc["rerank_score"] = float(score)

            # 按rerank分数降序排序
            reranked = sorted(
                request.documents,
                key=lambda x: x["rerank_score"],
                reverse=True,
            )[:request.top_k]

            elapsed = time.time() - start_time
            logger.debug(f"Rerank completed in {elapsed:.3f}s")

            # 设置结果
            if not request.future.done():
                request.future.get_loop().call_soon_threadsafe(
                    request.future.set_result, reranked
                )
        except Exception as e:
            logger.error(f"Rerank error: {e}")
            if not request.future.done():
                request.future.get_loop().call_soon_threadsafe(
                    request.future.set_exception, e
                )


class RerankService:
    """Rerank服务，支持同步和异步模式。"""

    def __init__(self, async_mode: bool = True):
        settings = get_settings()
        self.async_mode = async_mode and settings.rerank_async_enabled
        self._model = None

        # 尝试加载模型
        try:
            logger.info(f"Loading rerank model: {settings.rerank_model}")
            self._model = CrossEncoder(
                settings.rerank_model,
                max_length=settings.rerank_max_length,
            )
        except Exception as e:
            logger.warning(f"Failed to load rerank model: {e}. Rerank will be disabled.")
            return

        # 异步模式初始化
        if self.async_mode and self._model is not None:
            self._request_queue = Queue(maxsize=settings.rerank_queue_size)
            self._workers = []
            self._start_workers(settings.rerank_workers)

    def _start_workers(self, num_workers: int):
        """启动工作线程"""
        for i in range(num_workers):
            worker = RerankWorker(self._model, self._request_queue)
            worker.start()
            self._workers.append(worker)
        logger.info(f"Started {num_workers} rerank workers")

    async def rerank(
        self,
        query: str,
        documents: list[dict],
        top_k: int = 5,
    ) -> list[dict]:
        """
        对检索结果进行重排序。

        Args:
            query: 用户查询
            documents: 检索到的文档列表
            top_k: 返回Top-K个结果

        Returns:
            重排序后的文档列表
        """
        if not documents:
            return []

        # 如果模型未加载或文档数量不超过top_k，直接返回
        if self._model is None or len(documents) <= top_k:
            return documents[:top_k]

        if self.async_mode:
            return await self._rerank_async(query, documents, top_k)
        else:
            return await self._rerank_sync(query, documents, top_k)

    async def _rerank_async(
        self,
        query: str,
        documents: list[dict],
        top_k: int,
    ) -> list[dict]:
        """异步rerank"""
        # 创建Future
        loop = asyncio.get_event_loop()
        future = loop.create_future()

        # 创建请求
        request = RerankRequest(
            query=query,
            documents=documents,
            top_k=top_k,
            future=future,
        )

        # 放入队列
        self._request_queue.put(request)

        # 等待结果
        try:
            result = await asyncio.wait_for(future, timeout=30)
            return result
        except asyncio.TimeoutError:
            logger.warning("Rerank timeout, falling back to sync mode")
            return await self._rerank_sync(query, documents, top_k)

    async def _rerank_sync(
        self,
        query: str,
        documents: list[dict],
        top_k: int,
    ) -> list[dict]:
        """同步rerank（在线程池中执行）"""
        loop = asyncio.get_event_loop()

        # 在线程池中执行
        with ThreadPoolExecutor(max_workers=1) as executor:
            result = await loop.run_in_executor(
                executor,
                self._rerank_blocking,
                query,
                documents,
                top_k,
            )
        return result

    def _rerank_blocking(
        self,
        query: str,
        documents: list[dict],
        top_k: int,
    ) -> list[dict]:
        """阻塞式rerank"""
        start_time = time.time()

        # 构建query-document对
        pairs = [[query, doc["content"]] for doc in documents]

        # 计算相关性分数
        scores = self._model.predict(pairs, batch_size=32)

        # 将分数添加到文档中
        for doc, score in zip(documents, scores):
            doc["rerank_score"] = float(score)

        # 按rerank分数降序排序
        reranked = sorted(
            documents,
            key=lambda x: x["rerank_score"],
            reverse=True,
        )[:top_k]

        elapsed = time.time() - start_time
        logger.debug(f"Rerank completed in {elapsed:.3f}s")

        return reranked

    def __del__(self):
        """清理资源"""
        if hasattr(self, '_request_queue'):
            # 停止工作线程
            for _ in self._workers:
                self._request_queue.put(None)
