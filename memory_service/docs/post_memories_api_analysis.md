# POST /memories API Detailed Analysis Document

## Overview

This document provides a detailed analysis of the complete workflow of the POST `/memories` API in the Mem0 project, including how natural language input is converted into structured memory entries, and the decision mechanism for adding, updating, and deleting memories.

## API Entry Point

### HTTP Endpoint
- **URL**: `POST http://localhost:18088/memories`
- **Implementation Location**: `server/main.py:97-109`
- **Handler Function**: `add_memory(memory_create: MemoryCreate)`

```python
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
        logging.exception("Error in add_memory:")
        raise HTTPException(status_code=500, detail=str(e))
```

### Request Format (`server/main.py:73-78`)
```python
class MemoryCreate(BaseModel):
    messages: List[Message] = Field(..., description="List of messages to store.")
    user_id: Optional[str] = None
    agent_id: Optional[str] = None
    run_id: Optional[str] = None
    metadata: Optional[Dict[str, Any]] = None
```

## Core Processing Workflow

### 1. Memory.add() Method Entry Point
**Location**: `mem0/memory/main.py:190-287`

```python
def add(
    self,
    messages,
    *,
    user_id: Optional[str] = None,
    agent_id: Optional[str] = None,
    run_id: Optional[str] = None,
    metadata: Optional[Dict[str, Any]] = None,
    infer: bool = True,
    memory_type: Optional[str] = None,
    prompt: Optional[str] = None,
):
```

#### 1.1 Metadata and Filter Construction
**Call**: `_build_filters_and_metadata()` (`mem0/memory/main.py:46-119`)

```python
processed_metadata, effective_filters = _build_filters_and_metadata(
    user_id=user_id,
    agent_id=agent_id,
    run_id=run_id,
    input_metadata=metadata,
)
```

**Function**: Constructs storage metadata templates and query filters, supporting multiple session identifiers (user_id, agent_id, run_id).

#### 1.2 Message Format Normalization
**Location**: `mem0/memory/main.py:244-251`

```python
if isinstance(messages, str):
    messages = [{"role": "user", "content": messages}]
elif isinstance(messages, dict):
    messages = [messages]
elif not isinstance(messages, list):
    raise ValueError("messages must be str, dict, or list[dict]")
```

#### 1.3 Vision Message Parsing
**Call**: `parse_vision_messages()` (`mem0/memory/utils.py:88-115`)

```python
if self.config.llm.config.get("enable_vision"):
    messages = parse_vision_messages(messages, self.llm, self.config.llm.config.get("vision_details"))
else:
    messages = parse_vision_messages(messages)
```

#### 1.4 Concurrent Processing
**Location**: `mem0/memory/main.py:262-286`

```python
with concurrent.futures.ThreadPoolExecutor() as executor:
    future1 = executor.submit(self._add_to_vector_store, messages, processed_metadata, effective_filters, infer)
    future2 = executor.submit(self._add_to_graph, messages, effective_filters)

    concurrent.futures.wait([future1, future2])

    vector_store_result = future1.result()
    graph_result = future2.result()
```

### 2. Vector Store Processing (_add_to_vector_store)

**Location**: `mem0/memory/main.py:289-460`

#### 2.1 Non-Inference Mode Processing
**Location**: `mem0/memory/main.py:290-324`

When `infer=False`, each message is stored as a raw memory without intelligent analysis.

```python
if not infer:
    returned_memories = []
    for message_dict in messages:
        # Validate message format
        if (not isinstance(message_dict, dict) or
            message_dict.get("role") is None or
            message_dict.get("content") is None):
            logger.warning(f"Skipping invalid message format: {message_dict}")
            continue

        # Skip system messages
        if message_dict["role"] == "system":
            continue

        # Build metadata for each message
        per_msg_meta = deepcopy(metadata)
        per_msg_meta["role"] = message_dict["role"]

        # Handle actor_id
        actor_name = message_dict.get("name")
        if actor_name:
            per_msg_meta["actor_id"] = actor_name

        # Generate embeddings and create memory
        msg_content = message_dict["content"]
        msg_embeddings = self.embedding_model.embed(msg_content, "add")
        mem_id = self._create_memory(msg_content, msg_embeddings, per_msg_meta)
```

#### 2.2 Intelligent Inference Mode Processing
**Location**: `mem0/memory/main.py:326-460`

##### 2.2.1 Message Parsing
**Call**: `parse_messages()` (`mem0/memory/utils.py:11-20`)

```python
parsed_messages = parse_messages(messages)
```

**Function**: Converts the message list into plain text format for easier LLM processing:
```python
def parse_messages(messages):
    response = ""
    for msg in messages:
        if msg["role"] == "system":
            response += f"system: {msg['content']}\n"
        if msg["role"] == "user":
            response += f"user: {msg['content']}\n"
        if msg["role"] == "assistant":
            response += f"assistant: {msg['content']}\n"
    return response
```

##### 2.2.2 Fact Extraction Phase

**Get Prompt**: `get_fact_retrieval_messages()` (`mem0/memory/utils.py:7-8`)

```python
if self.config.custom_fact_extraction_prompt:
    system_prompt = self.config.custom_fact_extraction_prompt
    user_prompt = f"Input:\n{parsed_messages}"
else:
    system_prompt, user_prompt = get_fact_retrieval_messages(parsed_messages)
```

**Fact Extraction Prompt**: `FACT_RETRIEVAL_PROMPT` (`mem0/configs/prompts.py:14-59`)

This prompt guides the LLM to extract key facts from the conversation, including:
- Personal preferences
- Important personal details
- Plans and intentions
- Activity and service preferences
- Health and fitness preferences
- Professional information
- Other miscellaneous information

**LLM Call**: (`mem0/memory/main.py:334-340`)
```python
response = self.llm.generate_response(
    messages=[
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": user_prompt},
    ],
    response_format={"type": "json_object"},
)
```

**Result Parsing**: (`mem0/memory/main.py:342-347`)
```python
try:
    response = remove_code_blocks(response)  # Remove code block markers
    new_retrieved_facts = json.loads(response)["facts"]
except Exception as e:
    logger.error(f"Error in new_retrieved_facts: {e}")
    new_retrieved_facts = []
```

**Example Output**:
```json
{"facts": ["Name is John", "Is a Software engineer", "Likes pizza"]}
```

##### 2.2.3 Similar Memory Retrieval Phase

**Location**: `mem0/memory/main.py:352-369`

Performs a similarity search for each extracted fact:

```python
retrieved_old_memory = []
new_message_embeddings = {}
for new_mem in new_retrieved_facts:
    # Generate embedding
    messages_embeddings = self.embedding_model.embed(new_mem, "add")
    new_message_embeddings[new_mem] = messages_embeddings

    # Search for similar items in existing memories
    existing_memories = self.vector_store.search(
        query=new_mem,
        vectors=messages_embeddings,
        limit=5,  # Returns up to 5 similar memories
        filters=filters,
    )

    # Collect similar memories
    for mem in existing_memories:
        retrieved_old_memory.append({"id": mem.id, "text": mem.payload["data"]})
```

**Deduplication**: (`mem0/memory/main.py:366-369`)
```python
unique_data = {}
for item in retrieved_old_memory:
    unique_data[item["id"]] = item
retrieved_old_memory = list(unique_data.values())
```

##### 2.2.4 UUID Mapping Mechanism

**Location**: `mem0/memory/main.py:372-376`

To avoid LLM hallucinations when dealing with UUIDs, temporary numeric IDs are used:

```python
temp_uuid_mapping = {}
for idx, item in enumerate(retrieved_old_memory):
    temp_uuid_mapping[str(idx)] = item["id"]  # Numeric ID -> UUID mapping
    retrieved_old_memory[idx]["id"] = str(idx)  # Replace with numeric ID
```

##### 2.2.5 Memory Decision Phase

**Get Decision Prompt**: `get_update_memory_messages()` (`mem0/configs/prompts.py:291-345`)

```python
if new_retrieved_facts:
    function_calling_prompt = get_update_memory_messages(
        retrieved_old_memory,
        new_retrieved_facts,
        self.config.custom_update_memory_prompt
    )
```

**Decision Prompt Structure**: `DEFAULT_UPDATE_MEMORY_PROMPT` (`mem0/configs/prompts.py:61-209`)

This detailed prompt defines four types of operations:

1. **ADD**: Add completely new information
2. **UPDATE**: Update existing memories with richer information
3. **DELETE**: Delete contradictory information
4. **NONE**: No change required

**LLM Decision Call**: (`mem0/memory/main.py:384-390`)
```python
try:
    response: str = self.llm.generate_response(
        messages=[{"role": "user", "content": function_calling_prompt}],
        response_format={"type": "json_object"},
    )
except Exception as e:
    logger.error(f"Error in new memory actions response: {e}")
    response = ""
```

**Decision Result Parsing**: (`mem0/memory/main.py:392-403`)
```python
try:
    if not response or not response.strip():
        logger.warning("Empty response from LLM, no memories to extract")
        new_memories_with_actions = {}
    else:
        response = remove_code_blocks(response)
        new_memories_with_actions = json.loads(response)
except Exception as e:
    logger.error(f"Invalid JSON response: {e}")
    new_memories_with_actions = {}
```

##### 2.2.6 Memory Operation Execution

**Location**: `mem0/memory/main.py:405-452`

Executes corresponding operations based on the LLM's decision results:

```python
returned_memories = []
try:
    for resp in new_memories_with_actions.get("memory", []):
        logger.info(resp)
        try:
            action_text = resp.get("text")
            if not action_text:
                logger.info("Skipping memory entry because of empty `text` field.")
                continue

            event_type = resp.get("event")
            if event_type == "ADD":
                memory_id = self._create_memory(
                    data=action_text,
                    existing_embeddings=new_message_embeddings,
                    metadata=deepcopy(metadata),
                )
                returned_memories.append({
                    "id": memory_id,
                    "memory": action_text,
                    "event": event_type
                })

            elif event_type == "UPDATE":
                self._update_memory(
                    memory_id=temp_uuid_mapping[resp.get("id")],  # Map back to real UUID
                    data=action_text,
                    existing_embeddings=new_message_embeddings,
                    metadata=deepcopy(metadata),
                )
                returned_memories.append({
                    "id": temp_uuid_mapping[resp.get("id")],
                    "memory": action_text,
                    "event": event_type,
                    "previous_memory": resp.get("old_memory"),
                })

            elif event_type == "DELETE":
                self._delete_memory(memory_id=temp_uuid_mapping[resp.get("id")])
                returned_memories.append({
                    "id": temp_uuid_mapping[resp.get("id")],
                    "memory": action_text,
                    "event": event_type,
                })

            elif event_type == "NONE":
                logger.info("NOOP for Memory.")
        except Exception as e:
            logger.error(f"Error processing memory action: {resp}, Error: {e}")
except Exception as e:
    logger.error(f"Error iterating new_memories_with_actions: {e}")
```

## Memory Operation Implementation

### 1. Create Memory (_create_memory)

**Location**: `mem0/memory/main.py:818-845`

```python
def _create_memory(self, data, existing_embeddings, metadata=None):
    logger.debug(f"Creating memory with {data=}")

    # Get or generate embedding
    if data in existing_embeddings:
        embeddings = existing_embeddings[data]
    else:
        embeddings = self.embedding_model.embed(data, memory_action="add")

    # Generate unique ID
    memory_id = str(uuid.uuid4())
    metadata = metadata or {}
    metadata["data"] = data
    metadata["hash"] = hashlib.md5(data.encode()).hexdigest()
    metadata["created_at"] = datetime.now(pytz.timezone("US/Pacific")).isoformat()

    # Insert into vector database
    self.vector_store.insert(
        vectors=[embeddings],
        ids=[memory_id],
        payloads=[metadata],
    )

    # Record history
    self.db.add_history(
        memory_id,
        None,  # Previous value is None
        data,  # New value
        "ADD",  # Operation type
        created_at=metadata.get("created_at"),
        actor_id=metadata.get("actor_id"),
        role=metadata.get("role"),
    )

    capture_event("mem0._create_memory", self, {"memory_id": memory_id, "sync_type": "sync"})
    return memory_id
```

### 2. Update Memory (_update_memory)

**Location**: `mem0/memory/main.py:885-937`

```python
def _update_memory(self, memory_id, data, existing_embeddings, metadata=None):
    logger.info(f"Updating memory with {data=}")

    try:
        existing_memory = self.vector_store.get(vector_id=memory_id)
    except Exception:
        logger.error(f"Error getting memory with ID {memory_id} during update.")
        raise ValueError(f"Error getting memory with ID {memory_id}. Please provide a valid 'memory_id'")

    prev_value = existing_memory.payload.get("data")

    # Build new metadata
    new_metadata = deepcopy(metadata) if metadata is not None else {}
    new_metadata["data"] = data
    new_metadata["hash"] = hashlib.md5(data.encode()).hexdigest()
    new_metadata["created_at"] = existing_memory.payload.get("created_at")
    new_metadata["updated_at"] = datetime.now(pytz.timezone("US/Pacific")).isoformat()

    # Preserve original session identifiers
    for key in ["user_id", "agent_id", "run_id", "actor_id", "role"]:
        if key in existing_memory.payload:
            new_metadata[key] = existing_memory.payload[key]

    # Get or generate new embedding
    if data in existing_embeddings:
        embeddings = existing_embeddings[data]
    else:
        embeddings = self.embedding_model.embed(data, "update")

    # Update vector database
    self.vector_store.update(
        vector_id=memory_id,
        vector=embeddings,
        payload=new_metadata,
    )

    # Record history
    self.db.add_history(
        memory_id,
        prev_value,  # Previous value
        data,        # New value
        "UPDATE",    # Operation type
        created_at=new_metadata["created_at"],
        updated_at=new_metadata["updated_at"],
        actor_id=new_metadata.get("actor_id"),
        role=new_metadata.get("role"),
    )

    capture_event("mem0._update_memory", self, {"memory_id": memory_id, "sync_type": "sync"})
    return memory_id
```

### 3. Delete Memory (_delete_memory)

**Location**: `mem0/memory/main.py:939-954`

```python
def _delete_memory(self, memory_id):
    logger.info(f"Deleting memory with {memory_id=}")

    # Get existing memory to save history record
    existing_memory = self.vector_store.get(vector_id=memory_id)
    prev_value = existing_memory.payload["data"]

    # Delete from vector database
    self.vector_store.delete(vector_id=memory_id)

    # Record deletion history
    self.db.add_history(
        memory_id,
        prev_value,  # Deleted value
        None,        # New value is None
        "DELETE",    # Operation type
        actor_id=existing_memory.payload.get("actor_id"),
        role=existing_memory.payload.get("role"),
        is_deleted=1,  # Marked as deleted
    )

    capture_event("mem0._delete_memory", self, {"memory_id": memory_id, "sync_type": "sync"})
    return memory_id
```

## Graph Database Processing (_add_to_graph)

**Location**: `mem0/memory/main.py:462-471`

```python
def _add_to_graph(self, messages, filters):
    added_entities = []
    if self.enable_graph:
        if filters.get("user_id") is None:
            filters["user_id"] = "user"  # Default user ID

        # Merge all non-system message content
        data = "\n".join([
            msg["content"] for msg in messages
            if "content" in msg and msg["role"] != "system"
        ])

        # Add to graph database
        added_entities = self.graph.add(data, filters)

    return added_entities
```

## Utility Functions Detail

### 1. remove_code_blocks

**Location**: `mem0/memory/utils.py:35-46`

```python
def remove_code_blocks(content: str) -> str:
    """
    Removes code block markers ```[language] and ``` from LLM responses.
    """
    pattern = r"^```[a-zA-Z0-9]*\n([\s\S]*?)\n```$"
    match = re.match(pattern, content.strip())
    return match.group(1).strip() if match else content.strip()
```

### 2. process_telemetry_filters

**Location**: `mem0/memory/utils.py:118-133`

```python
def process_telemetry_filters(filters):
    """Processes telemetry filters, hashing sensitive IDs."""
    if filters is None:
        return {}, {}

    encoded_ids = {}
    if "user_id" in filters:
        encoded_ids["user_id"] = hashlib.md5(filters["user_id"].encode()).hexdigest()
    if "agent_id" in filters:
        encoded_ids["agent_id"] = hashlib.md5(filters["agent_id"].encode()).hexdigest()
    if "run_id" in filters:
        encoded_ids["run_id"] = hashlib.md5(filters["run_id"].encode()).hexdigest()

    return list(filters.keys()), encoded_ids
```

## Decision Logic Examples

### ADD Operation Example
```json
// Input: Existing memory empty, New fact: ["Name is John"]
// Output:
{
    "memory": [
        {
            "id": "0",
            "text": "Name is John",
            "event": "ADD"
        }
    ]
}
```

### UPDATE Operation Example
```json
// Input: Existing memory: "User likes pizza", New fact: ["Loves cheese and pepperoni pizza"]
// Output:
{
    "memory": [
        {
            "id": "0",
            "text": "Loves cheese and pepperoni pizza",
            "event": "UPDATE",
            "old_memory": "User likes pizza"
        }
    ]
}
```

### DELETE Operation Example
```json
// Input: Existing memory: "Loves cheese pizza", New fact: ["Dislikes cheese pizza"]
// Output:
{
    "memory": [
        {
            "id": "0",
            "text": "Loves cheese pizza",
            "event": "DELETE"
        }
    ]
}
```

### NONE Operation Example
```json
// Input: Existing memory: "Name is John", New fact: ["Name is John"]
// Output:
{
    "memory": [
        {
            "id": "0",
            "text": "Name is John",
            "event": "NONE"
        }
    ]
}
```

## System Components

### Vector Store
- **Creation**: `VectorStoreFactory.create()` (`mem0/utils/factory.py`)
- **Support**: Qdrant, Chroma, Pinecone, Weaviate, Redis, PostgreSQL, etc.

### Embedding Model
- **Creation**: `EmbedderFactory.create()` (`mem0/utils/factory.py`)
- **Support**: OpenAI, Hugging Face, Sentence Transformers, etc.

### LLM
- **Creation**: `LlmFactory.create()` (`mem0/utils/factory.py`)
- **Support**: OpenAI, Anthropic, AWS Bedrock, Azure, Ollama, Groq, etc.

### History Recording
- **Storage**: SQLite database (`SQLiteManager`)
- **Location**: `mem0/memory/storage.py`

## Error Handling

1. **Fact Extraction Failure**: Returns an empty list, skipping memory updates.
2. **LLM Decision Failure**: Records error, returns an empty operation list.
3. **Vector Operation Failure**: Throws an exception, rolls back operations.
4. **JSON Parsing Failure**: Records error, skips the entry.

## Performance Optimization

1. **Concurrent Processing**: Vector store and graph database operations are executed in parallel.
2. **Embedding Cache**: Reuses generated embedding vectors.
3. **Batch Operations**: Supports batch processing of multiple messages.
4. **Index Optimization**: Automatic index optimization in vector databases.

## Summary

The POST `/memories` API implements intelligent memory management through the following steps:

1. **Input Normalization**: Unifies various input formats into a message list.
2. **Fact Extraction**: Uses LLM to extract structured facts from natural language.
3. **Similarity Search**: Finds related existing memories based on vector embeddings.
4. **Intelligent Decision**: Uses LLM to analyze and decide how to process each fact.
5. **Operation Execution**: Executes ADD/UPDATE/DELETE/NONE operations based on decision results.
6. **History Tracking**: Records all change history for auditing and rollback.

This design skillfully combines the efficiency of traditional vector retrieval with the semantic understanding of LLMs, achieving a truly intelligent incremental memory management system.