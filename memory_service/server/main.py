import logging
import os
import sys
import json
from typing import Any, Dict, List, Optional
from time import time

from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import JSONResponse, RedirectResponse
from pydantic import BaseModel, Field

from mem0 import Memory
from mem0.user_profile import UserProfile
from middleware import RequestLoggingMiddleware, log_request_body, log_response_data

# Load environment variables first
load_dotenv()

# Get log level from environment variable (default: INFO)
LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO").upper()

# Configure logging with more detailed format for Docker logs
logging.basicConfig(
    level=getattr(logging, LOG_LEVEL),
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    handlers=[
        logging.StreamHandler(sys.stdout)  # Explicitly use stdout for Docker logs
    ]
)

# Set specific log levels for mem0 modules
mem0_log_level = getattr(logging, LOG_LEVEL)
logging.getLogger("mem0.user_profile").setLevel(mem0_log_level)
logging.getLogger("mem0.memory").setLevel(mem0_log_level)

logger = logging.getLogger(__name__)

# PostgreSQL configuration
POSTGRES_HOST = os.environ.get("POSTGRES_HOST", "localhost")
POSTGRES_PORT = int(os.environ.get("POSTGRES_PORT", "5432"))
POSTGRES_DB = os.environ.get("POSTGRES_DB", "postgres")
POSTGRES_USER = os.environ.get("POSTGRES_USER", "postgres")
POSTGRES_PASSWORD = os.environ.get("POSTGRES_PASSWORD", "postgres")
POSTGRES_COLLECTION = os.environ.get("POSTGRES_COLLECTION", "memories")
EMBEDDING_MODEL_DIMS = int(os.environ.get("EMBEDDING_MODEL_DIMS", "1536"))

# API Keys
DEEPSEEK_API_KEY = os.environ.get("DEEPSEEK_API_KEY")
OPENAI_API_KEY = os.environ.get("OPENAI_API_KEY")
DOUBAO_API_KEY = os.environ.get("DOUBAO_API_KEY")
DASHSCOPE_API_KEY = os.environ.get("DASHSCOPE_API_KEY")
HISTORY_DB_PATH = os.environ.get("HISTORY_DB_PATH", "/app/history/history.db")

# VolcEngine DeepSeek API Configuration (优先使用，可选)
# 如果配置了火山引擎，将优先使用火山引擎的DeepSeek；否则使用官方DeepSeek
VOLCENGINE_DEEPSEEK_API_KEY = os.environ.get("VOLCENGINE_DEEPSEEK_API_KEY")
VOLCENGINE_DEEPSEEK_ENDPOINT_ID = os.environ.get("VOLCENGINE_DEEPSEEK_ENDPOINT_ID")
VOLCENGINE_DEEPSEEK_BASE_URL = os.environ.get(
    "VOLCENGINE_DEEPSEEK_BASE_URL",
    "https://ark.cn-beijing.volces.com/api/v3"
)

# PalServer configuration (for cold start)
PALSERVER_BASE_URL = os.environ.get("PALSERVER_BASE_URL")

# Neo4j configuration
# NEO4J_URI = os.environ.get("NEO4J_URI", "bolt://neo4j:7687")
# NEO4J_USERNAME = os.environ.get("NEO4J_USERNAME", "neo4j")
# NEO4J_PASSWORD = os.environ.get("NEO4J_PASSWORD", "mem0graph")

DEFAULT_CONFIG = {
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
            "hnsw": True,
            "diskann": False,
            "minconn": 1,
            "maxconn": 10,
            "sslmode": "disable"
        },
    },
    # "graph_store": {
    #     "provider": "neo4j",
    #     "config": {"url": NEO4J_URI, "username": NEO4J_USERNAME, "password": NEO4J_PASSWORD},
    # },
    # Remove graph_store to disable graph database functionality
    "llm": {
        "provider": "deepseek",
        "config": {
            # 优先使用火山引擎DeepSeek，否则使用官方DeepSeek
            "api_key": VOLCENGINE_DEEPSEEK_API_KEY or DEEPSEEK_API_KEY,
            "model": VOLCENGINE_DEEPSEEK_ENDPOINT_ID or "deepseek-chat",
            "deepseek_base_url": VOLCENGINE_DEEPSEEK_BASE_URL if VOLCENGINE_DEEPSEEK_API_KEY else None,
            "temperature": 0.2,
            "max_tokens": 2000
        }
    },
    "embedder": {
        "provider": "qwen",
        "config": {
            "api_key": DASHSCOPE_API_KEY,
            "model": "text-embedding-v4",
            "qwen_base_url": "https://dashscope.aliyuncs.com/compatible-mode/v1",
            "embedding_dims": 1536
        }
    },
    "history_db_path": HISTORY_DB_PATH,
}


MEMORY_INSTANCE = Memory.from_config(DEFAULT_CONFIG)
USER_PROFILE_INSTANCE = UserProfile(
    MEMORY_INSTANCE.config,
    palserver_base_url=PALSERVER_BASE_URL
)

# Initialize UserProfile databases (auto-create tables if not exist)
try:
    USER_PROFILE_INSTANCE.initialize_databases()
    logger.info("UserProfile databases initialized (tables created if needed)")
except Exception as e:
    logger.warning(f"Failed to initialize UserProfile databases: {e}")
    logger.warning("UserProfile tables may need to be created manually")

logger.info("Mem0 Memory and UserProfile instances initialized successfully")
logger.info(f"Logging level set to: {LOG_LEVEL}")

app = FastAPI(
    title="Mem0 REST APIs",
    description="A REST API for managing and searching memories for your AI Agents and Apps.",
    version="1.0.0",
)

# Add request logging middleware
app.add_middleware(RequestLoggingMiddleware, log_level=LOG_LEVEL)


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


class ProfileCreate(BaseModel):
    messages: List[Message] = Field(..., description="List of messages to extract profile from.")
    user_id: str = Field(..., description="User ID (required).")


class ProfileGetRequest(BaseModel):
    user_id: str = Field(..., description="User ID (required).")
    options: Optional[Dict[str, Any]] = Field(
        default=None,
        description="Query options. e.g., {'fields': ['interests', 'skills']}"
    )


@app.post("/configure", summary="Configure Mem0")
def set_config(config: Dict[str, Any]):
    """Set memory configuration."""
    global MEMORY_INSTANCE
    MEMORY_INSTANCE = Memory.from_config(config)
    return {"message": "Configuration set successfully"}


@app.post("/memories", summary="Create memories")
def add_memory(memory_create: MemoryCreate):
    """Store new memories."""
    if not any([memory_create.user_id, memory_create.agent_id, memory_create.run_id]):
        raise HTTPException(status_code=400, detail="At least one identifier (user_id, agent_id, run_id) is required.")

    params = {k: v for k, v in memory_create.model_dump().items() if v is not None and k != "messages"}
    try:
        response = MEMORY_INSTANCE.add(messages=[m.model_dump() for m in memory_create.messages], **params)
        return JSONResponse(content=response)
    except Exception as e:
        logging.exception("Error in add_memory:")  # This will log the full traceback
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
        return MEMORY_INSTANCE.get_all(**params)
    except Exception as e:
        logging.exception("Error in get_all_memories:")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/memories/{memory_id}", summary="Get a memory")
def get_memory(memory_id: str):
    """Retrieve a specific memory by ID."""
    try:
        return MEMORY_INSTANCE.get(memory_id)
    except Exception as e:
        logging.exception("Error in get_memory:")
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/search", summary="Search memories")
def search_memories(search_req: SearchRequest):
    """Search for memories based on a query."""
    try:
        params = {k: v for k, v in search_req.model_dump().items() if v is not None and k != "query"}
        return MEMORY_INSTANCE.search(query=search_req.query, **params)
    except Exception as e:
        logging.exception("Error in search_memories:")
        raise HTTPException(status_code=500, detail=str(e))


@app.put("/memories/{memory_id}", summary="Update a memory")
def update_memory(memory_id: str, updated_memory: Dict[str, Any]):
    """Update an existing memory with new content.
    
    Args:
        memory_id (str): ID of the memory to update
        updated_memory (str): New content to update the memory with
        
    Returns:
        dict: Success message indicating the memory was updated
    """
    try:
        return MEMORY_INSTANCE.update(memory_id=memory_id, data=updated_memory)
    except Exception as e:
        logging.exception("Error in update_memory:")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/memories/{memory_id}/history", summary="Get memory history")
def memory_history(memory_id: str):
    """Retrieve memory history."""
    try:
        return MEMORY_INSTANCE.history(memory_id=memory_id)
    except Exception as e:
        logging.exception("Error in memory_history:")
        raise HTTPException(status_code=500, detail=str(e))


@app.delete("/memories/{memory_id}", summary="Delete a memory")
def delete_memory(memory_id: str):
    """Delete a specific memory by ID."""
    try:
        MEMORY_INSTANCE.delete(memory_id=memory_id)
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
        return {"message": "All relevant memories deleted"}
    except Exception as e:
        logging.exception("Error in delete_all_memories:")
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/reset", summary="Reset all memories")
def reset_memory():
    """Completely reset stored memories."""
    try:
        MEMORY_INSTANCE.reset()
        return {"message": "All memories reset"}
    except Exception as e:
        logging.exception("Error in reset_memory:")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/", summary="Redirect to the OpenAPI documentation", include_in_schema=False)
def home():
    """Redirect to the OpenAPI documentation."""
    return RedirectResponse(url="/docs")


# ============================================
# UserProfile Routes
# ============================================

@app.post("/profile", summary="Create or update user profile")
def set_profile(profile_create: ProfileCreate):
    """
    Extract and update user profile from conversation messages.

    This endpoint analyzes conversation messages to extract user profile information
    including basic info (name, location, etc.) and additional profile (interests, skills, etc.).

    Args:
        profile_create: ProfileCreate object with messages and user_id

    Returns:
        dict: Result with update status and operations performed
    """
    # TODO: Add authentication/authorization
    # Verify user has permission to update this profile
    # Consider implementing JWT token validation or API key check

    try:
        # Log request details in DEBUG mode
        request_data = profile_create.model_dump()
        log_request_body(request_data, "set_profile")

        response = USER_PROFILE_INSTANCE.set_profile(
            user_id=profile_create.user_id,
            messages=[m.model_dump() for m in profile_create.messages]
        )

        # Log response details in DEBUG mode
        log_response_data(response, "set_profile")

        return JSONResponse(content=response)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logging.exception("Error in set_profile:")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/profile", summary="Get user profile")
def get_profile(
    user_id: str,
    fields: Optional[str] = None,
    evidence_limit: int = 5
):
    """
    Retrieve user profile data.

    Args:
        user_id: User ID (required)
        fields: Comma-separated list of fields to return from additional_profile
                e.g., "interests,skills" (optional, returns all if not specified)
        evidence_limit: Control evidence return behavior (default 5):
                       * 0: Remove all evidence (return empty arrays)
                       * Positive N: Return latest N evidence items
                       * -1: Return all evidence

    Returns:
        dict: User profile with basic_info and additional_profile
    """
    # TODO: Add authentication/authorization
    # Verify user has permission to access this profile
    # Consider implementing JWT token validation or API key check

    try:
        options = {"evidence_limit": evidence_limit}
        if fields:
            options["fields"] = [f.strip() for f in fields.split(",")]

        response = USER_PROFILE_INSTANCE.get_profile(
            user_id=user_id,
            options=options
        )
        return JSONResponse(content=response)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logging.exception("Error in get_profile:")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/profile/missing-fields", summary="Get missing profile fields")
def get_missing_fields(
    user_id: str,
    source: str = "both"
):
    """
    Get list of missing fields in user profile.

    Args:
        user_id: User ID (required)
        source: Which source to check - "pg" (PostgreSQL), "mongo" (MongoDB), or "both" (default)

    Returns:
        dict: Missing fields for the user
        {
            "user_id": "user123",
            "missing_fields": {
                "basic_info": ["hometown", "gender"],
                "additional_profile": ["personality"]
            }
        }
    """
    # TODO: Add authentication/authorization
    # Verify user has permission to access this profile
    # Consider implementing JWT token validation or API key check

    try:
        response = USER_PROFILE_INSTANCE.get_missing_fields(
            user_id=user_id,
            source=source
        )
        return JSONResponse(content=response)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logging.exception("Error in get_missing_fields:")
        raise HTTPException(status_code=500, detail=str(e))


@app.delete("/profile", summary="Delete user profile")
def delete_profile(user_id: str):
    """
    Delete user profile completely.

    Args:
        user_id: User ID (required)

    Returns:
        dict: Deletion result with success status
    """
    # TODO: Add authentication/authorization
    # Verify user has permission to delete this profile
    # Consider implementing JWT token validation or API key check

    try:
        response = USER_PROFILE_INSTANCE.delete_profile(user_id=user_id)
        return JSONResponse(content=response)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logging.exception("Error in delete_profile:")
        raise HTTPException(status_code=500, detail=str(e))


# Placeholder for vocabulary feature (archived for Phase 2)
@app.post("/vocab", summary="Vocabulary management (not implemented)")
def set_vocab():
    """Placeholder for vocabulary management feature (Phase 2)."""
    raise HTTPException(status_code=501, detail="Vocabulary feature is not implemented yet. See archived/vocab_design.md for future plans.")


@app.get("/vocab", summary="Get vocabulary (not implemented)")
def get_vocab():
    """Placeholder for vocabulary retrieval feature (Phase 2)."""
    raise HTTPException(status_code=501, detail="Vocabulary feature is not implemented yet. See archived/vocab_design.md for future plans.")
