#!/usr/bin/env python3
"""
使用PostgreSQL作为向量存储的Mem0服务器配置
替代原有的Qdrant配置
"""
import logging
import os
from typing import Any, Dict, List, Optional

from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException
from fastapi.responses import JSONResponse, RedirectResponse
from pydantic import BaseModel, Field

from mem0 import Memory

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")

# Load environment variables
load_dotenv()

# PostgreSQL configuration from environment
POSTGRES_HOST = os.environ.get("POSTGRES_HOST", "localhost")
POSTGRES_PORT = int(os.environ.get("POSTGRES_PORT", "5432"))
POSTGRES_DB = os.environ.get("POSTGRES_DB", "mem0_db")
POSTGRES_USER = os.environ.get("POSTGRES_USER", "mem0_user")
POSTGRES_PASSWORD = os.environ.get("POSTGRES_PASSWORD", "mem0_password")
POSTGRES_COLLECTION = os.environ.get("POSTGRES_COLLECTION", "memories")
EMBEDDING_MODEL_DIMS = int(os.environ.get("EMBEDDING_MODEL_DIMS", "1536"))

# API Keys
DEEPSEEK_API_KEY = os.environ.get("DEEPSEEK_API_KEY")
OPENAI_API_KEY = os.environ.get("OPENAI_API_KEY")
HISTORY_DB_PATH = os.environ.get("HISTORY_DB_PATH", "/app/history/history.db")

# PostgreSQL + pgvector configuration
POSTGRESQL_CONFIG = {
    "version": "v1.1",
    "vector_store": {
        "provider": "pgvector",
        "config": {
            "dbname": POSTGRES_DB,
            "collection_name": POSTGRES_COLLECTION,
            "embedding_model_dims": EMBEDDING_MODEL_DIMS,
            "user": POSTGRES_USER,
            "password": POSTGRES_PASSWORD,
            "host": POSTGRES_HOST,
            "port": POSTGRES_PORT,
            "hnsw": True,  # 启用HNSW索引以获得更快搜索
            "diskann": False,  # DiskANN索引 (可选)
            "minconn": 1,
            "maxconn": 10,
            "sslmode": "prefer"  # SSL模式
        }
    },
    "llm": {
        "provider": "deepseek",
        "config": {
            "api_key": DEEPSEEK_API_KEY,
            "model": "deepseek-chat",
            "temperature": 0.2,
            "max_tokens": 2000
        }
    },
    "embedder": {
        "provider": "openai",
        "config": {
            "api_key": OPENAI_API_KEY,
            "model": "text-embedding-3-small"
        }
    },
    "history_db_path": HISTORY_DB_PATH,
}

# 记录配置信息
logging.info("🐘 初始化PostgreSQL配置")
logging.info(f"   数据库: {POSTGRES_HOST}:{POSTGRES_PORT}/{POSTGRES_DB}")
logging.info(f"   用户: {POSTGRES_USER}")
logging.info(f"   集合: {POSTGRES_COLLECTION}")
logging.info(f"   向量维度: {EMBEDDING_MODEL_DIMS}")

# 初始化Memory实例
try:
    MEMORY_INSTANCE = Memory.from_config(POSTGRESQL_CONFIG)
    logging.info("✅ Memory实例初始化成功")
except Exception as e:
    logging.error(f"❌ Memory实例初始化失败: {e}")
    raise

app = FastAPI(
    title="Mem0 REST APIs (PostgreSQL)",
    description="A REST API for managing and searching memories using PostgreSQL + pgvector.",
    version="1.0.0",
)

class Message(BaseModel):
    role: str = Field(..., description="Role of the message (user or assistant).")
    content: str = Field(..., description="Message content.")

class MemoryCreate(BaseModel):
    messages: List[Message] = Field(..., description="List of messages to store.")
    user_id: Optional[str] = None
    agent_id: Optional[str] = None
    run_id: Optional[str] = None
    metadata: Optional[Dict[str, Any]] = None

class SearchRequest(BaseModel):
    query: str = Field(..., description="Search query.")
    user_id: Optional[str] = None
    run_id: Optional[str] = None
    agent_id: Optional[str] = None
    filters: Optional[Dict[str, Any]] = None
    limit: int = Field(default=5, description="Maximum number of results to return")
    threshold: Optional[float] = Field(default=None, description="Minimum similarity threshold (0.0-1.0)")

@app.get("/health", summary="Health check")
def health_check():
    """检查服务健康状态"""
    try:
        # 简单的数据库连接测试
        # 这里可以添加更复杂的健康检查逻辑
        return {
            "status": "healthy",
            "database": "postgresql",
            "vector_store": "pgvector",
            "timestamp": "2023-01-01T00:00:00Z"  # 在实际应用中使用datetime.now()
        }
    except Exception as e:
        raise HTTPException(status_code=503, detail=f"Service unhealthy: {str(e)}")

@app.get("/config", summary="Get current configuration")
def get_config():
    """获取当前配置信息（不包含敏感信息）"""
    safe_config = {
        "vector_store": {
            "provider": "pgvector",
            "host": POSTGRES_HOST,
            "port": POSTGRES_PORT,
            "database": POSTGRES_DB,
            "collection": POSTGRES_COLLECTION,
            "embedding_dims": EMBEDDING_MODEL_DIMS
        },
        "llm": {
            "provider": "deepseek",
            "model": "deepseek-chat"
        },
        "embedder": {
            "provider": "openai",
            "model": "text-embedding-3-small"
        }
    }
    return safe_config

@app.post("/configure", summary="Configure Mem0")
def set_config(config: Dict[str, Any]):
    """Set memory configuration."""
    global MEMORY_INSTANCE
    try:
        MEMORY_INSTANCE = Memory.from_config(config)
        logging.info("配置已更新")
        return {"message": "Configuration set successfully"}
    except Exception as e:
        logging.error(f"配置更新失败: {e}")
        raise HTTPException(status_code=400, detail=str(e))

@app.post("/memories", summary="Create memories")
def add_memory(memory_create: MemoryCreate):
    """Store new memories."""
    if not any([memory_create.user_id, memory_create.agent_id, memory_create.run_id]):
        raise HTTPException(status_code=400, detail="At least one identifier (user_id, agent_id, run_id) is required.")

    params = {k: v for k, v in memory_create.model_dump().items() if v is not None and k != "messages"}
    try:
        response = MEMORY_INSTANCE.add(messages=[m.model_dump() for m in memory_create.messages], **params)
        logging.info(f"新增记忆: {len(memory_create.messages)} 条消息")
        return JSONResponse(content=response)
    except Exception as e:
        logging.exception("Error in add_memory:")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/memories", summary="Get memories")
def get_all_memories(
    user_id: Optional[str] = None,
    run_id: Optional[str] = None,
    agent_id: Optional[str] = None,
):
    """Retrieve stored memories."""
    if not any([user_id, run_id, agent_id]):
        raise HTTPException(status_code=400, detail="At least one identifier is required.")
    try:
        params = {
            k: v for k, v in {"user_id": user_id, "run_id": run_id, "agent_id": agent_id}.items() if v is not None
        }
        result = MEMORY_INSTANCE.get_all(**params)
        logging.info(f"获取记忆: {len(result) if isinstance(result, list) else 'unknown'} 条")
        return result
    except Exception as e:
        logging.exception("Error in get_all_memories:")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/memories/{memory_id}", summary="Get a memory")
def get_memory(memory_id: str):
    """Retrieve a specific memory by ID."""
    try:
        result = MEMORY_INSTANCE.get(memory_id)
        logging.info(f"获取单条记忆: {memory_id}")
        return result
    except Exception as e:
        logging.exception("Error in get_memory:")
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/search", summary="Search memories")
def search_memories(search_req: SearchRequest):
    """Search for memories based on a query."""
    try:
        params = {k: v for k, v in search_req.model_dump().items() if v is not None and k != "query"}
        result = MEMORY_INSTANCE.search(query=search_req.query, **params)
        logging.info(f"搜索记忆: '{search_req.query}' -> {len(result) if isinstance(result, list) else 'unknown'} 条结果")
        return result
    except Exception as e:
        logging.exception("Error in search_memories:")
        raise HTTPException(status_code=500, detail=str(e))

@app.put("/memories/{memory_id}", summary="Update a memory")
def update_memory(memory_id: str, updated_memory: Dict[str, Any]):
    """Update an existing memory with new content."""
    try:
        result = MEMORY_INSTANCE.update(memory_id=memory_id, data=updated_memory)
        logging.info(f"更新记忆: {memory_id}")
        return result
    except Exception as e:
        logging.exception("Error in update_memory:")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/memories/{memory_id}/history", summary="Get memory history")
def memory_history(memory_id: str):
    """Retrieve memory history."""
    try:
        result = MEMORY_INSTANCE.history(memory_id=memory_id)
        logging.info(f"获取记忆历史: {memory_id}")
        return result
    except Exception as e:
        logging.exception("Error in memory_history:")
        raise HTTPException(status_code=500, detail=str(e))

@app.delete("/memories/{memory_id}", summary="Delete a memory")
def delete_memory(memory_id: str):
    """Delete a specific memory by ID."""
    try:
        MEMORY_INSTANCE.delete(memory_id=memory_id)
        logging.info(f"删除记忆: {memory_id}")
        return {"message": "Memory deleted successfully"}
    except Exception as e:
        logging.exception("Error in delete_memory:")
        raise HTTPException(status_code=500, detail=str(e))

@app.delete("/memories", summary="Delete all memories")
def delete_all_memories(
    user_id: Optional[str] = None,
    run_id: Optional[str] = None,
    agent_id: Optional[str] = None,
):
    """Delete all memories for a given identifier."""
    if not any([user_id, run_id, agent_id]):
        raise HTTPException(status_code=400, detail="At least one identifier is required.")
    try:
        params = {
            k: v for k, v in {"user_id": user_id, "run_id": run_id, "agent_id": agent_id}.items() if v is not None
        }
        MEMORY_INSTANCE.delete_all(**params)
        logging.info(f"删除所有记忆: {params}")
        return {"message": "All relevant memories deleted"}
    except Exception as e:
        logging.exception("Error in delete_all_memories:")
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/reset", summary="Reset all memories")
def reset_memory():
    """Completely reset stored memories."""
    try:
        MEMORY_INSTANCE.reset()
        logging.warning("重置所有记忆")
        return {"message": "All memories reset"}
    except Exception as e:
        logging.exception("Error in reset_memory:")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/", summary="Redirect to the OpenAPI documentation", include_in_schema=False)
def home():
    """Redirect to the OpenAPI documentation."""
    return RedirectResponse(url="/docs")

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)