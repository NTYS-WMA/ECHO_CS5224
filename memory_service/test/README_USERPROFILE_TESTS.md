# UserProfile Test Suite

本目录包含两个主要的 UserProfile 测试文件，覆盖功能测试和质量测试。

## 测试文件

### 1. `test_userprofile_functional.py` - 功能测试

**目的**: 快速验证系统是否正常工作，没有报错

**特点**:
- 执行快速（大约 1-2 分钟）
- 测试基本功能是否可用
- 验证数据流是否正确

**测试覆盖** (13 tests):

| 测试类别 | 测试项 |
|---------|--------|
| **CRUD 操作** | 创建、读取、更新、删除 profile |
| **Prompt 结构** | 时间戳规则、语言一致性、degree 描述、social_context 结构 |
| **数据结构** | social_context (family/friends/others)、learning_preferences |
| **API 端点** | evidence_limit 参数、missing-fields 端点 |
| **Backend 逻辑** | 时间戳生成、字段清理、空值处理 |
| **数据库协调** | PostgreSQL + MongoDB 配合 |

**运行方式**:
```bash
python test/test_userprofile_functional.py
```

**预期结果**: 所有测试通过，耗时 < 2 分钟

---

### 2. `test_userprofile_quality.py` - 质量测试

**目的**: 验证 LLM 表现质量，归纳是否"好"

**特点**:
- 执行较慢（大约 5-10 分钟）
- 测试 LLM 推理能力
- 验证边缘情况处理

**测试覆盖** (8 tests):

| 测试类别 | 测试项 |
|---------|--------|
| **矛盾处理** | 基于证据数量和时间的决策（DELETE vs 降低 degree）|
| **Degree 调整** | 根据新证据智能调整用户技能等级 |
| **证据积累** | 多轮对话中证据的正确累积 |
| **兴趣 vs 技能** | 正确区分重叠的兴趣和技能 |
| **性格推断** | 从行为中推断性格特征（非显式陈述）|
| **丰富上下文** | 从复杂多轮对话中提取完整 profile |
| **混合社交关系** | 正确分类 family/friends/others（siblings, teachers）|
| **基础信息** | 将 basic_info 作为参考数据处理 |

**运行方式**:
```bash
python test/test_userprofile_quality.py
```

**预期结果**: 所有测试通过，耗时 5-10 分钟

---

## 测试策略

### 功能测试 (Functional)
- **频率**: 每次代码修改后
- **目标**: 确保没有破坏现有功能
- **失败处理**: 必须修复才能提交代码

### 质量测试 (Quality)
- **频率**: 重大功能更新、Prompt 修改后
- **目标**: 确保 LLM 表现符合预期
- **失败处理**: 分析原因，可能需要调整 Prompt 或示例

---

## 测试数据

所有测试使用独立的 test user IDs（如 `test_crud_001`, `test_social_002`），并在测试结束后清理数据，避免污染生产数据。

**测试用户 ID 命名规范**:
- `test_{category}_{number}`: 例如 `test_crud_001`, `test_social_002`
- 每个测试使用唯一的 ID，避免冲突

---

## 配置要求

测试需要以下环境变量：

```bash
# LLM API
DEEPSEEK_API_KEY=your_key

# PostgreSQL
POSTGRES_HOST=localhost
POSTGRES_PORT=8432
POSTGRES_USER=postgres
POSTGRES_PASSWORD=postgres
POSTGRES_DB=postgres

# MongoDB
MONGODB_URI=mongodb://mongo:mongo@localhost:27017/
MONGODB_DATABASE=mem0
```

确保 PostgreSQL 和 MongoDB 服务正在运行：
```bash
docker-compose up -d
```

---

## 调试技巧

### 查看详细日志
测试输出已包含详细信息，如果需要更多日志，可以设置环境变量：
```bash
export LOG_LEVEL=DEBUG
python test/test_userprofile_functional.py
```

### 单独运行某个测试
在文件中找到具体的测试函数，直接运行：
```python
if __name__ == "__main__":
    test_social_context_structure()  # 只运行这一个
```

### 保留测试数据（不清理）
在测试函数中注释掉 `user_profile.delete_profile()` 行，然后可以在数据库中查看实际保存的数据。

---

## 历史测试文件（已归档）

以下测试文件已整合到上述两个文件中，不再维护：

- ❌ `test_user_profile.py` - 基础 CRUD 测试（已整合到 functional）
- ❌ `test_user_profile_advanced.py` - 高级特性测试（已整合到 quality）
- ❌ `test_user_profile_quick.py` - 快速验证测试（已整合到 functional）
- ❌ `test_social_context.py` - 社交关系测试（已整合到 functional + quality）

---

## 未来扩展

### 可能添加的测试
1. **并发测试**: 多个请求同时更新同一用户 profile
2. **性能测试**: 大量数据下的查询性能
3. **边界测试**: 极长对话、极大 evidence 数组
4. **错误恢复测试**: LLM 返回格式错误时的处理

### 持续改进
- 根据实际使用中发现的 bug 添加回归测试
- 根据 Prompt 优化添加新的质量验证
- 定期审查测试覆盖率，补充缺失场景