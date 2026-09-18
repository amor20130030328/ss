"""
并发性能诊断脚本
测试 httpx 异步请求是否真正并发
"""
import asyncio
import time
import httpx
import json

async def test_http_concurrent():
    """测试纯HTTP并发（不涉及业务逻辑）"""

    # 模拟你的服务端地址
    url = "YOUR_SERVER_URL"  # 替换为实际地址

    client = httpx.AsyncClient(
        timeout=10.0,
        limits=httpx.Limits(max_connections=100, max_keepalive_connections=20),
    )

    async def single_request(i):
        start = time.time()
        try:
            # 模拟你的请求
            response = await client.post(
                url,
                headers={"Content-Type": "application/json"},
                content=json.dumps({"test": "data", "index": i}),
                timeout=10
            )
            elapsed = time.time() - start
            print(f"请求{i}: 状态={response.status_code}, 耗时={elapsed:.3f}秒")
            return elapsed
        except Exception as e:
            elapsed = time.time() - start
            print(f"请求{i}: 失败={e}, 耗时={elapsed:.3f}秒")
            return elapsed

    # 测试1个请求
    print("\n=== 测试1个请求 ===")
    start = time.time()
    await single_request(0)
    single_time = time.time() - start
    print(f"单请求总耗时: {single_time:.3f}秒\n")

    # 测试10个并发
    print("=== 测试10个并发 ===")
    start = time.time()
    times = await asyncio.gather(*[single_request(i) for i in range(10)])
    total_time = time.time() - start
    avg_time = sum(times) / len(times)
    print(f"\n10个并发:")
    print(f"  总耗时: {total_time:.3f}秒")
    print(f"  平均每个: {avg_time:.3f}秒")
    print(f"  理论最佳: {max(times):.3f}秒")
    print(f"  并发效率: {(max(times) / total_time * 100):.1f}%")

    await client.aclose()

if __name__ == "__main__":
    asyncio.run(test_http_concurrent())
