# Mem0 框架集成分析

> 本文档分析 mem0 框架的核心架构，确定 UserProfile 模块的集成方式。

## 1. Mem0 核心架构概览

### 1.1 目录结构

```
mem0/
├── __init__.py           # 暴露 Memory, AsyncMemory, MemoryClient
├── memory/               # 核心记忆管理模块
│   ├── main.py          # Memory 类（核心）
│   ├── base.py          # MemoryBase 基类
│   ├── setup.py         # 配置和用户ID管理
│   ├── storage.py       # SQLite 历史记录管理
│   ├── telemetry.py     # 遥测和分析
│   └── utils.py         # 工具函数
├── client/              # 客户端（HTTP/远程调用）
├── configs/             # 配置和 Prompt 模板
│   ├── prompts.py       # 核心 Prompt（FACT_RETRIEVAL, UPDATE_MEMORY）
│   ├── base.py          # 配置数据模型
│   └── enums.py         # 枚举类型
├── llms/                # LLM 提供商集成
│   ├── deepseek.py
│   ├── openai.py
│   └── ...
├── embeddings/          # Embedding 提供商集成
│   ├── qwen.py
│   ├── openai.py
│   └── ...
├── vector_stores/       # 向量数据库集成
│   ├── pgvector.py
│   ├── qdrant.py
│   └── ...
├── graphs/              # 图数据库集成（Neo4j等）
├── utils/               # 工具类
│   └── factory.py       # 工厂模式创建 LLM/Embedder/VectorStore
└── proxy/               # 代理相关

server/
└── main.py              # FastAPI 服务入口
```

---

## 2. 核心组件分析

### 2.1 Memory 类（mem0/memory/main.py）

**职责**：记忆管理的核心类

**关键方法**：
- `__init__()`: 初始化配置、LLM、Embedder、VectorStore
- `add()`: 添加记忆（两阶段 LLM Pipeline）
- `get()` / `get_all()`: 查询记忆
- `search()`: 向量搜索记忆
- `update()`: 更新记忆
- `delete()` / `delete_all()`: 删除记忆
- `history()`: 查询记忆历史

**依赖注入**：
```python
class Memory(MemoryBase):
    def __init__(self, config: MemoryConfig = MemoryConfig()):
        # 从配置创建组件
        self.config = config
        self.llm = LlmFactory.create(config.llm.provider, config.llm.config)
        self.embedding_model = EmbedderFactory.create(config.embedder.provider, config.embedder.config)
        self.vector_store = VectorStoreFactory.create(config.vector_store.provider, config.vector_store.config)
        self.graph = GraphStoreFactory.create(...) if config.graph_store else None
        self.db = SQLiteManager(config.history_db_path)
```

**配置方式**：
```python
# 方式 1：使用 DEFAULT_CONFIG
memory = Memory.from_config(DEFAULT_CONFIG)

# 方式 2：使用 MemoryConfig 对象
from mem0.configs.base import MemoryConfig
config = MemoryConfig(...)
memory = Memory(config)
```

---

### 2.2 工厂模式（mem0/utils/factory.py）

mem0 使用工厂模式创建组件，便于扩展：

```python
class LlmFactory:
    @staticmethod
    def create(provider: str, config: dict):
        if provider == "deepseek":
            from mem0.llms.deepseek import DeepSeek
            return DeepSeek(config)
        elif provider == "openai":
            from mem0.llms.openai import OpenAI
            return OpenAI(config)
        # ...

class EmbedderFactory:
    # 类似...

class VectorStoreFactory:
    # 类似...

class GraphStoreFactory:
    # 类似...
```

**优势**：
- 解耦：组件独立，易于替换
- 扩展：新增提供商只需实现接口
- 配置化：通过字符串选择提供商

---

### 2.3 配置系统（mem0/configs/base.py）

**核心配置类**：
```python
class MemoryConfig:
    version: str = "v1.1"
    api_version: str = "v1.1"
    llm: LlmConfig
    embedder: EmbedderConfig
    vector_store: VectorStoreConfig
    graph_store: Optional[GraphStoreConfig] = None
    history_db_path: str = None
    custom_fact_extraction_prompt: Optional[str] = None
    custom_update_memory_prompt: Optional[str] = None
```

**当前项目配置**（server/main.py）：
```python
DEFAULT_CONFIG = {
    "version": "v1.1",
    "vector_store": {
        "provider": "pgvector",
        "config": {...}
    },
    "llm": {
        "provider": "deepseek",
        "config": {...}
    },
    "embedder": {
        "provider": "qwen",
        "config": {...}
    },
    "history_db_path": HISTORY_DB_PATH
}
```

---

### 2.4 FastAPI 服务（server/main.py）

**当前结构**：
- 单文件：所有路由在 `server/main.py`
- 全局实例：`MEMORY_INSTANCE = Memory.from_config(DEFAULT_CONFIG)`
- 直接调用：路由函数直接调用 `MEMORY_INSTANCE.add()` 等方法

**现有路由**：
- `POST /configure`: 动态配置
- `POST /memories`: 添加记忆
- `GET /memories`: 获取记忆
- `GET /memories/{memory_id}`: 获取单个记忆
- `POST /search`: 搜索记忆
- `PUT /memories/{memory_id}`: 更新记忆
- `GET /memories/{memory_id}/history`: 查询历史
- `DELETE /memories/{memory_id}`: 删除记忆
- `DELETE /memories`: 批量删除
- `POST /reset`: 重置所有记忆

---

## 3. UserProfile 模块集成方案

### 3.1 集成原则

基于 mem0 的设计理念：
1. **模块独立**：UserProfile 作为独立模块，与 Memory 模块平级
2. **复用组件**：共享 LLM、Embedder 等组件
3. **统一配置**：扩展 DEFAULT_CONFIG，添加 user_profile 配置项
4. **独立路由**：新增 `/profile` 和 `/vocab`（预留）路由

---

### 3.2 目录结构设计

```
mem0/
├── memory/              # 现有：记忆模块
│   └── ...
├── user_profile/        # 新增：用户画像模块
│   ├── __init__.py      # 暴露 UserProfile 类
│   ├── main.py          # UserProfile 主类
│   ├── profile_manager.py  # Profile 逻辑（interests, skills, personality）
│   ├── vocab_manager.py    # Vocab 逻辑（预留）
│   ├── prompts.py       # UserProfile 相关 Prompt
│   ├── models.py        # Pydantic 数据模型
│   ├── database/
│   │   ├── __init__.py
│   │   ├── postgres.py  # PostgreSQL 操作
│   │   └── mongodb.py   # MongoDB 操作
│   └── utils.py         # 工具函数
├── llms/                # 现有
├── embeddings/          # 现有
└── ...

server/
├── main.py              # 修改：添加 UserProfile 实例和路由
└── routers/             # 新增：模块化路由（可选）
    ├── __init__.py
    ├── memory.py        # 迁移现有 /memories 路由
    ├── profile.py       # 新增 /profile 路由
    └── vocab.py         # 新增 /vocab 路由（预留）
```

---

### 3.3 UserProfile 类设计

**参考 Memory 类的设计**：

```python
# mem0/user_profile/main.py

from typing import Optional, List, Dict, Any
from mem0.configs.base import MemoryConfig  # 复用配置
from mem0.utils.factory import LlmFactory  # 复用工厂
from mem0.user_profile.database.postgres import PostgresManager
from mem0.user_profile.database.mongodb import MongoDBManager
from mem0.user_profile.profile_manager import ProfileManager

class UserProfile:
    def __init__(self, config: MemoryConfig):
        """
        初始化 UserProfile 模块

        Args:
            config: mem0 的 MemoryConfig 对象（复用）
        """
        self.config = config

        # 复用 LLM（与 Memory 共享）
        self.llm = LlmFactory.create(
            config.llm.provider,
            config.llm.config
        )

        # 初始化数据库管理器
        self.postgres = PostgresManager(config.user_profile.postgres)
        self.mongodb = MongoDBManager(config.user_profile.mongodb)

        # 初始化业务逻辑管理器
        self.profile_manager = ProfileManager(
            llm=self.llm,
            postgres=self.postgres,
            mongodb=self.mongodb
        )

    @classmethod
    def from_config(cls, config_dict: Dict[str, Any]):
        """从字典配置创建实例（类似 Memory.from_config）"""
        from mem0.configs.base import MemoryConfig
        config = MemoryConfig(**config_dict)
        return cls(config)

    def set_profile(
        self,
        user_id: str,
        messages: List[Dict[str, str]],
        manual_data: Optional[Dict[str, Any]] = None,
        options: Optional[Dict[str, bool]] = None
    ) -> Dict[str, Any]:
        """
        更新用户画像

        Args:
            user_id: 用户ID
            messages: 对话消息列表
            manual_data: 前端手动输入的数据（可选）
            options: 控制更新哪些部分（可选）

        Returns:
            更新结果
        """
        return self.profile_manager.set_profile(
            user_id, messages, manual_data, options
        )

    def get_profile(
        self,
        user_id: str,
        type: str = "all",
        field: Optional[str] = None,
        query_all: bool = True
    ) -> Dict[str, Any]:
        """
        获取用户画像

        Args:
            user_id: 用户ID
            type: 类型（"basic" / "additional" / "all"）
            field: 字段名（点语法支持，如 "social_context.father.name"）
            query_all: 是否查询全部数据（默认 True）

        Returns:
            用户画像数据
        """
        return self.profile_manager.get_profile(
            user_id, type, field, query_all
        )
```

---

### 3.4 配置扩展

**扩展 DEFAULT_CONFIG**（server/main.py）：

```python
DEFAULT_CONFIG = {
    "version": "v1.1",

    # 现有配置
    "vector_store": {...},
    "llm": {...},
    "embedder": {...},
    "history_db_path": HISTORY_DB_PATH,

    # 新增：用户画像配置
    "user_profile": {
        "postgres": {
            # 复用现有 PostgreSQL 配置
            "host": POSTGRES_HOST,
            "port": POSTGRES_PORT,
            "database": POSTGRES_DB,
            "user": POSTGRES_USER,
            "password": POSTGRES_PASSWORD,
            "schema": "user_profile"  # 独立 schema
        },
        "mongodb": {
            "uri": os.environ.get("MONGODB_URI", "mongodb://mongodb:27017"),
            "database": os.environ.get("MONGODB_DATABASE", "mem0_profile")
        }
    }
}
```

**环境变量新增**（.env）：
```bash
# 新增 MongoDB 配置
MONGODB_URI=mongodb://mongodb:27017
MONGODB_DATABASE=mem0_profile
```

---

### 3.5 FastAPI 路由集成

**方式 1：在 server/main.py 中直接添加（简单）**：

```python
from mem0 import Memory
from mem0.user_profile import UserProfile  # 新增

# 创建实例
MEMORY_INSTANCE = Memory.from_config(DEFAULT_CONFIG)
USER_PROFILE_INSTANCE = UserProfile.from_config(DEFAULT_CONFIG)  # 新增

# 现有路由
@app.post("/memories", ...)
def add_memory(...):
    ...

# 新增路由
@app.post("/profile", summary="Update user profile")
def set_profile(
    user_id: str,
    messages: List[Message],
    manual_data: Optional[Dict[str, Any]] = None,
    options: Optional[Dict[str, bool]] = None
):
    """更新用户画像"""
    try:
        result = USER_PROFILE_INSTANCE.set_profile(
            user_id=user_id,
            messages=[m.model_dump() for m in messages],
            manual_data=manual_data,
            options=options
        )
        return JSONResponse(content=result)
    except Exception as e:
        logging.exception("Error in set_profile:")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/profile", summary="Get user profile")
def get_profile(
    user_id: str,
    type: str = "all",
    field: Optional[str] = None
):
    """获取用户画像"""
    try:
        result = USER_PROFILE_INSTANCE.get_profile(
            user_id=user_id,
            type=type,
            field=field
        )
        return JSONResponse(content=result)
    except Exception as e:
        logging.exception("Error in get_profile:")
        raise HTTPException(status_code=500, detail=str(e))
```

---

**方式 2：模块化路由（推荐，长期）**：

```python
# server/routers/profile.py
from fastapi import APIRouter, HTTPException
from typing import List, Dict, Any, Optional

router = APIRouter(prefix="/profile", tags=["profile"])

# 全局 USER_PROFILE_INSTANCE 由 main.py 注入

@router.post("/", summary="Update user profile")
def set_profile(...):
    ...

@router.get("/", summary="Get user profile")
def get_profile(...):
    ...
```

```python
# server/main.py
from server.routers import profile as profile_router

app.include_router(profile_router.router)
```

**MVP 阶段**：使用方式 1（简单直接）
**后期优化**：迁移到方式 2（代码更清晰）

---

## 4. 复用 mem0 组件的优势

### 4.1 共享 LLM

- UserProfile 和 Memory 使用相同的 LLM 实例
- 配置统一，避免重复初始化
- 节省资源（连接池、API 配额等）

### 4.2 共享配置管理

- 复用 `MemoryConfig` 和环境变量加载逻辑
- 统一的配置验证
- 便于运维（一个配置文件管理所有模块）

### 4.3 共享工具类

- 日志记录（logging）
- 遥测和分析（telemetry）
- 工具函数（utils）

---

## 5. 与 Memory 模块的隔离

### 5.1 数据隔离

- **Memory**：
  - 向量数据库：`pgvector` (collection: "memories")
  - 历史记录：`SQLite` (history.db)

- **UserProfile**：
  - 结构化数据：`PostgreSQL` (schema: "user_profile")
  - 非结构化数据：`MongoDB` (database: "mem0_profile")

**无数据冲突**

### 5.2 代码隔离

- 独立目录：`mem0/user_profile/`
- 独立路由：`/profile` vs `/memories`
- 独立类：`UserProfile` vs `Memory`

**便于独立测试和维护**

### 5.3 配置隔离

- Memory 配置：`vector_store`, `graph_store`, `history_db_path`
- UserProfile 配置：`user_profile.postgres`, `user_profile.mongodb`

**各自扩展，互不影响**

---

## 6. 集成检查清单

### 6.1 代码集成
- [ ] 创建 `mem0/user_profile/` 目录结构
- [ ] 实现 `UserProfile` 主类
- [ ] 实现 `ProfileManager` 业务逻辑
- [ ] 实现 `PostgresManager` 数据库操作
- [ ] 实现 `MongoDBManager` 数据库操作
- [ ] 编写 UserProfile 相关 Prompt

### 6.2 配置集成
- [ ] 扩展 `DEFAULT_CONFIG` 添加 `user_profile` 配置项
- [ ] 更新 `.env.example` 添加 MongoDB 配置
- [ ] 验证配置加载逻辑

### 6.3 路由集成
- [ ] 在 `server/main.py` 创建 `USER_PROFILE_INSTANCE`
- [ ] 添加 `POST /profile` 路由
- [ ] 添加 `GET /profile` 路由
- [ ] （可选）添加 `POST /vocab` 和 `GET /vocab` 占位路由

### 6.4 数据库集成
- [ ] 创建 PostgreSQL 初始化脚本（`user_profile` schema）
- [ ] 创建 MongoDB 初始化脚本（集合和索引）
- [ ] 更新 `docker-compose.yaml` 添加 MongoDB 服务

### 6.5 文档集成
- [ ] 更新 `CLAUDE.md` 添加 UserProfile 模块说明
- [ ] 更新 API 文档（OpenAPI/Swagger）
- [ ] 更新 README（可选）

---

## 7. 潜在风险和应对

### 7.1 配置冲突

**风险**：`MemoryConfig` 可能不支持自定义字段（如 `user_profile`）

**应对**：
- 方案 A：扩展 `MemoryConfig` 类，添加 `user_profile` 字段
- 方案 B：使用独立的配置类 `UserProfileConfig`，不复用 `MemoryConfig`
- **推荐**：方案 A（保持配置统一）

### 7.2 LLM 并发调用

**风险**：Memory 和 UserProfile 同时调用 LLM 可能超出速率限制

**应对**：
- 共享 LLM 实例已经有连接池管理
- 如果需要，可以添加请求队列或速率限制

### 7.3 数据库连接管理

**风险**：PostgreSQL 和 MongoDB 连接泄漏

**应对**：
- 使用连接池（`psycopg2.pool` / `pymongo.MongoClient`）
- 在 `UserProfile` 初始化时创建连接池
- 在应用关闭时正确关闭连接

---

## 8. 总结

### 8.1 集成方式

**UserProfile 作为 mem0 的平级模块**：
- 复用 LLM、配置系统、工具类
- 独立的数据存储和业务逻辑
- 统一的 FastAPI 服务入口

### 8.2 集成优势

- ✅ **复用性高**：共享核心组件
- ✅ **隔离性好**：代码和数据独立
- ✅ **扩展性强**：便于添加新模块
- ✅ **维护性好**：模块化设计

### 8.3 下一步

1. 创建目录结构和基础文件
2. 实现 UserProfile 核心逻辑
3. 集成到 FastAPI 服务
4. 编写测试用例
5. 更新文档

---

## 附录：参考文件

- `mem0/memory/main.py` - Memory 类实现
- `mem0/utils/factory.py` - 工厂模式
- `mem0/configs/base.py` - 配置数据模型
- `mem0/configs/prompts.py` - Prompt 模板
- `server/main.py` - FastAPI 服务
- `discuss/06-implementation_plan.md` - 实施方案