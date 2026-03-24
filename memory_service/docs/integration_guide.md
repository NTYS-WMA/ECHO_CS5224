# 记忆服务（MyMem0）内部集成文档

**版本**: 1.0
**更新日期**: 2026-03-17
**维护方**: 记忆服务团队

---

## 目录

1. [服务定位](#1-服务定位)
2. [接入信息](#2-接入信息)
3. [数据模型](#3-数据模型)
4. [API 接口详情](#4-api-接口详情)
   - [记忆接口](#41-记忆接口)
   - [用户画像接口](#42-用户画像接口)
5. [数据库表结构](#5-数据库表结构)
   - [PostgreSQL — 向量存储](#51-postgresql--向量存储-public-schema)
   - [PostgreSQL — 用户基本信息](#52-postgresql--用户基本信息-user_profile-schema)
   - [MongoDB — 用户扩展画像](#53-mongodb--用户扩展画像)
   - [SQLite — 记忆历史](#54-sqlite--记忆历史)
6. [AI 服务依赖](#6-ai-服务依赖)
7. [错误处理](#7-错误处理)
8. [注意事项与约束](#8-注意事项与约束)

---

## 1. 服务定位

记忆服务（MyMem0）在整体微服务架构中的位置：

```
主控服务
  ├──▶ 记忆服务（本服务）  ◀── 本文档描述的是这个
  ├──▶ AI 服务
  ├──▶ DB 服务
  └──▶ 其他服务
```

**职责**：

- 存储、检索对话中产生的语义记忆（向量化存储，支持相似度搜索）
- 从对话中自动提取并维护用户画像（基本信息 + 兴趣/技能/性格等深度特征）

**不负责**：

- 用户认证/鉴权（调用方自行处理，本服务暂未实现鉴权）
- 用户权威基本信息的维护（由主控服务/DB 服务维护，本服务的 `basic_info` 仅为对话提取的参考数据）

---

## 2. 接入信息

**Base URL**（内部网络）：

```
http://<host>:18088
```

| 端口  | 用途                    |
|-------|------------------------|
| 18088 | 记忆服务主 API（本文档） |
| 8432  | PostgreSQL（内部，不直连）|
| 27017 | MongoDB（内部，不直连）  |

**交互协议**：HTTP/1.1，JSON 请求与响应，`Content-Type: application/json`。

**在线文档**：`http://<host>:18088/docs`（Swagger UI）

---

## 3. 数据模型

### 3.1 Message（消息）

所有写入接口均接受消息列表，格式统一：

```json
{
  "role": "user",       // "user" | "assistant"
  "content": "消息内容"
}
```

### 3.2 Memory Item（记忆条目）

读取接口返回的单条记忆：

```json
{
  "id": "550e8400-e29b-41d4-a716-446655440000",  // UUID
  "memory": "用户喜欢踢足球",                      // 提炼后的记忆文本
  "hash": "abc123...",                            // 内容哈希，用于去重
  "created_at": "2026-03-10T08:00:00.000Z",       // ISO 8601
  "updated_at": "2026-03-15T10:30:00.000Z",
  "user_id": "user_001",                          // 至少有一个 scope 字段
  "agent_id": "agent_001",                        // 可选
  "run_id": "run_001",                            // 可选
  "actor_id": "user_001",                         // 可选，消息发送者 ID
  "role": "user",                                 // 可选，消息角色
  "metadata": {}                                  // 可选，调用方传入的自定义 metadata
}
```

### 3.3 UserProfile（用户画像）

`GET /profile` 的完整响应结构：

```json
{
  "user_id": "user_001",
  "basic_info": {
    "name": "张三",
    "nickname": "小张",
    "english_name": "John",
    "birthday": "2016-05-20",
    "gender": "male",
    "nationality": "Chinese",
    "hometown": "成都",
    "current_city": "北京",
    "timezone": "Asia/Shanghai",
    "language": "zh-CN",
    "school_name": "北京实验小学",
    "grade": "三年级",
    "class_name": "2班"
  },
  "additional_profile": {
    "interests": [
      {
        "id": "interest_abc123",
        "name": "足球",
        "degree": 4,
        "evidence": [
          {"text": "每周末都去踢球，很享受", "timestamp": "2026-03-10T08:00:00.000Z"}
        ]
      }
    ],
    "skills": [
      {
        "id": "skill_def456",
        "name": "画画",
        "degree": 3,
        "evidence": [
          {"text": "参加了学校美术比赛获奖", "timestamp": "2026-03-12T10:00:00.000Z"}
        ]
      }
    ],
    "personality": [
      {
        "id": "pers_ghi789",
        "name": "外向",
        "degree": 4,
        "evidence": [
          {"text": "喜欢和同学一起玩", "timestamp": "2026-03-10T08:00:00.000Z"}
        ]
      }
    ],
    "social_context": {
      "family": {
        "father": {"name": "张明", "info": ["工程师", "喜欢篮球"]},
        "mother": {"name": "李华", "info": ["老师"]},
        "brother": [{"name": "张小弟", "info": ["5岁"]}],
        "sister": []
      },
      "friends": [
        {"name": "小明", "info": ["同班同学", "喜欢足球"]}
      ],
      "others": [
        {"name": null, "relation": "数学老师", "info": ["严格但耐心"]}
      ]
    },
    "learning_preferences": {
      "preferred_time": "evening",
      "preferred_style": "visual",
      "difficulty_level": "intermediate"
    }
  }
}
```

**`degree` 含义**（1-5 整数）：

| 字段         | 含义                  |
|--------------|----------------------|
| `interests`  | 喜爱程度（1=一般，5=非常热爱） |
| `skills`     | 熟练程度（1=初学，5=精通）     |
| `personality`| 特征强度（1=偶尔，5=非常明显） |

**`social_context` 说明**：

| 字段      | 类型   | 说明                                        |
|-----------|--------|---------------------------------------------|
| `family`  | object | 直系亲属，key 为关系标识符（见下表）         |
| `friends` | array  | 朋友列表，每项有 `name` + `info`            |
| `others`  | array  | 其他社会关系，每项有 `name` + `relation` + `info` |

`family` 支持的 key：

| 单数（object） | 复数（array） |
|---------------|-------------|
| `father`, `mother`, `spouse` | `brother[]`, `sister[]`, `son[]`, `daughter[]`, `grandson[]`, `granddaughter[]` |
| `grandfather_paternal`, `grandmother_paternal` | — |
| `grandfather_maternal`, `grandmother_maternal` | — |

> 旁系亲属（叔叔、舅舅、表兄弟等）放在 `others` 中，通过 `relation` 字段标注。

---

## 4. API 接口详情

### 4.1 记忆接口

---

#### `POST /memories` — 写入记忆

从对话消息中提取事实并存入记忆库。LLM 会自动判断是新增、更新还是删除已有记忆。

**请求体**：

```json
{
  "messages": [
    {"role": "user", "content": "我叫张三，住在北京，最近开始学钢琴"},
    {"role": "assistant", "content": "很好，学钢琴很有趣！"}
  ],
  "user_id": "user_001",       // user_id / agent_id / run_id 至少提供一个
  "agent_id": null,
  "run_id": null,
  "metadata": {"source": "chat"}  // 可选，自定义 metadata
}
```

**响应** `200 OK`：

```json
{
  "results": [
    {
      "id": "550e8400-e29b-41d4-a716-446655440000",
      "memory": "用户叫张三，住在北京",
      "event": "ADD"
    },
    {
      "id": "661f9511-f30c-52e5-b827-557766551111",
      "memory": "用户最近开始学钢琴",
      "event": "ADD"
    },
    {
      "id": "772a0622-g41d-63f6-c938-668877662222",
      "memory": "用户喜欢音乐",
      "event": "UPDATE",
      "previous_memory": "用户对音乐感兴趣"
    }
  ]
}
```

`event` 枚举：`ADD` | `UPDATE` | `DELETE`

---

#### `GET /memories` — 获取全部记忆

**查询参数**：

| 参数       | 类型   | 必填 | 说明                        |
|------------|--------|------|-----------------------------|
| `user_id`  | string | *    | 三者至少提供一个             |
| `agent_id` | string | *    | 同上                        |
| `run_id`   | string | *    | 同上                        |

**响应** `200 OK`：

```json
{
  "results": [
    {
      "id": "550e8400-e29b-41d4-a716-446655440000",
      "memory": "用户叫张三，住在北京",
      "hash": "d41d8cd98f00b204...",
      "created_at": "2026-03-10T08:00:00.000Z",
      "updated_at": "2026-03-10T08:00:00.000Z",
      "user_id": "user_001"
    }
  ]
}
```

---

#### `GET /memories/{memory_id}` — 获取单条记忆

**路径参数**：`memory_id`（UUID）

**响应** `200 OK`：返回单个 Memory Item 对象（结构同上）。

---

#### `PUT /memories/{memory_id}` — 更新记忆

直接覆盖记忆文本内容（不走 LLM）。

**路径参数**：`memory_id`（UUID）

**请求体**：

```json
{
  "memory": "更新后的记忆文本内容"
}
```

**响应** `200 OK`：

```json
{"message": "Memory updated successfully"}
```

---

#### `DELETE /memories/{memory_id}` — 删除单条记忆

**路径参数**：`memory_id`（UUID）

**响应** `200 OK`：

```json
{"message": "Memory deleted successfully"}
```

---

#### `DELETE /memories` — 删除某用户全部记忆

**查询参数**：`user_id` / `agent_id` / `run_id`（至少一个）

**响应** `200 OK`：

```json
{"message": "All relevant memories deleted"}
```

---

#### `POST /search` — 语义搜索记忆

对记忆库做向量相似度搜索，返回最相关的若干条。

**请求体**：

```json
{
  "query": "用户的音乐爱好",
  "user_id": "user_001",     // 至少一个 scope
  "agent_id": null,
  "run_id": null,
  "filters": {"source": "chat"},   // 可选，按 metadata 字段过滤
  "limit": 5,                      // 默认 5
  "threshold": 0.3                 // 可选，相似度最低阈值 0.0~1.0
}
```

**响应** `200 OK`：

```json
{
  "results": [
    {
      "id": "550e8400-e29b-41d4-a716-446655440000",
      "memory": "用户最近开始学钢琴",
      "score": 0.87,
      "hash": "abc123...",
      "created_at": "2026-03-10T08:00:00.000Z",
      "updated_at": "2026-03-10T08:00:00.000Z",
      "user_id": "user_001"
    }
  ]
}
```

> `score` 为余弦相似度，越高越相关。设置 `threshold` 可过滤掉低分结果。

---

#### `GET /memories/{memory_id}/history` — 记忆变更历史

查询某条记忆的完整修改记录。

**响应** `200 OK`：

```json
[
  {
    "id": "history-uuid",
    "memory_id": "550e8400-e29b-41d4-a716-446655440000",
    "old_memory": null,
    "new_memory": "用户最近开始学钢琴",
    "event": "ADD",
    "created_at": "2026-03-10T08:00:00.000Z",
    "updated_at": "2026-03-10T08:00:00.000Z",
    "is_deleted": false,
    "actor_id": null,
    "role": "user"
  }
]
```

`event` 枚举：`ADD` | `UPDATE` | `DELETE`

---

### 4.2 用户画像接口

---

#### `POST /profile` — 提取并更新用户画像

从对话消息中提取用户信息，更新基本信息（PostgreSQL）和扩展画像（MongoDB）。内部走两次 LLM 调用：先提取，再决策增删改。

**请求体**：

```json
{
  "messages": [
    {"role": "user", "content": "我叫李明，住在上海，最近迷上了摄影"},
    {"role": "assistant", "content": "摄影很有趣！你喜欢拍什么题材？"},
    {"role": "user", "content": "我喜欢拍风景，每周末都会出去拍"}
  ],
  "user_id": "user_001"   // 必填
}
```

**响应** `200 OK`：

```json
{
  "success": true,
  "basic_info_updated": true,
  "additional_profile_updated": true,
  "operations_performed": {
    "added": 2,
    "updated": 0,
    "deleted": 0
  },
  "errors": []
}
```

失败时：

```json
{
  "success": false,
  "error": "错误描述"
}
```

---

#### `GET /profile` — 获取用户画像

**查询参数**：

| 参数             | 类型    | 必填 | 默认  | 说明                                                    |
|------------------|---------|------|-------|--------------------------------------------------------|
| `user_id`        | string  | 是   | —     | 用户 ID                                                |
| `fields`         | string  | 否   | all   | 逗号分隔的字段名，如 `interests,skills`；不传则返回全部 |
| `evidence_limit` | integer | 否   | 5     | 证据条数控制：`0`=不返回证据，`N`=最新N条，`-1`=全部    |

**响应** `200 OK`：

见 [3.3 UserProfile 数据结构](#33-userprofile用户画像)。

若用户不存在且配置了 PalServer，服务会自动从 PalServer 冷启动导入初始数据后返回。

---

#### `GET /profile/missing-fields` — 查询缺失字段

用于判断哪些画像字段尚未采集，可作为主动采集信息的依据。

**查询参数**：

| 参数      | 类型   | 必填 | 默认   | 说明                            |
|-----------|--------|------|--------|---------------------------------|
| `user_id` | string | 是   | —      | 用户 ID                         |
| `source`  | string | 否   | `both` | `pg`（基本信息）/ `mongo`（扩展画像）/ `both` |

**响应** `200 OK`：

```json
{
  "user_id": "user_001",
  "missing_fields": {
    "basic_info": ["hometown", "gender", "birthday"],
    "additional_profile": ["personality", "learning_preferences"]
  }
}
```

---

#### `DELETE /profile` — 删除用户画像

**查询参数**：`user_id`（必填）

**响应** `200 OK`：

```json
{
  "success": true,
  "basic_info_deleted": true,
  "additional_profile_deleted": false
}
```

> `basic_info_deleted` / `additional_profile_deleted` 为 `false` 表示该数据库中原本无此用户数据。

---

#### `POST /vocab` 和 `GET /vocab` — 词汇管理（未实现）

预留接口，当前返回 `501 Not Implemented`，第二阶段实现。

---

## 5. 数据库表结构

> 以下为本服务内部数据存储结构，供联合排查问题、理解数据流转时参考。调用方无需直连数据库。

### 5.1 PostgreSQL — 向量存储（`public` schema）

表名：由环境变量 `POSTGRES_COLLECTION` 配置，默认为 `memories`。

```sql
CREATE TABLE memories (
    id      UUID PRIMARY KEY,
    vector  vector(1536),      -- Qwen text-embedding-v4 向量，1536 维
    payload JSONB              -- 记忆数据及 metadata
);

-- 索引（HNSW，加速近邻搜索）
CREATE INDEX memories_hnsw_idx ON memories USING hnsw (vector vector_cosine_ops);
```

`payload` 字段内容（JSONB）：

```json
{
  "data": "用户叫张三，住在北京",   // 记忆文本
  "hash": "md5_hash_string",
  "created_at": "2026-03-10T08:00:00.000Z",
  "updated_at": "2026-03-10T08:00:00.000Z",
  "user_id": "user_001",
  "agent_id": "agent_001",      // 可选
  "run_id": "run_001",          // 可选
  "actor_id": "user_001",       // 可选
  "role": "user"                // 可选
}
```

---

### 5.2 PostgreSQL — 用户基本信息（`user_profile` schema）

表名：`user_profile.user_profile`

> **注意**：此表存储的是从对话中提取的基本信息，**非权威数据**，仅供参考和个性化使用。用户的权威基本信息由主控服务/DB 服务维护。

```sql
CREATE TABLE user_profile.user_profile (
    user_id       VARCHAR(50)  PRIMARY KEY,
    created_at    TIMESTAMP    NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at    TIMESTAMP    NOT NULL DEFAULT CURRENT_TIMESTAMP,

    -- 基本信息
    name          VARCHAR(100),                    -- 真实姓名
    nickname      VARCHAR(100),                    -- 昵称/小名
    english_name  VARCHAR(100),                    -- 英文名
    birthday      DATE,                            -- 生日
    gender        VARCHAR(10),                     -- male / female / unknown
    nationality   VARCHAR(50),                     -- 国籍
    hometown      VARCHAR(100),                    -- 家乡
    current_city  VARCHAR(100),                    -- 现居城市
    timezone      VARCHAR(50),                     -- 如 Asia/Shanghai
    language      VARCHAR(50),                     -- 如 zh-CN, en-US

    -- 教育信息（面向 3-9 岁儿童场景）
    school_name   VARCHAR(200),                    -- 学校名称
    grade         VARCHAR(50),                     -- 年级，如 三年级 / Grade 3
    class_name    VARCHAR(50)                      -- 班级，如 2班 / Class 2A
);
```

---

### 5.3 MongoDB — 用户扩展画像

数据库：由 `MONGODB_DATABASE` 配置
集合：`user_additional_profile`

每个用户对应一个文档，结构如下：

```json
{
  "user_id": "user_001",

  "interests": [
    {
      "id": "interest_abc123",
      "name": "足球",
      "degree": 4,
      "evidence": [
        {"text": "每周末都去踢球", "timestamp": "2026-03-10T08:00:00.000Z"}
      ]
    }
  ],

  "skills": [
    {
      "id": "skill_def456",
      "name": "画画",
      "degree": 3,
      "evidence": [
        {"text": "参加了学校美术比赛获奖", "timestamp": "2026-03-12T10:00:00.000Z"}
      ]
    }
  ],

  "personality": [
    {
      "id": "pers_ghi789",
      "name": "外向",
      "degree": 4,
      "evidence": [
        {"text": "喜欢和同学一起玩", "timestamp": "2026-03-10T08:00:00.000Z"}
      ]
    }
  ],

  "social_context": {
    "family": {
      "father": {"name": "张明", "info": ["工程师"]},
      "mother": {"name": "李华", "info": ["老师"]},
      "brother": [{"name": "张小弟", "info": ["5岁"]}]
    },
    "friends": [
      {"name": "小明", "info": ["同班同学"]}
    ],
    "others": [
      {"name": null, "relation": "数学老师", "info": ["教数学", "很严格"]}
    ]
  },

  "learning_preferences": {
    "preferred_time": "evening",
    "preferred_style": "visual",
    "difficulty_level": "intermediate"
  }
}
```

索引：

| 字段           | 类型   |
|----------------|--------|
| `user_id`      | unique |
| `interests.id` | 普通   |
| `skills.id`    | 普通   |
| `personality.id` | 普通 |

---

### 5.4 SQLite — 记忆历史

文件路径：由 `HISTORY_DB_PATH` 配置，默认 `/app/history/history.db`

```sql
CREATE TABLE history (
    id          TEXT PRIMARY KEY,   -- UUID
    memory_id   TEXT,               -- 关联的 memory UUID
    old_memory  TEXT,               -- 变更前内容（ADD 时为 null）
    new_memory  TEXT,               -- 变更后内容（DELETE 时为 null）
    event       TEXT,               -- ADD | UPDATE | DELETE
    created_at  DATETIME,
    updated_at  DATETIME,
    is_deleted  INTEGER,            -- 0 / 1
    actor_id    TEXT,               -- 可选
    role        TEXT                -- 可选
);
```

---

## 6. AI 服务依赖

### 6.1 当前实现

本服务当前自行调用 AI 能力，依赖以下外部接口：

#### Embedding 服务

| 项目       | 内容                                      |
|------------|-------------------------------------------|
| 提供方     | 阿里云 DashScope（Qwen）                   |
| 模型       | `text-embedding-v4`                       |
| 向量维度   | 1536                                      |
| 接口       | `https://dashscope.aliyuncs.com/compatible-mode/v1` |
| 用途       | 记忆存储时生成向量；搜索时对 query 生成向量 |

#### LLM 服务

| 项目       | 内容                                      |
|------------|-------------------------------------------|
| 提供方     | DeepSeek 官方 / 火山引擎（优先火山引擎）   |
| 模型       | `deepseek-chat` / VolcEngine Endpoint ID  |
| 参数       | temperature=0.2，max_tokens=2000          |
| 用途（记忆）| 从对话中提取事实；判断对已有记忆的增/改/删 |
| 用途（画像）| 从对话中提取画像信息；判断字段的增/改/删   |

**LLM 调用链路（写入记忆 `POST /memories`）**：

```
调用方 → POST /memories
  → LLM: 提取对话中的事实
  → Embedding: 对现有记忆向量搜索（查相关旧记忆）
  → LLM: 决策 ADD / UPDATE / DELETE
  → 写入 PostgreSQL（向量） + SQLite（历史）
```

**LLM 调用链路（写入画像 `POST /profile`）**：

```
调用方 → POST /profile
  → LLM: 从对话提取画像信息（Stage 1）
  → 查询现有画像（PostgreSQL + MongoDB）
  → LLM: 决策各字段的 ADD / UPDATE / DELETE（Stage 2）
  → 写入 PostgreSQL（basic_info） + MongoDB（additional_profile）
```

### 6.2 未来规划

后续将由内部 **AI 服务** 统一提供 Embedding 和 LLM 能力，本服务改为调用 AI 服务的接口，不再直连外部 API。接口形式待 AI 服务确定后对接。

届时变更点：

- `POST /memories` 中的向量生成和 LLM 推理 → 转发给 AI 服务
- `POST /profile` 中的两阶段 LLM 调用 → 转发给 AI 服务
- `POST /search` 中的 query 向量化 → 转发给 AI 服务

**数据库直连计划**：同理，后续可能将 PostgreSQL / MongoDB 访问转交给内部 DB 服务管理，当前本服务直连数据库。

---

## 7. 错误处理

### HTTP 状态码

| 状态码 | 含义                                         |
|--------|----------------------------------------------|
| 200    | 成功                                         |
| 400    | 请求参数错误（如缺少必填 ID、source 值非法）  |
| 422    | 请求体格式错误（Pydantic 校验失败）           |
| 500    | 服务内部错误（数据库连接、LLM 调用失败等）    |
| 501    | 功能未实现（`/vocab` 接口）                   |

### 400 / 422 响应格式

```json
{
  "detail": "At least one identifier (user_id, agent_id, run_id) is required."
}
```

或（422）：

```json
{
  "detail": [
    {
      "loc": ["body", "user_id"],
      "msg": "field required",
      "type": "value_error.missing"
    }
  ]
}
```

### 500 响应格式

```json
{
  "detail": "具体错误信息（数据库连接超时、LLM 返回非法 JSON 等）"
}
```

---

## 8. 注意事项与约束

1. **`user_id` 由上游服务提供**：本服务不做用户身份验证，`user_id` 的合法性由调用方保证。

2. **`POST /memories` 是异步感知操作**：每次调用会触发 LLM 推理，耗时较长（通常 1-5 秒），不建议在高频实时链路中同步调用。

3. **`POST /profile` 更耗时**：需要两次 LLM 调用，耗时约 3-10 秒，建议异步/后台处理。

4. **`basic_info` 非权威数据**：从对话中提取的用户基本信息（姓名、生日等）仅供 AI 个性化参考，不作为用户档案的权威来源。若需权威数据，请从主控服务/DB 服务获取。

5. **`evidence_limit` 参数**：默认返回最新 5 条证据，若不需要证据（如仅做展示）请传 `evidence_limit=0` 减少响应体积。

6. **记忆 `scope` 隔离**：`user_id`、`agent_id`、`run_id` 三者可组合使用，搜索和获取均按传入的 scope 过滤，不同 scope 的记忆相互隔离。

7. **`/reset` 接口**：会清空所有记忆（不区分用户），仅用于测试环境，**生产禁止调用**。

8. **鉴权**：当前接口无鉴权，调用方需确保在内网环境下访问，后续将补充认证机制。
