"""测试异步推理效果"""

import asyncio
import sys
import time
from pathlib import Path

# 添加项目根目录到 Python 路径
sys.path.insert(0, str(Path(__file__).parent.parent))

from app.services.rerank_service import RerankService


async def test_rerank_performance():
    """测试rerank性能"""
    print("Rerank性能测试")
    print("="*60)

    # 测试数据
    test_query = "什么是车道检测？"
    test_documents = [
        {"chunk_id": i, "document_id": 1, "content": f"这是关于车道检测的文档片段{i}，包含了车道线识别和检测的相关内容。" * 3}
        for i in range(20)
    ]

    # 测试同步模式
    print("\n1. 测试同步模式...")
    sync_service = RerankService(async_mode=False)

    start_time = time.time()
    sync_results = await sync_service.rerank(test_query, test_documents, top_k=5)
    sync_time = time.time() - start_time

    print(f"   同步模式耗时: {sync_time:.3f}秒")
    print(f"   返回结果数: {len(sync_results)}")

    # 测试异步模式
    print("\n2. 测试异步模式...")
    async_service = RerankService(async_mode=True)

    # 预热
    await async_service.rerank(test_query, test_documents[:5], top_k=3)

    # 测试单次请求
    start_time = time.time()
    async_results = await async_service.rerank(test_query, test_documents, top_k=5)
    async_time = time.time() - start_time

    print(f"   异步模式耗时: {async_time:.3f}秒")
    print(f"   返回结果数: {len(async_results)}")

    # 测试并发请求
    print("\n3. 测试并发请求...")
    num_concurrent = 5

    async def single_request(i):
        start = time.time()
        results = await async_service.rerank(
            f"测试查询{i}",
            test_documents[:10],
            top_k=3,
        )
        return time.time() - start

    start_time = time.time()
    tasks = [single_request(i) for i in range(num_concurrent)]
    times = await asyncio.gather(*tasks)
    total_time = time.time() - start_time

    print(f"   并发请求数: {num_concurrent}")
    print(f"   总耗时: {total_time:.3f}秒")
    print(f"   平均单次耗时: {sum(times)/len(times):.3f}秒")
    print(f"   最快: {min(times):.3f}秒")
    print(f"   最慢: {max(times):.3f}秒")

    # 对比总结
    print("\n" + "="*60)
    print("性能对比总结")
    print("="*60)
    print(f"同步模式: {sync_time:.3f}秒")
    print(f"异步模式: {async_time:.3f}秒")
    print(f"性能提升: {((sync_time - async_time) / sync_time * 100):.1f}%")

    # 清理资源
    del sync_service
    del async_service


async def main():
    """主函数"""
    await test_rerank_performance()


if __name__ == "__main__":
    asyncio.run(main())
