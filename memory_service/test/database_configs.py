#!/usr/bin/env python3
"""
Mem0 数据库配置示例
支持PostgreSQL、MySQL等各种数据库配置
"""

# PostgreSQL (推荐) - 使用pgvector扩展
POSTGRESQL_CONFIG = {
    "version": "v1.1",
    "vector_store": {
        "provider": "pgvector",
        "config": {
            "dbname": "mem0_db",
            "collection_name": "memories",
            "embedding_model_dims": 1536,  # 根据你的embedding模型调整
            "user": "mem0_user",
            "password": "your_password",
            "host": "localhost",
            "port": 5432,
            "hnsw": True,  # 启用HNSW索引以获得更快搜索
            "diskann": False,  # 可选的DiskANN索引
            "minconn": 1,
            "maxconn": 10,
            "sslmode": "prefer"  # SSL模式: require, prefer, disable
        }
    },
    "llm": {
        "provider": "deepseek",
        "config": {
            "api_key": "your_deepseek_api_key",
            "model": "deepseek-chat",
            "temperature": 0.2,
            "max_tokens": 2000
        }
    },
    "embedder": {
        "provider": "openai",
        "config": {
            "api_key": "your_openai_api_key",
            "model": "text-embedding-3-small"
        }
    },
    "history_db_path": "/app/history/history.db"
}

# PostgreSQL - 使用连接字符串方式
POSTGRESQL_CONNECTION_STRING_CONFIG = {
    "version": "v1.1",
    "vector_store": {
        "provider": "pgvector",
        "config": {
            "connection_string": "postgresql://mem0_user:your_password@localhost:5432/mem0_db?sslmode=prefer",
            "collection_name": "memories",
            "embedding_model_dims": 1536,
            "hnsw": True
        }
    },
    # 其他配置同上...
}

# Supabase (托管PostgreSQL)
SUPABASE_CONFIG = {
    "version": "v1.1",
    "vector_store": {
        "provider": "supabase",
        "config": {
            "url": "https://your-project.supabase.co",
            "api_key": "your-supabase-api-key",
            "table_name": "memories",
            "embedding_model_dims": 1536
        }
    },
    # 其他配置...
}

# MongoDB (NoSQL选项)
MONGODB_CONFIG = {
    "version": "v1.1",
    "vector_store": {
        "provider": "mongodb",
        "config": {
            "host": "localhost",
            "port": 27017,
            "username": "mem0_user",
            "password": "your_password",
            "database": "mem0_db",
            "collection": "memories",
            "index_name": "vector_index",
            "embedding_model_dims": 1536
        }
    },
    # 其他配置...
}

# Redis (内存数据库，适合快速原型)
REDIS_CONFIG = {
    "version": "v1.1",
    "vector_store": {
        "provider": "redis",
        "config": {
            "host": "localhost",
            "port": 6379,
            "password": "your_redis_password",  # 可选
            "db": 0,
            "index_name": "mem0_index",
            "collection_name": "memories",
            "embedding_model_dims": 1536
        }
    },
    # 其他配置...
}

# Chroma (轻量级向量数据库)
CHROMA_CONFIG = {
    "version": "v1.1",
    "vector_store": {
        "provider": "chroma",
        "config": {
            "collection_name": "memories",
            "host": "localhost",
            "port": 8000,
            "path": "/tmp/chroma"  # 本地文件存储路径
        }
    },
    # 其他配置...
}

# Pinecone (云向量数据库)
PINECONE_CONFIG = {
    "version": "v1.1",
    "vector_store": {
        "provider": "pinecone",
        "config": {
            "api_key": "your_pinecone_api_key",
            "index_name": "mem0-index",
            "environment": "your_pinecone_environment",
            "dimension": 1536
        }
    },
    # 其他配置...
}

# 当前使用的Qdrant配置（参考）
CURRENT_QDRANT_CONFIG = {
    "version": "v1.1",
    "vector_store": {
        "provider": "qdrant",
        "config": {
            "host": "qdrant",
            "port": 6333,
            "collection_name": "memories"
        }
    },
    "llm": {
        "provider": "deepseek",
        "config": {
            "api_key": "your_deepseek_api_key",
            "model": "deepseek-chat",
            "temperature": 0.2,
            "max_tokens": 2000
        }
    },
    "embedder": {
        "provider": "openai",
        "config": {
            "api_key": "your_openai_api_key",
            "model": "text-embedding-3-small"
        }
    },
    "history_db_path": "/app/history/history.db"
}

def get_config_by_name(config_name: str):
    """根据名称获取配置"""
    configs = {
        "postgresql": POSTGRESQL_CONFIG,
        "postgresql_connection": POSTGRESQL_CONNECTION_STRING_CONFIG,
        "supabase": SUPABASE_CONFIG,
        "mongodb": MONGODB_CONFIG,
        "redis": REDIS_CONFIG,
        "chroma": CHROMA_CONFIG,
        "pinecone": PINECONE_CONFIG,
        "qdrant": CURRENT_QDRANT_CONFIG
    }
    return configs.get(config_name.lower())

def print_config_info():
    """打印所有可用配置的信息"""
    print("🗄️  Mem0 支持的数据库配置选项:")
    print("=" * 60)

    configs_info = [
        ("postgresql", "PostgreSQL + pgvector", "✅ 推荐，功能完整，性能优秀"),
        ("supabase", "Supabase (托管PostgreSQL)", "☁️ 云托管，无需维护"),
        ("mongodb", "MongoDB", "📊 NoSQL，适合文档存储"),
        ("redis", "Redis", "⚡ 内存数据库，速度快"),
        ("chroma", "Chroma", "🪶 轻量级，适合开发测试"),
        ("pinecone", "Pinecone", "☁️ 专业向量数据库"),
        ("qdrant", "Qdrant (当前)", "🎯 高性能向量搜索")
    ]

    for name, desc, note in configs_info:
        print(f"  {name:15} - {desc:25} {note}")

    print("\n📖 使用方法:")
    print("  config = get_config_by_name('postgresql')")
    print("  memory = Memory.from_config(config)")

if __name__ == "__main__":
    print_config_info()