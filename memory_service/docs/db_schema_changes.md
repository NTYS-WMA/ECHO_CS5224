# DB Schema Changes — Adult User Adaptation

## Overview

The memory service was originally built for child users (ages 3–9). It has been adapted for general adult users (ages 14–40). The following documents all database schema changes.

---

## PostgreSQL — `user_profile.user_profile`

### Removed Columns

| Column | Type | Reason |
|--------|------|--------|
| `school_name` | VARCHAR(200) | Child-specific (current school name) |
| `grade` | VARCHAR(50) | Child-specific (e.g. "Grade 3") |
| `class_name` | VARCHAR(50) | Child-specific (e.g. "Class 3A") |

### Added Columns

| Column | Type | Description | Example |
|--------|------|-------------|---------|
| `occupation` | VARCHAR(100) | Current job title / profession | `"software engineer"` |
| `company` | VARCHAR(200) | Current employer | `"Google"` |
| `education_level` | VARCHAR(50) | Highest degree attained | `"master"`, `"bachelor"`, `"PhD"` |
| `university` | VARCHAR(200) | Most recent / highest university | `"NUS"` |
| `major` | VARCHAR(100) | Field of study | `"Computer Science"` |

### Unchanged Columns

`user_id`, `created_at`, `updated_at`, `name`, `nickname`, `english_name`, `birthday`, `gender`, `nationality`, `hometown`, `current_city`, `timezone`, `language` — all unchanged.

### Migration Script

`scripts/migrations/002_adult_schema.sql` — drops the 3 old columns and adds the 5 new ones. Safe to run on an existing database.

```sql
ALTER TABLE user_profile.user_profile
DROP COLUMN IF EXISTS school_name,
DROP COLUMN IF EXISTS grade,
DROP COLUMN IF EXISTS class_name;

ALTER TABLE user_profile.user_profile
ADD COLUMN IF NOT EXISTS occupation      VARCHAR(100),
ADD COLUMN IF NOT EXISTS company         VARCHAR(200),
ADD COLUMN IF NOT EXISTS education_level VARCHAR(50),
ADD COLUMN IF NOT EXISTS university      VARCHAR(200),
ADD COLUMN IF NOT EXISTS major           VARCHAR(100);
```

---

## MongoDB — `user_additional_profile`

**No schema changes.** The existing structure (interests, skills, personality, social_context, learning_preferences) is already generic and applies to adults without modification.

---

## Notes

- All new columns are nullable — no default values required.
- The `init_userprofile_db.sql` initialization script has also been updated to reflect the new schema (for fresh deployments).
- If deploying to an existing database, run `002_adult_schema.sql` only; do **not** re-run `init_userprofile_db.sql`.
