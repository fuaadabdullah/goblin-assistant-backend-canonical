from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel
from sqlalchemy.orm import Session
from sqlalchemy import func
import os
import httpx
import socket
import pathlib
import urllib.parse
from typing import Dict, Any, List, Optional
from datetime import datetime, timedelta

from database import get_db
from models.routing import ProviderMetric, RoutingProvider

router = APIRouter(prefix="/health", tags=["health"])


class HealthCheckResponse(BaseModel):
    status: str
    checks: Dict[str, Any]


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


@router.get("/all", response_model=HealthCheckResponse)
async def health_all():
    """Perform full health checks: database, vector DB, and providers"""
    checks: Dict[str, Any] = {}

    # DB check (Supabase / Postgres)
    db_url = os.getenv("DATABASE_URL") or os.getenv("SUPABASE_URL")
    if db_url:
        try:
            # Simple TCP connect test for DB host:port
            # Accept URL formats: postgres://user:pass@host:port/db
            host = None
            port = None
            if db_url.startswith("postgres") or db_url.startswith("postgresql"):
                # parse host and port
                import re

                m = re.search(r"@([\w\-\.]+)(?::(\d+))?", db_url)
                if m:
                    host = m.group(1)
                    port = int(m.group(2)) if m.group(2) else 5432
            else:
                # If SUPABASE_URL is given (https), try TCP connect to its host/443
                parsed = urllib.parse.urlparse(db_url)
                host = parsed.hostname
                port = parsed.port or (443 if parsed.scheme == "https" else 80)

            if host:
                s = socket.socket()
                s.settimeout(2)
                s.connect((host, port))
                s.close()
                checks["database"] = {"status": "healthy", "host": host, "port": port}
            else:
                checks["database"] = {
                    "status": "skipped",
                    "reason": "Could not parse database URL",
                }
        except Exception as e:
            checks["database"] = {"status": "unhealthy", "error": str(e)}
    else:
        checks["database"] = {
            "status": "skipped",
            "reason": "DATABASE_URL or SUPABASE_URL not set",
        }

    # Vector DB check (Chroma sqlite file or connection)
    try:
        chroma_path = os.getenv("CHROMA_DB_PATH")
        if not chroma_path:
            # default path in repo
            chroma_path = os.path.join(
                os.path.dirname(__file__), "..", "..", "chroma_db", "chroma.sqlite3"
            )
        chroma_file = pathlib.Path(chroma_path).resolve()
        if chroma_file.exists():
            checks["vector_db"] = {"status": "healthy", "path": str(chroma_file)}
        else:
            # If not file-backed, check hosted vector DBs (Qdrant/Chroma cloud)
            qdrant_url = os.getenv("QDRANT_URL") or os.getenv("CHROMA_API_URL")
            if qdrant_url:
                try:
                    parsed = urllib.parse.urlparse(qdrant_url)
                    host = parsed.hostname
                    port = parsed.port or (443 if parsed.scheme == "https" else 80)
                    # attempt a TCP connection
                    s = socket.socket()
                    s.settimeout(3)
                    s.connect((host, port))
                    s.close()
                    checks["vector_db"] = {
                        "status": "healthy",
                        "host": host,
                        "port": port,
                        "url": qdrant_url,
                    }
                except Exception as e:
                    checks["vector_db"] = {
                        "status": "unhealthy",
                        "url": qdrant_url,
                        "error": str(e),
                    }
            else:
                checks["vector_db"] = {
                    "status": "unhealthy",
                    "path": str(chroma_file),
                    "error": "file not found; set CHROMA_DB_PATH or QDRANT_URL",
                }
    except Exception as e:
        checks["vector_db"] = {"status": "unhealthy", "error": str(e)}

    # Providers check (basic connectivity)
    providers = []
    try:
        providers_config = [
            {
                "name": "Anthropic",
                "env_key": "ANTHROPIC_API_KEY",
                "base_url": os.getenv(
                    "ANTHROPIC_BASE_URL", "https://api.anthropic.com"
                ),
            },
            {
                "name": "OpenAI",
                "env_key": "OPENAI_API_KEY",
                "base_url": os.getenv("OPENAI_BASE_URL", "https://api.openai.com"),
            },
            {
                "name": "Groq",
                "env_key": "GROQ_API_KEY",
                "base_url": os.getenv("GROQ_BASE_URL", "https://api.groq.com"),
            },
            {
                "name": "DeepSeek",
                "env_key": "DEEPSEEK_API_KEY",
                "base_url": os.getenv("DEEPSEEK_BASE_URL", "https://api.deepseek.ai"),
            },
            {
                "name": "Gemini",
                "env_key": "GEMINI_API_KEY",
                "base_url": os.getenv(
                    "GEMINI_BASE_URL", "https://generative.googleapis.com"
                ),
            },
        ]

        async with httpx.AsyncClient(timeout=3) as client:
            for p in providers_config:
                # Allow explicit disabling per-provider via <PROVIDER>_ENABLED env var (false/0/no -> disabled)
                enabled_override = os.getenv(f"{p['name'].upper()}_ENABLED")
                if enabled_override is not None and enabled_override.lower() in (
                    "0",
                    "false",
                    "no",
                ):
                    result = {"enabled": False}
                    providers.append({p["name"]: result})
                    continue

                key = os.getenv(p["env_key"]) if p["env_key"] else None
                result = {"enabled": bool(key)}
                if key:
                    try:
                        # Try DNS resolution first
                        parsed = urllib.parse.urlparse(p["base_url"])
                        dns_host = parsed.hostname
                        try:
                            socket.getaddrinfo(dns_host, 0)
                        except Exception as de:
                            raise Exception(f"DNS lookup failed for {dns_host}: {de}")
                        # Try a lightweight request to the base_url
                        r = await client.get(p["base_url"], timeout=3)
                        result["status_code"] = r.status_code
                        result["status"] = (
                            "reachable" if r.status_code < 400 else "unreachable"
                        )
                    except Exception as e:
                        result["status"] = "unreachable"
                        result["error"] = str(e)
                providers.append({p["name"]: result})

        checks["providers"] = providers
    except Exception as e:
        checks["providers"] = {"status": "unhealthy", "error": str(e)}

    # App-level check
    overall = "healthy"
    for k, v in checks.items():
        if isinstance(v, dict) and v.get("status") == "unhealthy":
            overall = "degraded"
        if isinstance(v, list):
            for item in v:
                # item is like {"Anthropic": {...}}
                for _, s in item.items():
                    if s.get("status") == "unreachable":
                        overall = "degraded"

    return HealthCheckResponse(status=overall, checks=checks)


# ============================================================================
# NEW ENDPOINTS FOR ENHANCED DASHBOARD
# ============================================================================


@router.get("/chroma/status", response_model=ChromaStatusResponse)
async def get_chroma_status():
    """Get detailed Chroma vector database status"""
    try:
        chroma_path = os.getenv("CHROMA_DB_PATH")
        if not chroma_path:
            chroma_path = os.path.join(
                os.path.dirname(__file__), "..", "..", "chroma_db", "chroma.sqlite3"
            )

        chroma_file = pathlib.Path(chroma_path).resolve()

        if chroma_file.exists():
            # Try to import chromadb and get actual collection stats
            try:
                import chromadb

                client = chromadb.PersistentClient(path=str(chroma_file.parent))
                collections = client.list_collections()
                total_docs = sum(
                    [col.count() for col in collections if hasattr(col, "count")]
                )

                return ChromaStatusResponse(
                    status="healthy",
                    collections=len(collections),
                    documents=total_docs,
                    last_check=datetime.now().isoformat(),
                )
            except ImportError:
                # Fallback if chromadb not available - just check file exists
                return ChromaStatusResponse(
                    status="healthy",
                    collections=0,
                    documents=0,
                    last_check=datetime.now().isoformat(),
                )
        else:
            return ChromaStatusResponse(
                status="down",
                collections=0,
                documents=0,
                last_check=datetime.now().isoformat(),
            )
    except Exception as e:
        raise HTTPException(
            status_code=500, detail=f"Failed to get Chroma status: {str(e)}"
        )


@router.get("/mcp/status", response_model=MCPStatusResponse)
async def get_mcp_status():
    """Get MCP (Model Context Protocol) server status"""
    try:
        # Check for MCP server configuration
        # This is a placeholder - adjust based on your actual MCP setup
        mcp_servers = []
        active_connections = 0

        # Check for common MCP server environment variables
        if os.getenv("MCP_SERVER_URL"):
            mcp_servers.append("primary")
            active_connections += 1

        # Check if local MCP servers are running
        mcp_ports = [8765, 8766]  # Common MCP ports
        for port in mcp_ports:
            try:
                s = socket.socket()
                s.settimeout(1)
                s.connect(("localhost", port))
                s.close()
                mcp_servers.append(f"localhost:{port}")
                active_connections += 1
            except Exception:
                pass

        status = "healthy" if active_connections > 0 else "down"

        return MCPStatusResponse(
            status=status,
            servers=mcp_servers,
            active_connections=active_connections,
            last_check=datetime.now().isoformat(),
        )
    except Exception as e:
        raise HTTPException(
            status_code=500, detail=f"Failed to get MCP status: {str(e)}"
        )


@router.get("/raptor/status", response_model=RaptorStatusResponse)
async def get_raptor_status():
    """Get RAG indexer (Raptor) status"""
    try:
        import sys
        from pathlib import Path

        # Add GoblinOS to path for raptor import
        sys.path.insert(0, str(Path(__file__).parent.parent.parent.parent / "GoblinOS"))
        from raptor_mini import raptor

        running = bool(raptor.running) if hasattr(raptor, "running") else False
        config_file = getattr(raptor, "ini_path", "config/raptor.ini")

        status = "healthy" if running else "down"

        return RaptorStatusResponse(
            status=status,
            running=running,
            config_file=config_file,
            last_check=datetime.now().isoformat(),
        )
    except Exception:
        # If raptor can't be imported or checked, return down status
        return RaptorStatusResponse(
            status="down",
            running=False,
            config_file="unknown",
            last_check=datetime.now().isoformat(),
        )


@router.get("/sandbox/status", response_model=SandboxStatusResponse)
async def get_sandbox_status():
    """Get sandbox runner status"""
    try:
        # Check for active sandbox jobs
        active_jobs = 0
        queue_size = 0

        # Try Redis-backed task queue
        try:
            from task_queue import get_task_meta
            import redis

            REDIS_URL = os.getenv("REDIS_URL", "redis://localhost:6379/0")
            r = redis.from_url(REDIS_URL)
            keys = r.keys("task:*")

            # Count active jobs (exclude logs and artifacts keys)
            for key in keys:
                k = key.decode("utf-8")
                if ":logs" in k or ":artifacts" in k:
                    continue
                task_id = k.split(":", 1)[1]
                meta = get_task_meta(task_id)
                if meta.get("status") in ["running", "queued"]:
                    if meta.get("status") == "running":
                        active_jobs += 1
                    elif meta.get("status") == "queued":
                        queue_size += 1
        except Exception:
            # Fall back to in-memory TASKS
            try:
                from execute_router import TASKS

                for job_id, info in TASKS.items():
                    if info.get("status") == "running":
                        active_jobs += 1
                    elif info.get("status") == "queued":
                        queue_size += 1
            except Exception:
                pass

        status = "healthy" if active_jobs >= 0 else "down"

        return SandboxStatusResponse(
            status=status,
            active_jobs=active_jobs,
            queue_size=queue_size,
            last_check=datetime.now().isoformat(),
        )
    except Exception as e:
        raise HTTPException(
            status_code=500, detail=f"Failed to get sandbox status: {str(e)}"
        )


@router.get("/cost-tracking", response_model=CostTrackingResponse)
async def get_cost_tracking(db: Session = Depends(get_db)):
    """Get aggregated cost tracking across providers"""
    try:
        now = datetime.now()
        today_start = datetime(now.year, now.month, now.day)
        month_start = datetime(now.year, now.month, 1)

        # Query total costs from provider metrics
        total_cost_query = (
            db.query(func.sum(ProviderMetric.cost_incurred))
            .filter(ProviderMetric.cost_incurred.isnot(None))
            .scalar()
        )
        total_cost = float(total_cost_query or 0.0)

        # Today's costs
        cost_today_query = (
            db.query(func.sum(ProviderMetric.cost_incurred))
            .filter(
                ProviderMetric.cost_incurred.isnot(None),
                ProviderMetric.timestamp >= today_start,
            )
            .scalar()
        )
        cost_today = float(cost_today_query or 0.0)

        # This month's costs
        cost_month_query = (
            db.query(func.sum(ProviderMetric.cost_incurred))
            .filter(
                ProviderMetric.cost_incurred.isnot(None),
                ProviderMetric.timestamp >= month_start,
            )
            .scalar()
        )
        cost_this_month = float(cost_month_query or 0.0)

        # Cost by provider
        by_provider = {}
        providers = db.query(RoutingProvider).all()
        for provider in providers:
            provider_cost = (
                db.query(func.sum(ProviderMetric.cost_incurred))
                .filter(
                    ProviderMetric.provider_id == provider.id,
                    ProviderMetric.cost_incurred.isnot(None),
                )
                .scalar()
            )
            by_provider[provider.display_name] = float(provider_cost or 0.0)

        return CostTrackingResponse(
            total_cost=total_cost,
            cost_today=cost_today,
            cost_this_month=cost_this_month,
            by_provider=by_provider,
        )
    except Exception as e:
        raise HTTPException(
            status_code=500, detail=f"Failed to get cost tracking: {str(e)}"
        )


@router.get("/latency-history/{service}", response_model=LatencyHistoryResponse)
async def get_latency_history(
    service: str, hours: int = 24, db: Session = Depends(get_db)
):
    """Get latency history for a service over the specified hours"""
    try:
        cutoff_time = datetime.now() - timedelta(hours=hours)

        if service == "backend":
            # For backend, we can track API response times from provider metrics
            metrics = (
                db.query(ProviderMetric.timestamp, ProviderMetric.response_time_ms)
                .filter(
                    ProviderMetric.timestamp >= cutoff_time,
                    ProviderMetric.response_time_ms.isnot(None),
                )
                .order_by(ProviderMetric.timestamp)
                .limit(100)  # Limit to last 100 data points
                .all()
            )

            timestamps = [m[0].isoformat() for m in metrics]
            latencies = [float(m[1]) for m in metrics]

        elif service == "chroma":
            # Placeholder for chroma latency - could track query times
            timestamps = []
            latencies = []

        else:
            # For other services, return empty for now
            timestamps = []
            latencies = []

        return LatencyHistoryResponse(timestamps=timestamps, latencies=latencies)
    except Exception as e:
        raise HTTPException(
            status_code=500, detail=f"Failed to get latency history: {str(e)}"
        )


@router.get("/service-errors/{service}", response_model=List[ServiceError])
async def get_service_errors(service: str, limit: int = 10):
    """Get recent errors for a specific service"""
    try:
        errors = []

        # Check service-specific log files or error tracking
        # This is a placeholder implementation
        # You would integrate with your actual logging system

        if service == "backend":
            log_file = os.path.join(os.path.dirname(__file__), "logs", "app.log")
        elif service == "chroma":
            log_file = os.path.join(os.path.dirname(__file__), "logs", "chroma.log")
        elif service == "raptor":
            log_file = os.path.join(os.path.dirname(__file__), "logs", "raptor.log")
        else:
            log_file = None

        if log_file and os.path.exists(log_file):
            # Read last N lines that contain "error" or "ERROR"
            with open(log_file, "r") as f:
                lines = f.readlines()
                error_lines = [line for line in lines if "error" in line.lower()][
                    -limit:
                ]

                for line in error_lines:
                    # Parse timestamp and message (basic implementation)
                    errors.append(
                        ServiceError(
                            timestamp=datetime.now().isoformat(),
                            message=line.strip(),
                            service=service,
                        )
                    )

        return errors
    except Exception:
        # Return empty list on error rather than failing
        return []


@router.post("/retest/{service}", response_model=RetestServiceResponse)
async def retest_service(service: str, db: Session = Depends(get_db)):
    """Trigger a health retest for a specific service"""
    try:
        start_time = datetime.now()

        if service == "backend":
            # Test basic health endpoint
            try:
                async with httpx.AsyncClient() as client:
                    response = await client.get("http://localhost:8000/health")
                    success = response.status_code == 200
            except Exception:
                success = False

        elif service == "chroma":
            # Test Chroma database connection
            try:
                chroma_response = await get_chroma_status()
                success = chroma_response.status == "healthy"
            except Exception:
                success = False

        elif service == "mcp":
            # Test MCP servers
            try:
                mcp_response = await get_mcp_status()
                success = mcp_response.status == "healthy"
            except Exception:
                success = False

        elif service == "raptor":
            # Test Raptor status
            try:
                raptor_response = await get_raptor_status()
                success = raptor_response.status == "healthy"
            except Exception:
                success = False

        elif service == "sandbox":
            # Test Sandbox status
            try:
                sandbox_response = await get_sandbox_status()
                success = sandbox_response.status == "healthy"
            except Exception:
                success = False

        else:
            raise HTTPException(status_code=400, detail=f"Unknown service: {service}")

        end_time = datetime.now()
        latency = (end_time - start_time).total_seconds() * 1000  # Convert to ms

        message = f"{service.capitalize()} is {'healthy' if success else 'unhealthy'}"

        return RetestServiceResponse(success=success, latency=latency, message=message)
    except Exception as e:
        return RetestServiceResponse(
            success=False, latency=None, message=f"Retest failed: {str(e)}"
        )
