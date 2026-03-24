import json
import logging
import os
import time
from contextlib import contextmanager
from datetime import datetime
from typing import Any, Dict, Optional


class PerformanceLogger:
    """性能监控日志记录器"""

    def __init__(self, log_file_path: Optional[str] = None):
        self.log_file_path = log_file_path or "/tmp/mem0_performance.log"
        self.setup_logger()

    def setup_logger(self):
        """设置性能日志记录器"""
        # 创建日志目录
        os.makedirs(os.path.dirname(self.log_file_path), exist_ok=True)

        # 创建专门的性能日志记录器
        self.logger = logging.getLogger("mem0_performance")
        self.logger.setLevel(logging.INFO)

        # 避免重复添加handler
        if not self.logger.handlers:
            # 文件handler
            file_handler = logging.FileHandler(self.log_file_path, encoding='utf-8')
            file_handler.setLevel(logging.INFO)

            # 格式化器
            formatter = logging.Formatter('%(asctime)s - %(message)s')
            file_handler.setFormatter(formatter)

            self.logger.addHandler(file_handler)

            # 防止日志传播到root logger
            self.logger.propagate = False

    @contextmanager
    def time_step(self, step_name: str, context: Dict[str, Any] = None):
        """计时上下文管理器"""
        start_time = time.perf_counter()
        step_context = context or {}

        try:
            yield step_context
        finally:
            end_time = time.perf_counter()
            duration = (end_time - start_time) * 1000  # 转换为毫秒

            log_data = {
                "step": step_name,
                "duration_ms": round(duration, 3),
                "timestamp": datetime.now().isoformat(),
                **step_context
            }

            self.logger.info(json.dumps(log_data, ensure_ascii=False))

    def log_search_summary(self, total_duration_ms: float, query: str,
                          user_id: str, result_count: int, filters: Dict[str, Any] = None):
        """记录搜索总结信息"""
        summary_data = {
            "event": "search_summary",
            "total_duration_ms": round(total_duration_ms, 3),
            "query_length": len(query),
            "user_id": user_id,
            "result_count": result_count,
            "filters": filters or {},
            "timestamp": datetime.now().isoformat()
        }

        self.logger.info(json.dumps(summary_data, ensure_ascii=False))

    def log_error(self, step_name: str, error: Exception, context: Dict[str, Any] = None):
        """记录错误信息"""
        error_data = {
            "event": "error",
            "step": step_name,
            "error_type": type(error).__name__,
            "error_message": str(error),
            "timestamp": datetime.now().isoformat(),
            **(context or {})
        }

        self.logger.info(json.dumps(error_data, ensure_ascii=False))

    def log_step(self, step_name: str, duration_ms: float, context: Dict[str, Any] = None):
        """简单的步骤日志记录方法"""
        log_data = {
            "step": step_name,
            "duration_ms": round(duration_ms, 3),
            "timestamp": datetime.now().isoformat(),
            **(context or {})
        }
        self.logger.info(json.dumps(log_data, ensure_ascii=False))

    def start_timer(self) -> float:
        """开始计时，返回开始时间"""
        return time.perf_counter()

    def end_timer(self, start_time: float) -> float:
        """结束计时，返回耗时（毫秒）"""
        return (time.perf_counter() - start_time) * 1000


# 全局性能日志记录器实例
_global_perf_logger = None

def get_performance_logger(log_file_path: Optional[str] = None) -> PerformanceLogger:
    """获取全局性能日志记录器实例"""
    global _global_perf_logger
    if _global_perf_logger is None:
        _global_perf_logger = PerformanceLogger(log_file_path)
    return _global_perf_logger


def enable_performance_logging(log_file_path: Optional[str] = None):
    """启用性能日志记录"""
    global _global_perf_logger
    _global_perf_logger = PerformanceLogger(log_file_path)
    return _global_perf_logger


def disable_performance_logging():
    """禁用性能日志记录"""
    global _global_perf_logger
    if _global_perf_logger:
        for handler in _global_perf_logger.logger.handlers:
            handler.close()
        _global_perf_logger.logger.handlers.clear()
        _global_perf_logger = None