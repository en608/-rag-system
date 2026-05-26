"""上下文压缩服务：去除冗余信息，保留关键内容。"""

import logging
import re
from difflib import SequenceMatcher

logger = logging.getLogger(__name__)


class ContextCompressor:
    """上下文压缩器：优化检索结果，去除冗余。"""

    def __init__(self, similarity_threshold: float = 0.8):
        """
        Args:
            similarity_threshold: 相似度阈值，超过此值认为是重复内容
        """
        self.similarity_threshold = similarity_threshold

    def _compute_similarity(self, text1: str, text2: str) -> float:
        """计算两个文本的相似度。"""
        return SequenceMatcher(None, text1, text2).ratio()

    def deduplicate(self, chunks: list[dict]) -> list[dict]:
        """
        去重：移除高度相似的文档块。

        Args:
            chunks: 文档块列表

        Returns:
            去重后的文档块列表
        """
        if not chunks:
            return []

        unique_chunks = [chunks[0]]

        for chunk in chunks[1:]:
            is_duplicate = False

            for unique_chunk in unique_chunks:
                similarity = self._compute_similarity(
                    chunk["content"],
                    unique_chunk["content"]
                )

                if similarity >= self.similarity_threshold:
                    is_duplicate = True
                    # 如果新chunk分数更高，替换
                    if chunk.get("hybrid_score", 0) > unique_chunk.get("hybrid_score", 0):
                        unique_chunks.remove(unique_chunk)
                        unique_chunks.append(chunk)
                    break

            if not is_duplicate:
                unique_chunks.append(chunk)

        return unique_chunks

    def extract_key_sentences(self, text: str, max_sentences: int = 5) -> str:
        """
        提取关键句子：基于句子位置和长度。

        Args:
            text: 原始文本
            max_sentences: 最大句子数

        Returns:
            压缩后的文本
        """
        # 简单的句子分割
        sentences = re.split(r'[。！？.!?]', text)
        sentences = [s.strip() for s in sentences if len(s.strip()) > 10]

        if len(sentences) <= max_sentences:
            return text

        # 选择前N个句子（通常开头包含最重要信息）
        selected = sentences[:max_sentences]
        return '。'.join(selected) + '。'

    def compress_context(
        self,
        chunks: list[dict],
        max_tokens: int = 2000,
        use_dedup: bool = True,
        use_extraction: bool = True,
    ) -> str:
        """
        压缩上下文：去重 + 提取关键信息。

        Args:
            chunks: 文档块列表
            max_tokens: 最大token数（近似）
            use_dedup: 是否去重
            use_extraction: 是否提取关键句子

        Returns:
            压缩后的上下文文本
        """
        # 第一步：去重
        if use_dedup:
            chunks = self.deduplicate(chunks)

        # 第二步：拼接并控制长度
        parts = []
        current_length = 0

        for i, chunk in enumerate(chunks, 1):
            content = chunk["content"]

            # 提取关键句子
            if use_extraction and len(content) > 500:
                content = self.extract_key_sentences(content, max_sentences=5)

            # 估算token数（中文约1.5字/token）
            estimated_tokens = len(content) * 1.5

            if current_length + estimated_tokens > max_tokens:
                # 截断到剩余空间
                remaining_tokens = max_tokens - current_length
                remaining_chars = int(remaining_tokens / 1.5)
                if remaining_chars > 100:
                    content = content[:remaining_chars] + "..."
                else:
                    break

            parts.append(f"[片段{i}]\n{content}")
            current_length += estimated_tokens

        return "\n\n".join(parts)

    def rerank_by_diversity(self, chunks: list[dict], top_k: int = 5) -> list[dict]:
        """
        多样性重排序：确保结果来自不同文档。

        Args:
            chunks: 文档块列表（已按相关性排序）
            top_k: 返回Top-K结果

        Returns:
            多样性排序后的结果
        """
        if not chunks:
            return []

        # 按文档分组
        doc_groups = {}
        for chunk in chunks:
            doc_id = chunk.get("document_id")
            if doc_id not in doc_groups:
                doc_groups[doc_id] = []
            doc_groups[doc_id].append(chunk)

        # 贪心选择：从每个文档中选择最高分的chunk
        result = []
        doc_indices = {doc_id: 0 for doc_id in doc_groups}

        while len(result) < top_k:
            best_chunk = None
            best_score = -1

            for doc_id, group in doc_groups.items():
                idx = doc_indices[doc_id]
                if idx < len(group):
                    chunk = group[idx]
                    score = chunk.get("hybrid_score", 0)

                    # 添加多样性惩罚
                    doc_count = sum(1 for r in result if r.get("document_id") == doc_id)
                    diversity_score = score * (0.8 ** doc_count)

                    if diversity_score > best_score:
                        best_score = diversity_score
                        best_chunk = chunk
                        best_doc_id = doc_id

            if best_chunk:
                result.append(best_chunk)
                doc_indices[best_doc_id] += 1
            else:
                break

        return result
