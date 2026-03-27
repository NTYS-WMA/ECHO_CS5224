# Logging Guide

This document explains how to use and configure the logging system for the Mem0 service.

## Overview

The Mem0 service implements a layered logging system that supports different levels of verbosity. Logging is controlled via the `LOG_LEVEL` environment variable.

## Log Levels

### INFO (Default)
**Purpose**: Daily operations and monitoring.

**Output Content**:
- Basic HTTP request information (method, path, status code, duration)
- System initialization messages
- Errors and exceptions

**Example**:
```
2025-10-04 23:30:15,123 - main - INFO - Mem0 Memory and UserProfile instances initialized successfully
2025-10-04 23:30:15,124 - main - INFO - Logging level set to: INFO
2025-10-04 23:30:20,456 - main - INFO - → POST /profile
2025-10-04 23:30:22,789 - main - INFO - ← POST /profile - Status: 200 - Duration: 2.333s
```

### DEBUG
**Purpose**: Development debugging and problem diagnosis.

**Output Content** (includes everything in INFO plus):
- Request query parameters
- Request body data (summarized)
- Response data (summarized)
- LLM call details
- Database operation details
- Profile extraction/update process details

**Example**:
```
2025-10-04 23:30:20,456 - main - INFO - → POST /profile
2025-10-04 23:30:20,457 - main - DEBUG - Query params: {}
2025-10-04 23:30:20,458 - main - DEBUG - [set_profile] Request body: {user_id: test_001, messages: 3 items, first: 'My name is Zhang San, I am 25 years old...'}
2025-10-04 23:30:21,123 - mem0.user_profile.profile_manager - DEBUG - Stage 1: Extracting profile information from messages
2025-10-04 23:30:22,456 - mem0.user_profile.profile_manager - DEBUG - Stage 3: Deciding operations (ADD/UPDATE/DELETE)
2025-10-04 23:30:22,789 - main - DEBUG - [set_profile] Response: {success: True, operations: {'added': 2, 'updated': 0, 'deleted': 0}}
2025-10-04 23:30:22,790 - main - INFO - ← POST /profile - Status: 200 - Duration: 2.333s
```

## Configuration

### Method 1: Environment Variables (Recommended)

Set in your `.env` file:
```bash
LOG_LEVEL=DEBUG
```

Then start the service:
```bash
docker-compose up -d
```

### Method 2: Docker Compose CLI

Temporary DEBUG mode:
```bash
LOG_LEVEL=DEBUG docker-compose up
```

### Method 3: Docker Runtime

If running the Docker container directly:
```bash
docker run -e LOG_LEVEL=DEBUG mem0-service
```

## Viewing Logs

### Real-time logs
```bash
docker-compose logs -f mem0-service
```

### View last N lines
```bash
docker-compose logs --tail 100 mem0-service
```

### View logs by time
```bash
docker-compose logs --since 10m mem0-service  # Last 10 minutes
docker-compose logs --since "2025-10-04T23:00:00" mem0-service  # From specific time
```

### Filtering logs
```bash
# View only UserProfile related logs
docker-compose logs mem0-service | grep "mem0.user_profile"

# View only errors
docker-compose logs mem0-service | grep "ERROR"

# View logs for a specific endpoint
docker-compose logs mem0-service | grep "/profile"
```

## Log Structure

### Log Format
```
Timestamp - Module Name - Level - Message
```

### Module Naming
- `main`: FastAPI main application
- `middleware`: HTTP middleware
- `mem0.user_profile`: UserProfile module
- `mem0.user_profile.profile_manager`: Profile manager
- `mem0.user_profile.database.postgres_manager`: PostgreSQL manager
- `mem0.user_profile.database.mongodb_manager`: MongoDB manager

## Use Cases

### Scenario 1: Daily Operations
**Config**: `LOG_LEVEL=INFO`

**Usage**:
- Monitor request volume and response times
- Detect anomalies and errors
- Track slow requests

### Scenario 2: Performance Tuning
**Config**: `LOG_LEVEL=INFO`

**Usage**:
- Analyze request latency
- Identify performance bottlenecks
- Monitor LLM call frequency

**Analysis**:
```bash
# Find slow requests (duration > 5s)
docker-compose logs mem0-service | grep "Duration:" | awk '{print $NF}' | grep -E "[5-9]\.[0-9]+s|[0-9]{2}\.[0-9]+s"
```

### Scenario 3: Feature Debugging
**Config**: `LOG_LEVEL=DEBUG`

**Usage**:
- Debug new features
- Analyze LLM extraction results
- Troubleshoot data inconsistency issues

**Workflow**:
1. Set `LOG_LEVEL=DEBUG`
2. Restart service: `docker-compose restart mem0-service`
3. Send test requests
4. Check detailed logs
5. Locate the issue
6. Revert to `LOG_LEVEL=INFO` after fix

### Scenario 4: Problem Diagnosis
**Config**: `LOG_LEVEL=DEBUG`

**Usage**:
- Troubleshooting bugs
- Understanding data flow
- Analyzing LLM decision process

**Example**:
```bash
# Trace all operations for a specific user_id
docker-compose logs mem0-service | grep "test_user_001"

# View complete flow for a specific request
docker-compose logs --since "2025-10-04T23:30:00" mem0-service | grep -A 20 "POST /profile"
```

## Data Protection

### Sensitive Information Handling
Middleware automatically handles sensitive information:
- ✅ Request body truncation (max 200 characters)
- ✅ `messages` array shows count, not full content
- ✅ API keys do not appear in logs
- ✅ Raw user content shows only summaries

### DEBUG Mode Warnings
⚠️ **DEBUG mode records significant data, use with caution in production!**

Production recommendations:
- Use INFO level by default
- Enable DEBUG only temporarily for troubleshooting
- Disable DEBUG immediately after use
- Regularly clean up old logs

## Log Rotation

Docker logs rotate automatically as configured in `docker-compose.yaml`:

```yaml
logging:
  driver: "json-file"
  options:
    max-size: "10m"
    max-file: "3"
```

This means:
- Individual log files are capped at 10MB
- Maximum of 3 files are kept
- Total log size is approximately 30MB

## Performance Impact

### INFO Level
- ✅ Minimal impact (< 1%)
- ✅ Suitable for production
- ✅ Can be enabled indefinitely

### DEBUG Level
- ⚠️ Performance impact ~5-10%
- ⚠️ Log volume increases 10-20x
- ⚠️ Only for debugging, not recommended for long-term production use

## Custom Logging

To add custom logs in code, use the Python `logging` module:

```python
import logging

logger = logging.getLogger(__name__)

# Always visible (ERROR, WARNING, INFO)
logger.info("User profile updated successfully")
logger.warning("Evidence count exceeds limit")
logger.error("Failed to connect to database")

# Only visible in DEBUG mode
logger.debug("Extracted data: %s", extracted_data)
logger.debug("LLM response: %s", response)
```

## Troubleshooting

### Problem: No logs visible
**Solution**:
```bash
# 1. Check if container is running
docker ps | grep mem0

# 2. Check log driver
docker inspect mem0-api | grep LogPath

# 3. View container stdout directly
docker logs mem0-api
```

### Problem: DEBUG mode not working
**Solution**:
```bash
# 1. Verify environment variable
docker exec mem0-api env | grep LOG_LEVEL

# 2. Restart container to apply config
docker-compose restart mem0-service

# 3. Check startup logs for confirmation
docker-compose logs mem0-service | grep "Logging level"
```

### Problem: Too many logs
**Solution**:
```bash
# 1. Lower log level
LOG_LEVEL=INFO docker-compose up -d

# 2. Clear old logs
docker-compose logs --tail 0 mem0-service

# 3. Reduce log rotation limits
# Edit docker-compose.yaml and decrease max-size
```

## Best Practices

### Development Environment
```bash
LOG_LEVEL=DEBUG
```
- Easy debugging
- Understand data flow
- Fast issue localization

### Testing Environment
```bash
LOG_LEVEL=INFO
```
- Monitor test execution
- Record key operations
- Balance performance and info

### Production Environment
```bash
LOG_LEVEL=INFO
```
- Minimum performance impact
- Sufficient operational info
- Temporarily enable DEBUG for issues

## Summary

| Feature | INFO | DEBUG |
|------|------|-------|
| HTTP Request Logs | ✅ | ✅ |
| Request Parameters | ❌ | ✅ |
| Request Body | ❌ | ✅ (Summary) |
| Response Data | ❌ | ✅ (Summary) |
| LLM Call Details | ❌ | ✅ |
| Database Operations | ❌ | ✅ |
| Profile Extraction Process | ❌ | ✅ |
| Performance Impact | < 1% | 5-10% |
| Production Environment | ✅ Recommended | ⚠️ Temporary Only |

**Recommended Configuration**: Default to `LOG_LEVEL=INFO`, temporarily switch to `DEBUG` when issues occur.
