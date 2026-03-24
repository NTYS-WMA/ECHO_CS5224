-- 初始化pgvector扩展
CREATE EXTENSION IF NOT EXISTS vector;

-- 验证扩展已安装
SELECT * FROM pg_extension WHERE extname = 'vector';

-- 创建用于测试的示例表 (mem0会自动创建实际的表)
-- CREATE TABLE IF NOT EXISTS test_vectors (
--     id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
--     vector vector(1536),
--     payload JSONB,
--     created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
-- );

-- 显示可用的操作符
SELECT
    op.oprname as operator,
    op.oprleft::regtype as left_type,
    op.oprright::regtype as right_type,
    op.oprresult::regtype as result_type
FROM pg_operator op
JOIN pg_type lt ON op.oprleft = lt.oid
WHERE lt.typname = 'vector'
ORDER BY op.oprname;