"""
Memory类的性能监控版本 - 直接在原有方法中添加埋点
使用方法：
1. 导入性能日志记录器
2. 在需要监控的方法中添加计时埋点
3. 用这个文件替换原有的main.py，或者将埋点代码复制到原文件中
"""

# 在原有的import基础上添加性能监控
import sys
import os

# 添加性能监控模块路径
current_dir = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, current_dir)

from performance_logger import get_performance_logger

# 这里演示如何修改原有的search方法
def search_with_performance_monitoring(
    self,
    query: str,
    *,
    user_id: Optional[str] = None,
    agent_id: Optional[str] = None,
    run_id: Optional[str] = None,
    limit: int = 100,
    filters: Optional[Dict[str, Any]] = None,
    threshold: Optional[float] = None,
):
    """
    带性能监控的搜索方法
    """
    # 获取性能日志记录器
    perf_logger = get_performance_logger()

    # 开始总计时
    total_start = perf_logger.start_timer()

    try:
        # 1. 过滤器构建阶段
        filter_start = perf_logger.start_timer()
        _, effective_filters = _build_filters_and_metadata(
            user_id=user_id, agent_id=agent_id, run_id=run_id, input_filters=filters
        )
        filter_duration = perf_logger.end_timer(filter_start)
        perf_logger.log_step("search.build_filters", filter_duration, {
            "user_id": user_id[:8] + "..." if user_id and len(user_id) > 8 else user_id,
            "agent_id": agent_id[:8] + "..." if agent_id and len(agent_id) > 8 else agent_id,
            "filter_count": len(effective_filters)
        })

        if not any(key in effective_filters for key in ("user_id", "agent_id", "run_id")):
            raise ValueError("At least one of 'user_id', 'agent_id', or 'run_id' must be specified.")

        # 2. 遥测处理阶段
        telemetry_start = perf_logger.start_timer()
        keys, encoded_ids = process_telemetry_filters(effective_filters)
        capture_event(
            "mem0.search",
            self,
            {
                "limit": limit,
                "version": self.api_version,
                "keys": keys,
                "encoded_ids": encoded_ids,
                "sync_type": "sync",
                "threshold": threshold,
            },
        )
        telemetry_duration = perf_logger.end_timer(telemetry_start)
        perf_logger.log_step("search.telemetry", telemetry_duration)

        # 3. 并发搜索阶段
        concurrent_start = perf_logger.start_timer()

        with concurrent.futures.ThreadPoolExecutor() as executor:
            future_memories = executor.submit(self._search_vector_store_with_perf, query, effective_filters, limit, threshold)
            future_graph_entities = (
                executor.submit(self.graph.search, query, effective_filters, limit) if self.enable_graph else None
            )

            concurrent.futures.wait(
                [future_memories, future_graph_entities] if future_graph_entities else [future_memories]
            )

            original_memories = future_memories.result()
            graph_entities = future_graph_entities.result() if future_graph_entities else None

        concurrent_duration = perf_logger.end_timer(concurrent_start)
        perf_logger.log_step("search.concurrent_execution", concurrent_duration, {
            "graph_enabled": self.enable_graph,
            "memory_results": len(original_memories) if original_memories else 0,
            "graph_results": len(graph_entities) if graph_entities else 0
        })

        # 4. 结果格式化阶段
        format_start = perf_logger.start_timer()

        if self.enable_graph:
            result = {"results": original_memories, "relations": graph_entities}
        elif self.api_version == "v1.0":
            warnings.warn(
                "The current search API output format is deprecated. "
                "To use the latest format, set `api_version='v1.1'`. "
                "The current format will be removed in mem0ai 1.1.0 and later versions.",
                category=DeprecationWarning,
                stacklevel=2,
            )
            result = {"results": original_memories}
        else:
            result = {"results": original_memories}

        format_duration = perf_logger.end_timer(format_start)
        perf_logger.log_step("search.format_result", format_duration)

        # 记录总体搜索结果
        total_duration = perf_logger.end_timer(total_start)
        perf_logger.log_search_summary(
            total_duration,
            query,
            user_id or agent_id or run_id or "unknown",
            len(original_memories) if original_memories else 0,
            effective_filters
        )

        return result

    except Exception as e:
        total_duration = perf_logger.end_timer(total_start)
        perf_logger.log_error("search.error", e, {
            "query_length": len(query),
            "user_id": user_id,
            "total_duration_ms": total_duration
        })
        raise


def _search_vector_store_with_perf(self, query, filters, limit, threshold: Optional[float] = None):
    """
    带性能监控的向量搜索方法
    """
    perf_logger = get_performance_logger()

    # 1. 向量嵌入阶段
    embed_start = perf_logger.start_timer()
    embeddings = self.embedding_model.embed(query, "search")
    embed_duration = perf_logger.end_timer(embed_start)
    perf_logger.log_step("vector_search.embedding", embed_duration, {
        "query_length": len(query),
        "embedding_model": str(type(self.embedding_model).__name__)
    })

    # 2. 向量搜索阶段
    search_start = perf_logger.start_timer()
    memories = self.vector_store.search(query=query, vectors=embeddings, limit=limit, filters=filters)
    search_duration = perf_logger.end_timer(search_start)
    perf_logger.log_step("vector_search.database_search", search_duration, {
        "limit": limit,
        "filter_count": len(filters) if filters else 0,
        "raw_results": len(memories)
    })

    # 3. 结果处理阶段
    process_start = perf_logger.start_timer()

    promoted_payload_keys = [
        "user_id",
        "agent_id",
        "run_id",
        "actor_id",
        "role",
    ]

    core_and_promoted_keys = {"data", "hash", "created_at", "updated_at", "id", *promoted_payload_keys}

    original_memories = []
    filtered_count = 0

    for mem in memories:
        memory_item_dict = MemoryItem(
            id=mem.id,
            memory=mem.payload["data"],
            hash=mem.payload.get("hash"),
            created_at=mem.payload.get("created_at"),
            updated_at=mem.payload.get("updated_at"),
            score=mem.score,
        ).model_dump()

        for key in promoted_payload_keys:
            if key in mem.payload:
                memory_item_dict[key] = mem.payload[key]

        additional_metadata = {k: v for k, v in mem.payload.items() if k not in core_and_promoted_keys}
        if additional_metadata:
            memory_item_dict["metadata"] = additional_metadata

        if threshold is None or mem.score >= threshold:
            original_memories.append(memory_item_dict)
        else:
            filtered_count += 1

    process_duration = perf_logger.end_timer(process_start)
    perf_logger.log_step("vector_search.result_processing", process_duration, {
        "processed_memories": len(memories),
        "final_results": len(original_memories),
        "filtered_by_threshold": filtered_count,
        "threshold": threshold
    })

    return original_memories


# 使用示例和说明
PERFORMANCE_MONITORING_USAGE = """
如何在原有代码中添加性能监控：

1. 在 mem0/memory/main.py 的开头添加：
   from performance_monitoring.performance_logger import get_performance_logger

2. 替换原有的 search 方法为 search_with_performance_monitoring
3. 替换原有的 _search_vector_store 方法为 _search_vector_store_with_perf

或者，你可以直接在原有方法中添加以下埋点代码：

# 在方法开始处
perf_logger = get_performance_logger()
step_start = perf_logger.start_timer()

# 在关键步骤后
step_duration = perf_logger.end_timer(step_start)
perf_logger.log_step("step_name", step_duration, {"context": "info"})

性能日志将保存在 /tmp/mem0_performance.log 文件中，格式为JSON，方便后续分析。
"""