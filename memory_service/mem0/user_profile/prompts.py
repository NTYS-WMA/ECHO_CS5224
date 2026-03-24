"""
Prompts for UserProfile LLM calls
"""

EXTRACT_PROFILE_PROMPT = """Extract user profile from conversation. Return JSON only.

## Output Format
```json
{{
  "basic_info": {{
    "name": "张三",
    "current_city": "上海",
    "school_name": "上海实验小学",
    "grade": "三年级",
    "class_name": "3班"
  }},
  "additional_profile": {{
    "interests": [{{"name": "足球", "degree": 4, "evidence": [{{"text": "周末踢球很开心"}}]}}],
    "skills": [{{"name": "Python", "degree": 3, "evidence": [{{"text": "写了数据工具"}}]}}],
    "personality": [{{"name": "外向", "degree": 4, "evidence": [{{"text": "喜欢社交"}}]}}],
    "social_context": {{
      "family": {{"father": {{"name": "李明", "info": ["医生"]}}}},
      "friends": [{{"name": "Jack", "info": ["打篮球"]}}],
      "others": [{{"name": null, "relation": "老师", "info": ["教数学"]}}]
    }},
    "learning_preferences": {{"preferred_time": "evening", "preferred_style": "visual"}}
  }}
}}
```

## Rules

**1. ❗Language Consistency - MOST CRITICAL**
- Preserve user's EXACT words - NO translation between languages
- 中文→中文 | English→English | 混合→混合
- ❌ "退休了"→"retired" | ✅ "退休了"→"退休了"

**2. Evidence & Degree**
- Evidence: text only (NO timestamp - backend handles it)
- Degree (1-5): interests=liking level, skills=proficiency, personality=strength
- Every attribute needs evidence from conversation

**3. social_context Schema**

| Field | Type | Members | Rules |
|-------|------|---------|-------|
| **family** | object | father, mother, spouse, brother[], sister[], son[], daughter[], grandfather_*, grandmother_* | Direct relatives only. name=actual name or null (NOT relation word) |
| **friends** | array | name + info | NO relation field |
| **others** | array | name + relation + info | Collateral relatives (uncle/aunt/cousin), teachers, colleagues, etc. |

**Critical**:
- name field: actual name like "小芳" OR null (❌ NOT "妻子"/"wife")
- Collateral relatives (uncle/aunt/cousin) → others (need "relation" to distinguish "叔叔" vs "舅舅")
- Unified format: family/friends have name+info, others have name+relation+info

**4. learning_preferences** - Object (NOT array)
- preferred_time: "morning"/"afternoon"/"evening"
- preferred_style: "visual"/"auditory"/"kinesthetic"
- difficulty_level: "beginner"/"intermediate"/"advanced"

**5. Extract Explicit Info Only**
- Don't infer or guess
- Omit fields with no data (don't include empty keys)

**6. ❗CRITICAL: Only Extract What USER Says About THEMSELVES**
- **ONLY extract** information the user explicitly states about their OWN life
- **IGNORE** AI assistant responses even if mislabeled as "user"
- **Ignore patterns that indicate AI responses**:
  - Questions (e.g., "你喜欢什么运动？", "What's your hobby?")
  - Suggestions (e.g., "我建议你...", "You should try...")
  - Explanations (e.g., "这是因为...", "This is because...")
  - Acknowledgments (e.g., "好的，我明白了", "Got it, I understand")
  - Generic responses without personal info
- **Extract patterns from USER**:
  - Self-statements (e.g., "我叫李明", "I like basketball")
  - Personal experiences (e.g., "昨天我去爬山了", "I went hiking yesterday")
  - Personal preferences (e.g., "我喜欢晚上学习", "I prefer learning at night")

## Examples

**Ex1: Basic + Interest + Education**
User: "我叫李明住杭州，在北京实验小学上三年级2班，最近迷上摄影，每周末拍照"
```json
{{
  "basic_info": {{
    "name": "李明",
    "current_city": "杭州",
    "school_name": "北京实验小学",
    "grade": "三年级",
    "class_name": "2班"
  }},
  "additional_profile": {{
    "interests": [{{"name": "摄影", "degree": 4, "evidence": [{{"text": "最近迷上摄影，每周末拍照"}}]}}]
  }}
}}
```

**Ex2: Social Context - Complete**
User: "我爸爸叫李明是医生，妈妈是老师。大哥叫小明在北京。我舅舅是工程师。老婆小芳是设计师，女儿小静静三岁"
```json
{{
  "additional_profile": {{
    "social_context": {{
      "family": {{
        "father": {{"name": "李明", "info": ["医生"]}},
        "mother": {{"name": null, "info": ["老师"]}},
        "brother": [{{"name": "小明", "info": ["大哥", "在北京工作"]}}, {{"name": null, "info": ["哥哥"]}}],
        "spouse": {{"name": "小芳", "info": ["设计师"]}},
        "daughter": [{{"name": "小静静", "info": ["三岁"]}}]
      }},
      "others": [{{"name": null, "relation": "舅舅", "info": ["工程师"]}}]
    }}
  }}
}}
```
Note: brother is array (can have multiple), father/mother/spouse are objects (single). Collateral relative (舅舅) goes to others.

**Ex3: IGNORE AI Assistant Responses** ❌
Conversation:
- User: "我最近在学Python"
- Assistant: "太好了！我建议你可以从基础语法开始，然后学习数据结构。我认为Python很适合初学者。"
- User: "好的，我会试试"

Extract ONLY: {{"additional_profile": {{"skills": [{{"name": "Python", "degree": 2, "evidence": [{{"text": "我最近在学Python"}}]}}]}}}}

**DO NOT extract**:
- ❌ "我建议你..." (AI suggestion)
- ❌ "我认为Python很适合初学者" (AI opinion, not user's)
- ❌ "好的，我会试试" (no new profile info, just acknowledgment)

---
Extract from: {messages}
Return JSON only.
"""

UPDATE_PROFILE_PROMPT = """Analyze extracted info vs existing profile. Decide operations: ADD/UPDATE/DELETE/SKIP.

## Input
**Extracted**: {extracted_info}
**Existing** (with timestamps): {existing_profile}

## Output Format
```json
{{
  "basic_info": {{"name": "张三"}},
  "additional_profile": {{
    "interests": [
      {{"id": "1", "event": "UPDATE", "name": "足球", "degree": 5, "evidence": [{{"text": "又赢了比赛"}}]}},
      {{"id": null, "event": "ADD", "name": "摄影", "degree": 3, "evidence": [{{"text": "买了相机"}}]}}
    ],
    "personality": [
      {{"id": "2", "event": "DELETE", "name": "内向"}}
    ]
  }}
}}
```

## Rules

**1. Language Consistency** - Keep user's original language (see extraction rules)

**2. Timestamps** - Return evidence text only (NO timestamp - backend adds it)

**3. ID Mapping** - Use existing ID for UPDATE/DELETE, null for ADD

**4. Evidence Analysis for Contradictions**
- Strong recent evidence (10+ entries, <3mo) + user says "不喜欢了" → reduce degree (temp mood)
- Weak/old evidence (1-2 entries or >6mo) + user says "不喜欢了" → DELETE (real change)

**5. Degree** - Combine new + existing evidence to determine

**6. basic_info** - Direct upsert (NO events)

**7. Evidence** - Return NEW evidence only (backend merges with existing)

**8. ❗social_context - DEEP MERGE**
- Return ONLY mentioned relationships with events (ADD/UPDATE/DELETE)
- Backend preserves unmentioned relationships
- Example: To add spouse, return `{{"family": {{"spouse": {{"event": "ADD", "name": "小芳", "info": [...]}}}}}}`
- Backend will merge with existing father/mother (DON'T return them)

**9. ❗Personality Conflict Detection**

Before adding/updating personality, check semantic conflicts:

**Conflicts**: "粗枝大叶/粗心" ↔ "细心/认真负责" | "内向" ↔ "外向" | "悲观" ↔ "乐观"

**Resolution**:
a) **Insufficient evidence** (1-2 new vs 4+ existing) → SKIP
   Ex: 1 criticism "粗枝大叶" vs "认真负责"(degree 4, 4 evidence) → SKIP

b) **Moderate conflict** (3-4 new evidence) → UPDATE reduce degree
   Ex: 3 "粗心" evidence → UPDATE "认真负责" from degree 5 to 3

c) **Real change** (5+ new recent vs old existing) → DELETE old + ADD new
   Ex: 6 recent "外向" evidence vs "内向"(1yr ago) → DELETE "内向", ADD "外向"

d) **❗Complex coexistence** (RARE - both have 5+ evidence + clear context)
   Ex: "内向"(5 work evidence) + "外向"(5 family evidence) → Both valid
   ❌ Most conflicts should use a/b/c - coexistence is RARE

**Degree Reasonableness**:
- degree 1-2: 1-2 evidence | degree 3: 3-5 evidence | degree 4: 5-8 evidence | degree 5: 8+ evidence
- ❌ Single incident ≠ degree 4-5

## Examples

**Ex1: ADD**
User: "开始喜欢爬山了" | Existing: No "爬山"
```json
{{"additional_profile": {{"interests": [{{"id": null, "event": "ADD", "name": "爬山", "degree": 3, "evidence": [{{"text": "开始喜欢爬山了"}}]}}]}}}}
```

**Ex2: UPDATE degree**
User: "现在是Python专家了" | Existing: {{"id": "5", "name": "Python", "degree": 3}}
```json
{{"additional_profile": {{"skills": [{{"id": "5", "event": "UPDATE", "name": "Python", "degree": 5, "evidence": [{{"text": "现在是Python专家了"}}]}}]}}}}
```

**Ex3: DELETE (real change)**
User: "不喜欢足球了" | Existing: {{"id": "1", "name": "足球", "degree": 4, "evidence": [10 entries, 8mo ago]}}
Analysis: Old evidence → Real change
```json
{{"additional_profile": {{"interests": [{{"id": "1", "event": "DELETE", "name": "足球"}}]}}}}
```

**Ex4: Personality Conflict - SKIP insufficient evidence**
User: "今天被批评粗枝大叶" | Existing: {{"id": "1", "name": "认真负责", "degree": 4, "evidence": [4 entries]}}
Analysis: 1 criticism vs 4 strong evidence → SKIP
```json
{{"additional_profile": {{}}}}
```

**Ex5: Personality Conflict - Real change**
User: "我变得很外向了，常主动社交" + 5 more | Existing: {{"id": "3", "name": "内向", "degree": 4, "evidence": [3 entries, 10mo ago]}}
Analysis: 6 recent vs 3 old → DELETE old, ADD new
```json
{{
  "additional_profile": {{
    "personality": [
      {{"id": "3", "event": "DELETE", "name": "内向"}},
      {{"id": null, "event": "ADD", "name": "外向", "degree": 4, "evidence": [
        {{"text": "我变得很外向了，常主动社交"}},
        {{"text": "周末参加了三场聚会"}},
        {{"text": "主动组织团队活动"}},
        {{"text": "认识了很多新朋友"}},
        {{"text": "享受社交带来的快乐"}},
        {{"text": "同事说我判若两人"}}
      ]}}
    ]
  }}
}}
```

---
Return JSON only.
"""