"""
Ollama provider adapter for local LLM operations.
"""

import asyncio
import time
from typing import Dict, List, Optional, Any
import httpx
import logging

logger = logging.getLogger(__name__)


class OllamaAdapter:
    """Adapter for Ollama local LLM provider operations."""

    def __init__(self, api_key: str, base_url: Optional[str] = None):
        """Initialize Ollama adapter.

        Args:
            api_key: API key for the local proxy
            base_url: Optional custom base URL (defaults to local proxy)
        """
        self.api_key = api_key
        self.base_url = base_url or "http://localhost:8002"
        self.client = httpx.AsyncClient(timeout=120.0)

    async def health_check(self) -> Dict[str, Any]:
        """Perform health check on Ollama via local proxy.

        Returns:
            Dict containing health status and metrics
        """
        start_time = time.time()
        try:
            response = await self.client.get(f"{self.base_url}/health")
            response_time = (time.time() - start_time) * 1000

            if response.status_code == 200:
                # Get models to check if Ollama is responsive
                models_response = await self.client.get(
                    f"{self.base_url}/models", headers={"x-api-key": self.api_key}
                )

                available_models = 0
                if models_response.status_code == 200:
                    data = models_response.json()
                    available_models = len(data.get("models", {}).get("ollama", []))

                return {
                    "healthy": True,
                    "response_time_ms": round(response_time, 2),
                    "error_rate": 0.0,
                    "available_models": available_models,
                    "timestamp": time.time(),
                }
            else:
                return {
                    "healthy": False,
                    "response_time_ms": round(response_time, 2),
                    "error_rate": 1.0,
                    "error": f"HTTP {response.status_code}",
                    "timestamp": time.time(),
                }

        except Exception as e:
            response_time = (time.time() - start_time) * 1000
            logger.error(f"Ollama health check failed: {e}")

            return {
                "healthy": False,
                "response_time_ms": round(response_time, 2),
                "error_rate": 1.0,
                "error": str(e),
                "timestamp": time.time(),
            }

    async def list_models(self) -> List[Dict[str, Any]]:
        """List available Ollama models via local proxy.

        Returns:
            List of model information dictionaries
        """
        try:
            response = await self.client.get(
                f"{self.base_url}/models", headers={"x-api-key": self.api_key}
            )

            if response.status_code != 200:
                logger.error(
                    f"Failed to list Ollama models: HTTP {response.status_code}"
                )
                return []

            data = response.json()
            ollama_models = data.get("models", {}).get("ollama", [])

            models = []
            for model_name in ollama_models:
                models.append(
                    {
                        "id": model_name,
                        "name": model_name,
                        "capabilities": ["chat"],  # Ollama models support chat
                        "context_window": self._get_context_window(model_name),
                        "pricing": {
                            "input": 0.0,
                            "output": 0.0,
                        },  # Local models are free
                        "provider": "ollama",
                        "local": True,
                    }
                )

            return models

        except Exception as e:
            logger.error(f"Failed to list Ollama models: {e}")
            return []

    def _get_context_window(self, model_name: str) -> int:
        """Get context window size for Ollama model.

        Args:
            model_name: Ollama model name

        Returns:
            Context window size in tokens
        """
        # Common context windows for popular Ollama models
        context_windows = {
            "phi3:3.8b": 4096,
            "gemma:2b": 8192,
            "qwen2.5:3b": 32768,
            "deepseek-coder:1.3b": 16384,
            "llama2:7b": 4096,
            "llama2:13b": 4096,
            "mistral:7b": 8192,
            "codellama:7b": 16384,
            "codellama:13b": 16384,
        }

        # Default to 4096 for unknown models
        return context_windows.get(model_name, 4096)

    async def chat(
        self,
        model: str,
        messages: List[Dict[str, str]],
        temperature: float = 0.7,
        max_tokens: int = 1024,
        top_p: float = 0.9,
        **kwargs: Any,
    ) -> str:
        """Send chat completion request via local proxy.

        Args:
            model: Model name to use
            messages: List of message dictionaries with role and content
            temperature: Sampling temperature (0.0 to 2.0)
            max_tokens: Maximum tokens in response
            top_p: Nucleus sampling parameter
            **kwargs: Additional parameters to pass to the API

        Returns:
            The text content of the model's response

        Raises:
            Exception: If the API request fails
        """
        try:
            payload = {
                "model": model,
                "messages": messages,
                "options": {
                    "temperature": temperature,
                    "num_predict": max_tokens,
                    "top_p": top_p,
                },
                "stream": False,
            }

            response = await self.client.post(
                f"{self.base_url}/api/chat",
                json=payload,
                headers={"x-api-key": self.api_key} if self.api_key else {},
            )

            if response.status_code != 200:
                error_text = response.text
                logger.error(
                    f"Ollama chat failed: HTTP {response.status_code} - {error_text}"
                )
                raise Exception(f"HTTP {response.status_code}: {error_text}")

            data = response.json()

            # Extract content from Ollama response
            # Format: {"model": "...", "message": {"role": "...", "content": "..."}, ...}
            if "message" in data and "content" in data["message"]:
                return data["message"]["content"]
            else:
                logger.error(f"Unexpected response format: {data}")
                raise Exception(f"Unexpected response format from Ollama")

        except Exception as e:
            logger.error(f"Ollama chat request failed: {e}")
            raise

    async def test_completion(
        self, model: str = "phi3:3.8b", max_tokens: int = 10
    ) -> Dict[str, Any]:
        """Test completion capability via local proxy.

        Args:
            model: Model to test
            max_tokens: Maximum tokens for response

        Returns:
            Dict with test results
        """
        start_time = time.time()
        try:
            # Use the new chat method for consistency
            await self.chat(
                model=model,
                messages=[{"role": "user", "content": "Hello, test message"}],
                max_tokens=max_tokens,
            )

            response_time = (time.time() - start_time) * 1000

            return {
                "success": True,
                "response_time_ms": round(response_time, 2),
                "model": model,
                "local": True,
            }

        except Exception as e:
            response_time = (time.time() - start_time) * 1000
            logger.error(f"Ollama completion test failed: {e}")

            return {
                "success": False,
                "response_time_ms": round(response_time, 2),
                "error": str(e),
                "model": model,
            }
