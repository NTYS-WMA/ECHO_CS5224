# Mem0 性能监控系统

这是一个为Mem0项目设计的轻量级性能监控系统，可以帮助你分析search API的各个步骤耗时情况。

## 文件结构

```
performance_monitoring/
├── README.md                 # 本文档
├── performance_logger.py     # 性能日志记录器
├── decorators.py            # 性能监控装饰器（高级用法）
├── simple_patch.py          # 简单补丁方案（推荐）
├── memory_with_perf.py      # 完整的性能监控版本（参考）
└── test_performance.py      # 性能测试脚本
```

## 快速开始

### 方案1：最简单的方式（推荐）

只需要在原有代码中添加几行代码即可：

1. **在 `mem0/memory/main.py` 文件开头添加导入**：

```python
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
```

2. **在search方法中添加埋点**（在第623行的search方法中）：

```python
def search(self, query: str, *, user_id: Optional[str] = None, ...):
    # 在方法开始处添加
    if PERFORMANCE_MONITORING_ENABLED:
        perf_logger = get_performance_logger()
        total_start = perf_logger.start_timer()

    # 在关键步骤前后添加计时
    if PERFORMANCE_MONITORING_ENABLED:
        filter_start = perf_logger.start_timer()

    _, effective_filters = _build_filters_and_metadata(...)

    if PERFORMANCE_MONITORING_ENABLED:
        filter_duration = perf_logger.end_timer(filter_start)
        perf_logger.log_step("search.build_filters", filter_duration)

    # ... 其他步骤类似 ...

    # 在方法结束前添加总结
    if PERFORMANCE_MONITORING_ENABLED:
        total_duration = perf_logger.end_timer(total_start)
        perf_logger.log_search_summary(total_duration, query, user_id or "unknown",
                                     len(original_memories) if original_memories else 0)
```

3. **在_search_vector_store方法中添加埋点**（在第699行的方法中）：

```python
def _search_vector_store(self, query, filters, limit, threshold=None):
    if PERFORMANCE_MONITORING_ENABLED:
        perf_logger = get_performance_logger()

        # 嵌入生成计时
        embed_start = perf_logger.start_timer()

    embeddings = self.embedding_model.embed(query, "search")

    if PERFORMANCE_MONITORING_ENABLED:
        embed_duration = perf_logger.end_timer(embed_start)
        perf_logger.log_step("vector_search.embedding", embed_duration)

        # 数据库搜索计时
        search_start = perf_logger.start_timer()

    memories = self.vector_store.search(...)

    if PERFORMANCE_MONITORING_ENABLED:
        search_duration = perf_logger.end_timer(search_start)
        perf_logger.log_step("vector_search.database_search", search_duration)
```

### 方案2：使用装饰器（高级）

如果你想要更优雅的方式，可以使用装饰器：

```python
from performance_monitoring.decorators import search_monitor, vector_search_monitor

@search_monitor
def search(self, query: str, ...):
    # 原有代码不变
    pass

@vector_search_monitor
def _search_vector_store(self, query, filters, limit, threshold=None):
    # 原有代码不变
    pass
```

## 运行测试

1. **启动Mem0服务**：
```bash
cd mem0
python -m uvicorn server.main:app --host 0.0.0.0 --port 18088
```

2. **运行性能测试**：
```bash
cd mem0
python performance_monitoring/test_performance.py
```

3. **查看性能日志**：
```bash
tail -f /tmp/mem0_performance_test.log
```

## 日志格式

性能日志以JSON格式输出，每行一条记录：

```json
{"step": "search.build_filters", "duration_ms": 0.123, "timestamp": "2024-01-15T10:30:00", "filter_count": 2}
{"step": "vector_search.embedding", "duration_ms": 45.678, "timestamp": "2024-01-15T10:30:00", "query_length": 20}
{"step": "vector_search.database_search", "duration_ms": 89.012, "timestamp": "2024-01-15T10:30:00", "limit": 100}
{"event": "search_summary", "total_duration_ms": 150.456, "query_length": 20, "result_count": 5}
```

## 监控的关键步骤

### Search方法监控点：
- `search.build_filters` - 过滤器构建耗时
- `search.concurrent_execution` - 并发搜索执行耗时
- `search.format_result` - 结果格式化耗时
- `search_summary` - 搜索总结（总耗时、结果数等）

### Vector Search监控点：
- `vector_search.embedding` - 查询向量化耗时
- `vector_search.database_search` - 向量数据库搜索耗时
- `vector_search.result_processing` - 结果处理耗时

## 性能分析

测试脚本会自动分析性能日志并输出统计信息：

```
性能步骤统计:
================================================================================
步骤                            次数      平均(ms)     最小(ms)     最大(ms)
================================================================================
search.build_filters            10        0.2          0.1          0.5
vector_search.embedding          10        45.3         40.1         52.7
vector_search.database_search     10        89.7         78.2         105.3
vector_search.result_processing   10        2.1          1.8          3.2
search.concurrent_execution       10        135.6        120.5        155.8
```

## 配置选项

### 自定义日志文件路径：
```python
from performance_monitoring.performance_logger import enable_performance_logging
enable_performance_logging("/your/custom/path/mem0_perf.log")
```

### 禁用性能监控：
```python
from performance_monitoring.performance_logger import disable_performance_logging
disable_performance_logging()
```

## 注意事项

1. **性能开销**：埋点代码的性能开销极小（通常<1ms），不会影响正常业务
2. **日志轮转**：建议定期清理日志文件，或使用系统的日志轮转功能
3. **生产环境**：可以通过环境变量控制是否启用性能监控
4. **并发安全**：日志记录器是线程安全的，支持并发场景

## 故障排除

1. **导入错误**：确保performance_monitoring文件夹在正确的位置
2. **权限问题**：确保有写入日志文件的权限
3. **API不可用**：确保Mem0服务正在运行且端口正确

## 扩展使用

你可以很容易地扩展这个系统来监控其他方法：

```python
# 监控任意方法
if PERFORMANCE_MONITORING_ENABLED:
    perf_logger = get_performance_logger()
    start = perf_logger.start_timer()

# ... 你的代码 ...

if PERFORMANCE_MONITORING_ENABLED:
    duration = perf_logger.end_timer(start)
    perf_logger.log_step("your_method_name", duration, {"context": "info"})
```

这个性能监控系统设计简单、侵入性小，可以帮助你快速定位性能瓶颈。