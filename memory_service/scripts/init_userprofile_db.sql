-- UserProfile Database Initialization Script
-- This script creates the necessary schema and tables for UserProfile module

-- Create schema
CREATE SCHEMA IF NOT EXISTS user_profile;

-- Create user_profile table
CREATE TABLE IF NOT EXISTS user_profile.user_profile (
    user_id VARCHAR(50) PRIMARY KEY,
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,

    -- Basic Information Fields
    name VARCHAR(100),
    nickname VARCHAR(100),
    english_name VARCHAR(100),
    birthday DATE,
    gender VARCHAR(10),
    nationality VARCHAR(50),
    hometown VARCHAR(100),
    current_city VARCHAR(100),
    timezone VARCHAR(50),
    language VARCHAR(50),

    -- Education Fields (for children 3-9 years old)
    school_name VARCHAR(200),
    grade VARCHAR(50),
    class_name VARCHAR(50)
);

-- Create indexes
CREATE INDEX IF NOT EXISTS idx_user_profile_name ON user_profile.user_profile(name);
CREATE INDEX IF NOT EXISTS idx_user_profile_updated_at ON user_profile.user_profile(updated_at);

-- Add comments for documentation
COMMENT ON SCHEMA user_profile IS 'Schema for user profile data';
COMMENT ON TABLE user_profile.user_profile IS 'Stores basic user profile information';
COMMENT ON COLUMN user_profile.user_profile.user_id IS 'Unique user identifier';
COMMENT ON COLUMN user_profile.user_profile.created_at IS 'Timestamp when profile was created';
COMMENT ON COLUMN user_profile.user_profile.updated_at IS 'Timestamp when profile was last updated';
COMMENT ON COLUMN user_profile.user_profile.name IS 'User full name';
COMMENT ON COLUMN user_profile.user_profile.nickname IS 'User nickname or preferred name';
COMMENT ON COLUMN user_profile.user_profile.english_name IS 'User English name';
COMMENT ON COLUMN user_profile.user_profile.birthday IS 'User birthday';
COMMENT ON COLUMN user_profile.user_profile.gender IS 'User gender (male/female/other)';
COMMENT ON COLUMN user_profile.user_profile.nationality IS 'User nationality';
COMMENT ON COLUMN user_profile.user_profile.hometown IS 'User hometown';
COMMENT ON COLUMN user_profile.user_profile.current_city IS 'User current city of residence';
COMMENT ON COLUMN user_profile.user_profile.timezone IS 'User timezone (e.g., Asia/Shanghai)';
COMMENT ON COLUMN user_profile.user_profile.language IS 'User preferred language (e.g., zh-CN, en-US)';
COMMENT ON COLUMN user_profile.user_profile.school_name IS '学校名称 (School name, e.g., 北京实验小学)';
COMMENT ON COLUMN user_profile.user_profile.grade IS '年级，支持中英文 (Grade, supports Chinese/English, e.g., 三年级/Grade 3)';
COMMENT ON COLUMN user_profile.user_profile.class_name IS '班级，可选 (Class name, optional, e.g., 3班/Class 3A)';

-- Grant permissions (adjust as needed for your environment)
-- GRANT ALL PRIVILEGES ON SCHEMA user_profile TO your_app_user;
-- GRANT ALL PRIVILEGES ON ALL TABLES IN SCHEMA user_profile TO your_app_user;

-- Success message
DO $$
BEGIN
    RAISE NOTICE 'UserProfile database initialization completed successfully!';
    RAISE NOTICE 'Schema: user_profile';
    RAISE NOTICE 'Table: user_profile.user_profile';
END $$;
