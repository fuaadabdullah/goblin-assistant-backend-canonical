"""
Chat API endpoint with intelligent routing to local and cloud LLMs.
Uses the routing service to select the best model based on request characteristics.
"""

from fastapi import APIRouter, HTTPException, Depends, Header
from pydantic import BaseModel, Field
from typing import List, Optional, Dict, Any
from sqlalchemy.orm import Session
import logging
import os

from database import get_db
from services.routing import RoutingService
from services.output_verification import VerificationPipeline
from providers import (
    OllamaAdapter,
    GrokAdapter,
    OpenAIAdapter,
    AnthropicAdapter,
    DeepSeekAdapter,
)

logger = logging.getLogger(__name__)

# Get encryption key from environment
ROUTING_ENCRYPTION_KEY = os.getenv("ROUTING_ENCRYPTION_KEY")
if not ROUTING_ENCRYPTION_KEY:
    raise ValueError("ROUTING_ENCRYPTION_KEY environment variable must be set")

router = APIRouter(prefix="/chat", tags=["chat"])


class ChatMessage(BaseModel):
    role: str = Field(
        ..., description="Role of the message sender (user, assistant, system)"
    )
    content: str = Field(..., description="Content of the message")


class ChatCompletionRequest(BaseModel):
    messages: List[ChatMessage] = Field(
        ..., description="List of messages in the conversation"
    )
    model: Optional[str] = Field(
        None,
        description="Specific model to use (optional, auto-routed if not provided)",
    )
    intent: Optional[str] = Field(
        None, description="Explicit intent (code-gen, creative, rag, chat, etc.)"
    )
    latency_target: Optional[str] = Field(
        "medium", description="Latency requirement (ultra_low, low, medium, high)"
    )
    context: Optional[str] = Field(
        None, description="Additional context for RAG/retrieval"
    )
    cost_priority: Optional[bool] = Field(
        False, description="Prioritize cost over quality"
    )
    stream: Optional[bool] = Field(False, description="Stream the response")
    temperature: Optional[float] = Field(None, description="Override temperature")
    max_tokens: Optional[int] = Field(None, description="Override max tokens")
    top_p: Optional[float] = Field(None, description="Override top_p")
    enable_verification: Optional[bool] = Field(
        True, description="Enable output safety verification (default: True)"
    )
    enable_confidence_scoring: Optional[bool] = Field(
        True, description="Enable confidence scoring and escalation (default: True)"
    )
    auto_escalate: Optional[bool] = Field(
        True,
        description="Automatically escalate to better model if confidence is low (default: True)",
    )


class ChatCompletionResponse(BaseModel):
    id: str
    model: str
    provider: str
    intent: Optional[str] = None
    routing_explanation: Optional[str] = None
    verification_result: Optional[Dict[str, Any]] = None
    confidence_result: Optional[Dict[str, Any]] = None
    escalated: Optional[bool] = False
    original_model: Optional[str] = None
    choices: List[Dict[str, Any]]
    usage: Optional[Dict[str, int]] = None


def get_routing_service(db: Session = Depends(get_db)) -> RoutingService:
    """Dependency to get routing service instance."""
    return RoutingService(db, ROUTING_ENCRYPTION_KEY)


@router.post("/completions", response_model=ChatCompletionResponse)
async def create_chat_completion(
    request: ChatCompletionRequest,
    service: RoutingService = Depends(get_routing_service),
    x_api_key: Optional[str] = Header(
        None, description="Optional API key for authentication"
    ),
):
    """
    Create a chat completion with intelligent routing to the best model.

    This endpoint automatically selects the optimal local or cloud LLM based on:
    - Intent (code-gen, creative, rag, chat, classification, etc.)
    - Context length (short vs long documents)
    - Latency requirements (ultra-low, low, medium, high)
    - Cost priority (optimize for cost vs quality)

    Examples:

    1. Code Generation (routes to mistral:7b):
       {
         "messages": [{"role": "user", "content": "Write a Python function to sort a list"}]
       }

    2. Quick Status Check (routes to gemma:2b):
       {
         "messages": [{"role": "user", "content": "What's the status?"}],
         "latency_target": "ultra_low"
       }

    3. Long Document RAG (routes to qwen2.5:3b):
       {
         "messages": [{"role": "user", "content": "Summarize the key points"}],
         "context": "<long document>",
         "intent": "rag"
       }

    4. Conversational Chat (routes to phi3:3.8b):
       {
         "messages": [
           {"role": "user", "content": "Hi!"},
           {"role": "assistant", "content": "Hello!"},
           {"role": "user", "content": "Can you help me?"}
         ],
         "latency_target": "low"
       }
    """
    try:
        # Convert messages to dict format
        messages = [
            {"role": msg.role, "content": msg.content} for msg in request.messages
        ]

        # Build requirements for routing
        requirements = {
            "messages": messages,
            "intent": request.intent,
            "latency_target": request.latency_target,
            "context": request.context,
            "cost_priority": request.cost_priority,
        }

        # If model is specified, add it to requirements
        if request.model:
            requirements["model"] = request.model

        # Route the request
        routing_result = await service.route_request(
            capability="chat", requirements=requirements
        )

        if not routing_result.get("success"):
            raise HTTPException(
                status_code=503,
                detail=f"No suitable provider available: {routing_result.get('error')}",
            )

        provider_info = routing_result["provider"]
        selected_model = provider_info.get("model", request.model or "auto-selected")

        # Get recommended parameters (or use provided overrides)
        recommended_params = routing_result.get("recommended_params", {})
        temperature = (
            request.temperature
            if request.temperature is not None
            else recommended_params.get("temperature", 0.2)
        )
        max_tokens = (
            request.max_tokens
            if request.max_tokens is not None
            else recommended_params.get("max_tokens", 512)
        )
        top_p = (
            request.top_p
            if request.top_p is not None
            else recommended_params.get("top_p", 0.95)
        )

        # Get system prompt if available
        system_prompt = routing_result.get("system_prompt")
        if system_prompt and not any(msg["role"] == "system" for msg in messages):
            messages = [{"role": "system", "content": system_prompt}] + messages

        # Initialize the adapter for the selected provider
        # For now, we'll focus on Ollama (local LLMs)
        if provider_info["name"].lower() == "ollama":
            # Get Ollama configuration - prefer Kalmatura for production
            use_local_llm = os.getenv("USE_LOCAL_LLM", "false").lower() == "true"

            if use_local_llm:
                # Local development mode
                ollama_base_url = os.getenv("LOCAL_LLM_PROXY_URL", "http://localhost:11434")
                ollama_api_key = os.getenv("LOCAL_LLM_API_KEY", "")
            else:
                # Production mode - use Kalmatura-hosted LLM runtime
                ollama_base_url = os.getenv("KALMATURA_LLM_URL", "http://localhost:11434")
                ollama_api_key = os.getenv("KALMATURA_LLM_API_KEY", "")

            adapter = OllamaAdapter(ollama_api_key, ollama_base_url)

            adapter = OllamaAdapter(ollama_api_key, ollama_base_url)

            # Initialize verification pipeline if needed
            verification_pipeline = None
            if request.enable_verification or request.enable_confidence_scoring:
                verification_pipeline = VerificationPipeline(adapter)

            # Track escalation attempts
            original_model = selected_model
            escalated = False
            max_escalations = 2
            escalation_count = 0

            response_text = None
            verification_result = None
            confidence_result = None

            # Attempt generation with escalation loop
            while escalation_count <= max_escalations:
                # Make the completion request
                response_text = await adapter.chat(
                    model=selected_model,
                    messages=messages,
                    temperature=temperature,
                    max_tokens=max_tokens,
                    top_p=top_p,
                )

                # If verification/scoring disabled, accept immediately
                if not (
                    request.enable_verification or request.enable_confidence_scoring
                ):
                    break

                # Run verification and confidence scoring
                (
                    verification_result,
                    confidence_result,
                ) = await verification_pipeline.verify_and_score(
                    original_prompt=messages[-1]["content"],  # Get last user message
                    model_output=response_text,
                    model_used=selected_model,
                    context={
                        "intent": request.intent,
                        "latency_target": request.latency_target,
                    },
                    skip_verification=not request.enable_verification,
                )

                # Check if we should reject the output
                if verification_pipeline.should_reject_output(
                    verification_result, confidence_result
                ):
                    raise HTTPException(
                        status_code=422,
                        detail={
                            "error": "Output rejected due to safety or quality concerns",
                            "verification": {
                                "is_safe": verification_result.is_safe,
                                "safety_score": verification_result.safety_score,
                                "issues": verification_result.issues,
                            },
                            "confidence": {
                                "score": confidence_result.confidence_score,
                                "reasoning": confidence_result.reasoning,
                            },
                        },
                    )

                # Check if we should escalate
                if request.auto_escalate and verification_pipeline.should_escalate(
                    verification_result, confidence_result, selected_model
                ):
                    next_model = verification_pipeline.get_escalation_target(
                        selected_model
                    )

                    if next_model and escalation_count < max_escalations:
                        logger.info(
                            f"Escalating from {selected_model} to {next_model} "
                            f"(confidence: {confidence_result.confidence_score:.2f})"
                        )
                        selected_model = next_model
                        escalated = True
                        escalation_count += 1
                        continue

                # If we get here, accept the output
                break

            # Build response
            response_data = {
                "id": routing_result["request_id"],
                "model": selected_model,
                "provider": provider_info["display_name"],
                "intent": routing_result.get("intent"),
                "routing_explanation": routing_result.get("routing_explanation"),
                "choices": [
                    {
                        "index": 0,
                        "message": {"role": "assistant", "content": response_text},
                        "finish_reason": "stop",
                    }
                ],
                "usage": {
                    "prompt_tokens": routing_result.get("context_length", 0),
                    "completion_tokens": len(response_text.split()),
                    "total_tokens": routing_result.get("context_length", 0)
                    + len(response_text.split()),
                },
            }

            # Add verification results if enabled
            if verification_result:
                response_data["verification_result"] = {
                    "is_safe": verification_result.is_safe,
                    "safety_score": verification_result.safety_score,
                    "issues": verification_result.issues,
                    "explanation": verification_result.explanation,
                }

            if confidence_result:
                response_data["confidence_result"] = {
                    "confidence_score": confidence_result.confidence_score,
                    "reasoning": confidence_result.reasoning,
                    "recommended_action": confidence_result.recommended_action,
                }

            if escalated:
                response_data["escalated"] = True
                response_data["original_model"] = original_model

            return ChatCompletionResponse(**response_data)

        else:
            # Handle cloud providers (OpenAI, Anthropic, Grok, DeepSeek, etc.)
            provider_name = provider_info["name"].lower()

            # Map provider names to adapter classes and their env var keys
            provider_adapters = {
                "openai": (OpenAIAdapter, "OPENAI_API_KEY", None),
                "anthropic": (AnthropicAdapter, "ANTHROPIC_API_KEY", None),
                "grok": (GrokAdapter, "GROK_API_KEY", "https://api.x.ai/v1"),
                "deepseek": (DeepSeekAdapter, "DEEPSEEK_API_KEY", None),
            }

            if provider_name not in provider_adapters:
                raise HTTPException(
                    status_code=501,
                    detail=f"Provider {provider_info['name']} not yet implemented in chat endpoint",
                )

            # Get adapter class, API key env var, and base URL
            adapter_class, api_key_env, base_url = provider_adapters[provider_name]
            api_key = os.getenv(api_key_env)

            if not api_key:
                raise HTTPException(
                    status_code=500,
                    detail=f"API key not configured for provider {provider_info['name']}",
                )

            # Initialize adapter
            adapter = adapter_class(api_key, base_url)

            # Make the completion request
            response_text = await adapter.chat(
                model=selected_model,
                messages=messages,
                temperature=temperature,
                max_tokens=max_tokens,
                top_p=top_p,
            )

            # Build response
            response_data = {
                "id": routing_result["request_id"],
                "model": selected_model,
                "provider": provider_info["display_name"],
                "intent": routing_result.get("intent"),
                "routing_explanation": routing_result.get("routing_explanation"),
                "choices": [
                    {
                        "index": 0,
                        "message": {"role": "assistant", "content": response_text},
                        "finish_reason": "stop",
                    }
                ],
                "usage": {
                    "prompt_tokens": routing_result.get("context_length", 0),
                    "completion_tokens": len(response_text.split()),
                    "total_tokens": routing_result.get("context_length", 0)
                    + len(response_text.split()),
                },
            }

            return ChatCompletionResponse(**response_data)

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Chat completion failed: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Chat completion failed: {str(e)}")


@router.get("/models")
async def list_available_models(
    service: RoutingService = Depends(get_routing_service),
):
    """
    List all available models across all providers.
    Includes routing recommendations for each model.
    """
    try:
        providers = await service.discover_providers()

        models = []
        for provider in providers:
            for model in provider["models"]:
                models.append(
                    {
                        "id": model["id"],
                        "provider": provider["display_name"],
                        "provider_name": provider["name"],
                        "capabilities": model.get("capabilities", []),
                        "context_window": model.get("context_window", 0),
                        "pricing": model.get("pricing", {}),
                    }
                )

        # Add routing recommendations
        routing_recommendations = {
            "gemma:2b": "Ultra-fast responses, classification, status checks",
            "phi3:3.8b": "Low-latency chat, conversational UI",
            "qwen2.5:3b": "Long context (32K), multilingual, RAG",
            "mistral:7b": "High quality, code generation, creative writing",
        }

        for model in models:
            model["routing_recommendation"] = routing_recommendations.get(
                model["id"], "General purpose"
            )

        return {
            "models": models,
            "total_count": len(models),
            "routing_info": {
                "automatic": True,
                "factors": [
                    "intent",
                    "context_length",
                    "latency_target",
                    "cost_priority",
                ],
                "documentation": "/docs/LOCAL_LLM_ROUTING.md",
            },
        }

    except Exception as e:
        logger.error(f"Failed to list models: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to list models: {str(e)}")


@router.get("/routing-info")
async def get_routing_info():
    """
    Get information about the intelligent routing system.
    """
    return {
        "routing_system": "intelligent",
        "version": "1.0",
        "factors": {
            "intent": {
                "description": "Detected or explicit intent (code-gen, creative, rag, chat, etc.)",
                "options": [
                    "code-gen",
                    "creative",
                    "explain",
                    "summarize",
                    "rag",
                    "retrieval",
                    "chat",
                    "classification",
                    "status",
                    "translation",
                ],
                "auto_detect": True,
            },
            "latency_target": {
                "description": "Target latency for response",
                "options": ["ultra_low", "low", "medium", "high"],
                "default": "medium",
            },
            "context_length": {
                "description": "Length of the conversation context",
                "thresholds": {
                    "short": "< 2000 tokens",
                    "medium": "2000-8000 tokens",
                    "long": "> 8000 tokens (uses qwen2.5:3b with 32K window)",
                },
            },
            "cost_priority": {
                "description": "Prioritize cost over quality",
                "default": False,
                "effect": "Routes to smaller, faster models when enabled",
            },
        },
        "models": {
            "gemma:2b": {
                "size": "1.7GB",
                "context": "8K tokens",
                "latency": "5-8s",
                "best_for": ["ultra_fast", "classification", "status_checks"],
                "params": {"temperature": 0.0, "max_tokens": 40},
            },
            "phi3:3.8b": {
                "size": "2.2GB",
                "context": "4K tokens",
                "latency": "10-12s",
                "best_for": ["low_latency_chat", "conversational_ui", "quick_qa"],
                "params": {"temperature": 0.15, "max_tokens": 128},
            },
            "qwen2.5:3b": {
                "size": "1.9GB",
                "context": "32K tokens",
                "latency": "14s",
                "best_for": [
                    "long_context",
                    "multilingual",
                    "rag",
                    "document_retrieval",
                ],
                "params": {"temperature": 0.0, "max_tokens": 1024},
            },
            "mistral:7b": {
                "size": "4.4GB",
                "context": "8K tokens",
                "latency": "14-15s",
                "best_for": [
                    "high_quality",
                    "code_generation",
                    "creative_writing",
                    "explanations",
                ],
                "params": {"temperature": 0.2, "max_tokens": 512},
            },
        },
        "cost": {
            "per_request": "$0 (self-hosted)",
            "monthly_infrastructure": "$15-20",
            "savings_vs_cloud": "86-92% ($110-240/month)",
        },
    }
