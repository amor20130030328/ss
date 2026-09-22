"""
测试全局 httpx.AsyncClient 是否会导致并发变慢
"""
import asyncio
import time
import httpx
import json

# 模拟全局共享客户端
_shared_client = None

def get_shared_client():
    global _shared_client
    if _shared_client is None:
        _shared_client = httpx.AsyncClient(
            timeout=10.0,
            limits=httpx.Limits(max_connections=100, max_keepalive_connections=20),
        )
    return _shared_client

async def test_shared_vs_independent():
    """测试共享客户端 vs 独立客户端的性能差异"""
    
    # 替换为你的实际服务端地址
    url = "http://your-server-url/api"  # 需要修改
    test_data = {"test": "data"}
    
    async def single_request_shared(i):
        start = time.time()
        client = get_shared_client()  # 共享客户端
        try:
            await client.post(url, content=json.dumps(test_data))
            return time.time() - start
        except Exception as e:
            print(f"请求{i}失败: {e}")
            return -1
    
    async def single_request_independent(i):
        start = time.time()
        client = httpx.AsyncClient(timeout=10.0)  # 独立客户端
        try:
            await client.post(url, content=json.dumps(test_data))
            await client.aclose()
            return time.time() - start
        except Exception as e:
            print(f"请求{i}失败: {e}")
            return -1
    
    print("=" * 60)
    print("测试：共享客户端 10个并发")
    print("=" * 60)
    start = time.time()
    times_shared = await asyncio.gather(*[single_request_shared(i) for i in range(10)])
    total_shared = time.time() - start
    valid_shared = [t for t in times_shared if t > 0]
    avg_shared = sum(valid_shared) / len(valid_shared) if valid_shared else 0
    print(f"总耗时: {total_shared:.3f}s, 平均: {avg_shared:.3f}s\n")
    
    print("=" * 60)
    print("测试：独立客户端 10个并发")
    print("=" * 60)
    start = time.time()
    times_independent = await asyncio.gather(*[single_request_independent(i) for i in range(10)])
    total_independent = time.time() - start
    valid_independent = [t for t in times_independent if t > 0]
    avg_independent = sum(valid_independent) / len(valid_independent) if valid_independent else 0
    print(f"总耗时: {total_independent:.3f}s, 平均: {avg_independent:.3f}s\n")
    
    print("=" * 60)
    print("对比结果")
    print("=" * 60)
    if avg_shared > avg_independent * 1.5:
        print(f"⚠️  共享客户端慢 {avg_shared/avg_independent:.1f}x")
        print("   可能存在客户端层面的竞争")
    else:
        print("✅ 共享客户端性能正常")
    
    # 关闭共享客户端
    if _shared_client:
        await _shared_client.aclose()

if __name__ == "__main__":
    print("\n⚠️  请先修改代码第16行的 url 为你的实际服务端地址！\n")
    asyncio.run(test_shared_vs_independent())
