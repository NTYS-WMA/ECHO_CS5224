# POST /search API 详细分析文档

## 概述

本文档详细分析了Mem0项目中POST `/search` API的完整工作流程，包括如何将自然语言查询转换为向量搜索，以及搜索结果的排序、过滤和返回机制。

## API入口点

### HTTP端点
- **URL**: `POST http://localhost:18088/search`
- **实现位置**: `server/main.py:141-149`
- **处理函数**: `search_memories(search_req: SearchRequest)`

```python
@app.post("/search", summary="Search memories")
def search_memories(search_req: SearchRequest):
    """Search for memories based on a query."""
    try:
        params = {k: v for k, v in search_req.model_dump().items() if v is not None and k != "query"}
        return MEMORY_INSTANCE.search(query=search_req.query, **params)
    except Exception as e:
        logging.exception("Error in search_memories:")
        raise HTTPException(status_code=500, detail=str(e))
```

### 请求格式 (`server/main.py:81-86`)
```python
class SearchRequest(BaseModel):
    query: str = Field(..., description="Search query.")
    user_id: Optional[str] = None
    run_id: Optional[str] = None
    agent_id: Optional[str] = None
    filters: Optional[Dict[str, Any]] = None
```

#### 请求参数详解
- **query** (必需): 自然语言搜索查询，例如："我喜欢什么食物？"
- **user_id** (可选): 用户标识符，用于范围搜索
- **agent_id** (可选): 代理标识符，用于范围搜索
- **run_id** (可选): 运行标识符，用于范围搜索
- **filters** (可选): 额外的自定义过滤条件

### 请求示例
```json
{
    "query": "告诉我关于用户的饮食偏好",
    "user_id": "user123",
    "filters": {
        "actor_id": "assistant",
        "category": "food_preferences"
    },
    "limit": 50,
    "threshold": 0.7
}
```

## 核心处理流程

### 1. Memory.search() 方法入口
**位置**: `mem0/memory/main.py:623-697`

```python
def search(
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
```

#### 1.1 参数验证和过滤器构建
**调用**: `_build_filters_and_metadata()` (`mem0/memory/main.py:46-119`)

```python
_, effective_filters = _build_filters_and_metadata(
    user_id=user_id, agent_id=agent_id, run_id=run_id, input_filters=filters
)

if not any(key in effective_filters for key in ("user_id", "agent_id", "run_id")):
    raise ValueError("At least one of 'user_id', 'agent_id', or 'run_id' must be specified.")
```

**功能**:
- 构建有效的查询过滤器，合并会话标识符和自定义过滤器
- 验证必须提供至少一个会话标识符
- 支持多会话标识符组合搜索

#### 1.2 遥测数据处理
**调用**: `process_telemetry_filters()` (`mem0/memory/utils.py:118-133`)

```python
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
```

**功能**: 对敏感标识符进行MD5哈希处理，用于安全的遥测数据收集。

#### 1.3 并发搜索执行
**位置**: `mem0/memory/main.py:671-682`

```python
with concurrent.futures.ThreadPoolExecutor() as executor:
    future_memories = executor.submit(self._search_vector_store, query, effective_filters, limit, threshold)
    future_graph_entities = (
        executor.submit(self.graph.search, query, effective_filters, limit) if self.enable_graph else None
    )

    concurrent.futures.wait(
        [future_memories, future_graph_entities] if future_graph_entities else [future_memories]
    )

    original_memories = future_memories.result()
    graph_entities = future_graph_entities.result() if future_graph_entities else None
```

**功能**: 同时执行向量搜索和图搜索（如果启用），提高搜索效率。

#### 1.4 结果格式化
**位置**: `mem0/memory/main.py:684-697`

```python
if self.enable_graph:
    return {"results": original_memories, "relations": graph_entities}

if self.api_version == "v1.0":
    warnings.warn(
        "The current search API output format is deprecated. "
        "To use the latest format, set `api_version='v1.1'`. "
        "The current format will be removed in mem0ai 1.1.0 and later versions.",
        category=DeprecationWarning,
        stacklevel=2,
    )
    return {"results": original_memories}
else:
    return {"results": original_memories}
```

## 向量搜索核心实现

### 1. _search_vector_store() 方法
**位置**: `mem0/memory/main.py:699-735`

#### 1.1 查询向量化
**位置**: `mem0/memory/main.py:700-701`

```python
def _search_vector_store(self, query, filters, limit, threshold: Optional[float] = None):
    embeddings = self.embedding_model.embed(query, "search")
    memories = self.vector_store.search(query=query, vectors=embeddings, limit=limit, filters=filters)
```

**流程**:
1. **嵌入生成**: 使用配置的嵌入模型（如OpenAI text-embedding-3-small）将查询文本转换为向量
2. **向量搜索**: 在向量数据库中执行相似性搜索
3. **相似度计算**: 使用余弦相似度等算法计算查询向量与存储向量的相似性

#### 1.2 元数据字段定义
**位置**: `mem0/memory/main.py:703-711`

```python
promoted_payload_keys = [
    "user_id",
    "agent_id",
    "run_id",
    "actor_id",
    "role",
]

core_and_promoted_keys = {"data", "hash", "created_at", "updated_at", "id", *promoted_payload_keys}
```

**功能**: 定义需要提升到顶级字段的元数据键，便于客户端访问。

#### 1.3 搜索结果处理和格式化
**位置**: `mem0/memory/main.py:713-735`

```python
original_memories = []
for mem in memories:
    # 创建标准化的记忆项
    memory_item_dict = MemoryItem(
        id=mem.id,
        memory=mem.payload["data"],
        hash=mem.payload.get("hash"),
        created_at=mem.payload.get("created_at"),
        updated_at=mem.payload.get("updated_at"),
        score=mem.score,  # 相似度分数
    ).model_dump()

    # 提升重要元数据字段到顶级
    for key in promoted_payload_keys:
        if key in mem.payload:
            memory_item_dict[key] = mem.payload[key]

    # 处理额外的元数据
    additional_metadata = {k: v for k, v in mem.payload.items() if k not in core_and_promoted_keys}
    if additional_metadata:
        memory_item_dict["metadata"] = additional_metadata

    # 阈值过滤
    if threshold is None or mem.score >= threshold:
        original_memories.append(memory_item_dict)

return original_memories
```

### 2. MemoryItem 数据模型
**位置**: `mem0/configs/base.py:16-27`

```python
class MemoryItem(BaseModel):
    id: str = Field(..., description="The unique identifier for the text data")
    memory: str = Field(..., description="The memory deduced from the text data")
    hash: Optional[str] = Field(None, description="The hash of the memory")
    metadata: Optional[Dict[str, Any]] = Field(None, description="Additional metadata for the text data")
    score: Optional[float] = Field(None, description="The score associated with the text data")
    created_at: Optional[str] = Field(None, description="The timestamp when the memory was created")
    updated_at: Optional[str] = Field(None, description="The timestamp when the memory was updated")
```

## 异步搜索实现

### AsyncMemory.search() 方法
**位置**: `mem0/memory/main.py:1485-1562`

#### 主要差异
1. **异步向量化**: 使用 `asyncio.to_thread()` 包装同步的嵌入生成
2. **异步任务管理**: 使用 `asyncio.create_task()` 和 `asyncio.gather()` 管理并发任务
3. **智能图搜索**: 自动检测图搜索方法是否为异步

```python
async def _search_vector_store(self, query, filters, limit, threshold: Optional[float] = None):
    embeddings = await asyncio.to_thread(self.embedding_model.embed, query, "search")
    memories = await asyncio.to_thread(
        self.vector_store.search, query=query, vectors=embeddings, limit=limit, filters=filters
    )
    # ... 后续处理逻辑与同步版本相同
```

## 搜索功能特性

### 1. 多模态搜索
- **向量搜索**: 基于语义相似度的高精度搜索
- **图搜索**: 基于实体关系的结构化搜索（可选）
- **混合结果**: 同时返回向量匹配和关系匹配结果

### 2. 灵活的过滤机制

#### 会话级过滤
```python
# 单会话搜索
{"user_id": "user123"}

# 多会话组合搜索
{"user_id": "user123", "agent_id": "assistant"}
```

#### 自定义过滤器
```python
{
    "actor_id": "user",        # 按消息发送者过滤
    "role": "assistant",       # 按角色过滤
    "category": "preferences", # 按自定义分类过滤
    "timestamp": "2024-01-01"  # 按时间过滤
}
```

### 3. 结果质量控制

#### 相似度阈值
```python
threshold = 0.7  # 只返回相似度≥0.7的结果
```

#### 结果数量限制
```python
limit = 50  # 最多返回50个结果
```

#### 自动排序
- 结果按相似度分数降序排列
- 分数范围通常为0.0-1.0，1.0表示完全匹配

### 4. 元数据丰富性

#### 核心字段
- **id**: 唯一标识符
- **memory**: 记忆内容
- **score**: 相似度分数
- **created_at/updated_at**: 时间戳

#### 上下文字段
- **user_id/agent_id/run_id**: 会话标识符
- **actor_id**: 消息发送者
- **role**: 角色信息

#### 扩展元数据
- **hash**: 内容哈希值
- **metadata**: 自定义元数据对象

## 响应格式

### 标准响应 (API v1.1+)
```json
{
    "results": [
        {
            "id": "uuid-1234-5678-9012",
            "memory": "用户喜欢意大利面和披萨",
            "score": 0.92,
            "hash": "a1b2c3d4e5f6",
            "created_at": "2024-01-15T10:30:00-08:00",
            "updated_at": "2024-01-16T14:20:00-08:00",
            "user_id": "user123",
            "agent_id": "food_assistant",
            "actor_id": "user",
            "role": "user",
            "metadata": {
                "category": "food_preferences",
                "confidence": 0.95,
                "source": "conversation"
            }
        }
    ]
}
```

### 图增强响应 (启用图存储时)
```json
{
    "results": [
        {
            "id": "uuid-1234-5678-9012",
            "memory": "用户喜欢意大利面和披萨",
            "score": 0.92,
            // ... 其他字段
        }
    ],
    "relations": [
        {
            "source": "用户",
            "relationship": "喜欢",
            "destination": "意大利面",
            "weight": 0.9
        },
        {
            "source": "用户",
            "relationship": "喜欢",
            "destination": "披萨",
            "weight": 0.85
        }
    ]
}
```

## 搜索算法流程

### 1. 查询预处理
1. **输入验证**: 检查必需参数和格式
2. **过滤器构建**: 合并会话标识符和自定义过滤器
3. **权限检查**: 确保用户只能搜索授权范围内的记忆

### 2. 向量搜索阶段
1. **查询向量化**: 将自然语言查询转换为密集向量表示
2. **相似度计算**: 在向量空间中计算查询与存储记忆的相似度
3. **初步排序**: 按相似度分数降序排列候选结果

### 3. 过滤和精排
1. **会话过滤**: 根据user_id/agent_id/run_id限制搜索范围
2. **自定义过滤**: 应用额外的元数据过滤条件
3. **阈值过滤**: 移除低于指定相似度阈值的结果
4. **数量限制**: 截取top-K结果

### 4. 结果后处理
1. **元数据提升**: 将重要字段提升到顶级
2. **格式标准化**: 转换为统一的MemoryItem格式
3. **额外信息**: 添加搜索上下文和调试信息

## 性能优化策略

### 1. 并发搜索
- **向量搜索和图搜索并行执行**
- **使用ThreadPoolExecutor避免阻塞**
- **异步版本支持更高并发**

### 2. 缓存机制
- **嵌入向量缓存**: 避免重复计算常见查询的向量
- **结果缓存**: 缓存频繁查询的搜索结果
- **连接池**: 复用数据库连接

### 3. 索引优化
- **向量索引**: 使用HNSW、IVF等高效向量索引
- **元数据索引**: 为过滤字段建立B-tree索引
- **复合索引**: 为常见查询模式优化索引组合

### 4. 查询优化
- **早期终止**: 达到足够结果时提前结束搜索
- **分页搜索**: 支持大结果集的分页返回
- **预过滤**: 在向量搜索前应用廉价的元数据过滤

## 错误处理

### 1. 输入验证错误
```python
# 缺少会话标识符
raise ValueError("At least one of 'user_id', 'agent_id', or 'run_id' must be specified.")

# 无效的查询格式
raise ValueError("Query must be a non-empty string.")
```

### 2. 搜索执行错误
```python
# 向量化失败
logger.error(f"Failed to embed query: {query}")

# 向量数据库连接失败
logger.error(f"Vector store search failed: {e}")
```

### 3. 结果处理错误
```python
# 结果格式化失败
logger.warning(f"Failed to format memory item: {mem_id}")

# 阈值过滤异常
logger.error(f"Invalid threshold value: {threshold}")
```

## 使用场景示例

### 1. 个性化推荐
```json
{
    "query": "推荐一些用户可能喜欢的电影",
    "user_id": "user123",
    "filters": {"category": "entertainment"},
    "limit": 10,
    "threshold": 0.8
}
```

### 2. 对话上下文检索
```json
{
    "query": "用户之前提到的会议安排",
    "user_id": "user123",
    "agent_id": "calendar_assistant",
    "filters": {"role": "user"},
    "limit": 5
}
```

### 3. 知识库搜索
```json
{
    "query": "关于Python编程的技巧",
    "agent_id": "coding_assistant",
    "filters": {"topic": "programming"},
    "limit": 20,
    "threshold": 0.7
}
```

## 总结

POST `/search` API提供了强大而灵活的记忆搜索功能：

### 核心优势
1. **语义理解**: 基于向量嵌入的深度语义搜索
2. **灵活过滤**: 支持多维度、多层级的结果过滤
3. **高性能**: 并发执行和智能索引优化
4. **可扩展**: 支持图搜索等扩展功能

### 技术特点
1. **向量化查询**: 将自然语言转换为高维向量表示
2. **相似度计算**: 使用数学距离度量语义相似性
3. **多模态搜索**: 结合向量搜索和图搜索结果
4. **智能排序**: 按相似度和相关性自动排序

这种设计使得用户可以用自然语言查询复杂的记忆信息，系统能够理解查询意图并返回最相关的结果，是现代AI应用中记忆检索的核心实现。