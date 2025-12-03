"""
Routing router with real provider discovery, health monitoring, and intelligent task routing.
"""

from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel
from typing import List, Optional, Dict, Any
from sqlalchemy.orm import Session

from database import get_db
from services.routing import RoutingService
from tasks.provider_probe_worker import ProviderProbeWorker
import os

# Get encryption key from environment
ROUTING_ENCRYPTION_KEY = os.getenv("ROUTING_ENCRYPTION_KEY")
if not ROUTING_ENCRYPTION_KEY:
    raise ValueError("ROUTING_ENCRYPTION_KEY environment variable must be set")

# Initialize services
routing_service = None
probe_worker = None


def get_routing_service(db: Session = Depends(get_db)) -> RoutingService:
    """Dependency to get routing service instance."""
    global routing_service
    if routing_service is None:
        routing_service = RoutingService(db, ROUTING_ENCRYPTION_KEY)
    return routing_service


def get_probe_worker() -> ProviderProbeWorker:
    """Dependency to get probe worker instance."""
    global probe_worker
    if probe_worker is None:
        probe_worker = ProviderProbeWorker(ROUTING_ENCRYPTION_KEY)
    return probe_worker


router = APIRouter(prefix="/routing", tags=["routing"])


class RouteRequest(BaseModel):
    capability: str
    requirements: Optional[Dict[str, Any]] = None
    prefer_cost: Optional[bool] = False
    max_retries: Optional[int] = 2


class ProviderInfo(BaseModel):
    id: int
    name: str
    display_name: str
    capabilities: List[str]
    models: List[Dict[str, Any]]
    priority: int
    is_active: bool
    score: Optional[float] = None


@router.get("/providers", response_model=List[ProviderInfo])
async def get_available_providers(
    service: RoutingService = Depends(get_routing_service),
):
    """Get list of all configured providers with their capabilities and status"""
    try:
        providers = await service.discover_providers()
        return [ProviderInfo(**provider) for provider in providers]
    except Exception as e:
        raise HTTPException(
            status_code=500, detail=f"Failed to discover providers: {str(e)}"
        )


@router.get("/providers/{capability}", response_model=List[ProviderInfo])
async def get_providers_for_capability(
    capability: str, service: RoutingService = Depends(get_routing_service)
):
    """Get providers that support a specific capability"""
    try:
        providers = await service.discover_providers()

        # Filter providers that support the capability
        suitable = []
        for provider in providers:
            if capability in provider["capabilities"]:
                suitable.append(ProviderInfo(**provider))

        return suitable
    except Exception as e:
        raise HTTPException(
            status_code=500, detail=f"Failed to get providers for capability: {str(e)}"
        )


@router.post("/route")
async def route_request(
    request: RouteRequest, service: RoutingService = Depends(get_routing_service)
):
    """Route a request to the best available provider"""
    try:
        result = await service.route_request(
            capability=request.capability, requirements=request.requirements
        )
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Routing failed: {str(e)}")


@router.get("/health")
async def routing_health(service: RoutingService = Depends(get_routing_service)):
    """Check if the routing system is operational"""
    try:
        providers = await service.discover_providers()
        healthy_providers = [p for p in providers if p.get("is_active", False)]

        return {
            "status": "healthy" if healthy_providers else "degraded",
            "providers_available": len(providers),
            "healthy_providers": len(healthy_providers),
            "routing_system": "active",
        }
    except Exception as e:
        return {"status": "error", "error": str(e), "routing_system": "failed"}
