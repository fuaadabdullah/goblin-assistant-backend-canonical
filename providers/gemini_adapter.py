"""
Google Gemini provider adapter for health checks and model discovery.
"""

import asyncio
import time
from typing import Dict, List, Optional, Any
import google.generativeai as genai
import logging

logger = logging.getLogger(__name__)


class GeminiAdapter:
    """Adapter for Google Gemini API provider operations."""

    def __init__(self, api_key: str, base_url: Optional[str] = None):
        """Initialize Gemini adapter.

        Args:
            api_key: Google AI API key
            base_url: Optional custom base URL (not used for Gemini)
        """
        self.api_key = api_key
        self.base_url = base_url
        genai.configure(api_key=api_key)
        self.client = genai

    async def health_check(self) -> Dict[str, Any]:
        """Perform health check on Google Gemini API.

        Returns:
            Dict containing health status and metrics
        """
        start_time = time.time()
        try:
            # Test with a simple generation to check API availability
            model = self.client.GenerativeModel("gemini-pro")
            await asyncio.get_event_loop().run_in_executor(
                None,
                lambda: model.generate_content(
                    "Hello", generation_config={"max_output_tokens": 10}
                ),
            )

            response_time = (time.time() - start_time) * 1000  # Convert to milliseconds

            return {
                "healthy": True,
                "response_time_ms": round(response_time, 2),
                "error_rate": 0.0,
                "available_models": len(self._get_available_models()),
                "timestamp": time.time(),
            }

        except Exception as e:
            response_time = (time.time() - start_time) * 1000
            logger.error(f"Gemini health check failed: {e}")

            return {
                "healthy": False,
                "response_time_ms": round(response_time, 2),
                "error_rate": 1.0,
                "error": str(e),
                "timestamp": time.time(),
            }

    async def list_models(self) -> List[Dict[str, Any]]:
        """List available Google Gemini models.

        Returns:
            List of model information dictionaries
        """
        try:
            # Return known Gemini models since the API doesn't provide a comprehensive list
            models = self._get_available_models()

            result = []
            for model_info in models:
                result.append(
                    {
                        "id": model_info["id"],
                        "name": model_info["name"],
                        "capabilities": model_info["capabilities"],
                        "context_window": model_info["context_window"],
                        "pricing": model_info["pricing"],
                    }
                )

            return result

        except Exception as e:
            logger.error(f"Failed to list Gemini models: {e}")
            return []

    def _get_available_models(self) -> List[Dict[str, Any]]:
        """Get list of available Gemini models with their specifications.

        Returns:
            List of model specifications
        """
        return [
            {
                "id": "gemini-pro",
                "name": "Gemini Pro",
                "capabilities": ["chat"],
                "context_window": 32768,
                "pricing": {"input": 0.00025, "output": 0.0005},  # per 1K characters
            },
            {
                "id": "gemini-pro-vision",
                "name": "Gemini Pro Vision",
                "capabilities": ["chat", "vision"],
                "context_window": 16384,
                "pricing": {"input": 0.00025, "output": 0.0005},
            },
            {
                "id": "gemini-1.5-pro",
                "name": "Gemini 1.5 Pro",
                "capabilities": ["chat", "vision"],
                "context_window": 2097152,  # 2M tokens
                "pricing": {"input": 0.00125, "output": 0.005},
            },
            {
                "id": "gemini-1.5-flash",
                "name": "Gemini 1.5 Flash",
                "capabilities": ["chat", "vision"],
                "context_window": 1048576,  # 1M tokens
                "pricing": {"input": 0.000075, "output": 0.0003},
            },
            {
                "id": "gemini-1.0-pro",
                "name": "Gemini 1.0 Pro",
                "capabilities": ["chat"],
                "context_window": 32768,
                "pricing": {"input": 0.00025, "output": 0.0005},
            },
        ]

    async def test_completion(
        self, model: str = "gemini-pro", max_tokens: int = 10
    ) -> Dict[str, Any]:
        """Test completion capability.

        Args:
            model: Model to test
            max_tokens: Maximum tokens for response

        Returns:
            Dict with test results
        """
        start_time = time.time()
        try:
            genai_model = self.client.GenerativeModel(model)
            response = await asyncio.get_event_loop().run_in_executor(
                None,
                lambda: genai_model.generate_content(
                    "Hello, test message",
                    generation_config={"max_output_tokens": max_tokens},
                ),
            )

            response_time = (time.time() - start_time) * 1000

            # Check if response was successful
            # Note: Gemini may return empty parts with finish_reason MAX_TOKENS or SAFETY
            # which still means the API call succeeded
            if response and response.candidates:
                success = True
            else:
                success = False

            return {
                "success": success,
                "response_time_ms": round(response_time, 2),
                "tokens_used": None,  # Gemini doesn't provide token counts in the same way
                "model": model,
            }

        except Exception as e:
            response_time = (time.time() - start_time) * 1000
            logger.error(f"Gemini completion test failed: {e}")

            return {
                "success": False,
                "response_time_ms": round(response_time, 2),
                "error": str(e),
                "model": model,
            }
