# PalServer Integration Tests Guide

## 📖 Overview

The `test_palserver_integration.py` file supports **both mock and real service testing** through environment variables.

## 🎛️ Configuration Variables

Control which services to use via environment variables:

| Variable | Values | Default | Description |
|----------|--------|---------|-------------|
| `USE_REAL_PALSERVER` | `0` / `1` | `0` | Use real PalServer instead of mocks |
| `USE_REAL_POSTGRES` | `0` / `1` | `0` | Use real PostgreSQL instead of mocks |
| `USE_REAL_MONGODB` | `0` / `1` | `0` | Use real MongoDB instead of mocks |
| `PALSERVER_BASE_URL` | URL | `http://localhost:8099/pal` | PalServer URL (when `USE_REAL_PALSERVER=1`) |
| `PALSERVER_TEST_CHILD_ID` | string | `12345` | Child ID for real PalServer tests |

## 🚀 Usage Examples

### 1. Default: All Mocks (Fast, No Dependencies)

```bash
# Run all tests with mocks - recommended for CI/CD
python -m pytest test/test_palserver_integration.py -v

# Output: 12 passed, 2 skipped (< 2 seconds)
```

**What runs:**
- ✅ 6 PalServer client mock tests
- ✅ 4 Data conversion tests
- ✅ 2 Cold start integration mock tests
- ⏭️ Skips real service tests

---

### 2. Test Real PalServer Only

```bash
# Test connection to real PalServer
USE_REAL_PALSERVER=1 python -m pytest test/test_palserver_integration.py -v

# With custom URL and child ID
USE_REAL_PALSERVER=1 \
PALSERVER_BASE_URL=http://172.18.168.242:8099/pal \
PALSERVER_TEST_CHILD_ID=12345 \
python -m pytest test/test_palserver_integration.py -v
```

**What runs:**
- ✅ 4 Data conversion tests (still use mocked DB for conversion logic)
- ✅ 1 Real PalServer connection test
- ⏭️ Skips PalServer client mock tests (6)
- ⏭️ Skips cold start integration mock tests (2)

**Output example:**
```
======================================================================
Test Configuration:
  USE_REAL_PALSERVER: True (URL: http://localhost:8099/pal)
  USE_REAL_POSTGRES:  False
  USE_REAL_MONGODB:   False
======================================================================

test/test_palserver_integration.py::TestRealPalServer::test_real_palserver_connection
✓ PalServer returned data for child_id=12345
  Fields: ['id', 'childName', 'age', 'gender', 'personalityTraits', 'hobbies']
  - id: 12345
  - childName: 小明
  - gender: 1
  - personalityTraits: 开朗,善良,勇敢
  - hobbies: 篮球,音乐,阅读
PASSED
```

---

### 3. Test Real Databases Only

```bash
# Test with real PostgreSQL and MongoDB
USE_REAL_POSTGRES=1 USE_REAL_MONGODB=1 python -m pytest test/test_palserver_integration.py -v
```

**What runs:**
- ✅ 6 PalServer client mock tests
- ✅ 4 Data conversion tests (now using real DBs)
- ✅ 1 Real database integration test
- ⏭️ Skips cold start integration mock tests (2)

**Requirements:**
- PostgreSQL running with proper config (see `.env.example`)
- MongoDB running with proper config

---

### 4. Full Integration Test (All Real Services)

```bash
# Test complete end-to-end flow with all real services
USE_REAL_PALSERVER=1 \
USE_REAL_POSTGRES=1 \
USE_REAL_MONGODB=1 \
python -m pytest test/test_palserver_integration.py -v
```

**What runs:**
- ✅ 4 Data conversion tests (using real DBs)
- ✅ 1 Real PalServer connection test
- ✅ 1 Real database cold start test
- ⏭️ Skips all mock tests (8)

**Requirements:**
- PalServer running and accessible
- PostgreSQL running and accessible
- MongoDB running and accessible

**Output example:**
```
test/test_palserver_integration.py::TestRealDatabaseIntegration::test_real_database_cold_start
✓ Created test user: test_cold_start_20251021_102345
  basic_info: {}
  additional_profile keys: []
✓ Cleaned up test user: test_cold_start_20251021_102345
PASSED
```

---

## 📊 Test Breakdown

### Mock Tests (Run by default)

| Test Class | Tests | What it tests |
|------------|-------|---------------|
| `TestPalServerClient` | 6 | HTTP client behavior (success, timeout, errors) |
| `TestDataConversion` | 4 | Data format conversion (gender, empty fields, whitespace) |
| `TestColdStartIntegration` | 2 | End-to-end mock flow (user not exists, disabled) |

### Real Service Tests (Run when enabled)

| Test Class | Tests | Requires | What it tests |
|------------|-------|----------|---------------|
| `TestRealPalServer` | 1 | `USE_REAL_PALSERVER=1` | PalServer connectivity |
| `TestRealDatabaseIntegration` | 1 | `USE_REAL_POSTGRES=1` + `USE_REAL_MONGODB=1` | Full cold start flow |

---

## 🔍 Troubleshooting

### All tests skip with "not enabled"

**Problem:**
```
test_real_palserver_connection SKIPPED (USE_REAL_PALSERVER not enabled)
test_real_database_cold_start SKIPPED (USE_REAL_POSTGRES and USE_REAL_MONGODB not both enabled)
```

**Solution:** Set environment variables to `1`:
```bash
USE_REAL_PALSERVER=1 python -m pytest test/test_palserver_integration.py -v
```

---

### Connection timeout errors with real PalServer

**Problem:**
```
WARNING: PalServer request timeout (1s) for child_id=12345
```

**Solutions:**
1. Verify PalServer is running: `curl http://localhost:8099/pal/child/12345/summary`
2. Check URL is correct: `echo $PALSERVER_BASE_URL`
3. Check child_id exists in PalServer database

---

### Database connection errors

**Problem:**
```
pymongo.errors.ServerSelectionTimeoutError: localhost:27017: [Errno 61] Connection refused
```

**Solutions:**
1. Ensure services are running: `docker-compose up -d postgres mongodb`
2. Check `.env` configuration matches docker-compose settings
3. Verify connection: `docker exec -it mem0-postgres psql -U postgres -d postgres -c "SELECT 1"`

---

## 🎯 Recommended Workflow

### Development (Fast Iteration)
```bash
# Quick validation with mocks
python -m pytest test/test_palserver_integration.py -v
```

### Pre-Deployment (Verify Integration)
```bash
# Start services
docker-compose up -d

# Test real PalServer connection
USE_REAL_PALSERVER=1 python -m pytest test/test_palserver_integration.py::TestRealPalServer -v

# Test real databases
USE_REAL_POSTGRES=1 USE_REAL_MONGODB=1 python -m pytest test/test_palserver_integration.py::TestRealDatabaseIntegration -v
```

### CI/CD Pipeline
```yaml
# .github/workflows/test.yml
- name: Run unit tests (mocked)
  run: python -m pytest test/test_palserver_integration.py -v
  # Fast, no external dependencies
```

---

## 📝 Notes

- **Mock tests are always safe to run** - no external dependencies
- **Real service tests require running infrastructure** - may fail if services are down
- **Data conversion tests** use mocks by default but can use real DBs if configured
- **Real database tests auto-cleanup** - test users are deleted after each run
- **1-second timeout** is enforced for PalServer requests (cluster internal network)

---

## 🔗 Related Documentation

- **Implementation Plan**: `discuss/40-cold_start_implementation.md`
- **API Documentation**: `DEV_GUIDE_UserProfile.md` section 6.5
- **Docker Setup**: `docker-compose.yaml` and `docker-compose.production.yaml`
