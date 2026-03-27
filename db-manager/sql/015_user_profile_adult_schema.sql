-- Adult profile schema compatibility migration for existing deployments.
ALTER TABLE user_profile.user_profile
DROP COLUMN IF EXISTS school_name,
DROP COLUMN IF EXISTS grade,
DROP COLUMN IF EXISTS class_name;

ALTER TABLE user_profile.user_profile
ADD COLUMN IF NOT EXISTS occupation VARCHAR(100),
ADD COLUMN IF NOT EXISTS company VARCHAR(200),
ADD COLUMN IF NOT EXISTS education_level VARCHAR(50),
ADD COLUMN IF NOT EXISTS university VARCHAR(200),
ADD COLUMN IF NOT EXISTS major VARCHAR(100);
