-- Migration: Add education fields to user_profile table
-- Date: 2025-10-05
-- Description: Add school_name, grade, class_name for children (3-9 years old)
-- Usage: psql -U your_user -d your_database -f scripts/migrations/001_add_education_fields.sql

-- Add education-related columns
ALTER TABLE user_profile.user_profile
ADD COLUMN IF NOT EXISTS school_name VARCHAR(200),
ADD COLUMN IF NOT EXISTS grade VARCHAR(50),
ADD COLUMN IF NOT EXISTS class_name VARCHAR(50);

-- Add comments
COMMENT ON COLUMN user_profile.user_profile.school_name IS '学校名称 (School name, e.g., 北京实验小学)';
COMMENT ON COLUMN user_profile.user_profile.grade IS '年级，支持中英文 (Grade, supports Chinese/English, e.g., 三年级/Grade 3)';
COMMENT ON COLUMN user_profile.user_profile.class_name IS '班级，可选 (Class name, optional, e.g., 3班/Class 3A)';

-- Verify columns were added
DO $$
DECLARE
    col_count INTEGER;
BEGIN
    SELECT COUNT(*)
    INTO col_count
    FROM information_schema.columns
    WHERE table_schema = 'user_profile'
      AND table_name = 'user_profile'
      AND column_name IN ('school_name', 'grade', 'class_name');

    IF col_count = 3 THEN
        RAISE NOTICE 'Migration 001 completed successfully! Added 3 education fields.';
    ELSE
        RAISE WARNING 'Migration 001 may have issues. Expected 3 columns, found %', col_count;
    END IF;
END $$;