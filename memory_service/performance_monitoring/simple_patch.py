"""
简单的性能监控补丁 - 直接在原有方法中添加几行代码即可

使用方法：
1. 将下面的import添加到 mem0/memory/main.py 的开头
2. 将对应的埋点代码添加到相应的方法中
"""

# ===============================
# 1. 添加到文件开头的import
# ===============================
import sys
import os
# 添加性能监控路径
perf_monitoring_path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'performance_monitoring')
if perf_monitoring_path not in sys.path:
    sys.path.insert(0, perf_monitoring_path)

try:
    from performance_logger import get_performance_logger
    PERFORMANCE_MONITORING_ENABLED = True
except ImportError:
    PERFORMANCE_MONITORING_ENABLED = False
    print("性能监控模块未找到，跳过性能监控")


# ===============================
# 2. 在search方法中添加的代码
# ===============================

def search_method_patch():
    """
    在原有的search方法中添加这些代码片段
    位置：mem0/memory/main.py 的 search 方法
    """

    # 在方法开始处添加（第一行）
    if PERFORMANCE_MONITORING_ENABLED:
        perf_logger = get_performance_logger()
        total_start = perf_logger.start_timer()

    # 在 _build_filters_and_metadata 调用前后添加
    if PERFORMANCE_MONITORING_ENABLED:
        filter_start = perf_logger.start_timer()

    _, effective_filters = _build_filters_and_metadata(
        user_id=user_id, agent_id=agent_id, run_id=run_id, input_filters=filters
    )

    if PERFORMANCE_MONITORING_ENABLED:
        filter_duration = perf_logger.end_timer(filter_start)
        perf_logger.log_step("search.build_filters", filter_duration, {
            "filter_count": len(effective_filters)
        })

    # 在并发执行前后添加
    if PERFORMANCE_MONITORING_ENABLED:
        concurrent_start = perf_logger.start_timer()

    with concurrent.futures.ThreadPoolExecutor() as executor:
        # ... 原有的并发代码 ...
        pass

    if PERFORMANCE_MONITORING_ENABLED:
        concurrent_duration = perf_logger.end_timer(concurrent_start)
        perf_logger.log_step("search.concurrent_execution", concurrent_duration, {
            "memory_results": len(original_memories) if original_memories else 0
        })

    # 在方法结束前添加（return语句前）
    if PERFORMANCE_MONITORING_ENABLED:
        total_duration = perf_logger.end_timer(total_start)
        perf_logger.log_search_summary(
            total_duration,
            query,
            user_id or agent_id or run_id or "unknown",
            len(original_memories) if original_memories else 0,
            effective_filters
        )


# ===============================
# 3. 在_search_vector_store方法中添加的代码
# ===============================

def search_vector_store_patch():
    """
    在原有的_search_vector_store方法中添加这些代码片段
    位置：mem0/memory/main.py 的 _search_vector_store 方法
    """

    # 在方法开始处添加
    if PERFORMANCE_MONITORING_ENABLED:
        perf_logger = get_performance_logger()

    # 在嵌入生成前后添加
    if PERFORMANCE_MONITORING_ENABLED:
        embed_start = perf_logger.start_timer()

    embeddings = self.embedding_model.embed(query, "search")

    if PERFORMANCE_MONITORING_ENABLED:
        embed_duration = perf_logger.end_timer(embed_start)
        perf_logger.log_step("vector_search.embedding", embed_duration, {
            "query_length": len(query)
        })

    # 在向量搜索前后添加
    if PERFORMANCE_MONITORING_ENABLED:
        search_start = perf_logger.start_timer()

    memories = self.vector_store.search(query=query, vectors=embeddings, limit=limit, filters=filters)

    if PERFORMANCE_MONITORING_ENABLED:
        search_duration = perf_logger.end_timer(search_start)
        perf_logger.log_step("vector_search.database_search", search_duration, {
            "limit": limit,
            "raw_results": len(memories)
        })

    # 在结果处理前后添加
    if PERFORMANCE_MONITORING_ENABLED:
        process_start = perf_logger.start_timer()

    # ... 原有的结果处理代码 ...
    original_memories = []
    # 处理逻辑...

    if PERFORMANCE_MONITORING_ENABLED:
        process_duration = perf_logger.end_timer(process_start)
        perf_logger.log_step("vector_search.result_processing", process_duration, {
            "final_results": len(original_memories),
            "threshold": threshold
        })


# ===============================
# 4. 完整的修改说明
# ===============================

MODIFICATION_GUIDE = """
完整修改步骤：

1. 在 mem0/memory/main.py 文件开头添加性能监控导入：

import sys
import os
perf_monitoring_path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'performance_monitoring')
if perf_monitoring_path not in sys.path:
    sys.path.insert(0, perf_monitoring_path)

try:
    from performance_logger import get_performance_logger
    PERFORMANCE_MONITORING_ENABLED = True
except ImportError:
    PERFORMANCE_MONITORING_ENABLED = False

2. 在search方法中添加埋点（约10行代码）
3. 在_search_vector_store方法中添加埋点（约15行代码）

总共只需要添加约25-30行代码，不会影响原有逻辑，性能开销极小。

性能日志将输出到：/tmp/mem0_performance.log
日志格式为JSON，包含每个步骤的耗时和上下文信息。
"""

print(MODIFICATION_GUIDE)