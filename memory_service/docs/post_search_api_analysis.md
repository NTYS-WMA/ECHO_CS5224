# POST /search API Detailed Analysis Document

## Overview

This document provides a detailed analysis of the complete workflow of the POST `/search` API in the Mem0 project, including how natural language queries are converted into vector searches, as well as the sorting, filtering, and return mechanisms for search results.

## API Entry Point

### HTTP Endpoint
- **URL**: `POST http://localhost:18088/search`
- **Implementation Location**: `server/main.py:141-149`
- **Handler Function**: `search_memories(search_req: SearchRequest)`

```python
@app.post("/search", summary="Search memories")
def search_memories(search_req: SearchRequest):
    """Search for memories based on a query."""
    try:
        params = {k: v for k, v in search_req.model_dump().items() if v is not None and k != "query"}
        return MEMORY_INSTANCE.search(query=search_req.query, **params)
    except Exception as e:
        logging.exception("Error in search_memories:")
        raise HTTPException(status_code=500, detail=str(e))
```

### Request Format (`server/main.py:81-86`)
```python
class SearchRequest(BaseModel):
    query: str = Field(..., description="Search query.")
    user_id: Optional[str] = None
    run_id: Optional[str] = None
    agent_id: Optional[str] = None
    filters: Optional[Dict[str, Any]] = None
```

#### Detailed Request Parameters
- **query** (Required): Natural language search query, e.g., "What food do I like?"
- **user_id** (Optional): User identifier, used for scoped search.
- **agent_id** (Optional): Agent identifier, used for scoped search.
- **run_id** (Optional): Run identifier, used for scoped search.
- **filters** (Optional): Additional custom filtering conditions.

### Request Example
```json
{
    "query": "Tell me about the user's dietary preferences",
    "user_id": "user123",
    "filters": {
        "actor_id": "assistant",
        "category": "food_preferences"
    },
    "limit": 50,
    "threshold": 0.7
}
```

## Core Processing Workflow

### 1. Memory.search() Method Entry Point
**Location**: `mem0/memory/main.py:623-697`

```python
def search(
    self,
    query: str,
    *,
    user_id: Optional[str] = None,
    agent_id: Optional[str] = None,
    run_id: Optional[str] = None,
    limit: int = 100,
    filters: Optional[Dict[str, Any]] = None,
    threshold: Optional[float] = None,
):
```

#### 1.1 Parameter Validation and Filter Construction
**Call**: `_build_filters_and_metadata()` (`mem0/memory/main.py:46-119`)

```python
_, effective_filters = _build_filters_and_metadata(
    user_id=user_id, agent_id=agent_id, run_id=run_id, input_filters=filters
)

if not any(key in effective_filters for key in ("user_id", "agent_id", "run_id")):
    raise ValueError("At least one of 'user_id', 'agent_id', or 'run_id' must be specified.")
```

**Function**:
- Constructs effective query filters by merging session identifiers and custom filters.
- Validates that at least one session identifier must be provided.
- Supports combined search with multiple session identifiers.

#### 1.2 Telemetry Data Processing
**Call**: `process_telemetry_filters()` (`mem0/memory/utils.py:118-133`)

```python
keys, encoded_ids = process_telemetry_filters(effective_filters)
capture_event(
    "mem0.search",
    self,
    {
        "limit": limit,
        "version": self.api_version,
        "keys": keys,
        "encoded_ids": encoded_ids,
        "sync_type": "sync",
        "threshold": threshold,
    },
)
```

**Function**: MD5 hashes sensitive identifiers for secure telemetry data collection.

#### 1.3 Concurrent Search Execution
**Location**: `mem0/memory/main.py:671-682`

```python
with concurrent.futures.ThreadPoolExecutor() as executor:
    future_memories = executor.submit(self._search_vector_store, query, effective_filters, limit, threshold)
    future_graph_entities = (
        executor.submit(self.graph.search, query, effective_filters, limit) if self.enable_graph else None
    )

    concurrent.futures.wait(
        [future_memories, future_graph_entities] if future_graph_entities else [future_memories]
    )

    original_memories = future_memories.result()
    graph_entities = future_graph_entities.result() if future_graph_entities else None
```

**Function**: Simultaneously executes vector search and graph search (if enabled) to improve search efficiency.

#### 1.4 Result Formatting
**Location**: `mem0/memory/main.py:684-697`

```python
if self.enable_graph:
    return {"results": original_memories, "relations": graph_entities}

if self.api_version == "v1.0":
    warnings.warn(
        "The current search API output format is deprecated. "
        "To use the latest format, set `api_version='v1.1'`. "
        "The current format will be removed in mem0ai 1.1.0 and later versions.",
        category=DeprecationWarning,
        stacklevel=2,
    )
    return {"results": original_memories}
else:
    return {"results": original_memories}
```

## Vector Search Core Implementation

### 1. _search_vector_store() Method
**Location**: `mem0/memory/main.py:699-735`

#### 1.1 Query Vectorization
**Location**: `mem0/memory/main.py:700-701`

```python
def _search_vector_store(self, query, filters, limit, threshold: Optional[float] = None):
    embeddings = self.embedding_model.embed(query, "search")
    memories = self.vector_store.search(query=query, vectors=embeddings, limit=limit, filters=filters)
```

**Process**:
1. **Embedding Generation**: Uses the configured embedding model (e.g., OpenAI text-embedding-3-small) to convert query text into a vector.
2. **Vector Search**: Executes a similarity search in the vector database.
3. **Similarity Calculation**: Uses algorithms like Cosine Similarity to calculate the similarity between the query vector and stored vectors.

#### 1.2 Metadata Field Definition
**Location**: `mem0/memory/main.py:703-711`

```python
promoted_payload_keys = [
    "user_id",
    "agent_id",
    "run_id",
    "actor_id",
    "role",
]

core_and_promoted_keys = {"data", "hash", "created_at", "updated_at", "id", *promoted_payload_keys}
```

**Function**: Defines metadata keys that need to be promoted to top-level fields for easier client access.

#### 1.3 Search Result Processing and Formatting
**Location**: `mem0/memory/main.py:713-735`

```python
original_memories = []
for mem in memories:
    # Create standardized memory item
    memory_item_dict = MemoryItem(
        id=mem.id,
        memory=mem.payload["data"],
        hash=mem.payload.get("hash"),
        created_at=mem.payload.get("created_at"),
        updated_at=mem.payload.get("updated_at"),
        score=mem.score,  # Similarity score
    ).model_dump()

    # Promote important metadata fields to top-level
    for key in promoted_payload_keys:
        if key in mem.payload:
            memory_item_dict[key] = mem.payload[key]

    # Handle extra metadata
    additional_metadata = {k: v for k, v in mem.payload.items() if k not in core_and_promoted_keys}
    if additional_metadata:
        memory_item_dict["metadata"] = additional_metadata

    # Threshold filtering
    if threshold is None or mem.score >= threshold:
        original_memories.append(memory_item_dict)

return original_memories
```

### 2. MemoryItem Data Model
**Location**: `mem0/configs/base.py:16-27`

```python
class MemoryItem(BaseModel):
    id: str = Field(..., description="The unique identifier for the text data")
    memory: str = Field(..., description="The memory deduced from the text data")
    hash: Optional[str] = Field(None, description="The hash of the memory")
    metadata: Optional[Dict[str, Any]] = Field(None, description="Additional metadata for the text data")
    score: Optional[float] = Field(None, description="The score associated with the text data")
    created_at: Optional[str] = Field(None, description="The timestamp when the memory was created")
    updated_at: Optional[str] = Field(None, description="The timestamp when the memory was updated")
```

## Asynchronous Search Implementation

### AsyncMemory.search() Method
**Location**: `mem0/memory/main.py:1485-1562`

#### Key Differences
1. **Asynchronous Vectorization**: Wraps synchronous embedding generation using `asyncio.to_thread()`.
2. **Asynchronous Task Management**: Manages concurrent tasks using `asyncio.create_task()` and `asyncio.gather()`.
3. **Intelligent Graph Search**: Automatically detects if the graph search method is asynchronous.

```python
async def _search_vector_store(self, query, filters, limit, threshold: Optional[float] = None):
    embeddings = await asyncio.to_thread(self.embedding_model.embed, query, "search")
    memories = await asyncio.to_thread(
        self.vector_store.search, query=query, vectors=embeddings, limit=limit, filters=filters
    )
    # ... Subsequent processing logic same as synchronous version
```

## Search Function Features

### 1. Multi-modal Search
- **Vector Search**: High-precision search based on semantic similarity.
- **Graph Search**: Structured search based on entity relationships (optional).
- **Hybrid Results**: Returns both vector matching and relationship matching results.

### 2. Flexible Filtering Mechanism

#### Session-level Filtering
```python
# Single session search
{"user_id": "user123"}

# Multi-session combined search
{"user_id": "user123", "agent_id": "assistant"}
```

#### Custom Filters
```python
{
    "actor_id": "user",        # Filter by message sender
    "role": "assistant",       # Filter by role
    "category": "preferences", # Filter by custom category
    "timestamp": "2024-01-01"  # Filter by time
}
```

### 3. Result Quality Control

#### Similarity Threshold
```python
threshold = 0.7  # Only return results with similarity >= 0.7
```

#### Result Quantity Limit
```python
limit = 50  # Return at most 50 results
```

#### Automatic Sorting
- Results are sorted in descending order of similarity score.
- Scores typically range from 0.0 to 1.0, where 1.0 represents a perfect match.

### 4. Metadata Richness

#### Core Fields
- **id**: Unique identifier
- **memory**: Memory content
- **score**: Similarity score
- **created_at/updated_at**: Timestamps

#### Contextual Fields
- **user_id/agent_id/run_id**: Session identifiers
- **actor_id**: Message sender
- **role**: Role information

#### Extended Metadata
- **hash**: Content hash value
- **metadata**: Custom metadata object

## Response Format

### Standard Response (API v1.1+)
```json
{
    "results": [
        {
            "id": "uuid-1234-5678-9012",
            "memory": "User likes pasta and pizza",
            "score": 0.92,
            "hash": "a1b2c3d4e5f6",
            "created_at": "2024-01-15T10:30:00-08:00",
            "updated_at": "2024-01-16T14:20:00-08:00",
            "user_id": "user123",
            "agent_id": "food_assistant",
            "actor_id": "user",
            "role": "user",
            "metadata": {
                "category": "food_preferences",
                "confidence": 0.95,
                "source": "conversation"
            }
        }
    ]
}
```

### Graph-enhanced Response (When Graph Store is Enabled)
```json
{
    "results": [
        {
            "id": "uuid-1234-5678-9012",
            "memory": "User likes pasta and pizza",
            "score": 0.92,
            // ... Other fields
        }
    ],
    "relations": [
        {
            "source": "User",
            "relationship": "likes",
            "destination": "pasta",
            "weight": 0.9
        },
        {
            "source": "User",
            "relationship": "likes",
            "destination": "pizza",
            "weight": 0.85
        }
    ]
}
```

## Search Algorithm Process

### 1. Query Preprocessing
1. **Input Validation**: Check required parameters and format.
2. **Filter Construction**: Merge session identifiers and custom filters.
3. **Permission Check**: Ensure users can only search memories within authorized scopes.

### 2. Vector Search Phase
1. **Query Vectorization**: Convert natural language query into a dense vector representation.
2. **Similarity Calculation**: Calculate similarity between query and stored memories in vector space.
3. **Initial Sorting**: Rank candidate results in descending order of similarity score.

### 3. Filtering and Re-ranking
1. **Session Filtering**: Limit search scope based on `user_id`/`agent_id`/`run_id`.
2. **Custom Filtering**: Apply additional metadata filtering conditions.
3. **Threshold Filtering**: Remove results below the specified similarity threshold.
4. **Quantity Limit**: Truncate top-K results.

### 4. Result Post-processing
1. **Metadata Promotion**: Promote important fields to top-level.
2. **Format Standardization**: Convert to unified `MemoryItem` format.
3. **Extra Information**: Add search context and debugging information.

## Performance Optimization Strategies

### 1. Concurrent Search
- **Parallel execution of vector search and graph search.**
- **Use `ThreadPoolExecutor` to avoid blocking.**
- **Async version supports higher concurrency.**

### 2. Caching Mechanism
- **Embedding Vector Cache**: Avoid redundant vector calculations for common queries.
- **Result Cache**: Cache search results for frequent queries.
- **Connection Pooling**: Reuse database connections.

### 3. Index Optimization
- **Vector Index**: Use efficient vector indexes like HNSW, IVF.
- **Metadata Index**: Establish B-tree indexes for filter fields.
- **Composite Index**: Optimize index combinations for common query patterns.

### 4. Query Optimization
- **Early Termination**: End search early when enough results are found.
- **Paginated Search**: Support paginated return for large result sets.
- **Pre-filtering**: Apply inexpensive metadata filters before vector search.

## Error Handling

### 1. Input Validation Errors
```python
# Missing session identifier
raise ValueError("At least one of 'user_id', 'agent_id', or 'run_id' must be specified.")

# Invalid query format
raise ValueError("Query must be a non-empty string.")
```

### 2. Search Execution Errors
```python
# Vectorization failure
logger.error(f"Failed to embed query: {query}")

# Vector database connection failure
logger.error(f"Vector store search failed: {e}")
```

### 3. Result Processing Errors
```python
# Result formatting failure
logger.warning(f"Failed to format memory item: {mem_id}")

# Invalid threshold value
logger.error(f"Invalid threshold value: {threshold}")
```

## Use Case Examples

### 1. Personalized Recommendations
```json
{
    "query": "Recommend some movies the user might like",
    "user_id": "user123",
    "filters": {"category": "entertainment"},
    "limit": 10,
    "threshold": 0.8
}
```

### 2. Dialogue Context Retrieval
```json
{
    "query": "Meeting arrangements mentioned by the user earlier",
    "user_id": "user123",
    "agent_id": "calendar_assistant",
    "filters": {"role": "user"},
    "limit": 5
}
```

### 3. Knowledge Base Search
```json
{
    "query": "Tips on Python programming",
    "agent_id": "coding_assistant",
    "filters": {"topic": "programming"},
    "limit": 20,
    "threshold": 0.7
}
```

## Summary

The POST `/search` API provides powerful and flexible memory search capabilities:

### Core Advantages
1. **Semantic Understanding**: Deep semantic search based on vector embeddings.
2. **Flexible Filtering**: Supports multi-dimensional, multi-level result filtering.
3. **High Performance**: Concurrent execution and intelligent index optimization.
4. **Extensible**: Supports extended features like graph search.

### Technical Features
1. **Vectorized Query**: Converts natural language into high-dimensional vector representations.
2. **Similarity Calculation**: Uses mathematical distance to measure semantic similarity.
3. **Multi-modal Search**: Combines results from vector search and graph search.
4. **Intelligent Sorting**: Automatically sorts by similarity and relevance.

This design allows users to query complex memory information using natural language, with the system understanding the query intent and returning the most relevant results, serving as the core implementation of memory retrieval in modern AI applications.