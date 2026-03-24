# Logging Guide

本文档说明如何使用和配置 Mem0 服务的日志系统。

## 概述

Mem0 服务实现了分层日志系统，支持不同详细程度的日志输出。日志通过 `LOG_LEVEL` 环境变量控制。

## 日志级别

### INFO（默认）
**用途**: 日常运维监控

**输出内容**:
- HTTP 请求基本信息（方法、路径、状态码、耗时）
- 系统初始化信息
- 错误和异常

**示例**:
```
2025-10-04 23:30:15,123 - main - INFO - Mem0 Memory and UserProfile instances initialized successfully
2025-10-04 23:30:15,124 - main - INFO - Logging level set to: INFO
2025-10-04 23:30:20,456 - main - INFO - → POST /profile
2025-10-04 23:30:22,789 - main - INFO - ← POST /profile - Status: 200 - Duration: 2.333s
```

### DEBUG
**用途**: 开发调试、问题诊断

**输出内容**（除 INFO 级别外，还包括）:
- 请求查询参数
- 请求 body 数据（摘要）
- 响应数据（摘要）
- LLM 调用详情
- 数据库操作详情
- Profile 提取/更新过程

**示例**:
```
2025-10-04 23:30:20,456 - main - INFO - → POST /profile
2025-10-04 23:30:20,457 - main - DEBUG - Query params: {}
2025-10-04 23:30:20,458 - main - DEBUG - [set_profile] Request body: {user_id: test_001, messages: 3 items, first: '我叫张三，今年25岁...'}
2025-10-04 23:30:21,123 - mem0.user_profile.profile_manager - DEBUG - Stage 1: Extracting profile information from messages
2025-10-04 23:30:22,456 - mem0.user_profile.profile_manager - DEBUG - Stage 3: Deciding operations (ADD/UPDATE/DELETE)
2025-10-04 23:30:22,789 - main - DEBUG - [set_profile] Response: {success: True, operations: {'added': 2, 'updated': 0, 'deleted': 0}}
2025-10-04 23:30:22,790 - main - INFO - ← POST /profile - Status: 200 - Duration: 2.333s
```

## 配置方法

### 方法 1: 环境变量（推荐）

在 `.env` 文件中设置：
```bash
LOG_LEVEL=DEBUG
```

然后启动服务：
```bash
docker-compose up -d
```

### 方法 2: Docker Compose 命令行

临时使用 DEBUG 模式：
```bash
LOG_LEVEL=DEBUG docker-compose up
```

### 方法 3: Docker 运行时

如果直接运行 Docker 容器：
```bash
docker run -e LOG_LEVEL=DEBUG mem0-service
```

## 查看日志

### 实时查看所有日志
```bash
docker-compose logs -f mem0-service
```

### 查看最近 N 条日志
```bash
docker-compose logs --tail 100 mem0-service
```

### 查看特定时间的日志
```bash
docker-compose logs --since 10m mem0-service  # 最近10分钟
docker-compose logs --since "2025-10-04T23:00:00" mem0-service  # 指定时间
```

### 过滤特定类型的日志
```bash
# 只看 UserProfile 相关日志
docker-compose logs mem0-service | grep "mem0.user_profile"

# 只看错误
docker-compose logs mem0-service | grep "ERROR"

# 只看某个端点
docker-compose logs mem0-service | grep "/profile"
```

## 日志结构

### 日志格式
```
时间戳 - 模块名 - 级别 - 消息
```

### 模块命名
- `main`: FastAPI 主应用
- `middleware`: HTTP 中间件
- `mem0.user_profile`: UserProfile 模块
- `mem0.user_profile.profile_manager`: Profile 管理器
- `mem0.user_profile.database.postgres_manager`: PostgreSQL 管理器
- `mem0.user_profile.database.mongodb_manager`: MongoDB 管理器

## 使用场景

### 场景 1: 日常运维
**配置**: `LOG_LEVEL=INFO`

**用途**:
- 监控请求量和响应时间
- 发现异常和错误
- 追踪慢请求

### 场景 2: 性能调优
**配置**: `LOG_LEVEL=INFO`

**用途**:
- 分析请求耗时
- 识别性能瓶颈
- 监控 LLM 调用频率

**分析方法**:
```bash
# 查看慢请求（耗时 > 5秒）
docker-compose logs mem0-service | grep "Duration:" | awk '{print $NF}' | grep -E "[5-9]\.[0-9]+s|[0-9]{2}\.[0-9]+s"
```

### 场景 3: 功能调试
**配置**: `LOG_LEVEL=DEBUG`

**用途**:
- 调试新功能
- 分析 LLM 提取结果
- 排查数据不一致问题

**调试流程**:
1. 设置 `LOG_LEVEL=DEBUG`
2. 重启服务: `docker-compose restart mem0-service`
3. 发送测试请求
4. 查看详细日志
5. 定位问题
6. 修复后改回 `LOG_LEVEL=INFO`

### 场景 4: 问题诊断
**配置**: `LOG_LEVEL=DEBUG`

**用途**:
- 排查 bug
- 理解数据流
- 分析 LLM 决策过程

**诊断示例**:
```bash
# 追踪某个 user_id 的所有操作
docker-compose logs mem0-service | grep "test_user_001"

# 查看某个请求的完整流程
docker-compose logs --since "2025-10-04T23:30:00" mem0-service | grep -A 20 "POST /profile"
```

## 日志数据保护

### 敏感信息处理
中间件自动处理敏感信息：
- ✅ 请求 body 自动截断（最多 200 字符）
- ✅ messages 数组显示数量，不完全展开
- ✅ API keys 不会出现在日志中
- ✅ 用户原始内容仅显示摘要

### DEBUG 模式注意事项
⚠️ **DEBUG 模式会记录较多数据，生产环境慎用！**

生产环境建议：
- 默认使用 INFO 级别
- 仅在排查问题时临时开启 DEBUG
- DEBUG 开启后及时关闭
- 定期清理旧日志

## 日志轮转

Docker logs 会自动轮转，配置在 `docker-compose.yaml`:

```yaml
logging:
  driver: "json-file"
  options:
    max-size: "10m"
    max-file: "3"
```

这意味着：
- 单个日志文件最大 10MB
- 最多保留 3 个文件
- 总日志大小约 30MB

## 性能影响

### INFO 级别
- ✅ 性能影响极小（< 1%）
- ✅ 适合生产环境
- ✅ 可以长期开启

### DEBUG 级别
- ⚠️ 性能影响约 5-10%
- ⚠️ 日志量增加 10-20 倍
- ⚠️ 仅用于调试，不建议生产环境长期开启

## 自定义日志

如果需要添加自定义日志，可以在代码中使用 Python logging：

```python
import logging

logger = logging.getLogger(__name__)

# 始终显示（ERROR, WARNING, INFO）
logger.info("User profile updated successfully")
logger.warning("Evidence count exceeds limit")
logger.error("Failed to connect to database")

# 仅在 DEBUG 模式显示
logger.debug("Extracted data: %s", extracted_data)
logger.debug("LLM response: %s", response)
```

## 故障排查

### 问题: 看不到日志
**解决方法**:
```bash
# 1. 检查容器是否运行
docker ps | grep mem0

# 2. 检查日志驱动
docker inspect mem0-api | grep LogPath

# 3. 直接查看容器 stdout
docker logs mem0-api
```

### 问题: DEBUG 模式不生效
**解决方法**:
```bash
# 1. 确认环境变量设置
docker exec mem0-api env | grep LOG_LEVEL

# 2. 重启容器使配置生效
docker-compose restart mem0-service

# 3. 查看启动日志确认
docker-compose logs mem0-service | grep "Logging level"
```

### 问题: 日志太多
**解决方法**:
```bash
# 1. 降低日志级别
LOG_LEVEL=INFO docker-compose up -d

# 2. 清理旧日志
docker-compose logs --tail 0 mem0-service

# 3. 增加日志轮转限制
# 编辑 docker-compose.yaml, 减小 max-size
```

## 最佳实践

### 开发环境
```bash
LOG_LEVEL=DEBUG
```
- 方便调试
- 理解数据流
- 快速定位问题

### 测试环境
```bash
LOG_LEVEL=INFO
```
- 监控测试执行
- 记录关键操作
- 平衡性能和信息量

### 生产环境
```bash
LOG_LEVEL=INFO
```
- 最小性能影响
- 足够的运维信息
- 遇到问题时临时开启 DEBUG

## 总结

| 功能 | INFO | DEBUG |
|------|------|-------|
| HTTP 请求日志 | ✅ | ✅ |
| 请求参数 | ❌ | ✅ |
| 请求 body | ❌ | ✅ (摘要) |
| 响应数据 | ❌ | ✅ (摘要) |
| LLM 调用详情 | ❌ | ✅ |
| 数据库操作 | ❌ | ✅ |
| Profile 提取过程 | ❌ | ✅ |
| 性能影响 | < 1% | 5-10% |
| 生产环境 | ✅ 推荐 | ⚠️ 临时使用 |

**推荐配置**: 默认使用 `LOG_LEVEL=INFO`，遇到问题时临时开启 `DEBUG`。
