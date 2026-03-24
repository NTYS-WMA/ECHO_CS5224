# UserProfile 功能设计总结与重难点

> 本文档总结 discuss/01-17 的所有讨论内容，提炼关键决策和技术难点。

## 1. 功能概述

### 1.1 核心需求

开发一个**用户画像系统**，为 AI 对话提供丰富的用户上下文信息，包括：
- **基本信息**：姓名、昵称、生日、性别、地理位置等
- **兴趣爱好**：用户喜欢的活动、事物
- **技能**：用户掌握的能力
- **性格特征**：从对话中推断的性格倾向
- **社交关系**：家人、朋友等
- **学习偏好**：偏好时间、学习风格等

### 1.2 暂不实现的功能

- **词汇管理**（vocab）：英语词汇掌握度追踪
  - 原因：逻辑需要与产品进一步讨论
  - 处理：归档设计，预留接口
  - 位置：`archived/vocab_design.md`

---

## 2. 关键技术决策

### 2.1 数据库选型

| 数据类型 | 存储方案 | 理由 |
|---------|---------|------|
| **基本信息** | PostgreSQL (user_profile 表) | 结构化、稳定、易查询 |
| **扩展信息** | MongoDB (user_additional_profile 集合) | 灵活、支持嵌套、易扩展 |

**最初方案**：MySQL + MongoDB
**最终方案**：PostgreSQL + MongoDB（复用现有 PostgreSQL）

---

### 2.2 数据结构设计（Evidence-Based）

**核心创新**：用 evidence 列表代替 count 统计

#### 统一的字段结构（interests, skills, personality）

```javascript
{
    "id": "0",
    "name": "足球",              // 名称（中文）
    "degree": 4,                // 程度（整数 1-5）
    "evidence": [               // 证据列表
        {
            "text": "和朋友踢足球很开心",
            "timestamp": "2025-10-01T10:30:00"
        },
        {
            "text": "周末又赢了一场",
            "timestamp": "2025-10-08T15:20:00"
        }
    ]
}
```

**优势**：
- 可追溯：每个判断都有证据支撑
- 智能判断：LLM 可以综合 evidence 的数量和时间做出决策
- 易调试：出现问题时可以查看具体 evidence

---

### 2.3 degree 字段的语义

**统一用整数 1-5 表示程度**：

| 类型 | degree 语义 | 示例 |
|------|------------|------|
| **interests** | 喜好程度 | 1=不太喜欢, 3=喜欢, 5=最爱 |
| **skills** | 掌握程度 | 1=初学, 3=中级, 5=专家 |
| **personality** | 明显程度 | 1=不明显, 3=一般, 5=非常明显 |

**判断依据**：
- evidence 数量（多 → degree 高）
- evidence 质量（明确、积极 → degree 高）
- evidence 时间（近期 → 更可信）

---

### 2.4 兴趣 vs 技能的边界

**问题**："我喜欢踢足球" 算兴趣还是技能？

**最终方案**：**允许重叠（方案 B）**
- 同一事物可以同时出现在 interests 和 skills 中
- 兴趣侧重"喜欢"，技能侧重"会做"
- 符合现实（既喜欢又擅长）

**其他考虑过的方案**：
- 方案 A：严格区分（prompt 复杂，判断困难）
- 方案 C：统一为"能力项"（过于抽象）

---

### 2.5 性格评估的策略

**简化后的设计**（移除复杂度）：

#### 移除的字段
- ❌ `confidence`（LLM 判断的置信度）→ 不可靠
- ❌ `first_observed`, `last_observed`（时间追踪）→ 过于复杂
- ❌ `trait_cn` + `trait`（中英文冗余）→ 只保留中文

#### 保留的字段
```javascript
{
    "id": "0",
    "name": "好奇",      // 只保留中文
    "degree": 4,        // 程度（1-5）
    "evidence": [...]   // 证据列表
}
```

**degree 作为隐式置信度**：
- degree 高 + evidence 多 = 稳定的性格特征
- degree 低 + evidence 少 = 初步观察，可能不稳定

---

### 2.6 Pipeline 设计

#### 两阶段 LLM 调用（参考 mem0）

**阶段 1：提取信息和 evidence**

Input: messages（对话）
Output:
```json
{
    "basic_info": {"current_city": "Beijing"},
    "interests": [
        {"name": "足球", "evidence": "和朋友踢足球很开心"}
    ],
    "skills": [...],
    "personality": [...]
}
```

**阶段 2：查询现有数据 + LLM 决策**

Input:
- 现有数据（全部查询，not只查相关的）
- 新提取的信息

Output:
```json
{
    "basic_info": [
        {"field": "current_city", "value": "Beijing", "event": "UPDATE"}
    ],
    "interests": [
        {
            "id": "0",
            "name": "足球",
            "event": "UPDATE",
            "new_degree": 4,
            "new_evidence": {...}
        }
    ],
    ...
}
```

**阶段 3：执行数据库操作**

根据 event 类型（ADD/UPDATE/DELETE）执行相应操作。

---

#### basic_info 的简化

**特殊处理**：basic_info 不需要阶段 2 的 LLM 判断

理由：
- 字段值是唯一的（如 current_city 只有一个值）
- 提取到新值就直接覆盖（UPSERT）
- 无需复杂的合并逻辑

**流程**：
1. LLM 提取 basic_info
2. 与 manual_data（前端输入）合并
3. 直接 UPSERT 到 PostgreSQL

---

### 2.7 矛盾处理的智能判断

**场景**：之前有 10 个 evidence 说"喜欢足球"，现在用户说"不喜欢了"

**智能判断规则**：

| 场景 | 判断依据 | 操作 |
|------|---------|------|
| 旧证据多 + 时间近 | 可能是临时情绪 | UPDATE（degree 降低但不删除） |
| 旧证据多 + 时间久远 | 兴趣真的改变了 | DELETE 或 degree=1 |
| 旧证据少 | 之前判断可能不准 | DELETE |
| 明确转变 | "以前喜欢X，现在喜欢Y" | X 降低，Y 提升 |

**LLM Prompt 指引**：
- 综合考虑 evidence 的数量、时间分布
- 人类的兴趣可能变化，也可能只是一时情绪
- 保守处理：不轻易删除

---

### 2.8 接口设计

#### 统一接口 + 可选控制

```python
POST /profile
{
    "user_id": "u123",
    "messages": [...],
    "manual_data": {...},  // 可选：前端手动输入
    "options": {           // 可选：控制更新哪些部分
        "update_basic": true,
        "update_interests": true,
        "update_skills": true,
        "update_personality": true,
        "query_all": true  // 新增：是否查询全部数据（默认 true）
    }
}
```

**query_all 参数**：
- `true`（默认）：查询用户的所有 additional_profile 数据
- `false`：只查询相关字段（需要传入查询字段列表）

---

## 3. 重难点分析

### 3.1 LLM 幻觉和容错（★★★★★）

**难点**：LLM 输出可能不稳定，JSON 格式可能错误

**解决方案**：4 层容错机制

#### 第 1 层：LLM 调用容错
```python
try:
    response = llm.generate_response(...)
except Exception as e:
    logger.error(f"LLM service unavailable: {e}")
    return {"error": "LLM service unavailable"}
```

#### 第 2 层：JSON 解析容错
```python
try:
    data = json.loads(response)
except json.JSONDecodeError:
    # 尝试修复（如去除 markdown 代码块）
    cleaned = remove_code_blocks(response)
    try:
        data = json.loads(cleaned)
    except:
        logger.error(f"Invalid JSON: {response}")
        return {}
```

#### 第 3 层：逐字段容错
```python
results = {}
for field in ["interests", "skills", "personality"]:
    try:
        results[field] = update_field(data.get(field, []))
    except Exception as e:
        logger.error(f"Failed to update {field}: {e}")
        results[field] = {"error": str(e)}
```

#### 第 4 层：数据库事务（可选）
```python
with db.transaction():
    update_all_fields(...)
    # 任何一步失败，全部回滚
```

**MVP 阶段**：前 3 层足够

---

### 3.2 Prompt 设计（★★★★☆）

**难点**：
- 需要准确提取信息
- 需要正确判断 ADD/UPDATE/DELETE
- 需要输出稳定的 JSON 格式

**解决方案**：

#### 参考 mem0 的成功经验
1. **分阶段**：提取和决策分开（降低单次复杂度）
2. **Few-shot**：提供多个示例
3. **明确格式**：严格定义 JSON schema
4. **UUID 映射**：用整数 ID 代替 UUID，防止幻觉
5. **字段验证**：检查必填字段是否存在

#### 示例（阶段 1）
```
从对话中提取用户的兴趣、技能和性格特征。

对话内容：
[messages]

请返回 JSON（严格遵守格式）：
{
    "interests": [
        {"name": "足球", "evidence": "和朋友踢足球很开心"}
    ],
    "skills": [],
    "personality": []
}

注意：
- 只提取对话中明确提到的内容
- evidence 字段记录具体事实（1-2 句话）
- 如果某类信息不存在，返回空列表 []
```

---

### 3.3 MongoDB 和 PostgreSQL 混合使用（★★★☆☆）

**难点**：
- 两个数据库的事务隔离
- 数据一致性保证
- 连接池管理

**解决方案**：

#### 数据一致性
- 使用 `user_id` 作为跨库唯一标识
- basic_info 和 additional_profile 独立更新
- 不强求强一致性（允许短暂不一致）

#### 连接池管理
```python
class PostgresManager:
    def __init__(self, config):
        self.pool = psycopg2.pool.SimpleConnectionPool(
            minconn=1, maxconn=10, **config
        )

class MongoDBManager:
    def __init__(self, config):
        self.client = MongoClient(
            config["uri"],
            maxPoolSize=10
        )
        self.db = self.client[config["database"]]
```

#### 错误处理
```python
# 逐个数据库操作，失败不影响其他
try:
    postgres.update_basic_info(...)
except Exception as e:
    logger.error(f"PostgreSQL update failed: {e}")

try:
    mongodb.update_additional_profile(...)
except Exception as e:
    logger.error(f"MongoDB update failed: {e}")
```

---

### 3.4 Evidence 的时间分析（★★★☆☆）

**难点**：如何综合 evidence 的数量和时间做出智能判断

**解决方案**：

#### 程序辅助分析
```python
def analyze_evidence_time(evidence_list):
    now = datetime.now()
    recent = sum(1 for e in evidence_list
                 if (now - datetime.fromisoformat(e["timestamp"])).days <= 90)
    old = sum(1 for e in evidence_list
              if (now - datetime.fromisoformat(e["timestamp"])).days >= 365)
    return {
        "total": len(evidence_list),
        "recent": recent,
        "old": old
    }
```

#### 在 Prompt 中提供分析结果
```
当前兴趣：足球
证据分析：总数=10, 近期(3个月内)=8, 久远(1年前)=1

新对话：用户说"我不喜欢足球了"

请判断如何处理...
```

#### LLM 综合判断
- 如果 recent 多 → 可能是临时情绪 → 降低 degree
- 如果 old 多 → 兴趣可能真的变了 → DELETE 或 degree=1

---

### 3.5 前端手动输入 vs LLM 提取的优先级（★★☆☆☆）

**难点**：如何处理两个来源的数据冲突

**解决方案**：

#### 简单优先级规则
```python
def merge_basic_info(extracted, manual_data):
    """前端数据优先"""
    result = extracted.copy()

    if manual_data:
        for key, value in manual_data.items():
            if value is not None:  # 前端有值
                result[key] = value  # 覆盖 LLM 提取的值

    return result
```

#### PROTECTED_FIELDS（可选）
```python
PROTECTED_FIELDS = ["name", "birthday", "gender"]

# 这些字段如果前端有值，永远不被 LLM 覆盖
for field in PROTECTED_FIELDS:
    if manual_data.get(field):
        result[field] = manual_data[field]
```

---

### 3.6 degree 的动态调整（★★★☆☆）

**难点**：如何根据 evidence 更新 degree

**解决方案**：

#### 方案 A：完全由 LLM 判断（推荐）
```
当前：degree=3, evidence 数量=2
新增：1 条积极的 evidence

请判断新的 degree（1-5）：
- 考虑 evidence 总数（现在是 3）
- 考虑 evidence 质量
- 考虑时间分布

建议：degree=4
```

#### 方案 B：程序辅助规则（兜底）
```python
def suggest_degree(evidence_count, current_degree):
    """根据 evidence 数量建议 degree"""
    if evidence_count >= 6:
        return min(5, current_degree + 1)
    elif evidence_count >= 3:
        return max(3, current_degree)
    elif evidence_count == 1:
        return 2
    return current_degree
```

**MVP 阶段**：方案 A（信任 LLM）

---

## 4. 架构设计亮点

### 4.1 模块化设计

```
mem0/
├── memory/              # 现有：记忆模块
└── user_profile/        # 新增：用户画像模块
    ├── main.py          # UserProfile 主类
    ├── profile_manager.py  # 业务逻辑
    ├── database/
    │   ├── postgres.py  # 数据访问
    │   └── mongodb.py
    ├── prompts.py       # Prompt 模板
    └── models.py        # 数据模型
```

**优势**：
- 职责清晰
- 易于测试
- 便于后期维护

---

### 4.2 复用 mem0 核心组件

**共享组件**：
- LLM（DeepSeek）
- 配置系统（MemoryConfig）
- 工具类（logging, utils）

**独立组件**：
- 数据库（PostgreSQL + MongoDB）
- 业务逻辑（ProfileManager）
- Prompt（user_profile/prompts.py）

**优势**：
- 减少资源占用
- 配置统一
- 代码复用

---

### 4.3 Evidence-Based 设计

**核心创新**：用证据列表代替简单计数

**优势**：
- **可追溯**：每个结论都有依据
- **智能化**：LLM 可以深度分析
- **灵活性**：支持复杂的矛盾处理
- **可调试**：出问题时可以查看证据

---

## 5. 开发优先级

### Phase 1: 基础架构（高优先级）
1. 创建目录结构
2. 实现 PostgresManager 和 MongoDBManager
3. 实现 UserProfile 主类骨架
4. 配置集成（DEFAULT_CONFIG 扩展）

### Phase 2: Profile 功能（高优先级）
1. 实现 basic_info 的 UPSERT
2. 实现 interests/skills/personality 的两阶段 pipeline
3. 编写 Prompt 模板
4. FastAPI 路由集成

### Phase 3: 测试和优化（中优先级）
1. 单元测试
2. 集成测试
3. 错误处理完善
4. 性能优化

### Phase 4: 文档和部署（中优先级）
1. API 文档
2. 数据库初始化脚本
3. Docker Compose 更新
4. CLAUDE.md 更新

---

## 6. 风险清单

| 风险 | 等级 | 应对措施 |
|------|------|---------|
| LLM 输出不稳定 | 高 | 4 层容错机制 |
| JSON 解析失败 | 高 | 多重尝试 + 日志记录 |
| 数据库连接泄漏 | 中 | 连接池 + 资源管理 |
| Evidence 过多导致性能问题 | 低 | 限制 evidence 数量（如最多保留 20 条） |
| MongoDB 和 PostgreSQL 数据不一致 | 低 | 容忍短暂不一致 + 日志追踪 |

---

## 7. 未来优化方向

### 7.1 性能优化
- Evidence 数量限制（如只保留最近 20 条）
- 批量更新接口
- 缓存热点数据

### 7.2 功能增强
- Profile 和 Memories 的联动
- 从历史 memories 批量生成 profile
- 词汇管理功能（下一阶段）

### 7.3 安全和隐私
- 访问权限控制
- 敏感字段加密
- GDPR 合规（数据导出/删除）

---

## 8. 关键文件索引

### 讨论文档
- `discuss/01-user_profile.md` - 初始需求
- `discuss/06-implementation_plan.md` - mem0 pipeline 分析
- `discuss/14-evidence_based_design.md` - Evidence-based 设计
- `discuss/16-final_clarification.md` - 最终确认

### 技术文档
- `docs/mem0_integration_analysis.md` - 集成分析
- `docs/summary_and_challenges.md` - 本文档

### 参考代码
- `mem0/memory/main.py` - Memory 类实现
- `mem0/configs/prompts.py` - Prompt 模板
- `server/main.py` - FastAPI 服务

---

## 9. 总结

### 9.1 核心设计理念

1. **Evidence-Based**：用证据代替计数，可追溯、可分析
2. **简化优先**：移除复杂的置信度和时间追踪，用 degree 统一表达
3. **智能判断**：让 LLM 综合 evidence 做出决策，而不是写死规则
4. **容错为主**：多层容错，保证部分失败不影响整体

### 9.2 技术难点排序

1. ★★★★★ LLM 幻觉和容错
2. ★★★★☆ Prompt 设计
3. ★★★☆☆ MongoDB + PostgreSQL 混合
4. ★★★☆☆ Evidence 时间分析
5. ★★★☆☆ degree 动态调整

### 9.3 成功关键

- ✅ 参考 mem0 的成熟设计
- ✅ Evidence-Based 的创新思路
- ✅ 简化和务实的平衡
- ✅ 充分的容错机制
- ✅ 模块化和可维护性

---

准备进入开发阶段！🚀