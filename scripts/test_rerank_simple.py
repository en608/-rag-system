"""简单的Rerank测试"""

import asyncio
import sys
import time
from pathlib import Path

# 添加项目根目录到 Python 路径
sys.path.insert(0, str(Path(__file__).parent.parent))

from app.services.rerank_service import RerankService


async def main():
    """主函数"""
    print("Rerank服务测试")
    print("="*60)

    # 测试数据
    test_query = "什么是车道检测？"
    test_documents = [
        {"chunk_id": i, "document_id": 1, "content": f"这是关于车道检测的文档片段{i}，包含了车道线识别和检测的相关内容。"}
        for i in range(10)
    ]

    # 测试同步模式
    print("\n1. 测试同步模式...")
    try:
        sync_service = RerankService(async_mode=False)

        start_time = time.time()
        sync_results = await sync_service.rerank(test_query, test_documents, top_k=5)
        sync_time = time.time() - start_time

        print(f"   同步模式耗时: {sync_time:.3f}秒")
        print(f"   返回结果数: {len(sync_results)}")
        print(f"   第一个结果分数: {sync_results[0].get('rerank_score', 'N/A'):.4f}" if sync_results else "   无结果")
    except Exception as e:
        print(f"   同步模式测试失败: {e}")
        import traceback
        traceback.print_exc()

    # 测试异步模式
    print("\n2. 测试异步模式...")
    try:
        async_service = RerankService(async_mode=True)

        start_time = time.time()
        async_results = await async_service.rerank(test_query, test_documents, top_k=5)
        async_time = time.time() - start_time

        print(f"   异步模式耗时: {async_time:.3f}秒")
        print(f"   返回结果数: {len(async_results)}")
        print(f"   第一个结果分数: {async_results[0].get('rerank_score', 'N/A'):.4f}" if async_results else "   无结果")
    except Exception as e:
        print(f"   异步模式测试失败: {e}")
        import traceback
        traceback.print_exc()

    print("\n" + "="*60)
    print("测试完成")


if __name__ == "__main__":
    asyncio.run(main())
