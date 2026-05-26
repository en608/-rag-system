"""优化后的RAG系统评估脚本：测试轻量模型和异步推理效果。"""

import asyncio
import json
import sys
import time
from pathlib import Path

# 添加项目根目录到 Python 路径
sys.path.insert(0, str(Path(__file__).parent.parent))

from scripts.evaluate_rag import RAGEvaluator, TEST_CASES, EvalResult


async def run_evaluation(mode: str, use_rerank: bool, use_hybrid: bool) -> dict:
    """运行单次评估"""
    print(f"\n{'='*60}")
    print(f"评估模式: {mode}")
    print(f"{'='*60}")

    evaluator = RAGEvaluator(use_rerank=use_rerank, use_hybrid=use_hybrid)
    result = await evaluator.evaluate(TEST_CASES, top_k=5)

    return {
        "mode": mode,
        "precision_at_5": result.precision_at_k,
        "recall_at_5": result.recall_at_k,
        "f1_at_5": result.f1_at_k,
        "mrr": result.mrr,
        "hit_rate": result.hit_rate,
        "answer_accuracy": result.answer_accuracy,
        "avg_latency": result.avg_latency,
    }


async def main():
    """主函数：对比不同配置的性能"""
    print("RAG系统优化效果评估")
    print("测试轻量模型和异步推理的效果")

    results = []

    # 1. 基准测试（无Rerank）
    baseline = await run_evaluation("Baseline", use_rerank=False, use_hybrid=False)
    results.append(baseline)

    # 2. Rerank测试（使用默认模型）
    rerank = await run_evaluation("Rerank (Default)", use_rerank=True, use_hybrid=False)
    results.append(rerank)

    # 3. 混合检索测试
    hybrid = await run_evaluation("Hybrid", use_rerank=False, use_hybrid=True)
    results.append(hybrid)

    # 4. 混合检索 + Rerank测试
    hybrid_rerank = await run_evaluation("Hybrid + Rerank", use_rerank=True, use_hybrid=True)
    results.append(hybrid_rerank)

    # 保存结果
    output_file = Path(__file__).parent.parent / "eval_result_optimized.json"
    with open(output_file, "w", encoding="utf-8") as f:
        json.dump(results, f, indent=2, ensure_ascii=False)

    # 打印对比表格
    print("\n" + "="*80)
    print("优化效果对比")
    print("="*80)
    print(f"{'模式':<20} {'精确率':<10} {'召回率':<10} {'F1':<10} {'MRR':<10} {'准确率':<10} {'延迟':<10}")
    print("-"*80)

    for r in results:
        print(f"{r['mode']:<20} "
              f"{r['precision_at_5']:.2%}{'':<4} "
              f"{r['recall_at_5']:.2%}{'':<4} "
              f"{r['f1_at_5']:.2%}{'':<4} "
              f"{r['mrr']:.2%}{'':<4} "
              f"{r['answer_accuracy']:.2%}{'':<4} "
              f"{r['avg_latency']:.3f}s")

    # 计算提升
    print("\n" + "="*80)
    print("相对于Baseline的提升")
    print("="*80)

    baseline = results[0]
    for r in results[1:]:
        print(f"\n{r['mode']}:")
        print(f"  精确率: {(r['precision_at_5'] - baseline['precision_at_5']):.2%} "
              f"({baseline['precision_at_5']:.2%} -> {r['precision_at_5']:.2%})")
        print(f"  F1分数: {(r['f1_at_5'] - baseline['f1_at_5']):.2%} "
              f"({baseline['f1_at_5']:.2%} -> {r['f1_at_5']:.2%})")
        print(f"  MRR: {(r['mrr'] - baseline['mrr']):.2%} "
              f"({baseline['mrr']:.2%} -> {r['mrr']:.2%})")
        print(f"  延迟: {(r['avg_latency'] - baseline['avg_latency']):.3f}s "
              f"({baseline['avg_latency']:.3f}s -> {r['avg_latency']:.3f}s)")

    print(f"\n结果已保存到: {output_file}")


if __name__ == "__main__":
    asyncio.run(main())
