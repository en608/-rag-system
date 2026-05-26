"""RAG系统评估脚本：测试检索准确率、召回率、F1等指标。"""

import asyncio
import json
import sys
import time
from pathlib import Path
from dataclasses import dataclass, field

# 添加项目根目录到 Python 路径
sys.path.insert(0, str(Path(__file__).parent.parent))

from app.core.database import AsyncSessionLocal
from app.models.document import Document
from app.models.document_chunk import DocumentChunk
from app.services.embedding_service import EmbeddingService
from app.services.rerank_service import RerankService
from app.services.hybrid_retriever import HybridRetriever
from sqlalchemy import select


@dataclass
class TestCase:
    """测试用例：问题 + 标准答案 + 相关文档ID"""
    question: str
    expected_answer_keywords: list[str]  # 答案中应包含的关键词
    relevant_doc_ids: list[int]  # 相关文档ID
    relevant_chunk_keywords: list[str] = field(default_factory=list)  # 相关chunk应包含的关键词


@dataclass
class EvalResult:
    """评估结果"""
    precision_at_k: float = 0.0  # 精确率
    recall_at_k: float = 0.0  # 召回率
    f1_at_k: float = 0.0  # F1分数
    mrr: float = 0.0  # 平均倒数排名
    hit_rate: float = 0.0  # 命中率
    answer_accuracy: float = 0.0  # 答案准确率
    avg_latency: float = 0.0  # 平均延迟


# 测试数据集 - 基于数据库中实际文档内容
# 文档5: UFLDv2.pdf (车道检测论文)
# 文档6: 实习总结
# 文档8: ufldv1.pdf (车道检测论文)
# 文档12: 课程作业说明书
TEST_CASES = [
    TestCase(
        question="什么是UFLDv2？",
        expected_answer_keywords=["Ultra Fast", "Lane Detection", "车道检测", "deep learning"],
        relevant_doc_ids=[5, 8],
        relevant_chunk_keywords=["Ultra Fast", "lane", "detection"],
    ),
    TestCase(
        question="车道检测的主要挑战是什么？",
        expected_answer_keywords=["occlusion", "lighting", "遮挡", "光照", "challenge"],
        relevant_doc_ids=[5, 8],
        relevant_chunk_keywords=["occlusion", "lighting", "challenge"],
    ),
    TestCase(
        question="UFLDv1和v2有什么区别？",
        expected_answer_keywords=["version", "improve", "fast", "speed"],
        relevant_doc_ids=[5, 8],
        relevant_chunk_keywords=["v1", "v2", "version", "improve"],
    ),
    TestCase(
        question="实习的主要内容是什么？",
        expected_answer_keywords=["实习", "项目", "开发", "实践", "工作"],
        relevant_doc_ids=[6],
        relevant_chunk_keywords=["实习", "项目", "工作"],
    ),
    TestCase(
        question="前端作业的要求是什么？",
        expected_answer_keywords=["前端", "作业", "页面", "HTML"],
        relevant_doc_ids=[12],
        relevant_chunk_keywords=["前端", "作业", "页面"],
    ),
    TestCase(
        question="什么是深度学习？",
        expected_answer_keywords=["deep learning", "neural", "network", "model"],
        relevant_doc_ids=[5, 8],
        relevant_chunk_keywords=["deep", "learning", "neural"],
    ),
    TestCase(
        question="车道线检测的数据集有哪些？",
        expected_answer_keywords=["dataset", "CULane", "Tusimple", "benchmark"],
        relevant_doc_ids=[5, 8],
        relevant_chunk_keywords=["dataset", "CULane", "Tusimple"],
    ),
    TestCase(
        question="什么是Python？",
        expected_answer_keywords=["Python", "programming", "language", "simple"],
        relevant_doc_ids=[10],
        relevant_chunk_keywords=["Python", "programming", "language"],
    ),
    TestCase(
        question="FastAPI是什么框架？",
        expected_answer_keywords=["FastAPI", "web", "framework", "modern"],
        relevant_doc_ids=[10],
        relevant_chunk_keywords=["FastAPI", "web", "framework"],
    ),
    TestCase(
        question="实习报告的格式要求是什么？",
        expected_answer_keywords=["报告", "格式", "实习", "总结"],
        relevant_doc_ids=[6],
        relevant_chunk_keywords=["报告", "格式", "实习"],
    ),
]


class RAGEvaluator:
    """RAG系统评估器"""

    def __init__(self, use_rerank: bool = False, use_hybrid: bool = False):
        self.embedding_service = EmbeddingService()
        self.use_rerank = use_rerank
        self.use_hybrid = use_hybrid
        self.rerank_service = RerankService() if use_rerank else None
        self.hybrid_retriever = HybridRetriever() if use_hybrid else None

    async def retrieve_chunks(
        self,
        query: str,
        top_k: int = 5,
    ) -> list[dict]:
        """检索相关chunks"""
        query_vector = await self.embedding_service.embed_query(query)

        # 如果使用rerank或混合检索，先召回更多候选
        recall_top_k = 20 if (self.use_rerank or self.use_hybrid) else top_k

        async with AsyncSessionLocal() as session:
            # 使用pgvector进行向量检索
            stmt = (
                select(DocumentChunk)
                .order_by(DocumentChunk.embedding.cosine_distance(query_vector))
                .limit(recall_top_k)
            )
            result = await session.execute(stmt)
            chunks = result.scalars().all()

            chunks_dict = [
                {
                    "chunk_id": chunk.id,
                    "document_id": chunk.document_id,
                    "content": chunk.content,
                    "chunk_index": chunk.chunk_index,
                }
                for chunk in chunks
            ]

            # 如果使用混合检索
            if self.use_hybrid and self.hybrid_retriever:
                chunks_dict = await self.hybrid_retriever.retrieve(
                    db=session,
                    query=query,
                    tenant_id="default",
                    top_k=recall_top_k,
                )

            # 如果使用rerank，进行重排序
            if self.use_rerank and self.rerank_service and len(chunks_dict) > top_k:
                chunks_dict = await self.rerank_service.rerank(
                    query=query,
                    documents=chunks_dict,
                    top_k=top_k,
                )

            return chunks_dict[:top_k]

    def calculate_metrics(
        self,
        retrieved_chunks: list[dict],
        test_case: TestCase,
        top_k: int = 5,
    ) -> dict:
        """计算单个测试用例的指标"""
        # 获取检索到的文档ID
        retrieved_doc_ids = [c["document_id"] for c in retrieved_chunks[:top_k]]

        # 计算精确率：检索到的相关文档数 / 检索到的文档总数
        relevant_retrieved = sum(
            1 for doc_id in retrieved_doc_ids if doc_id in test_case.relevant_doc_ids
        )
        precision = relevant_retrieved / top_k if top_k > 0 else 0.0

        # 计算召回率：检索到的相关文档数 / 所有相关文档总数
        total_relevant = len(test_case.relevant_doc_ids)
        recall = relevant_retrieved / total_relevant if total_relevant > 0 else 0.0

        # 计算F1分数
        f1 = (
            2 * precision * recall / (precision + recall)
            if (precision + recall) > 0
            else 0.0
        )

        # 计算MRR（平均倒数排名）
        mrr = 0.0
        for i, doc_id in enumerate(retrieved_doc_ids):
            if doc_id in test_case.relevant_doc_ids:
                mrr = 1.0 / (i + 1)
                break

        # 计算命中率：是否检索到至少一个相关文档
        hit = 1.0 if relevant_retrieved > 0 else 0.0

        # 计算答案准确率：基于关键词匹配
        all_content = " ".join(c["content"] for c in retrieved_chunks[:top_k])
        keyword_hits = sum(
            1
            for keyword in test_case.expected_answer_keywords
            if keyword.lower() in all_content.lower()
        )
        answer_accuracy = (
            keyword_hits / len(test_case.expected_answer_keywords)
            if test_case.expected_answer_keywords
            else 0.0
        )

        return {
            "precision": precision,
            "recall": recall,
            "f1": f1,
            "mrr": mrr,
            "hit": hit,
            "answer_accuracy": answer_accuracy,
        }

    async def evaluate(
        self,
        test_cases: list[TestCase],
        top_k: int = 5,
    ) -> EvalResult:
        """运行完整评估"""
        results = []
        total_latency = 0.0

        print(f"\n开始评估，共 {len(test_cases)} 个测试用例...")
        print("=" * 60)

        for i, test_case in enumerate(test_cases, 1):
            print(f"\n测试用例 {i}: {test_case.question}")

            # 计时
            start_time = time.time()
            chunks = await self.retrieve_chunks(test_case.question, top_k=top_k)
            latency = time.time() - start_time
            total_latency += latency

            # 计算指标
            metrics = self.calculate_metrics(chunks, test_case, top_k)
            results.append(metrics)

            # 输出详细结果
            print(f"  检索到的文档ID: {[c['document_id'] for c in chunks[:top_k]]}")
            print(f"  相关文档ID: {test_case.relevant_doc_ids}")
            print(f"  精确率@{top_k}: {metrics['precision']:.2%}")
            print(f"  召回率@{top_k}: {metrics['recall']:.2%}")
            print(f"  F1@{top_k}: {metrics['f1']:.2%}")
            print(f"  MRR: {metrics['mrr']:.2%}")
            print(f"  命中: {'是' if metrics['hit'] else '否'}")
            print(f"  答案准确率: {metrics['answer_accuracy']:.2%}")
            print(f"  延迟: {latency:.3f}秒")

        # 计算平均指标
        avg_result = EvalResult(
            precision_at_k=sum(r["precision"] for r in results) / len(results),
            recall_at_k=sum(r["recall"] for r in results) / len(results),
            f1_at_k=sum(r["f1"] for r in results) / len(results),
            mrr=sum(r["mrr"] for r in results) / len(results),
            hit_rate=sum(r["hit"] for r in results) / len(results),
            answer_accuracy=sum(r["answer_accuracy"] for r in results) / len(results),
            avg_latency=total_latency / len(results),
        )

        print("\n" + "=" * 60)
        print("评估结果汇总")
        print("=" * 60)
        print(f"精确率@{top_k}: {avg_result.precision_at_k:.2%}")
        print(f"召回率@{top_k}: {avg_result.recall_at_k:.2%}")
        print(f"F1@{top_k}: {avg_result.f1_at_k:.2%}")
        print(f"MRR: {avg_result.mrr:.2%}")
        print(f"命中率: {avg_result.hit_rate:.2%}")
        print(f"答案准确率: {avg_result.answer_accuracy:.2%}")
        print(f"平均延迟: {avg_result.avg_latency:.3f}秒")

        return avg_result


async def main():
    """主函数"""
    import argparse

    parser = argparse.ArgumentParser(description="RAG系统评估脚本")
    parser.add_argument(
        "--rerank",
        action="store_true",
        help="启用Rerank重排序",
    )
    parser.add_argument(
        "--hybrid",
        action="store_true",
        help="启用混合检索（向量+BM25）",
    )
    parser.add_argument(
        "--top-k",
        type=int,
        default=5,
        help="返回Top-K个结果（默认5）",
    )
    args = parser.parse_args()

    # 构建模式描述
    modes = []
    if args.hybrid:
        modes.append("Hybrid")
    if args.rerank:
        modes.append("Rerank")
    mode = " + ".join(modes) if modes else "Baseline"

    print(f"RAG系统评估脚本 ({mode})")
    print("=" * 60)

    evaluator = RAGEvaluator(use_rerank=args.rerank, use_hybrid=args.hybrid)
    result = await evaluator.evaluate(TEST_CASES, top_k=args.top_k)

    # 保存结果到文件
    result_dict = {
        "mode": mode,
        "precision_at_5": result.precision_at_k,
        "recall_at_5": result.recall_at_k,
        "f1_at_5": result.f1_at_k,
        "mrr": result.mrr,
        "hit_rate": result.hit_rate,
        "answer_accuracy": result.answer_accuracy,
        "avg_latency": result.avg_latency,
    }

    # 生成文件名
    filename_parts = ["eval_result"]
    if args.hybrid:
        filename_parts.append("hybrid")
    if args.rerank:
        filename_parts.append("rerank")
    if len(filename_parts) == 1:
        filename_parts.append("baseline")
    output_file = Path(__file__).parent.parent / f"{'_'.join(filename_parts)}.json"

    with open(output_file, "w", encoding="utf-8") as f:
        json.dump(result_dict, f, indent=2, ensure_ascii=False)

    print(f"\n结果已保存到: {output_file}")


if __name__ == "__main__":
    asyncio.run(main())
