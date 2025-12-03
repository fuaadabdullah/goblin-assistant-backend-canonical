# Health & Provider Management API Implementation

**Date**: December 1, 2025
**Status**: ✅ Implementation Complete
**Files Modified**: 3 files
**New Endpoints**: 10 endpoints

## Overview

Implemented comprehensive health monitoring and provider management endpoints for the Enhanced Dashboard and Enhanced Providers Page in the frontend application.

## 📋 Implementation Summary

### Files Modified

1. **`health_router.py`** - Enhanced with 7 new health monitoring endpoints
2. **`settings_router.py`** - Enhanced with 3 new provider management endpoints
3. **`main.py`** - Added health_router to FastAPI application

## 🔌 New API Endpoints

### Health Monitoring Endpoints (7)

#### 1. GET `/health/chroma/status`
**Purpose**: Get detailed Chroma vector database status
**Response Model**: `ChromaStatusResponse`

```python
{
    "status": "healthy" | "down",
    "collections": int,
    "documents": int,
    "last_check": "2025-12-01T10:30:00"
}
```

**Implementation Details**:
- Checks for Chroma DB file existence or hosted instance
- Uses `chromadb.PersistentClient` to get actual collection stats
- Falls back to file existence check if chromadb not available

---

#### 2. GET `/health/mcp/status`
**Purpose**: Get MCP (Model Context Protocol) server status
**Response Model**: `MCPStatusResponse`

```python
{
    "status": "healthy" | "down",
    "servers": ["primary", "localhost:8765"],
    "active_connections": 2,
    "last_check": "2025-12-01T10:30:00"
}
```

**Implementation Details**:
- Checks `MCP_SERVER_URL` environment variable
- Probes common MCP ports (8765, 8766) via TCP socket
- Returns list of discovered servers

---

#### 3. GET `/health/raptor/status`
**Purpose**: Get RAG indexer (Raptor) status
**Response Model**: `RaptorStatusResponse`

```python
{
    "status": "healthy" | "down",
    "running": true,
    "config_file": "config/raptor.ini",
    "last_check": "2025-12-01T10:30:00"
}
```

**Implementation Details**:
- Imports `raptor_mini.raptor` from GoblinOS
- Checks `raptor.running` attribute
- Returns config file location

---

#### 4. GET `/health/sandbox/status`
**Purpose**: Get sandbox runner status
**Response Model**: `SandboxStatusResponse`

```python
{
    "status": "healthy" | "down",
    "active_jobs": 3,
    "queue_size": 5,
    "last_check": "2025-12-01T10:30:00"
}
```

**Implementation Details**:
- Attempts to use Redis-backed task queue via `task_queue` module
- Falls back to in-memory `TASKS` from `execute_router`
- Counts jobs with status "running" and "queued"

---

#### 5. GET `/health/cost-tracking`
**Purpose**: Get aggregated cost tracking across providers
**Response Model**: `CostTrackingResponse`

```python
{
    "total_cost": 45.67,
    "cost_today": 2.34,
    "cost_this_month": 12.89,
    "by_provider": {
        "OpenAI": 30.45,
        "Anthropic": 15.22
    }
}
```

**Implementation Details**:
- Queries `ProviderMetric.cost_incurred` from database
- Aggregates costs by time period (today, month, all-time)
- Groups costs by provider display name
- Uses `func.sum()` for efficient database aggregation

---

#### 6. GET `/health/latency-history/{service}`
**Query Parameters**: `hours` (default: 24)
**Purpose**: Get latency history for a service over specified hours
**Response Model**: `LatencyHistoryResponse`

```python
{
    "timestamps": ["2025-12-01T09:00:00", "2025-12-01T10:00:00"],
    "latencies": [125.4, 132.7]
}
```

**Supported Services**: `backend`, `chroma`

**Implementation Details**:
- Queries `ProviderMetric.response_time_ms` from database
- Filters by timestamp within specified hours
- Limits to last 100 data points for performance
- Orders by timestamp chronologically

---

#### 7. GET `/health/service-errors/{service}`
**Query Parameters**: `limit` (default: 10)
**Purpose**: Get recent errors for a specific service
**Response Model**: `List[ServiceError]`

```python
[
    {
        "timestamp": "2025-12-01T10:25:00",
        "message": "Connection timeout to database",
        "service": "backend"
    }
]
```

**Supported Services**: `backend`, `chroma`, `raptor`

**Implementation Details**:
- Reads service-specific log files (e.g., `logs/app.log`)
- Filters lines containing "error" or "ERROR"
- Returns last N error lines
- Returns empty list on file read failure (graceful degradation)

---

#### 8. POST `/health/retest/{service}`
**Purpose**: Trigger a health retest for a specific service
**Response Model**: `RetestServiceResponse`

```python
{
    "success": true,
    "latency": 45.2,
    "message": "Backend is healthy"
}
```

**Supported Services**: `backend`, `chroma`, `mcp`, `raptor`, `sandbox`

**Implementation Details**:
- Measures latency from start to completion
- For `backend`: Calls `/health` endpoint via httpx
- For others: Calls respective status functions
- Returns success/failure with latency metrics

---

### Provider Management Endpoints (3)

#### 9. POST `/settings/providers/{provider_id}/test-prompt`
**Purpose**: Test a provider with custom prompt and get full response
**Request Model**: `ProviderTestWithPromptRequest`

```python
{
    "prompt": "Write a hello world program in Python"
}
```

**Response Model**: `ProviderTestWithPromptResponse`

```python
{
    "success": true,
    "message": "Test successful",
    "latency": 234.5,
    "response": "Here's a simple hello world program:\n\nprint('Hello, World!')",
    "model_used": "gpt-4"
}
```

**Implementation Details**:
- Retrieves provider from database by ID
- Decrypts API key using `EncryptionService`
- Maps provider name to adapter class (OpenAI, Anthropic, etc.)
- Initializes adapter with decrypted API key
- Calls adapter's `complete()` method with custom prompt
- Measures and returns latency + full response
- Handles errors gracefully with failure message

**Supported Providers**:
- OpenAI
- Anthropic
- Grok (X.AI)
- DeepSeek
- Ollama
- LlamaCpp
- Silliconflow
- Moonshot

---

#### 10. POST `/settings/providers/reorder`
**Purpose**: Reorder providers by updating priorities
**Request Model**: `ReorderProvidersRequest`

```python
{
    "provider_ids": [3, 1, 5, 2, 4]
}
```

**Response**:

```python
{
    "success": true,
    "message": "Provider order updated successfully"
}
```

**Implementation Details**:
- Accepts array of provider IDs in desired order
- Updates `priority` field for each provider
- Higher index → lower priority (UX-friendly ordering)
- Commits all changes in single transaction
- Rolls back on error

**Priority Calculation**:
```python
priority = len(provider_ids) - index
# First item gets highest priority, last gets lowest
```

---

#### 11. POST `/settings/providers/{provider_id}/priority`
**Purpose**: Set priority for a specific provider
**Request Model**: `SetProviderPriorityRequest`

```python
{
    "priority": 50,
    "role": "primary"  // Optional: "primary" or "fallback"
}
```

**Response**:

```python
{
    "success": true,
    "message": "Priority set to 100 for OpenAI",
    "provider_id": 1,
    "priority": 100
}
```

**Implementation Details**:
- Updates provider priority in database
- Special handling for roles:
  - `"primary"` → priority = 100 (highest)
  - `"fallback"` → priority = 1 (lowest)
  - Custom value → uses provided priority
- Returns updated priority value

---

## 📦 Response Models (Pydantic)

### Health Monitoring Models

```python
class ChromaStatusResponse(BaseModel):
    status: str
    collections: int
    documents: int
    last_check: str

class MCPStatusResponse(BaseModel):
    status: str
    servers: List[str]
    active_connections: int
    last_check: str

class RaptorStatusResponse(BaseModel):
    status: str
    running: bool
    config_file: str
    last_check: str

class SandboxStatusResponse(BaseModel):
    status: str
    active_jobs: int
    queue_size: int
    last_check: str

class CostTrackingResponse(BaseModel):
    total_cost: float
    cost_today: float
    cost_this_month: float
    by_provider: Dict[str, float]

class LatencyHistoryResponse(BaseModel):
    timestamps: List[str]
    latencies: List[float]

class ServiceError(BaseModel):
    timestamp: str
    message: str
    service: str

class RetestServiceResponse(BaseModel):
    success: bool
    latency: Optional[float]
    message: str
```

### Provider Management Models

```python
class ProviderTestWithPromptRequest(BaseModel):
    prompt: str = "Write a hello world program in Python"

class ProviderTestWithPromptResponse(BaseModel):
    success: bool
    message: str
    latency: float
    response: Optional[str] = None
    model_used: Optional[str] = None

class ReorderProvidersRequest(BaseModel):
    provider_ids: List[int]

class SetProviderPriorityRequest(BaseModel):
    priority: int
    role: Optional[str] = None
```

---

## 🔧 Technical Details

### Database Models Used

- **`ProviderMetric`**: Stores cost and latency metrics
  - Fields: `cost_incurred`, `response_time_ms`, `timestamp`, `provider_id`
- **`RoutingProvider`**: Stores provider configuration
  - Fields: `id`, `name`, `display_name`, `api_key_encrypted`, `models`, `is_active`, `priority`

### Dependencies

```python
# FastAPI & Database
from fastapi import APIRouter, HTTPException, Depends
from sqlalchemy.orm import Session
from sqlalchemy import func

# Models
from models.routing import ProviderMetric, RoutingProvider

# Services
from services.encryption import EncryptionService

# Providers
from providers import (
    OpenAIAdapter, AnthropicAdapter, GrokAdapter,
    DeepSeekAdapter, OllamaAdapter, LlamaCppAdapter,
    SilliconflowAdapter, MoonshotAdapter
)
```

### Error Handling

All endpoints implement robust error handling:

1. **HTTPException** for client errors (400, 404)
2. **Graceful degradation** for optional services
3. **Database rollback** on transaction failures
4. **Empty responses** instead of errors for non-critical services

### Security Considerations

- API keys encrypted in database using `EncryptionService`
- Requires `ROUTING_ENCRYPTION_KEY` environment variable
- Provider test endpoints decrypt keys only when needed
- No sensitive data in error messages

---

## 🧪 Testing Instructions

### Health Monitoring Endpoints

```bash
# 1. Check Chroma status
curl http://localhost:8000/health/chroma/status

# 2. Check MCP status
curl http://localhost:8000/health/mcp/status

# 3. Check Raptor status
curl http://localhost:8000/health/raptor/status

# 4. Check Sandbox status
curl http://localhost:8000/health/sandbox/status

# 5. Get cost tracking
curl http://localhost:8000/health/cost-tracking

# 6. Get latency history (last 24 hours)
curl http://localhost:8000/health/latency-history/backend?hours=24

# 7. Get service errors
curl http://localhost:8000/health/service-errors/backend?limit=10

# 8. Retest a service
curl -X POST http://localhost:8000/health/retest/backend
```

### Provider Management Endpoints

```bash
# 9. Test provider with custom prompt
curl -X POST http://localhost:8000/settings/providers/1/test-prompt \
  -H "Content-Type: application/json" \
  -d '{"prompt": "Explain quantum computing in one sentence"}'

# 10. Reorder providers (drag-and-drop result)
curl -X POST http://localhost:8000/settings/providers/reorder \
  -H "Content-Type: application/json" \
  -d '{"provider_ids": [3, 1, 5, 2, 4]}'

# 11. Set provider as primary
curl -X POST http://localhost:8000/settings/providers/1/priority \
  -H "Content-Type: application/json" \
  -d '{"priority": 100, "role": "primary"}'

# Set provider as fallback
curl -X POST http://localhost:8000/settings/providers/2/priority \
  -H "Content-Type: application/json" \
  -d '{"priority": 1, "role": "fallback"}'
```

---

## 📊 Frontend Integration

### Client Axios Methods (Already Defined in Frontend)

The frontend's `client-axios.ts` already defines all these endpoints:

```typescript
// Health Monitoring
getChromaStatus(): Promise<ChromaStatusResponse>
getMCPStatus(): Promise<MCPStatusResponse>
getRaptorStatus(): Promise<RaptorStatusResponse>
getSandboxStatus(): Promise<SandboxStatusResponse>
getCostTracking(): Promise<CostTrackingResponse>
getLatencyHistory(service: string, hours?: number): Promise<LatencyHistoryResponse>
getServiceErrors(service: string, limit?: number): Promise<ServiceError[]>
retestService(service: string): Promise<RetestServiceResponse>

// Provider Management
testProviderWithPrompt(id: number, prompt: string): Promise<ProviderTestWithPromptResponse>
reorderProviders(providerIds: number[]): Promise<{ success: boolean }>
setProviderPriority(id: number, priority: number, role?: string): Promise<{ success: boolean }>
```

### Usage in Components

#### Enhanced Dashboard
```tsx
// Fetch all health data
const [chromaStatus, mcpStatus, raptorStatus, sandboxStatus, cost] =
  await Promise.all([
    apiClient.getChromaStatus(),
    apiClient.getMCPStatus(),
    apiClient.getRaptorStatus(),
    apiClient.getSandboxStatus(),
    apiClient.getCostTracking(),
  ]);

// Get latency history for sparklines
const latencyData = await apiClient.getLatencyHistory('backend', 24);

// Retest a service
const result = await apiClient.retestService('backend');
```

#### Enhanced Providers Page
```tsx
// Test provider with custom prompt
const result = await apiClient.testProviderWithPrompt(provider.id!, testPrompt);

// Reorder providers (after drag-and-drop)
await apiClient.reorderProviders(reorderedIds);

// Set as primary
await apiClient.setProviderPriority(provider.id!, 100, 'primary');
```

---

## ✅ Verification Checklist

- [x] All 10 endpoints implemented
- [x] Response models defined with Pydantic
- [x] Database queries optimized (uses aggregation)
- [x] Error handling implemented
- [x] Security considerations addressed (encryption)
- [x] Health router registered in main.py
- [x] Python syntax verified (py_compile passed)
- [x] Graceful degradation for optional services
- [x] Logging for debugging
- [x] Documentation complete

---

## 🚀 Deployment Notes

### Environment Variables Required

```bash
# Required for provider management
ROUTING_ENCRYPTION_KEY=<your-encryption-key>

# Optional service configurations
MCP_SERVER_URL=<mcp-server-url>
REDIS_URL=redis://localhost:6379/0
CHROMA_DB_PATH=/path/to/chroma.sqlite3
```

### Database Migrations

No new tables required. Uses existing:
- `provider_metrics` (for costs and latency)
- `routing_providers` (for provider management)

### Service Dependencies

Optional dependencies that enhance functionality:
- **Redis**: For persistent task queue tracking
- **Chroma DB**: For vector database metrics
- **GoblinOS Raptor**: For RAG indexer monitoring

---

## 🐛 Known Limitations

1. **Latency History**: Currently only tracks backend service via ProviderMetric
   - Future: Add dedicated latency tracking for Chroma and other services

2. **Service Errors**: Reads from log files (basic implementation)
   - Future: Integrate with structured logging system (e.g., Sentry, ELK)

3. **Provider Test**: Only tests first available model
   - Future: Allow model selection in request

4. **Cost Tracking**: Based on ProviderMetric.cost_incurred
   - Requires providers to log costs during API calls

---

## 📚 Related Documentation

- Frontend Implementation: `apps/goblin-assistant/src/components/EnhancedDashboard.tsx`
- Frontend API Client: `apps/goblin-assistant/src/api/client-axios.ts`
- Provider Adapters: `apps/goblin-assistant/backend/providers/`
- Routing Service: `apps/goblin-assistant/backend/services/routing.py`

---

## 🎉 Summary

**All 10 new API endpoints are fully implemented and ready for use!**

The backend now provides comprehensive health monitoring and provider management capabilities, enabling the Enhanced Dashboard and Enhanced Providers Page to display real-time metrics, cost tracking, latency trends, and advanced provider testing with custom prompts.

---

**Implementation completed by**: GitHub Copilot
**Review status**: Ready for code review
**Next steps**: Start backend server and test with frontend components
