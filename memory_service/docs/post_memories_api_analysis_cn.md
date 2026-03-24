# POST /memories API 详细分析文档

## 概述

本文档详细分析了Mem0项目中POST `/memories` API的完整工作流程，包括如何将自然语言输入转换为结构化记忆点，以及新增、更新、删除记忆的决策机制。

## API入口点

### HTTP端点
- **URL**: `POST http://localhost:18088/memories`
- **实现位置**: `server/main.py:97-109`
- **处理函数**: `add_memory(memory_create: MemoryCreate)`

```python
@app.post("/memories", summary="Create memories")
def add_memory(memory_create: MemoryCreate):
    """Store new memories."""
    if not any([memory_create.user_id, memory_create.agent_id, memory_create.run_id]):
        raise HTTPException(status_code=400, detail="At least one identifier (user_id, agent_id, run_id) is required.")

    params = {k: v for k, v in memory_create.model_dump().items() if v is not None and k != "messages"}
    try:
        response = MEMORY_INSTANCE.add(messages=[m.model_dump() for m in memory_create.messages], **params)
        return JSONResponse(content=response)
    except Exception as e:
        logging.exception("Error in add_memory:")
        raise HTTPException(status_code=500, detail=str(e))
```

### 请求格式 (`server/main.py:73-78`)
```python
class MemoryCreate(BaseModel):
    messages: List[Message] = Field(..., description="List of messages to store.")
    user_id: Optional[str] = None
    agent_id: Optional[str] = None
    run_id: Optional[str] = None
    metadata: Optional[Dict[str, Any]] = None
```

## 核心处理流程

### 1. Memory.add() 方法入口
**位置**: `mem0/memory/main.py:190-287`

```python
def add(
    self,
    messages,
    *,
    user_id: Optional[str] = None,
    agent_id: Optional[str] = None,
    run_id: Optional[str] = None,
    metadata: Optional[Dict[str, Any]] = None,
    infer: bool = True,
    memory_type: Optional[str] = None,
    prompt: Optional[str] = None,
):
```

#### 1.1 元数据和过滤器构建
**调用**: `_build_filters_and_metadata()` (`mem0/memory/main.py:46-119`)

```python
processed_metadata, effective_filters = _build_filters_and_metadata(
    user_id=user_id,
    agent_id=agent_id,
    run_id=run_id,
    input_metadata=metadata,
)
```

**功能**: 构建存储元数据模板和查询过滤器，支持多会话标识符(user_id, agent_id, run_id)。

#### 1.2 消息格式标准化
**位置**: `mem0/memory/main.py:244-251`

```python
if isinstance(messages, str):
    messages = [{"role": "user", "content": messages}]
elif isinstance(messages, dict):
    messages = [messages]
elif not isinstance(messages, list):
    raise ValueError("messages must be str, dict, or list[dict]")
```

#### 1.3 视觉消息解析
**调用**: `parse_vision_messages()` (`mem0/memory/utils.py:88-115`)

```python
if self.config.llm.config.get("enable_vision"):
    messages = parse_vision_messages(messages, self.llm, self.config.llm.config.get("vision_details"))
else:
    messages = parse_vision_messages(messages)
```

#### 1.4 并发处理
**位置**: `mem0/memory/main.py:262-286`

```python
with concurrent.futures.ThreadPoolExecutor() as executor:
    future1 = executor.submit(self._add_to_vector_store, messages, processed_metadata, effective_filters, infer)
    future2 = executor.submit(self._add_to_graph, messages, effective_filters)

    concurrent.futures.wait([future1, future2])

    vector_store_result = future1.result()
    graph_result = future2.result()
```

### 2. 向量存储处理 (_add_to_vector_store)

**位置**: `mem0/memory/main.py:289-460`

#### 2.1 非推理模式处理
**位置**: `mem0/memory/main.py:290-324`

当`infer=False`时，直接将每条消息作为原始记忆存储，不进行智能分析。

```python
if not infer:
    returned_memories = []
    for message_dict in messages:
        # 验证消息格式
        if (not isinstance(message_dict, dict) or
            message_dict.get("role") is None or
            message_dict.get("content") is None):
            logger.warning(f"Skipping invalid message format: {message_dict}")
            continue

        # 跳过系统消息
        if message_dict["role"] == "system":
            continue

        # 构建每条消息的元数据
        per_msg_meta = deepcopy(metadata)
        per_msg_meta["role"] = message_dict["role"]

        # 处理actor_id
        actor_name = message_dict.get("name")
        if actor_name:
            per_msg_meta["actor_id"] = actor_name

        # 生成嵌入向量并创建记忆
        msg_content = message_dict["content"]
        msg_embeddings = self.embedding_model.embed(msg_content, "add")
        mem_id = self._create_memory(msg_content, msg_embeddings, per_msg_meta)
```

#### 2.2 智能推理模式处理
**位置**: `mem0/memory/main.py:326-460`

##### 2.2.1 消息解析
**调用**: `parse_messages()` (`mem0/memory/utils.py:11-20`)

```python
parsed_messages = parse_messages(messages)
```

**功能**: 将消息列表转换为纯文本格式，便于LLM处理：
```python
def parse_messages(messages):
    response = ""
    for msg in messages:
        if msg["role"] == "system":
            response += f"system: {msg['content']}\n"
        if msg["role"] == "user":
            response += f"user: {msg['content']}\n"
        if msg["role"] == "assistant":
            response += f"assistant: {msg['content']}\n"
    return response
```

##### 2.2.2 事实提取阶段

**获取提示词**: `get_fact_retrieval_messages()` (`mem0/memory/utils.py:7-8`)

```python
if self.config.custom_fact_extraction_prompt:
    system_prompt = self.config.custom_fact_extraction_prompt
    user_prompt = f"Input:\n{parsed_messages}"
else:
    system_prompt, user_prompt = get_fact_retrieval_messages(parsed_messages)
```

**事实提取提示词**: `FACT_RETRIEVAL_PROMPT` (`mem0/configs/prompts.py:14-59`)

这个提示词指导LLM从对话中提取关键事实，包括：
- 个人偏好
- 重要个人详情
- 计划和意图
- 活动和服务偏好
- 健康和健身偏好
- 专业信息
- 其他杂项信息

**LLM调用**: (`mem0/memory/main.py:334-340`)
```python
response = self.llm.generate_response(
    messages=[
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": user_prompt},
    ],
    response_format={"type": "json_object"},
)
```

**结果解析**: (`mem0/memory/main.py:342-347`)
```python
try:
    response = remove_code_blocks(response)  # 移除代码块标记
    new_retrieved_facts = json.loads(response)["facts"]
except Exception as e:
    logger.error(f"Error in new_retrieved_facts: {e}")
    new_retrieved_facts = []
```

**示例输出**:
```json
{"facts": ["Name is John", "Is a Software engineer", "Likes pizza"]}
```

##### 2.2.3 相似记忆检索阶段

**位置**: `mem0/memory/main.py:352-369`

对每个提取的事实进行相似性搜索：

```python
retrieved_old_memory = []
new_message_embeddings = {}
for new_mem in new_retrieved_facts:
    # 生成嵌入向量
    messages_embeddings = self.embedding_model.embed(new_mem, "add")
    new_message_embeddings[new_mem] = messages_embeddings

    # 在现有记忆中搜索相似项
    existing_memories = self.vector_store.search(
        query=new_mem,
        vectors=messages_embeddings,
        limit=5,  # 最多返回5个相似记忆
        filters=filters,
    )

    # 收集相似记忆
    for mem in existing_memories:
        retrieved_old_memory.append({"id": mem.id, "text": mem.payload["data"]})
```

**去重处理**: (`mem0/memory/main.py:366-369`)
```python
unique_data = {}
for item in retrieved_old_memory:
    unique_data[item["id"]] = item
retrieved_old_memory = list(unique_data.values())
```

##### 2.2.4 UUID映射机制

**位置**: `mem0/memory/main.py:372-376`

为避免LLM在处理UUID时产生幻觉，使用临时数字ID：

```python
temp_uuid_mapping = {}
for idx, item in enumerate(retrieved_old_memory):
    temp_uuid_mapping[str(idx)] = item["id"]  # 数字ID -> UUID映射
    retrieved_old_memory[idx]["id"] = str(idx)  # 替换为数字ID
```

##### 2.2.5 记忆决策阶段

**获取决策提示词**: `get_update_memory_messages()` (`mem0/configs/prompts.py:291-345`)

```python
if new_retrieved_facts:
    function_calling_prompt = get_update_memory_messages(
        retrieved_old_memory,
        new_retrieved_facts,
        self.config.custom_update_memory_prompt
    )
```

**决策提示词结构**: `DEFAULT_UPDATE_MEMORY_PROMPT` (`mem0/configs/prompts.py:61-209`)

这个详细的提示词定义了四种操作类型：

1. **ADD**: 添加全新信息
2. **UPDATE**: 更新已存在但信息更丰富的记忆
3. **DELETE**: 删除矛盾的信息
4. **NONE**: 无需更改

**LLM决策调用**: (`mem0/memory/main.py:384-390`)
```python
try:
    response: str = self.llm.generate_response(
        messages=[{"role": "user", "content": function_calling_prompt}],
        response_format={"type": "json_object"},
    )
except Exception as e:
    logger.error(f"Error in new memory actions response: {e}")
    response = ""
```

**决策结果解析**: (`mem0/memory/main.py:392-403`)
```python
try:
    if not response or not response.strip():
        logger.warning("Empty response from LLM, no memories to extract")
        new_memories_with_actions = {}
    else:
        response = remove_code_blocks(response)
        new_memories_with_actions = json.loads(response)
except Exception as e:
    logger.error(f"Invalid JSON response: {e}")
    new_memories_with_actions = {}
```

##### 2.2.6 记忆操作执行

**位置**: `mem0/memory/main.py:405-452`

根据LLM的决策结果执行相应操作：

```python
returned_memories = []
try:
    for resp in new_memories_with_actions.get("memory", []):
        logger.info(resp)
        try:
            action_text = resp.get("text")
            if not action_text:
                logger.info("Skipping memory entry because of empty `text` field.")
                continue

            event_type = resp.get("event")
            if event_type == "ADD":
                memory_id = self._create_memory(
                    data=action_text,
                    existing_embeddings=new_message_embeddings,
                    metadata=deepcopy(metadata),
                )
                returned_memories.append({
                    "id": memory_id,
                    "memory": action_text,
                    "event": event_type
                })

            elif event_type == "UPDATE":
                self._update_memory(
                    memory_id=temp_uuid_mapping[resp.get("id")],  # 映射回真实UUID
                    data=action_text,
                    existing_embeddings=new_message_embeddings,
                    metadata=deepcopy(metadata),
                )
                returned_memories.append({
                    "id": temp_uuid_mapping[resp.get("id")],
                    "memory": action_text,
                    "event": event_type,
                    "previous_memory": resp.get("old_memory"),
                })

            elif event_type == "DELETE":
                self._delete_memory(memory_id=temp_uuid_mapping[resp.get("id")])
                returned_memories.append({
                    "id": temp_uuid_mapping[resp.get("id")],
                    "memory": action_text,
                    "event": event_type,
                })

            elif event_type == "NONE":
                logger.info("NOOP for Memory.")
        except Exception as e:
            logger.error(f"Error processing memory action: {resp}, Error: {e}")
except Exception as e:
    logger.error(f"Error iterating new_memories_with_actions: {e}")
```

## 记忆操作实现

### 1. 创建记忆 (_create_memory)

**位置**: `mem0/memory/main.py:818-845`

```python
def _create_memory(self, data, existing_embeddings, metadata=None):
    logger.debug(f"Creating memory with {data=}")

    # 获取或生成嵌入向量
    if data in existing_embeddings:
        embeddings = existing_embeddings[data]
    else:
        embeddings = self.embedding_model.embed(data, memory_action="add")

    # 生成唯一ID
    memory_id = str(uuid.uuid4())
    metadata = metadata or {}
    metadata["data"] = data
    metadata["hash"] = hashlib.md5(data.encode()).hexdigest()
    metadata["created_at"] = datetime.now(pytz.timezone("US/Pacific")).isoformat()

    # 插入向量数据库
    self.vector_store.insert(
        vectors=[embeddings],
        ids=[memory_id],
        payloads=[metadata],
    )

    # 记录历史
    self.db.add_history(
        memory_id,
        None,  # 之前的值为None
        data,  # 新值
        "ADD",  # 操作类型
        created_at=metadata.get("created_at"),
        actor_id=metadata.get("actor_id"),
        role=metadata.get("role"),
    )

    capture_event("mem0._create_memory", self, {"memory_id": memory_id, "sync_type": "sync"})
    return memory_id
```

### 2. 更新记忆 (_update_memory)

**位置**: `mem0/memory/main.py:885-937`

```python
def _update_memory(self, memory_id, data, existing_embeddings, metadata=None):
    logger.info(f"Updating memory with {data=}")

    try:
        existing_memory = self.vector_store.get(vector_id=memory_id)
    except Exception:
        logger.error(f"Error getting memory with ID {memory_id} during update.")
        raise ValueError(f"Error getting memory with ID {memory_id}. Please provide a valid 'memory_id'")

    prev_value = existing_memory.payload.get("data")

    # 构建新的元数据
    new_metadata = deepcopy(metadata) if metadata is not None else {}
    new_metadata["data"] = data
    new_metadata["hash"] = hashlib.md5(data.encode()).hexdigest()
    new_metadata["created_at"] = existing_memory.payload.get("created_at")
    new_metadata["updated_at"] = datetime.now(pytz.timezone("US/Pacific")).isoformat()

    # 保留原有的会话标识符
    for key in ["user_id", "agent_id", "run_id", "actor_id", "role"]:
        if key in existing_memory.payload:
            new_metadata[key] = existing_memory.payload[key]

    # 获取或生成新的嵌入向量
    if data in existing_embeddings:
        embeddings = existing_embeddings[data]
    else:
        embeddings = self.embedding_model.embed(data, "update")

    # 更新向量数据库
    self.vector_store.update(
        vector_id=memory_id,
        vector=embeddings,
        payload=new_metadata,
    )

    # 记录历史
    self.db.add_history(
        memory_id,
        prev_value,  # 之前的值
        data,        # 新值
        "UPDATE",    # 操作类型
        created_at=new_metadata["created_at"],
        updated_at=new_metadata["updated_at"],
        actor_id=new_metadata.get("actor_id"),
        role=new_metadata.get("role"),
    )

    capture_event("mem0._update_memory", self, {"memory_id": memory_id, "sync_type": "sync"})
    return memory_id
```

### 3. 删除记忆 (_delete_memory)

**位置**: `mem0/memory/main.py:939-954`

```python
def _delete_memory(self, memory_id):
    logger.info(f"Deleting memory with {memory_id=}")

    # 获取现有记忆以保存历史记录
    existing_memory = self.vector_store.get(vector_id=memory_id)
    prev_value = existing_memory.payload["data"]

    # 从向量数据库删除
    self.vector_store.delete(vector_id=memory_id)

    # 记录删除历史
    self.db.add_history(
        memory_id,
        prev_value,  # 被删除的值
        None,        # 新值为None
        "DELETE",    # 操作类型
        actor_id=existing_memory.payload.get("actor_id"),
        role=existing_memory.payload.get("role"),
        is_deleted=1,  # 标记为已删除
    )

    capture_event("mem0._delete_memory", self, {"memory_id": memory_id, "sync_type": "sync"})
    return memory_id
```

## 图数据库处理 (_add_to_graph)

**位置**: `mem0/memory/main.py:462-471`

```python
def _add_to_graph(self, messages, filters):
    added_entities = []
    if self.enable_graph:
        if filters.get("user_id") is None:
            filters["user_id"] = "user"  # 默认用户ID

        # 合并所有非系统消息内容
        data = "\n".join([
            msg["content"] for msg in messages
            if "content" in msg and msg["role"] != "system"
        ])

        # 添加到图数据库
        added_entities = self.graph.add(data, filters)

    return added_entities
```

## 工具函数详解

### 1. remove_code_blocks

**位置**: `mem0/memory/utils.py:35-46`

```python
def remove_code_blocks(content: str) -> str:
    """
    移除LLM响应中的代码块标记 ```[language] 和 ```
    """
    pattern = r"^```[a-zA-Z0-9]*\n([\s\S]*?)\n```$"
    match = re.match(pattern, content.strip())
    return match.group(1).strip() if match else content.strip()
```

### 2. process_telemetry_filters

**位置**: `mem0/memory/utils.py:118-133`

```python
def process_telemetry_filters(filters):
    """处理遥测过滤器，对敏感ID进行哈希处理"""
    if filters is None:
        return {}, {}

    encoded_ids = {}
    if "user_id" in filters:
        encoded_ids["user_id"] = hashlib.md5(filters["user_id"].encode()).hexdigest()
    if "agent_id" in filters:
        encoded_ids["agent_id"] = hashlib.md5(filters["agent_id"].encode()).hexdigest()
    if "run_id" in filters:
        encoded_ids["run_id"] = hashlib.md5(filters["run_id"].encode()).hexdigest()

    return list(filters.keys()), encoded_ids
```

## 决策逻辑示例

### ADD操作示例
```json
// 输入：现有记忆为空，新事实：["Name is John"]
// 输出：
{
    "memory": [
        {
            "id": "0",
            "text": "Name is John",
            "event": "ADD"
        }
    ]
}
```

### UPDATE操作示例
```json
// 输入：现有记忆："User likes pizza"，新事实：["Loves cheese and pepperoni pizza"]
// 输出：
{
    "memory": [
        {
            "id": "0",
            "text": "Loves cheese and pepperoni pizza",
            "event": "UPDATE",
            "old_memory": "User likes pizza"
        }
    ]
}
```

### DELETE操作示例
```json
// 输入：现有记忆："Loves cheese pizza"，新事实：["Dislikes cheese pizza"]
// 输出：
{
    "memory": [
        {
            "id": "0",
            "text": "Loves cheese pizza",
            "event": "DELETE"
        }
    ]
}
```

### NONE操作示例
```json
// 输入：现有记忆："Name is John"，新事实：["Name is John"]
// 输出：
{
    "memory": [
        {
            "id": "0",
            "text": "Name is John",
            "event": "NONE"
        }
    ]
}
```

## 系统组件

### 向量存储
- **创建**: `VectorStoreFactory.create()` (`mem0/utils/factory.py`)
- **支持**: Qdrant, Chroma, Pinecone, Weaviate, Redis, PostgreSQL等

### 嵌入模型
- **创建**: `EmbedderFactory.create()` (`mem0/utils/factory.py`)
- **支持**: OpenAI, Hugging Face, Sentence Transformers等

### LLM
- **创建**: `LlmFactory.create()` (`mem0/utils/factory.py`)
- **支持**: OpenAI, Anthropic, AWS Bedrock, Azure, Ollama, Groq等

### 历史记录
- **存储**: SQLite数据库 (`SQLiteManager`)
- **位置**: `mem0/memory/storage.py`

## 错误处理

1. **事实提取失败**: 返回空列表，跳过记忆更新
2. **LLM决策失败**: 记录错误，返回空操作列表
3. **向量操作失败**: 抛出异常，回滚操作
4. **JSON解析失败**: 记录错误，跳过该条目

## 性能优化

1. **并发处理**: 向量存储和图数据库操作并行执行
2. **嵌入缓存**: 重用已生成的嵌入向量
3. **批量操作**: 支持多条消息批量处理
4. **索引优化**: 向量数据库自动索引优化

## 总结

POST `/memories` API通过以下步骤实现智能记忆管理：

1. **输入标准化**: 将各种格式输入统一为消息列表
2. **事实提取**: 使用LLM从自然语言中提取结构化事实
3. **相似性搜索**: 基于向量嵌入查找相关现有记忆
4. **智能决策**: 使用LLM分析并决定每个事实的处理方式
5. **操作执行**: 根据决策结果执行ADD/UPDATE/DELETE/NONE操作
6. **历史追踪**: 记录所有变更历史以便审计和回滚

这种设计巧妙地结合了传统向量检索的效率和LLM的语义理解能力，实现了真正智能的增量记忆管理系统。