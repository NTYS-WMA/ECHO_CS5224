import functools
import time
from typing import Any, Callable, Dict, Optional

from .performance_logger import get_performance_logger


def performance_monitor(
    step_name: Optional[str] = None,
    context_extractor: Optional[Callable] = None,
    log_args: bool = False,
    log_result_count: bool = False
):
    """
    性能监控装饰器

    Args:
        step_name: 步骤名称，如果不提供则使用函数名
        context_extractor: 从函数参数中提取上下文信息的函数
        log_args: 是否记录函数参数
        log_result_count: 是否记录结果数量（适用于返回列表/字典的函数）
    """
    def decorator(func: Callable) -> Callable:
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            perf_logger = get_performance_logger()
            actual_step_name = step_name or f"{func.__module__}.{func.__name__}"

            # 构建上下文信息
            context = {}

            # 提取自定义上下文
            if context_extractor:
                try:
                    extracted_context = context_extractor(*args, **kwargs)
                    if isinstance(extracted_context, dict):
                        context.update(extracted_context)
                except Exception as e:
                    perf_logger.log_error("context_extraction", e, {"step": actual_step_name})

            # 记录函数参数（可选）
            if log_args:
                context["args_count"] = len(args)
                context["kwargs_keys"] = list(kwargs.keys())
                # 记录一些重要参数的值
                if "query" in kwargs:
                    context["query_length"] = len(str(kwargs["query"]))
                if "limit" in kwargs:
                    context["limit"] = kwargs["limit"]
                if "threshold" in kwargs:
                    context["threshold"] = kwargs["threshold"]

            start_time = time.perf_counter()
            try:
                result = func(*args, **kwargs)

                # 记录结果信息
                if log_result_count and result:
                    if isinstance(result, dict):
                        if "results" in result:
                            context["result_count"] = len(result["results"])
                        if "relations" in result:
                            context["relations_count"] = len(result["relations"])
                    elif isinstance(result, (list, tuple)):
                        context["result_count"] = len(result)

                return result

            except Exception as e:
                end_time = time.perf_counter()
                duration = (end_time - start_time) * 1000

                error_context = {**context, "duration_ms": round(duration, 3)}
                perf_logger.log_error(actual_step_name, e, error_context)
                raise

            finally:
                end_time = time.perf_counter()
                duration = (end_time - start_time) * 1000

                # 记录性能信息
                final_context = {**context, "duration_ms": round(duration, 3)}
                perf_logger.logger.info(
                    perf_logger.logger._log.__class__.__module__ and
                    f'{{"step": "{actual_step_name}", {", ".join(f'"{k}": {v if isinstance(v, (int, float)) else f'"{v}"'}' for k, v in final_context.items())}, "timestamp": "{time.strftime("%Y-%m-%dT%H:%M:%S")}"}}'
                    or f'{{"step": "{actual_step_name}", "duration_ms": {round(duration, 3)}, "timestamp": "{time.strftime("%Y-%m-%dT%H:%M:%S")}"}}'
                )

        return wrapper
    return decorator


def extract_search_context(*args, **kwargs) -> Dict[str, Any]:
    """提取search方法的上下文信息"""
    context = {}

    # 从kwargs中提取关键信息
    if "query" in kwargs:
        context["query_length"] = len(str(kwargs["query"]))
    if "user_id" in kwargs:
        context["user_id"] = str(kwargs["user_id"])[:8] + "..." if len(str(kwargs["user_id"])) > 8 else str(kwargs["user_id"])
    if "agent_id" in kwargs:
        context["agent_id"] = str(kwargs["agent_id"])[:8] + "..." if len(str(kwargs["agent_id"])) > 8 else str(kwargs["agent_id"])
    if "limit" in kwargs:
        context["limit"] = kwargs["limit"]
    if "threshold" in kwargs:
        context["threshold"] = kwargs["threshold"]
    if "filters" in kwargs and kwargs["filters"]:
        context["filters_keys"] = list(kwargs["filters"].keys())

    return context


def extract_vector_search_context(*args, **kwargs) -> Dict[str, Any]:
    """提取向量搜索的上下文信息"""
    context = {}

    # args[0] 通常是 self, args[1] 是 query
    if len(args) > 1:
        query = args[1]
        context["query_length"] = len(str(query))

    # args[2] 通常是 filters
    if len(args) > 2 and args[2]:
        filters = args[2]
        if isinstance(filters, dict):
            context["filter_keys"] = list(filters.keys())

    # args[3] 通常是 limit
    if len(args) > 3:
        context["limit"] = args[3]

    # args[4] 通常是 threshold
    if len(args) > 4 and args[4] is not None:
        context["threshold"] = args[4]

    return context


# 预定义的常用装饰器
search_monitor = performance_monitor(
    step_name="memory.search",
    context_extractor=extract_search_context,
    log_args=True,
    log_result_count=True
)

vector_search_monitor = performance_monitor(
    step_name="memory.vector_search",
    context_extractor=extract_vector_search_context,
    log_args=True,
    log_result_count=True
)

embedding_monitor = performance_monitor(
    step_name="embedding.generate",
    log_args=True
)

graph_search_monitor = performance_monitor(
    step_name="graph.search",
    log_args=True,
    log_result_count=True
)