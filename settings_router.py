from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from typing import List, Optional, Dict, Any
from sqlalchemy.orm import Session
from services.settings import SettingsService
from database import get_db

router = APIRouter(prefix="/settings", tags=["settings"])


class ProviderUpdate(BaseModel):
    display_name: Optional[str] = None
    capabilities: Optional[List[str]] = None
    default_model: Optional[str] = None
    metadata: Optional[Dict[str, Any]] = None


class ModelUpdate(BaseModel):
    provider_name: str
    params: Dict[str, Any]


class TestConnectionRequest(BaseModel):
    api_key: Optional[str] = None  # If not provided, use stored


class SettingsResponse(BaseModel):
    providers: Dict[str, Any]
    global_settings: Dict[str, Any]


@router.get("/", response_model=SettingsResponse)
async def get_settings(db: Session = Depends(get_db)):
    """Get current provider and model settings"""
    try:
        service = SettingsService(db)
        return service.get_all_settings()
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to get settings: {str(e)}")


@router.put("/providers/{provider_name}")
async def update_provider_settings(
    provider_name: str, data: ProviderUpdate, db: Session = Depends(get_db)
):
    """Update settings for a specific provider"""
    try:
        service = SettingsService(db)
        provider = service.update_provider(provider_name, data.dict(exclude_unset=True))
        return {
            "status": "success",
            "message": f"Settings updated for provider: {provider_name}",
            "provider": provider.name,
        }
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(
            status_code=500, detail=f"Failed to update provider settings: {str(e)}"
        )


@router.put("/models/{model_name}")
async def update_model_settings(
    model_name: str, data: ModelUpdate, db: Session = Depends(get_db)
):
    """Update settings for a specific model"""
    try:
        service = SettingsService(db)
        model = service.update_model(model_name, data.dict())
        return {
            "status": "success",
            "message": f"Settings updated for model: {model_name}",
            "model": model.name,
        }
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(
            status_code=500, detail=f"Failed to update model settings: {str(e)}"
        )


@router.post("/test-connection")
async def test_provider_connection(
    provider_name: str, request: TestConnectionRequest, db: Session = Depends(get_db)
):
    """Test connection to a provider's API"""
    try:
        service = SettingsService(db)
        result = service.test_connection(provider_name, request.api_key)

        if not result["success"]:
            raise HTTPException(
                status_code=400, detail=result.get("error", "Connection test failed")
            )

        return result

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Connection test failed: {str(e)}")


# ============================================================================
# NEW ENDPOINTS FOR ENHANCED PROVIDER MANAGEMENT
# ============================================================================


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
    role: Optional[str] = None  # "primary" or "fallback"


@router.post(
    "/providers/{provider_id}/test-prompt",
    response_model=ProviderTestWithPromptResponse,
)
async def test_provider_with_prompt(
    provider_id: int,
    request: ProviderTestWithPromptRequest,
    db: Session = Depends(get_db),
):
    """Test a provider with a custom prompt and return the full response"""
    try:
        import time
        import os
        from models.routing import RoutingProvider
        from providers import (
            OpenAIAdapter,
            AnthropicAdapter,
            GrokAdapter,
            DeepSeekAdapter,
            OllamaAdapter,
            LlamaCppAdapter,
            SilliconflowAdapter,
            MoonshotAdapter,
        )
        from services.encryption import EncryptionService

        start_time = time.time()

        # Get provider from database
        provider = (
            db.query(RoutingProvider).filter(RoutingProvider.id == provider_id).first()
        )
        if not provider:
            raise HTTPException(status_code=404, detail="Provider not found")

        if not provider.is_active:
            return ProviderTestWithPromptResponse(
                success=False,
                message="Provider is not active",
                latency=0,
            )

        # Get encryption key for decrypting API key
        encryption_key = os.getenv("ROUTING_ENCRYPTION_KEY")
        if not encryption_key:
            raise HTTPException(status_code=500, detail="Encryption key not configured")

        # Decrypt API key
        encryption_service = EncryptionService(encryption_key)
        api_key = encryption_service.decrypt(provider.api_key_encrypted)

        # Get appropriate adapter based on provider name
        adapters = {
            "openai": OpenAIAdapter,
            "anthropic": AnthropicAdapter,
            "grok": GrokAdapter,
            "deepseek": DeepSeekAdapter,
            "ollama": OllamaAdapter,
            "llamacpp": LlamaCppAdapter,
            "silliconflow": SilliconflowAdapter,
            "moonshot": MoonshotAdapter,
        }

        adapter_class = adapters.get(provider.name.lower())
        if not adapter_class:
            return ProviderTestWithPromptResponse(
                success=False,
                message=f"No adapter available for provider: {provider.name}",
                latency=0,
            )

        # Get provider adapter and test with prompt
        try:
            adapter = adapter_class(api_key, provider.base_url)

            # Use first available model
            model = provider.models[0]["name"] if provider.models else "default"

            # Make actual API call
            response = await adapter.complete(
                prompt=request.prompt,
                model=model,
                max_tokens=150,
            )

            latency = (time.time() - start_time) * 1000  # Convert to ms

            # Extract response content based on adapter response format
            content = ""
            if isinstance(response, dict):
                content = response.get("content", response.get("text", str(response)))
            else:
                content = str(response)

            return ProviderTestWithPromptResponse(
                success=True,
                message="Test successful",
                latency=round(latency, 2),
                response=content,
                model_used=model,
            )

        except Exception as e:
            latency = (time.time() - start_time) * 1000
            return ProviderTestWithPromptResponse(
                success=False,
                message=f"Provider API error: {str(e)}",
                latency=round(latency, 2),
            )

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=500, detail=f"Failed to test provider with prompt: {str(e)}"
        )


@router.post("/providers/reorder")
async def reorder_providers(
    request: ReorderProvidersRequest, db: Session = Depends(get_db)
):
    """Reorder providers by updating their priority based on the provided list"""
    try:
        from models.routing import RoutingProvider

        # Update priority for each provider based on position in list
        for index, provider_id in enumerate(request.provider_ids):
            provider = (
                db.query(RoutingProvider)
                .filter(RoutingProvider.id == provider_id)
                .first()
            )
            if provider:
                # Higher index = lower priority (inverted for UX)
                provider.priority = len(request.provider_ids) - index

        db.commit()

        return {
            "success": True,
            "message": "Provider order updated successfully",
        }

    except Exception as e:
        db.rollback()
        raise HTTPException(
            status_code=500, detail=f"Failed to reorder providers: {str(e)}"
        )


@router.post("/providers/{provider_id}/priority")
async def set_provider_priority(
    provider_id: int, request: SetProviderPriorityRequest, db: Session = Depends(get_db)
):
    """Set priority for a specific provider"""
    try:
        from models.routing import RoutingProvider

        provider = (
            db.query(RoutingProvider).filter(RoutingProvider.id == provider_id).first()
        )
        if not provider:
            raise HTTPException(status_code=404, detail="Provider not found")

        # Handle special roles
        if request.role == "primary":
            provider.priority = 100  # High priority for primary
        elif request.role == "fallback":
            provider.priority = 1  # Low priority for fallback
        else:
            provider.priority = request.priority

        db.commit()

        return {
            "success": True,
            "message": f"Priority set to {provider.priority} for {provider.display_name}",
            "provider_id": provider_id,
            "priority": provider.priority,
        }

    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        raise HTTPException(
            status_code=500, detail=f"Failed to set provider priority: {str(e)}"
        )
