<!-- Canonical copy for backend docs (moved from apps/goblin-assistant/ENDPOINT_AUDIT.md) -->
<!-- Please edit content only in apps/goblin-assistant/backend/docs/ENDPOINT_AUDIT.md -->

# Endpoint Audit & Production Readiness - December 2, 2025

## Executive Summary

**Status**: ✅ Production Ready (with notes)

All critical endpoint mismatches have been fixed. Backend routes verified and frontend API client updated for consistency. Health, auth, chat, settings, routing, sandbox, and orchestration endpoints validated.

---

## Critical Fixes Applied

### 1. ✅ Settings Endpoints (BREAKING CHANGES)

**Issue**: Frontend expected full CRUD for providers/models/credentials but backend only has update endpoints.

**Backend Reality** (`/settings`):

- `GET /` - Get all settings
- `PUT /providers/{provider_name}` - Update provider by name (not ID)
- `PUT /models/{model_name}` - Update model by name
- `POST /test-connection?provider_name=X` - Test connection (query param)
- `POST /providers/{provider_id}/test-prompt` - Test with custom prompt
- `POST /providers/reorder` - Reorder providers (body: `provider_ids`)
- `POST /providers/{provider_id}/priority` - Set priority (body: `priority`, `role`)

**Frontend Changes**:

- ✅ Removed non-existent CRUD endpoints (create/delete providers/credentials/models)
- ✅ Fixed `updateProvider` to use provider name, not ID
- ✅ Fixed `testConnection` to use query param `provider_name`
- ✅ Fixed `reorderProviders` body: `provider_ids` (was `order`)
- ✅ Fixed `setProviderPriority` method: POST (was PATCH)

### 2. Search Endpoints

**Issue**: Frontend used non-existent `/search/documents` and `/search/search`.

**Backend Reality** (`/search`):

- `POST /query` - Search documents
- `GET /collections` - List collections
- `GET /collections/{collection_name}/documents` - Get documents
- `POST /collections/{collection_name}/add` - Add document

**Frontend Changes**:

- ✅ Replaced `searchDocuments` with `searchQuery` → `/search/query`
- ✅ Added `getCollectionDocuments` → `/collections/{name}/documents`
- ✅ Added `addDocument` → `/collections/{name}/add`
- ✅ Removed `createCollection`, `indexDocument`

### 3. API Keys Endpoints

**Issue**: Frontend used ID-based CRUD but backend uses provider-based access.

**Backend Reality** (`/api-keys`):

- `GET /{provider}` - Get API key for provider
- `POST /{provider}` - Set API key for provider
- `DELETE /{provider}` - Delete API key for provider

**Frontend Changes**:

- ✅ Changed to provider-based methods
- ✅ Removed `getApiKeys`, `createApiKey(name, provider)`
- ✅ Added `getApiKey(provider)`, `setApiKey(provider, apiKey, keyType)`, `deleteApiKey(provider)`

### 4. Orchestration/Execute Endpoints

**Issue**: Frontend called `/api/orchestrate/*` but backend is at `/execute/*`.

**Backend Reality** (`/execute`):

- `POST /` - Create orchestration plan
- `POST /orchestrate/parse` - Parse orchestration text
- `POST /orchestrate/execute?plan_id=X` - Execute plan
- `GET /orchestrate/plans/{plan_id}` - Get plan
- `GET /status/{task_id}` - Get execution status

**Frontend Changes**:

- ✅ Fixed paths: `/api/orchestrate/*` → `/execute/*` or `/execute/orchestrate/*`
- ✅ Added `createOrchestrationPlan` → `POST /execute/`
- ✅ Added `getExecutionStatus` → `GET /execute/status/{task_id}`

### 5. RAPTOR Status Endpoint

**Issue**: Duplicate `getRaptorStatus` method (once for enhanced health, once for RAPTOR router).

**Frontend Changes**:

- ✅ Removed duplicate from RAPTOR section (kept health section version)

### 6. Health Endpoints

**Already Fixed Previously**:

- ✅ `/health/chroma/status` (not `/health/chroma`)
- ✅ `/health/sandbox/status` (not `/health/sandbox`)
- ✅ `/health/mcp/status` (not `/health/mcp`)
- ✅ `/health/raptor/status` (not `/health/raptor`)
- ✅ `/health/cost-tracking` (not `/cost/summary`)
- ✅ `/health/latency-history/{service}` (not `/health/latency`)
- ✅ `/health/service-errors/{service}` (not `/health/errors`)
- ✅ `POST /health/retest/{service}` (not `POST /health/retest` with body)

---

## Backend Router Inventory

### Core Routers

1. **`/auth`** - Authentication (register, login, Google OAuth, Passkey WebAuthn)
2. **`/health`** - Health monitoring (all, chroma, mcp, raptor, sandbox, cost, latency, errors, retest)
3. **`/chat`** - Chat completions (with intelligent routing)
4. **`/routing`** - Provider routing (providers, capabilities, route request, health)
5. **`/settings`** - Settings management (providers, models, test connection)
6. **`/execute`** - Task execution & orchestration (create plan, parse, execute, status)
7. **`/sandbox`** - Sandbox jobs (jobs, logs, artifacts)
8. **`/raptor`** - RAG indexer (start, stop, status, logs)
9. **`/search`** - Vector search (query, collections, documents, add)
10. **`/api`** - Task routing & goblins (route_task, goblins, history, stats, streaming)
11. **`/stream`** - Server-sent events streaming
12. **`/api-keys`** - API key management (get, set, delete by provider)
13. **`/parse`** - Code parsing
14. **`/ws`** - WebSocket support
15. **`debugger`** - Debug suggestions

### Root Endpoints

- `GET /` - API info
- `GET /health` - Simple health check

---

## Production Readiness Checklist

### ✅ Security

-- **CORS**: Currently `allow_origins=["*"]` — **ACTION REQUIRED**: Restrict to production domains

```python
    # In main.py
    allow_origins=[
        "https://goblin-assistant.example.com",
        "https://www.goblin-assistant.example.com",
    ]
    ```

- **Auth**: Bearer token interceptor configured in frontend ✅
- **API Keys**: Encrypted with `ROUTING_ENCRYPTION_KEY` and `SETTINGS_ENCRYPTION_KEY` ✅
- **Secrets**: Using `.env` files (gitignored) ✅

### ✅ Error Handling

- Frontend: `handleError` method with network error detection ✅
- Backend: HTTPException with proper status codes ✅
- Auth: 401 auto-clears auth store ✅

### ✅ Timeouts

- Frontend: 30s timeout configured ✅
- Backend: FastAPI default (depends on uvicorn/gunicorn config)
- **ACTION REQUIRED**: Set backend timeout for production (recommend 60s for LLM calls)

### ⚠️ Rate Limiting

-- **ACTION REQUIRED**: Add rate limiting middleware for production

```python
    from slowapi import Limiter, _rate_limit_exceeded_handler
    from slowapi.util import get_remote_address

    limiter = Limiter(key_func=get_remote_address)
    app.state.limiter = limiter
    app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)
    ```


### ✅ Logging

- Console logging active (stdout/stderr) ✅
-- **ACTION REQUIRED**: Add structured logging for production (JSON logs)

```python
    import structlog
    structlog.configure(...)
    ```


### ⚠️ Health Checks

- Basic health: `GET /health` ✅
- Comprehensive: `GET /health/all` ✅
- **ACTION REQUIRED**: Set up Datadog/monitoring for production alerts

### ✅ API Documentation

- FastAPI auto-generates docs at `/docs` (Swagger UI) ✅
- Backend title: "GoblinOS Assistant Backend" ✅
