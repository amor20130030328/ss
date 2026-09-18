#!/usr/bin/env python
"""
并发性能分析脚本
用于定位为什么多并发时性能下降
"""
import re
import sys
from collections import defaultdict
from datetime import datetime

def analyze_log(log_file):
    """分析日志找出性能瓶颈"""

    # 存储每个session的时间线
    sessions = defaultdict(list)

    # 正则模式
    patterns = {
        'base64_encode': r'\[request_\w+\] Base64编码耗时=([\d.]+)s',
        'network_time': r'网络耗时=([\d.]+)s',
        'api_timeout': r'API call timeout',
        'start_request': r'\[request_\w+\] 开始请求 session_id=(\w+)',
        'complete': r'完成 session_id=(\w+).*总耗时=([\d.]+)s',
    }

    stats = {
        'base64_times': [],
        'network_times': [],
        'total_times': [],
        'timeouts': 0,
        'total_requests': 0
    }

    print("=" * 60)
    print("并发性能分析报告")
    print("=" * 60)

    try:
        with open(log_file, 'r', encoding='utf-8') as f:
            for line in f:
                # Base64编码时间
                match = re.search(patterns['base64_encode'], line)
                if match:
                    encode_time = float(match.group(1))
                    stats['base64_times'].append(encode_time)
                    if encode_time > 1.0:
                        print(f"⚠️  Base64编码慢: {encode_time:.3f}s")

                # 网络请求时间
                match = re.search(patterns['network_time'], line)
                if match:
                    net_time = float(match.group(1))
                    stats['network_times'].append(net_time)

                # 完成时间
                match = re.search(patterns['complete'], line)
                if match:
                    session_id = match.group(1)
                    total_time = float(match.group(2))
                    stats['total_times'].append(total_time)
                    stats['total_requests'] += 1

                # 超时
                if 'API call timeout' in line:
                    stats['timeouts'] += 1
                    print(f"❌ 超时: {line.strip()}")

    except FileNotFoundError:
        print(f"错误: 找不到日志文件 {log_file}")
        return

    # 统计分析
    print("\n" + "=" * 60)
    print("统计摘要")
    print("=" * 60)

    print(f"\n📊 请求总数: {stats['total_requests']}")
    print(f"⏱️  超时次数: {stats['timeouts']}")

    if stats['base64_times']:
        avg_encode = sum(stats['base64_times']) / len(stats['base64_times'])
        max_encode = max(stats['base64_times'])
        print(f"\n🔧 Base64编码:")
        print(f"   平均: {avg_encode:.3f}s")
        print(f"   最大: {max_encode:.3f}s")
        if max_encode > 0.5:
            print(f"   ⚠️  编码时间过长，可能阻塞并发")

    if stats['network_times']:
        avg_net = sum(stats['network_times']) / len(stats['network_times'])
        max_net = max(stats['network_times'])
        min_net = min(stats['network_times'])
        print(f"\n🌐 网络请求:")
        print(f"   平均: {avg_net:.3f}s")
        print(f"   最小: {min_net:.3f}s")
        print(f"   最大: {max_net:.3f}s")

        # 判断服务端是否排队
        if max_net > min_net * 3:
            print(f"   ⚠️  最大耗时是最小的{max_net/min_net:.1f}倍，服务端可能在排队处理")

    if stats['total_times']:
        avg_total = sum(stats['total_times']) / len(stats['total_times'])
        max_total = max(stats['total_times'])
        min_total = min(stats['total_times'])
        print(f"\n⏱️  总耗时:")
        print(f"   平均: {avg_total:.3f}s")
        print(f"   最小: {min_total:.3f}s")
        print(f"   最大: {max_total:.3f}s")

    # 瓶颈分析
    print("\n" + "=" * 60)
    print("🔍 瓶颈分析")
    print("=" * 60)

    if stats['timeouts'] > 0:
        print(f"❌ 主要问题: {stats['timeouts']} 个请求超时")
        print("   建议: 增加超时时间或优化服务端")

    if stats['network_times']:
        avg_net = sum(stats['network_times']) / len(stats['network_times'])
        if avg_net > 2.0:
            print("❌ 主要问题: 服务端处理慢")
            print(f"   平均网络耗时 {avg_net:.3f}s，接近或超过3秒超时")

        max_net = max(stats['network_times'])
        min_net = min(stats['network_times'])
        if max_net > min_net * 2:
            print("❌ 主要问题: 服务端不支持真正并发")
            print(f"   请求耗时波动大({min_net:.3f}s ~ {max_net:.3f}s)")
            print("   说明服务端在排队串行处理")

    if stats['base64_times']:
        max_encode = max(stats['base64_times'])
        if max_encode > 0.5:
            print("⚠️  次要问题: Base64编码耗时较长")
            print(f"   最大编码时间 {max_encode:.3f}s")

    print("\n✅ 分析完成")

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("用法: python analyze_performance.py <log_file>")
        print("示例: python analyze_performance.py /path/to/your/log")
        sys.exit(1)

    analyze_log(sys.argv[1])
