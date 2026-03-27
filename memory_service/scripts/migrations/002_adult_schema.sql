-- Migration: Replace child education fields with adult work & education fields
-- Date: 2026-03-24
-- Description: Drop school_name/grade/class_name; add occupation/company/education_level/university/major
-- Usage: psql -U your_user -d your_database -f scripts/migrations/002_adult_schema.sql

-- Remove child-specific columns
ALTER TABLE user_profile.user_profile
DROP COLUMN IF EXISTS school_name,
DROP COLUMN IF EXISTS grade,
DROP COLUMN IF EXISTS class_name;

-- Add adult work & education columns
ALTER TABLE user_profile.user_profile
ADD COLUMN IF NOT EXISTS occupation VARCHAR(100),
ADD COLUMN IF NOT EXISTS company VARCHAR(200),
ADD COLUMN IF NOT EXISTS education_level VARCHAR(50),
ADD COLUMN IF NOT EXISTS university VARCHAR(200),
ADD COLUMN IF NOT EXISTS major VARCHAR(100);

-- Add comments
COMMENT ON COLUMN user_profile.user_profile.occupation IS 'Current job title or profession';
COMMENT ON COLUMN user_profile.user_profile.company IS 'Current employer or organization';
COMMENT ON COLUMN user_profile.user_profile.education_level IS 'Highest education level (e.g., bachelor, master, PhD)';
COMMENT ON COLUMN user_profile.user_profile.university IS 'Most recent or highest-level university attended';
COMMENT ON COLUMN user_profile.user_profile.major IS 'Field of study or academic major';

-- Verify
DO $$
DECLARE
    new_col_count INTEGER;
    old_col_count INTEGER;
BEGIN
    SELECT COUNT(*)
    INTO new_col_count
    FROM information_schema.columns
    WHERE table_schema = 'user_profile'
      AND table_name = 'user_profile'
      AND column_name IN ('occupation', 'company', 'education_level', 'university', 'major');

    SELECT COUNT(*)
    INTO old_col_count
    FROM information_schema.columns
    WHERE table_schema = 'user_profile'
      AND table_name = 'user_profile'
      AND column_name IN ('school_name', 'grade', 'class_name');

    IF new_col_count = 5 AND old_col_count = 0 THEN
        RAISE NOTICE 'Migration 002 completed successfully! Added 5 adult fields, removed 3 child fields.';
    ELSE
        RAISE WARNING 'Migration 002 may have issues. New columns found: %, old columns remaining: %', new_col_count, old_col_count;
    END IF;
END $$;
