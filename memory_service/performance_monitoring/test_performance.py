#!/usr/bin/env python3
"""
性能监控测试脚本

使用方法：
1. 确保mem0项目正常运行
2. 运行此脚本测试性能监控功能
3. 查看生成的性能日志文件

python performance_monitoring/test_performance.py
"""

import sys
import os
import time
import requests
import json
from typing import Dict, Any

# 添加项目路径
project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, project_root)

# 导入性能监控
from performance_monitoring.performance_logger import enable_performance_logging, get_performance_logger


class PerformanceTestSuite:
    """性能测试套件"""

    def __init__(self, base_url: str = "http://localhost:18088", log_file: str = "/tmp/mem0_performance_test.log"):
        self.base_url = base_url
        self.log_file = log_file
        self.perf_logger = enable_performance_logging(log_file)
        print(f"性能日志将保存到: {log_file}")

    def test_performance_logger(self):
        """测试性能日志记录器本身"""
        print("\n=== 测试性能日志记录器 ===")

        # 测试简单计时
        start_time = self.perf_logger.start_timer()
        time.sleep(0.1)  # 模拟100ms操作
        duration = self.perf_logger.end_timer(start_time)

        self.perf_logger.log_step("test.simple_timing", duration, {
            "test_type": "logger_test",
            "expected_duration_ms": 100
        })

        # 测试上下文管理器
        with self.perf_logger.time_step("test.context_manager", {"test_type": "context_test"}):
            time.sleep(0.05)  # 模拟50ms操作

        print("✓ 性能日志记录器测试完成")

    def test_search_api_performance(self):
        """测试搜索API的性能"""
        print("\n=== 测试搜索API性能 ===")

        # 准备测试数据
        test_queries = [
            "用户喜欢什么食物",
            "告诉我关于编程的建议",
            "最近的会议安排",
            "用户的个人偏好",
            "技术相关的记忆"
        ]

        user_id = "test_user_123"

        for i, query in enumerate(test_queries):
            print(f"测试查询 {i+1}: {query}")

            # 记录API调用性能
            api_start = self.perf_logger.start_timer()

            try:
                response = requests.post(
                    f"{self.base_url}/search",
                    json={
                        "query": query,
                        "user_id": user_id,
                        "limit": 10
                    },
                    timeout=30
                )

                api_duration = self.perf_logger.end_timer(api_start)

                if response.status_code == 200:
                    result = response.json()
                    result_count = len(result.get("results", []))

                    self.perf_logger.log_step("api.search_request", api_duration, {
                        "query_length": len(query),
                        "user_id": user_id,
                        "result_count": result_count,
                        "status_code": response.status_code,
                        "query_index": i + 1
                    })

                    print(f"  ✓ 查询成功，耗时: {api_duration:.1f}ms，结果数: {result_count}")
                else:
                    self.perf_logger.log_step("api.search_request_failed", api_duration, {
                        "query_length": len(query),
                        "status_code": response.status_code,
                        "error": response.text[:200]
                    })
                    print(f"  ✗ 查询失败，状态码: {response.status_code}")

            except Exception as e:
                api_duration = self.perf_logger.end_timer(api_start)
                self.perf_logger.log_error("api.search_request_error", e, {
                    "query_length": len(query),
                    "duration_ms": api_duration
                })
                print(f"  ✗ 查询异常: {str(e)}")

            # 添加间隔避免请求过快
            time.sleep(0.5)

    def test_add_memories_performance(self):
        """测试添加记忆的性能"""
        print("\n=== 测试添加记忆性能 ===")

        user_id = "test_user_123"
        test_messages = [
            "我喜欢意大利面和披萨",
            "我是一名软件工程师",
            "我每天早上8点起床",
            "我住在上海",
            "我喜欢看科幻电影"
        ]

        for i, message in enumerate(test_messages):
            print(f"添加记忆 {i+1}: {message}")

            add_start = self.perf_logger.start_timer()

            try:
                response = requests.post(
                    f"{self.base_url}/memories",
                    json={
                        "messages": [{"role": "user", "content": message}],
                        "user_id": user_id
                    },
                    timeout=30
                )

                add_duration = self.perf_logger.end_timer(add_start)

                if response.status_code == 200:
                    result = response.json()
                    results = result.get("results", [])

                    self.perf_logger.log_step("api.add_memory", add_duration, {
                        "message_length": len(message),
                        "user_id": user_id,
                        "operations_count": len(results),
                        "status_code": response.status_code,
                        "message_index": i + 1
                    })

                    print(f"  ✓ 添加成功，耗时: {add_duration:.1f}ms，操作数: {len(results)}")
                else:
                    print(f"  ✗ 添加失败，状态码: {response.status_code}")

            except Exception as e:
                add_duration = self.perf_logger.end_timer(add_start)
                self.perf_logger.log_error("api.add_memory_error", e, {
                    "message_length": len(message),
                    "duration_ms": add_duration
                })
                print(f"  ✗ 添加异常: {str(e)}")

            time.sleep(1)  # 给LLM处理时间

    def test_concurrent_requests(self):
        """测试并发请求性能"""
        print("\n=== 测试并发请求性能 ===")

        import threading
        import queue

        results_queue = queue.Queue()
        num_threads = 3
        requests_per_thread = 2

        def worker(thread_id: int):
            """工作线程函数"""
            for req_id in range(requests_per_thread):
                query = f"线程{thread_id}的查询{req_id}"

                request_start = self.perf_logger.start_timer()
                try:
                    response = requests.post(
                        f"{self.base_url}/search",
                        json={
                            "query": query,
                            "user_id": f"thread_user_{thread_id}",
                            "limit": 5
                        },
                        timeout=30
                    )

                    request_duration = self.perf_logger.end_timer(request_start)

                    result = {
                        "thread_id": thread_id,
                        "request_id": req_id,
                        "duration_ms": request_duration,
                        "status_code": response.status_code,
                        "success": response.status_code == 200
                    }

                    if response.status_code == 200:
                        data = response.json()
                        result["result_count"] = len(data.get("results", []))

                    results_queue.put(result)

                    self.perf_logger.log_step("concurrent.search_request", request_duration, {
                        "thread_id": thread_id,
                        "request_id": req_id,
                        "query": query,
                        "status_code": response.status_code
                    })

                except Exception as e:
                    request_duration = self.perf_logger.end_timer(request_start)
                    results_queue.put({
                        "thread_id": thread_id,
                        "request_id": req_id,
                        "duration_ms": request_duration,
                        "error": str(e),
                        "success": False
                    })

        # 启动并发测试
        concurrent_start = self.perf_logger.start_timer()

        threads = []
        for i in range(num_threads):
            thread = threading.Thread(target=worker, args=(i,))
            threads.append(thread)
            thread.start()

        # 等待所有线程完成
        for thread in threads:
            thread.join()

        concurrent_duration = self.perf_logger.end_timer(concurrent_start)

        # 收集结果
        results = []
        while not results_queue.empty():
            results.append(results_queue.get())

        successful_requests = [r for r in results if r.get("success", False)]
        avg_duration = sum(r["duration_ms"] for r in successful_requests) / len(successful_requests) if successful_requests else 0

        self.perf_logger.log_step("concurrent.test_summary", concurrent_duration, {
            "total_threads": num_threads,
            "requests_per_thread": requests_per_thread,
            "total_requests": len(results),
            "successful_requests": len(successful_requests),
            "average_request_duration_ms": round(avg_duration, 2)
        })

        print(f"✓ 并发测试完成")
        print(f"  总请求数: {len(results)}")
        print(f"  成功请求数: {len(successful_requests)}")
        print(f"  平均请求耗时: {avg_duration:.1f}ms")
        print(f"  总测试时间: {concurrent_duration:.1f}ms")

    def analyze_performance_log(self):
        """分析性能日志"""
        print("\n=== 性能日志分析 ===")

        try:
            with open(self.log_file, 'r', encoding='utf-8') as f:
                lines = f.readlines()

            if not lines:
                print("日志文件为空")
                return

            # 统计各步骤的性能
            step_stats = {}
            total_logs = 0

            for line in lines:
                try:
                    log_data = json.loads(line.split(' - ', 1)[1])  # 去除时间戳前缀
                    total_logs += 1

                    step = log_data.get("step")
                    duration = log_data.get("duration_ms", 0)

                    if step and duration:
                        if step not in step_stats:
                            step_stats[step] = {"count": 0, "total_ms": 0, "min_ms": float('inf'), "max_ms": 0}

                        stats = step_stats[step]
                        stats["count"] += 1
                        stats["total_ms"] += duration
                        stats["min_ms"] = min(stats["min_ms"], duration)
                        stats["max_ms"] = max(stats["max_ms"], duration)

                except (json.JSONDecodeError, IndexError, KeyError):
                    continue

            print(f"总日志条数: {total_logs}")
            print(f"性能步骤统计:")
            print("-" * 80)
            print(f"{'步骤':<30} {'次数':<8} {'平均(ms)':<12} {'最小(ms)':<12} {'最大(ms)':<12}")
            print("-" * 80)

            for step, stats in sorted(step_stats.items()):
                avg_ms = stats["total_ms"] / stats["count"]
                print(f"{step:<30} {stats['count']:<8} {avg_ms:<12.1f} {stats['min_ms']:<12.1f} {stats['max_ms']:<12.1f}")

            print(f"\n性能日志文件: {self.log_file}")

        except FileNotFoundError:
            print(f"日志文件不存在: {self.log_file}")
        except Exception as e:
            print(f"分析日志时出错: {e}")

    def run_all_tests(self):
        """运行所有测试"""
        print("开始性能监控测试...")

        try:
            # 测试日志记录器
            self.test_performance_logger()

            # 检查API是否可用
            try:
                response = requests.get(f"{self.base_url}/", timeout=5)
                print(f"✓ API服务正常 (状态码: {response.status_code})")
            except Exception as e:
                print(f"✗ API服务不可用: {e}")
                print("请确保mem0服务正在运行")
                return

            # 先添加一些记忆
            self.test_add_memories_performance()

            # 等待记忆处理完成
            print("\n等待3秒让记忆处理完成...")
            time.sleep(3)

            # 测试搜索性能
            self.test_search_api_performance()

            # 测试并发性能
            self.test_concurrent_requests()

            # 分析结果
            self.analyze_performance_log()

            print("\n=== 测试完成 ===")
            print(f"详细性能日志请查看: {self.log_file}")

        except KeyboardInterrupt:
            print("\n测试被用户中断")
        except Exception as e:
            print(f"\n测试过程中出错: {e}")


def main():
    """主函数"""
    import argparse

    parser = argparse.ArgumentParser(description="Mem0性能监控测试")
    parser.add_argument("--url", default="http://localhost:18088", help="API服务地址")
    parser.add_argument("--log", default="/tmp/mem0_performance_test.log", help="性能日志文件路径")

    args = parser.parse_args()

    test_suite = PerformanceTestSuite(args.url, args.log)
    test_suite.run_all_tests()


if __name__ == "__main__":
    main()