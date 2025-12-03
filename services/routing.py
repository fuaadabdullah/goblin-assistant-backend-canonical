"""
Routing service for provider discovery, health monitoring, and intelligent task routing.
"""

import uuid
from typing import Dict, List, Optional, Any
from datetime import datetime, timedelta
import logging
from sqlalchemy.orm import Session

from models.routing import RoutingProvider, ProviderMetric, RoutingRequest

from providers import (
    OpenAIAdapter,
    AnthropicAdapter,
    GrokAdapter,
    DeepSeekAdapter,
    OllamaAdapter,
    LlamaCppAdapter,
    SilliconflowAdapter,
    MoonshotAdapter,
    ElevenLabsAdapter,
)
from services.encryption import EncryptionService
from services.local_llm_routing import (
    select_model,
    get_system_prompt,
    get_routing_explanation,
    detect_intent,
    get_context_length,
    Intent,
    LatencyTarget,
)

logger = logging.getLogger(__name__)


class RoutingService:
    """Service for intelligent routing of AI tasks to appropriate providers."""

    def __init__(self, db: Session, encryption_key: str):
        """Initialize routing service.

        Args:
            db: Database session
            encryption_key: Key for decrypting API keys
        """
        self.db = db
        self.encryption_service = EncryptionService(encryption_key)
        self.adapters = {
            "openai": OpenAIAdapter,
            "anthropic": AnthropicAdapter,
            "grok": GrokAdapter,
            "deepseek": DeepSeekAdapter,
            "ollama": OllamaAdapter,
            "llamacpp": LlamaCppAdapter,
            "silliconflow": SilliconflowAdapter,
            "moonshot": MoonshotAdapter,
            "elevenlabs": ElevenLabsAdapter,
        }

    async def discover_providers(self) -> List[Dict[str, Any]]:
        """Discover all active providers and their capabilities.

        Returns:
            List of provider information dictionaries
        """
        providers = (
            self.db.query(RoutingProvider).filter(RoutingProvider.is_active).all()
        )

        result = []
        for provider in providers:
            # Decrypt API key
            try:
                api_key = self.encryption_service.decrypt(provider.api_key_encrypted)
            except Exception as e:
                logger.error(
                    f"Failed to decrypt API key for provider {provider.name}: {e}"
                )
                continue

            # Get adapter
            adapter_class = self.adapters.get(provider.name.lower())
            if not adapter_class:
                logger.warning(f"No adapter found for provider {provider.name}")
                continue

            # Initialize adapter
            adapter = adapter_class(api_key, provider.base_url)

            # Get models
            models = await adapter.list_models()

            result.append(
                {
                    "id": provider.id,
                    "name": provider.name,
                    "display_name": provider.display_name,
                    "capabilities": provider.capabilities,
                    "models": models,
                    "priority": provider.priority,
                    "is_active": provider.is_active,
                }
            )

        return result

    async def route_request(
        self, capability: str, requirements: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """Route a request to the best available provider.

        Args:
            capability: Required capability (e.g., "chat", "vision")
            requirements: Additional requirements for the request

        Returns:
            Dict with routing decision and provider info
        """
        request_id = str(uuid.uuid4())

        try:
            # Check if this is a chat request that can be handled by local LLMs
            if capability == "chat" and requirements:
                local_routing = await self._try_local_llm_routing(requirements)
                if local_routing:
                    # Log the routing decision
                    self._log_routing_request(
                        request_id=request_id,
                        capability=capability,
                        requirements=requirements,
                        selected_provider_id=local_routing.get("provider_id"),
                        success=True,
                    )

                    return {
                        "success": True,
                        "request_id": request_id,
                        "provider": local_routing["provider"],
                        "capability": capability,
                        "requirements": requirements,
                        "routing_explanation": local_routing.get("explanation"),
                        "recommended_params": local_routing.get("params"),
                        "system_prompt": local_routing.get("system_prompt"),
                    }

            # Find suitable providers
            candidates = await self._find_suitable_providers(capability, requirements)

            if not candidates:
                return {
                    "success": False,
                    "error": f"No providers available for capability: {capability}",
                    "request_id": request_id,
                }

            # Score and rank providers
            scored_providers = await self._score_providers(
                candidates, capability, requirements
            )

            if not scored_providers:
                return {
                    "success": False,
                    "error": "No healthy providers available",
                    "request_id": request_id,
                }

            # Select best provider
            selected_provider = scored_providers[0]

            # Log the routing decision
            self._log_routing_request(
                request_id=request_id,
                capability=capability,
                requirements=requirements,
                selected_provider_id=selected_provider["id"],
                success=True,
            )

            return {
                "success": True,
                "request_id": request_id,
                "provider": selected_provider,
                "capability": capability,
                "requirements": requirements or {},
            }

        except Exception as e:
            logger.error(f"Routing failed for capability {capability}: {e}")

            # Log failed routing
            self._log_routing_request(
                request_id=request_id,
                capability=capability,
                requirements=requirements,
                success=False,
                error_message=str(e),
            )

            return {"success": False, "error": str(e), "request_id": request_id}

    async def _try_local_llm_routing(
        self, requirements: Dict[str, Any]
    ) -> Optional[Dict[str, Any]]:
        """Try to route request to local LLM based on intelligent routing rules.

        Args:
            requirements: Request requirements including messages, latency_target, etc.

        Returns:
            Dict with local provider info and routing details, or None if not suitable
        """
        try:
            # Extract routing parameters
            messages = requirements.get("messages", [])
            if not messages:
                return None

            # Get optional routing hints
            intent = requirements.get("intent")
            if intent and isinstance(intent, str):
                try:
                    intent = Intent(intent)
                except ValueError:
                    intent = None

            latency_target = requirements.get("latency_target", "medium")
            if isinstance(latency_target, str):
                try:
                    latency_target = LatencyTarget(latency_target)
                except ValueError:
                    latency_target = LatencyTarget.MEDIUM

            context_provided = requirements.get("context")
            cost_priority = requirements.get("cost_priority", False)

            # Select model using routing logic
            model_id, params = select_model(
                messages=messages,
                intent=intent,
                latency_target=latency_target,
                context_provided=context_provided,
                cost_priority=cost_priority,
            )

            # Find Ollama provider
            ollama_provider = (
                self.db.query(RoutingProvider)
                .filter(RoutingProvider.name == "ollama", RoutingProvider.is_active)
                .first()
            )

            if not ollama_provider:
                logger.warning("Ollama provider not found or not active")
                return None

            # Get system prompt
            detected_intent = intent or detect_intent(messages)
            system_prompt = get_system_prompt(detected_intent)

            # Get routing explanation
            context_length = get_context_length(messages)
            if context_provided:
                from services.local_llm_routing import estimate_token_count

                context_length += estimate_token_count(context_provided)

            explanation = get_routing_explanation(
                model_id, detected_intent, context_length, latency_target
            )

            # Build provider info
            provider_info = {
                "id": ollama_provider.id,
                "name": ollama_provider.name,
                "display_name": ollama_provider.display_name,
                "model": model_id,
                "capabilities": ollama_provider.capabilities,
                "priority": ollama_provider.priority,
            }

            return {
                "provider": provider_info,
                "provider_id": ollama_provider.id,
                "params": params,
                "system_prompt": system_prompt,
                "explanation": explanation,
                "intent": detected_intent.value,
                "context_length": context_length,
            }

        except Exception as e:
            logger.error(f"Local LLM routing failed: {e}")
            return None

    async def _find_suitable_providers(
        self, capability: str, requirements: Optional[Dict[str, Any]] = None
    ) -> List[Dict[str, Any]]:
        """Find providers that can handle the given capability and requirements.

        Args:
            capability: Required capability
            requirements: Additional requirements

        Returns:
            List of suitable provider dictionaries
        """
        providers = await self.discover_providers()

        suitable = []
        for provider in providers:
            # Check if provider supports the capability
            if capability not in provider["capabilities"]:
                continue

            # Check additional requirements
            if requirements:
                if not self._check_requirements(provider, requirements):
                    continue

            suitable.append(provider)

        return suitable

    def _check_requirements(
        self, provider: Dict[str, Any], requirements: Dict[str, Any]
    ) -> bool:
        """Check if provider meets additional requirements.

        Args:
            provider: Provider information
            requirements: Requirements to check

        Returns:
            True if requirements are met
        """
        # Check model requirements
        if "model" in requirements:
            required_model = requirements["model"]
            if not any(model["id"] == required_model for model in provider["models"]):
                return False

        # Check context window requirements
        if "min_context_window" in requirements:
            min_window = requirements["min_context_window"]
            if not any(
                model["context_window"] >= min_window for model in provider["models"]
            ):
                return False

        # Check vision capability
        if requirements.get("vision_required", False):
            if "vision" not in provider["capabilities"]:
                return False

        return True

    async def _score_providers(
        self,
        providers: List[Dict[str, Any]],
        capability: str,
        requirements: Optional[Dict[str, Any]] = None,
    ) -> List[Dict[str, Any]]:
        """Score and rank providers based on health, performance, and cost.

        Args:
            providers: List of provider candidates
            capability: Required capability
            requirements: Additional requirements

        Returns:
            List of providers with scores, sorted by score descending
        """
        scored = []

        for provider in providers:
            score = await self._calculate_provider_score(
                provider, capability, requirements
            )
            if score > 0:  # Only include providers with positive scores (healthy)
                provider_with_score = provider.copy()
                provider_with_score["score"] = score
                scored.append(provider_with_score)

        # Sort by score descending
        scored.sort(key=lambda x: x["score"], reverse=True)
        return scored

    async def _calculate_provider_score(
        self,
        provider: Dict[str, Any],
        capability: str,
        requirements: Optional[Dict[str, Any]] = None,
    ) -> float:
        """Calculate a score for a provider based on multiple factors.

        Args:
            provider: Provider information
            capability: Required capability
            requirements: Additional requirements

        Returns:
            Score between 0-100 (0 = unusable, 100 = perfect)
        """
        base_score = 50.0  # Start with neutral score

        # Get recent health metrics
        health_score = await self._get_health_score(provider["id"])
        base_score += health_score * 0.4  # 40% weight on health

        # Priority bonus
        priority_bonus = provider["priority"] * 2.0
        base_score += priority_bonus

        # Cost factor (prefer cheaper providers)
        cost_penalty = await self._calculate_cost_penalty(provider, capability)
        base_score -= cost_penalty

        # Performance bonus (faster = better)
        performance_bonus = await self._get_performance_bonus(provider["id"])
        base_score += performance_bonus

        # Capability match bonus
        capability_bonus = self._calculate_capability_bonus(
            provider, capability, requirements
        )
        base_score += capability_bonus

        # Ensure score is within bounds
        return max(0.0, min(100.0, base_score))

    async def _get_health_score(self, provider_id: int) -> float:
        """Get health score for provider based on recent metrics.

        Args:
            provider_id: Provider ID

        Returns:
            Health score (-50 to 50)
        """
        # Get metrics from last hour
        one_hour_ago = datetime.utcnow() - timedelta(hours=1)
        metrics = (
            self.db.query(ProviderMetric)
            .filter(
                ProviderMetric.provider_id == provider_id,
                ProviderMetric.timestamp >= one_hour_ago,
            )
            .all()
        )

        if not metrics:
            return 0.0  # No data = neutral

        # Calculate average health metrics
        total_metrics = len(metrics)
        healthy_count = sum(1 for m in metrics if m.is_healthy)
        health_rate = healthy_count / total_metrics if total_metrics > 0 else 0

        # Average response time (prefer faster)
        avg_response_time = (
            sum(m.response_time_ms for m in metrics if m.response_time_ms)
            / len([m for m in metrics if m.response_time_ms])
            if metrics
            else 1000
        )

        # Response time score (faster = better, max 2000ms = 0 points)
        response_time_score = max(0, 25 - (avg_response_time / 80))

        # Health score: -50 (all unhealthy) to 50 (all healthy)
        health_score = (health_rate - 0.5) * 100

        return health_score + response_time_score

    async def _calculate_cost_penalty(
        self, provider: Dict[str, Any], capability: str
    ) -> float:
        """Calculate cost penalty for provider.

        Args:
            provider: Provider info
            capability: Required capability

        Returns:
            Cost penalty (0-20, higher = more expensive)
        """
        # Find cheapest model for capability
        min_cost = float("inf")
        for model in provider["models"]:
            if capability in model["capabilities"]:
                # Use input token cost as proxy
                cost = model["pricing"].get("input", 0.002)
                min_cost = min(min_cost, cost)

        if min_cost == float("inf"):
            return 10.0  # Default penalty

        # Penalty based on cost relative to baseline (0.001 = 0 penalty, 0.01 = 20 penalty)
        return min(20.0, (min_cost - 0.001) * 2000)

    async def _get_performance_bonus(self, provider_id: int) -> float:
        """Get performance bonus based on recent metrics.

        Args:
            provider_id: Provider ID

        Returns:
            Performance bonus (0-15)
        """
        # Get recent metrics
        one_hour_ago = datetime.utcnow() - timedelta(hours=1)
        metrics = (
            self.db.query(ProviderMetric)
            .filter(
                ProviderMetric.provider_id == provider_id,
                ProviderMetric.timestamp >= one_hour_ago,
            )
            .order_by(ProviderMetric.timestamp.desc())
            .limit(10)
            .all()
        )

        if not metrics:
            return 0.0

        # Average response time
        response_times = [m.response_time_ms for m in metrics if m.response_time_ms]
        if not response_times:
            return 0.0

        avg_response_time = sum(response_times) / len(response_times)

        # Bonus for faster response times (under 500ms = 15 points, over 2000ms = 0)
        if avg_response_time <= 500:
            return 15.0
        elif avg_response_time >= 2000:
            return 0.0
        else:
            return 15.0 * (2000 - avg_response_time) / 1500

    def _calculate_capability_bonus(
        self,
        provider: Dict[str, Any],
        capability: str,
        requirements: Optional[Dict[str, Any]] = None,
    ) -> float:
        """Calculate bonus for capability match.

        Args:
            provider: Provider info
            capability: Required capability
            requirements: Additional requirements

        Returns:
            Capability bonus (0-10)
        """
        bonus = 0.0

        # Base capability match
        if capability in provider["capabilities"]:
            bonus += 5.0

        # Specific model requirement
        if requirements and "model" in requirements:
            required_model = requirements["model"]
            if any(model["id"] == required_model for model in provider["models"]):
                bonus += 5.0

        return bonus

    def _log_routing_request(
        self,
        request_id: str,
        capability: str,
        requirements: Optional[Dict[str, Any]] = None,
        selected_provider_id: Optional[int] = None,
        success: bool = True,
        error_message: Optional[str] = None,
    ) -> None:
        """Log a routing request.

        Args:
            request_id: Unique request ID
            capability: Requested capability
            requirements: Request requirements
            selected_provider_id: ID of selected provider
            success: Whether routing was successful
            error_message: Error message if failed
        """
        try:
            routing_request = RoutingRequest(
                request_id=request_id,
                capability=capability,
                requirements=requirements,
                selected_provider_id=selected_provider_id,
                success=success,
                error_message=error_message,
            )
            self.db.add(routing_request)
            self.db.commit()
        except Exception as e:
            logger.error(f"Failed to log routing request: {e}")
            self.db.rollback()
