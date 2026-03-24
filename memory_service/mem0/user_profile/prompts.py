"""
Prompts for UserProfile LLM calls
"""

EXTRACT_PROFILE_PROMPT = """Extract user profile from conversation. Return JSON only.

## Output Format
```json
{{
  "basic_info": {{
    "name": "Alice",
    "current_city": "Singapore",
    "occupation": "Software Engineer",
    "company": "Google",
    "education_level": "master",
    "university": "NUS",
    "major": "Computer Science"
  }},
  "additional_profile": {{
    "interests": [{{"name": "hiking", "degree": 4, "evidence": [{{"text": "go hiking every weekend"}}]}}],
    "skills": [{{"name": "Python", "degree": 3, "evidence": [{{"text": "built data tools at work"}}]}}],
    "personality": [{{"name": "outgoing", "degree": 4, "evidence": [{{"text": "loves socializing"}}]}}],
    "social_context": {{
      "family": {{"father": {{"name": "John", "info": ["doctor"]}}}},
      "friends": [{{"name": "Jack", "info": ["plays basketball together"]}}],
      "others": [{{"name": null, "relation": "uncle", "info": ["engineer"]}}]
    }},
    "learning_preferences": {{"preferred_time": "evening", "preferred_style": "visual"}}
  }}
}}
```

## Rules

**1. ❗Language Consistency - MOST CRITICAL**
- Preserve user's EXACT words - NO translation between languages
- Chinese → Chinese | English → English | mixed → mixed
- ❌ "退休了" → "retired" | ✅ "退休了" → "退休了"

**2. Evidence & Degree**
- Evidence: text only (NO timestamp - backend handles it)
- Degree (1-5): interests=liking level, skills=proficiency, personality=strength
- Every attribute needs evidence from conversation

**3. basic_info fields**
- name, nickname, english_name, birthday, gender, nationality, hometown, current_city, timezone, language
- occupation (job title), company (employer), education_level (bachelor/master/PhD/etc.), university, major

**4. social_context Schema**

| Field | Type | Members | Rules |
|-------|------|---------|-------|
| **family** | object | spouse, father, mother, son[], daughter[], brother[], sister[], grandfather_*, grandmother_*, father_in_law, mother_in_law, grandson[], granddaughter[] | Direct relatives only. name=actual name or null (NOT relation word) |
| **friends** | array | name + info | NO relation field |
| **others** | array | name + relation + info | Collateral relatives (uncle/aunt/cousin), teachers, colleagues, etc. |

**Critical**:
- name field: actual name like "Alice" OR null (❌ NOT "wife"/"spouse")
- Collateral relatives (uncle/aunt/cousin) → others (use "relation" field to specify)
- Unified format: family/friends have name+info, others have name+relation+info

**5. learning_preferences** - Object (NOT array)
- preferred_time: "morning"/"afternoon"/"evening"
- preferred_style: "visual"/"auditory"/"kinesthetic"
- difficulty_level: "beginner"/"intermediate"/"advanced"

**6. Extract Explicit Info Only**
- Don't infer or guess
- Omit fields with no data (don't include empty keys)

**7. ❗CRITICAL: Only Extract What USER Says About THEMSELVES**
- **ONLY extract** information the user explicitly states about their OWN life
- **IGNORE** AI assistant responses even if mislabeled as "user"
- **Ignore patterns that indicate AI responses**:
  - Questions (e.g., "What's your hobby?", "你喜欢什么运动？")
  - Suggestions (e.g., "You should try...", "我建议你...")
  - Explanations (e.g., "This is because...", "这是因为...")
  - Acknowledgments (e.g., "Got it, I understand", "好的，我明白了")
  - Generic responses without personal info
- **Extract patterns from USER**:
  - Self-statements (e.g., "I'm a software engineer", "我叫李明")
  - Personal experiences (e.g., "I went hiking yesterday", "昨天我去爬山了")
  - Personal preferences (e.g., "I prefer learning at night", "我喜欢晚上学习")

## Examples

**Ex1: Basic + Work + Education + Interest**
User: "I'm Alice, living in Singapore. I work as a software engineer at Google. Got my master's in CS from NUS. Recently got into photography, shooting every weekend."
```json
{{
  "basic_info": {{
    "name": "Alice",
    "current_city": "Singapore",
    "occupation": "software engineer",
    "company": "Google",
    "education_level": "master",
    "university": "NUS",
    "major": "CS"
  }},
  "additional_profile": {{
    "interests": [{{"name": "photography", "degree": 4, "evidence": [{{"text": "recently got into photography, shooting every weekend"}}]}}]
  }}
}}
```

**Ex2: Social Context - Complete**
User: "My dad John is a doctor, mom is a teacher. My older brother Tom lives in New York. My uncle is an engineer. My wife Sarah is a designer, our daughter Emma just turned 3."
```json
{{
  "additional_profile": {{
    "social_context": {{
      "family": {{
        "father": {{"name": "John", "info": ["doctor"]}},
        "mother": {{"name": null, "info": ["teacher"]}},
        "brother": [{{"name": "Tom", "info": ["older brother", "lives in New York"]}}],
        "spouse": {{"name": "Sarah", "info": ["designer"]}},
        "daughter": [{{"name": "Emma", "info": ["3 years old"]}}]
      }},
      "others": [{{"name": null, "relation": "uncle", "info": ["engineer"]}}]
    }}
  }}
}}
```
Note: brother/son/daughter are arrays (can have multiple); spouse/father/mother are objects (single). Collateral relative (uncle) goes to others.

**Ex3: IGNORE AI Assistant Responses** ❌
Conversation:
- User: "I've been learning Python lately"
- Assistant: "Great! I'd suggest starting with the basics, then data structures. Python is very beginner-friendly."
- User: "Sure, I'll give it a try"

Extract ONLY: {{"additional_profile": {{"skills": [{{"name": "Python", "degree": 2, "evidence": [{{"text": "I've been learning Python lately"}}]}}]}}}}

**DO NOT extract**:
- ❌ "I'd suggest..." (AI suggestion)
- ❌ "Python is very beginner-friendly" (AI opinion, not user's)
- ❌ "Sure, I'll give it a try" (no new profile info, just acknowledgment)

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
  "basic_info": {{"name": "Alice"}},
  "additional_profile": {{
    "interests": [
      {{"id": "1", "event": "UPDATE", "name": "football", "degree": 5, "evidence": [{{"text": "won another match"}}]}},
      {{"id": null, "event": "ADD", "name": "photography", "degree": 3, "evidence": [{{"text": "bought a camera"}}]}}
    ],
    "personality": [
      {{"id": "2", "event": "DELETE", "name": "introverted"}}
    ]
  }}
}}
```

## Rules

**1. Language Consistency** - Keep user's original language (see extraction rules)

**2. Timestamps** - Return evidence text only (NO timestamp - backend adds it)

**3. ID Mapping** - Use existing ID for UPDATE/DELETE, null for ADD

**4. Evidence Analysis for Contradictions**
- Strong recent evidence (10+ entries, <3mo) + user says they no longer like it → reduce degree (temp mood)
- Weak/old evidence (1-2 entries or >6mo) + user says they no longer like it → DELETE (real change)

**5. Degree** - Combine new + existing evidence to determine

**6. basic_info** - Direct upsert (NO events)

**7. Evidence** - Return NEW evidence only (backend merges with existing)

**8. ❗social_context - DEEP MERGE**
- Return ONLY mentioned relationships with events (ADD/UPDATE/DELETE)
- Backend preserves unmentioned relationships
- Example: To add spouse, return `{{"family": {{"spouse": {{"event": "ADD", "name": "Sarah", "info": [...]}}}}}}`
- Backend will merge with existing father/mother (DON'T return them)

**9. ❗Personality Conflict Detection**

Before adding/updating personality, check semantic conflicts:

**Conflicts**: "careless/sloppy" ↔ "careful/responsible" | "introverted" ↔ "extroverted" | "pessimistic" ↔ "optimistic"

**Resolution**:
a) **Insufficient evidence** (1-2 new vs 4+ existing) → SKIP
   Ex: 1 criticism "careless" vs "responsible"(degree 4, 4 evidence) → SKIP

b) **Moderate conflict** (3-4 new evidence) → UPDATE reduce degree
   Ex: 3 "careless" evidence → UPDATE "responsible" from degree 5 to 3

c) **Real change** (5+ new recent vs old existing) → DELETE old + ADD new
   Ex: 6 recent "extroverted" evidence vs "introverted"(1yr ago) → DELETE "introverted", ADD "extroverted"

d) **❗Complex coexistence** (RARE - both have 5+ evidence + clear context)
   Ex: "introverted"(5 work evidence) + "extroverted"(5 family evidence) → Both valid
   ❌ Most conflicts should use a/b/c - coexistence is RARE

**Degree Reasonableness**:
- degree 1-2: 1-2 evidence | degree 3: 3-5 evidence | degree 4: 5-8 evidence | degree 5: 8+ evidence
- ❌ Single incident ≠ degree 4-5

## Examples

**Ex1: ADD**
User: "started enjoying hiking" | Existing: No "hiking"
```json
{{"additional_profile": {{"interests": [{{"id": null, "event": "ADD", "name": "hiking", "degree": 3, "evidence": [{{"text": "started enjoying hiking"}}]}}]}}}}
```

**Ex2: UPDATE degree**
User: "I'm a Python expert now" | Existing: {{"id": "5", "name": "Python", "degree": 3}}
```json
{{"additional_profile": {{"skills": [{{"id": "5", "event": "UPDATE", "name": "Python", "degree": 5, "evidence": [{{"text": "I'm a Python expert now"}}]}}]}}}}
```

**Ex3: DELETE (real change)**
User: "I don't like football anymore" | Existing: {{"id": "1", "name": "football", "degree": 4, "evidence": [10 entries, 8mo ago]}}
Analysis: Old evidence → Real change
```json
{{"additional_profile": {{"interests": [{{"id": "1", "event": "DELETE", "name": "football"}}]}}}}
```

**Ex4: Personality Conflict - SKIP insufficient evidence**
User: "got criticized for being careless today" | Existing: {{"id": "1", "name": "responsible", "degree": 4, "evidence": [4 entries]}}
Analysis: 1 incident vs 4 strong evidence → SKIP
```json
{{"additional_profile": {{}}}}
```

**Ex5: Personality Conflict - Real change**
User: "I've become very outgoing, always initiating social activities" + 5 more | Existing: {{"id": "3", "name": "introverted", "degree": 4, "evidence": [3 entries, 10mo ago]}}
Analysis: 6 recent vs 3 old → DELETE old, ADD new
```json
{{
  "additional_profile": {{
    "personality": [
      {{"id": "3", "event": "DELETE", "name": "introverted"}},
      {{"id": null, "event": "ADD", "name": "extroverted", "degree": 4, "evidence": [
        {{"text": "I've become very outgoing, always initiating social activities"}},
        {{"text": "attended three parties last weekend"}},
        {{"text": "organized a team outing"}},
        {{"text": "made a lot of new friends"}},
        {{"text": "enjoy the energy from socializing"}},
        {{"text": "colleagues said I'm like a different person"}}
      ]}}
    ]
  }}
}}
```

---
Return JSON only.
"""