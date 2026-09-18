"""
并发性能测试脚本
测试真实业务函数 request_qwen3_asr 的并发性能
"""
import asyncio
import time
import sys
import numpy as np
from pathlib import Path

# 添加项目路径到 sys.path
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

from src.utils.http_util import request_qwen3_asr
from src.configs.config import config

async def test_qwen3_asr_concurrent():
    """测试 request_qwen3_asr 的并发性能"""

    print("=" * 60)
    print("request_qwen3_asr 并发性能测试")
    print("=" * 60)

    # 生成测试音频数据（模拟真实场景）
    # 16kHz, 2秒音频 = 32000个采样点
    sample_rate = 16000
    duration = 2.0  # 秒
    num_samples = int(sample_rate * duration)

    # 生成随机音频数据（int16格式）
    test_audio = np.random.randint(-32768, 32767, num_samples, dtype=np.int16)

    print(f"\n测试参数:")
    print(f"  音频长度: {duration}秒")
    print(f"  采样率: {sample_rate}Hz")
    print(f"  数据大小: {len(test_audio.tobytes())/1024:.1f}KB")
    print(f"  服务端地址: {config.omni_address}")

    async def single_request(i, session_id):
        start = time.time()
        try:
            result = await request_qwen3_asr(
                session_id=session_id,
                data=test_audio,
                prev="",
                enable_fa=False
            )
            elapsed = time.time() - start
            has_result = "有结果" if result else "无结果"
            print(f"请求{i}: {has_result}, 耗时={elapsed:.3f}秒")
            return elapsed, bool(result)
        except Exception as e:
            elapsed = time.time() - start
            print(f"请求{i}: 失败={e}, 耗时={elapsed:.3f}秒")
            return elapsed, False

    # 测试1个请求
    print("\n" + "=" * 60)
    print("测试1个请求")
    print("=" * 60)
    start = time.time()
    single_time, single_success = await single_request(0, "test_session_single")
    total_single = time.time() - start
    print(f"\n单请求总耗时: {total_single:.3f}秒")
    print(f"请求状态: {'成功' if single_success else '失败'}")

    # 测试10个并发
    print("\n" + "=" * 60)
    print("测试10个并发")
    print("=" * 60)
    start = time.time()
    results = await asyncio.gather(*[
        single_request(i, f"test_session_concurrent_{i}")
        for i in range(10)
    ])
    total_time = time.time() - start

    times = [r[0] for r in results]
    successes = [r[1] for r in results]

    avg_time = sum(times) / len(times)
    max_time = max(times)
    min_time = min(times)
    success_count = sum(successes)

    print("\n" + "=" * 60)
    print("统计结果")
    print("=" * 60)
    print(f"\n📊 10个并发:")
    print(f"  总耗时: {total_time:.3f}秒")
    print(f"  平均每个: {avg_time:.3f}秒")
    print(f"  最快: {min_time:.3f}秒")
    print(f"  最慢: {max_time:.3f}秒")
    print(f"  理论最佳: {max_time:.3f}秒")
    print(f"  并发效率: {(max_time / total_time * 100):.1f}%")
    print(f"  成功率: {success_count}/10")

    # 性能分析
    print("\n" + "=" * 60)
    print("性能分析")
    print("=" * 60)

    if max_time > min_time * 3:
        print(f"⚠️  最慢请求是最快的 {max_time/min_time:.1f}x")
        print("   → 服务端可能在串行处理（排队）")

    if avg_time > single_time * 2:
        print(f"⚠️  并发平均耗时({avg_time:.3f}s)是单请求({single_time:.3f}s)的 {avg_time/single_time:.1f}x")
        print("   → 服务端可能不支持真正的并发")

    if total_time > max_time * 1.2:
        print(f"⚠️  总耗时({total_time:.3f}s)明显大于最慢请求({max_time:.3f}s)")
        print("   → 可能存在调度或其他开销")

    if success_count < 10:
        print(f"❌ 有 {10-success_count} 个请求失败")
        print("   → 检查服务端日志和超时设置")

    if max_time < single_time * 1.2 and total_time < max_time * 1.2:
        print("✅ 并发性能正常，客户端和服务端都支持真正的并发")

if __name__ == "__main__":
    asyncio.run(test_qwen3_asr_concurrent())
